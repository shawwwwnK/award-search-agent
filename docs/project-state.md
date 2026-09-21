# Project State

## Phase

Milestone 2B market-aware gateway-airport discovery is implemented and owner-closed as of 2026-09-19.
Milestone 2C deterministic search-strategy compilation is implemented in place, with no V1
compatibility path. The [planning handoff](handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md)
records the accepted design and the
[implementation record](build-log/2026-09-19-m2c-implementation.md) records the code, independent
review fixes, offline verification, and model-only integrated diagnostic. The provider-neutral
compiler makes no additional model call and no provider call. Provider execution and
provider/product qualification remain outside this stage. M2A remains diagnostic-only, 2B remains
closed, and independent human semantic qualification is not claimed.
The owner's subsequent Cached Search airport-list challenge is recorded in the handoff's Section G:
retain pair-level coverage/provenance and specify grouped downstream requests. The owner delegated the
compiler-limit decision to the parent/architect; two independent recommendations converged on 31 input days,
100 mandatory pairs, 24 supplemental relationships, 128 total unique logical queries, and 4,000
query-date-days. These are selected local compiler guardrails, not provider limits. The owner then
explicitly declined V1 compatibility: 2C should replace the current planner contract, policy, handoff,
callers, and fixtures in place. The old 25/40/1,400 limits and route-expansion runtime are not retained
as an active compatibility path. Historical evidence remains preserved. Provider batching and live
provider execution were not implemented by 2C.
Search planning is implemented and offline verified as a planning-only, retrieval-backed
`EffectiveRequest -> CompiledSearchPlan` stage that follows the frozen one-way award request-understanding
and clarification boundary. Its declared coverage remains the checked-in offline seed snapshot,
not a claim of operational airport, route, schedule, inventory, or provider coverage.

On 2026-09-20, the owner requested a one-trial end-to-end diagnostic over the active 19-case Intent
behavioral corpus. The behavior-preserving connector projected every completed Intent result into
clarification state without inventing answers and sent only ready sessions into current planning.
The final artifact recorded 13/19 Intent behavioral passes, six awaiting-answer sessions, four
correct unsupported stops, two `pending_retryable` Intent outcomes, and seven compiled plans. All
seven plans had complete mandatory coverage, equal same-record replay, and current executable
handoffs; 35/35 model calls reconciled to private traces, and no travel provider was called. An
exact-date precision bug in the evaluation connector was fixed and regression-tested before the
final run; runtime behavior was unchanged. The unsafe `ambiguous_departure` ready/plan outcome,
holiday and typo misses, missing-destination property mismatch, and two pending outcomes preserve
the broad upstream evidence gap. This is one development trial, not semantic qualification. See
the [evaluation record](build-log/2026-09-20-intent-to-search-planning-evaluation.md).

The operational Milestone 1 geographic/airport catalog is a versioned local SQLite artifact
with a JSON receipt/manifest (ADR 0018). The small Pydantic/JSON seed remains the Milestone 0
fixture contract; Pydantic validates import/publication/query boundaries rather than materializing
the full operational catalog in memory.

On 2026-09-19, the owner requested architecture and engineering review in preparation for 2C,
including FDE recruiting evidence and a durable register of work to revisit after the core workflow.
The advisory findings are in
`docs/reviews/2026-09-19-search-planning-architecture-review.md`; the root `DEFERRED.md` separates
core remaining work, claim-specific prerequisites, parked enhancements, and deliberate non-goals.
An owner-requested fresh-context Astra challenge revised the advisory review in place: earlier
owner/provider feedback, no automatic cross-query assembly in the first provider pilot, and
corrected historical-versus-current evidence claims. Its record is
`docs/build-log/2026-09-19-astra-adversarial-review.md`.
Those records were design input; the later authorized 2C implementation is recorded separately.
Their unadopted recommendations remain advisory, and closed stages remain closed.

The owner subsequently requested a high-level reassessment of each future stage grounded in
implemented-stage lessons and agent-system engineering. The advisory
[future stage goals](reviews/2026-09-19-future-stage-goals.md) proposes revised objectives,
completion evidence, an earlier provider/result/output pilot, and conditional RAG, coverage,
and adaptive-control investments. It complements the implementation-focused review; the active
roadmap and existing stage status remain unchanged. No proposed sequencing or policy was adopted.

An owner-requested fresh Astra agent subsequently challenged that stage-goal proposal through
back-and-forth review. The revised recommendation compares against the owner's current workflow,
requires positive task-value evidence as well as honest failure handling, and tests reviewed search
bundles before deciding whether full supplemental 2C automation is worthwhile. Progressive coverage
is an explicit proposed alternative to the current all-pairs contract. These changes remain advisory;
the [debate record](build-log/2026-09-19-future-stage-astra-challenge.md) records qualifications and
the distinction from approved scope.

The owner also requested a deferred intent/clarification improvement plan on 2026-09-19, to revisit
after the core workflow is built. The [advisory plan](reviews/2026-09-19-intent-clarification-improvement-plan.md)
examines contextual amendments, post-ready revision, recovery, presentation alternatives, and
task-level evidence. It is linked from D01 in `DEFERRED.md`; G01/G03 remain claim-specific gates.
This planning session made no upstream implementation, live evaluation, or architecture-policy
change.
At the owner's request, a fresh Astra challenge subsequently revised that plan through parent-agent
debate: choose work from observed task costs, count context-induced errors, separate known-intent
and exploratory tasks, and compare explicit outbound-scope recovery before assuming linked trips
are necessary. These remain advisory options under D01/D04, not policy changes or reopened work.
A subsequent use-case/FDE pass and separate fresh Astra challenge tied the plan to a justified
traveler decision and effort versus the owner's existing workflow. D01/D14 now emphasize one actual
task observation and personally explaining an existing AI failure before adding new mechanisms;
these do not establish broad qualification, customer adoption, or enterprise delivery.

Milestone 1 is complete. The owner reviewed the local lossless replacement release
`m1a-3cb7981519612945` on 2026-09-16, including its manifest, coverage, counts, 35 explicit
reconciliation quarantines, full retained-source payloads, lookup limits, and qualification
results. It remains local-only; deployment-time hosting/retention is deferred. Milestone 1B serves
that selected release read-only through the existing planner boundary while preserving the JSON
fixture path. Its completed components and acceptance criteria remain recorded in the current
milestone roadmap.

Milestone 2A has a narrow implementation boundary: an LLM may propose bounded individual
endpoint-airport IATA codes for an already resolved canonical geographic entity; deterministic
code records catalog identity/facility/supported-scope validation and replays a supplied selection
record without another model call. It does not establish city-serving facts, regional membership
outside country evidence, routes, schedules, award availability, provider execution, RAG, or a
cache. Its active-policy v3 live diagnostic completed, but the selector remains diagnostic-only
pending independent human semantic review, preregistered holdout evidence, evidence that larger
caps improve useful coverage relative to work, and an adoption decision; see ADR 0019 and the M2A
evaluation protocol. The active cap
policy gives the United States a country maximum of 10 for US-focused international-gateway
coverage; the prior v2 active-policy diagnostic used US=6 and is historical evidence only, not
validation of US=10. The active v3 diagnostic has completed and remains diagnostic evidence only.

The owner approved the Milestone 2B direction on 2026-09-18 in ADR 0020: a versioned global
planning-market policy deterministically classifies original endpoints and skips generation only
when every endpoint is known and their combined market union has exactly one member. Every other
valid input receives one grouped structured model proposal. An unknown endpoint market forces
generation with an explicit mapping-gap receipt. A model/policy candidate-market disagreement is
advisory and passes to 2C rather than rejecting an otherwise valid candidate. Generated candidates
remain bounded, unverified search hypotheses, not route, schedule, connectivity, award, or booking
facts. This decision does not close or adopt 2A: reviewed fixtures or supplied selection records
remain permitted without promoting model proposals into geographic fact.

On 2026-09-19, the small versioned market policy, grouped structured generator,
relationship-aware validator, and immutable replay record were implemented and offline verified.
The prompt-v5/casebook-v2 and first prompt-v5/casebook-v3 evaluations are historical diagnostics.
The final prompt-v6/casebook-v3 development evaluation completed mechanically: its public artifact
and private trace sidecars reconcile all expected calls. Access gateways may be materially
complementary departure or arrival alternatives even for already-strong endpoints, but must clear a
higher specific incremental-value threshold; size, proximity, shared market, or geographic diversity
alone is insufficient. Origin access (0–2), destination access (0–2), and hubs (0–5) have independent
maximums, with no intermediate-market diversity quota. It is development evidence only; no semantic
qualification, connectivity claim, SearchPlan adoption, or 2C implementation follows from it. The
v6 run recorded 46 case-trials and 42/42 expected calls across two trials: 37 nonempty, 4 empty,
4 policy-skip, and 1 partial outcomes; 82 accepted candidates (22 origin access, 18 destination
access, and 42 hubs), 43 scopes, and 400 accepted relationships; 186,549 tokens; one PNH
catalog-absence rejection; and three retained market-mismatch advisories. Artifact-integrity and
independent AI semantic review passed for owner human review, not human semantic qualification.
Relationship-level budgeting remains mandatory for 2C.

## 2026-09-19 casebook-v3 live diagnostic complete

The disclosed v3 casebook preserves all eight v2 scenarios and appends 15
grounded endpoint sets across additional market boundaries, grouped metro
inputs, and the ITO Hawaii override. It has 23 scenarios: two deterministic
same-market skips and 21 grouped-generation cases, so the fixed two-trial
live bound is 42 calls with no retry or refill. The v3 fixture SHA-256 is
`ba3b2e0efd73a2774da6af2950ff4addaf5e7763f754b49042dd56acec3b2f06`.

The first prompt-v5/v3 diagnostic exposed relationship multiplication: 46
records and 42 calls produced 125 accepted candidates, 76 scopes, and 731
accepted relationships across 184,604 tokens. Prompt-v6 added relationship-level
uncertainty/scope reconciliation and same-scope candidate consolidation without
changing the schema, adapter, catalog, policy, or deterministic validator. The
final artifact is
`evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json`.
It has 46 records and 42/42 calls: 37 nonempty, 4 empty, 4 policy skips, and
1 partial; 82 accepted candidates, 43 scopes, 400 accepted relationships, and
186,549 tokens. One PNH catalog-absence rejection and three market-mismatch
advisories were retained; there were zero errors or generation failures.
Artifact/privacy audit and independent AI semantic
review passed for owner human review, not human qualification. Residual review
notes include high relationship counts for India and Los Angeles/Australia-New
Zealand cases, trial variation, one IPC→PPT circuitous regression, and a private
trace control-character hygiene note. No prompt-v7 or deterministic semantic
rejection change is currently recommended; 2C budgeting is mandatory.

## Current conclusion

The owner closed Milestone 2B on 2026-09-19 after reviewing the implemented boundary, offline
verification, prompt-v6/casebook-v3 live diagnostic, artifact audit, and independent AI semantic
review. Closure accepts the 2B implementation and evidence record without claiming verified
connectivity or independent human semantic qualification. The later authorized Milestone 2C
implementation consumes the closed 2B replay record without changing that closure.
The durable closeout is
`docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md`.
Milestone 1 completed the local geographic/airport foundation, and Milestone 2A supplied the
still-diagnostic endpoint selection seam described above. The preceding
search-planning cut is implemented and fixture-qualified for the declared local seed coverage.
This is the planning-only boundary recorded in
`docs/handoffs/2026-09-10-search-plan-design-stage.md`:

```text
ClarificationSession(ready).effective_request -> SearchPlan
```

The implemented planner consumes a ready outbound-only `EffectiveRequest` and produces
inspectable, bounded, deterministic expected search items from versioned local evidence. Its
ten-case offline golden evaluator qualifies the declared seed fixture coverage, including airport
groups, typed failures, directional synthetic topology, dates, budgets, payment annotations,
canonical ordering, optional-path budget degradation, and stale-plan handoff. It must not call
Seats.aero, map provider payloads, parse provider responses, normalize results, rank
recommendations, or mutate the source request/session. Search planning is fixture-qualified for
this declared local coverage. Milestone 1 supplied the geographic and airport-data foundation in
`docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`: reviewed, versioned GeoNames and
OurAirports records, named-region taxonomies, and an explicit local catalog release. M2A evaluates
model-proposed endpoint selection against that catalog. M2B uses the approved market policy and
grouped model-proposal boundary to evaluate useful optional search hypotheses without assuming that
a route catalog is the answer or claiming connectivity.
Airport groups beyond the existing examples are not a mandatory runtime whitelist. Search-strategy
compilation, providers, and RAG are later milestones.
The recorded broad behavioral evidence gap for the upstream one-way boundary remains historical
evidence and is not silently promoted to qualification or used to reopen intent/clarification
semantics.

The qualification corpus pins canonical SHA-256 identities for the default knowledge snapshot,
Cached-Search capability record and version, and default planning policy; it also validates the
local capability-source bytes before evaluation. Its executable coverage matrix names the exact
end-to-end fixture cases. Fine-grained tamper and forged-handoff receipt behavior is unit-only
coverage, not a claim that the golden corpus exercises every internal branch. No provider execution
is included in this planning qualification or the current non-provider planning work.

On 2026-09-12, local Seats.aero reference review fixed the planning capability target to Cached
Search. Product admission remains the one-way origin, destination, traveler, bounded-window,
award, and no-conflict boundary; a distinct provider-executability check requires resolved airport
lists. Optional unknowns, such as cabin, remain visible planning issues. Cached Search has no
traveler-count filter, so travelers remain a later result-validation obligation. Its reviewed
filter enum contains only cabin availability, direct-flight availability, carrier involvement,
redemption-program, and minimum-reported-cabin-distance filters. Current free-text hard constraints
remain deferred post-search validation obligations until a future typed, item-grounded upstream
contract exists; they are not silently parsed. Planning dates use the selected first actual origin
airport's IANA timezone; later components use the explicit exploratory numeric envelope from one
day before the supplied start through two days after its end. These decisions are recorded in
docs/handoffs/2026-09-12-search-planning-design.md.

On 2026-09-11, the owner reopened the initial intent boundary. ADR 0017 supersedes ADR 0010 and
the scanner-owned portions of ADR 0009: one LLM semantic receiver now reads all initial-request
language, including understandable typos and date paraphrases, and returns grounded semantic facts
and generic calendar operations. Deterministic code validates grounding and authority, computes
calendar dates, applies conflicts and ADR 0016 policy, and derives clarification. The scanner,
candidate catalog, and opaque selector are not on the live path and have no runtime fallback.

The initial three-trial, 19-scenario Luna diagnostic completed all 57 runs with trace
reconciliation and public-redaction inspection passing, but only 8 behaviorally passed; 46 became
`pending_retryable` results after post-inference structured-proposal validation failures. That
diagnostic is historical evidence of the retired provider-contract defect, not behavioral
qualification. The artifact is
`evals/intent/baseline/2026-09-11-intent-behavior-v1-gpt-5.6-luna-3-trials-redesign.json`.

The subsequent wire-v2/repair correction completed with 273 passing offline tests and 99
explicitly historical skips. A narrow ten-trial Luna reliability gate for `Find two business award
seats from SFO to BKK on October 5.` returned 10/10 exact ready results—SFO to BKK, two travelers,
business award, and 2026-10-05—with zero repairs, pending outcomes, errors, blockers, unsupported
parts, or active return/duration state. This establishes the direct reasonable-input promise for
that request, but is not a replacement for a refreshed broad behavioral live matrix.

The active initial-intent policy now requires ordinary reasonable input to complete as `ready`,
`clarification`, or `unsupported` after internal normalization/repair. If an inference-reached
model result remains unusable after the permitted repair, it completes as clarification with
salvaged facts and explicit blockers. `pending_retryable` is reserved for genuine preflight,
authentication/configuration, network/transport, or provider operational failure. The local
harness keeps an operationally pending request and its deterministic context session-local, shows
only a stable stage/code status, offers an explicit retry, and never creates a clarification session
or displays raw provider/model/validation detail.

The owner closed this intent/clarification redesign stage for now after the narrow reliability gate.
Do not make further semantic-boundary changes or run broad live qualification without explicitly
reopening it. The remaining broad behavioral matrix is an evidence gap, not an authorization to
resume the stage automatically.

The selector-only history below is retained as historical evidence and does not describe the
current live initial-intent workflow.

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
strategy. The clarification receiver is the only semantic reader of an answer; prompt copy is
post-reduction LLM output, without a deterministic clarification fallback. ADR 0015 further
supersedes ADR 0014's clarification temporal representation: the receiver owns generic,
grounded calendar-calculation proposals rather than a phrase-oriented temporal mini-language.
Deterministic code validates invariant safety, evaluates the proposal against immutable context
through an acyclic same-answer fact graph, and reduces state; it does not parse or repair answer
wording. A proposal failure receives at most one shared model-owned repair across schema,
grounding, and calculation failures and otherwise becomes a visibly communicated, non-mutating
pending/retryable outcome, not a raw user-visible exception or a user no-progress turn.

The historical initial parser is retained as evidence only. In particular, none of the historic
continuation-only raw-text rules for `this weekend`, weekdays, endpoint cues, numbered answers,
or `following`/`afterwards` are current policy. Their prior qualifications and artifacts are
historical evidence for superseded implementations, not qualification of ADR 0015.

The clarification-stage receiver is currently configured as `gpt-5.6-luna`; GPT-4o mini remains
comparison evidence, not a fallback or runtime alternative. The live Luna/Luna run completed with
telemetry reconciliation but exposed representation-boundary failures for reasonable answers.
It is diagnostic evidence only, not a qualification result. The prior one-trial v3 development
diagnostic had all eight scenarios rejected by the provider's `oneOf` output schema before model
inference, so it is adapter/preflight evidence rather than semantic or behavioral evidence. The
OpenAI-only flat wire adapter now structurally translates provider-safe fixed fact arrays into the
internal generic proposal contract without raw-text parsing. The checked-in v3 pilot corpus still
does not provide a non-vacuous qualifying denominator for every behavioral metric. Future traces
and artifacts bind the internal proposal-contract version, wire-adapter version, and generated
schema hash; the v3 protocol separates semantic diagnosis, safe workflow action/property success,
hard safety, and operational repair/pending metrics. No live receiver or composer model-selection
qualification exists for the ADR 0015 boundary yet.

On 2026-09-10, the project owner closed this ADR 0015 implementation/evaluation stage for now.
The final disclosed Luna/Luna matrix ran all eight public pilot scenarios for three trials (24
sessions): all 63 calls reached structured results with zero preflight, runtime, or telemetry
errors, but the current evaluator gate failed. Trace review confirmed an unsafe ambiguous-endpoint
acceptance, safe-but-unsuccessful alternatives and bounded-month handling, and loss of independent
siblings after an exhausted invalid-proposal repair. It also identified two evaluator
classification issues (disclosure when no approximation was accepted, and conflict blocker
replacement classified as partial resolution). These are diagnostic findings, not qualification or
a direction to resume ADR 0015 work. The closeout is
`docs/handoffs/2026-09-10-adr-0015-stage-closeout.md`.

On 2026-09-10, the owner narrowed the next cut to
`EffectiveRequest -> SearchPlan`. This is a design stage for the expected Seats.aero request
items; implementation begins only after external high-level design review. It must not make API
calls, normalize provider responses, or rank results. The planning boundary must resolve
city/region/country candidates into stable airport sets and may propose connection-search legs
using grounded retrieval data. The stage brief is
`docs/handoffs/2026-09-10-search-plan-design-stage.md`.

On 2026-09-11, the owner paused that search-plan design stage and reopened the live intent and
clarification boundary for a one-way award-only recut (ADR 0016). The active workflow requires an
origin, destination, bounded outbound departure window, and traveler count. Return dates and trip
durations are out of scope: when structured intent or clarification semantics identify either,
the system must visibly direct the user to submit a separate one-way request and must not add them
to active request/session state. Cash-only requests are invalid. Mixed award-and-cash requests may
continue as award requests, without any claim that cash pricing is available. The existing
round-trip/cash-capable contracts, code paths, and evaluation artifacts remain historical evidence;
there is one replacement live workflow, not a runtime mode switch.

The ADR 0016 implementation has 334 passing offline tests and completed its architect-reviewed v2
live matrix with Luna at every model boundary. The immutable intent fixture ran 18 scenarios for
three trials (54 runs): 52 passed, 2 behaviorally failed, and 0 errored; 102/102 model calls and
54/54 private run traces reconciled. The immutable clarification fixture ran 12 scenarios for three
trials (36 sessions): 35 passed, 1 behaviorally failed, and 0 errored; 123 calls reconciled with
36/36 private session traces. Both public artifacts carry fixture hashes and passed redaction
inspection. This is a mechanically complete, diagnostic evaluation—not behavioral qualification:
the remaining failures cover cash-only traveler extraction, default-award handling in the
home-airport guard, and an ambiguous departure answer that became pending and invoked a composer.

### Superseded clarification evidence

The following records are retained as evidence for their then-current continuation contracts,
not as ADR 0015 qualification. Historic recovery/template artifacts reported 48/48 terminal
outcomes, 60/60 exact blocker/prompt checks, and zero unauthorized mutations; they relied on the
retired deterministic raw-text recovery/relative-selector policy. The ADR 0012 behavioral-v2
artifact reported zero false blocks (0/27), zero incorrect acceptances (0/12), assumption
disclosures (24/24), and valid-sibling retention (18/18), while also identifying generic conflict
follow-ups (12/15 targeted questions). The detailed files and private trace metadata remain in
the build log and artifact history; their scores must not be carried forward to the new proposal
boundary.

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

One-way award request understanding and clarification: turn an initial parsed snapshot plus
successive user answers into a traceable outbound-only `EffectiveRequest` that is `ready` for later
planning or explicitly stopped/unsupported.

## Representative request

"Find two business-class award seats from SFO to Bangkok leaving during Labor Day weekend."

## Intended current output

An `EffectiveRequest`, full blocker-set clarification prompt, and traceable session state after
each response, terminating at `ready`, explicit `stopped`, or non-mutating pending/retryable
interpretation only for a genuine preflight, authentication/configuration, network/transport, or
provider operational failure. An inference-reached model response that remains unusable after
repair completes as clarification with salvaged facts; reasonable user language never terminates
in pending.

## Current technical assumptions

- Python with a `src/` layout.
- Pydantic domain models.
- pytest.
- Model interaction behind an interface.
- No agent framework selected.

## Largest project-level risk

Feasible access to useful award-inventory data.

## Immediate milestone

The ADR 0015 implementation/evaluation stage is closed for now. Its generic-proposal design and
the frozen initial workflow remain unchanged; do not make further ADR 0015 live evaluations or
semantic-boundary changes without explicit owner reopening. If reopened, begin from the documented
failure ownership and closeout, rather than treating the public pilot as qualification. Preserve
the current no-raw-text-parsing boundary, one-repair/pending policy, immutable-state invariants,
and private-trace/redacted-artifact discipline until then.

The current search-planning boundary is implemented and fixture-qualified for the declared checked-in
offline seed snapshot. It consumes the frozen ADR 0016 outbound-only contract and ADR 0017
upstream request-understanding boundary: no return date or duration can enter planning state,
cash-only requests do not become ready, and mixed award-and-cash requests remain award-only
without cash-search claims. This qualification is planning-only and does not claim operational
airport, route, schedule, inventory, or provider coverage. Milestone 1B is owner-approved and
closed as of 2026-09-16. It serves the owner-reviewed local SQLite catalog through the existing
deterministic location/planner boundary while preserving the Milestone 0 JSON fixture path and its
reviewed group policies. M2A is implemented but remains diagnostic-only pending its recorded
semantic/adoption gate. M2B implements ADR 0020's approved market policy, generation gate,
grouped proposal, deterministic relationship validation, and replayable selection record; its
prompt-v6/casebook-v3 diagnostic is mechanically complete but not independently human-qualified.
The stage is owner-closed. The implemented 2C compiler preserves mandatory original endpoint
coverage, budgets compiled relationships and query/date work, and records omissions without
relabeling accepted candidates invalid. Provider execution remains subsequent and separately
scoped. Preserve the upstream and M2A evidence gaps as
such—do not reopen their semantics or call them qualified through this documentation change.

The prior implementation handoff remains historical context. ADRs 0014 and 0015 plus the v3
clarification acceptance protocol are the current policy where they differ from ADRs 0011--0013
or that handoff. The freeze handoff is `docs/handoffs/2026-09-05-intent-freeze-handoff.md`; ADR
0010 is superseded for the live initial request-understanding decision by ADR 0017. Earlier
references to `two_pass` and selector-only extraction are historical evidence only.

## Current implementation status

- Seats.aero passed one narrow cached-search access-and-response-shape spike; no application
  adapter or provider error fixture exists yet. The provider-neutral `CompiledSearchPlan` boundary
  is implemented and offline verified, but it does not authorize a provider adapter or any provider
  call. M2B's grouped generator, relationship-aware validation, and replayable candidate record
  are implemented and owner-closed. M2C compilation is implemented; provider execution remains
  separately scoped. SerpAPI Google Flights
  remains a later cash-fare candidate. See
  `docs/provider-feasibility/2026-09-08-initial-provider-intake.md`.
- The frozen initial workflow stops after `ClarificationDecision`; the additive continuation
  boundary owns subsequent answers, deterministic reduction, a local-only Streamlit harness, and
  separate offline/live corpora under ADR 0011. Every live continuation evaluation writes
  all-call private trace sidecars by default and a redacted public artifact.
- The continuation receiver owns raw language and emits generic calendar proposals. Deterministic
  continuation code may validate/evaluate those proposals but may not scan answer language for
  relative-time phrases, endpoint cues, line positions, typo variants, or other semantic repairs.
- Receiver proposal failures share exactly one model-owned repair across schema, grounding, and
  calculation stages. A residual failure is a visibly communicated, non-mutating pending/retryable
  outcome; valid independent facts are retained and it never leaks as a raw schema exception or
  automatically counts as user no-progress. Same-answer fact references form an acyclic graph and
  are evaluated by dependency, not source-text order.
- The OpenAI adapter is intentionally flat and provider-specific: fixed arrays by fact kind and
  flat anchor fields structurally translate into the provider-independent calendar proposal. A
  provider schema rejection is pre-inference adapter/pending evidence, never a semantic failure;
  retrying the identical schema does not spend the repair budget. Live artifacts retain the
  proposal-contract version, wire-adapter version, and generated-schema hash.
- The v1/v2 continuation corpus and historic three-trial scores are retained as historical
  conformance evidence. They are not ADR 0015 qualification evidence. The checked-in v3 corpus is
  an oracle/telemetry pilot, not a qualifying run. Current qualification requires v3
  action/property oracles, non-vacuous eligible metric denominators, a locked holdout, rotating
  post-freeze metamorphic challenges, and separate semantic-diagnostic, behavioral, safety, and
  operational metrics.
- One semantic receiver is the sole live initial-intent boundary (ADR 0017). Ordinary reasonable
  language and provider-wire representation/shape noise are internally normalized/repaired into a
  normal outcome; an inference-reached model result that remains unusable after repair completes as
  clarification with salvaged facts and explicit blockers. Only genuine preflight,
  authentication/configuration, network/transport, or provider operational failures are typed
  pending outcomes and cannot start clarification. The harness preserves pending request context
  locally and offers a generic, user-triggered retry. There is no scanner, candidate selector, or
  runtime fallback.
- The active intent evaluator is schema v9 and scores action/property outcomes, preserving exact
  deterministic safety assertions. Earlier selector artifacts and fixtures are historical evidence
  and are explicitly segregated from active coverage.

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

The living register is [DEFERRED.md](../DEFERRED.md). It supersedes this section's
old undifferentiated scaffold list, which incorrectly continued to call all planning
deferred after planning milestones were implemented.

The register distinguishes required work for the first complete one-way award
workflow from post-core enhancements and prerequisites for specific claims. It
records sources, stable IDs, revisit triggers, and closure evidence. New review
recommendations remain proposals; the active roadmap/ADRs are unchanged.

## Living workbook

Broader project design context is maintained at:

`/Users/shawnkang/bots/workbook_formatted.md`

The workbook evolves alongside the implementation and should be consulted when broader product or evaluation context is needed.

## Decisions that supersede older project notes

The first workflow has now been selected as the award-search agent.

Older source documents should not be automatically updated as part of this scaffold task.
