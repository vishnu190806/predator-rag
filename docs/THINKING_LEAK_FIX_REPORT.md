# THINKING_LEAK_FIX_REPORT — Qwen reasoning traces no longer reach users

Date: Oct 2026. Prior state: `QWEN_ADOPTION_REPORT.md` §5 — 6/20 benchmark
answers exposed raw thinking (12–16k chars) via the empty-response fallback.
Thinking stays enabled throughout (accuracy mechanism: 50%→77% in the A/B).

## 1. Root cause

`answer.generate_answer` contained:
```python
if not raw_response and thinking_text:
    raw_response = f"Worked Solution:\n{thinking_text}"
```
When qwen3's thinking consumed the `num_predict` budget, `response` came back
empty and the *private reasoning trace* was substituted verbatim as the answer
and rendered, cited, and persisted like a real result. The stream path never had
this bug (it only yields `response` tokens) but the UI had no empty-output
handling at all.

## 2. Files changed

- **`answer.py`**:
  - Removed the thinking substitution; only the `response` field may become the
    answer (`thinking` is never appended, yielded, or substituted).
  - New `EMPTY_ANSWER_MESSAGE` + `is_empty_answer()`: empty finals return an
    honest message directing users to retry or the llama fallback.
  - Stream docstring now pins the contract (response-only, in-order, malformed
    lines skipped, empty stream = caller shows empty-state).
  - Unchanged: default `qwen3:8b`, fallback/grader `llama3.1:8b`, ctx 4096,
    budgets 512/4096, prompts, retrieval, citations. No `think` param anywhere.
- **`app.py`**: empty stream → warning + "Retry query" / "Retry with
  llama3.1:8b fallback" buttons (fallback was already imported); citations,
  metrics, and diagnostics render only for real answers; diagnostics comment
  records that reasoning traces are never logged or displayed.
- **`test_thinking_leak.py`** (new, 9 tests, mocked Ollama, no LLM needed).

## 3. Regression tests and results

`test_thinking_leak.py` **9/9 pass** (written first: 3 failed on the old code,
proving they capture the leak — thinking-only substitution, empty-everything,
missing-fields). Coverage: thinking-only Fluids (1,4), think+response
separation (2), stream order/exclusion (3), thinking-only stream (4), malformed
lines (7), transport errors (6), derivation/citation passthrough incl. LaTeX and
`[Section 5.6]` (9). A distinctive `THINKMARKER-7Q2X` appears only in mock
`thinking` fields and in zero outputs. Existing `test_answer_config.py` **7/7
still pass** (budgets, model pinning, no-think-override, grader pin).

## 4. Live verification (`verify_think_live.py` → `verify_think_live.json`)

Against real Ollama/qwen3:8b: raw `/api/generate` returns separate `thinking`
(present, 43 chars on a trivial prompt) and `response` fields — format as
assumed. Both our paths returned the identical 112-char grounded answer
(`P = W/t`, watt, `[Section 5.10]`), no thinking content, not the empty message.
Stream/non-stream parity confirmed live.

## 5. Can thinking still reach users?

No, through any code path: non-stream ignores the field; stream never yields it;
empty results produce the honest message (plain) or warning + retry/fallback
(UI); errors propagate without content (nothing was read into them); diagnostics
show only retrieved textbook chunks. `clean_think_tags` remains as a belt-and-
braces pass for inline tags.

## 6. Limitations / unverified

- Streamlit was not launched (main DB holds 7,868 chunks; startup wipes it) —
  the new warning/buttons/fallback branch is compile- plus code-verified only.
- The 4096-cap looping case (id43) still exhausts its budget; it now fails
  honestly instead of leaking trace, but remains unsolved (see adoption report).
- `py_compile` clean on `answer.py`/`app.py`; main DB verified intact; no tmp
  corpora created by this task (live test used a fixed context string).
