# 2026-09-03: Deterministic temporal compiler and offline oracle gate

## Objective evidence

- Added raw-text temporal lexing, local candidate generation with scoped anchor use, and direct
  compilation to the existing canonical `TemporalRelationGraph`.
- Added `compiler_select_v1` as an opt-in workflow and CLI strategy. It auto-compiles safe groups
  and makes no Pass-2 temporal resolver call; the default remains `two_pass`.
- The six exact ready-case requests compile through existing enrichment/evaluation in focused
  offline tests: `labor_day_thailand`, `labor_day_thursday_flexibility`,
  `return_weekend_after_departure`, `exact_dates_and_cabin`,
  `early_month_with_approximate_duration`, and `unbounded_after_new_year`.
- The compiler tests assert `return_weekend_after_departure` references
  `request_field:departure:end`, not Labor Day; test outcomes alone would not expose that
  distinction.
- Extended the table-driven offline oracle from the six proven cases to every one of the sixteen
  ready corpus cases. The test supplies each exact corpus request and context, checks oracle local
  candidate IDs and canonical graph kinds, compiles/evaluates with a fake holiday provider, and
  verifies windows plus clarification-relevant workflow output while a temporal resolver fake
  fails if invoked.
- Added deterministic coverage for Thanksgiving-relative weekends, Christmas-period wording,
  next month, word/hyphenated durations, and strict `back before` return bounds. The last detects
  chronology conflicts without inventing a finite return date.
- Architecture checkpoint fixes ensure non-contiguous wording remains unresolved, day/week
  duration relaxation cannot mask an unsupported month duration, and repeated holidays bind to
  their own clause. Candidate validation now has explicit cycle and cross-target composition
  rejection coverage.
- Added tests for anchor scope, malformed Pass-1 temporal-output isolation, unsupported
  first-week/season wording, known duration with an unbounded departure, candidate membership /
  coverage checks, and no Pass-2 call for an auto-compiled request.
- Added the Cut 1 OpenAI temporal-candidate selector adapter. It uses a dedicated date-free
  prompt and the single-field `TemporalSelectorOutput` structured-output contract, makes exactly
  one selector call with response storage disabled, and never repairs selector output. Empty
  selector groups return an empty schema-valid selection without a provider call. The adapter is
  a separately configured `OpenAIIntentExtractor`, so its model can be selected independently of
  the Pass-1 extractor without widening shared configuration.
- Added fake-client coverage for selector payload privacy, strict required output schema,
  independent model/stage/trace/usage/latency capture, missing or wrong parsed output, provider
  errors, zero-call empty inputs, and no selector-repair path. LLM traces now retain a per-call
  `latency_seconds` value for separate selector-stage evaluation.
- Added an offline frozen selector-study harness with twelve public date-free projections and
  private manual catalogs. Preflight rebuilds each projection, checks semantic discrimination and
  reversed-order pair balance, then restores, validates, and compiles selections using static
  holiday dates. The standalone CLI exposes explicit Mini and Luna model IDs alongside the None
  control; no live model calls were made in this implementation session.
- Addressed P0 confounders: known duration does not create a redundant return-or-duration unknown;
  return-before-departure suppresses the derivative duration mismatch; first-person traveler
  guidance distinguishes travel subjects from discourse wording; `Portland, Oregon` is an explicit
  evaluation alias for `Portland`; and Contract-v2 repair errors retain local decision context with
  redacted conversion causes.
- User-supplied prior live evidence retained for this design decision: the Mini full matrix passed
  2/48 and completed 5/48; the Luna matrix passed 13/48 and completed 34/48 at 2.9x latency.
  Luna had no Pass-1/grounding failures but retained repeated duration-wire and semantic graph
  errors. The six-case candidate pipeline probe supplied the direct-graph feasibility evidence.

## Commands and results

- `.venv/bin/pytest -q tests/unit/test_temporal_compiler.py` — 14 passed.
- `.venv/bin/pytest -q tests/unit/test_workflow.py tests/unit/test_temporal_compiler.py` — 25
  passed after compiler workflow integration.
- `.venv/bin/pytest -q tests/unit/test_temporal_compiler.py` — 38 passed after the 16-case gate
  and architecture-checkpoint fixes.
- `.venv/bin/pytest -q` — 273 passed after the 16-case gate and checkpoint fixes.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy` — passed for 49 source files.
- `git diff --check` — passed.
- `.venv/bin/pytest -q tests/unit/test_openai_extractor.py tests/unit/test_temporal_selector.py`
  — 58 passed after the selector adapter cut.
- `.venv/bin/ruff check src/award_agent/intent/openai_extractor.py
  src/award_agent/intent/model_views.py tests/unit/test_openai_extractor.py` — passed.
- `.venv/bin/mypy src/award_agent/intent/openai_extractor.py
  src/award_agent/intent/model_views.py tests/unit/test_openai_extractor.py` — passed.
- `.venv/bin/pytest -q` — 300 passed after the selector adapter and documentation checkpoint.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy` — passed for 51 source files.
- `git diff --check` — passed.
- `.venv/bin/pytest -q` — 305 passed after the frozen selector-evaluator cut.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy` — passed for 56 source files.
- `git diff --check` — passed.

## Not yet evidenced

- No live model or provider evaluation was run for `compiler_select_v1`.
- A local selector input/output projection and restoration contract, one-call OpenAI selector
  adapter, and frozen selector-evaluation harness exist. No Mini or Luna study has been run and no
  live-selector decision is recorded; explicit model IDs and the gate results remain required
  before selecting a model.
- The production-slot architecture checkpoint fixed implicit same-target composition binding:
  local slots and explicit operands make the dependency deterministic while exposing only opaque
  `pN` values to a future selector. The latest source verification before this handoff was 294
  passing tests, Ruff clean, mypy clean for 51 source files, and `git diff --check` clean.

## Owner interpretation

<!-- Project owner: record product/architecture conclusion and the next cut line here. -->
