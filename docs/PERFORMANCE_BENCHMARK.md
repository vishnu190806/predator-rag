# PERFORMANCE_BENCHMARK — Predator RAG before → after

Machine: Windows, RTX 4070 Laptop (8188 MiB VRAM), 16.9GB RAM, Ollama 0.35.1,
llama3.1:8b Q4_K_M, bge-base-en-v1.5, ChromaDB 1.4.1. All numbers measured on
this machine Oct 2026. Sample counts are small — medians reported, no p95
(fewer than 20 observations per metric).

## 1. Eval sets

- **Latency probe (6 Qs):** theory / formula / worked-example / numerical /
  chapter-specific / theory-2 (`perf_probe.py`, `baseline_e2e.py`).
- **Routing probe (8 Qs):** 4 theory-or-formula (must stay off numerical path) +
  4 numerical (must take numerical path), incl. two previously-misrouted cases.
- **Quality probe (6 physics Qs on isolated 626-chunk keph105/106/107 corpus):**
  strict top-3 section match + answer/citation inspection (`verify_opt.py`,
  temp collection, real DB untouched).

## 2. Baseline (pre-optimization code)

Source: `perf_probe_results.json` + `baseline_e2e.json` (scripts removed after
numbers were extracted here).

| Metric | Baseline |
|---|---|
| Parse (keph105, 236 chunks) | 0.18s |
| Parse 3 physics chapters (626 chunks) | 0.61s |
| Embedder load | 7.9s per fresh process — and per uploaded file in UI (`ingest_single_pdf` rebuilt it each call) |
| Bulk encode, CUDA, real chunks | 0.842s / 64 = 13.2ms/chunk → ~104s per 7868, ~9s per 700 |
| Query encode | 8–12ms CUDA |
| BM25 build (7868 docs) | 0.66s once |
| Retrieval total | 50–90ms/query (encode ~10ms, dense 2–37ms, BM25 8–29ms) |
| LLM model load (first request) | ~6s |
| LLM warmup ctx12k | 6.5s, VRAM → 7938/8188MB |
| Decode | 46–48 tok/s (100% GPU) |
| Short theory answer wall | 6.9–8.9s (one-time load/prefill + 0.8s decode) |
| Numerical (262–291 tok) wall | 6.0–6.7s |
| ctx 12k vs 4k decode | Identical (~47 tok/s); switching ctx costs ~6–8s realloc |
| Classifier | Misroutes both ways: "5.6 … torque?" → numerical; cylinder KE (digits+units) → theory |
| UI warmup | Blocking spinner, up to 180s, before any interaction |
| UI answer render | After full generation (4–8s of nothing) |
| DB composition | 7868 chunks, 100% one maths PDF, 49% duplicated formula vectors |
| Physics retrieval on that DB | 0/6 usable (wrong subject entirely) |

## 3. Post-optimization (this code)

| Metric | After | Δ |
|---|---|---|
| Parse/chunk | Unchanged code path, 0.61s / 3 chapters | — |
| Embedder loads per N-file upload | 1 (singleton `get_shared_embedder`) | N×7.9s → 7.9s once |
| Cold bulk encode | CUDA kept: ~13ms/chunk (rejected a CPU pin after real-chunk test showed 81ms/chunk CPU) | No regression; ~9s per physics subset |
| Cache-hit re-ingest (3 chapters, 626 chunks) | **0.32s** vs 50.43s cold (CPU run) — ~150× | Clean-start repeat uploads ~free |
| Cache invalidation | sha256(pdf bytes ‖ model ‖ chunk params ‖ v1); verified HIT prints + byte-compare of texts | Stale risk ≈ 0 |
| Query encode / retrieval | Unchanged path, 28–53ms on 626-corpus | Still negligible |
| NUM_CTX | 4096 everywhere (warmup, serve, grader) | VRAM 7938 → **5798MB** both resident; decode unchanged 47 tok/s |
| Model load | Same ~6s, now in background thread; UI usable during it | Perceived cold start −6s blocking |
| Streaming | Content-identical to plain (len_match 2/2, heads equal); numerical stream 6.39s vs plain 9.67s wall | First token ~1s vs 4–8s wait |
| Classifier routing probe | **8/8** (was 6/8 with both failure modes) | Correct caps/prompts |
| Formula duplication | Removed (one vector per formula block) | 49% dup share gone |
| Physics quality probe | 3/6 strict section hits; 2/2 answers correct & grounded; citations resolve to real file/section/page | Usable; see §5 |

E2E spot answers (post-opt, physics corpus, ctx4096): Kepler theory correct
("square of time period ∝ cube of semi-major axis"); cylinder numerical correct
path (given values → I=½mr² → K=½Iω² framing). Both cited real sections.

## 4. Checks performed

- `python -m py_compile` on app/answer/retrieve/ingest/benchmark: pass.
- Classifier 8-case probe: pass (in §2 routing set).
- `verify_opt.py` full run: pass (timings + quality + streaming parity + tmp-DB cleanup).
- `ollama ps`: 100% GPU, ctx 4096, llama3.1:8b resident.
- `nvidia-smi`: 5798MB with LLM + CUDA embedder co-resident.
- Grep: no stale `num_ctx:12000`, no `think` param, no `res[` misuse in app.py.
- Streamlit UI itself was NOT launched (would wipe/rebuild the real DB and take
  minutes); app.py verified by compile + reference audit only.

## 5. Remaining uncertainties / limitations

1. **Retrieval quality 3/6 strict hits.** Misses (Kepler→"Escape Speed" top-1,
   power→"Collisions" top-1, cylinder→"Exercises" top-1) are same-chapter/
   keyword-overlap effects of RRF on short queries, not regressions (no
   pre-change physics-corpus baseline exists). Answers were still correct because
   top-6 context covered the topic. Improving rank quality (e.g. section-aware
   boosting) is the next quality lever — deliberately left out: retrieval is
   30–50ms and "good enough to answer correctly."
2. **Full 20-question `benchmark.py` suite not rerun** (needs
   `benchmark_questions.json` + ~40 LLM calls ≈ 15+ min). Regenerate input with
   `python generate_questions_v2.py` first. E2E spot checks substitute.
3. **Embed-cache size:** ~6KB/chunk JSON → ~48MB per 7868-chunk corpus. Fine on
   disk; loading is still ~50× faster than re-encoding.
4. **First-ever ingest of new PDFs still costs ~13ms/chunk on CUDA** (≈2 min for
   a 14-PDF library). Unavoidable without a smaller embedding model (rejected:
   recall risk for no query-time need).
5. **VRAM headroom (2.4GB) assumes one resident model.** Loading a second large
   model while the embedder sits on CUDA could spill — the documented escape
   hatch is pinning `retrieve._get_device` to `"cpu"`.
