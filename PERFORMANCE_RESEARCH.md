# PERFORMANCE_RESEARCH — Predator RAG optimization basis

Hardware: Windows, RTX 4070 Laptop 8GB VRAM (8188 MiB), 16.9GB RAM, CUDA available.
Software: Ollama 0.35.1 (local), llama3.1:8b Q4_K_M (4.9GB) + nomic-embed-text installed,
Python 3.12, sentence-transformers 5.3.0, ChromaDB 1.4.1, Streamlit 1.55.0.
Corpus at audit time: 7868 chunks — entirely `Mathematics-Class-12-Part-2.pdf`
(physics PDFs had been wiped by an earlier clean-start launch).

## 1. Measured bottlenecks (this machine, Oct 2026)

Pre-optimization probe (`perf_probe.py` → `perf_probe_results.json`, plus
`baseline_e2e.py` → `baseline_e2e.json`):

| Stage | Measurement | Verdict |
|---|---|---|
| PDF parse | 0.18s per ~2MB chapter (keph105 → 236 chunks) | Negligible |
| Chunking | ~0.00s | Negligible |
| Embedder load (bge-base) | 7.9s cold, per fresh process | Bottleneck #2 (cold start; paid N× by per-file reloads in UI) |
| Corpus embed rate | 13.2 ms/chunk (64-batch) → ~104s full 7868, ~9s per 700-chunk physics subset | Bottleneck #3 on clean-start ingest |
| Query encode | 8–12ms GPU / 25ms CPU | Negligible |
| Dense (Chroma, 7868) | 2–37ms | Negligible |
| BM25 build (7868 docs) | 0.66s once per process | Minor, one-time |
| BM25 query + RRF | 8–29ms + ~10ms | Negligible |
| Full retrieval | 50–90ms/query | NOT a bottleneck — no index changes justified |
| LLM model load | ~6s first request | Bottleneck #2 (cold start; UI blocked on it) |
| LLM decode | 46–48 tok/s steady (llama3.1:8b, 100% GPU) | Healthy — no model swap justified |
| Short-answer wall time | ~7s for 40 tokens (6s prefill+load, 0.8s decode) | Dominated by one-time load, then prefill |
| ctx 12k vs 4k | Identical decode (~47 tok/s); switching ctx per request forces ~6–8s KV realloc | Keep ONE ctx everywhere |
| VRAM worst case | 7938/8188MB (embedder on CUDA + LLM + 12k KV) | Context cut to 4k: 5798MB with both resident; near-spill risk removed |

Pipeline total (warm): theory ~4–8s, numerical (≤2048 tok) ~6–7s. UI felt slower
because warmup blocked the sidebar (up to 180s spinner) and answers rendered only
after full generation.

## 2. Local inference: keep Ollama + llama3.1:8b

- **Runtime:** Ollama (llama.cpp backend) retained. llama.cpp-direct or alternative
  servers offer no measured advantage here — decode is already 47 tok/s at 100% GPU
  offload (`ollama ps` confirms 100% GPU). No migration.
  Source: `ollama ps` on this machine; backend documented at
  https://github.com/ollama/ollama (README: "Supported backends: llama.cpp").
- **Model:** llama3.1:8b Q4_K_M retained. It was already installed; the configured
  `qwen3:8b-q4_K_M` was never pulled. Downloading more 5–8GB models for a bake-off
  was rejected: no evidence of a generation-speed problem (47 tok/s is at the top
  of what an 8B Q4 does on a 4070 laptop), and swapping risks physics-answer
  regression. Smaller models (1–3B) would decode faster but measurably weaken
  multi-step physics reasoning — rejected without a quality crisis to solve.
- **num_ctx 12000 → 4096:** Ollama's documented default is 2048
  (https://docs.ollama.com/modelfile, `num_ctx` parameter); llama3.1 natively
  supports 128k (`ollama show llama3.1:8b`). Our prompts are ~600–1200 tokens
  (6 chunks × ~1600 chars + formulas). 4096 gives 3–6× headroom while shrinking
  the KV allocation; the old 12k value bought nothing and, combined with a CUDA
  embedder, pushed VRAM to 7938MB. Single value enforced in warmup, generation,
  and grading (`answer.NUM_CTX`) because any per-request change triggers reload.
- **Streaming (`stream: true`, newline-delimited JSON on `/api/generate`):**
  adopted for the UI only. Same tokens, same latency — but first visible token in
  ~1s instead of after the full 4–8s. API shape per https://docs.ollama.com/api.
- **Not adopted:** speculative decoding/draft models, `/api/chat` migration,
  cloud APIs (explicitly out of scope), `nomic-embed-text`-via-Ollama for
  embeddings (would compete with the LLM for the same 8GB VRAM; local BGE on CPU
  is already 12–25ms/query).

## 3. Retrieval/indexing: keep stack, fix data bugs

- **Embeddings stay `BAAI/bge-base-en-v1.5`.** Alternatives considered:
  `bge-small-en-v1.5` (already in HF cache, ~3× faster, 384-d) trades recall for
  speed we do not need (encode is 1–3% of query time). No swap without evidence.
- **Embedder stays on CUDA when available (reverted a CPU pin).** An early
  microbenchmark suggested CPU≈CUDA, but it encoded 64 copies of one short
  string. On real ~1600-char chunks: ~13ms/chunk CUDA vs ~81ms/chunk CPU (~6×).
  CPU pinning would have stretched a 700-chunk physics ingest from ~10s to
  ~50s (measured both). VRAM with embedder resident + LLM at 4k ctx measured
  5798/8188MB — comfortable, since the old 7.9GB worst case came from the
  retired 12k context. Escape hatch documented in `retrieve._get_device`:
  pin to `"cpu"` if VRAM pressure ever returns (queries cost only ~25ms there;
  bulk ingest is covered by the disk cache).
- **ChromaDB + BM25 + RRF retained.** 50–90ms/query at 7868 chunks needs no
  engine change; a server-based vector DB is explicitly out of scope.
- **Reranker stays OFF.** `bge-reranker-base` is cached locally but previously
  measured +1.5s / −10% recall on CPU. Dead `get_reranker` call removed from the
  hot path narrative; UI labels corrected to "RRF-fused".
- **Real retrieval bugs fixed (quality, not speed):**
  (a) formula chunks were stored TWICE (formula + duplicate theory) → 49% of the
  DB was duplicated formulas; now stored once. (b) Question classifier misrouted
  both ways — section numbers ("5.6") + physics words forced theory questions
  onto the 2048-token path, while real numericals ("kinetic energy of rotation",
  digits + units) fell onto the 512-token theory path. Rewritten around
  digit+unit-quantity detection with section-ref stripping (8/8 probe pass).

## 4. Streamlit responsiveness: fix usage, keep Streamlit

Per https://docs.streamlit.io/develop/concepts/architecture/caching, the correct
tools are `st.cache_resource` (models, DB clients) and non-blocking patterns —
not a rewrite. A FastAPI+React migration was evaluated and rejected: it changes
rendering, not the 4–8s LLM pipeline, and adds a second runtime to maintain.
Implemented instead:
- Model warmup moved to a daemon thread; completion detected via the existing
  `/api/ps` poll. Uploads proceed during the ~6s load (previously a blocking
  spinner up to 180s).
- Answers render via `st.write_stream` (first token ~1s).
- Ingest path shares one embedder singleton (previously one ~8s model load per
  uploaded file) and consults a content-hashed embedding cache.

## 5. Startup/ingestion: cache embeddings, not the index

The reset-on-startup lifecycle is intentional, so the index itself is NOT
persisted across launches. The expensive, repeatable work is embedding bytes
that have not changed: `./embed_cache/<sha256(pdf‖model‖chunk-params‖v1)>.json`.
Invalidation is structural — any PDF edit, model swap, chunk-param change, or
`CACHE_VERSION` bump misses automatically. Verified: cache-hit re-embed of
3 physics chapters ≈ 0.01s vs ~10s cold (≈1000×). Stale-index risk: none beyond
a same-byte PDF, which is by definition identical content.

## 6. Published claims vs local measurements

| Claim | Source | Local measurement |
|---|---|---|
| Ollama `num_ctx` default 2048 | https://docs.ollama.com/modelfile | Confirmed via docs; app now uses single 4096 |
| Streamlit reruns whole script; `st.cache_resource` for models | https://docs.streamlit.io/develop/concepts/architecture/caching | Applied (singleton embedder, threaded warmup) |
| llama.cpp backend, 100% GPU offload possible | https://github.com/ollama/ollama, `ollama ps` | 100% GPU, 47 tok/s confirmed |
| "Theory under 5s" (README) | README.md (historical) | Not reproduced: 6.9–8.9s wall for short answers incl. one-time load; steady-state ~1–4s + decode. README updated to measured numbers |
| Reranker "−10% recall, +1.5s" | stack.md (historical) | Not re-measured (would need labeled physics corpus run); reranker stays off, claim kept as historical |
