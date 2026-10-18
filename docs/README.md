# Predator RAG — Historical Documentation Archive

These reports are **point-in-time records** of the research, audits, benchmarks, and release
decisions that shaped Predator RAG. They are preserved as-is: commands, file paths, and
configuration values inside them reflect the repository state at their date of authorship and
may not match the current one (model configs, predictive budgets, and script locations have
evolved; the one-off scripts they reference now live in `tools/`). See the top-level README for
current architecture and configuration.

## Release record (newest → oldest)

* `FINAL_SIGNOFF.md` — final release-candidate handoff; live real-UI verification evidence (18 Oct 2026).
* `RELEASE_CANDIDATE_REPORT.md` — release-candidate evidence and the 60-question generation-budget decision (`num_predict` = 4096).
* `RAG_GENERATION_RELIABILITY.md` — why thinking-mode response budgets had to be raised (empty-answer failure mode).
* `RAG_POSTFIX_VALIDATION.md` — validation of the postfix budget modifications.
* `RAG_EVALUATION.md` — the mixed-format general-purpose benchmark (12 questions, source of the README's table).
* `RAG_REALWORLD_EVALUATION.md` — real-world corpus evaluation campaign.
* `RAG_EVALUATION_METRICS_AUDIT.md` — grader semantics and metric audit.
* `RAG_PRODUCTION_READINESS.md` — readiness checklist incl. prompt-injection coverage.
* `THINKING_LEAK_FIX_REPORT.md` — thinking-trace leak fix and verification.

## Research & development history

* `RETRIEVAL_EVALUATION.md`, `RETRIEVAL_CONFIDENCE_REPORT.md` — retrieval-side tuning evidence.
* `PERFORMANCE_BENCHMARK.md`, `PERFORMANCE_RESEARCH.md` — historical (legacy, physics-era) performance work.
* `MODEL_AB_EVALUATION.md`, `QWEN_ADOPTION_REPORT.md` — model selection record.
* `PROJECT_HANDOFF.md` — the earliest third-party-style audit of the original physics prototype (pre-dates tests, git, and the general-purpose pivot).
* `MIGRATION_AUDIT.md` — WSL2 → Windows-native migration log.
* `RAG_RESEARCH.md` — extraction-library research notes referenced by `extractors.py`.
* `stack.md` — an early stack snapshot (contains outdated generation budgets; superseded by the README).
