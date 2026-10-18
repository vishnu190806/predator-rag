# RELEASE CANDIDATE REPORT — Predator RAG (18 Oct 2026)

Status: release candidate, pending final sign-off. Scope frozen; historical research/evaluation
reports preserved; no benchmark artifacts overwritten by this closeout.

---

## 1. Selected model and final generation settings

All values verified in code this session (file:line).

| Setting | Value | Evidence |
|---|---|---|
| Generation model | `qwen3:8b` (Ollama) | `answer.py:17` |
| Fallback model | `llama3.1:8b` | `answer.py:20` |
| Grader model (benchmark) | `llama3.1:8b` (pinned) | `answer.py:21`, `benchmark.py:66` |
| Context length | `num_ctx=4096` everywhere (completion, warmup, grader) | `answer.py:52`, `app.py:34`, `benchmark.py:72` |
| Temperature | 0.1 | `answer.py:210,267` |
| Thinking mode | No `think` override sent (model default: on); private thinking never captured or rendered | `answer.py:204-214, 261-271`; `test_answer_config.py::test_no_think_override_sent` |
| Theory budget | `NUM_PREDICT_THEORY = 4096` | `answer.py:37` |
| Numerical budget | `NUM_PREDICT_NUMERICAL = 4096` | `answer.py:38` |
| Honest-empty behavior | Thinking exhausted / timeout → exact `EMPTY_ANSWER_MESSAGE`, never substituted | `answer.py:187-192`; leak guard `answer.py:179-180` |
| Generation timeout | 300 s (requests) | `answer.py:219,275` |
| Retrieval | BGE `bge-base-en-v1.5` + BM25 + RRF k=60 + BM25 additive score weight 0.05; reranker intentionally disabled | `retrieve.py:96,99-147`; `README` notes measured cost of reranker |
| Extraction / cache | `EXTRACTOR_VERSION="ext-v4"`, `CACHE_VERSION="v6"`, content-addressed cache (file bytes + extractor version + chunk params + embedding model) | `extractors.py:26`, `ingest.py:35,49-55` |
| Corpora / workspaces | Single embedded ChromaDB `./chroma_db`, collection `workspace_chunks`; uploads define workspace; no subject hardcoding | `ingest.py:19`; `retrieve.py:17` |

## 2. Generation-budget evaluation and decision (2048 vs 4096)

**Background.** The theory budget was raised 2048 → 4096 on 18 Oct after controlled experiments:
isolated `su1` sweep (8 trials per arm) showed 2048 → 1/8 correct (7/8 empty, `done_reason=length`),
3072 → 4/8, 4096 → 5/8; six-format controls were all correct ×3 at 4096 (no regression). These were
small samples; the full held-out validation was explicitly pending before release
(`RAG_GENERATION_RELIABILITY.md` §8.5).

**Validation run (this closeout, 18 Oct).** One complete, uninterrupted 60-question held-out run with
`eval_realworld/postfix_runner.py --rebuild`:

- Harness: resumable parent/worker, per-question wall budget 200 s, ≤1 retry, both attempts
  persisted, isolated storage (`eval_realworld/tmp_postfix/{chroma,cache}`) — production
  `./chroma_db` never touched. Config metadata recorded (`meta`: `ext-v4` / cache `v6` / chunk
  counts verified against shipped extractors before any question ran).
- Production config only: `qwen3:8b`, ctx 4096, temp 0.1, no `think` override, theory budget 4096,
  shipped retrieval (BM25 weight 0.05, prefetch 20 → limit 6). Deterministic graders
  (`grader.py`: corrected numeric-aware + legacy substring). No LLM judge in this harness
  (the grader-model pin applies to `benchmark.py`, unchanged).
- Comparator: `postfix_results_2048_20261017.json` — a complete 60/60 run of the same harness on the
  same corpus/extractor/cache versions (ext-v4 / v6) with theory budget 2048. Identical scoring
  applied to both artifacts for this comparison (`analyze_budget.py`, corrected + legacy).

| Metric (final outcomes, harness policy) | 2048 run (17 Oct artifact) | 4096 run (18 Oct) |
|---|---|---|
| Corrected grader accuracy | 0.9333 (56/60) | 0.9333 (56/60) |
| Legacy grader accuracy | 0.8500 (51/60) | 0.8667 (52/60) |
| Empty answers | 1/60 (`su1`) | 1/60 (`wb8`) |
| Timeouts / errors (final) | 0 / 0 | 0 / 0 |
| Wall latency median / p95 / max | 11.81 s / 48.94 s / 57.0 s | 9.28 s / 43.21 s / 104.26 s |
| Generation latency (ok) median / max | 11.45 s / 56.97 s | 9.15 s / 56.48 s |
| Attempt-level events | none | `fr2` attempt-1 timeout (200 s) → attempt-2 ok (14.78 s) |

**Effect on previously correct controls:** 55 of 56 previously-correct questions stayed correct; the
one 2048-empty question (`su1`, the chronic thinking-exhaustion case) became **correct in 11.78 s at
4096**; one 2048-correct question (`wb8`, numerical cross-document calculation) became **empty after
104 s of hidden thinking** at 4096. Aggregates are therefore equal (56/60 both) and the empty rate
is unchanged (1/60 ≈ 1.7%); the identity of the empty moved from the chronic theory case to one
stochastic numerical instance in a question class (`wb7`/`wb8`) that earlier reports already flag as
flaky (`wb7` itself improved 0→1 this run).

**Decision: KEEP `NUM_PREDICT_THEORY = 4096`.** Rationalized against actual reliability, correctness,
worst-case latency, and generation cost: no concrete defect of the budget is established; the known
chronic empty class is repaired; aggregate accuracy equals the 2048 comparator; typical latency
improved (median 11.81 → 9.28 s). The regression risks observed (one new empty; one retry-after-
timeout on an already-wrong question; worst-case latency 57 s → 104 s on the empty) are bounded by
the shipped per-call timeout and the honest-empty path, and are listed in §7 as monitored
non-critical defects. No further budget sweeps are warranted.

**Comparability disclosures.** (a) Generation is stochastic (temp 0.1, sampling on): both runs can
differ question-by-question; ±1 question at n=60 is within noise. (b) Corpus versions are identical
for the main comparison (ext-v4 / cache v6, verified chunk counts both sides); the earlier
`postfix_report.60run.json` (ext-v3, legacy 0.7833) is an older-corpus artifact and was NOT used as
the primary comparator. (c) The 4096 run re-indexed its isolated corpus (27.36 s embed build) before
starting — normal `--rebuild` behavior. (d) Harness fidelity gap discovered this run: a parent-
observed timeout attempt (fr2) is written to the interim state but the final state is rebuilt from
the stream only, so that attempt appears in `run4096_20261018.log` yet is absent from
`postfix_results.json`. Evidence for the timeout is therefore textual (run log) rather than
machine-summary; the harness was NOT modified in this closeout (scope), and the facts are disclosed
here. (e) The parent's `report()` currently crashes on abstain questions (`recall3=None` breaks the
latency/recall sums — TypeError). The run's per-question data was complete (60/60) and all summary
numbers in this report were recomputed externally from the artifacts, so the validation stands; the
crash is listed as a non-critical harness defect in §7.

## 3. Supported document formats and known limitations

Supported today (`extractors.py:28-40`, verified by the regression suite and the real-corpus UI run):
`pdf`, `docx`, `pptx` (incl. speaker notes), `xlsx` (sheet + row groups), `csv` (row groups),
`txt`, `md` (heading-aware), `html/htm`, `json` (600-char records), `xml` (long-leaf preservation
since ext-v4). Format-specific source locations: PDF page / DOCX heading / PPTX slide (+ notes) /
XLSX sheet+rows / CSV rows / MD+HTML headings / JSON+XML record tags. Unsupported extensions and
oversized/empty files are rejected with a clear message; extraction failures never kill ingestion
(`extractors.py:471-508`; demonstrated in `ui_realworld.py` and `test_general_rag.py`).

**Known limitations (all documented in prior reports, unchanged):** no OCR backend is installed, so
scanned/image-only PDFs yield little or no text (no OCR claims are made anywhere in this project);
`fr7/wb8`-class table/passage-ranking and `su1`-type long-thinking cases are improved but not solved;
`id43` can still loop-exhaust even at 4096 (recovered by the honest-empty path); Streamlit's file
uploader widget cannot be driven by AppTest (uploads are simulated in tests; a manual procedure is
documented in `RAG_REALWORLD_EVALUATION.md`).

## 4. Test commands and actual outcomes (this session)

| Command | Result |
|---|---|
| `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py -q` | **105 passed** (pre-eval gate, 31.65 s) |
| `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py test_app_startup_preserves_foreign.py -q` | **107 passed** (after the release-critical fix, 29.84 s) |
| new `test_app_startup_preserves_foreign.py` alone, pre-fix | **2 failed** (red — reproduced silent deletion of foreign collections on app boot) |
| new `test_app_startup_preserves_foreign.py` alone, post-fix | **2 passed** (green) |
| `python -m py_compile app.py ingest.py retrieve.py answer.py benchmark.py extractors.py eval_realworld/postfix_runner.py eval_realworld/eval_realworld.py` | OK |
| `python -m py_compile app.py test_app_startup_preserves_foreign.py` | OK (post-fix) |
| `python eval_realworld/ui_realworld.py` | all steps pass: ingest, indexed list, streamed grounded answer + citations + slide location, leak-free, no exception, per-file removal, reset-to-empty |
| `python eval_stress/ui_apptest.py` | all steps pass: toolbar workflow, grounded answer + citations, no think leak, delete, reset |
| `python eval_realworld/postfix_runner.py --rebuild` | 60/60 recorded (`run4096_20261018.log`; §2) |

## 5. Current performance measurements and conditions

Conditions: Acer Predator Helios Neo 16 — i9-14900HX, RTX 4070 Laptop 8 GB, 16 GB DDR5, native
Windows, local Ollama (127.0.0.1), single-user, GPU exclusive during the eval run, temp 0.1,
ctx 4096. Wall = retrieval+generation per question.

From today's 60-question run (4096): wall median 9.28 s, p95 43.21 s, max 104.26 s (the lone empty),
mean 13.93 s; retrieval redeterministic pass median ~0.02–0.03 s class as before. Trailing 2048-baseline
condition: median 11.81 s / p95 48.94 s / max 57.0 s. Resource notes from the current README:
qwen3:8b resident ≈ 6.1 GB / 8 GB VRAM; ≈1.38 GB process RAM; cache-hit re-ingest ≈0.08 s;
index build 17 chunks 0.8 s (isolated 10-corpus rebuild measured 27.36 s this session).

## 6. Files changed and why

1. **`app.py`** — release-critical data-loss fix. The first-session boot block deleted EVERY
   collection in `./chroma_db`, destroying foreign collections the app does not own (concretely the
   legacy `textbook_chunks`, ~7,868 chunks, would have been silently lost on the next app launch).
   Fix: boot reset now deletes only the app's own `workspace_chunks` collection, matching the
   documented per-session lifecycle and the Reset button's scope. Intentional lifecycle unchanged.
2. **`test_app_startup_preserves_foreign.py`** (new) — TDD regression test for #1: seeds a foreign
   collection + owned workspace in an isolated tmp Chroma dir, boots the real app via AppTest,
   asserts foreign collections survive and the own workspace resets. Handles chromadb's in-process
   client cache by pinning `CHROMA_DB_PATH` per test via monkeypatch.
3. **`README.md`** — corrected two statements verified stale: standard-question budget now documents
   4096 (was 2048) with the 18-Oct validation reference; regression-test command now lists all five
   test files. Setup/execution instructions were otherwise verified accurate (e.g. `ingest_files`
   exists at `ingest.py:713`; model names match `/api/tags`).
4. New evaluation artifacts created this session (nothing historical overwritten):
   `postfix_results.json` (4096 run state, runner's canonical output),
   `postfix_results_2048_20261017.json` + `postfix_report_60run_2048_20261017.json` (SHA-pinned
   archives of the comparator), `run4096_20261018.log` (run transcript incl. the fr2 timeout line),
   `eval_realworld/tmp_postfix/results_stream.jsonl` (attempt-level truth).
   Note: `eval_realworld/ui_results.json` and `eval_stress/ui_results.json` are regenerated outputs
   of the UI scripts and were replaced by this session's passing runs (previous snapshot not
   retained — they are test outputs, not benchmark data).

## 7. Remaining (non-critical) defects and observations

Reliability / latency (monitored):
- `wb8`-class numerical answers can exhaust hidden thinking at 4096 and surface as an honest empty
  (1/60 this run); `fr7/f3` passage-ranking and `fr2` timeout-class stalls remain edge cases.
- `su1` improved (empty → correct in this run) but its isolated 8-trial rate at 4096 is 5/8, i.e.
  stochastic, not guaranteed.
- Worst-case latency grows with budget (104 s empty, one 200 s-timeout-retry at 4096 vs max 57 s at
  2048 in this comparison).

Harness (non-production, left untouched by scope decision):
- `postfix_runner.py::report()` raises TypeError on abstain questions (`recall3=None`);
  post-17-Oct scorer change. Workaround used: external recomputation (§2). A one-line
  `(value or 0)` guard would fix it.
- Parent-observed timeout attempts don't survive the final state rebuild (log-only evidence).

Workspace / docs:
- Streamlit uploader widget not AppTest-drivable (simulated uploads; manual procedure documented).
- `pytest` is used by four test files but is not in `requirements.txt` (dev dependency; not added
  per the no-new-deps rule). `defusedxml` is listed but the extractor uses stdlib XML.
- Legacy scripts (`benchmark.py` with its physics question bank, `generate_questions*.py`,
  `think_probe.py`, budget experiment scripts) remain as historical/one-off utilities, clearly
  out of the shipped path.

## 8. Main database state — confirmation

`./chroma_db` was never used for evaluation this session (all evals write to isolated
`eval_realworld/tmp_postfix`, `tmp_*` copies, and pytest tmp dirs). Final state verified after all
work: one collection `textbook_chunks` with exactly **7,868 chunks** — the same artifact and count
recorded by all historical audits. The sqlite file's `LastWriteTime` changes on connection because
a `PersistentClient` open performs sqlite bookkeeping (differential-verified: a read-only open+list
updates the mtime); the collection inventory and chunk count are the authoritative content evidence.
The boot-wipe fix in §6.1 guarantees this collection survives app launches.

## 9. Recommendation for the final sign-off task (Prompt 2 of 2)

1. **Manual boot smoke on the real machine state** (the one test automation cannot do): run
   `streamlit run app.py` against the existing `./chroma_db` (containing `textbook_chunks`), confirm
   the legacy collection survives boot (`chroma_db` count stays 7,868), then upload ≥2 fresh files
   across formats, ask one grounded question, verify citations, remove one file, and finally press
   Reset (workspaces only; originals untouched).
2. **Version control**: the project still has no git repo — initialize and commit the RC
   (`git init`, add everything, tag e.g. `rc-20261018`) before any further change.
3. Optional small hygiene fixes (post-RC, one-line each, listed in §7): null-guard
   `postfix_runner::report()`, persist parent-timeout attempts in the final state,
   decide on `defusedxml` and pytest placement in requirements.
4. Re-run the five-file regression suite once more at sign-off; expect **107 passed**.
