# Predator RAG: Windows-Native Local Document Assistant

A lightweight, high-performance, locally-hosted Retrieval-Augmented Generation (RAG) system that runs natively on Windows. Upload your own documents — PDF, Word, PowerPoint, Excel, CSV, text, Markdown, HTML, JSON, XML — and ask factual, summary, comparison, or extraction questions with source citations. Tested on Acer Predator Helios Neo 16 (i9-14900HX, RTX 4070 8GB VRAM, 16GB RAM) with zero cloud calls after setup.

---

## 🛠️ The Architecture & Stack

This project replaces resource-heavy WSL2 configurations and database daemons with a fully in-process, high-efficiency Windows-native pipeline:

### 1. Ingestion & Document Processing (`ingest.py`, `extractors.py`)
*   **Modular extractor registry**: format-specific extractors for PDF (`PyMuPDF`), Word (`python-docx`), PowerPoint (`python-pptx`, incl. speaker notes), Excel/CSV (sheet + row-group tables), Markdown (heading-aware), HTML (`beautifulsoup4`), TXT, JSON, XML. Unsupported types are rejected with a clear message; one bad file never blocks the rest.
*   **Structure-aware chunking**: never merges across page/slide/sheet/section boundaries; tables, slides, and records stay atomic; heading breadcrumbs prefix chunk text. PDFs keep the legacy layout-aware parser (worked examples, exercises, formulas) plus a page-boundary flush fix.
*   **Content-addressed embedding cache** (`./embed_cache`): unchanged files skip re-encoding (cache HIT ~0.08 s). Keys hash file bytes + extractor version + chunking params + embedding model; changed files/configs always re-encode.
*   **Workspace lifecycle**: clean start on launch; per-file removal; reset wipes the index but never source files.

### 2. Embeddings & Database (`retrieve.py`)
*   **Dense Vectors**: `BAAI/bge-base-en-v1.5` (768-d) on **CUDA** via `sentence-transformers`, shared singleton process-wide.
*   **Sparse Vectors**: in-memory BM25 index (`rank-bm25`) rebuilt when the workspace changes.
*   **Vector Database**: embedded **ChromaDB** under `./chroma_db`, collection `workspace_chunks` (SQLite in-process, zero service overhead).
*   **Retrieval Fusion**: dense + sparse via **Reciprocal Rank Fusion (RRF, k=60)**, optional per-file filtering, near-duplicate suppression. No reranker (measured +1.5 s, −10% recall on CPU).

### 3. Generation & LLM Inference (`answer.py`)
*   **Local LLM Service**: Windows-native **Ollama** on `http://127.0.0.1:11434` with direct CUDA acceleration.
*   **Active LLM Model**: `qwen3:8b` (fallback `llama3.1:8b` retained; grader pinned to `llama3.1:8b`).
*   **General-purpose grounded prompts**: no subject/domain assumptions; retrieved context is wrapped as untrusted evidence (never followed as instructions); answers must cite `[Source N]`; missing evidence gets an exact abstention instead of a guess. Model thinking traces are never rendered (thinking-leak fix intact).
*   **Latency-Optimized Inference**:
    *   *Standard questions*: `"num_predict": 4096` (stepped up 512 → 2048 → 4096 after measured empty responses when the thinking budget was exhausted; the 4096 budget was re-validated on the full 60-question held-out evaluation on 18 Oct 2026 — see `RAG_GENERATION_RELIABILITY.md` and `RELEASE_CANDIDATE_REPORT.md`).
    *   *Calculation-heavy questions*: step-by-step prompt with `"num_predict": 4096`.
    *   Answers stream token-by-token in the UI (`generate_answer_stream`).
*   **KV Cache Optimization**: single shared `"num_ctx": 4096` (`answer.NUM_CTX`) across warmup, completion, and grading to avoid model reload spikes (~6-8 s).

### 4. Streamlit Dashboard UI (`app.py`)
*   Multi-format upload with progress, per-file removal, empty-workspace state, and format-aware citations (Page / Slide / Sheet+rows / Section).
*   **Dynamic Status Panel**: Ollama, CUDA, and ChromaDB chunk counts.
*   **Dynamic Model Swapper**: switch models via `/api/tags`; old model unloaded from VRAM.
*   **Clean Startup**: workspace index starts empty; you upload what you want to query.
*   **Interactive Diagnostics**: RRF scores, raw chunks, and citations per answer.

---

## 📈 Performance & Resource Benchmarks

Mixed-format evaluation on **Acer Predator Helios Neo 16 (i9-14900HX, RTX 4070 8GB, 16GB RAM)** — 6 documents (PDF, DOCX, PPTX, XLSX, CSV, MD), 12 questions (see `RAG_EVALUATION.md`, run `python eval_general/eval_general.py --with-llm`):

| Metric | Result |
| :--- | :--- |
| **Recall@3 (correct file retrieved)** | **12/12 (100%)** |
| **Source-location accuracy** | **12/12 (100%)** |
| **Citation validity (no invented locations)** | **12/12 (100%)** |
| **Answer keyword hit (incl. cross-doc + abstain)** | **12/12 (100%)** |
| **Retrieval latency (steady-state)** | **~0.02–0.03 s** |
| **LLM generation latency (avg)** | **5.7 s** (range 2.7–12.3 s) |
| **Index build (17 chunks, cached)** | **0.8 s**; cache-hit re-ingest **0.08 s** |
| **Python Process RAM** | **~1.38 GB** |
| **GPU VRAM (qwen3:8b resident)** | **6.1 GB / 8 GB** |

*Scope note: n=12 toy corpus; see `RAG_EVALUATION.md` limitations. Historical physics-only reports (`PERFORMANCE_BENCHMARK.md`, `RETRIEVAL_EVALUATION.md`, `MODEL_AB_EVALUATION.md`) remain for reference but do not represent general-purpose performance.*

---

## 🚀 Setup & Execution

### Prerequisites
1. Install native [Ollama for Windows](https://ollama.com).
2. Pull the models (default + fallback):
   ```bash
   ollama pull qwen3:8b
   ollama pull llama3.1:8b
   ```
3. Make sure your Python 3.10+ environment is ready.

### Installation
Install the Windows-native dependencies:
```bash
pip install -r requirements.txt
```

### 1. Ingest Documents (CLI)
Ingest any supported files into embedded ChromaDB:
```bash
python -c "from ingest import ingest_files; print(ingest_files(['doc.pdf','slides.pptx','data.xlsx']))"
```
*(Unchanged files are served from `./embed_cache` instead of re-encoded.
Supported: pdf, docx, pptx, xlsx, csv, txt, md, html/htm, json, xml.)*

### 2. Run Evaluations
Mixed-format general-purpose eval (no LLM needed for retrieval metrics):
```bash
python eval_general/make_corpus.py   # one-time corpus build (already committed)
python eval_general/eval_general.py --with-llm
```
*(Saves results to `eval_general/results.json`; see `RAG_EVALUATION.md`.)*
Legacy physics benchmark: `python benchmark.py` (reference only).

### 3. Launch Streamlit Web App
Run the Streamlit application interface:
```bash
streamlit run app.py
```
*   Open your browser to [http://localhost:8501](http://localhost:8501).
*   The workspace starts empty — upload your own documents to start querying.
*   Remove files individually or reset the workspace anytime; originals are never deleted.

### Regression tests
```bash
python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py test_app_startup_preserves_foreign.py -q
```

---

## 📂 Repository Structure

The repository is kept minimal and clean, containing only the essential production files:

*   **`app.py`**: Streamlit web dashboard — multi-format upload, workspace management, streaming Q&A, citations, retrieval diagnostics.
*   **`extractors.py`**: Modular per-format extraction registry (pdf/docx/pptx/xlsx/csv/txt/md/html/json/xml) with explicit support list and clear rejection of anything else.
*   **`ingest.py`**: Chunking (structure-aware, boundary-safe), content-addressed embedding cache, workspace index management (ingest/remove/clear/list).
*   **`retrieve.py`**: Hybrid search retriever combining dense vector query (via ChromaDB), sparse keyword search (via BM25), and Reciprocal Rank Fusion (RRF) with file filtering and dedup.
*   **`answer.py`**: General-purpose grounded generation (no domain assumptions) + local LLM orchestration via Ollama.
*   **`eval_general/`**: Mixed-format corpus builder, evaluation harness, and results.
*   **`test_general_rag.py`**: Regression tests (extraction, metadata, cache, retrieval, citations, workspace, failures).
*   **`benchmark.py`**: Legacy physics benchmark (reference only; see `RAG_EVALUATION.md` for scope).
*   **`generate_questions.py` / `generate_questions_v2.py`**: Scripts for synthesizing evaluation benchmark questions from source documents.
*   **`requirements.txt`**: Python package dependencies list for the native Windows environment.
*   **`MIGRATION_AUDIT.md`**: Architectural log detailing the migration from WSL2 virtualization to the native Windows configuration.
*   **`README.md`**: Main configuration, benchmark documentation, and user guide.
*   **`PR`**: Detailed project report detailing the technology stack and component breakdown.

