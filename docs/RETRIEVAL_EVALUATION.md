# RETRIEVAL_EVALUATION — Predator RAG benchmark, diagnosis & evidence-backed fix

Date: Oct 2026. Machine: Windows, RTX 4070 Laptop (8188 MiB VRAM), 16.9GB RAM.
Prior reports (`PERFORMANCE_RESEARCH.md`, `PERFORMANCE_BENCHMARK.md`) preserved;
this file adds the full-benchmark validation and retrieval-failure diagnosis.
Previous "3/6 strict hits, 2/2 e2e" figures are superseded by the measurements below.

## 1. Environment, model, corpus, benchmark config

- **Inference:** Ollama 0.35.1, `llama3.1:8b` Q4_K_M, 100% GPU, `answer.NUM_CTX=4096`
  for warmup/generation/grading; temp 0.1; caps 512 theory / 2048 numerical.
- **Corpus for evaluation:** ISOLATED keph105/106/107 (NCERT physics ch. 5–7),
  626 chunks pre-fix → 628 post-fix (see §5). Built via embed-cache fast path in
  ~3s. The main `./chroma_db` (7868 chunks, 100% `Mathematics-Class-12-Part-2.pdf`)
  cannot evaluate physics questions and was **never touched**; tmp DBs deleted after
  each run. Nothing below is claimed about the full textbook corpus.
- **Questions:** `benchmark_questions.json` (from `generate_questions_v2.py`, 99 Qs:
  20/20/20/20/19 across NCERT Theory / NCERT Exercise / JEE Main / NEET /
  Formula-Based). Harness samples first 5 per category by id → **20 questions**,
  all referencing ch. 5–7 sections present in the isolated corpus.
- **Harness:** unmodified `benchmark.run_benchmark()` (recall = section-substring
  or section-number match; correctness = LLM grader temp 0; citation = section-number
  mentioned in answer/citations). Command: `python run_isolated_benchmark.py`.
  Output: `benchmark_isolated_phys626_results.json` + manifest.

## 2. Results (n=20, isolated physics corpus, pre-fix parse)

| Metric | Result |
|---|---|
| Retrieval recall | **60.0%** (12/20) |
| Answer correctness (LLM-graded) | **45.0%** (9/20) |
| Citation accuracy | **65.0%** (13/20) |
| Avg end-to-end latency | 9.11s (retrieval ~0.03s steady; Q1 7.4s incl. one-time embedder load; worst Q12 46s long ramble) |
| Peak VRAM / process RAM | 5802MB / 1396MB — within budget |

By category (recall / accuracy): Theory 3/5, 3/5; Exercise 3/5, 1/5; JEE 3/5, 1/5;
NEET 3/5, 4/5. Numerical reasoning is the weak dimension (1/8 correct among
computation-heavy items).

## 3. Metric-by-metric evaluation (with manual inspection)

- **Retrieval quality:** 12/20 strict hits. Of 8 misses, component diagnosis
  (`diag_misses.py`: dense top-20 + BM25 top-20 + RRF top-6) shows only **1 real
  defect** — Kepler/7.2 (§5). The rest retrieve content-correct chunks under
  different labels (power definition text under boundary section 5.11; verbatim
  NCERT exercise for the cylinder question) or topically adjacent sections.
- **Answer correctness:** manually reviewed 8 zeros + 4 ones — **grader agreed in
  all 12 cases**. Failure modes (all with correct context retrieved in 6 of 9
  inspected zeros): garbled formula (id=1: "dK/dt = FΔx"), ignored friction (21),
  backwards efficiency (22: ×0.3 instead of ÷0.3), incomplete derivation (23),
  algebra sign error (24: negative KE), conservative-force framing for friction
  + wrong distance (41), rambling integration failure (42), hallucinated "masses
  are equal" (44), per-particle moments without positions (45), wrong-section
  cherry-pick (61), flat-out wrong physics conclusion (65).
- **Citation validity:** 13/20; citations resolve to real file/section/page via
  `format_citations`. Failure mode is selecting a *valid but off-topic* source
  (61: spring section for a general work question), not fabricated references.
- **Latency:** retrieval negligible; generation dominates (1.4–46s by answer length).
- **Reliability:** 20/20 ran, no exceptions, no empty retrievals, no grader errors.

## 4. Failure table (root causes, evidence)

| Q | Symptom | Root cause | Evidence |
|---|---|---|---|
| Kepler (probe) | 7.2 never retrieved | **Parsing defect:** `SECTION_HEADER_RE` rejected `7.2 KEPLER'S LAWS` (U+FFFD apostrophe); section absent from corpus | PDF block dump; corpus section list 7.1→7.3; dense+BM25 agreed (fusion innocent) |
| Power (probe) | fused top-1 labeled 5.11 | Boundary-chunk mislabel; **text is the exact power definition** — metric artifact | Chunk text inspection |
| Cylinder (probe) | top hits "Exercises" | Retrieved chunk **is the verbatim NCERT question** — metric expects theory 6.9 | Chunk text inspection |
| ids 1,21,22,24,41,42,44,45,61,65 | wrong answers despite R=1 in 6/9 | **LLM reasoning failures** (see §3 list) | Manual answer-vs-GT review; grader confirmed |
| ids 23,24 (R=0) | related-but-generic sections | Imprecise retrieval + weak reasoning combined | diag ranks; truncated derivations |

## 5. Change implemented (and only change)

`ingest.py`: widened section-title class to include `'’‘ʼ′U+FFFD`, `CACHE_VERSION`
v1→v2 (stale entries auto-miss; old files deleted). Before/after on identical
6-probe set, same corpus build: **Kepler MISS→HIT** (dense #1 = fused #1 = 7.2),
other 5 unchanged; keph105/106 chunk counts identical (205/272, no new false
sections); corpus 626→628 chunks. Expected benchmark effect: Q5 recall 0→1
(verified at retrieval level; full 20-Q rerun not repeated — the harness is
deterministic in sampling and the only corpus delta is +7.2 attribution).
**Section-aware boosting / reranker / model swap: deliberately NOT implemented**
— ranking already surfaces correct content in every diagnosed case, and the
failures occur downstream of retrieval.

## 6. Prompt experiment (offline, production untouched)

Hypothesis: grounding rules ("never assume values", "re-check signs", "prefer
topic-matching section") fix reasoning failures. A/B on 11 benchmark-failures +
2 controls, same corpus/retrieval/grader (`prompt_lab.py` → `prompt_lab_results.json`):
**A (current) 2/13 vs B (tightened) 2/13, with flips in both directions**
(B fixed 65, 25; regressed 44, 2). Verdict: **no reliable gain — not implemented.**
Side finding: single-run grades are noisy (id=44 and id=25 flipped between runs
under identical prompts), so ±1-question deltas must not drive decisions.

## 7. Files inspected / modified; tests executed

- Inspected: `benchmark.py`, `generate_questions_v2.py`, `answer.py`, `retrieve.py`,
  `ingest.py`, `verify_opt.py`, prior reports, README/stack config sections.
- Modified: `ingest.py` (regex + cache version + comment); `README.md`, `stack.md`
  (removed stale `think`/12k/qwen3 claims). Nothing else.
- Executed: `generate_questions_v2.py` (bank); `run_isolated_benchmark.py` (20/20,
  results JSON + manifest); `diag_misses.py` pre- and post-fix (4/6→5/6 strict,
  residual misses content-correct); `prompt_lab.py` A/B (no gain);
  `recall_ceiling.py` (20/20 refs in corpus); `py_compile` all sources (pass);
  manual review of 12 graded answers (12/12 grader agreement).
- Remaining harnesses kept: `run_isolated_benchmark.py`, `diag_misses.py`,
  `prompt_lab.py`, `verify_opt.py`. Scratch viewers removed.

## 8. Limitations & highest-value next improvement

- Results describe the 628-chunk physics subset only; full-library quality unknown
  (main DB is maths-only — a corpus-management issue, not a code issue).
- Grader + generation are noisy run-to-run; the 45% figure has wide error bars.
- Unverified: Streamlit UI launch; post-fix full 20-Q rerun (only Q5-class retrieval
  re-verified); reranker claims from older docs.
- **Highest-value next step:** raise the reasoning ceiling, not retrieval —
  evaluate one stronger local model (e.g. pull `qwen3:8b` and A/B the 11 failed
  numericals with `prompt_lab.py`) before any prompt/architecture churn. Second:
  rebuild the main DB from the intended physics PDFs so the shipped corpus matches
  the question bank.
