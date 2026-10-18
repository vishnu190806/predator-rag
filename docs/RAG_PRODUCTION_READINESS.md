# RAG Production Readiness — Stress Evaluation (Oct 2026)

## 1. Environment and configuration

- Acer Predator Helios Neo 16, i9-14900HX, RTX 4070 Laptop 8 GB, 15.7 GB RAM,
  Windows native, Python 3.12.10, torch 2.11+cu128 (CUDA available).
- Ollama models: `qwen3:8b` (default generation), `llama3.1:8b` (fallback/grader).
- Pipeline: BGE-base-en-v1.5 (CUDA) + BM25 + RRF(k=60), prefetch 20 → 6 shown;
  NUM_CTX=4096, theory budget 2048, numerical 4096, temperature 0.1.
- All evaluation ran in isolated temp workspaces. The real `./chroma_db`
  (7868-chunk physics collection) was verified untouched after every run.

## 2. Corpus and question distribution

`eval_stress/stress_corpus` (all fixtures synthetic): 12-page PDF
(`harbor_ops.pdf`), DOCX with headings + rate table, 5-slide PPTX with speaker
notes, XLSX with 3 sheets (same SKUs, different yearly prices + discounts),
131-row CSV, long Markdown runbook, HTML (with planted script text), JSON, XML,
TXT with planted instruction-override, plus `malformed.pdf` and `notes.xyz`
failure fixtures.

43 questions (`eval_stress/eval_stress.py`): exact 8, deep-doc 6, sheet/row 7,
cross-doc 5, similar-entity 5, conflict 2, summary 3, abstain 5, injection 2.
Each has an explicit expected file/location/keywords; no LLM grader.
Retrieval is scored at strict limit=3 (app uses 6); answers go through the
real `answer_question` path (limit=6).

## 3. Fixes implemented (before → after, all reproduced first)

1. **Cache misattribution of duplicate content.** Same bytes ingested as
   `crew_DUPLICATE.csv` were indexed under `crew.csv` (wrong citations,
   unremovable by the new name). Cause: content-addressed HIT returned cached
   metadatas verbatim. Fix: remap `file` metadata to the requested name on
   every HIT (`ingest.py`). Verified by new test (attribution + removal).
2. **RRF `KeyError` crash on duplicates.** The near-duplicate guard dropped a
   fused key's representative while its score survived → `key_to_hit[key]`
   raised. Found by the test above. Fix: `.get()` guard plus per-source
   best-rank dedup, so duplicate chunks can no longer stack RRF mass and crowd
   out diverse hits (`retrieve.py`). The x4 miss during diagnosis traced to
   harness-pollution duplicates amplified by this bug.
3. **Table row-groups too large (30 → 12).** Sensor lookup S-1117 failed 0/3
   (39–50 s, wrong/empty) although the target chunk ranked #1: 30-row groups
   overflowed the chunk size, split mid-table, and buried the row in
   distractors. Controlled experiment on the full workspace: 12-row groups →
   2/2 correct in ~10 s. Adopted 12 (`extractors.py`, EXTRACTOR_VERSION
   bumped to ext-v2, one-time table re-encode). New unit test locks group
   sizing and row_range accuracy.
4. **Harness hygiene (eval-only).** Cache-hit timing re-ingested a file and
   polluted retrieval ranks; now times the encode-cache path without DB
   writes. Three sensor `loc` expectations corrected to true row ranges.

No new runtimes, databases, rerankers, cloud services, or heavy deps added.

## 4. Results by format and category (`--with-llm`, 14 Oct 2026)

| Category | n | Recall@3 | Loc | Answer |
|---|---|---|---|---|
| exact | 8 | 1.00 | 0.875 | 1.00 |
| deep-doc | 6 | 1.00 | 1.00 | 1.00 |
| sheet/row | 7 | 1.00 | 1.00 | 1.00 |
| cross-doc | 5 | 1.00 | 1.00 | 0.80 |
| similar-entity | 5 | 1.00 | 1.00 | 1.00 |
| conflict | 2 | 1.00 | 1.00 | 1.00 |
| summary | 3 | 1.00 | 1.00 | 1.00 |
| abstain | 5 | — | — | 1.00 (5/5 refused) |
| injection | 2 | 1.00 | 1.00 | 1.00 (no PWNED/password leak) |
| **Total** | **43** | **1.00** | **0.977** | **0.977 (42/43)** |

Citation validity 1.00 throughout (no invented pages/slides/rows).
Legacy general eval re-run after the chunking change: 12/12 unchanged.
Regression suite: **30 passed**
(`test_general_rag.py` + `test_thinking_leak.py` + `test_answer_config.py`).

## 5. Failed cases and root causes

- **sh5 (fixed):** LLM scanning failure on oversized table chunks → fixed by
  row-group change (§3.3). Post-fix: 9.2 s pass.
- **x5 (known flake, 2/4 across runs):** cross-doc question; retrieval always
  correct, but Qwen thinking sometimes consumes the full 2048 budget with zero
  response tokens. Retry passes (20.3 s). No budget increase: poor trade-off,
  no termination guarantee. The honest-empty + retry/fallback path handles it.
- **ex1 loc at k=3:** expected file retrieved; exact page chunk ranked 4th at
  the strict eval depth. App depth (6) answers it correctly (17.6 s gen in an
  earlier run, keyword hit). Not a defect; eval strictness documented.

## 6. Latency and resources (medians where applicable)

- Import (torch/sentence-transformers/chromadb): ~16–21 s one-time per process.
- Embedder load (CUDA): ~23 s one-time; Ollama model load similar (amortized
  in the Streamlit process; warmup thread overlaps uploads).
- Index build, 54 chunks, true cold: 7.44 s; cache-hit re-ingest: 0.02 s.
- Retrieval: median 0.019 s, p95 0.023 s (n=43; first-query model load excluded).
- Time to first token (streamed): 5.7 / 6.2 / 9.4 s sampled.
- End-to-end generation: typically 5–10 s; table/cross-doc/conflict 10–35 s;
  flake retries up to ~48 s.
- Process RAM ~0.8–1.4 GB; VRAM ~6.1–6.3 GB of 8 GB with qwen3:8b resident.
- Extraction per format: pdf 0.01–0.04 s, docx ~0.15 s, pptx ~0.17 s,
  xlsx ~0.26 s, csv/md/json/xml ≤ 0.01 s; malformed/unsupported correctly
  rejected with messages.

## 7. UI and workspace lifecycle (isolated copy + AppTest, no browser)

`eval_stress/ui_apptest.py` → `ui_results.json`: fresh-run clean, empty-state
shown, 3-format indexed list rendered, real streamed answer contained the
expected fact with citations, no thinking text, per-file delete verified in
Chroma (`{'rates.xlsx': 3, 'safety_brief.pptx': 6}`), reset returned to empty
(`{}`). One transient first-run exception appeared once (all assertions still
passed) and never reproduced in 5 subsequent runs — attributed to cold-start
flake (remote sidebar icon fetch), not a product defect. The empty-retrieval
warning path was also observed rendering honestly. **Limitation:** the
file_uploader widget has no AppTest accessor in this Streamlit version, so
uploads were simulated by indexing + seeding session state; the widget chrome
itself was not automation-tested. Malformed/oversized/unsupported handling is
covered at the handler level by tests.

## 8. Commands executed

- `python eval_stress/make_stress_corpus.py`
- `python eval_stress/eval_stress.py [--with-llm]` → `eval_stress/results.json`
- `python eval_stress/ui_apptest.py` → `eval_stress/ui_results.json`
- `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py -q` → 30 passed
- `python eval_general/eval_general.py --with-llm` → 12/12 (no regression)

## 9. Remaining limitations and next improvement

- Synthetic corpus (n=43); real-world noisy collections will score lower.
  Keyword grading is weaker than independent grading; both failures were
  manually inspected, the rest were not line-reviewed.
- Qwen thinking-length flake (~1/4 on the hardest cross-doc question):
  honest-empty + retry is the current handling. Highest-value next step, if
  pursued, would be a **confidence-gated single lightweight query rewrite
  only on low top-1 retrieval scores** — not a default reranker or
  multi-query fan-out (both previously measured unjustified).
- Duplicate bytes keep the original `[filename]` heading prefix inside chunk
  text on cache HIT (metadata attribution is correct; cosmetic only).
- No OCR backend installed: scanned pages are reported, not read.
- `ingest_files` API does not skip already-indexed content (the app layer
  does via `processed_files`).
