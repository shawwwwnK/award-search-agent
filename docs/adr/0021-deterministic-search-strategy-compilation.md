# ADR 0021: Deterministic search-strategy compilation

> Current-status note (2026-09-21): ADR 0023 adopts M2A replay as the sole geographic endpoint
> source, retains direct airport grounding, and removes the reviewed-mapping and Milestone 0
> compatibility alternatives. The compiler remains deterministic and provider-neutral.

## 2026-09-20 amendment: provider-neutral compilation and structural safety

The owner superseded only the provider-capability binding and compiler-allocation
decisions below. The original 2026-09-19 text remains in this ADR as historical
context for the first implementation; where it conflicts with this amendment,
this section is the active decision.

The active 2C compiler is provider-neutral. `SearchPlanningInput`, plan identity,
the compilation binding, and handoff freshness do not contain a Cached Search or
other provider-capability receipt. Capability acceptance and provider request
mapping belong to the later provider-planning/execution boundary.

The 31-day input-window limit and the 24 supplemental relationship, 128 unique
query, and 4,000 query-date-day allocation limits are removed. They were
provisional execution-shaped controls without a 2C structural basis. The
compiler deterministically materializes every replay-valid, representable 2B
relationship and preserves semantic query deduplication, complete provenance,
positioning suppression/conditionality, and explicit unsupported-rule receipts.
It does not prune supplemental work or return reduced coverage because an
execution budget was exhausted.

One provider-independent structural safety boundary remains: at most 100
selected origin × selected destination pairs may be materialized. This is an
all-or-nothing quadratic expansion guard, not a provider limit or an upstream
promise that endpoint counts are capped. Exactly 100 pairs compile; an observed
cross-product above 100 returns a typed `UNPLANNABLE` result with no plan. No
separate relationship or logical-query cap is needed: replay-verified 2B
candidate/scope bounds together with the 100-pair guard finitely bound the
downstream compiler graph. Finite departure windows longer than 31 days remain
valid 2C inputs.

Provider planning later owns rectangle-safe multi-airport batching and its own
pages, attempts, returned rows, bytes, time, result-validation, and
scheduled-versus-deferred receipts. Conceptual query-date-days may be measured
as an observation; they are not a 2C admission unit.

## Context

The pre-2C planner creates a route-evidenced `SearchPlan` from frozen request
state and selected endpoints. Its active path-expansion and fixed item limits do
not represent the work supplied by Milestone 2B: an immutable, replayable record
of model-proposed gateway and hub candidates. A 2B candidate is a search
hypothesis, not evidence of a route, schedule, protected connection, award
availability, or a bookable journey.

Milestone 2C needs a deterministic boundary that turns frozen
`EffectiveRequest`, selected endpoints, and a bound 2B record into complete
mandatory pair coverage and bounded optional search work. It must preserve the
distinction among a supplemental hypothesis, a pair-valued logical query, a
later provider request, and an observed itinerary.

The project is local development work with no deployed consumers. The owner has
chosen an in-place replacement rather than a V1 compatibility path and has
delegated the current compiler limits. Provider execution remains a later,
separately scoped slice.

## Options

1. Retain the route-evidenced `SearchPlan`, add a compatibility wrapper, and
   represent 2B proposals as incomplete paths.
2. Create a second active planner and maintain V1/V2 conversion and caller
   compatibility.
3. Replace the active planner contract in place with one deterministic
   `CompiledSearchPlan`, one current `PlanningPolicy`, and one planning handoff;
   migrate repository callers and retain old plans only as historical evidence.

Choose option 3.

## Decision

### One compiler, one current contract

The active public planning entry point compiles one `CompiledSearchPlan` from
reparsed frozen inputs, selected endpoint projections, a replay-bound 2B record,
catalog evidence, and the current policy. It makes zero model or provider calls.
There is no V1 runtime, compatibility adapter, automatic migration of old plans,
or second planning policy. Existing historical fixtures and reports retain their
meaning as evidence; they are not executable compatibility artifacts.

The plan identity binds request state, catalog receipt, endpoint-selection
source/provenance, 2B result/input and market-policy identities, compiler and
policy versions/digests, and the provider-capability planning receipt. It also
states that route-topology expansion is absent. Canonical content-derived IDs and
canonical serialization make valid inputs replayable and byte-stable.

Mandatory work is every selected origin × selected destination pair. The
compiler never silently trims endpoints. An over-limit mandatory set returns a
typed unplannable outcome with no partial plan.

### Current compiler limits

The versioned current policy is:

| Unit | Limit |
| --- | ---: |
| Input departure-window days | 31 |
| Mandatory endpoint pairs | 100 |
| Supplemental relationship bundles | 24 |
| Unique logical queries | 128 |
| Query-date-days | 4,000 |

These are compiler admission limits, not Seats.aero capability claims, request
limits, or bounds on replay validation CPU/memory. They allow the full product
of the current single-location selection maxima through 10 × 10 while retaining
an explicit overflow outcome for larger combined inputs. The compiler reserves
mandatory work first, then admits only whole supplemental bundles under all
applicable limits. It records each accepted 2B relationship as admitted,
budget-omitted, explicitly refused positioning, or unsupported due to a finite
representability rule. It does not truncate those receipts.

### First-slice supplemental vocabulary

The compiler has exactly these supplemental strategy types:

```text
origin access:       alternate gateway G -> selected destination D
destination access:  selected origin O -> alternate gateway A
scoped hub:          typed origin-side reference X -> hub H, then H -> typed destination-side reference Y
```

It does not independently compose origin and destination access into `G -> A`.
A typed hub scope may reference access gateways, allowing `G -> H` and/or
`H -> A` within that explicit scope. That is a bounded first slice, not a claim
that further composition is impossible.

Strategies carry exact 2B relationship identities, scoped support alternatives,
and unresolved positioning, separate-ticket, temporal, original-departure, and
complete-journey validation obligations. They do not assert that their
components form an itinerary. Ordinary connections inside a provider-returned
result remain permitted; cross-query assembly is deferred.

### Queries, provenance, and allocation

`LogicalAwardQuery` is the pair-valued, provider-neutral work unit. Its semantic
identity includes both airport facts, inclusive dates and query-origin timezone,
award/cabin/filter semantics, connection semantics, and result-validation
requirements. It excludes strategy provenance, model reasons/confidence, and
source ordering. This permits semantic deduplication while preserving
many-to-many mandatory and supplemental query-use links.

Mandatory pairs reserve their query and date work before supplemental admission.
Supplemental queries may reuse existing semantic queries at zero marginal query
or date cost, but each strategy must be admitted as its complete one- or
two-query bundle. Allocation uses an explicit versioned strategy-type priority
and round-robin original endpoint-pair lanes, with stable content IDs only as
ties. Model confidence and explanation text are provenance, never a usefulness
score or allocation input.

Every supplemental date envelope derives directly from the original departure
window and uses the query-origin airport's IANA timezone. Wider component
windows are research approximations and cannot authorize a completed journey
outside the requested departure window.

### Positioning policy

`EffectiveRequest.repositioning_allowed=false` suppresses only strategies that
require positioning. Such work is not admitted and has a refusal receipt.
Absent or unknown permission permits conditional research within the optional
budget and retains the unresolved positioning obligation. This does not infer
separate-ticket permission, which remains unknown for supplemental work. It
does not reinterpret free text such as "nonstop only" or "no positioning".

### Replay and topology boundary

The compiler replays and validates the complete bound 2B record before using
it. Catalog/policy identity mismatches, malformed evidence, invalid endpoint
bindings, and input errors are evidence failures; they cannot produce a
success-shaped mandatory-only plan. Known market mapping gaps and model/policy
market mismatches remain advisory provenance and do not silently reject work.

An authentic, replay-valid optional `GENERATION_FAILURE` or
`VALIDATION_FAILURE` fails soft: the result may contain complete mandatory work
with `REDUCED_COVERAGE` and its distinct preserved receipt. A policy skip or
successful empty record may produce mandatory-only `PLANNED`. Partial or
rejected-all results preserve their limitations and reduce supplemental
coverage.

The compiler does not accept route topology, create `ExplicitPathHypothesis`,
or reduce coverage because route evidence is absent. Existing route-evidence
contracts stay meaningful where historical tooling still uses them, but they
are not active 2C inputs.

### Provider boundary and qualification

2C stops at logical queries. A later provider slice may map compatible logical
queries into exact Cached Search airport-list batches, pages, attempts, and
observations. Pair-level logical queries remain the coverage ledger even when
several are issued in one provider request. The provider slice owns proof of
multi-airport request semantics, pagination, result attribution, trip-detail
and error behavior, and observed-itinerary validation.

M2A and M2B diagnostic records may be supplied as immutable, replay-bound
inputs. This decision does not adopt the M2A selector, convert model proposals
into geographic or route facts, or qualify model, provider, product, or
itinerary behavior. Offline fixture qualification proves only the deterministic
compiler boundary for its declared inputs and policies.

## Consequences

- Repository callers, tests, fixtures, evaluator, and planning-handoff
  validation migrate to the replacement contract; obsolete runtime path
  expansion and limits are removed after reference checks.
- Every admitted endpoint pair remains inspectable independently of a later
  batched provider request, while shared query work and strategy provenance are
  traceable.
- Optional 2B failure cannot erase valid mandatory work only when replay proves
  the supplied terminal record is authentic. Corrupt or mismatched evidence
  remains a hard failure.
- The fixed admission budgets do not promise a pre-replay resource bound:
  current 2B replay can expand finite scope products before compiler admission.
  Replay, enumeration, receipt size, and compiled query work are measured
  separately.
- The first slice intentionally leaves automatic cross-query assembly,
  provider execution, ranking, RAG, persistence, and broader endpoint-policy
  adoption outside its boundary.

## Evaluation

Qualification is offline. Tests must cover mandatory O×D coverage and overflow,
semantic deduplication with many-to-many query use, complete-bundle admission,
deterministic type/lane ordering, dates/timezones and date-line cases,
positioning false/unknown treatment, replay identities, authentic failure versus
corrupt evidence, advisory market mismatches, high-fanout records, long windows,
and synthetic access-referenced hub scopes.

The completion report must distinguish portable checked-in synthetic replay
cases from any available local historical M2B diagnostic artifacts. Live M2A/
M2B diagnostics remain development evidence only. No live model or provider
call is part of compiler qualification.

When the separate provider slice opens, it must test its own batch mapping and
pagination/result contracts. Its live evaluation is not evidence that 2C's
compiler logic is correct, and 2C offline success is not provider or product
qualification.

## Revisit trigger

Revisit this ADR when evidence justifies changing the policy limits, strategy
vocabulary, allocation order, date-envelope policy, positioning semantics, or
fail-soft outcome matrix; each change needs a new policy/contract identity and
offline evidence. Revisit the topology boundary only with a separately reviewed
route-evidence source and contract. Revisit the provider boundary when a
provider adapter has documented capability and result-validation evidence.
