# MODEL_AB_EVALUATION — llama3.1:8b vs qwen3:8b for Predator RAG

Date: Oct 2026. Question: does a stronger local LLM fix the reasoning failures
found in `RETRIEVAL_EVALUATION.md` (wrong formulas, ignored friction, invented
equalities, sign errors — all with correct context retrieved)? Prompt tightening
had already failed (2/13 vs 2/13). No prompt, retrieval, or production changes
were made in this task.

## 1. Models and exact configurations

| | llama3.1:8b (current default) | qwen3:8b (candidate) |
|---|---|---|
| Ollama tag / size | `llama3.1:8b`, 4.9GB | `qwen3:8b` (latest), 5.2GB |
| Params / quant | 8.0B, Q4_K_M | 8.2B, Q4_K_M |
| Native context | 128K | 40K (`ollama show`) |
| Thinking | n/a (no `thinking` field ever returned) | supported; **on by default** even with no `think` param (1.5–7k thinking chars/trial measured) |
| Payload (both arms, byte-identical shape) | `answer.py` templates, `num_ctx=4096`, temp 0.1, caps 512/2048, `keep_alive 5m`, stream off, **no `think` param** (drop-in test) | same |

Download cost: one 5.2GB pull (`ollama pull qwen3:8b`). Nothing else installed.
Sources: https://ollama.com/library/qwen3 (size/ctx/quant),
https://ollama.com/blog/thinking (opt-in `think` API; qwen3 in thinking-models).

## 2. Hardware, corpus, methodology

- Windows, RTX 4070 Laptop 8GB, 16.9GB RAM, Ollama 0.35.1, CUDA embedder resident.
- Isolated keph105/106/107 corpus (628 chunks, embed-cache build), tmp dir deleted
  after each run; main `chroma_db` and PDFs untouched.
- 13 questions: the 11 benchmark failures (ids 1,21,22,23,24,41,42,44,45,61,65)
  + 2 passed controls (2,25). Contexts **frozen once** and reused across models
  and trials (retrieval variance eliminated).
- 2 generation trials × 13 Qs × 2 models = 52 generations + 52 grades
  (`model_lab.py` → `model_lab_results.json`); plus `think_probe.py` follow-up:
  full-text recapture (3 Qs) + `think:false` arm (8 Qs) → `think_probe_results.json`.
- Grader: same `llama3.1:8b` grader (temp 0) for both arms — biased *against* the
  challenger if at all. Every disagreement class below was manually verified
  against full answer texts; grader was right in 11/12 prior checks but showed
  1 false negative (qwen id21 with g=10 — GT itself allows 875J) and 1 false
  positive (llama id44 assuming equal masses) here.

## 3. Per-question comparison (grader → manual-adjusted)

| id | type | llama 2 trials | qwen default 2 trials | qwen nothink | Verdict |
|---|---|---|---|---|---|
| 1 Work-energy thm | theory | ✗✗ (garbled eq) | ✓✓ (`Kf−Ki=∫Fdx`, verified) | ✓ | qwen fixes |
| 21 friction work | num | ✗✗ (ignores μ) | 1/2 + recapture correct w/ g=10 | ✓ (exact 882J) | qwen fixes |
| 22 pump power | num | ✗✗ | ✗✗ (10× arithmetic slip) | ✗ (same slip) | both fail |
| 23 vertical circle | num | ✗✗ | ✓✓ (√5gL + derivation, verified) | ✓ | qwen fixes |
| 24 central-force E | num | ✗✗ (neg. KE) | ✓✓ (E=−k/2r derived, verified) | ✗ (neg. KE again) | qwen fixes **via thinking** |
| 41 incline friction | num | ✗✗ | ✗✗ | ✗ | both fail |
| 42 const-power s | num | ✗✗ | ✓✓ (verified s-formula) but 1 empty recapture at cap | ✗ (13.5m) | qwen fixes **via thinking**; reliability flag |
| 44 reduced mass | num | ✗✗ manual (grader said 1/2 — false +) | ✓✓ (μ formula, verified) | — | qwen fixes |
| 45 COM shift | num | ✓✓ | ✓✓ | — | tie |
| 61 work-zero cond | theory | ✗✗ | ✗✗ | — | tie (both fail) |
| 65 circular L | theory | ✗✗ (wrong conclusion) | ✓✓ (verified) | ✓ | qwen fixes |
| 2 conservative | control | ✓✓ | ✓✓ | — | tie |
| 25 spheres COM | control | 1/2 (noise) | ✓✓ | — | qwen more stable |

## 4. Aggregates

| Metric | llama3.1:8b | qwen3:8b default | qwen3:8b think:false |
|---|---|---|---|
| Accuracy (grader) | 6/26 (23%) | 19/26 (73%) | 4/8 (50%) |
| Accuracy (manual-adjusted) | **5/26 (19%)** | **20/26 (77%)** | 4/8 (50%) |
| Wall median (min–max) | 8.4s (1–47) | 51s (33–76) | 34s (27–38) |
| Decode speed median | 46 tok/s | 42 tok/s (≈identical; gap is thinking + prefill, not decode) | 42 tok/s |
| VRAM resident | 5784MB | 6076MB (+292MB, fits 8GB) | same binary |
| Cold warm-up | 4.8s | 25.3s (one-time; background-able) | — |
| Citation validity | retrieval-determined (`format_citations`), identical for both by construction; no fabricated references observed in either arm | | |

## 5. Manual review, disagreements, grader uncertainty

- Verified-correct qwen wins (full text): id1 integral form, id24 E=−k/2r with
  U-integration, id21-nothink exact 882J chain, id23 √5gL quoted from Example 5.7,
  id44 reduced mass, id65 torque reasoning. Verified-genuine qwen failures: id22
  arithmetic (4388 vs 43556W), id41 W=K conceptual error, id61 off-topic section.
- Run-to-run variance is large under thinking nondeterminism (qwen id21/42 flipped
  between runs; llama controls flipped in prior work) — only the aggregate gap
  (19% vs 77%) is decision-grade, never single questions.
- Reliability flag: one empty qwen response at the 2048 cap (thinking starved the
  answer budget; id21t0 also truncated mid-equation). Mitigation proposed in §7.

## 6. Limitations / unverified

- Grader is one of the contestants (bias direction favors llama; qwen won anyway).
- 2 trials/question is thin for variance quantification; aggregates only.
- Citation metric is model-independent here — citation *selection* (61-type
  cherry-pick) still fails on both models and is unaddressed.
- Theory-cap 512 held for qwen (4/4 correct) but with thinking excerpts separate
  from `eval_count`; id22/41-type long numericals need the cap fix below.
- Production default NOT switched; UI streaming behavior with 35–75s generations
  not re-tested; full 20-Q rerun under qwen not done.

## 7. Recommendation: ADOPT qwen3:8b as the default generation model

The accuracy gap (19% → 77% manual-adjusted, wins-or-ties every question over
three runs) is large, repeatable, and directly addresses the diagnosed failure
class; cost is +292MB VRAM (fits), ~6× wall latency (masked by existing
streaming UI), and a 25s one-time warm-up (already backgrounded). `think:false`
halves the gain (50%) — thinking is the mechanism, keep it on.
Adoption patch (NOT yet applied, pending review): `answer.OLLAMA_MODEL =
"qwen3:8b"` + numerical `num_predict` 2048→4096 (think-starvation evidence:
truncation/empty at 2048; thinking consumes ~0.5–1.7k tokens before the answer).
Keep theory cap 512, keep llama3.1:8b installed as fallback, keep everything
else identical. Then rerun `run_isolated_benchmark.py` to publish post-switch
numbers. If latency proves unacceptable in UI practice, the scoped follow-up is
per-type routing (llama for theory, qwen for numerical) — not a third model.
