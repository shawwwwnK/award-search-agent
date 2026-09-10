# Project State

## Phase

Iterative clarification continuation — ADR 0014 semantic-boundary redesign in implementation.

## Current conclusion

The project owner concluded the initial request-understanding implementation on 2026-09-06. The
selector-only Luna path is the sole live path: Luna handles non-temporal Pass 1 and opaque
temporal-candidate selection; deterministic code owns temporal scanning, validation, compilation,
calendar evaluation, conflicts, and clarification. Sequential two-pass resolution is retired from
the live code path and configuration. On 2026-09-08, the owner explicitly reopened a narrow
follow-on slice: accept iterative answers to a clarification prompt, produce a conversation-aware
effective request, and recompute all remaining blockers after every response. The project owner
approved the architecture in ADR 0011: one prompt lists all current blocking requirements, a user
may resolve any subset, and the loop reaches `ready` or `stopped`. The additive continuation
boundary is now implemented and qualified offline plus through a three-trial live Luna run. The
existing parser, selector, temporal compiler, clarification policy, and ready corpus remain
frozen.

ADR 0014 supersedes continuation raw-answer grammar/recovery and ADR 0013's one-call prompt
strategy. The clarification receiver is now the only semantic reader of an answer; deterministic
code validates typed output, compiles symbolic temporal semantics, and reduces state. Prompt copy
is post-reduction LLM output, without a deterministic clarification fallback. The new offline
gate is executable typed-conformance evidence; a live receiver or composer-model-selection
qualification has not yet run.

The follow-up relative-time repair is continuation-only: answer messages may use `this weekend`,
`this <weekday>`, or `on <weekday>`, and complete numbered answer lines map positionally to the
ordered typed prompt requirements. The frozen initial parser remains unchanged and still does not
recognize a bare `this weekend` in an initial raw request. If a model returns only a narrow temporal
fact span, deterministic cue validation may inspect only that fact's same-answer physical sentence
or line; alternatives, distant cues, and target mismatches are re-asked. The fresh three-trial
online recovery qualification passed 48/48 terminal outcomes and 60/60 exact blocker/prompt checks
with zero errors or unauthorized mutations; details and private trace metadata are recorded in the
build log below.

The continuation-only relative selector has subsequently been qualified with a global, date-free
affordance catalog selected by the answer model and compiled deterministically. It retains
same-answer-only `following`/`afterwards` dependencies and does not expose calendar state or
template identities to the model. The final redacted three-trial Luna artifact
`evals/clarification/baseline/2026-09-10-gpt-5.6-luna-3-trials-template-v2-final-qualified.json`
records 48/48 terminal-correct sessions, 60/60 exact blocker and prompt checks, zero system
errors, and zero unauthorized mutations. Each protected target passed 3/3; private all-call
traces are retained separately.

The clarification-stage LLM model is `gpt-5.6-luna`. The separate answer-only interpreter uses
Luna behind its narrow contract; deterministic code retains temporal context, grounding,
validation, reduction, and blocker policy. GPT-4o mini remains recorded comparison evidence, not
a fallback or runtime alternative for this stage.

ADR 0013 supersedes ADR 0012's separate prompt-composer runtime call: each processed answer uses
only the answer receiver model call. The receiver may return ordered follow-up items, but the
controller renders them only after exact deterministic agreement with recomputed remaining
blockers; otherwise it uses the issue-specific fallback.

On 2026-09-10, the project owner refined the next clarification cut in ADR 0012. Clarification
must be more accepting than frozen initial intent: it should turn reasonable, grounded fuzzy
answers into one bounded, visible approximation and move forward rather than re-ask solely for
narrow grammar mismatch. True alternatives, conflicts, unresolved endpoint ownership, and
unsupported revisions remain explicit blockers. ADR 0012 originally authorized a separate
post-reduction prompt composer to receive authoritative remaining requirements plus answer-local
issue records. ADR 0013 supersedes that runtime call: the answer receiver returns any proposed
follow-up items in the same response, and deterministic post-reduction validation decides whether
to render them. Qualification retains exact deterministic safety
gates but add a property-based behavioral corpus and human-calibrated metrics for false blocking,
unnecessary clarification, assumption disclosure, and targeted follow-ups. Existing exact v1
corpora remain conformance evidence, not the sole optimization target.

ADR 0012 is now implemented and qualified. The final public three-trial Luna artifact,
`evals/clarification/baseline/2026-09-10-gpt-5.6-luna-behavior-v2-final.json`, passed its exact
safety gate with zero model, system, or evaluator errors and 129/129 private-traced calls
captured. It recorded zero false blocks (0/27), zero incorrect acceptances (0/12), all required
assumption disclosures (24/24), and all valid siblings retained (18/18). Its behavioral metrics
remain diagnostic rather than owner-approved release thresholds: the three conflict trajectories
remained safe but received generic rather than sufficiently issue-specific follow-up wording
(12/15 targeted questions; generic-repeat rate 0.20). The evidence establishes safe accepting
behavior; it also identifies conflict-prompt specificity as the next bounded quality concern.

The qualification record is the traced three-trial run
`evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`:
47/48 passed (97.92%), with zero errors, Pass-1 boundary failures, selector failures, grounding
failures, semantic failures, or deterministic-output failures, and one clarification miss
(`repositioning_allowed` asked for `origin` rather than `departure`). Its 48 all-call traces are
private/local under `evals/intent/traces/` and are not a public artifact.

## Long-term thesis

An award-travel decision assistant that converts vague requests into grounded, traceable flight-search recommendations.

## Selected first workflow

Award-search agent.

## Current slice

Iterative clarification continuation: turn an initial parsed snapshot plus successive user answers
into a traceable `EffectiveRequest` that is `ready` for later planning or explicitly `stopped`.

## Representative request

"My boyfriend and I want to go to Thailand from SF leaving on the weekend of Labor Day weekend and be back after about 10 days. Find award and cash flight options."

## Intended current output

An `EffectiveRequest`, full blocker-set clarification prompt, and traceable session state after
each response, terminating at `ready` or `stopped`.

## Current technical assumptions

- Python with a `src/` layout.
- Pydantic domain models.
- pytest.
- Model interaction behind an interface.
- No agent framework selected.

## Largest project-level risk

Feasible access to useful award-inventory data.

## Immediate milestone

The accepting clarification refinement in ADR 0012 is implemented and qualified without changing
the frozen initial workflow. Every prompt's typed requirements list all current blocking requirements in
deterministic order; under ADR 0013, the answer receiver may return issue-specific follow-up
items in the same call, which are rendered only after deterministic validation and otherwise use
an issue-specific fallback. Each answer may
resolve any subset, including a reasonable, grounded bounded approximation whose assumption is
visible and traceable. Preserve immutable revisions, answer-turn evidence, and atomic
merge semantics. Do not silently mutate a prior `ParsedRequest`, re-run initial parsing, or reopen
unrelated frozen request-understanding behavior. An explicit, grounded correction to a supported
already-resolved field is an approved amendment and must trigger full recomputation. The local
Streamlit harness may exercise only this session boundary and must remain ephemeral and
provider-free.

The implemented sequence, contract invariants, code entry points, and acceptance gates are in
`docs/handoffs/2026-09-08-clarification-continuation-implementation-plan.md`; ADR 0013 is the
newer policy where it differs from ADR 0012's prompt-composer runtime decision.

After this design and its implementation are qualified, the following cut is a fixed-planner,
one-provider vertical slice: `ClarificationSession(ready).effective_request -> fixed SearchPlan ->
provider query -> traced result or explicit error`. The freeze handoff is
`docs/handoffs/2026-09-05-intent-freeze-handoff.md`; ADR 0010 remains the current selector-only
request-understanding decision. Earlier references to `two_pass` are historical evidence only.

## Current implementation status

- Seats.aero passed one narrow cached-search access-and-response-shape spike; no application
  adapter or provider error fixture exists yet. SerpAPI Google Flights remains a later cash-fare
  candidate. See
  `docs/provider-feasibility/2026-09-08-initial-provider-intake.md`.
- The frozen initial workflow stops after `ClarificationDecision`; the additive continuation
  boundary owns subsequent answers, deterministic reduction, a local-only Streamlit harness, and
  separate offline/live corpora under ADR 0011. Every live continuation evaluation writes
  all-call private trace sidecars by default and a redacted public artifact.
- The continuation temporal normalizer accepts `this weekend`, `this <weekday>`, and `on <weekday>`
  using the immutable initial `RequestContext`; complete numbered answer lines map one-based to
  ordered typed blockers. This is an answer-only grammar and does not broaden the frozen initial
  parser, which still leaves a bare `this weekend` unresolved when it appears in the initial raw
  request.
- Narrow temporal fact spans may borrow endpoint cues only from the same answer message and same
  physical sentence or line under the deterministic normalizer. Alternatives/disjunctions, distant
  or cross-line cues, and target mismatches remain explicit ambiguity and trigger a re-ask; accepted
  contributions retain the narrow span as provenance.
- The separate continuation corpus contains 30 scenarios and 43 turns. Its latest offline
  evaluator run passed 43/43 turns with exact blocker/prompt coverage. The fresh online recovery
  qualification also passed 48/48 terminal outcomes and 60/60 exact blocker/prompt checks; see the
  build log for the redacted artifact and private trace directory.
- Selector-only request understanding is the sole live path (ADR 0010). It requires separately
  configured non-temporal Pass 1 and temporal selector adapters before work begins.
- The compiler owns all temporal facts and always uses `supported_or_unresolved`; the selector can
  choose only opaque candidate handles, including explicit unresolved choices. There is no runtime
  strategy switch or fallback.
- The ready evaluator is schema v6 and records only Pass 1 and selector telemetry. Version-5 and
  older artifacts remain historical evidence and are intentionally not rewritten.
- The test-only catalog injection is exact-request matched and exists only in selector workflow
  integration. It is not exposed through application or evaluator configuration.

## Historical implementation and evaluation log (superseded where ADR 0010 conflicts)

Everything in this section is retained historical evidence. Statements about `two_pass`, rollback,
legacy Pass 2, selector enablement, or earlier scores describe prior experiments and must not be
read as current runtime status; the current conclusion is recorded above.

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
- A selector-arm trace review found that the v2 public summary represented every literal duration
  as a default `1-unit` relation ordinal, even when the evidence said (for example) “about 10
  days.” The selector consequently chose explicit unresolved alternatives in the affected runs;
  compiler arithmetic and clarification correctly reflected those selections. The projection now
  emits the scanner-derived duration modifier, quantity range, and unit, and durations publish no
  relation ordinal. Focused offline coverage verifies five literal forms, date/context non-leakage,
  selector restoration, and deterministic compilation; the targeted test set passed 121 tests,
  Ruff, mypy, and `git diff --check`. The repository-local ignored `.env` then supplied the API
  key for live selector evaluation without exposing it: focused three-trial Mini and Luna Pass-1
  selector arms improved from 0/15 to 8/15 and 5/15 respectively, both with zero errors; the full
  Mini-plus-Luna-selector matrix improved from 24/48 to 33/48 with zero errors. Remaining selector
  misses retain unresolved duration choices for Labor-Day-Thursday and approximate-duration wording;
  multiple-destination remains a non-temporal Pass-1 ambiguity. The full Luna-selector matrix was
  not completed because the combined follow-on run was stopped before further `two_pass` spending;
  `two_pass` remains the rollback path. A later parallel Mini-versus-Luna selector comparison held
  Luna on the non-temporal Pass 1 boundary, but both 48-run arms failed before selection with the
  same `missing_or_invalid_model_output` Pass-1 classification. They made zero selector attempts,
  so they are recorded only as upstream-boundary failures, not selector evidence. Sequential
  reruns of the same Mini-versus-Luna selector arms completed without errors: Mini passed 11/48
  (22.9%; 143.08s) and Luna passed 39/48 (81.3%; 194.20s), with 48 Pass-1 attempts and 42 selector
  attempts per arm. This is strong end-to-end decision evidence for Luna under the shared
  configuration, while separate stochastic Pass-1 samples prevent strict selector-only causal
  attribution. Both still missed all three Labor-Day-Thursday trials; no fallback, compiler, or
  deterministic validation change was made from these runs. A subsequent traced Luna-only rerun
  produced 48 Pass-1 `APIConnectionError` sidecars and zero selector attempts; it is recorded as
  provider-connectivity evidence, not as a selector outcome. Its immediate same-configuration
  retry reproduced all 48 connection failures and zero selector attempts. Review confirms that
  tracing writes only after the SDK call, so it did not cause the connection failures; current
  artifacts cannot distinguish local network/proxy/TLS/firewall from provider connection-path
  failure. A one-call diagnostic subsequently reproduced the error and showed an `httpx`
  connection cause with `gaierror` errno 8; the official `api.openai.com` endpoint itself could
  not resolve and no endpoint/proxy/certificate override was configured. That is current local DNS
  connectivity evidence, not selector evidence. On 2026-09-05, a credential-safe recovery
  preflight loaded the repository-local `.env` through the normal CLI mechanism and made one
  authenticated, non-model `GET /v1/models` request: it returned HTTP 200 in 1.03 seconds. This
  establishes that DNS, TLS, routing, and credentials were working at that later instant; it does
  not revise the prior failed matrices. The repeatable command and failure interpretation are in
  `docs/build-log/2026-09-04-selector-duration-projection-fix.md`. An immediately subsequent,
  traced network-authorized Luna Pass-1 plus Luna-selector rerun completed all 48 records with
  39/48 passes, zero transport or selector errors, 42 selector attempts, and 90 calls. The
  sandbox attempt's 48 connection errors are retained separately and are not scored selector
  evidence. Both artifacts and the exact trace location are recorded in that build-log entry.
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
