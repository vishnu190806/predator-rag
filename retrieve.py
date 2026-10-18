import os
import re
import sys
import torch
import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# =====================================================
# CONFIGURATION
# =====================================================
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "workspace_chunks"
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"

# Lazy-loaded global instances
_db_client = None
_collection = None
_embedder = None
_reranker = None
_bm25 = None
_corpus_data = None  # maps index to document data

def get_db():
    global _db_client, _collection
    if _db_client is None:
        _db_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        # Use get_or_create so retrieval doesn't crash before any PDF is ingested
        _collection = _db_client.get_or_create_collection(COLLECTION_NAME)
    return _collection

def _get_device():
    """Prefer CUDA, fall back to CPU.

    Measured Oct 2026 (RTX 4070 Laptop, bge-base-en-v1.5, real ~1600-char
    chunks): 64-batch encodes at ~13ms/chunk on CUDA vs ~81ms/chunk on CPU
    (~6x). An early CPU-vs-CUDA comparison looked tied only because it
    encoded 64 copies of one short string — not representative.
    VRAM budget with the serving config (llama3.1:8b + NUM_CTX=4096):
    ~5.8GB of 8GB with the embedder resident, leaving ~2.4GB headroom.
    (The old 7.9GB worst case came from the retired 12k context, not the
    embedder.) If VRAM pressure ever returns, pin this to "cpu": queries
    cost only ~25ms there and bulk ingest is covered by ./embed_cache.
    """
    return "cuda" if torch.cuda.is_available() else "cpu"

def get_embedder():
    global _embedder
    if _embedder is None:
        device = _get_device()
        print(f"Loading Embedding Model on {device.upper()}...")
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    return _embedder

def get_reranker():
    global _reranker
    if _reranker is None:
        device = _get_device()
        print(f"Loading Reranker Model on {device.upper()}...")
        _reranker = CrossEncoder(RERANKER_MODEL_NAME, device=device)
    return _reranker

def tokenize(text):
    return re.findall(r"\w+", text.lower())


def get_content_key(hit):
    """Deduplication identity for a retrieval hit."""
    m = hit["metadata"]
    text_snippet = hit["text"][:100]
    return (m.get("file"), m.get("section"), m.get("page"), text_snippet)


# Reciprocal Rank Fusion constant (standard k=60, unchanged since the stress
# campaign) and the additive BM25 score-quality term.
RRF_K = 60

# Additive normalized-BM25 term (measured Oct 17 2026 on 60 real-world
# questions, see eval_realworld/simulate_fusion.py): five queries placed
# their value-bearing chunk at fused rank 7-10 while the chunk was
# BM25-dominant but ABSENT from the dense top-20 (vector_distance = -1).
# Raising BM25's RRF rank weight made it WORSE (competitors occupy nearby
# BM25 ranks; targets fell out of the top-20) because rank position cannot
# express score quality. The additive term does: rare-token exact hits
# (USGS ids, "United Kingdom") normalize to ~1.0 of the top-20 BM25 maximum;
# generic keyword chunks sit at ~0.2-0.5. alpha=0.05 was the smallest sweep
# value that recovered the misses (World Bank rank 7->3, USGS id 10->1)
# with no deterministic regression on the other questions. It only affects
# queries whose lexical terms actually match the rare token; purely
# semantic misses (the answer word not in the query) stay dense-driven.
BM25_SCORE_WEIGHT = 0.05


def _fuse_hybrid(vector_hits, bm25_hits, bm25_max=0.0,
                 alpha=BM25_SCORE_WEIGHT, k=RRF_K):
    """Reciprocal Rank Fusion (k=60) + additive normalized-BM25 term.

    Each distinct content key contributes once per source at its BEST rank:
    duplicate chunks (same file/section/page/snippet, e.g. after a re-ingest)
    must not stack RRF mass and crowd out diverse hits. The sparse pass adds
    `alpha * (bm25_score / bm25_max)` so a chunk containing the only corpus
    occurrence of a rare query token outranks chunks that merely share
    generic vocabulary — resting on BM25 score quality, not rank order.
    """
    scores = {}
    seen_dense, seen_sparse = set(), set()

    for rank, hit in enumerate(vector_hits):
        key = get_content_key(hit)
        if key in seen_dense:
            continue
        seen_dense.add(key)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)

    for rank, hit in enumerate(bm25_hits):
        key = get_content_key(hit)
        if key in seen_sparse:
            continue
        seen_sparse.add(key)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
        if alpha > 0.0 and bm25_max > 0.0:
            scores[key] += (alpha
                            * float(hit.get("bm25_score", 0.0)) / bm25_max)

    key_to_hit = {}
    seen_texts = set()
    for hit in vector_hits + bm25_hits:
        key = get_content_key(hit)
        if key not in key_to_hit:
            # Near-duplicate guard: identical chunk text indexed twice
            # (e.g. re-upload) contributes only once.
            th = hash(hit["text"])
            if th in seen_texts:
                continue
            seen_texts.add(th)
            key_to_hit[key] = hit

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    hits = [key_to_hit[key] for key, _ in ranked if key in key_to_hit]
    for i, hit in enumerate(hits, 1):
        hit["rerank_score"] = hit["rrf_score"] = scores[get_content_key(hit)]
    return hits

def initialize_retrieval_components():
    global _bm25, _corpus_data
    collection = get_db()
    current_count = collection.count()
    
    if _bm25 is None or _corpus_data is None or len(_corpus_data) != current_count:
        if current_count == 0:
            _corpus_data = []
            _bm25 = None
            return
            
        print("Initializing BM25 index and loading documents...")
        # Load all documents for BM25 and RRF correlation
        data = collection.get(include=["documents", "metadatas"])
        
        documents = data["documents"]
        metadatas = data["metadatas"]
        ids = data["ids"]
        
        _corpus_data = []
        tokenized_corpus = []
        
        for idx in range(len(ids)):
            doc_text = documents[idx]
            _corpus_data.append({
                "id": ids[idx],
                "text": doc_text,
                "metadata": metadatas[idx]
            })
            tokenized_corpus.append(tokenize(doc_text))
            
        _bm25 = BM25Okapi(tokenized_corpus)
        print(f"BM25 index initialized with {len(_corpus_data)} documents.")

def retrieve_formulas(query, limit=3):
    """
    Search specifically for formulas matching the query.
    """
    collection = get_db()
    if collection.count() == 0:
        return []
        
    embedder = get_embedder()
    query_emb = embedder.encode([query])[0].tolist()
    
    # Query ChromaDB with a metadata filter for type='formula'
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=limit,
        where={"type": "formula"}
    )
    
    hits = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i]
            })
    return hits

def retrieve(query, limit=6, prefetch_limit=20, file_filter=None):
    """
    Hybrid search combining ChromaDB dense vector search and BM25 sparse search,
    fused via Reciprocal Rank Fusion (RRF, k=60).

    file_filter: optional filename (or list) restricting BOTH dense (Chroma
    `where`) and sparse (post-filter) retrieval to selected workspace docs.

    Timings on 7868-chunk corpus (Oct 2026): encode ~10-25ms, dense ~2-37ms,
    BM25 ~8-29ms, total ~50-90ms. Retrieval is NOT the pipeline bottleneck;
    keep prefetch small and do not add a reranker (measured +1.5s, -10% recall).
    """
    collection = get_db()
    if collection.count() == 0:
        return []
        
    embedder = get_embedder()
    # reranker = get_reranker()
    
    # Ensure BM25 is loaded
    initialize_retrieval_components()
    
    # 1. Vector Search (ChromaDB)
    query_emb = embedder.encode([query])[0].tolist()
    where = None
    if file_filter:
        names = [file_filter] if isinstance(file_filter, str) else list(file_filter)
        where = {"file": names[0]} if len(names) == 1 else {"file": {"$in": names}}
    vec_results = collection.query(
        query_embeddings=[query_emb],
        n_results=prefetch_limit,
        where=where
    )
    
    vector_hits = []
    if vec_results["ids"] and vec_results["ids"][0]:
        for i in range(len(vec_results["ids"][0])):
            vector_hits.append({
                "id": vec_results["ids"][0][i],
                "text": vec_results["documents"][0][i],
                "metadata": vec_results["metadatas"][0][i],
                "vector_distance": vec_results["distances"][0][i]
            })
            
    # 2. BM25 Search
    tokenized_query = tokenize(query)
    bm25_scores = _bm25.get_scores(tokenized_query)
    top_indices = np.argsort(bm25_scores)[::-1][:prefetch_limit]
    
    bm25_hits = []
    allowed = None
    if file_filter:
        allowed = {file_filter} if isinstance(file_filter, str) else set(file_filter)
    for idx in top_indices:
        if bm25_scores[idx] > 0.0:
            hit = _corpus_data[idx]
            if allowed is not None and hit["metadata"].get("file") not in allowed:
                continue
            hit = dict(hit)  # copy: do not mutate the shared corpus cache
            hit["bm25_score"] = float(bm25_scores[idx])
            bm25_hits.append(hit)
    bm25_max = max((h["bm25_score"] for h in bm25_hits), default=0.0)

    # 3. Hybrid fusion: RRF (k=60) + additive normalized-BM25 term
    # (see _fuse_hybrid for the measured rationale).
    fused_hits = _fuse_hybrid(vector_hits, bm25_hits,
                              bm25_max=bm25_max)[:prefetch_limit]

    # 4. Reranking using Cross-Encoder on CPU
    # Disabling reranking on CPU because it degrades recall by 10% and adds 1.5s latency
    for hit in fused_hits:
        hit["rerank_score"] = hit.get("rrf_score", 0.0)
        
    return fused_hits[:limit]

if __name__ == "__main__":
    # Test retrieval CLI
    initialize_retrieval_components()
    test_query = input("Enter query to test retrieval: ")
    results = retrieve(test_query, limit=5)
    print("\n--- Top Retrieved Results (Reranked) ---")
    for r, hit in enumerate(results, 1):
        meta = hit["metadata"]
        print(f"\nRank {r} | Rerank Score: {hit.get('rerank_score', 0.0):.4f} | RRF Score: {hit.get('rrf_score', 0.0):.4f}")
        print(f"File: {meta['file']} | Chapter: {meta['chapter']} | Section: {meta['section']} | Type: {meta['type']} | Page: {meta['page']}")
        print(f"Text snippet: {hit['text'][:250]}...")
