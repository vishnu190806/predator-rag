# RAG Evaluation Metrics Audit (Oct 2026)

Evaluation-only corrections to the real-world benchmark. **No production file
was modified.** `answer.py`, `retrieve.py`, `ingest.py`, `extractors.py`,
`app.py`, model configuration, prompts, chunking and retrieval settings are all
byte-identical to their state at the start of this work, and `./chroma_db` was
never opened.

---

## 1. Original scoring defects and metric ambiguity

### 1.1 Numeric grading used raw substring matching

`eval_realworld.check_answer` matched every expected keyword with
`keyword.lower() in answer.lower()`. That produced errors in **both**
directions:

**False negatives** — correct answers marked wrong (the three reported):

| Q | expected | model wrote | value |
|---|---|---|---|
| wb1 | `125124989` | `125,124,989` | identical |
| wb2 | `66628000` | `66,628,000` | identical |
| wb3 | `83160871` | `83,160,871` | identical |

**False positives** — wrong answers marked right. Latent in *every* score ever
reported, always in the optimistic direction:

| expected | answer | legacy verdict | truth |
|---|---|---|---|
| `13` | "…was 130 km" | pass | wrong |
| `500` | "…is 1,500 dollars" | pass | wrong |
| `10` | "…within 100 days" | pass | wrong |

These never occurred in the two stored artifacts (verified: the corrected
grader **loses zero** answers on both), but the weakness was real and is now
closed and regression-tested.

### 1.2 Cross-document recall could not express "all sources"

`postfix_runner.score()` computed, for a question declaring `files_all`:

```python
r3 = 1.0 if (item.get("files_all") and all(f in files6 for f in need)) ...
```

`recall3` for a cross-document question was silently evaluated against the
**depth-6** list. A question needing two documents with only one retrieved
would have been recorded as `recall3 = 1.0`. There was also no way to express
"at least one required source" separately from "every required source".

### 1.3 Absent-answer questions received unearned retrieval credit

Questions with `abstain: True` have no correct source by construction, yet the
harness set `recall3 = recall6 = loc = 1.0` for them, so 4 of 60 questions
inflated the retrieval and location denominators.

### 1.4 The location denominator was never stated

`loc` defaulted to `1.0` for the 14 questions that declare no expected
location, so `loc` was reported over 60 when only 46 questions are actually
checkable.

---

## 2. Corrected definitions

### 2.1 Numeric normalization — the complete permitted rule set

Implemented in `eval_realworld/grader.py`. Standard library only (`re`,
`decimal`); no new dependencies.

A keyword is treated as a **numeric literal** only if it is
`[+-]? ( 1234 | 1,234 | 1,234,567 ) ( . digits )?`. This deliberately
**excludes** ratios (`4.5:1`), versions (`0.7.1`), currency symbols
(`$500`), ranges (`72-135`), units (`17 km`) and identifiers (`us6000m0xl`).

1. **Value matching, not substring.** A numeric expectation matches only if a
   complete number token in the answer carries the same value.
2. **Thousands separators are stripped, nothing else.** No percent↔fraction
   rescaling, no unit conversion, no rounding of the answer.
3. **Agreement is evaluated at the precision the expectation declares.**
4. **Sign is significant.** `-500` never satisfies `500`.
5. **Precision differences are rejected** at the declared precision:
   `73.0` ≠ `73.038`.
6. **Non-numeric keywords keep exact case-insensitive substring** semantics.
7. **Abstain / absent handling is byte-for-byte unchanged.**
8. **No question id, filename or corpus value is special-cased** — enforced by
   an AST test that inspects executable string literals only.

**Why rule 3 rather than exact equality.** `verify_expected_values.py`
independently re-derives every numeric token from the raw source files
(bypassing retrieval entirely). 30 of 36 expectations appear **verbatim** in
the corpus; **6 do not**, because they are author-rounded copies of longer
source values:

| Q | expected | actual source value |
|---|---|---|
| wb5 | `76.98` / `76.980` | 76.98 (stored as text) |
| wb6 | `6.067`, `6.06` | 6.06704239487995 |
| sm3 | `2.339` | 2.3390000000000004 |
| eq3 | `607` | 607.0 |
| wb5 | `76.98` | — |

Exact equality would therefore have manufactured *new* false negatives for those
six. Quantizing both sides to the expectation's declared precision keeps
`6.07 ≡ 6.06704239487995` while still rejecting `125,124,980` for `125124989`,
`130` for `13`, and `73.0` for `73.038`.

### 2.2 Retrieval / source coverage

`source_coverage(item, files3, files6)` returns, per question:

| Field | Meaning |
|---|---|
| `has_expected_source` | False for abstain questions (no correct source exists) |
| `n_required` | length of `files_all`, else 1 if `file`, else 0 |
| `covered_at3` / `covered_at6` | how many required sources were retrieved |
| `any_required_at3/6` | ≥1 required source retrieved |
| `all_required_at3/6` | **every** required source retrieved at that depth |
| `missing_at3` / `missing_at6` | which sources are absent |

A cross-document question is **fully retrieved only when `all_required_*` is
true**. `all_required_at3` and `all_required_at6` are reported separately, so
depth sensitivity is visible rather than hidden.

**Scoring denominators:** retrieval is computed over the **56 answerable
questions that declare ≥1 expected source**. The 4 abstain questions are
excluded from retrieval scoring and reported separately. Location is reported
both over all 60 (legacy convention) and over the **46** questions that declare
an expected location.

---

## 3. Before-and-after scores (existing artifacts, no new generations)

Two stored artifacts were re-scored offline. No Ollama calls were made to
produce these numbers.

### 3.1 Post-fix artifact — `eval_realworld/postfix_results.json` (60/60, `ext-v4`)

| Metric | Legacy | Corrected | Δ |
|---|---|---|---|
| **Answer accuracy** | **51/60 = 0.8500** | **56/60 = 0.9333** | **+0.0833** (+5) |
| Answer, sheetrow (n=12) | 0.6667 | **1.0000** | +0.3333 |
| Answer, conflict (n=1) | 0.0000 | **1.0000** | +1.0000 |
| Answer, exact (n=24) | 0.8750 | 0.8750 | 0 |
| Citation validity | 1.0000 | 1.0000 | 0 |
| Source-location (46 questions declaring a location) | — | **42/46 = 0.9130** | — |
| Source-location (legacy all-60 convention) | 0.9333 | 0.9333 | 0 |

Completeness: **60 recorded, 0 missing, 59 `ok` + 1 `empty`, 0 timeouts,
0 transport errors.** Empty responses stay in the denominator and count as
incorrect.

Corrected retrieval, over the 56 answerable questions:

| Metric | @3 | @6 |
|---|---|---|
| `all_required` (every required source retrieved) | **1.0000** | **1.0000** |
| `any_required` (≥1 required source) | 1.0000 | 1.0000 |
| source-level coverage | 1.0000 (56/56) | 1.0000 (56/56) |

### 3.2 Pre-fix artifact — `eval_realworld/results.json` (60/60, `ext-v2`)

| Metric | Legacy | Corrected | Δ |
|---|---|---|---|
| Answer accuracy | 39/60 = 0.6500 | 39/60 = 0.6500 | **0** |

Gained: none. Lost: none. This isolates the grader's effect cleanly: on the
older run the model wrote numbers without separators, so no false negative
existed to fix. **The grader correction is worth exactly +5 questions and
costs 0 on both artifacts.**

### 3.3 Cross-document source coverage at each depth

| Q | Required sources | @3 | @6 | Missing @3 | Missing @6 |
|---|---|---|---|---|---|
| cd1 | `faa_weather.pdf` + `faa_drones.pdf` | both | both | — | — |
| cd2 | `whale_slides.pptx` + `bluewhale_export.xml` | both | both | — | — |
| ab1–ab4 | none (unsupported) | n/a | n/a | n/a | n/a |

Both cross-document questions genuinely retrieve **every** required source at
depth 3, so the corrected metrics agree with the legacy values on this run —
the legacy `files6`-based bug changed nothing here. The corrected metric is
nonetheless required for correctness, and `test_eval_grader.py` proves it
distinguishes all four required cases (all sources retrieved; 1-of-3
retrieved; all at @6 but not @3; unsupported question).

---

## 4. Every answer whose classification changed

Five changes, all **incorrect → correct**. Each was manually inspected and
checked against the source workbook, not merely re-graded.

| Q | expected | stored answer | verdict |
|---|---|---|---|
| wb1 | `125124989` | "Japan's population in 2022 was **125,124,989**." | value identical → correct |
| wb2 | `66628000` | "The United Kingdom's population in 2019 was **66,628,000**." | value identical → correct |
| wb3 | `83160871` | "Germany's population in 2020 was **83,160,871**." | value identical → correct |
| wb7 | `126633000` + `124516650` | "decreased from **126,633,000** in 2019 to **124,516,650** in 2023, with annual declines…" | both values present → correct |
| wb8 | `126633000` + `124516650` | "2019 … **126,633,000**; 2023 … **124,516,650**. Change = **-2,116,350**" | correct values **and** arithmetic |

**Independent ground-truth check** (read straight from `worldbank.xlsx` with
`openpyxl`, no retrieval stack):

```
Japan: 2019=126633000  2020=126261000  2021=125681593  2022=125124989  2023=124516650
124,516,650 - 126,633,000 = -2,116,350   -> model's figure correct
```

**No answer was accepted merely because normalization loosened matching.**
The corrected grader is *stricter* than legacy on substring cases; it lost 0
answers on both artifacts. Tests additionally pin the rejection side:
`125,124,980`, `12512499`, `1,251,249,890`, `66,628,001`, `83,160,872`, `130`
for `13`, `1,500` for `500`, `35` for `3`, `-500` for `500`, `73.0` for `73.038`.

### Remaining incorrect after correction (4 of 60)

| Q | status | assessment |
|---|---|---|
| fr2 | ok | "the works of the orientalists" — retrieval fine, wrong passage summarized |
| fr3 | ok | declined; expected `November` |
| fr7 | ok | declined; expected `pole` / `New World` |
| su1 | **empty** | thinking consumed the budget; counted incorrect, kept in denominator |

No LLM judge was used anywhere; every verdict above is deterministic or manual.

---

## 5. A correction to the previous report's framing

`RAG_POSTFIX_VALIDATION.md` reported 47/60 = 0.7833 from an `ext-v3` run, and
described `wb7`/`wb8` as "genuine LLM reasoning failures". Re-scoring the
recovered `ext-v4` artifact shows this needs qualifying:

| Q | ext-v3 run | ext-v4 run | cause |
|---|---|---|---|
| js1 | fail | pass | **deterministic** — the JSON record-block fix |
| dr5 | fail (empty) | pass | sampling variance |
| wc2 | fail | pass | sampling variance |
| wx1 | fail (empty) | pass | sampling variance |
| wb7 | fail | pass | **sampling variance**, not a reasoning failure |
| wb8 | fail | pass | **sampling variance**, not a reasoning failure |
| — | — | no newly failing questions | — |

So `wb7`/`wb8` are **flaky**, not reliably failing: identical code path and
identical retrieved context, different sampled completion. Only `js1` is a
genuine deterministic improvement. The corrected 0.9333 must therefore not be
read as "+0.083 from the grader and +0.083 from the fixes" — most of the gap
between 0.7833 and 0.8500 legacy is run-to-run variance, and the grader's own
contribution is exactly the +5 listed in §4.

---

## 6. Tests performed and outcomes

| Command | Outcome |
|---|---|
| `python -m pytest test_eval_grader.py -q` | **69 passed** |
| — original 3 false negatives (`125124989`/`66628000`/`83160871`) | reproduced as failing, now pass |
| — nearby wrong values (10 cases) | all still fail |
| — legacy substring false positives (4 cases) | legacy passes, corrected rejects |
| — precision / sign / zero / units / percent | pass |
| — non-numeric keywords (10 cases: ratios, versions, ids, names) | unchanged semantics |
| — abstain, absent-violation, multi n-of | unchanged semantics |
| — cross-document coverage (4 required scenarios) | pass |
| — no hardcoded question ids (AST check on executable literals) | pass |
| `python -m pytest test_general_rag.py test_thinking_leak.py test_answer_config.py test_eval_grader.py -q` | **104 passed** |
| `python eval_realworld/verify_expected_values.py` | 30 verbatim, 6 author-rounded (documented in §2.1) |
| `python eval_realworld/rescore.py` | `rescore_corrected.json` |
| `python eval_realworld/rescore_compare.py` | `rescore_compare.json` (both artifacts) |

TDD sequence honoured: `test_eval_grader.py` failed with
`ModuleNotFoundError: eval_realworld.grader` before implementation, and three
test-side errors were caught and corrected rather than papered over.

## 7. Remaining scoring limitations

1. **Precision-aware matching has a residual false-positive window.** An
   expectation declaring 2 decimals (`6.07`) will accept `6.074`, because the
   expectation itself is rounded. Exact equality would avoid this but creates
   false negatives on the six author-rounded values in §2.1. The trade-off is
   deliberate and documented.
2. **Precision-aware matching is permissive beyond the declared precision.**
   Same window as (1).
3. **Semantic equivalence is still out of scope.** "18 years or newer" vs `18`
   matches by luck of surface form; a paraphrased unit or scale (e.g. km vs
   miles) will not. No unit conversion is performed, by design.
4. **Keyword-presence scoring remains weak** for synthesis questions; `su1` is
   graded purely on keyword presence.
5. **Single-run point estimates carry sampling variance** (temperature 0.1).
   §5 shows four questions flipping between runs. Differences under ~5 points
   should not be treated as signal without repeated runs.
6. **`cd1` remains scored only at top-3** although it needs two documents;
   both happen to appear, but a genuinely hard cross-doc question would need
   `@6` reported alongside.
7. **Manual judgment** was used only to confirm the five §4 changes against
   the workbook; all other scoring is deterministic. No LLM-as-judge anywhere.

## 8. Production integrity confirmation

| File | LastWriteTime | Modified this task? |
|---|---|---|
| `answer.py` | 17-10 12:08 | **No** |
| `retrieve.py` | 17-10 13:07 | **No** |
| `ingest.py` | 17-10 15:44 | **No** (previous task's JSON fix) |
| `extractors.py` | 17-10 15:44 | **No** (previous task's JSON fix) |
| `app.py` | 14-10 22:09 | **No** |
| `chroma_db/chroma.sqlite3` | 14-10 23:02 | **No** — never opened |

Files created/changed, all under `eval_realworld/` plus one root test:

- `eval_realworld/grader.py` *(new)* — corrected scorer + coverage metrics
- `eval_realworld/rescore.py` *(new)* — offline re-scoring of stored results
- `eval_realworld/rescore_compare.py` *(new)* — legacy vs corrected, both artifacts
- `eval_realworld/verify_expected_values.py` *(new)* — independent ground truth
- `eval_realworld/postfix_runner.py` — now records **both** graders and full
  coverage per question, and uses depth-correct cross-document recall
- `test_eval_grader.py` *(new, root)* — 69 tests

Preserved untouched: `results.json`, `RAG_REALWORLD_EVALUATION.md`,
`RAG_POSTFIX_VALIDATION.md`, `RAG_PRODUCTION_READINESS.md`, and the earlier run
artifacts (backed up as `postfix_report.60run.json`,
`postfix_results.extv4_58.json`, `results_stream.extv4_58.jsonl`).

### One disclosure

The completed 60-question result set from the `ext-v3` run was **overwritten**
by a later `--rebuild` invocation before this audit began; only its summary
survives (`postfix_report.60run.json`). The audit therefore re-scores the
`ext-v4` artifact, which is the **more** appropriate target since it reflects
final production code. The two lost questions (`fr1`, `fr2`) were recovered
with a 2-question `postfix_runner.py --resume` (no benchmark re-run), yielding
a complete 60/60 artifact whose stored answers are used above.
