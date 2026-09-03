# Opt-in exact LLM failure traces

- **Date:** 2026-09-02
- **Goal for this session:** Make failed live-model evaluations diagnosable from the exact model-facing call data.
- **User outcome shipped:** The eval runner writes private per-case LLM-call sidecars by default for every non-passing case, including initial and bounded-repair calls.
- **Commands and tests run:** `.venv/bin/python -m pytest -q`; `.venv/bin/ruff check .`;
  targeted `.venv/bin/ruff format --check` for changed files; `.venv/bin/mypy src tests`;
  `git diff --check`.
- **Evaluation result:** 229 offline tests passed; Ruff and mypy passed; diff whitespace check passed.
- **Most instructive failure:** The prior baseline retained structured evaluator failures but intentionally discarded the model-facing request packets and raw responses.
- **Failure classification:** Evaluation observability gap.
- **Trace observation:** Sidecars retain exact instructions, serialized input, structured-output schema, parsed output, SDK response JSON when available, and exceptions. Normal baseline artifacts reference the raw I/O sidecars without embedding their contents; `--no-trace` disables capture.
- **Decision made:** Per the project owner's request, capture failed-call traces by default under `evals/intent/traces/`; support `--trace-dir` overrides and `--trace-all-calls` for passing-case comparisons. Trace directories are treated as private because they may contain travel requests and evidence quotes.
- **What Codex generated:** `LLMCallTraceCollector`, adapter and one-pass capture hooks, eval CLI
  flags, per-case trace sidecar writer, runner links, focused tests, and documentation.
- **What the project owner changed or rejected:** The project owner requested exact failed LLM I/O for triage.
- **Next cut line:** [Project-owner selection pending.]
