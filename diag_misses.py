"""Component-level retrieval diagnosis (no LLM calls).

Builds ./chroma_diag from keph105/106/107 (cache-hit), then for 6 probe
questions records: dense top-20 (with distances), BM25 top-20 (with scores),
RRF fused top-6, and whether any corpus chunk carries the expected section.
Writes: diag_misses.json
"""
import json, os, shutil, sys, time
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np

TMP_DB = "./chroma_diag"
if os.path.exists(TMP_DB):
    shutil.rmtree(TMP_DB)

import ingest as I
import retrieve as R
I.CHROMA_DB_PATH = TMP_DB
R.CHROMA_DB_PATH = TMP_DB

import chromadb
PHYS = ["data/keph105.pdf", "data/keph106.pdf", "data/keph107.pdf"]
client = chromadb.PersistentClient(path=TMP_DB)
coll = client.get_or_create_collection(R.COLLECTION_NAME)
at, ae, am = [], [], []
for pdf in PHYS:
    pb, chunks = I._parse_and_chunk_pdf(pdf, os.path.basename(pdf))
    t, e, m = I._embed_chunks_cached(pb, os.path.basename(pdf), chunks)
    at.extend(t); ae.extend(e); am.extend(m)
I._add_to_collection(coll, at, ae, am)
print(f"diag corpus: {coll.count()} chunks", flush=True)
R.initialize_retrieval_components()

CASES = [
    ("State Kepler's third law of periods.", ["7.2", "kepler"]),
    ("Define power and write its SI unit.", ["5.10", "power"]),
    ("A solid cylinder of mass 20 kg rotates at 100 rad/s, radius 0.25 m. Kinetic energy of rotation?", ["6.9", "moment of inertia", "kinetic"]),
    ("State the Universal Law of Gravitation.", ["7.3", "gravitation"]),
    ("What is the relation between torque and angular momentum?", ["6.7", "torque"]),
    ("Write the formula for escape velocity.", ["escape"]),
]

# Does the expected passage exist in the corpus at all?
all_data = coll.get(include=["documents", "metadatas"])
secs = sorted({m.get("section", "?") for m in all_data["metadatas"]})

out = {"corpus_sections": secs, "cases": []}
for q, expects in CASES:
    emb = R.get_embedder().encode([q])[0].tolist()
    vec = coll.query(query_embeddings=[emb], n_results=20)
    dense = [(vec["metadatas"][0][i].get("section", "?"),
              round(vec["distances"][0][i], 4)) for i in range(len(vec["ids"][0]))]
    tok = R.tokenize(q)
    scores = R._bm25.get_scores(tok)
    order = np.argsort(scores)[::-1][:20]
    bm25 = [(R._corpus_data[i]["metadata"].get("section", "?"),
             round(float(scores[i]), 3)) for i in order if scores[i] > 0][:20]
    fused = R.retrieve(q, limit=6)
    fused_list = [(h["metadata"].get("section", "?"), round(h.get("rrf_score", 0), 4)) for h in fused]
    top3 = " | ".join(s for s, _ in fused_list[:3]).lower()
    entry = {"q": q, "expects": expects,
             "strict_hit": any(e.lower() in top3 for e in expects),
             "expected_in_corpus": [s for s in secs if any(e.lower() in s.lower() for e in expects)],
             "dense_top5": dense[:5], "bm25_top5": bm25[:5], "fused_top6": fused_list}
    out["cases"].append(entry)
    print(f"[{'HIT' if entry['strict_hit'] else 'MISS'}] {q[:55]}", flush=True)
    print(f"   dense: {[d[0][:45] for d in dense[:3]]}", flush=True)
    print(f"   bm25 : {[b[0][:45] for b in bm25[:3]]}", flush=True)
    print(f"   fused: {[f[0][:45] for f in fused_list[:3]]}", flush=True)
    print(f"   in-corpus matches: {entry['expected_in_corpus'][:4]}", flush=True)

with open("diag_misses.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print("WROTE diag_misses.json", flush=True)
shutil.rmtree(TMP_DB, ignore_errors=True)
