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

Run the frozen date-free temporal-selector study with explicitly chosen Mini and Luna model IDs,
then make the compiler-route end-to-end runner decision. The deterministic scanner, candidate
compiler, 16-case offline oracle gate, one-call OpenAI selector adapter, strict non-temporal
compiler Pass 1, and offline frozen-evaluation harness are complete; a live selector is not
enabled.

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
- Pass-two catalog entries state the canonical direct relation for explicit anchors and the allowed
  targets and relation kinds for references and evidence. The OpenAI adapter and shared conformance
  layer both enforce those date-free permissions; named whole-month anchors remain canonical
  `month_portion` relations.
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
- Dependency and cycle errors identify the consuming constraint collection/index, selected relation
  kind, evidence ID, and exact reference edge so bounded repair can address the local invalid use.
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
- The evaluation runner writes private LLM-call sidecars for non-passing cases by default under
  `evals/intent/traces/`. Each sidecar retains the exact model instructions, serialized input,
  output schema, parsed output, SDK response JSON when available, and exception details for every
  initial or repair call; `--no-trace` disables sidecars and the normal baseline artifact stores
  only a reference to them when enabled.
- An opt-in `compiler_select_v1` migration path scans `RawRequest.text` for temporal facts,
  produces local scoped candidates, and directly compiles the existing canonical relation graph.
  It bypasses the model-authored Pass 2 wire for fully auto-compilable requests; `two_pass`
  remains the default rollback strategy. The scanner does not consume Pass-1 temporal anchors or
  phrases, and the compiler path makes no temporal resolver call when all groups auto-compile.
- `compiler_select_v1` now invokes only `extract_non_temporal()` for its model Pass 1. Its strict
  input/output models have no temporal fields, the call has no repair path, and the workflow
  explicitly merges that result with scanner-derived `date_anchors` and `temporal_phrases` after
  compilation. The legacy `extract()`/`repair_extract()` path remains exclusive to `two_pass`.
- The deterministic compiler covers all sixteen ready corpus cases in a table-driven offline
  oracle gate using their exact raw requests and contexts, fake holiday data, static non-temporal
  extraction, and a temporal resolver that fails if called. The gate asserts selected local IDs,
  canonical graph kinds, computed windows, and clarification-relevant output. It preserves
  first-week month wording and seasons as unresolved, keeps day/week duration known when the
  departure is unbounded, and detects a strict `back before` return boundary without fabricating
  a finite return window.
- A local, date-free selector projection/restoration contract now exists with opaque candidate,
  group, evidence, anchor, and production-slot handles. `OpenAIIntentExtractor` implements it as
  a dedicated, one-call, no-repair boundary with `TemporalSelectorOutput` as the only structured
  output and response storage disabled. A separately configured extractor keeps selector model,
  trace, usage, and latency capture independent from Pass 1. Current production grammar has no
  genuinely ambiguous groups, so fully auto-compiled requests make zero selector calls;
  frozen/manual ambiguity fixtures are required to qualify a selector. Explicit production slots
  and composition operands prevent a dependent relation from binding to an arbitrary same-target
  producer.
- A standalone frozen selector evaluator reconstructs private manual catalogs and asserts their
  projections match twelve checked-in public, date-free YAML inputs before every run. It includes
  paired candidate-order variants across target, reference, composition, scope, dependency-closure,
  and unsupported-to-unresolved ambiguities; it uses static holiday dates and never calls Pass 1,
  Pass 2, the workflow, or a live holiday provider. The `none`, `mini`, and `luna` arms report
  parse, restoration, compiler completion, semantic and per-class accuracy, unsupported accuracy,
  zero repairs, latency, and usage. A one-trial `gpt-4o-mini` versus `gpt-5.6-luna` study parsed,
  restored, and compiled every model output with zero repairs, but achieved only 6/12 and 8/12
  semantic selections respectively. A subsequent selector-contract v2 study with the same private
  scenarios and a public self-sufficient projection confirmed `gpt-5.6-luna` at 36/36 semantic
  selections over three trials, with every parse, membership, compiler, class, unsupported, and
  zero-repair gate satisfied. `gpt-4o-mini` remained at 16/36 with two dependency compiler errors.
  Luna is qualified only for the next selector-enabled compiler E2E experiment; the selector is
  not yet enabled as a default and Mini remains disqualified. A matched three-trial comparison
  found `gpt-4.1-mini` at 25/36 semantic selections (69.4%) and `gpt-4.1` at 29/36 (80.6%), versus
  Luna's 36/36. Both 4.1 models were faster but failed blocking class gates, so neither is
  qualified for selector experiments.
- A matched v2 frozen-selector comparison found `gpt-5.4-mini` at 25/36 semantic selections
  (69.4%) with complete parse/membership/compiler checks and zero repairs, but it failed all
  composition cases, half the scope cases, and two unsupported-to-unresolved cases. It is not
  qualified. `gpt-5.6-terra` achieved 36/36 semantic selections with every parse, membership,
  compiler, class, unsupported, and zero-repair gate satisfied. Terra averaged 1.663 seconds and
  761.8 tokens per request, compared with Luna's previous 1.781 seconds and 804.5 tokens per
  request on the same v2 fixture. The project owner selected `gpt-5.6-luna` as the selector model
  for future selector-enabled experiments because it passed the gate at materially lower published
  token prices than Terra. Terra remains comparison evidence, not the chosen selector model. The
  selector remains disabled by default; this is not a production-default decision. The deferred
  decision protocol is recorded at `docs/experiments/selector-model-choice-protocol.md`.
- A test-only, manually catalog-injected selector-to-workflow integration corpus reuses the twelve
  frozen-v2 ambiguity cases while executing the real `projection -> selector -> restoration ->
  compiler -> workflow` chain. The injection is accepted only for `compiler_select_v1` with an
  exact request-text match; production grammar and normal construction are unchanged. A three-trial
  live `gpt-5.6-luna` run completed all 36 cases with selector and exact workflow oracles matched,
  zero errors/repairs, 36 selector attempts, 1.403 seconds mean latency, and 798 tokens/request.
  Artifacts bind to the frozen-v2 path/SHA/contract and retain only redacted public data. A
  post-change live ready-corpus rollback check made 16 non-temporal Pass-1 calls with zero selector
  and Pass-2 calls. This proves test-only E2E wiring and route isolation, not independent semantic
  generalization, genuine production-grammar ambiguity behavior, full live workflow quality, or
  production enablement; `two_pass` remains default and the selector disabled.
- The ready-corpus intent evaluator now has an opt-in `compiler_select_v1` arm with a separate
  optional `--selector-model`. It constructs only the non-temporal Pass 1 boundary and an
  explicitly configured selector; no live Pass 2 resolver is constructed. Schema-v5 artifacts
  retain existing totals and add payload-free stage telemetry (configuration, model, attempts,
  latency, and usage) even with `--no-trace`. Selector failures are redacted and classified
  separately from legacy Pass-2 wire failures. A one-trial `gpt-4o-mini` compiler smoke across
  the sixteen ready cases completed with 10 passing, 6 failed checks, and 0 errors; it made 16
  non-temporal Pass-1 calls, 0 selector calls, and 0 Pass-2 calls. This is route evidence only,
  not a selector result or a decision-grade accuracy estimate.
- Clarification no longer asks for `return_or_duration` when a literal duration is known but an
  unbounded departure prevents deriving a return. A definite `return_before_departure` conflict
  suppresses its derivative duration-mismatch conflict. First-person discourse such as “help me
  find” does not imply one traveler; an explicit first-person travel subject does.
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
- The post-optimization Pass 2 full evaluation completed 34/48 runs and passed all blocking checks
  in 15/48, compared with 30/48 and 11/48 in the immediate pre-Pass 2 artifact. Dependency terminal
  errors fell 10 to 0, while explicit wire failures rose 1 to 7 because invented catalog IDs and an
  incompatible evidence relation remained invalid after bounded repair. The evaluator contract,
  corpus, model, deterministic calendar policy, and validation strength were unchanged.
- An evaluation-only split-model experiment kept Pass 1 on `gpt-4o-mini` and used `gpt-4o` for Pass 2.
  It passed 23/48 versus 15/48 and completed 40/48 versus 34/48, reducing wire and deterministic
  failures but increasing total latency 285.463s to 451.516s and clarification failures 4 to 8.
  This is evidence for an owner cost/quality decision, not a production model selection.

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
