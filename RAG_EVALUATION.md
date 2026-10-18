# RAG Evaluation — Mixed-Format Benchmark (Oct 2026)

## Methodology

- Corpus: `eval_general/eval_corpus` (built by `eval_general/make_corpus.py`):
  text PDF (2 pages), DOCX (headings + table-free facts), PPTX (2 slides +
  speaker notes), XLSX (2 sheets), CSV, Markdown, plus a `.exe` for rejection.
- Questions: 12 in `eval_general/eval_general.py` — 10 single-format lookups
  with known file + location, 1 cross-document comparison, 1 unsupported
  (must abstain). Expected answers/keywords are explicit; no LLM grader.
- Runs in a temp workspace (`eval_general/tmp_eval`), never touches
  `./chroma_db`. Deterministic part needs no LLM; `--with-llm` checks answer
  keywords and abstention through Ollama (`qwen3:8b`).
- Command: `python eval_general/eval_general.py [--with-llm]`
  (results → `eval_general/results.json`).
- Regression: `python -m pytest test_general_rag.py test_thinking_leak.py
  test_answer_config.py -q` → **27 passed**.

## Baseline (pre-change, measured)

- Only PDFs ingestible; app uploader accepted `.pdf` only; prompts hardcoded
  to physics/JEE/NEET; citations assumed chapter/section/page.
- `parse_pdf` on generic 2-page PDF: 0.044 s, but theory runs merged across
  pages (wrong page citation) and non-PDF formats had zero support.
- Retrieval on existing 7868-chunk physics DB: ~20–30 ms steady-state
  (first query ~9–10 s incl. embedder load); embedder on CUDA.
- Old physics-only scores are NOT claimed as general-purpose performance.

## Post-change results (this machine, `--with-llm`, 14 Oct 2026)

| Metric | Result |
|---|---|
| Extraction (6 formats) | all ok; slowest xlsx 0.41 s, fastest csv/md ~0.001 s; `.exe` correctly rejected |
| Index build (17 chunks, cold incl. model load) | 0.76 s (cache HIT); true cold with encode 9.5 s |
| Cache-hit re-ingest | 0.08 s (no re-encode) |
| Recall@3 (expected file retrieved) | **12/12 (1.00)** |
| Source-location accuracy | **12/12 (1.00)** |
| Citation validity (no invented pages/slides/rows) | **12/12 (1.00)** |
| Answer keyword hit (incl. cross-doc + abstain) | **12/12 (1.00)** |
| Avg retrieval latency (incl. one model-load outlier) | 0.59 s; steady-state ~0.02–0.03 s |
| Avg LLM generation latency | 5.68 s (range 2.7–12.3 s; table query slowest) |
| Process RAM / VRAM (qwen3:8b resident) | ~1.38 GB / 6100 MB of 8188 MB |

## Limitations (honest)

- n=12 toy corpus; real-world recall on large noisy collections will be lower.
- Keyword-hit grading is weaker than independent grading; scores measure
  grounding plausibility, not proof.
- One query class (identifier-heavy table lookup, `xlsx-2`) needed the theory
  budget raised 512 → 2048 after reproducible empty responses; stochastic
  thinking length means rare empties remain possible (UI offers retry/fallback).
- No scanned-PDF OCR backend installed: scanned pages are reported, not read.
- Physics regression on the old 7868-chunk DB was not re-run (old DB uses a
  retired collection name; clean-start lifecycle rebuilds it).
