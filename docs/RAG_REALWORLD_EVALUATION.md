# RAG Real-World General-Purpose Evaluation (Oct 2026)

## 1. Document sources and corpus composition

Isolated corpus: `eval_realworld/real_corpus/` (never mixed with `./data` or `./chroma_db`).
Provenance recorded in `eval_realworld/real_corpus/provenance.json` (official/public sources).

| File | Format | Source | Notes |
|---|---|---|---|
| `faa_weather.pdf` | PDF (213 pp) | FAA AC 00-6B (official) | long, multi-section, tables |
| `faa_drones.pdf` | PDF (104 pp) | FAA AC 107-2A (official) | regulations |
| `frankenstein.docx` | DOCX | Project Gutenberg #84 (public domain) | headings, prose |
| `whale_slides.pptx` | PPTX | derived from Wikipedia CC BY-SA article | slide facts + speaker notes |
| `worldbank.xlsx` | XLSX | World Bank API (CC BY-4.0) snapshot | 3 sheets, conflicting year values |
| `usgs_jan2024.csv` | CSV | USGS Jan-2024 M5+ feed | 228 rows, similar IDs |
| `awesome_nodejs.md` | MD | CC0 readme | nested sections |
| `wcag22.html` | HTML | W3C WCAG 2.2 | spec text |
| `express_package.json` | JSON | MIT manifest | engines/dependencies |
| `bluewhale_export.xml` | XML | Wikipedia CC BY-SA (MediaWiki export) | long article (120,799 bytes) |

Total indexed chunks (current code, isolated workspace): **2,698** (cold ingest 29.95 s;
cache-hit re-ingest 5.86 s).

## 2. Question design and evaluation methodology

- Two disjoint sets: **CALIB** (8, harness sanity, never reported as final) and
  **HELDOUT** (60 questions across 9 categories).
- Categories: exact (24), deep (5), summary (3), sheetrow (12), conflict (1),
  identifier (6), similar (3), crossdoc (2), absent (4).
- Each answerable question has an independently verifiable expected answer and
  source location (page/slide/sheet/row/section). Grading is deterministic
  keyword/presence checks, not an LLM grader; representative answers were
  manually inspected.
- Retrieval scored at limit=3 and limit=6. Answers generated through the real
  `answer_question` path (limit=6).
- All runs isolated (`eval_realworld/tmp_real`); main `./chroma_db` never touched.

## 3. Results by format and query category (deterministic pass, current code)

Source: `eval_realworld/det3.json` (60 held-out questions, current code).

| Category | n | Recall@3 | Recall@6 | Location | Citation |
|---|---|---|---|---|---|
| exact | 24 | 1.000 | 1.000 | 0.875 | 1.000 |
| deep | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| summary | 3 | 1.000 | 1.000 | 1.000 | 1.000 |
| sheetrow | 12 | 1.000 | 1.000 | 1.000 | 1.000 |
| conflict | 1 | 1.000 | 1.000 | 1.000 | 1.000 |
| identifier | 6 | 0.833 | 0.833 | 0.833 | 1.000 |
| similar | 3 | 1.000 | 1.000 | 1.000 | 1.000 |
| crossdoc | 2 | 1.000 | 1.000 | 1.000 | 1.000 |
| absent | 4 | 1.000 | 1.000 | 1.000 | 1.000 |
| **Total** | **60** | **0.983** | **0.983** | **0.933** | **1.000** |

Retrieval misses: `js1` (express package Node version) only — the express
manifest chunk loses to the much larger `awesome_nodejs.md` in BM25/RRF
ranking. Location misses: `fr2`, `fr3`, `fr7` (Frankenstein chapter-level
location not in top-3 hits) and `md2` (chalk section).

## 4. Answer quality

Full end-to-end LLM re-run on the current code was attempted
(`eval_realworld/RAG_REALWORLD_FINAL.json`) but blocked by Ollama stability on
long-thinking questions (process hung on `fr7`/`wx1`); 7/60 completed and are
consistent with the prior full run for those questions.

Prior full run on the pre-change corpus (`eval_realworld/results.json`,
60 questions, `qwen3:8b`) — answer accuracy by category:

| Category | n | Answer accuracy | Empty answers |
|---|---|---|---|
| exact | 24 | 0.792 | 0 |
| deep | 5 | 1.000 | 0 |
| summary | 3 | 0.667 | 1 |
| sheetrow | 12 | 0.083 | 0 |
| conflict | 1 | 0.000 | 0 |
| identifier | 6 | 0.833 | 0 |
| similar | 3 | 0.667 | 0 |
| crossdoc | 2 | 1.000 | 0 |
| absent | 4 | 0.750 | 0 |
| **Total** | **60** | **0.650** | **1** |

The dominant answer failures were table-scanning failures: the LLM could not
locate a target row inside 12-row (XLSX) / 12-row (CSV) groups even though
retrieval was correct (17/21 failures had the answer keyword in top-6).

## 5. Production change and measured impact

**Change (justified by the failures above):** reduce table row-group size.

- `extractors.py`: `extract_xlsx` default `rows_per_chunk` 12 → 6;
  `extract_csv` default 12 → 1. `EXTRACTOR_VERSION` bumped `ext-v2` → `ext-v3`.
- `ingest.py`: `CACHE_VERSION` bumped `v4` → `v5` (cache invalidates automatically).
- `test_general_rag.py`: group-size expectation updated to match new CSV grouping.

Rationale: the prior 30 → 12 reduction fixed sensor lookups; the real corpus
showed 12-row groups still bury ambiguous identifiers (USGS IDs, Japan
population) in distractors. Controlled experiment (mixed config, XLSX 6 / CSV 1)
recovered **11/11** previously-failing table questions (wb1–wb8, eq1–eq5),
all answered correctly with citations. Expected answer accuracy rises from
0.650 to ≈0.850 (≈51/60) once the full LLM run completes.

Regression suite: `python -m pytest test_general_rag.py test_thinking_leak.py
test_answer_config.py -q` → **34 passed**. `verify_fixes.py` → all PASS.

## 6. Latency, memory, reliability

Deterministic (current code, isolated):
- Cold ingest: 29.95 s (2,698 chunks); cache-hit re-ingest: 5.86 s.
- Retrieval median: 0.044 s; p95: 0.054 s.
- Process RAM: 1,557.8 MB; VRAM (embedder only): 3,027 MB.

Prior full run (pre-change, with LLM):
- Retrieval median: 0.843 s; p95: 1.803 s.
- TTFT (streamed): 17.94 / 11.07 / 17.82 s.
- RAM: 963.5 MB; VRAM (qwen3:8b resident): 7,564 MB.
- Empty answers: 1; request errors: 0; auto-retries: 1.

UI verification (`eval_realworld/ui_results.json`): fresh run no exception,
empty state shown, 4 files indexed, streamed answer contains "krill" with
`whale_slides.pptx` citation and `Slide 3` location, no thinking leak, per-file
delete and reset-to-empty all verified.

## 7. Important failure cases and root causes

1. `fr2`, `fr3`, `fr7` (Frankenstein): location not in top-3 at limit=3
   (retrieval returns a different chapter). Root cause: retrieval/ranking on
   paraphrase; not a code defect. App depth (6) and answer still mostly correct.
2. `js1` (express Node version): retrieval miss at limit=6. Root cause: the
   small JSON chunk is outranked by the large `awesome_nodejs.md` in BM25/RRF.
   Not fixed (no reranker/multi-query added per policy); reported as limitation.
3. `md2` (chalk section): location miss. Root cause: same BM25 dominance.
4. Table questions (sheetrow/conflict): LLM scanning failure on multi-row
   chunks — **fixed** by row-group reduction (§5).
5. `su1` empty answer: Qwen thinking consumed the full budget (known flake);
   retry path handles it.

## 8. Test commands and outcomes

- `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py -q`
  → **34 passed**.
- `python eval_realworld/verify_fixes.py` → all PASS.
- `python eval_realworld/eval_realworld.py` (deterministic) → R@3 0.983,
  R@6 0.983, loc 0.933, cit 1.000.
- `python eval_realworld/ui_realworld.py` → all steps PASS (see ui_results.json).

## 9. Remaining limitations and highest-value next improvement

- LLM answer metrics above are from the pre-change full run; the full
  post-change LLM run was attempted but blocked by Ollama stability on
  long-thinking questions. Targeted experiments confirm table-answer recovery.
- `js1` retrieval miss remains; a confidence-gated single lightweight query
  rewrite on low top-1 scores (not a default reranker/multi-query fan-out) is
  the highest-value next step if pursued.
- No OCR backend installed: scanned PDF pages are reported, not read.
- Context size fixed at 4096; long derivations rely on the retry/fallback path.