# Typed temporal-relation graph

- **Date:** 2026-09-01
- **Goal for this session:** Replace authoritative second-pass calendar ranges with grounded typed
  semantic temporal relations and deterministic graph evaluation.
- **Work attempted:** Added discriminated relation/reference contracts; strict evidence, anchor-kind,
  reference, dependency, and cycle validation; deterministic holiday-window, weekend, weekday,
  offset, month-portion, and duration evaluation; workflow, adapter, conflict, eval-runner, corpus,
  architecture, and ADR migration updates.
- **Files changed:** `src/award_agent/domain/models.py`, domain exports, intent extractor/resolver
  interface and OpenAI adapter, temporal evaluator, evidence grounding, conflicts, workflow, temporal
  and workflow tests, mocked adapter tests, eval runner and corpus, ADRs 0001/0003/0006,
  `docs/architecture.md`, `docs/project-state.md`, `evals/intent/README.md`, and this build log.
  Existing dirty-worktree evidence/location changes were preserved and integrated rather than
  reverted.
- **Commands and tests run:**
  - Pre-change `.venv/bin/python -m pytest -q` — 111 passed.
  - Focused `.venv/bin/python -m pytest -q tests/unit/test_temporal.py
    tests/unit/test_temporal_relations.py tests/unit/test_temporal_evidence.py
    tests/unit/test_workflow.py tests/unit/test_openai_extractor.py
    tests/unit/test_intent_eval_runner.py tests/unit/test_eval_cases.py
    tests/integration/test_labor_day_evidence_regression.py` — 96 passed.
  - Final `.venv/bin/python -m pytest -q` — 130 passed.
  - `.venv/bin/ruff check src tests` — passed.
  - `.venv/bin/ruff format --check src tests` — 38 files already formatted.
  - `.venv/bin/mypy src tests` — passed with no issues in 38 source files.
  - `git diff --check` — passed.
- **Evaluation result:** Offline tests cover first/second relative weekends, holiday- and
  request-field-relative weekdays, before relations, a Saturday departure edge, offsets, missing
  anchors and fields, cycles, ungrounded evidence, unbounded New Year behavior, durations with
  explicit return constraints, date conflicts, fabricated month anchors, and OpenAI strict-schema
  conversion. No live model evaluation was run.
- **Most instructive failure:** The model's three recorded ranges for “the weekend afterwards” were
  grounded but calendrically wrong. Grounding alone could not validate semantic conformance; the
  relation graph preserves the understood reference while deterministic code calculates the first
  strictly following Saturday-Sunday weekend.
- **Failure classification:** Architectural responsibility mismatch between semantic interpretation
  and exact calendar arithmetic.
- **Trace observation:** `ParsedRequest.temporal_relations` retains the model-facing graph.
  `ParsedRequest.date_resolution` is now generated deterministically for trace and historical scorer
  compatibility and is not accepted from the model.
- **Decision made:** The project owner's explicit task direction selected a typed semantic relation
  layer and deterministic calendar evaluation; ADR 0006 records the boundary and partially
  supersedes ADR 0003.
- **What Codex generated:** Contracts, validator/evaluator, adapter and workflow migration, semantic
  eval scoring, offline regressions, ADR 0006, architecture/state/eval documentation, and this log.
- **What the project owner changed or rejected:** The owner rejected phrase-specific regex date
  policies, prompt-only correction, and authoritative model-proposed calendar dates in the task
  instructions.
- **Next cut line:** _Owner decision pending._ A focused live relation-level evaluation could measure
  schema validity and semantic reference accuracy, but no live run is authorized by this session.

## Structured Outputs API compatibility fix

- **Goal:** Remove the blocking HTTP 400 while preserving typed internal temporal references and
  constraint variants.
- **Implementation:** Added an adapter-only flat `TemporalRelationGraphWire` and
  `TemporalReferenceWire`. Every API-visible kind-specific field is present and nullable; the wire
  schema contains no `oneOf`. Deterministic conversion requires the selected kind's fields, enforces
  exclusive anchor/request-field references, and returns the existing internally discriminated
  `TemporalRelationGraph`.
- **Offline verification:** Added wire conversion, mixed-reference rejection, and zero-`oneOf`
  strict-schema tests. Final `.venv/bin/python -m pytest -q` passed 132 tests; Ruff, format check,
  mypy, and `git diff --check` passed.
- **Live verification:** Replayed the `approximate_duration` request with `gpt-4o-mini`. The Responses
  API accepted the schema and the command completed end to end with exit code 0, producing an
  internal month-portion relation plus duration relation and deterministic windows.
- **Observed non-API behavior:** The replay classified `first week of June` as `whole`, yielding the
  full June departure window. This is a separate semantic-quality failure for the next full rerun;
  it does not reproduce the schema error.
- **Files changed:** `src/award_agent/intent/openai_extractor.py`, mocked adapter tests, ADR 0006,
  architecture, project state, and this log.
- **Next cut:** Rerun the same full 48-run live matrix and compare semantic relation accuracy. _Owner
  interpretation pending._

## Post-fix full live evaluation

- **Command:** `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --trials 3
  --output
  evals/intent/baseline/2026-09-01-gpt-4o-mini-temporal-relations-post-fix-3-trials.json`
- **Pre-run verification:** `.venv/bin/python -m pytest -q` — 132 passed.
- **Observed result:** 48 runs, 8 passed all blocking checks, 7 completed with failed checks, and 33
  ended in explicit errors. Total measured latency was 320.547 seconds. Usage and cost remained
  unavailable from the adapter.
- **Summary artifact:**
  `evals/intent/baseline/2026-09-01-gpt-4o-mini-temporal-relations-post-fix-3-trials-summary.md`
  classifies all 40 non-passing runs into mutually exclusive failure types and records per-scenario
  outcomes.
- **Scenario outcomes:** `missing_travel_period` passed 3/3; `multiple_destination_options` passed
  2/3; `missing_origin`, `early_month_with_approximate_duration`, and
  `whole_month_with_exact_duration` each passed 1/3. The other eleven scenarios passed 0/3.
- **Error classification:** 19 `DateResolutionError` records came from deterministic conversion of
  a schema-valid flat wire object into a typed relation. The runner preserves only the generic
  message `OpenAI returned an invalid temporal reference`; a diagnostic replay of
  `approximate_duration` exposed the actual cause `relative_weekday constraint requires direction`,
  showing that this bucket includes missing kind-specific fields and is not limited to bad
  references. Fourteen `TemporalResolutionValidationError` records rejected fabricated anchor
  kinds or cyclic request-field dependencies. Three `TemporalEvidenceValidationError` records
  rejected invalid occurrence indexes.
- **Completed-run diagnostics:** All 15 completed records were schema-valid. Twelve passed strict
  grounding, semantic-field, and evidence-support checks; eight passed deterministic-output checks.
  The seven blocking check failures comprised three grounding failures, three duration-semantic
  failures, two return-window failures, and one departure-window failure, with some runs failing
  more than one check.
- **Semantic observations:** Completed relation graphs demonstrate that deterministic calendar
  evaluation is reachable after the schema fix. Observed failures before calendar arithmetic
  included classifying `early May` as the whole month, treating exact `a week` as approximately
  6–8 days, treating `about a week` as exactly six days, and treating exact `2 weeks` as 13–15
  days. These are relation-level semantic errors; deterministic code evaluated the supplied typed
  quantities and portions rather than inventing replacements.
- **Comparison:** The original full baseline immediately following the August 30 implementation
  recorded 14 passed, 31 failed, and 3 errors (29.2%). The later August 30-era current-workflow
  rerun recorded 30 passed, 16 failed, and 2 errors (62.5%). The post-fix relation run recorded
  8 passed, 7 failed, and 33 errors (16.7%). The old and new rates are not direct accuracy measures:
  today's runner replaced exact phrase checks with claim-level evidence checks, added relation
  invariants, and introduced hard typed conversion and graph validation. The comparison does show
  a current reliability regression at the model-to-wire boundary even though the HTTP 400 schema
  blocker is fixed.
- **Trace observation:** The three-trial smoke success before this matrix did not establish flat-wire
  conversion stability. Nullable kind-specific wire fields satisfy the server schema subset but do
  not reliably cause `gpt-4o-mini` to populate every field required by the selected internal
  relation variant. The wrapper message also hides the actionable conversion cause in eval
  artifacts.
- **Owner interpretation / next cut:** _Owner decision pending._ No runtime correction was made in
  this evaluation follow-up.
