# RAG Generation Reliability (Oct 2026)

Targeted investigation of the four answer failures in the corrected 60-question
artifact, using frozen questions and contexts. Production was changed **once**,
on measured evidence. Retrieval was left untouched because two independent
candidates were tested and both failed.

---

## 1. The four failures and their root causes

| Q | Stored symptom | Actual stage that failed |
|---|---|---|
| `fr2` | answered "the works of the orientalists" | **retrieval AND generation** |
| `fr3` | "I don't have enough information" | **retrieval only** |
| `fr7` | "I don't have enough information" | **retrieval only** |
| `su1` | empty final answer | **generation budget exhaustion** |

### Document-level retrieval was never the problem

Document recall is perfect: **56/56 answerable questions retrieve every
required source at limit=6** (verified live and against the stored artifact).
All three Frankenstein failures returned six chunks, *all* from
`frankenstein.docx`. The failure is **passage-level** — the right document is
found, the right paragraph inside it is not.

> Audit note: my first control metric printed 0.9333 because I divided by 60
> while only 56 questions contribute. Retrieval is 1.0, not 0.9333.

---

## 2. Evidence: source → chunk → context

Expected answers were verified against `frankenstein.docx` with `python-docx`,
independently of retrieval or model output:

| Q | Paragraph | Verified text | Benchmark expectation |
|---|---|---|---|
| fr2 | #104, Ch.2 | "I chanced to find a volume of the works of **Cornelius Agrippa**" | correct |
| fr3 | #152, Ch.5 | "It was on a dreary night of **November** that I beheld the accomplishment of my toils" | correct |
| fr7 | #14, Letter 1 | "I try in vain to be persuaded that **the pole** is the seat of frost" | correct |

Extraction and chunking are **sound**: the answer sentence survives intact in
exactly one chunk each (Ch.2 #50, Ch.5 #85, Letter 1 #6–8).

**The context is the failure.** Reproduced with the frozen index:

| Q | answer text in the context sent to Qwen? | expected location present? | top-6 sections |
|---|---|---|---|
| fr2 | **True — but the wrong occurrence** (Ch.6 "believed in Cornelius Agrippa as firmly as in the gospel", not Ch.2) | No | Ch6, Ch7, front-matter, Ch6, Ch6, Ch7 |
| fr3 | **False** | No | Ch4, Ch7, Ch7, Ch4, Ch8, Ch4 |
| fr7 | **False** | No | front-matter, Ch7, Ch1, Letter4, Ch1, Ch8 |

### Why the passage misses — dense is right, fusion discards it

| Q | target chunk dense rank (of 2,700) | BM25 rank | fused top-6 |
|---|---|---|---|
| fr2 | **2** | 70 | absent (rank 5 is a *different* Agrippa chunk) |
| fr3 | **3** | 28 | absent |
| fr7 | **13** | 30 | absent |

The embedding model finds the right passage almost immediately. RRF gives a
chunk credit per list it appears in; the targets sit outside the 20-chunk BM25
prefetch, so they collect only the dense contribution, while competitors
usually appear in **both** lists and collect roughly double. The question
vocabulary is the cause: `fr2`'s query ("writings… interested in") shares
almost no content words with the passage ("found a volume of the works of…").

### Generation is not the bottleneck for fr3/fr7

Frozen contexts, 5 trials each, production prompt and budgets:

| Q | as-retrieved (real context) | with the answer passage appended | empty |
|---|---|---|---|
| fr2 | **0/5** | **0/5** | 0 |
| fr3 | **0/5** | **5/5** | 0 |
| fr7 | **0/5** | **5/5** | 0 |

`fr3` and `fr7` flip to perfect as soon as the passage is present — the model is
capable, retrieval is the blocker. **`fr2` fails either way (0/5)**: even with
the Chapter 2 passage in context, Qwen still prefers the Chapter 6 distractor.
`fr2` is therefore a genuine generation weakness *on top of* a retrieval miss.

---

## 3. Candidate retrieval fixes — both rejected on evidence

### 3.1 Prefetch window sweep

| prefetch_limit | fr2 | fr3 | fr7 | 56-q recall@6 | loc (all 60) |
|---|---|---|---|---|---|
| 20 (shipped) | rank 5, wrong chunk | absent | absent | 1.0 | 0.7167 |
| 30 | rank 5, wrong chunk | **rank 5** | rank 12 | 1.0 | 0.7333 |
| 40 | rank 5, wrong chunk | **rank 6** | rank 12 | 1.0 | 0.7500 |
| 50 / 60 / 80 | rank 5, wrong chunk | rank 8 / 8 / 10 | rank 13 / 14 / 15 | 1.0 | 0.7167 |

Never resolves all three; `fr3` is only transiently fixed and then degrades
past 40. **Rejected.**

### 3.2 Per-section diversification (cap chunks per chapter)

| cap | targets in top-6 | 56-q recall@6 | loc (all 60) |
|---|---|---|---|
| 1 (no repeats) | 1/3 (fr3 @4) | 1.0 | **0.7000** ← regression |
| 2 | 0/3 | 1.0 | 0.7333 |
| 3 | 0/3 | 1.0 | 0.7167 |
| ∞ (shipped) | 0/3 | 1.0 | 0.7167 |

At best fixes one of three while regressing location accuracy. **Rejected.**

> Harness correction found while testing: `retrieve()` truncates the fused list
> to `prefetch_limit` regardless of `limit`, so an initial run silently pooled
> only 20 candidates. Re-run with a real 60-deep pool before drawing conclusions.

**Conclusion: production retrieval is unchanged.** No embedding-model, RRF,
BM25, reranker or prefetch change is justified by this evidence.

---

## 4. `su1` empty answers — mechanism and recovery strategies

### Root cause: thinking consumes the entire output ceiling

Every empty response was `done_reason=length` with `output_tokens` exactly equal
to `num_predict`. Successful runs finished at 1,209–1,512 tokens. Qwen's
thinking shares the `num_predict` budget, so on this long narrative context it
can spend the entire allowance before emitting one answer token.

### Recovery strategies compared (8 trials each, frozen context, 2048 budget)

| Strategy | Correct | Empty | Mean | Verdict |
|---|---|---|---|---|
| Baseline `qwen3:8b` | 2/8 | **6/8** | 45.4 s | 75% empty |
| **One bounded Qwen retry** | 2/8 | **6/8** | 47.1 s | **no benefit** |
| **`llama3.1:8b` fallback** | **0/8** | 0/8 | **1.4 s** | **worse than useless** |

The Llama fallback never fails, but it answers all eight trials with a 15-token
canned refusal: *"I don't have enough information in the provided sources to
answer this."* It converts a visible "please retry" state into a confident
wrong answer, and is **not** a valid recovery path for this question.

### Budget is the binding constraint

Same frozen context, same model/prompt/temperature; only the ceiling changes:

| `num_predict` | Correct | Empty | Hit budget | Mean | Worst |
|---|---|---|---|---|---|
| 2048 (shipped) | **1/8** | 7/8 | 7/8 | 48.6 s | 50.4 s |
| 3072 | 4/8 | 4/8 | 4/8 | 56.3 s | 75.4 s |
| **4096** | **5/8** | **2/8** | 2/8 | 55.2 s | 100.0 s |

Monotone, and reproduced twice (2048 gave 1/8 here and 2/8 in the recovery
run — same failure regime).

---

## 5. Implemented fix

**`answer.py`: `NUM_PREDICT_THEORY` 2048 → 4096** (now equal to
`NUM_PREDICT_NUMERICAL`). One constant; the rationale and measurements are in
the code comment.

Why this is safe: `num_predict` is a **ceiling**, so raising it cannot truncate
an answer that would otherwise have completed.

**Control check** — 6 previously-correct questions spanning **six formats**,
3 trials each at 4096 on identical frozen contexts:

| Q | Format | 2048 (stored) | 4096 | Empty | Mean |
|---|---|---|---|---|---|
| wx1 | PDF | correct | 3/3 | 0/3 | 21.2 s |
| eq1 | CSV | correct | 3/3 | 0/3 | 5.1 s |
| wb4 | XLSX | correct | 3/3 | 0/3 | 7.9 s |
| wc1 | HTML | correct | 3/3 | 0/3 | 10.2 s |
| fr1 | DOCX | correct | 3/3 | 0/3 | 5.7 s |
| wh3 | PPTX | correct | 3/3 | 0/3 | 5.3 s |

**No regression, no new empties.** Cost is confined to runs that previously
returned nothing: worst case 50.4 s → 100.0 s, mean 48.6 s → 55.2 s — both well
inside the existing 300 s request timeout, which is locked by a new test.

### Before / after through the real `answer_question()` path (3 trials each)

| Q | before (stored) | after | note |
|---|---|---|---|
| **su1** | **0/3** | **2/3** | fixed; 1/3 still empty |
| fr2 | 0/3 | 0/3 | unchanged (diagnosed, unfixed) |
| fr3 | 0/3 | 0/3 | unchanged (diagnosed, unfixed) |
| fr7 | 0/3 | 0/3 | unchanged (diagnosed, unfixed) |
| wc1 | correct | 3/3 | control |
| eq1 | correct | 3/3 | control |

Citations continued to render (3–6 per answer). Thinking traces remain
inaccessible: all 105 tests pass, including `test_thinking_leak.py`.

### Regression tests

- `test_theory_budget_4096` — locks the shipped ceiling.
- `test_budgets_stay_within_request_timeout` — new; a budget-exhausting run must
  still finish inside the HTTP timeout, or the honest-empty path is unreachable.
- `test_stream_path_same_budgets` — updated to the new value.

### Deliberately not changed

Retry and Llama-fallback policy (measured: retry neutral, fallback harmful for
this case; both are user-facing product decisions needing their own evidence),
plus embedding model, RRF, BM25, reranking, prompts, context size and
retrieval settings.

---

## 6. Commands executed

```
python eval_realworld/diag_frankenstein_source.py          # verify expectations
python eval_realworld/diag_frankenstein_passages.py        # chunks + boundaries
python eval_realworld/diag_frankenstein_context.py         # context contents
python eval_realworld/diag_frankenstein_ranking.py        # dense vs BM25 ranks
python eval_realworld/exp_prefetch.py                      # candidate 1 (rejected)
python eval_realworld/exp_diversify.py                     # candidate 2 (rejected)
python eval_realworld/exp_frankenstein_context_injection.py# frozen-context trials
python eval_realworld/exp_su1_empty.py                     # retry vs fallback
python eval_realworld/exp_su1_budget.py                    # budget sweep
python eval_realworld/exp_budget_controls.py               # no-regression controls
python eval_realworld/verify_budget_change.py              # end-to-end verification
python -m pytest test_general_rag.py test_thinking_leak.py \
    test_answer_config.py test_eval_grader.py -q           # 105 passed
```

Artifacts: `exp_frankenstein_injection.json`, `exp_su1_empty.json`,
`exp_su1_budget.json`, `exp_budget_controls.json`, `exp_prefetch.json`,
`exp_diversify.json`, `verify_budget_change.json`,
`diag_frankenstein_context.json`, `diag_ctx_fr{2,3,7}.txt`.

## 7. Methodological note

An early run recorded five "empty" trials per case. The cause was **not** the
product: Ollama had exited, and `generate_answer` correctly mapped the transport
failure to the honest-empty message in ~2 s — indistinguishable from a real
thinking overrun. Both experiment scripts now abort if the server is
unreachable and raise if a response carries no token counts. Recorded results
here all come from runs with a verified-reachable server.

## 8. Remaining uncertainties and next steps

1. **`fr2` is unfixed and doubly broken.** Even with the correct passage
   injected it scores 0/5 — Qwen prefers the Chapter 6 distractor. A
   prompt-level nudge ("prefer the passage that directly answers the question")
   was **not** tested; it risks degrading the 46 currently-correct questions and
   needs its own controlled experiment.
2. **`fr3`/`fr7` need a retrieval capability that does not yet exist here**
   — finding a specific passage inside a document when the query shares no
   content words with it. Every cheap candidate tested failed. The honest next
   step is a deliberate, separately-evaluated design (e.g. hierarchical
   retrieval: select the chapter, then the passage), not another parameter
   sweep.
3. **`su1` is improved, not solved**: 2/3, with a residual 1/3 empty rate. Its
   worst case is now ~100 s, which is a real UX cost.
4. **Sample sizes are small** (8 trials/arm). The budget effect is monotone and
   reproduced across two independent runs, but the 1/8 vs 5/8 contrast should
   be confirmed on a larger sample before treating 4096 as final.
5. **One question cannot justify a global constant.** The change is justified
   because a ceiling is monotone and controls did not regress — but the
   empty-response rate across the *whole* 60-question set at 4096 was not
   re-measured, and should be before release.
6. **Latency was measured with an idle GPU.** Concurrent CUDA models slow
   decode ~10x; run latency benchmarks on an otherwise idle machine.

## 9. Production integrity

| File | Changed this task? |
|---|---|
| `answer.py` | **Yes** — `NUM_PREDICT_THEORY` 2048 → 4096 (one constant) |
| `test_answer_config.py` | **Yes** — budget assertions + new timeout-bound test |
| `retrieve.py`, `ingest.py`, `extractors.py`, `app.py` | **No** |
| `chroma_db/chroma.sqlite3` | **No** — never opened |

All evaluation work stayed in `eval_realworld/` against the isolated
`tmp_postfix` workspace. Previous reports and completed benchmark artifacts are
preserved; no stored result file was overwritten.
