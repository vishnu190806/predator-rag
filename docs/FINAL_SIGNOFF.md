# FINAL_SIGNOFF.md — Predator RAG Release Candidate (rc-20261018)

Date: 2026-10-18 · Scope closure for the general-purpose, local-first RAG system.
This document is the final handoff. It does not supersede `RELEASE_CANDIDATE_REPORT.md`
or the research reports; those remain the accepted decision record.

---

## 1. Final release status

**RELEASE CANDIDATE — SIGNED OFF.**

- The real application was booted and exercised against the production `./chroma_db`, and
  every mandated workflow step passed with collected evidence (Section 2–3).
- One release-critical defect found during the live smoke was reproduced, fixed via
  red→green regression tests, and re-verified end-to-end in the real UI (Section 7).
- Regression suite: **110/110 passed** (Section 4). Compilation: **all 28 relevant files OK**.
- Repository created from scratch this session; clean initial commit annotated and tagged
  `rc-20261018` (Section 5). Working tree clean; all generated/local data properly ignored.
- No OCR, reranker, query rewriting, or multi-query retrieval was introduced; the system
  remains general-purpose (no subject/textbook hardcoding).

## 2. Real-database startup results

Environment at test time: Ollama reachable with `qwen3:8b`, `llama3.1:8b`, `nomic-embed-text`;
GPU idle before the run (0 MiB / 8188 MiB, 0 % util); port 8501 free.

| Checkpoint | Collections present (read-only inspection) |
|---|---|
| Before boot | `textbook_chunks` = **7,868** (only collection) |
| After real boot (`streamlit run app.py`, page loaded) | `textbook_chunks` = **7,868** (unchanged; app-owned `workspace_chunks` intentionally absent until first upload) |
| After uploading 2 test files (CSV + MD) | `workspace_chunks` = **5** (new) + `textbook_chunks` = **7,868** |
| After deleting one test document | `workspace_chunks` = **2** + `textbook_chunks` = **7,868** |
| After workspace Reset (sidebar button) | `textbook_chunks` = **7,868** (only collection; workspace deleted) |

- Startup deletion (`app.py` boot block) and the Reset button delete **only** the app-owned
  `workspace_chunks` collection; the foreign legacy collection survived both boots, uploads,
  deletion, and Reset. `$data/` on disk: 14 files / 97,215,465 bytes, **zero writes** in the
  window (source documents untouched).
- The temporary Streamlit server was stopped after the smoke (port 8501 released).

## 3. UI workflow results

Driven by real browser automation (Playwright MCP) against the live Streamlit server. The
kimi-webbridge daemon was started successfully but reported **"no extension connected"**
(the user-side browser extension was not attached), so per the fallback rule the same real
server/database was exercised with Playwright instead. No UI step was faked.

| Step | Result |
|---|---|
| App boot & empty workspace | ✅ "Workspace is empty" state shown; sidebar honest initial ChromaDB indicator |
| Upload 2 files (Markdown 306 B + CSV 163 B) via the real uploader | ✅ "Ingestion complete!", Indexed Files lists both, badge "Indexed Chunks: 5" |
| Grounded question 1 (CSV facts) | ✅ "The Zephyr Anemometer has 24 units in stock with a unit price of $149.50. [Source 1]" — Total 7.13 s (retrieval 0.16 s), streamed |
| Grounded question 2 (Markdown fact) | ✅ "A full battery charge for the Kite-Runner rover prototype takes exactly 7 hours [Source 1]" — 5.19 s |
| Format-aware citations | ✅ CSV → `rccatalog.csv … (rows 2-2 / 3-3 / 4-4) (type: table)`; MD → heading-title location `(type: heading)`; also shown per-chunk in Retrieval Diagnostics with RRF scores |
| Thinking-trace leak protection | ✅ Answer bodies regex-checked: no `think` tags / no reasoning-trace text in user-visible output (matches test_thinking_leak.py coverage) |
| Delete one document (row ✖, its chip removed first, then via the fixed row-only path) | ✅ Indexed Files drops to the remaining doc; chunks 5 → 2 |
| Reset action | ✅ Workspace cleared end-to-end; empty-state restored; DB back to `textbook_chunks` only |
| Original project source documents | ✅ Untouched (no writes; only the app's owned collection lifecycle changed) |

**Manual checks not completed:** none — all mandated steps were executed by automation.
Synthetic test files were created outside the project directory and removed afterwards.

## 4. Regression suite and compilation

- Final sign-off run (after every change in this task):
  `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py test_app_startup_preserves_foreign.py -q`
  → **110 passed, 1 warning, 31.39 s** (was 107 before this session; +3 new removal-guard regressions).
- `py_compile` clean for: `app.py, answer.py, ingest.py, extractors.py, retrieve.py, benchmark.py,
  run_isolated_benchmark.py, generate_questions*.py, model_lab.py, prompt_lab.py, think_probe.py,
  budget_verify.py, diag_misses.py, verify_*.py`, the 5 test files, and the committed eval-harness
  scripts (`postfix_runner.py, ui_realworld.py, eval_realworld.py, grader.py, eval_stress.py,
  ui_apptest.py, make_stress_corpus.py`).
- Citation metadata: format-aware (table rows / headings / text) — verified live and covered by tests.
- No new benchmark was run; the recorded 60-question budget comparison remains the accepted
  model-behavior evidence (see `RELEASE_CANDIDATE_REPORT.md`).

## 5. Git commit and release tag

- Repository initialized fresh this session (`main` branch; identity: `Vishnu <redacted>`).
- Initial RC commit `5d5a1f041b3ae01cd42c6df2cfe42e80c6d69f46` (51 files: source, tests, README,
  research/report docs, `requirements.txt`, `benchmark_questions.json` fixture, committed eval-harness scripts).
- Annotated tag: **`rc-20261018`** → target commit `5d5a1f041b3ae01cd42c6df2cfe42e80c6d69f46`.
  (In-session note: the tag annotation was re-created once, minutes after creation, to fix a typo in
  the message I authored; the target commit is identical and nothing referenced the tag in between.)
- `FINAL_SIGNOFF.md` is committed in a separate follow-up commit so the tag keeps pointing exactly
  at the verified RC state — no history or tag target was moved.
- `git diff --cached --check` findings (trailing whitespace / blank-at-EOF in `answer.py`, `app.py`,
  `benchmark.py`, `retrieve.py`, `README.md`) are **pre-existing style** from the original codebase,
  intentionally not mass-reformatted for the RC. No conflict markers, no secrets (pattern scan clean
  across the staged set).

## 6. Files intentionally excluded from version control

Via `.gitignore` (verified with `git check-ignore` and a zero-untracked `git status`):

- `chroma_db/` — local vector database (legacy `textbook_chunks` + runtime state), 139 MB.
- `data/` — user document corpora (97 MB).
- `embed_cache/` — content-addressed embedding cache (10.5 MB).
- `eval_confidence/`, `eval_general/`, `eval_realworld/`, `eval_stress/` — ephemeral eval workspaces,
  temp caches, logs, and result artifacts (~572 MB). The **code** of the supported harnesses is
  commited (see below).
- Regenerable research artifacts at root: `benchmark_isolated_*_results/_manifest.json`,
  `diag_misses.json`, `model_lab_results.json`, `prompt_lab_results.json`,
  `think_probe_results.json`, `verify_budget.json`, `verify_think_live.json`.
- `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, virtualenvs.
- `.env`, `.env.*`, `*.pem`, `*.key` (no secrets exist in the tree; scan verified).
- `Stack.png`, `PR` — superseded draft/binary notes (kept locally only).

Committed despite living under excluded directories (code only, added explicitly):
`eval_realworld/eval_realworld.py` (held-out question set module), `eval_realworld/postfix_runner.py`
(resumable benchmark harness), `eval_realworld/grader.py`, `eval_realworld/ui_realworld.py`,
`eval_stress/eval_stress.py`, `eval_stress/ui_apptest.py`, `eval_stress/make_stress_corpus.py`.
These are required so the committed regression suite (`test_eval_grader.py → eval_realworld.grader`)
and the benchmark harness the RC report references remain functional in a fresh clone.

## 7. Remaining known, non-critical limitations

1. **Fixed during sign-off (was release-critical):** deleting a document via its workspace ✖
   button was silently undone because Streamlit's uploader chip persisted across reruns (the app
   re-queued and re-indexed the file on the next rerun — server logs confirmed 5 re-ingest cycles).
   Fix: name-keyed `removed_files` session guard (`ingest.py` pure helpers +
   `app.py` wiring), suppressing re-ingestion while the chip persists; unblocked when the chip is
   removed or the same name is re-ingested; cleared on Reset. Verified in the real UI:
   row-✖ alone now sticks (5 → 2 chunks, stable across additional reruns). Regression tests:
   `test_per_document_removal_*` in `test_general_rag.py` (red→green cycle documented).
2. CSV citations show an internal `Sheet 'tmpXXXX.csv'` label from the extractor's temp-file name
   next to the correct original filename and row metadata — cosmetic.
3. The THEORY/NUMERICAL question-type heuristic is keyword-based; a numeric-stocking question was
   classified THEORY yet answered correctly via the same retrieval path.
4. `git diff --cached --check` reports pre-existing trailing whitespace/EOF style in a few files
   (documented in Section 5; deliberately not mass-reformatted).
5. Pre-existing, previously disclosed (unchanged, out of scope):
   `eval_realworld/postfix_runner.py::report()` raises a `TypeError` on abstain questions; the
   parent-observed timeout attempts of the eval harness are not carried into the final state rebuild
   (log-only evidence). Both affect the tools, not the product; fix list for a later iteration.
6. chromadb caches client instances by path string — relative `"./chroma_db"` paths can alias DBs
   across tests in one pytest process; the committed tests already handle this with absolute paths.
7. `pytest` is intentionally absent from `requirements.txt` (dev-only dependency; keep
   `pip install pytest` for development).
8. The kimi-webbridge browser extension was not attached during this session ("no extension
   connected"); the smoke was executed with equivalent Playwright automation against the same
   server. Users who prefer kimi-webbridge UI checks should re-run them manually if desired; no
   behavioral claim in this report depends on which browser drove the app.

## 8. Exact commands

```bat
:: 1. Install dependencies (Python 3.12 on Windows)
pip install -r requirements.txt
pip install pytest            :: dev/test only (see §7.7)

:: 2. Verify Ollama is running and the required models are present
curl.exe -s http://127.0.0.1:11434/api/tags
:: Required tags: qwen3:8b, llama3.1:8b, nomic-embed-text
:: (pull with: ollama pull qwen3:8b   — ~5.2 GB)

:: 3. Run the regression suite (expect 110 passed)
python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py test_app_startup_preserves_foreign.py -q

:: 4. Launch the application against the existing local database
streamlit run app.py
```

The app serves `http://localhost:8501`; the workspace starts clean each session, uploads index on
drop, Q&A streams with citations, and the sidebar Reset wipes only `workspace_chunks`.

## 9. Supported formats and local model configuration

**Ingestion formats** (via `extractors.py`, unified before chunking/embedding):
`.csv, .docx, .htm, .html, .json, .md, .pdf, .pptx, .txt, .xlsx, .xml`.

**Retrieval:** dense BGE embeddings (`sentence-transformers`) fused with BM25 (`rank-bm25`) via
**RRF**; the cross-encoder reranker is intentionally disabled (measured latency/recall penalty).
Citations carry per-format location metadata (table rows, headings, page/section text).

**Generation (actual, verified code + service state):**
- Local Ollama at `http://127.0.0.1:11434`; primary **`qwen3:8b`**, fallback **`llama3.1:8b`**
  (also the benchmark grader model), streaming via `/api/generate`.
- `NUM_PREDICT` (theory & numerical) = **4096**; `NUM_CTX` = **4096**; temperature 0.1;
  thinking stays enabled server-side but only the final `response` field is streamed/displayed.
- Embeddings: `BAAI/bge-base-en-v1.5` (loader name), content-addressed cache `CACHE_VERSION="v6"`,
  extraction pipeline `EXTRACTOR_VERSION="ext-v4"` — cache invalidation keys on file bytes + model
  + extraction/chunk parameters + version.
- No external services, no API keys, everything runs locally (Windows-native install).
