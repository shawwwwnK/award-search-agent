# 2026-09-04: Frozen temporal-selector evaluator

- **Milestone:** frozen selector-only evaluation before enabling a live selector.
- Added a standalone evaluator and CLI for the None/Mini/Luna comparison. The model arms require
  explicit CLI model IDs; the evaluator does not assign model IDs.
- Added a private/manual catalog registry with twelve scenarios: target, reference, composition,
  anchor scope, dependency closure, and unsupported-to-unresolved, each in forward and reversed
  candidate order.
- Checked in date-free public projections at `evals/selector/frozen_cases.yaml`. Preflight rebuilds
  each private catalog and fails when its public projection is not exactly equal to the YAML.
- Preflight also checks that each fixture has multiple valid compiled semantic outcomes and that
  its paired order variant preserves the oracle semantics while moving oracle candidate positions.
- The evaluator restores opaque output, validates selection membership and dependency closure,
  compiles with a fixed local holiday provider, and records parse, membership, compiler completion,
  semantic/per-class accuracy, unsupported accuracy, zero repairs, latency, and usage.
- No live model or holiday-provider call was run during this implementation session.

## Verification

- `.venv/bin/pytest -q tests/unit/test_frozen_selector_eval.py tests/unit/test_temporal_selector.py tests/unit/test_temporal_compiler.py` — 64 passed.
- `.venv/bin/ruff check src/award_agent/evaluation src/award_agent/cli/frozen_selector_eval.py tests/unit/test_frozen_selector_eval.py` — passed.
- `.venv/bin/mypy src/award_agent/evaluation src/award_agent/cli/frozen_selector_eval.py tests/unit/test_frozen_selector_eval.py` — passed.

## Owner decision pending

- Run the frozen study with explicit model IDs and use its pre-agreed quality thresholds before
  enabling a live selector in the compiler route.

## Hardening follow-up

- Public study artifacts now retain only stable failure stage/code classifications; raw exception
  text is excluded because restoration and compiler exceptions may name private candidate or
  production-slot identifiers.
- Model-arm selector call and parsed-schema failures are recorded as failed parses. Selector call
  attempts are counted before the boundary independently of SDK usage capture or missing usage.
- Each artifact evaluates the handoff quality gate per Mini/Luna arm. The `none` control remains
  comparison-only and is explicitly ineligible; the CLI exits nonzero for a failing model-arm
  gate. No live model or holiday-provider call was run for this hardening work.

## Live study result

- Ran one frozen-study trial with `gpt-4o-mini` as Mini and `gpt-5.6-luna` as Luna. The artifact
  is `evals/selector/baseline/2026-09-04-gpt-4o-mini-vs-gpt-5.6-luna-1-trial.json`.
- Both model arms parsed, restored membership, and compiled all 12 scenarios with zero repairs.
  Mini selected 6/12 semantic oracles (50.0%); Luna selected 8/12 (66.7%).
- Mini failed target, reference, composition, and scope thresholds. Luna failed target,
  composition, and unsupported-to-unresolved thresholds. Neither arm met the 95% overall gate;
  the selector remains disabled.
- Mini used 5,904 tokens over 9.969 seconds. Luna used 6,738 tokens over 20.650 seconds.
- The artifact contains public scenario labels, opaque candidate handles, telemetry, and model IDs;
  it contains no raw request text, dates, prompts, private catalog/slot handles, or raw exception
  messages.
