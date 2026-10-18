# RAG Research — General-Purpose Local RAG Decisions (Oct 2026)

Researched via agent-reach (web/Jina backend; Exa channel unavailable) plus
official docs and repos. Only alternatives that could materially improve this
project were evaluated. All choices verified on the target machine
(i9-14900HX, RTX 4070 8 GB, 16 GB RAM, Windows native, Python 3.12).

## 1. Document ingestion

| Option | Formats | Cost on this hardware | Verdict |
|---|---|---|---|
| Lightweight registry (PyMuPDF + python-docx / python-pptx / openpyxl / bs4-lxml / stdlib) | pdf, docx, pptx, xlsx, csv, txt, md, html, json, xml | ms-scale extraction, MBs of deps, Windows wheels | **Adopted** (`extractors.py`) |
| Docling (IBM) | broadest incl. layout/tables/OCR | GBs of models, slow CPU OCR, install friction | Rejected as required dep; overkill for 16 GB laptop |
| MarkItDown (MS) | office/PDF/HTML → Markdown | light, but weak tables/scans, no local OCR by default | Rejected; registry covers the same formats natively |
| unstructured | broad | needs LibreOffice/poppler/tesseract on Windows | Rejected (install complexity) |

Scanned PDFs/images: optional local OCR path only (reported clearly when no
OCR backend is installed; never silently skipped). Supported list is explicit
in `extractors.SUPPORTED_EXTENSIONS`; anything else raises
`UnsupportedFormatError` with the supported list.

## 2. Chunking and metadata

- ~1600 chars / 300 overlap retained (matches existing cache/perf profile).
- Never merge across structural boundaries: PDF page, slide, sheet row-group,
  headed section. Tables/slides/records stay atomic unless oversized.
- Heading breadcrumbs (`H1 > H2`) are stored in metadata AND prefixed to chunk
  text so embeddings see the context.
- Metadata (Chroma-compatible scalar types only): file, doc_id, doc_type,
  chapter, section, heading, page, slide, sheet, row_range, type.
- PDFs keep the legacy structure-aware parser (verified quality on real
  textbooks); generic PDFs additionally benefit from a page-boundary flush fix
  (theory runs no longer merge across pages — found via eval `pdf-2`).

## 3. Retrieval and ranking

- Kept: BGE-base-en-v1.5 dense + BM25 + RRF (k=60), prefetch 20 → 6.
  Measured steady-state ~20–30 ms on a 7868-chunk corpus; retrieval is not the
  bottleneck.
- Rejected: cross-encoder reranker (prior measurement: +1.5 s, −10% recall on
  CPU), multi-query/HyDE (gains need rerank+MMR baselines; unjustified cost
  locally), query rewriting except as future work behind a low-confidence gate.
- Added (cheap, measured-safe): per-file `where` filtering on dense + post
  filter on BM25, near-duplicate suppression by text hash.

## 4. Local inference

- Kept Qwen3:8B default + llama3.1:8b fallback/grader, NUM_CTX=4096,
  temperature 0.1, thinking left on Ollama's default (accuracy gain), with the
  thinking-leak fix intact (only `response` is ever rendered).
- Changed: theory `num_predict` 512 → 2048. Evidence: a table-lookup query
  failed 3/3 at 512 (2027 chars of thinking, zero response tokens) and 1/2 at
  1024; 3/3 pass at 2048. Ceiling only bounds runaways; typical theory answers
  still finish in ~3–6 s.
- Prompts generalized (no subject/domain), wrapped context as
  `<untrusted_context>` with an explicit do-not-follow-instructions rule, and
  require `[Source N]` citations plus an exact abstention sentence when
  evidence is missing.

## 5. UX

Kept Streamlit: the bottlenecks were domain hardcoding and PDF-only upload,
not the framework. Added multi-format upload, per-file removal, progress,
empty-workspace state, and format-aware diagnostics. No migration.
