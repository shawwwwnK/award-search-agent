# 2026-09-04: Selector-to-workflow integration evaluation

## Objective evidence

- Added a test-only selector-to-workflow integration seam. It accepts a manually constructed
  temporal candidate catalog only for `compiler_select_v1`, verifies that its scan text exactly
  matches the request, and leaves the normal compiler catalog construction, production grammar,
  default `two_pass` strategy, and all normal callers unchanged.
- The dedicated integration evaluator reuses the twelve existing private frozen-v2 ambiguity
  catalogs (six semantic categories with forward/reversed variants). It runs static complete
  non-temporal extraction and static holiday data, while a resolver sentinel fails if Pass 2 is
  called. Private exact oracles check canonical relation kinds, evaluated windows, unresolved
  semantics, conflicts, and clarification; saved artifacts retain only booleans, opaque public
  selector handles, output hashes, usage, latency, and redacted errors.
- An architecture review initially blocked the live run because fixture binding, exact final
  workflow assertions, and temporal clarification coverage were incomplete. The follow-up
  implementation bound the integration corpus to the checked-in frozen-v2 projection and SHA,
  added private workflow-result oracles and complete static non-temporal input, and corrected
  selector-attempt telemetry. The architect then approved the live run.
- Live `gpt-5.6-luna` integration evaluation: 36/36 runs completed, selected the private oracle,
  and satisfied exact workflow-result oracles; all forward/reverse pairs matched. There were zero
  errors and repairs, exactly 36 selector attempts, 26,208 input plus 2,520 output tokens, and
  50.511 seconds total latency (1.403 seconds/request; p50 1.237, p95 2.370, max 2.415 seconds).
- The saved artifact records the frozen fixture path, v2 contract, and SHA-256. Independent audit
  found no request text, resolved dates, reference context, private `manual:`/`slot:` handles, or
  private oracle values; the timestamp is the sole date-like metadata.
- Re-ran the ready-corpus compiler-route rollback isolation after the integration work. With no
  selector configured, its 16 `gpt-4o-mini` non-temporal Pass-1 calls yielded 12 passing, 4 failed,
  and 0 error records. Crucially, stage telemetry recorded zero selector and Pass-2 attempts; the
  changed test-only seam did not activate either boundary. The ordinary output failures are
  non-temporal/evaluation checks and are not selector evidence.

## Files added or changed

- `src/award_agent/intent/workflow.py`
- `src/award_agent/evaluation/selector_workflow_integration.py`
- `src/award_agent/cli/selector_workflow_integration_eval.py`
- `evals/selector/workflow_integration_cases_v1.yaml`
- `tests/unit/test_selector_workflow_integration.py`
- `pyproject.toml`

## Artifacts

- Live test-only integration: `evals/selector/baseline/2026-09-04-gpt-5.6-luna-selector-workflow-integration-3-trials.json`
- Ready-corpus rollback isolation: `evals/intent/baseline/2026-09-04-gpt-4o-mini-compiler-select-ready-post-selector-e2e-1-trial.json`

## Commands and verification

- `.venv/bin/pytest -q tests/unit/test_selector_workflow_integration.py` — 9 passed after the
  architecture-approved corrections.
- `.venv/bin/pytest -q` — 332 passed after implementation corrections.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy src tests` — passed.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.selector_workflow_integration_eval
  --selector-model gpt-5.6-luna --trials 3 --output
  evals/selector/baseline/2026-09-04-gpt-5.6-luna-selector-workflow-integration-3-trials.json`
  — live selector-only integration run.
- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.intent_eval --strategy compiler_select_v1
  --model gpt-4o-mini --trials 1 --no-trace --output
  evals/intent/baseline/2026-09-04-gpt-4o-mini-compiler-select-ready-post-selector-e2e-1-trial.json`
  — live non-temporal ready-corpus rollback isolation.
- `jq` artifact gate checks, artifact privacy scans, and `git diff --check` — passed.

## Evidence boundary

- This validates the exact selector-to-workflow wiring for Luna with the known development stems.
  It does not establish independent semantic generalization, production-grammar ambiguity
  behavior, full live workflow quality, concurrency/tail-latency behavior, or production
  enablement. `two_pass` remains the default rollback strategy and the selector remains disabled.

## Owner interpretation

<!-- Project owner: record whether to begin the independent holdout/adversarial cut. -->
