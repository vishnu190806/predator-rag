# Retrieval Confidence & Gated Rewrite — Experiment Report (Oct 2026)

## 1. Corpus and methodology

- Workspace: 12 files / 58 chunks in `eval_confidence/conf_corpus` — the 10
  stress fixtures plus two adversarial distractors built for this experiment:
  `old_tariff.pdf` (superseded 2023 prices/drafts) and `gate_notice.md`
  (superseded gate hours). All synthetic. Isolated temp workspace; the real
  `./chroma_db` was never written (production code paths untouched).
- **Calibration set (22):** paraphrases ("high-cube container cost this year",
  "Who do I call if everything is on fire"), typos ("Whatz"), terseness
  ("muster code?", "CNT40HC price"), word-form numbers ("berth three"),
  ambiguous ("Crane lift capacity?"), follow-up without referent
  ("and the standard one?"), superseded-targeting ("Old tariff for HC
  containers?"), conflict ("bunkering hours?"), and 2 absent-answer probes.
- **Held-out set (25, disjoint):** same difficulty classes plus transposed
  identifier ("S-1171"), wrong-year trap ("2024 price of high-cube?"),
  role paraphrase ("Who handles inland transport?"), and 1 absent probe.
- Arms (identical docs, settings limit=6/prefetch=20, scoring rules):
  **baseline** = dense + BM25 + RRF as shipped; **candidate** = baseline first,
  at most one local rule-based rewrite only on low confidence, keep rewrite
  hits only if its top-1 dense distance is strictly smaller, else original.
- Metrics: recall@3/@6, trigger/switch rates, per-query latency, regressions.

## 2. Confidence signals vs correctness (calibration)

Baseline recall@3 on the 20 answerable calibration queries: **20/20 — zero
failures**, despite typos/paraphrases/ambiguity. Signals collected per query
(Chroma L2 `vector_distance`, BM25 top-1, RRF top-1/margin, dense–sparse
top-3/top-6 agreement):

| Signal | Correct range (n=20) | Absent queries (n=2) | Separates? |
|---|---|---|---|
| Top-1 dense distance | 0.32 – 0.91 | 0.926, 0.946 | No (c22 correct at 0.91) |
| Dense margin (d2−d1) | 0.0004 – 0.25 | 0.025 – 0.031 | No (c10 correct at 0.0004) |
| BM25 top-1 | 0.0 – 18.9 | 2.9, 5.8 | No (c2 correct at 0.0) |
| Dense–sparse agree@3 | 1 – 3 | 1 – 2 | No (overlap both ends) |
| RRF top-1 / margin | — | — | Same overlap pattern |

With zero failures to separate and every signal overlapping, any threshold
fit here would be noise-fitting. The frozen gate (`d1 > 0.85 AND agree3 ≤ 1`)
is deliberately conservative: on calibration it fires only on c22 (vague but
correctly retrieved) and c20 (absent). RRF scores were used as rank/margin
only — never as correctness probabilities.

## 3. Baseline vs candidate (held-out, n=25)

| Metric | Baseline | Gated rewrite |
|---|---|---|
| Recall@3 (24 answerable) | **1.00** | **1.00** (identical) |
| Recall@6 | **1.00** | **1.00** (identical) |
| Trigger rate | — | 0.04 (1/25: h21, unanswerable) |
| Switch rate | — | 0.04 (same query; no expected file either way) |
| Retrieval median | 0.028 s | 0.06 s (run-to-run noise; gate itself is µs of float compares) |
| Triggered-query extra cost | — | 0.059 s (one extra encode+retrieve, no LLM) |

Per-query results identical on all 24 answerable questions
(`eval_confidence/conf_compare.json`). No regressions, no improvements.

## 4. Quality by query category (held-out baseline)

Paraphrase, typo/identifier-variant, ambiguous-name, superseded-distractor,
section-targeted, cross-doc, and absent classes: 24/24 retrieved at @3.
Notably robust cases: "CNT40HC" (BM25 score 0, dense alone retrieves),
"S-1171" (transposed ID still resolves to sensors.csv), "2024 price"
(no 2024 sheet; rates.xlsx returned), old-tariff/gate-notice targeting
retrieves the superseded doc when asked, current doc otherwise.

## 5. Trigger rate and latency overhead

Gate fires ~4% (only on vague/absent queries in both sets). Cost when fired:
one extra retrieval ≈ 0.06 s; amortized ≈ 2 ms/query. Median diff between arms
is measurement noise, not gate cost. An LLM-based rewrite was never tested:
at ~5–10 s per rewrite it would exceed total retrieval cost by 200× for a
problem this data does not demonstrate.

## 6. Failure diagnoses

- Zero retrieval failures across 44 calibration + held-out answerable queries.
- The single candidate switch (h21, absent) is mechanism-correct behavior with
  no definable improvement — the fallback comparison ran, found a smaller d1,
  and returned equally answer-free hits; the answer path would abstain as before.
- The previously known intermittent x5 generation-empty case is explicitly a
  generation failure (retrieval correct every time), not attributable to
  retrieval and not addressable by rewriting.

## 7. Regression tests

`python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py -q`
→ **30 passed** (fresh run after the experiment; production files unchanged).

## 8. Decision: REJECT (do not implement)

Gated rewriting is rejected for production: baseline holds 100% recall@3/@6 on
47 deliberately hard queries; the candidate produced zero retrieval
improvement; no confidence signal separates success from failure because there
are no failures to separate. Adding the gate would trade real complexity for
no measured benefit. The experiment harness (`eval_confidence/`) is retained
so the question can be re-opened with evidence if real-user queries ever show
retrieval failures. No reranker, fan-out, embedding, runtime, or service
changes were made. Production files changed: **none**.
