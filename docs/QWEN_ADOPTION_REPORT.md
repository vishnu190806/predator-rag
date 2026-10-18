# QWEN_ADOPTION_REPORT — qwen3:8b default + 4096 numerical budget

Date: Oct 2026. Basis: `MODEL_AB_EVALUATION.md` (qwen3:8b 20/26 vs llama3.1:8b
5/26 manual-adjusted). No prompts, embeddings, chunking, BM25, RRF, reranking,
or retrieval ranking were changed in this task.

## 1. Files changed and why

- **`answer.py`** (only production change):
  - `OLLAMA_MODEL = "qwen3:8b"` (was `"llama3.1:8b"`).
  - New `FALLBACK_MODEL = "llama3.1:8b"` (stays installed; UI dropdown fallback).
  - New `GRADER_MODEL = "llama3.1:8b"` (grading stays on the fast, stable scorer).
  - New `NUM_PREDICT_THEORY = 512`, `NUM_PREDICT_NUMERICAL = 4096` (was 512/2048):
    qwen3 thinks by default and thinking shares the `num_predict` budget — at 2048
    we measured one empty response and one mid-equation truncation.
  - No `think` param added: thinking stays on Ollama's verified default (on for
    qwen3 — the accuracy mechanism, 50%→77% in the A/B); no per-model assumption.
  - `NUM_CTX=4096`, templates, streaming, citations untouched.
- **`benchmark.py`**: grader uses `GRADER_MODEL` (decoupled from the switched
  default, so scoring stays comparable); warmup + generation follow `OLLAMA_MODEL`.
- **`app.py`**: offline model list is `[OLLAMA_MODEL, FALLBACK_MODEL]`; QA path
  already generated with and displayed `selected_model` — verified the reported
  model is the generating model (grep + read, `app.py:230,233,352`).
- **`run_isolated_benchmark.py`**: manifest now records generation model, grader,
  ctx, and both budgets instead of a hardcoded model name.
- **`test_answer_config.py`** (new, 7 tests, no LLM needed): default=qwen3,
  fallback retained and distinct, 4096/512 budgets on both plain and stream paths,
  no `think` key sent, grader pinned to llama. **7/7 pass.**
- **`README.md` / `stack.md`**: model + budget + `think`-history lines corrected
  to the actual configuration.

## 2. Configured default and fallback

Default generation: `qwen3:8b` (Q4_K_M, 5.2GB). Fallback: `llama3.1:8b` (installed,
UI-selectable). Grader: `llama3.1:8b`. Budgets: theory 512, numerical 4096,
ctx 4096 everywhere. Thinking: Ollama default (on for qwen3), never overridden.

## 3. Budget-fix verification (`verify_budget.py` → `verify_budget.json`)

Live runs on the post-switch default path, isolated 628-chunk corpus:
- id=21 (was truncated): **exact 882J**, boxed, 807 chars, stream parity ✓.
- id=42 (was empty): **exact 18m**, boxed, 726 chars (stream/plain lengths differ
  across separate generations — nondeterminism, not transport loss; stream path
  itself is byte-exact per unit test).
- id=2 theory (control): correct, 512-budget intact.
- **Zero empty responses** across budget checks and the full benchmark (min answer
  69 chars). Unit tests prove the wire payloads carry 4096/512 + ctx 4096.

## 4. Full post-change benchmark (20 Qs, isolated physics corpus)

`benchmark_isolated_phys628_qwen_results.json` (+ manifest). Same questions,
same grader, same retrieval settings as the llama baseline
(`benchmark_isolated_phys626_results.json`). Corpus delta is only the 7.2-section
fix (626→628 chunks); main DB untouched.

| Metric | Before (llama) | After (qwen3) |
|---|---|---|
| Retrieval recall | 60.0% (12/20) | **65.0%** (13/20; +Kepler fix) |
| Answer correctness (LLM-graded) | 45.0% (9/20) | **95.0%** (19/20) |
| Citation accuracy | 65.0% (13/20) | **75.0%** (15/20) |
| Avg end-to-end latency | 9.1s (gen 8.7s) | **47.0s** (gen 46.5s; thinking cost) |
| Peak VRAM | 5802MB | 6100MB (fits 8GB) |
| Process RAM peak | 1396MB | 1396MB |

Manual verification: id22 (44.44kW ✓), id41 (0.257K present ✓), id5 Kepler (correct,
cites 7.2 ✓). Sole failure id43 (string-slack 40/27·l): thinking loops on geometry
and exhausts even 4096 — the budget fix does not solve unbounded reasoning loops.
Notable: id43 was grader-correct under llama (lucky short answer) — the only
per-question regression, against 10 flips to correct.

## 5. Known issues (honest)

- **6/20 answers expose raw thinking** (`Worked Solution:` prefix from the
  empty-response fallback): grading mostly unaffected (5/6 correct) but users see
  chain-of-thought rambling (12–16k chars on hard numericals). Noisy single-run
  caveat from the A/B still applies to the 95% figure.
- **Latency ~5×** (47s avg; worst 112s). Existing streaming UI masks it partially.
- System-VRAM "targets" in the harness count the whole OS (13.9GB) — misleading;
  process/VRAM figures above are the meaningful ones.
- Results are isolated-corpus only, not full-library performance.

## 6. Checks performed / not performed

Performed: 7/7 config tests; live budget + streaming checks; full 20-Q benchmark;
manual review of failures and key flips; `py_compile` all sources; main-DB
integrity (7868 chunks, untouched); tmp corpora removed.
Not performed: Streamlit UI launch (would clear the main DB); post-switch full
rerun beyond this benchmark; think-budget tuning for looping cases like id43.

## 7. Remaining work (highest value first)

1. Thinking-leak UX: render only the final answer in the UI (keep trace in
   diagnostics) — small, well-evidenced.
2. Unbounded-loop guard for id43-class problems (e.g. stop-sequence / staged
   derivation), only with a dedicated experiment.
3. Rebuild the main DB from physics PDFs so the shipped corpus matches the bank.
