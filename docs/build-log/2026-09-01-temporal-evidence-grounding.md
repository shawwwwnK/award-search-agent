# Claim-linked temporal evidence grounding and evaluation

- **Date:** 2026-09-01
- **Goal for this session:** Replace exact preferred-phrase scoring with strict source grounding and
  deterministic claim-level evidence sufficiency, while preserving date and clarification behavior.
- **User outcome shipped:** Model-facing temporal quotes are linked to typed claims and grounded to
  canonical request offsets. Executable eval fixtures use allowed envelopes and required fragments;
  preferred boundaries are non-blocking diagnostics. The three recorded Labor Day outputs are
  covered by offline regressions: the two synthetic splice outputs fail grounding, and the grounded
  alternative-boundary output passes the full case.
- **Commands and tests run:**
  - `.venv/bin/python -m pytest -q tests/unit/test_temporal_evidence.py tests/integration/test_labor_day_evidence_regression.py tests/unit/test_eval_cases.py tests/unit/test_intent_eval_runner.py` — 48 passed.
  - `.venv/bin/python -m pytest -q` — 111 passed.
  - `.venv/bin/ruff check src tests` — passed.
  - `.venv/bin/ruff format --check src tests` — 37 files already formatted.
  - `.venv/bin/mypy src tests` — passed with no issues in 37 source files.
  - `git diff --check` — passed.
- **Evaluation result:** Offline Trial 1 and Trial 3 fixtures reject
  `leaving on the Thursday as well` as `ungrounded_quote`. Offline Trial 2 passes grounding,
  semantic fields, claim/evidence sufficiency, deterministic date outputs, and clarification; its
  preferred-boundary diagnostic is false and non-blocking. No live model evaluation was run.
- **Most instructive failure:** An initial fixture compilation attempt found that `weekend` occurs
  twice in the return-weekend request. The fixture now specifies zero-based occurrences instead of
  allowing the compiler to choose silently.
- **Failure classification:** The two recorded splice outputs are grounding failures. The recorded
  grounded output's former exact-set failure was an evaluation-contract mismatch.
- **Trace observation:** Canonical evidence uses Python start-inclusive/end-exclusive offsets, and
  its displayed text is derived from `original_request[start:end]`. Second-pass supporting quotes
  not already represented by first-pass spans are canonicalized through the same resolver.
- **Decision made:** Per the project owner's explicit decision, strict exact grounding remains a
  hard gate; claim-level sufficiency replaces exact preferred-boundary equality as a hard eval.
- **What Codex generated:** Domain contracts, strict resolver and structured errors, claim-level
  fixture compiler and scorer, evaluator diagnostics, prompt changes, offline regression tests,
  ADR 0005, architecture/eval documentation, and this build log.
- **What the project owner changed or rejected:** _Owner entry pending._
- **Next cut line:** _Owner decision pending._ A narrowly scoped possible follow-up is a bounded
  retry using structured grounding errors; no retry subsystem was added in this session.

## Focused live rerun

- **Command:** `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --cases /private/tmp/labor-day-evidence-eval.yaml --trials 3 --output evals/intent/baseline/2026-09-01-gpt-4o-mini-labor-day-evidence-3-trials.json`
- **Observed result:** 3 runs, 0 passed, 3 completed with failed checks, and 0 errors. Total measured
  latency was 35.908 seconds. Usage and cost were unavailable from the adapter.
- **Grounding observation:** All three runs were schema-valid and passed strict exact grounding.
  None reproduced the earlier synthetic quote `leaving on the Thursday as well`.
- **Evidence-support observation:** All three failed claim-level evidence support. Trials 1 and 2
  linked duration evidence to `duration` rather than `approximate_duration` and linked
  `leaving on Labor Day weekend` only to `departure_anchor`, leaving `departure_period` missing.
  Trials 1 and 3 also extracted `about 10 days` as a September month anchor. Trial 3 omitted the
  first-pass alternate-departure claim.
- **Deterministic-output observation:** Trials 1 and 2 retained the expected September 3-7
  departure and September 12-18 return windows with no clarification. Trial 3 produced September
  4-7 and September 13-18 because first-pass evidence did not preserve the Thursday alternative.
- **Interpretation:** _Owner entry pending._ This focused three-run sample is not an aggregate model
  reliability measurement.
