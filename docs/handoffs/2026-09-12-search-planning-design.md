# Search-planning design: EffectiveRequest -> SearchPlan

- Status: Implemented and fixture-qualified for the declared local seed coverage. On 2026-09-13,
  the owner selected operational knowledge-base expansion before the later provider-execution stage.
- Date: 2026-09-12
- Stage boundary: [2026-09-10-search-plan-design-stage.md](2026-09-10-search-plan-design-stage.md)

## 1. Purpose and repository findings

This stage deterministically turns a ready, outbound-only EffectiveRequest into an inspectable SearchPlan:

~~~text
ClarificationSession(ready).effective_request
  + caller trace identity
  + PlanningPolicy
  + reviewed KnowledgeSnapshot
  -> SearchPlanningResult
~~~

It ends before a provider call, provider payload, provider-response parsing, normalization, ranking,
recommendation, booking, persistence, or production UI. That cut line is established by
docs/handoffs/2026-09-10-search-plan-design-stage.md:5-23.

### Observed upstream boundary

EffectiveRequest is a frozen, copy-isolated value projection; the ClarificationSession revision
ledger remains authoritative (src/award_agent/domain/clarification_session.py:30-69,255-307,724-813).
It contains raw text, immutable resolution context, travelers, location arrays, departure window,
cabins, modes, repositioning, hard constraints, unknowns/conflicts, field provenance, and temporal
contributions. It does not contain a session ID or revision. The smallest planning input therefore
adds a caller-owned trace envelope containing session_id, revision, and effective_request_digest.
The caller/session layer owns stale-plan rejection; the planner records this identity but never
takes revision authority.

Initial projection is pure, copied, and records only active outbound provenance
(src/award_agent/clarification/projection.py:16-77); the reducer likewise produces a new value
rather than mutating the ledger (src/award_agent/clarification/reducer.py:53-134). Raw text,
temporal contributions, and field provenance are audit material, not permission to parse,
reinterpret, or recompute effective request fields.

LocationRef.value is explicitly a resolver candidate, not a stable entity ID
(src/award_agent/domain/models.py:42-55; docs/adr/0004-location-names-are-resolver-candidates.md:21-37).
The narrow exception is a model-classified airport with a verbatim standalone three-letter request
token: upstream preserves its uppercase code (src/award_agent/intent/locations.py:9-31). Named
airports remain candidates, and syntax never changes a city abbreviation into an airport
(tests/unit/test_locations.py:24-84).

The live contract is outbound-only. ParsedRequest rejects return/duration state, evidence, and
blockers (src/award_agent/domain/models.py:923-988). Cash-only stops upstream; omitted mode defaults
to award; award plus cash is a valid mixed request
(src/award_agent/intent/workflow.py:83-157,216-233; docs/adr/0016-one-way-award-request-boundary.md:53-58).

At the start of this design, no resolver, airport-group catalog, route-topology catalog, planning
module, or application provider adapter existed. That is historical design context. The planning
module and fixture-grade snapshot now exist; the Seats.aero spike and local reference still prove
only a cached-search request shape, not topology, schedules, seats, booking, freshness, coverage,
or failure behavior
(docs/provider-feasibility/2026-09-08-initial-provider-intake.md:31-55).

### Material mismatches

| Topic | Observed behavior | Recommended disposition |
| --- | --- | --- |
| READY and unknowns | Session readiness blocks conflicts plus only origin, destination, departure, and traveler unknowns. Cabin, mode, repositioning, and other unknowns are nonblocking (src/award_agent/clarification/blockers.py:28-78; tests/unit/test_clarification_blockers.py:86-99). | Preserve that **product-admission** boundary. A separate Cached-Search executability check requires resolved airport lists. Other unknowns remain visible but do not block merely for being unknown. |
| Hard constraints | The field is arbitrary tuple[str, ...], without a canonical vocabulary, item-level provenance, or active nonempty fixture (src/award_agent/domain/clarification_session.py:270-277; src/award_agent/intent/workflow.py:83-145). | **Owner decision:** only a future typed upstream user requirement may populate the versioned Seats.aero filter enum. Planner structure may add a separately identified physical-component prefilter. Current free text is preserved verbatim as deferred post-search validation, never parsed or silently dropped. |
| Location alternatives | The schema has ordered arrays but no pairing or preference semantics. | Treat as independent alternatives in stable resolved-entity order; never invent positional pairing. |
| Date-zone semantics | DateWindow validates only end >= start. RequestContext.timezone is an upstream interpretation context, not a flight-origin convention (src/award_agent/domain/models.py:17-27,856-875). | Add a versioned planning convention; do not present it as inherited behavior. |
| Manual cash | ADR 0016 forbids cash-search claims for mixed requests. | Represent only dormant, unpriced, unverified manual-cash dependencies; never a cash search or result. |

The workbook is background, not authority. Its older RAG, round-trip, model-led planning, and provider
execution ideas conflict with the current one-way deterministic cut
(/Users/shawnkang/bots/workbook_formatted.md:326-403).

## 2. Settled decisions and implementation defaults

### Settled for this stage

- One directional journey only; returns and durations cannot re-enter planning state.
- Product admission retains origin, destination, travelers, an inclusive bounded nonempty outbound
  window, no conflicts, and at least one award mode. The planner validates these properties
  defensively. This is distinct from provider executability: Cached Search requires only resolved
  nonempty origin and destination airport lists. An unspecified cabin or similar optional field is
  retained as an issue, not a planning blocker.
- Cities, countries, regions, and named airports need grounded resolver evidence. An explicitly
  preserved IATA code is eligible as an endpoint identifier, then still needs a snapshot airport
  record for metadata and evidence.
- Japan selects HND, NRT, and KIX; New York City selects JFK, EWR, and LGA; explicit SFO remains
  SFO. These are selected groups, not exhaustive geographic claims.
- Repositioning research is enabled in v1. The repositioning_allowed value stays unchanged and is
  recorded even when false or null, but does not gate planning.
- The original departure interval is inclusive and never recomputed. Overnight travel is allowed;
  it is not evidence of a feasible connection.
- Award is the only automated search mode. Any potentially supported journey contains at least one
  award component. Cash is manual, unpriced, and unverified.
- Every selected airport and physical path component cites versioned knowledge and a policy decision
  where a preference affected selection.

### Settled and implemented defaults for the fixture-qualified boundary

- No runtime LLM. The remaining work is narrow lookup, evidence validation, bounded graph traversal,
  date-envelope arithmetic, stable sorting, and policy application. A model may assist human
  curation offline but cannot be a runtime resolver or selector.
- Resolve origin/destination alternatives independently, then form their Cartesian product in stable
  entity-ID order. This is the implemented planning default, not a claim of upstream pairing
  semantics.
- Automatic groups select three airports by default, with a hard maximum of five. Explicit airports
  are singleton groups.
- Endpoint-market probes are always selected before optional explicit-path expansion. A probe is not
  a nonstop claim.
- A planner-generated path has at most one intermediate and two physical flight components. It has
  no airport-changing transfer or ground component.
- Every one-component path has the payment pattern award. Every two-component award-only path has
  award/award. A two-component mixed request additionally has award/manual_cash and
  manual_cash/award; the patterns reference the same path rather than duplicating it. A manual-cash
  template is conditional on a relevant award observation and is never executable in this stage.
- The first actual component uses the original date window under the
  selected first-origin airport's IANA timezone. A later component receives a bounded exploratory
  numeric local-date envelope from start minus one day through end plus two days.
  Owner approval was recorded on 2026-09-12; this convention is now settled planning policy.

### Cached-Search capability review (2026-09-12)

The local Seats.aero reference establishes `GET /partnerapi/search` (Cached Search) as the v1
capability target, not Live Search. Cached Search requires comma-delimited `origin_airport` and
`destination_airport` lists; `start_date`, `end_date`, and `cabins` are optional provider inputs
(.provider-docs/seats-aero/cached-search.md:37-76,166-183). The planner still always binds the
product's bounded date window. It must also retain travelers: Cached Search has no traveler or
seat-count filter, so traveler adequacy is a post-search result-validation obligation, not an API
filter. Live Search's `seat_count` belongs to a materially different, out-of-scope operation
(.provider-docs/seats-aero/live-search.md:73-116).

The local snapshot supports exactly these provider-neutral documented filter capabilities:
`CABIN_AVAILABLE_IN`, `DIRECT_FLIGHT_AVAILABLE`, `CARRIER_INVOLVEMENT_MATCH`,
`REDEMPTION_PROGRAM_IN`, and
`MIN_REPORTED_CABIN_DISTANCE_PERCENT`. They map respectively to Cached Search `cabins`,
`only_direct_flights`, `carriers`, `sources`, and `min_cabin_pct`. Airports and dates are search
dimensions, not filter obligations. Pagination, ordering, result-shape options, and result limits
are executor policy, not user constraints.

The owner resolved the policy questions as follows. Optional values such as an unstated cabin do
not block planning. The first actual component uses the selected origin airport's IANA timezone
and each later component uses the explicit exploratory numeric start - 1 / end + 2 envelope.

The current `hard_constraints` strings cannot safely populate that enum. They remain explicit
deferred post-search validation obligations until a later typed, item-grounded upstream constraint
contract exists. This avoids adding a second semantic parser at the planner boundary.

The local Cached Search page declares `updatedAt: 2025-04-23`, while related Concepts and Live
Search pages declare `2026-08-28`; the repository captured the local documentation on 2026-09-08.
The capability record must therefore retain source metadata and hashes. It also records known
uncertainties: endpoint inclusivity/timezone is undocumented, carrier matching says only
"involving" with otherwise undocumented match semantics, multi-cabin matching is unspecified, and the page mentions an undeclared singular
`cabin` field. These are adapter acceptance checks, not assumptions for the planner.

## 3. Architecture, components, and invariants

~~~mermaid
flowchart LR
    A["Planning input envelope"] --> B["Admission validator"]
    B --> C["Grounded location resolver"]
    C --> D["Airport-group selector"]
    D --> E["Endpoint-probe builder"]
    E --> F["Directed topology / path discovery"]
    F --> G["Constraint obligations and date envelopes"]
    G --> H["Budgeted selector and semantic deduper"]
    H --> I["Plan invariant validator"]
    I --> J["Planned | Reduced | Unplannable | Evidence failure"]
~~~

| Component | Input -> output | Responsibility and invariant |
| --- | --- | --- |
| Admission validator | Envelope -> validated view or issue | Rechecks product-ready core fields, no conflicts, and award. It separately verifies that grounded airport sets meet Cached Search's required fields. It never begins clarification or mutates state. |
| Location resolver | LocationRef -> LocationResolution | Exact/narrow alias lookup. It differentiates no match, ambiguity, kind mismatch, and missing/stale evidence; no semantic reparse or fuzzy guess. |
| Airport-group selector | resolved entity -> AirportSelection | Selects a singleton explicit airport or policy-ranked factual group members. Facts and preferences stay separate. |
| Endpoint-probe builder | selections -> EndpointProbe and award items | Covers requested markets before optional paths. An endpoint probe has no physical-route assertion. |
| Topology/path discovery | selections and directed edges -> PathHypothesis | Adds only evidence-backed directed components and retains requested O -> D dependencies. |
| Constraint/date compiler | request and components -> obligations and envelopes | Carries every supplied constraint, applies typed user requirements and separately identified structural filters, preserves first-component dates, and labels later envelopes exploratory. |
| Budgeted selector/deduper | candidate records -> ordered selected records | Bounds exploration before selection, then dedupes complete executable semantics rather than only an airport pair. |
| Plan invariant validator | records -> typed result | Requires evidence links, deterministic order, policy/snapshot identity, and truthful coverage. It makes no provider or bookability claim. |

Non-negotiable properties:

1. The planner never changes EffectiveRequest or a session ledger, and never recomputes effective
   temporal facts.
2. Every selected airport has an Airport fact reference; group expansion also has membership and
   preference references. Every physical component has a directed-edge fact reference.
3. A decomposition keeps the full requested journey. If O -> H -> D is useful, O -> H remains
   visible even when manual cash.
4. The first actual component, including manual cash first, remains inside the supplied inclusive
   window.
5. No all-cash path, automated cash item, cash price, or cash-flight availability claim exists.
6. endpoint_market items may later accept provider connections. exact_physical_component items add
   `DIRECT_FLIGHT_AVAILABLE` with origin `planner_structure` as a summary prefilter, then carry a
   mandatory future trip-validation obligation: returned segments must match the planned physical
   component and must not add a connection that changes its structure.
7. The planner computes the request digest over canonical complete EffectiveRequest serialization.
   Same computed digest, canonicalization/digest versions, policy version, and snapshot ID/as-of produce byte-equivalent canonical
   output despite equivalent fixture record order.
8. Missing, stale, ambiguous, or unsupported evidence never becomes a guessed airport, passed
   constraint, inventory claim, or booking claim.

## 4. Knowledge snapshot

Use small reviewed structured files behind one immutable KnowledgeSnapshot. A future location or
topology service, vector database, live retrieval, or provider data is outside this stage.

| Record | Minimum fields | Status of the information |
| --- | --- | --- |
| SnapshotMetadata | ID, schema version, as-of, source/license links, verification date, coverage statement | Snapshot-level provenance/freshness |
| GeoEntity | stable ID, kind, canonical label, disambiguators, exact/narrow aliases, sources | Geographic fact |
| Airport | stable ID, IATA, label, country/entity links, IANA timezone, sources | Airport fact |
| LocationAirportRelation | ID, entity, airport, relation kind (`within_geography`, `serves_city`, or equivalent), evidence | Factual relationship |
| DirectedRouteEdge | directed airports, kind, verified/as-of, source, applicability interval or explicit unknown | Topology fact only |
| AirportSelectionPolicy | entity/kind applicability, ordered airport IDs, selection reason, cap | Product preference, never a geographic fact |

Location resolution first matches LocationRef.kind plus a narrow normalized alias to a GeoEntity or
named-airport entity. Narrow normalization is restricted to case, spacing, and approved diacritic
forms; it cannot infer a geographic meaning. More than one match is an ambiguity. A group never
conceals an ambiguous alias. The explicit-IATA case resolves via Airport.iata; if its snapshot record
is absent, the result is evidence_failure rather than an unproven endpoint.

Location-airport relation kinds are explicit:

- serves_city: airports selected as useful for a city search;
- within_geography: airports physically in a requested geography;

`representative_gateway` is not a geographic fact. It is an AirportSelectionPolicy that ranks
airports already supported by a LocationAirportRelation (or an explicitly documented gateway
relation). AirportSelection cites both the factual relation and the policy. Japan's HND/NRT/KIX
list is therefore a product selection, not a claim that those are the only airports in Japan.

For a country destination, an arrival at a selected airport in that country satisfies the requested
geography. The planner does not invent an onward domestic flight.

DirectedRouteEdge is exploratory topology evidence, not schedule or connection proof. An edge whose
date applicability is unknown can be used only with a date_applicability_unknown disclosure. It
does not prove operating dates, seats, valid transfers, ticketing protection, or bookability. A
provider-searchable market is not an edge. Synthetic edge fixtures must carry synthetic: true and
are never operational evidence.

Maintenance is review-and-commit: store source, license, verification, and coverage; validate
referential integrity and canonical ordering offline; issue a new snapshot ID on semantic change;
and compare freshness against the declared snapshot as-of rather than wall-clock time.

### Knowledge availability and required retrieval surface

| Material | Available now | Still required before an operational claim |
| --- | --- | --- |
| Product selection examples | Japan HND/NRT/KIX, NYC JFK/EWR/LGA, and explicit-SFO preservation are settled policy examples. | Evidence-backed entity aliases, airport identities, relations, zones, source licenses, coverage, and freshness rules. |
| Provider capability | Local Seats.aero Cached-Search documentation and its version caveats. | It is not airport geography or physical-route evidence. |
| Route topology | No operational directed-edge catalog. | Reviewed directed edges, source/license, verification/as-of, applicability, and maintenance process. |
| Fixtures | Synthetic fixtures may test deterministic behavior. | Synthetic data may never support an operational airport/group/route claim. |

The first implementation supplies deterministic snapshot interfaces, rather than allowing callers
to inspect files directly:

~~~text
resolve_alias(kind, normalized_alias) -> [GeoEntityMatch]             # stable-ID order
lookup_airport_iata(iata) -> Airport | MissingEvidence
list_location_airport_relations(entity_id) -> [LocationAirportRelation]
get_airport_selection_policy(entity_id, entity_kind) -> AirportSelectionPolicy | None
list_directed_edges(airport_id, direction, limit) -> [DirectedRouteEdge]  # stable-ID order
lookup_directed_edge(origin_airport_id, destination_airport_id) -> DirectedRouteEdge | None
~~~

Each result carries snapshot evidence IDs and a freshness class. Alias resolution returns no match,
one match, or a stable ordered ambiguity; it never fuzzy-matches. Edge retrieval always enforces
its caller-supplied exploration bound before path selection.

## 5. SearchPlan contract

These design-level shapes are implemented by the production planning contracts; they remain
provider-neutral and do not contain provider payloads.

~~~text
PlanningInputEnvelope
  source: {session_id, revision, expected_effective_request_digest?}
  effective_request: EffectiveRequest
  policy_version: str
  snapshot: {snapshot_id, as_of, schema_version}

PlanIdentity
  source: {session_id, revision, computed_effective_request_digest,
           canonicalization_version, digest_algorithm_version}
  policy_version, snapshot_id, snapshot_as_of

SearchPlanningResult =
  Planned {plan}
  | ReducedCoverage {plan, exclusions}
  | Unplannable {issues}
  | EvidenceFailure {issues}

SearchPlan
  identity, location_resolutions, airport_selections, endpoint_probes,
  path_hypotheses, award_search_items, component_search_links,
  payment_patterns, manual_cash_check_templates, constraint_obligations,
  temporal_derivations, decisions, coverage, budget_receipts, issues
~~~

LocationResolution records the LocationRef, upstream field-provenance link, alias used, resolved
entity/airport, evidence IDs, and status. AirportSelection records airport, factual
LocationAirportRelation, and the separate AirportSelectionPolicy decision. That distinguishes explicit SFO from a
selected gateway group.

EndpointProbe records a requested resolved market, selected airport combinations, date envelope,
traveler/cabin requirements, and scope=endpoint_market. AwardSearchItem is atomic and reusable,
with a complete semantic key: origin/destination airport IDs, scope, inclusive envelope/basis,
traveler seat-adequacy obligation, requested cabins, automated award mode, and only approved
filter obligations. A later adapter may batch or encode items but may not alter their meaning.

PathHypothesis records requested journey, one or two directed physical components, topology evidence,
and links to PaymentPattern records. ComponentSearchLink is the many-to-many mapping from award
components to reusable items. ManualCashCheckTemplate identifies a manual component, cabin/traveler
requirements, relevant-award-observation trigger, and unpriced/unverified state. It is not a query.

ConstraintObligation retains its kind, typed operand/operator when available, origin
(`user_requirement` or `planner_structure`), the original supplied string where applicable,
field-provenance link, provenance_granularity, provider-filter support, responsible later stage,
evidence status, and disposition. The planner computes the digest from canonical EffectiveRequest
serialization and rejects an envelope's optional expected digest when it differs. TemporalDerivation
records only planning envelope arithmetic, the effective departure-window identity, component
position, timezone convention, and policy parameters; it never recreates a date expression.

PlanningIssue has a stable code and severity. It distinguishes invalid input; ambiguous/unsupported
location; missing/corrupt/stale evidence; unsupported constraint; required-scope budget exhaustion;
optional expansion omitted; and date applicability unknown. Deferred current free-text constraints
set provenance_granularity=`field`; they must never be represented as item-grounded evidence.

## 6. Constraint, temporal, budget, and outcome policy

### Constraint handling

The planner must not introduce a general constraint-parsing model. The executable registry is the
versioned Cached-Search filter enum above, anchored in the local provider reference and frozen with
source metadata/hashes before implementation. This stage records provider-neutral filter
obligations, not provider payload keys. Current arbitrary `hard_constraints` never populate a
user filter by alias or model interpretation; only a later typed upstream requirement can do so.
The planner may add the explicit physical-component structural prefilter defined above, with origin
`planner_structure`; it is never presented as a user requirement.

| Input / category | Planning action | Future responsible stage | Missing evidence/result |
| --- | --- | --- | --- |
| Origin, destination, travelers, outbound window | Product-admission requirement | Planner | unplannable |
| Resolved origin/destination airport lists | Cached-Search executability requirement | Provider mapping | unplannable |
| Traveler count | Carry as a minimum-seat result-validation obligation; no Cached Search filter exists | Result/trip validation | not_verified when seat evidence is absent or unreliable |
| Cabin enum | When supplied, compile `CABIN_AVAILABLE_IN`; never silently downgrade | Provider mapping then result validation | Explicit unsupported/deferred obligation |
| Exact physical component | Add `DIRECT_FLIGHT_AVAILABLE` with origin `planner_structure`, plus segment-structure validation | Provider mapping then trip validation | A matching summary is not proof of nonstop physical structure |
| Award mode | Create award items | Provider execution/result validation | unplannable only if no award plan is representable |
| Cash alongside award | Conditional manual template only | Human/manual cash check after award observation | Remains unpriced/unverified |
| Repositioning flag | Record input plus enabled_not_consumed_v1 policy receipt | None in v1 | Never erased or used as a gate |
| Future typed provider-filter requirement | Attach its enum obligation | Provider mapping and result validation | Filter does not prove itinerary compliance |
| Future typed result or journey requirement | Preserve validation obligation | Result or candidate validation | not_verified, never passed |
| Future typed manual-cash requirement | Preserve on manual template | Manual cash check | not_verified, never passed |
| Other supplied hard constraint | Preserve exact text plus available field provenance as deferred_after_search | Result or assembled-journey validation | not_verified when no later evidence exists; never silently discarded |

Current field provenance is field-level, not individual-hard-constraint evidence. A future typed,
item-grounded constraint contract is a marked later upstream improvement, not an incremental
planner parser. Until then, deferred obligations retain their original text, available provenance,
responsible stage, and explicit inability to verify.

`DIRECT_FLIGHT_AVAILABLE` filters an availability summary; it does not prove an explicit physical
component is nonstop. `CARRIER_INVOLVEMENT_MATCH` carries the provider's documented "involving"
text and `match_semantics=provider_undocumented`; it does not mean all segments or operating-carrier
identity. `CABIN_AVAILABLE_IN` and
`MIN_REPORTED_CABIN_DISTANCE_PERCENT` likewise require trip-level validation when trip data exists.
Some mileage programs do not expose reliable seat count or trip data, so unknown evidence cannot
be treated as zero seats or as a passed traveler/cabin/topology check
(.provider-docs/seats-aero/concepts-copy.md:11-16,61-100).

### Date policy

The departure interval remains inclusive. The implemented first-component convention attaches its
numeric date to the selected first-origin airport timezone, which must come from the snapshot.
RequestContext.timezone remains upstream interpretation provenance only. Later components receive
the numeric start - 1 / end + 2 local-origin envelope. This is deliberately conservative for
overnight/date-line research and explicitly does not validate a connection or schedule.

For manual_cash/award, manual cash is the first actual component and uses the original window.
For award/manual_cash, the award component is first. The two-component planning limit does not
restrict segment count in a future endpoint-market provider result.

### Provisional limits

| Limit | Value | Excess behavior |
| --- | ---: | --- |
| Airports per automatic group | 3 default, 5 hard max | Selection-policy/configuration failure if a policy names more than the cap; no selected airport is silently dropped |
| Airport pairs per resolved requested market | 25 | unplannable; no silent removal |
| Intermediate candidates examined per pair | 20 | Stop optional expansion and record receipt |
| Selected explicit path hypotheses | 12 total | Omit optional paths only, with reduced coverage |
| Physical components per path | 2 | Reject that hypothesis |
| Intermediates per path | 1 | Reject that hypothesis |
| Unique award search items | 40 | Required endpoint coverage: unplannable; optional paths: reduced coverage |
| Input window length | 31 inclusive days (provisional owner policy) | unplannable until a later policy approves more |
| Date-expanded work | 1,400 inclusive item-days | Same required/optional rule; covers 40 later-component items at 34 days each |

Order: required endpoint coverage; product preference rank; evidence-freshness class; stable entity,
airport, and edge IDs; canonical item ID. The semantic dedupe key includes component scope,
airports, exact envelope/basis, travelers, cabins, award mode, and supported obligations.

An automatic-group cap is selection policy: members ranked below the selected cap are not silently
discarded required scope. Planned means all required selected geographic coverage is retained.
ReducedCoverage means only optional topology/path expansion was omitted and each omission is listed.
Unplannable means a required input is invalid, a location is definitively outside declared coverage,
an explicitly requested origin/destination alternative is ambiguous/unresolved, or required selected
scope exceeds budget. EvidenceFailure means required snapshot evidence is missing, corrupt,
inconsistent, or stale under declared policy. Missing optional topology yields a valid endpoint plan
with ReducedCoverage. Current free-text constraints are never construction-critical because the
planner does not interpret them. None represents found inventory or a bookable itinerary.

## 7. Offline evaluation

Add a small disclosed golden set under a future evals/search_planning/ plus focused component and
property tests. It runs on reviewed fixtures only, with no model, provider, network, or credentials.

| Case family | Required assertion |
| --- | --- |
| Explicit airport and Japan | SFO remains singleton; Japan selects exactly HND/NRT/KIX with separate membership/preference evidence |
| New York City | NYC selects JFK/EWR/LGA without falsely claiming geographic containment |
| Resolver failure | Ambiguous alias, unsupported kind, missing airport, and stale snapshot are typed outcomes |
| Country destination | In-country airport satisfies the country; no domestic onward leg invented |
| Directed edge | A synthetic A -> H -> D path works only in that direction; reversed/missing edge is not inferred |
| Repositioning | true, false, and null are retained but do not gate v1 research |
| Constraints | Recognized obligations route correctly; unrecognized text is retained and fail-closed |
| Dates | Inclusive end, later overnight envelope, and cash-first first-departure rule hold |
| Payment patterns | Shared award items support several patterns; no all-cash or inventory/bookability claim |
| Budgets | Required endpoint coverage cannot silently shrink; optional topology can be reduced with a receipt |
| Determinism | Reordered equivalent snapshot records yield identical canonical output and complete dedupe |
| Immutability | Before/after effective request dumps match; plan links provenance without parsing raw text |

Hard properties: all selected facts carry evidence; no provider call/import at the planner boundary;
no return/duration state; no raw-text semantic work; no session mutation; no unknown constraint
marked passed; no cash price or availability; and no path claimed feasible/protected/bookable.

## 8. Original incremental implementation plan (completed for the fixture boundary)

### 1. Grounded endpoints and airport groups

Behavior: resolve candidates and select exact airport groups, with no topology path or provider
request. The originally expected modules, reviewed fixture records, and focused tests are now
implemented for the declared seed boundary.

Acceptance: SFO is preserved; Japan/NYC groups are exact; ambiguous/unsupported/missing/stale
knowledge is typed; record order cannot affect output; source request is unchanged; no provider
import/call. Non-goals: routes, payloads, cash tasks, and constraint parsing. Main risk tested:
whether model-produced resolver candidates become grounded airports reproducibly.

### 2. Endpoint probes, admission, and obligations

Behavior: provider-neutral endpoint-market award items plus a complete obligation ledger and typed
outcomes. The reviewed versioned Cached-Search capability record and evaluator are now implemented
for the declared seed boundary.

Acceptance: every required endpoint pair is covered or explicitly fails; supplied cabins compile
only the documented cabin filter; travelers carry as result validation rather than a provider
parameter; non-required unknowns remain visible; documented filter enums become obligations only
from typed input; other hard text is deferred with a named later owner; mixed mode produces no cash
item. Non-goals: routes, later envelopes, payloads, and result validation. Main risk: truthful
handling of optional upstream fields and provider capability limits.

### 3. Directed paths, dates, budgets, and dedupe

Behavior: evidence-backed two-component paths, component envelopes, bounded exploration, canonical
selection, and reusable linked award items. Reviewed synthetic directed edges and the approved date
convention are implemented for fixture qualification; operational evidence remains outside scope.

Acceptance: directionality, country no-onward policy, no ground/airport change, first-departure
bound, budget outcomes, and record-order determinism pass. Non-goal: schedule/connection feasibility.
Main risk: useful topology without hidden itinerary assumptions.

### 4. Payment annotations and dormant manual cash templates

Behavior: mixed-mode paths gain reusable award/award and hybrid annotations plus conditional manual
templates. Dependency: increment 3 and an interface-only award-observation contract.

Acceptance: one path is reused; cash-first preserves its first-departure rule; cash is unpriced and
unverified; all-cash and automated cash execution are structurally absent. Non-goal: cash provider,
quote, or task executor. Main risk: retaining hybrid intent honestly at the award-only boundary.

### 5. Stage evaluation and execution handoff

Behavior: deterministic end-to-end corpus, invariants, snapshot/policy identity checks, canonical
serialization, and a bounded provider-execution handoff. Dependencies: prior increments only.

Acceptance: the evaluation matrix passes and one fixture snapshot/policy identity reproduces its
canonical plan. Non-goal: provider adapter or response parser. Main risk: whether planning intent
is inspectable and safe to hand to a separate stage.

## 9. What remains after this design

This document began as a design record. The five increments are now implemented and qualified by
the fixture-only golden gate in `evals/search_planning/cases_v1.json`; the following table remains
the durable boundary between that narrow declared coverage and the work needed for broader product
usefulness. It does not turn fixture evidence into an operational knowledge or provider claim.

| Workstream | What must be done | Completion boundary | Evidence of completion |
| --- | --- | --- | --- |
| Planner implementation | **Done for the v1 fixture boundary.** The immutable envelope, typed contracts/outcomes, admission checks, grounding, group selection, endpoint probes, path expansion, temporal envelopes, constraint obligations, budgets, canonical dedupe, plan invariants, and stale-plan handoff are implemented. | Fixture-qualified search-planning stage; not provider execution. | Focused component tests plus the ten-case stage golden set and canonical-output checks pass offline. |
| Initial reviewed knowledge snapshot | **Done only as a declared offline seed fixture.** It covers the initial Japan/NYC/SFO examples and has no operational topology. Supply reviewed records for every geography/airport/group/topology path claimed by a real release. | Required for every claimed operational market. No fact may be substituted by model memory or a synthetic fixture. | Snapshot validation, evidence links, and declared coverage report pass. |
| Knowledge-base expansion | Grow the initial snapshot into additional city, country, region, airport-group, and directed-route coverage as product markets expand. Each addition needs the same factual evidence, product preference, version, and freshness treatment. | Required for broad geographic usefulness; **not** a requirement to create a global airport/route database before the narrow v1 stage is done. Requests outside declared coverage return a typed unsupported/reduced-coverage outcome. | Coverage manifest and market-specific golden cases show what is supported and what is intentionally not. |
| Structured upstream constraints | Replace or supplement `hard_constraints: tuple[str, ...]` with typed, value-validated, item-provenanced requirement records. Map only the supported subset to the five Cached-Search filter kinds; retain every unsupported type as a named later validation obligation. | Required before claiming that user hard requirements actively narrow provider searches. It is not required for the narrow planner to preserve current free text as deferred obligations. | Upstream extraction/projection/reduction tests prove type, value, provenance, correction, and deferral behavior; planning tests prove exact compilation. |
| Capability record | Materialize `seats_aero.cached_search.v1` as reviewed versioned data: provider operation, required dimensions, supported filters, source metadata/hashes, source/program capability variation, and known ambiguities. | Required before implementation maps a planning obligation to a provider-specific filter. | Deterministic snapshot-validation tests and source/version receipts. |
| Provider-semantic acceptance | Verify the capability ambiguities at the adapter/execution boundary: date endpoint behavior, cabin value and multi-cabin semantics, carrier any/all/operating meaning, and source-specific seat/trip evidence. | Not required to generate a provider-neutral plan. Required before execution claims those provider semantics or treats filtered summaries as validated itineraries. | Controlled adapter tests or renewed authoritative provider evidence, version-pinned to the capability record. |
| Caller integration and stale-plan handling | Have the caller supply session ID, revision, and request digest; reject execution of a plan whose source revision is stale. | Required for an integrated planning workflow. The planner never owns session revision authority. | Integration tests demonstrate no source mutation and stale-plan rejection by the caller. |
| Offline evaluation and release evidence | Build the golden corpus and invariants for initial groups, explicit airports, ambiguous/unsupported locations, knowledge failures, directionality, dates, budgets, deferred constraints, payment patterns, and deterministic ordering. | Required to call the implemented planning stage qualified for its declared coverage. | Reproducible offline evaluation artifact with fixture/snapshot/policy identities and results. |

### Qualification coverage boundary

The fixture-grade golden corpus is the end-to-end gate. Its checked-in executable coverage matrix
maps every required coverage tag to named case IDs and pins the canonical default knowledge,
capability (including version), and policy records. It proves the declared seed behavior, not an
operational market or provider result.

Focused unit-only coverage deliberately handles internal adversarial invariants that do not need a
separate end-to-end fixture: malformed knowledge/capability/policy pins, local capability-source
path traversal and byte-hash tampering, forged handoff status/executable receipts, and individual
contract edge cases. Unit coverage complements the golden matrix; neither is mislabeled as live
provider validation.

### Direct answer: the two large follow-on investments

**Knowledge base:** this design deliberately begins with a small reviewed snapshot. A functional
first release needs a complete snapshot for only its declared initial coverage. Broad usefulness
then requires an ongoing, curated expansion of geography, airport groups, airport metadata, and
directed route topology. The planner must make its coverage boundary visible rather than pretending
the initial snapshot is comprehensive.

**Previous-stage constraint cleanup:** yes, this is a real follow-on requirement. Current
free-text constraints are sufficient only for preservation and deferred validation. They are not a
safe input to provider filters. Typed constraints—kind, typed operand, provenance, and unsupported
handling—must be added upstream before the product can claim that requirements such as direct-only,
specific carrier, redemption program, or mixed-cabin threshold influence the generated search.
That upstream change is separately scoped so the planner does not quietly become a second intent
parser.

### Work explicitly outside search planning

Provider HTTP clients/payloads, live calls, response normalization, itinerary validation, ranking,
recommendation generation, booking, and automated cash search are subsequent stages. The planning
stage may prepare their obligations and handoff contracts, but does not complete them.

## 10. Decision log and remaining implementation evidence

| Item | Status | Reason |
| --- | --- | --- |
| Deterministic compiler and reviewed snapshot; no runtime LLM | Implemented for declared fixture coverage | Exact policy work does not acquire an ungrounded model authority |
| Curated Japan/NYC groups and explicit-airport preservation | Settled | Supplied product decision, with fact/preference separation |
| Independent alternatives and Cartesian endpoint coverage | Implemented for fixture-qualified boundary | Upstream has no pairing/preference contract; the planner uses stable Cartesian coverage |
| Cached-Search filter enum; free-text constraints deferred | Settled | Local capability review supports five kinds; current free text remains unparsed until upstream types it |
| Manual cash as dormant annotation only | Implemented for fixture-qualified boundary | Compatible with ADR 0016 only without cash execution/result claims |
| First-origin-local dates and later -1/+2 envelope | Settled | Owner approved the explicit planning convention |

The prior three owner decisions are closed. Product admission retains its one-way origin,
destination, traveler, date-window, award, and no-conflict boundary; Cached-Search executability
is a separate resolved-airport check. Other supplied constraints are deferred post-search
obligations unless a future typed user requirement maps to the fixed filter enum, and
first-actual-origin-local dates use the stated later-component envelope.

The reviewed capability record and its source-version/content-hash checks are now materialized for
the fixture-qualified planner. The later provider-execution stage must add adapter acceptance checks
for the documented ambiguities. The local cached page remains a versioned provisional reference,
not evidence that its semantics are current at an uncontrolled later date.

### Owner sequencing update — 2026-09-13

Before provider execution, the active next cut is to expand the small reviewed knowledge snapshot
into an operational snapshot for a deliberately declared initial coverage. That work must add
evidence-backed, versioned records for geographic entities and narrow aliases, airport identity and
timezones, factual location-to-airport relations, separate airport-selection preferences, and
directed physical topology with source, freshness, and date-applicability receipts. It also needs a
coverage manifest and market-specific offline cases that make unsupported or reduced coverage
visible. It does **not** require a global airport/route database, provider HTTP work, live provider
calls, provider-result handling, or an upstream free-text constraint parser. Typed upstream
constraints remain a separately scoped prerequisite before hard requirements can be represented as
provider filters.

The later implementation added planner code, fixture data, and offline tests; it did not add a
provider client, credential, live provider call, response parser, ranking, or automated cash search.
