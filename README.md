# Predator RAG: Windows-Native Local Document Assistant

A lightweight, locally-hosted Retrieval-Augmented Generation (RAG) system that runs natively on Windows. Upload your own documents — PDF, Word, PowerPoint, Excel, CSV, text, Markdown, HTML, JSON, XML — and ask factual, summary, comparison, or extraction questions with source citations. Local-first by design: no cloud services, no API keys, everything runs on your machine (developed and benchmarked on an Acer Predator Helios Neo 16, i9-14900HX / RTX 4070 8 GB).

---

## 🛠️ The Architecture & Stack

This project replaces resource-heavy WSL2 configurations and database daemons with a fully in-process, Windows-native pipeline:

### 1. Ingestion & Document Processing (`ingest.py`, `extractors.py`)
*   **Modular extractor registry**: format-specific extractors for PDF (`PyMuPDF`), Word (`python-docx`), PowerPoint (`python-pptx`, incl. speaker notes), Excel/CSV (sheet + row-group tables), Markdown (heading-aware), HTML (`beautifulsoup4`), TXT, JSON, XML. Unsupported types are rejected with a clear message; one bad file never blocks the rest.
*   **Structure-aware chunking**: never merges across page/slide/sheet/section boundaries; tables, slides, and records stay atomic; heading breadcrumbs prefix chunk text. PDFs keep a layout-aware parser (worked examples, exercises, formulas) with a page-boundary flush fix.
*   **Content-addressed embedding cache** (`./embed_cache`): unchanged files skip re-encoding (cache HIT ~0.08 s). Keys hash file bytes + extractor version + chunking params + embedding model; changed files/configs always re-encode.
*   **Workspace lifecycle**: the index starts empty on launch; per-file removal; Reset wipes the workspace index but never source files. Boot and Reset delete **only** the app-owned `workspace_chunks` ChromaDB collection — any other collections in `./chroma_db` are never touched (regression-tested).

### 2. Embeddings & Database (`retrieve.py`)
*   **Dense Vectors**: `BAAI/bge-base-en-v1.5` (768-d) via `sentence-transformers`, CUDA when available with automatic CPU fallback.
*   **Sparse Vectors**: in-memory BM25 index (`rank-bm25`) rebuilt when the workspace changes.
*   **Vector Database**: embedded **ChromaDB** under `./chroma_db`, collection `workspace_chunks` (SQLite in-process, zero service overhead).
*   **Retrieval Fusion**: dense + sparse via **Reciprocal Rank Fusion (RRF, k=60)**, optional per-file filtering, near-duplicate suppression. No reranker (cross-encoder measured +1.5 s, −10 % recall).

### 3. Generation & LLM Inference (`answer.py`)
*   **Local LLM Service**: Windows-native **Ollama** on `http://127.0.0.1:11434`.
*   **Active LLM Model**: `qwen3:8b` (fallback `llama3.1:8b` retained; benchmark grader pinned to `llama3.1:8b`).
*   **General-purpose grounded prompts**: no subject/domain assumptions; retrieved context is wrapped as untrusted evidence (never followed as instructions); answers must cite `[Source N]`; missing evidence gets an exact abstention instead of a guess. Model thinking traces are never rendered (thinking-leak fix).
*   **Latency-optimized inference**: `num_predict: 4096` for standard and calculation-heavy questions (raised 512 → 2048 → 4096 after measured empty responses when the thinking budget was exhausted; validated on a 60-question held-out run — see `docs/RAG_GENERATION_RELIABILITY.md` and `docs/RELEASE_CANDIDATE_REPORT.md`).
*   **KV-cache optimization**: single shared `"num_ctx": 4096` (`answer.NUM_CTX`) across completion, warmup, and grading, avoiding model reload spikes (~6–8 s).

### 4. Streamlit Dashboard UI (`app.py`)
*   Multi-format upload with progress, per-file removal, empty-workspace state, streaming answers, and format-aware citations (Page / Slide / Sheet+rows / Section).
*   **Dynamic status panel**: Ollama, CUDA, and ChromaDB chunk counts.
*   **Dynamic model swapper**: switch models via `/api/tags`; old model unloaded from VRAM.
*   **Interactive diagnostics**: RRF scores, raw chunks, and citations per answer.

---

## ⚠️ Known Limitations

*   **No OCR backend for scanned documents.** Extractors pull embedded text only (text-based PDFs are required). Image-only pages are detected and the extractor returns a note suggesting an OCR tool (e.g. `pip install rapidocr-onnxruntime`) — see `extractors.py`.
*   CSV citations may show an internal temp-file sheet label next to the (correct) original filename and row metadata — cosmetic.
*   The THEORY/NUMERICAL question-type router is keyword-based.
*   **No authentication** — the UI is localhost-only by design; do not expose port 8501 to other machines.
*   The cross-encoder reranker is intentionally disabled (measured latency/recall penalty).

---

## 📈 Performance & Resource Benchmarks

Mixed-format evaluation — 6 documents (PDF, DOCX, PPTX, XLSX, CSV, MD), 12 questions (see `docs/RAG_EVALUATION.md`; run `python eval_general/eval_general.py --with-llm`):

| Metric | Result |
| :--- | :--- |
| **Recall@3 (correct file retrieved)** | **12/12 (100%)** |
| **Source-location accuracy** | **12/12 (100%)** |
| **Citation validity (no invented locations)** | **12/12 (100%)** |
| **Answer keyword hit (incl. cross-doc + abstain)** | **12/12 (100%)** |
| **Retrieval latency (steady-state)** | **~0.02–0.03 s** |
| **LLM generation latency (avg)** | **5.7 s** (range 2.7–12.3 s) |
| **Index build (17 chunks, cached)** | **0.8 s**; cache-hit re-ingest **0.08 s** |
| **Python process RAM** | **~1.38 GB** |
| **GPU VRAM (qwen3:8b resident)** | **6.1 GB / 8 GB** |

*Scope note: n=12 toy corpus, limitations in `docs/RAG_EVALUATION.md`. A 60-question held-out harness (`eval_realworld/postfix_runner.py`) provided the release decision evidence (`docs/RELEASE_CANDIDATE_REPORT.md`); its real-world corpus is intentionally outside version control. Historical physics-only reports in `docs/` do not represent general-purpose performance.*

---

## 🚀 Setup & Execution

### Prerequisites
1.  Windows with Python **3.10+** (tested on 3.12).
2.  Install native [Ollama for Windows](https://ollama.com), then pull the required models:
    ```bash
    ollama pull qwen3:8b
    ollama pull llama3.1:8b
    ```
3.  First run additionally downloads the `BAAI/bge-base-en-v1.5` embedding model from Hugging Face (~0.4 GB, one time). After that, everything runs locally with zero cloud calls.

### Installation
```bash
pip install -r requirements.txt
pip install pytest          # test-only dependency, not in requirements.txt
```

### 1. Upload Documents (UI) or Ingest (CLI)
Launch the app and drop files onto the uploader:
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501). The workspace starts empty; remove files individually or reset the workspace anytime — originals are never deleted.

Or ingest supported files from the CLI (dump straight into the embedded ChromaDB):
```bash
python -c "from ingest import ingest_files; print(ingest_files(['doc.pdf','slides.pptx','data.xlsx']))"
```
*Unchanged files are served from `./embed_cache` instead of re-encoded. Supported: pdf, docx, pptx, xlsx, csv, txt, md, html/htm, json, xml.*

### 2. Run the General-Purpose Evaluation
Mixed-format eval on a temporary workspace — it never touches `./chroma_db` or your files (results → `eval_general/results.json`; see `docs/RAG_EVALUATION.md`):
```bash
python eval_general/make_corpus.py   # one-time mixed-format corpus build
python eval_general/eval_general.py            # retrieval + citation metrics, no LLM needed
python eval_general/eval_general.py --with-llm # + answer correctness via local Ollama
```

### 3. Run the Regression Tests
```bash
python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py test_app_startup_preserves_foreign.py -q
```

---

## 📂 Repository Structure

*   **`app.py` / `ingest.py` / `extractors.py` / `retrieve.py` / `answer.py`** — the production pipeline: Streamlit UI, chunking + cache + workspace index, per-format extraction, hybrid (dense+BM25+RRF) retrieval, grounded generation.
*   **`test_general_rag.py`, `test_thinking_leak.py`, `test_answer_config.py`, `test_eval_grader.py`, `test_app_startup_preserves_foreign.py`** — regression suite (extraction, metadata, cache, retrieval, citations, workspace lifecycle, config pins, grader, startup-wipe scope).
*   **`benchmark.py` + `benchmark_questions.json`** — legacy *physics* benchmark harness and its 99-question bank fixture, kept for reference and because the grader-model pin regression (`test_answer_config.py`) imports it.
*   **`eval_general/`** — mixed-format corpus builder (`make_corpus.py`), deterministic+LLM evaluation harness (`eval_general.py`).
*   **`eval_realworld/`** — 60-question held-out harness (`postfix_runner.py`, `eval_realworld.py`), answer grader (`grader.py`), AppTest UI probe (`ui_realworld.py`).
*   **`eval_stress/`** — malformed-input stress harness (`make_stress_corpus.py`, `eval_stress.py`, `ui_apptest.py`).
*   **`tools/`** — one-off diagnostics and legacy experiment scripts tied to the archived reports (`generate_questions*.py`, `model_lab.py`, `prompt_lab.py`, `think_probe.py`, `verify_*.py`, `diag_misses.py`, `budget_verify.py`, `run_isolated_benchmark.py`). Not part of the runtime; if ever needed, run from the repo root as `python -m tools.<name>`.
*   **`docs/`** — the complete point-in-time research/audit/release record: `FINAL_SIGNOFF.md` (latest handoff), `RELEASE_CANDIDATE_REPORT.md` (RC evidence), plus retrieval/generation/reliability research, benchmarks, and the earliest project audits. Paths inside these archived reports reflect the repo as of their date.
*   **`requirements.txt`**, `.gitignore`, `README.md`.
*   **Not in the repository** (generated or local-only): `chroma_db/` (vector DB), `embed_cache/` (embedding cache), `data/` (your own source documents), eval-workspace outputs, and caches.

---

## 📜 License

No license file yet — a license must be chosen before this repository is made public.
