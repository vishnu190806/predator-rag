# Predator RAG System Stack & Architecture Details

## Core Technology Stack & Libraries
* **Framework / UI**: `streamlit` (multi-format workspace UI with custom CSS styling)
* **Document Extraction**: modular registry (`extractors.py`) — `pymupdf` (PDF), `python-docx` (Word), `python-pptx` (PowerPoint + notes), `openpyxl` (Excel), stdlib `csv`, `beautifulsoup4`/`lxml` (HTML), stdlib for txt/md/json/xml
* **Embeddings**: `sentence-transformers` (Class `SentenceTransformer`)
* **Vector Database**: `chromadb` (Persistent vector store)
* **Lexical Search**: `rank-bm25` (Using `BM25Okapi` algorithm)
* **Deep Learning Runtime**: `torch` (PyTorch for CUDA-accelerated embedding/reranking)
* **LLM Orchestration**: `requests` (Communicating with local Ollama API)
* **Helper Modules**: `numpy` (for search rank sorting), `psutil` (system stats), `re` (structural regex parsing), `uuid` (unique document ID generation)

## Chunking Strategy
* **Document Chunking Method**: Boundary-safe chunking — never merges across PDF pages, slides, spreadsheet row-groups, or headed sections; tables/slides/records stay atomic. PDFs keep the legacy structure-aware parser (examples, exercises, formulas) with a page-boundary flush fix.
* **Chunk Size**: `1,600` characters (`chunk_size_chars=1600`).
* **Chunk Overlap**: `300` characters (`overlap_chars=300`).
* **Chunk Splitting Boundary**: Tries to cleanly split on double newlines (`\n\n`), falling back to single newlines (`\n`) if needed.
* **Heading context**: `H1 > H2` breadcrumbs stored in metadata and prefixed to chunk text.

## Embedding Generation
* **Embedding Model**: `BAAI/bge-base-en-v1.5`
* **Device Selection**: Automatically detects and uses GPU (`cuda`) via PyTorch if available, falling back to CPU (`cpu`).
* **Batching**: Processed in batch sizes of `64`.

## Vector Database
* **Database**: `chromadb` (Persistent Client)
* **Storage Path**: Local directory `./chroma_db`
* **Collection Name**: `workspace_chunks`
* **Metadata Fields**: `file`, `doc_id`, `doc_type`, `chapter`, `section`, `heading`, `page`, `slide`, `sheet`, `row_range`, `type`

## Search & Retrieval Mechanics
* **Hybrid Search Strategy**:
  1. **Dense Vector Search**: ChromaDB semantic search using `BAAI/bge-base-en-v1.5` embeddings.
  2. **Sparse Lexical Search**: BM25 search over lowercased, tokenized text (`re.findall(r"\w+", text.lower())`).
* **Fusion Algorithm**: Reciprocal Rank Fusion (RRF) with constant $k = 60$ to merge vector and lexical scores.
* **Metadata Filtering**: Optional per-file `where` filter on dense search (+ post-filter on BM25); a secondary targeted retrieval fetches up to 3 formulas (`where={"type": "formula"}`) for calculation-heavy questions.
* **Dedup**: Near-duplicate chunks (identical text indexed twice) contribute once to fusion.
* **Reranking**: Includes a Cross-Encoder reranker (`BAAI/bge-reranker-base`), but it is currently bypassed (disabled) in the search loop (`retrieve.py`) to prevent CPU-based latency overhead and recall degradation.

## LLM & Answer Generation
* **LLM Engine**: Local Ollama server (`http://127.0.0.1:11434`)
* **Active LLM Model**: `qwen3:8b` (Q4_K_M; fallback `llama3.1:8b` retained; grader pinned to `llama3.1:8b`)
* **Context Size**: `4096` tokens (single shared `answer.NUM_CTX` across warmup, generation, grading)
* **Generation Settings**:
  * **Temperature**: `0.1` (for high grounding / minimal hallucination)
  * **Keep-alive**: `5m` (5 minutes VRAM cache timeout)
  * **Calculation-heavy Questions**: Step-by-step prompt with output capped at `4096` tokens (covers thinking trace + final answer).
  * **Standard Questions**: Capped at `2048` tokens (raised from 512: thinking shares the budget; 512 gave reproducible empty responses).
