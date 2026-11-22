# PROJECT_HANDOFF — Predator RAG: Windows-Native Academic Assistant

## 1. Project identity and purpose

- **Name:** Predator RAG (also called "Predator RAG Assistant" / "Predator RAG Core" in `app.py`).
- **What it is:** A single-application, locally-hosted Retrieval-Augmented Generation (RAG) system for NCERT 11th/12th Physics (plus bundled Chemistry/Maths PDFs) Q&A — theory, worked examples, formulas, exercises, JEE/NEET style questions.
- **Intended users:** Student (self) preparing for JEE/NEET/CBSE; internship/portfolio project demonstrating local-LLM + hybrid retrieval.
- **Problem it solves:** Run accurate, cited textbook Q&A on a Windows gaming laptop (Acer Predator Helios Neo 16, RTX 4070 8GB, 16GB RAM) without WSL2 filesystem/RAM overhead and without exceeding 8GB VRAM.
- **Maturity:** Working prototype / advanced hobby build. Core pipeline (ingest → hybrid retrieve → Ollama generate → Streamlit UI → benchmark) is code-complete. No tests, no git repo, no deployment, no auth, no CI. Benchmark claims in `README.md` (60% recall, latency targets) are **unverified in this audit** — no `benchmark_questions.json` / `benchmark_results.json` present.
- **Cannot be established from evidence:** Original author timeline, whether README benchmark numbers were ever reproduced, intended production audience beyond personal/internship use.

## 2. Executive summary of the current state

- Single Python app, 6 source files (`app.py`, `ingest.py`, `retrieve.py`, `answer.py`, `benchmark.py`, `generate_questions*.py`), Streamlit UI, embedded ChromaDB at `./chroma_db`, local Ollama LLM.
- **Code-inspected:** full pipeline exists and is coherent: layout-aware PDF chunking (`ingest.py:53-268`), dense+BM25+RRF hybrid retrieval (`retrieve.py:122-197`), theory/numerical prompt routing (`answer.py:55-70`), Streamlit dashboard with model swap/warmup/diagnostics (`app.py:150-352`), benchmark harness (`benchmark.py:97-270`).
- **Verified this audit (safe, non-destructive):**
  - `python -m py_compile` passes on all 6 source files.
  - ChromaDB opens and collection `textbook_chunks` contains **7868 chunks** (far more than README's "698 chunks" — indicates later ingestions of the 14 PDFs in `data/`).
  - Ollama is **online** at `http://127.0.0.1:11434`, but the configured default model `qwen3:8b-q4_K_M` is **not installed**; installed models are `llama3.1:8b` and `nomic-embed-text:latest`, and `/api/ps` shows **no model currently loaded**.
  - `torch.cuda.is_available()` returns **True** on this machine.
  - `is_numerical_question` spot test shows over-triggering (e.g. `"What is 5.6 about torque?"` → `True`).
  - `benchmark.py` **cannot run as-is**: it opens `benchmark_questions.json`, which does not exist in the repo.
- **Not verified:** end-to-end query, ingestion rerun, benchmark rerun, latency/recall numbers, Streamlit launch (deliberately not run — heavyweight + requires model download).

## 3. Technology stack and architecture

| Layer | Technology | Evidence |
|---|---|---|
| Language/runtime | Python 3.12.10 (this machine); README says 3.10+ | `python --version`; `README.md:65` |
| UI | Streamlit 1.55.0, custom dark CSS | `app.py:1-90`, `requirements.txt` |
| PDF parsing | PyMuPDF (`fitz`), block-sorted layout parse | `ingest.py:6,53-68` |
| Embeddings | `sentence-transformers` 5.3.0, `BAAI/bge-base-en-v1.5` (768-d), batch 64, auto cuda/cpu | `retrieve.py:18,41-47`, `ingest.py:359`, `stack.md:20-23` |
| Vector DB | ChromaDB 1.4.1 `PersistentClient(path="./chroma_db")`, collection `textbook_chunks`, metadata `file, chapter, section, page, type` | `retrieve.py:29-35`, `ingest.py:363-372` |
| Sparse retrieval | `rank-bm25` `BM25Okapi`, tokenize `re.findall(r"\w+", text.lower())`, rebuilt when count changes | `retrieve.py:57-92` |
| Fusion | Reciprocal Rank Fusion k=60, dedup key `(file, section, page, text[:100])` | `retrieve.py:164-190` |
| Reranker | `BAAI/bge-reranker-base` `CrossEncoder` — **imported but disabled** (`# reranker = get_reranker()`, scores = RRF) | `retrieve.py:132,192-195`, `stack.md:37` |
| LLM | Local Ollama `http://127.0.0.1:11434`, default `qwen3:8b-q4_K_M`, `num_ctx=12000`, temp 0.1, theory `think:false/num_predict:512`, numerical `think:true/num_predict:2048`, `keep_alive 5m` | `answer.py:14-15,100-118` |
| Eval/resources | `psutil`, `torch`, `numpy`, `nvidia-smi` subprocess, LLM-as-grader | `benchmark.py:1-92` |
| Deps file | `requirements.txt`: streamlit, requests, pymupdf, chromadb, sentence-transformers, rank-bm25, psutil, torch (unpinned) | `requirements.txt` |

**Architecture / data flow:**
`data/*.pdf` → `ingest.py:parse_pdf` (chapter/section/example `⊳`/exercises/formula detection) → `chunk_parsed_items` (1600 chars / 300 overlap, `\n\n` then `\n` split; theory runs merged, examples/exercises/formulas kept whole) → `SentenceTransformer.encode` → ChromaDB + BM25 index → user query in Streamlit (`app.py:295-312`) → `answer.py:answer_question` (classify → `retrieve(limit=6)` + optional `retrieve_formulas(limit=3)` → build context → Ollama `/api/generate`) → answer + citations + latency metrics + diagnostics expander. `benchmark.py` samples 20 questions (5×4 categories) and grades with Ollama.

## 4. Important directories and files

- `app.py` (352 lines) — Streamlit UI, session state, Ollama/Chroma status, model swap (`keep_alive:0` unload), VRAM warmup (`num_ctx:12000`, 180s timeout), upload→`ingest_single_pdf`, Q&A + diagnostics. **Note: wipes all collections on first session load (`app.py:99-108`).**
- `ingest.py` (461 lines) — `parse_pdf`, `chunk_parsed_items`, `ingest_pdfs(data_dir="./data")`, `ingest_single_pdf(recreate, original_filename)`. Formula chunks are **duplicated** as both `formula` and `theory` (`ingest.py:224-240`).
- `retrieve.py` (209 lines) — `get_db/get_embedder/get_reranker`, `initialize_retrieval_components`, `retrieve_formulas` (`where={"type":"formula"}`), `retrieve(query, limit=20, prefetch_limit=20)`; note `answer.py` calls `retrieve(question, limit=6)` so `limit` ≠ prefetch default.
- `answer.py` (197 lines) — prompts, `is_numerical_question`, `build_context_string`, `generate_answer`, `format_citations`, `answer_question`. 300s generation timeout.
- `benchmark.py` (270 lines) — needs `benchmark_questions.json` (missing); writes `benchmark_results.json`; grader `num_ctx:12000`, grading timeout 60s.
- `generate_questions.py` (918 lines, 100 Qs, v1 section labels) / `generate_questions_v2.py` (910 lines, 100 Qs, corrected section labels) — both write `benchmark_questions.json` when run; **v2 is the corrected one**; running either overwrites the same filename. Neither has been run in this checkout (no JSON present).
- `data/` — 14 PDFs (~100MB total): `keph105/106/107.pdf`, NCERT Class 11/12 Physics Parts 1+2, Chemistry Parts 1+2 (11+12), Class 11 Maths, Class 12 Maths Part 2 (+ duplicate with space in name).
- `chroma_db/` — live embedded DB, ~20+ segment UUID dirs, 7868 vectors. Treat as local build artifact, not source.
- `README.md`, `stack.md`, `PR`, `MIGRATION_AUDIT.md` — overlapping docs; README is the user guide + benchmark table; `stack.md` is the most precise config reference; `PR` adds mermaid flow; `MIGRATION_AUDIT.md` explains WSL2→native migration.
- `requirements.txt` — 8 unpinned deps (transitives like numpy not listed).
- `Stack.png` — architecture diagram image (not inspected pixel-wise).
- `__pycache__/` — bytecode artifact.
- **Absent:** tests, `.env`/`.env.example`, Dockerfile, CI, git repo (this directory is not a git repo), `benchmark_questions.json`, `benchmark_results.json`, `PROJECT_HANDOFF.md` (this file is new).

## 5. Implemented features and their verification status

| Feature | Status | Evidence |
|---|---|---|
| Layout-aware PDF parse (chapters, sections, examples until `⊳`, exercises, formulas) | Code-inspected | `ingest.py:53-268` |
| Chunking 1600/300 with boundary splits | Code-inspected | `ingest.py:270-337`, `stack.md:15-18` |
| Batch embedding + Chroma persist | Code-inspected; DB non-empty verified | `ingest.py:375-401`; audit: 7868 chunks |
| Single-PDF upload ingest with original filename | Code-inspected | `ingest.py:403-458`, `app.py:268-271` |
| Hybrid dense+BM25+RRF retrieval + dedup | Code-inspected | `retrieve.py:122-197` |
| Formula-targeted retrieval for numerical | Code-inspected | `retrieve.py:94-120`, `answer.py:160-161` |
| Theory/numerical classifier + dual prompts + think toggle | Code-inspected; misclassification verified on 1 probe | `answer.py:55-134`; audit probe |
| Ollama generation (temp 0.1, ctx 12000, caps) | Code-inspected; service reachable verified, default model missing | `answer.py:100-134`; `/api/tags` audit |
| Citations (chapter/section/page/file) | Code-inspected | `answer.py:136-146` |
| Streamlit dashboard: status badges, model dropdown+swap, warmup, reset, diagnostics | Code-inspected (not launched) | `app.py:128-352` |
| Benchmark harness (recall/accuracy/citation/latency/RAM/VRAM, LLM grader) | Partially implemented — **broken as-is** (missing input JSON) | `benchmark.py:99`; no JSON on disk |
| Question banks (100 Qs v1 + 100 Qs corrected v2) | Code-inspected (both compile; tails write JSON) | `generate_questions.py:915-918`, `generate_questions_v2.py:906-910` |
| README benchmark claims (60% recall, 37.15s avg, VRAM 6.15GB) | Unverified | No results file; no run this audit |

Status key: Verified = test/build/execution evidence; Code-inspected = implementation read, runtime not exercised; Partially implemented / Broken / Unverified as labeled.

## 6. Partially implemented, missing, and broken functionality

1. **Broken: `benchmark.py` has no input.** Opens `benchmark_questions.json` (`benchmark.py:99`) but file is absent. Fix is to run `generate_questions_v2.py` first — but that overwrites the shared filename, and v1 vs v2 section-label mismatch means old results (if any) are not comparable. (P1)
2. **Broken-by-environment: default LLM not installed.** `OLLAMA_MODEL = "qwen3:8b-q4_K_M"` (`answer.py:15`) but `/api/tags` lists only `llama3.1:8b`, `nomic-embed-text:latest`. Any `answer_question` with default model will 404/fail until `ollama pull qwen3:8b-q4_K_M` or code default is changed. (P0/P1 — fundamental execution blocker for the documented path)
3. **Partial: reranker dead code.** `CrossEncoder` imported and `get_reranker()` defined but never called; `rerank_score = rrf_score` (`retrieve.py:132,192-195`). `stack.md:37` says intentionally disabled for CPU latency/recall — keep or remove, don't leave ambiguous. (P3)
4. **Partial: classifier over-triggers.** `is_numerical_question` = `(has_digits or has_unit) and has_keyword` (`answer.py:55-70`). Verified: `"What is 5.6 about torque?"` → True (section number + physics keyword). Unit list uses spaced tokens (`" m "`, `" s "`) that miss end-of-string/punctuation; keyword list is physics-only (no chemistry/maths despite `data/` containing those PDFs). Consequence: wrong prompt path (2048-token think mode → ~60s latency) for theory questions. (P1)
5. **Partial: retrieval limit confusion.** `retrieve(query, limit=20, prefetch_limit=20)` defaults to 20 but `answer_question` passes `limit=6` while prefetch stays 20 (`answer.py:156`, `retrieve.py:122`). Works, but diagnostics UI labels "Top Retrieved Chunks (Reranked)" when no reranking happens (`app.py:339-348`). (P3)
6. **Missing: tests, git, versioning, error UX.** No test files, no git repo, no pinned deps, bare `except: pass` swallows DB/Ollama errors (`app.py:105,126,141,174`; `ingest.py:370,429`), no empty-state beyond "no files" info, no query-history persistence. (P1/P2)
7. **Missing: multi-subject support in practice.** `data/` has Chemistry/Maths but classifier keywords, prompts ("physics and mathematics tutor"), and benchmark banks are physics-centric. Out-of-scope PDFs will retrieve but prompts/grading assume physics. (P2)
8. **Data-loss footgun: clean-startup wipe.** First Streamlit session deletes **every** collection in `chroma_db` (`app.py:99-108`), and Reset button deletes the production collection. With 7868 chunks on disk, one UI launch wipes hours of ingestion. (P0 — data loss)
9. **Inconsistency: docs vs code on embeddings device.** README says CPU-only to save VRAM; `stack.md:22` + code say auto cuda/cpu (`retrieve.py:37-47`, `ingest.py:20-22`, `app.py:222` caption says GPU-if-available). Actual behavior is auto, not CPU-pinned. (P2)

## 7. Frontend, backend, API, and database inventory

- **Frontend (`app.py`, Streamlit, no REST API of its own):** page config → session state (`processed_files`, `selected_model`, `warmed_up_models`, `clean_started`) → DB count load → Ollama `/api/tags` + `/api/ps` poll (1s timeout) → sidebar (model selectbox, unload-old via `POST /api/generate {keep_alive:0}`, warmup `POST /api/generate {num_ctx:12000}`, status badges, compute info, reset) → two columns (file uploader → temp file → `ingest_single_pdf`; text input → `answer_question` → answer/citations/4 latency metrics/diagnostics expander with per-chunk section/page/type/rrf score/text area).
- **Backend (same process, imported modules):** `ingest.ingest_single_pdf / ingest_pdfs`, `retrieve.initialize_retrieval_components` (imported in `app.py:14` but never called — BM25 lazy-loads via `retrieve()` instead), `answer.answer_question / is_numerical_question`, constants `COLLECTION_NAME/CHROMA_DB_PATH/EMBEDDING_MODEL_NAME/RERANKER_MODEL_NAME/OLLAMA_HOST/OLLAMA_MODEL`.
- **External API calls (all to local Ollama):** `GET /api/tags`, `GET /api/ps`, `POST /api/generate` (swap-unload, warmup, answer, grader). No auth. Timeouts: 1s (status), 5s (unload), 180s (warmup), 300s (answer), 60s (grader).
- **Database:** ChromaDB persistent, `./chroma_db`, collection `textbook_chunks`, 7868 docs; metadata `file/chapter/section/page/type` (`type` ∈ theory/example/exercise/formula); embeddings 768-d BGE-base; BM25 in-memory rebuilt on count change. No migrations, no schema file, no backup.

## 8. AI, external services, and configuration dependencies

- **Providers/models:** Ollama (local service, CUDA) + `qwen3:8b-q4_K_M` (documented, missing) — verified installed: `llama3.1:8b`, `nomic-embed-text:latest`. Embeddings `BAAI/bge-base-en-v1.5` (HuggingFace, downloaded on first run — heavy). Reranker `BAAI/bge-reranker-base` (configured, unused at runtime).
- **Fallbacks:** embedder device cuda→cpu; Ollama model list falls back to `[OLLAMA_MODEL]` if `/api/tags` fails (`app.py:144-145`); `get_or_create_collection` avoids crash on empty DB; **no LLM fallback** — if default model 404s, query fails.
- **Config (names only, no secrets in repo):** no `.env`; hardcoded `OLLAMA_HOST`, `OLLAMA_MODEL`, `CHROMA_DB_PATH`, `COLLECTION_NAME`, `EMBEDDING_MODEL_NAME`, `RERANKER_MODEL_NAME`, `num_ctx=12000`, temperatures, token caps. Internet icon URL in sidebar (`https://img.icons8.com/...`) requires network for the logo.
- **Execution evidence:** Ollama reachable + CUDA True verified; embedding generation, full Q&A, and benchmark grading **not executed** this audit (would download models / take minutes / need the missing model).

## 9. Build, test, and run instructions

- **Prereqs:** Python 3.10+, native Ollama for Windows running, `ollama pull qwen3:8b-q4_K_M` (or change `OLLAMA_MODEL` in `answer.py:15` to an installed model like `llama3.1:8b`), ~10GB free disk for HF models + `chroma_db`.
- **Install:** `pip install -r requirements.txt` (unpinned; expect large torch + sentence-transformers download).
- **Ingest all:** `python ingest.py` (parses `./data`, wipes + recreates collection, batch 64).
- **Make benchmark input:** `python generate_questions_v2.py` (writes `benchmark_questions.json`; prefer v2 over v1).
- **Benchmark:** `python benchmark.py` (needs DB ingested + Ollama model + `benchmark_questions.json`; writes `benchmark_results.json`; ~20 LLM calls + 20 grading calls — slow).
- **App:** `streamlit run app.py` → http://localhost:8501. **Warning:** first load wipes `chroma_db` (see §6.8); upload PDFs in sidebar before querying.
- **Tests:** none exist; nothing to run. **Build:** no build step (interpreted). **Lint/typecheck:** none configured.

## 10. Security, reliability, UX, and code-quality findings

- **Security:** Local-only by design (Ollama 127.0.0.1, embedded DB) — good. Risks: no auth on UI (anyone with port access can query/wipe DB via Reset button); `st.markdown(..., unsafe_allow_html=True)` + raw LLM text rendered with `st.markdown(res["answer"])` → prompt-injection → rendered HTML/JS surface (low but real); temp files via `NamedTemporaryFile(delete=False)` + manual unlink (leak on crash); bare excepts hide failures; no secret handling needed (no keys) — keep it that way.
- **Reliability:** clean-startup wipe + unguarded Reset = data loss; `retrieve_formulas` unguarded on empty DB except count check; `initialize_retrieval_components` imported but unused in `app.py` (works only because `retrieve()` calls it — fragile); `is_numerical_question` misroutes latency budget; formula duplication doubles those vectors; duplicate-space filename (`ncert-books-for-class-12-maths 1.pdf`) risks confusion.
- **UX:** strong status badges, latency breakdown, per-chunk diagnostics, citations with file/page. Gaps: wipe-on-launch is silent; warmup blocks with spinner up to 180s; no progress for retrieval/generation split in UI; diagnostics mislabels RRF as "Reranked"; no history, no export, no mobile check.
- **Code quality:** small, readable, well-commented structure; magic numbers inline (1600/300/60/12000/512/2048); two near-duplicate question banks; no typing/tests/lint; `numpy` used but not in `requirements.txt` (transitive — add explicitly).

## 11. Prioritized issues and risks

- **P0 — Critical:**
  - P0.1 Clean-startup + Reset wipe of `chroma_db` with 7868 chunks at risk (`app.py:99-108,225-235`). Back up `chroma_db/` before next UI launch; gate wipe behind explicit button/flag.
  - P0.2 Default model `qwen3:8b-q4_K_M` not installed (`answer.py:15` vs `/api/tags`). Documented quickstart fails until pulled or default changed.
- **P1 — High:**
  - P1.1 `benchmark.py` unrunnable — missing `benchmark_questions.json` (`benchmark.py:99`).
  - P1.2 Classifier over-triggers → wrong prompt/latency path (`answer.py:55-70`).
  - P1.3 No tests, no git, unpinned deps — any fix risks regression.
- **P2 — Medium:**
  - P2.1 Docs/code mismatch on embedding device; README benchmark numbers unverified; v1/v2 bank divergence.
  - P2.2 Bare `except: pass` error swallowing; formula duplication; unused import/call drift.
  - P2.3 Physics-only prompts/classifier vs multi-subject `data/`.
- **P3 — Low:**
  - P3.1 Dead reranker code, "Reranked" label, limit/prefetch naming, missing `numpy` in requirements, sidebar hotlink icon, duplicate filename with space.

## 12. Recommended improvement roadmap

- **Stage 0 — Stop data loss (do first, <1h):** back up `chroma_db/`; remove auto-wipe on launch (replace with explicit "Reset" + confirm); verify app boots read-only against existing 7868 chunks.
- **Stage 1 — Make documented path run (1-2h):** `ollama pull qwen3:8b-q4_K_M` OR set default to installed `llama3.1:8b` and note the swap; run `python generate_questions_v2.py`; smoke-test one theory + one numerical query and record latencies.
- **Stage 2 — Fix routing + honesty (half day):** tighten `is_numerical_question` (require digit+math-operator or explicit calc verb; strip section numbers like `5.6` before digit check; fix unit matching); relabel diagnostics to "RRF fused (reranker off)"; either delete `get_reranker` or gate behind flag; add `numpy` to requirements / pin versions.
- **Stage 3 — Verify claims (half day):** rerun `benchmark.py` on the 20-sample; replace README table with measured numbers or mark as historical.
- **Stage 4 — Portfolio hardening (1-2 days):** `git init` + commit, error surfacing (no silent pass), query history/export, empty/error states, input sanitization for markdown render, README quickstart with the model actually used.
- **Top 3-5 value features (after stages 0-2):** (1) persistent chat history + citation click-to-chunk; (2) subject-aware prompts (physics/chemistry/maths); (3) eval dashboard from `benchmark_results.json`; (4) ingest progress + skip-indexed-files; (5) optional cloud-LLM fallback. Per ponytail/YAGNI: do not add auth, Docker, vector-DB server, or framework rewrites — the embedded local design is the differentiator.

## 13. The best next task and its acceptance criteria

**Next task: Safe-boot fix — remove silent DB wipe and prove the existing 7868-chunk DB serves queries with the installed model.**

Why: it unblocks everything without new deps, prevents irreversible data loss, and resolves the model mismatch in one pass.

Acceptance criteria:
1. `chroma_db/` backed up (or copied) before any UI run.
2. `app.py` no longer deletes collections on launch; wipe only via explicit confirmed Reset.
3. `OLLAMA_MODEL` default matches an installed model OR README documents the required `ollama pull`.
4. `streamlit run app.py` boots, shows DB count ≈7868, Ollama online, one theory query returns an answer + ≥1 citation referencing `file/section/page`.
5. No new dependencies added; diff limited to `app.py` (+ `answer.py` default if changed).

## 14. Unknowns and questions that require human input

1. Which should be canonical: `qwen3:8b-q4_K_M` (pull it) or `llama3.1:8b` (already installed)? VRAM behavior differs.
2. Is the 7868-chunk `chroma_db` trusted (which PDFs ingested), or should it be rebuilt from `./data` via `ingest.py`?
3. Which question bank is canonical — v1 or v2? (Recommend v2; confirm then delete/archive v1.)
4. Are the README benchmark numbers historical (keep with date) or should they be replaced by a fresh run?
5. Target audience for next milestone: internship demo, portfolio piece, or real student tool? (Determines whether to invest in history/export/eval UI.)
6. Should Chemistry/Maths PDFs stay in scope or be split into per-subject collections?
7. Is re-enabling the reranker (`bge-reranker-base`) desired, or is RRF-only the permanent choice?

## 15. CHATGPT HANDOFF SUMMARY

> **Project:** Predator RAG — Windows-native local textbook RAG for NCERT 11th/12th Physics Q&A (JEE/NEET/CBSE theory, examples, formulas, exercises). Single Python app in the repository root.
> **Stack:** Python + Streamlit UI (`app.py`); PyMuPDF layout-aware chunking 1600/300 (`ingest.py`); `BAAI/bge-base-en-v1.5` embeddings + ChromaDB embedded (`./chroma_db`, collection `textbook_chunks`, 7868 chunks on disk) + BM25 + Reciprocal Rank Fusion k=60 (`retrieve.py`; cross-encoder reranker imported but disabled); local Ollama LLM default `qwen3:8b-q4_K_M`, ctx 12000, theory 512/think-off, numerical 2048/think-on (`answer.py`); `benchmark.py` + `generate_questions_v2.py` eval harness.
> **Status:** Pipeline code-complete, no tests, no git. Verified this audit: all files compile; ChromaDB has 7868 chunks; Ollama reachable but default model NOT installed (has `llama3.1:8b`, `nomic-embed-text:latest`, nothing loaded); CUDA available; classifier misroutes e.g. "5.6 torque" as numerical; `benchmark.py` broken (missing `benchmark_questions.json` — generate via v2 script). Not verified: end-to-end query, ingest rerun, benchmark numbers (README 60% recall/37s claims are historical).
> **Key decisions/constraints:** embedded Chroma over Qdrant server; native Windows over WSL2; CPU/auto embeddings to protect 8GB VRAM; fixed `num_ctx=12000` to avoid KV-cache reloads. Do NOT add servers/auth/Docker — local-embedded is the point.
> **Known issues:** (1) `app.py:99-108` wipes the DB on first launch + Reset button — back up `chroma_db` before running UI; (2) default Ollama model missing — pull or switch default; (3) benchmark needs generated JSON; (4) classifier over-triggers; (5) docs say CPU embeddings, code does auto cuda/cpu.
> **Commands:** `pip install -r requirements.txt` → `python ingest.py` (full ingest) → `python generate_questions_v2.py` (makes benchmark input) → `python benchmark.py` (writes results) → `streamlit run app.py` (UI at :8501). Prereq: Ollama running + model pulled.
> **Recommended next task:** safe-boot fix — remove silent wipe, align default model with installed one, boot UI read-only and prove one cited theory query against the 7868-chunk DB with no new deps.
> **Inspect first:** `app.py:92-145` (startup/wipe+status), `answer.py:55-70,100-160` (classifier+generation), `retrieve.py:122-197` (fusion), `ingest.py:270-337` (chunking), `benchmark.py:97-135` (input/warmup), `stack.md`, `README.md:38-95`.
