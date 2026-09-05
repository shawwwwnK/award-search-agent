# Compiler selector evaluation-runner wiring

## Objective evidence

- Extended `award_agent.cli.intent_eval` with the opt-in `compiler_select_v1` strategy and an
  independently configured optional `--selector-model`.
- The compiler arm constructs the non-temporal Pass 1 adapter and optional selector only; it
  invokes `understand_request` with no Pass 2 resolver. Incompatible per-stage flags now fail
  before a run starts.
- Bumped baseline artifacts to schema version 5. Each result and the aggregate artifact carry
  payload-free telemetry for `pass_one`, `selector`, `pass_two`, and `one_pass`: enabled,
  configured, model, attempts, latency, and usage. Telemetry remains present with `--no-trace`;
  sidecar suppression does not suppress metrics.
- Selector model/validation failures now use stable `temporal_candidate_selector` failure fields,
  redact exception text, and count independently from legacy Pass-2 wire failures.
- Added runner tests for argument validation, auto-only compiler runs, an injected ambiguity with a
  distinct selector model, redaction/failure classification, no-trace telemetry, and the retained
  two-pass totals.

## Commands run

- `.venv/bin/pytest -q tests/unit/test_intent_eval_runner.py tests/unit/test_workflow.py`
- `.venv/bin/ruff check src/award_agent/cli/intent_eval.py src/award_agent/intent/workflow.py src/award_agent/experiments/one_pass_intent.py tests/unit/test_intent_eval_runner.py`
- `.venv/bin/mypy src/award_agent/cli/intent_eval.py src/award_agent/intent/workflow.py src/award_agent/experiments/one_pass_intent.py`
- `git diff --check`

No live model or provider call was run. No Cut 5 work was attempted.
