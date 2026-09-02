# Project State

## Phase

Request-understanding implementation and initial evaluation.

## Long-term thesis

An award-travel decision assistant that converts vague requests into grounded, traceable flight-search recommendations.

## Selected first workflow

Award-search agent.

## Current slice

Request understanding and clarification.

## Representative request

"My boyfriend and I want to go to Thailand from SF leaving on the weekend of Labor Day weekend and be back after about 10 days. Find award and cash flight options."

## Intended current output

A typed parsed request, explicit unknowns/conflicts, and at most one focused clarification question.

## Current technical assumptions

- Python with a `src/` layout.
- Pydantic domain models.
- pytest.
- Model interaction behind an interface.
- No agent framework selected.

## Largest project-level risk

Feasible access to useful award-inventory data.

## Immediate next milestone

Run and analyze the full ready-scenario live evaluation for the redesigned two-pass workflow after
the offline gates pass. Compare it only with the retained historical artifacts under their original
contracts, and report first-attempt, repair, failure-stage, latency, and usage metrics separately.

## Current implementation status

- Typed request, extraction, parsed-request, unknown, conflict, and clarification contracts exist.
- Point-balance and spending-budget constraints are intentionally excluded from the MVP request
  contracts; award-versus-cash search intent remains in scope.
- Temporal understanding uses two model passes separated by a deterministic catalog checkpoint.
  Pass one receives request text only. Pass two receives a bounded temporal transcript plus
  date-free evidence, explicit-anchor, and allowed-reference catalogs; concrete request context and
  privately resolved anchors remain deterministic state.
- First-pass temporal quotes are linked to typed claims and grounded without normalization to
  canonical original-request offsets. Repeated quotes require an explicit zero-based occurrence;
  invalid, ambiguous, or out-of-range evidence fails with a structured validation error.
- Deterministic checkpoint construction assigns canonical evidence IDs and exact offsets, stable
  anchor IDs, source order, and the symbolic `context:request_date` reference. Pass two
  selects catalog IDs rather than repeating quotes or receiving resolved calendar values.
- Executable eval fixtures score claim-level evidence sufficiency inside allowed source envelopes.
  Preferred human span boundaries are retained as non-blocking diagnostics rather than exact-set
  correctness requirements.
- Exact-date, month, and holiday anchors use kind-specific Structured Output variants. Unstated model
  years are discarded before deterministic next-occurrence resolution.
- Deterministic code validates relation evidence, anchor and request-field references, dependency
  order, and cycles; evaluates recognized holiday windows, weekends, weekdays, day/week/month
  offsets, month portions, and durations; preserves unbounded constraints; constructs final windows;
  detects conflicts; and applies clarification policy.
- A context-relative calendar-period relation represents `next month` as the next whole month from
  the hidden request-date reference, distinct from a point offset. Unsupported seasons such as
  `next spring` remain unresolved; no deterministic season policy has been introduced.
- Duration relations retain literal stated quantities, unit, and exact/approximate/alternative
  modifier. Deterministic normalization applies day, week, and month arithmetic, including
  cross-month and cross-year behavior; the model does not author normalized day bounds.
- Cross-pass conformance and catalog-membership validation preserve structured stage, error code,
  relation location/kind, missing or contradictory fields, evidence/reference identifiers, and the
  underlying validation cause.
- Each model boundary permits at most one repair using the same narrow original input, rejected
  output, and structured errors. Complete deterministic validation reruns, a second failure remains
  explicit, and repair outcomes are retained in the workflow trace.
- `DateResolutionProposal` is now a deterministic trace/result compatibility shape. Model-proposed
  calendar dates are not accepted as authoritative workflow input.
- The earlier detailed `DateExpression` resolver remains temporarily for isolated legacy tests but
  is no longer used by the production request-understanding workflow.
- U.S. federal-holiday anchor dates come from Nager.Holidays Community API v4 through an injected
  `HolidayDateProvider`; offline tests use fakes.
- Model behavior sits behind `IntentExtractor` and `TemporalResolver`; offline tests use fakes.
- Location `raw_text` is verbatim evidence and the model's normalized `value` is only a resolver
  candidate. Stable location IDs, canonical display names, and city-to-airport expansion remain
  deterministic later-stage work.
- Explicit model-classified airport codes are preserved deterministically as uppercase `value`
  identifiers so the next workflow can consume them directly; this does not infer airports from
  city abbreviations.
- The OpenAI adapter uses Responses API Structured Outputs with response storage disabled. Its
  pass-two wire contract has fixed per-relation collections with required item fields and no
  unsupported `oneOf`; deterministic conversion restores the typed internal
  `TemporalRelationGraph` invariants.
- Offline regression coverage uses fake model passes and holiday providers. It includes payload
  non-leakage and context invariance, catalog membership and claim coverage, whole relative months,
  literal duration normalization, structured error preservation, bounded repair/non-leakage, and
  first-attempt versus repaired evaluator aggregation. No live result for the redesigned workflow
  is recorded here yet.
- Historical pre-redesign evidence: the retained 2026-09-01 post-fix flat-wire live evaluation
  completed 48 runs, with 8 passing all blocking checks, 7 completed with failed checks, and 33
  explicit errors. Nineteen errors occurred while converting schema-valid flat wire outputs into
  typed relation variants, fourteen rejected invalid coarse anchors or cyclic dependencies, and
  three additional completed records failed strict grounding because of invalid evidence
  occurrences. These results motivated the redesign and do not describe the current wire contract.
- The `award-intent` CLI requires explicit model, reference-date, and timezone context.
- Model selection is injected through immutable per-extractor configuration, not environment state,
  so evaluation code can compare model candidates and workflows can choose independently.
- A three-trial `gpt-4o-mini` baseline has been run across the sixteen ready scenarios: 14 of 48
  runs passed all automatic checks, 31 completed with failed checks, and 3 ended in explicit errors.
  Free-text invariants remain unscored and usage/cost is unavailable from the current adapter.
- The same matrix was rerun after the current deterministic holiday and location-candidate policies:
  30 of 48 runs passed, 16 completed with failed checks, and 2 ended in explicit errors. Seven
  previously failing scenarios passed all three current trials; five remain unsolved, and
  `missing_travel_period` now fails the exact `LAX` candidate expectation in all three trials.
- After the project owner selected explicit airport-code preservation, deterministic code retained
  `LAX` as the origin `value`; `missing_travel_period` then passed all three focused live trials.
- A deliberately naive one-pass `gpt-4o-mini` experiment on the same matrix produced 2 passes, 27
  failed outputs, and 19 schema-validation errors. It is isolated under `award_agent.experiments`
  and is not a production workflow option.
- The four requests that motivated the two-pass temporal design all completed in one live
  `gpt-4o-mini` regression run. This small run is not evidence of aggregate accuracy or stability.

## Explicit deferred work

- point-balance constraints;
- spending-budget constraints;
- planning;
- travel providers;
- normalization;
- ranking;
- explanation;
- UI;
- persistence;
- deployment;
- RAG.

## Living workbook

Broader project design context is maintained at:

`/Users/shawnkang/bots/workbook_formatted.md`

The workbook evolves alongside the implementation and should be consulted when broader product or evaluation context is needed.

## Decisions that supersede older project notes

The first workflow has now been selected as the award-search agent.

Older source documents should not be automatically updated as part of this scaffold task.
