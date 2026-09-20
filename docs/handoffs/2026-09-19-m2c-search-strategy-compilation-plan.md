# Milestone 2C search-strategy compilation plan

Date: 2026-09-19

Status: Implementation-ready proposal for owner review. Milestone 2C planning is open. The owner
delegated the numerical compiler-limit decision recorded in B7 and explicitly chose an in-place
replacement rather than V1 compatibility; the remaining policy choices,
runtime implementation, and live model/provider calls are not authorized by this document.

Authority: This handoff translates the owner-requested direction, the advisory architecture review,
and current repository evidence into proposed contracts and implementation cuts. Where this document
changes approved behavior, the change is explicitly marked as requiring owner approval. Historical
planner, Milestone 2A, and Milestone 2B evidence remains preserved as historical evidence, but the
current planner contract and fixtures may be replaced intentionally during 2C.

Batching follow-up, 2026-09-19: the owner challenged pair-at-a-time execution using the saved Cached
Search list parameters, then delegated the compiler-limit decision to the parent/architect. Two independent
architect recommendations converged on the revised limits in B7. [Section G](#g-cached-search-batching-reconsideration)
specifies the batch boundary and rationale. This does not implement batching, establish a
provider limit, or authorize live calls.

## A. Scope and completion boundary

### Objective

Milestone 2C should add one deterministic compiler:

```text
frozen EffectiveRequest
+ reviewed/supplied selected endpoint records
+ replay-bound Milestone 2B discovery record
+ versioned compilation policy
    -> CompiledSearchPlan
```

For the same validated values and policies, it must produce byte-stable canonical output while making
zero additional LLM or provider calls. The output must contain:

- complete mandatory award-query coverage for every selected origin/destination pair, when the input
  fits the admitted mandatory limits;
- a finite first-slice vocabulary of supplemental access and hub hypotheses;
- a shared, semantically deduplicated logical-query collection;
- many-to-many links from strategies to their queries and exact 2B source relationships;
- positioning, separate-ticket, temporal, result-validation, and upstream-constraint obligations;
- an accounting of every accepted 2B relationship as admitted, shared, omitted, suppressed, or
  unsupported; and
- identities and receipts sufficient to detect stale, mismatched, or corrupt evidence.

This advances Milestone 2 from selected endpoints and unverified gateway proposals to inspectable,
bounded search work. It does not:

- adopt diagnostic-only Milestone 2A or make its model selections a default;
- reopen or alter the owner-closed Milestone 2B prompt, schema, validation, or policy;
- convert a model proposal into route, schedule, protected-connection, availability, feasibility, or
  bookability evidence;
- call a provider, batch or page provider requests, normalize results, assemble cross-query journeys,
  rank itineraries, or claim product/provider qualification;
- reinterpret request language, create new airport facts, silently trim selected endpoints, or add a
  second endpoint-selection subsystem; or
- reintroduce round-trip, return-duration, or cash search into the frozen ADR 0016 boundary.

### Completion boundary

2C is complete when offline evidence proves all admitted selected endpoint pairs are present, every
accepted 2B relationship has one truthful disposition, logical queries are unique under the declared
semantic key, complete supplemental bundles are admitted atomically within all budgets, bindings and
obligations survive serialization, and corrupt evidence cannot yield a success-shaped plan. The gate
must include local replay of available original high-fanout 2B records plus portable checked-in
synthetic cases that exercise access-referenced hub scopes and long windows absent from the final live
diagnostic. Missing private/local prerequisites must be reported, never silently skipped or recreated
through a live call.

Closing 2C would qualify only this deterministic compilation boundary for declared fixtures and
policies. It would not satisfy the independent M2A adoption gate, the upstream broad behavioral gate,
provider capability/result-validation gate, or usefulness comparison in `DEFERRED.md`.

### Four objects that must remain distinct

| Object | 2C meaning | Explicit non-claim |
| --- | --- | --- |
| `SupplementalStrategy` | A bounded reason to search, with source relationships and conditions | Not a route or itinerary |
| `LogicalAwardQuery` | Complete provider-neutral semantics for one reusable airport-pair search | Not a provider call or batch |
| Provider request | A future adapter call/page that may cover one or more logical queries | Not emitted by 2C |
| Observed itinerary | Future provider evidence normalized and checked against the request | Never inferred from a strategy or query |

A baseline O -> D logical query allows whatever connections the later provider query semantics allow;
it is not a nonstop claim. Likewise, O -> H and H -> D are independently searched itinerary
boundaries. Even when both return observations, they remain research leads until a separately opened
assembler validates chronology, continuity, seats, constraints, and separate-ticket implications.

## B. Concrete contracts and worked examples

### B1. Integration input and outcome

Replace the current top-level `SearchPlan` / `plan_searches` boundary with one compilation boundary:

```text
SearchPlanningInput
  envelope: PlanningInputEnvelope
  endpoint_source: DirectGroundingSource |
                   ReviewedEndpointMappingSource |
                   M2ASelectionRecordSource
  upstream_selection_id_bindings: tuple[SelectionRecordIdBinding, ...]
  gateway_discovery_result: GatewayDiscoveryResult
  capability: CachedSearchCapability

SearchPlanningResult
  outcome: PLANNED | REDUCED_COVERAGE |
           UNPLANNABLE | EVIDENCE_FAILURE
  plan: CompiledSearchPlan | None
  issues: tuple[StrategyCompilationIssue, ...]
  budget_receipts: tuple[CompilationBudgetReceipt, ...]
```

`PLANNED` means mandatory coverage is complete and every policy-eligible accepted relationship was
compiled, or discovery validly skipped/returned empty. Explicit-refusal suppression is a policy
disposition, not by itself reduced coverage. Unknown positioning likewise remains conditional without
causing reduction. `REDUCED_COVERAGE` is still a valid plan with complete mandatory coverage and
explicit supplemental limitations. Result-level budget receipts remain present when no plan exists,
so `UNPLANNABLE` can state limit, observed value, unit, and mandatory scope without constructing a
partial plan. `UNPLANNABLE` covers a
valid input that cannot preserve required coverage, including the input window, endpoint-pair, unique
query, or query-date-day budget being smaller than the mandatory baseline. `EVIDENCE_FAILURE` covers
a corrupt, stale, mismatched, unreplayable, or contract-invalid input and must not carry a plan.

`StrategyCompilationIssue` has `code`, `stage`, `severity`, `message`, and optional source
relationship/record references. Reuse existing admission/grounding issue codes and distinctions;
new binding codes are `gateway_record_missing`, `unsupported_knowledge_source`,
`endpoint_selection_binding_mismatch`, `gateway_input_binding_mismatch`, `gateway_replay_failed`,
and `compiler_contract_failure`. Budget failures use the specific failed unit plus observed/limit
receipts. Finite supplemental reasons are `positioning_explicitly_refused`,
`supplemental_timezone_unavailable`, `supplemental_date_overflow`,
`relationship_budget_exhausted`, `unique_query_budget_exhausted`, and `query_date_budget_exhausted`.
Unexpected compiler faults must never become a valid optional-discovery failure.

The compiler always requires a `GatewayDiscoveryResult`, including for skip, empty, and authentic failure
outcomes. `None` or a missing record is `EVIDENCE_FAILURE`; the compiler must never fabricate a
successful-empty discovery record to enable mandatory-only output.

The compiler consumes immutable endpoint sources, not caller-asserted selected-airport arrays or a
self-described binding:

```text
DirectGroundingSource
  source_kind: Literal["direct_grounding"]

ReviewedEndpointMappingRecord
  record_version: Literal["reviewed-endpoint-mapping-v1"]
  role: origin | destination
  request_location: LocationRef
  resolved_entity_id: str
  selected_airports: tuple[SelectedAirport, ...]
  catalog_receipt: CatalogKnowledgeReceipt
  review_label: str
  review_source_ref: str
  record_digest: sha256(canonical record excluding record_digest)

ReviewedEndpointMappingSource
  source_kind: Literal["reviewed_mapping"]
  records: tuple[ReviewedEndpointMappingRecord, ...]

M2ASelectionRecordSource
  source_kind: Literal["m2a_replay"]
  selection_records: tuple[AirportSelectionRecord, ...]

SelectionRecordIdBinding
  upstream_record_id: str
  record_digest: sha256
```

`DirectGroundingSource` supplies no overrides: the existing grounder regenerates catalog-groundable
explicit/named-airport selections. The current M1 catalog has no reviewed geographic groups; a city
or country needs supplied reviewed mappings or M2A records. Old JSON fixture groups do not become
compiler-compatible catalog evidence. A reviewed mapping is an
immutable human-supplied selection record for an experiment; it must match the request location,
grounded canonical entity, role, selected airport facts/source IDs, and exact catalog receipt. It does
not create new airport or relation facts. An M2A source carries the actual records, which are replayed
with the supplied cap/distance policies through the existing `_selection_record_overrides` behavior;
it remains diagnostic unless separately adopted.

Every request origin/destination location must be accounted for exactly once by direct grounding or a
role/entity-matching override, and every supplied reviewed/M2A record must be consumed exactly once.
Reject missing, duplicate, wrong-role, or unused records. `SelectionRecordIdBinding` exists only to
match nonempty 2B upstream IDs to authoritative record digests; it cannot substitute for the record.

`EndpointSelectionBinding` is recomputed by the compiler and stored on the output; it is never trusted
as an input claim:

```text
EndpointSelectionBinding
  source_kind: direct_grounding | reviewed_mapping | m2a_replay
  selected_origin_ids: tuple[str, ...]
  selected_destination_ids: tuple[str, ...]
  record_digests: tuple[sha256, ...]
  cap_policy_version/digest: str | None
  distance_policy_version/digest: str | None
  catalog_release_identity: CatalogKnowledgeReceipt
  review_status: deterministic_approved_policy | reviewed_experiment | m2a_diagnostic
```

For an M2A input, compute it from the existing replay receipt only after replay succeeds. For reviewed
records, recompute every digest and catalog binding. The compiler may accept any source above, but its identity
and coverage text must state which one it actually validated.

The public deterministic entry point is:

```python
def plan_searches(
    planning_input: SearchPlanningInput,
    *,
    repository: StrategyCompilationRepository,
    policy: PlanningPolicy,
    market_policy: PlanningMarketPolicy,
    selection_cap_policy: AirportSelectionCapPolicy | None = None,
    selection_distance_policy: CityAirportDistanceConsistency | None = None,
) -> SearchPlanningResult:
    ...
```

The two selection policies are required and consumed only for `M2ASelectionRecordSource`; reject them
as missing for M2A or extraneous for other source kinds. The function reparses all frozen inputs,
validates endpoint source records, builds the mandatory baseline, performs all external bindings and
2B replay, then compiles. It proposes no endpoints or gateways and exposes no model/provider client.

`StrategyCompilationRepository` combines `PlanningKnowledgeRepository` and
`GatewayDiscoveryCatalogRepository`, narrows `knowledge_receipt` to `CatalogKnowledgeReceipt`, and
declares `airport(airport_id) -> Airport | None` to resolve the inherited protocol return types.
Use the existing catalog implementation or a genuinely catalog-compatible offline test repository.
A legacy `KnowledgeReceipt` produces `unsupported_knowledge_source` / `EVIDENCE_FAILURE` before
gateway replay; never relabel a JSON seed receipt as a catalog receipt.

### B2. Compiled plan and identity

Replace the existing top-level plan with:

```text
CompiledSearchPlan
  identity: CompiledPlanIdentity
  location_resolutions: tuple[ResolvedLocation, ...]
  endpoint_selections: tuple[EndpointSelectionProjection, ...]
  endpoint_selection_binding: EndpointSelectionBinding
  airport_directory: tuple[PlanningAirportIdentity, ...]
  mandatory_endpoint_probes: tuple[EndpointProbe, ...]
  mandatory_query_uses: tuple[MandatoryQueryUse, ...]
  supplemental_strategies: tuple[SupplementalStrategy, ...]
  logical_queries: tuple[LogicalAwardQuery, ...]
  strategy_query_uses: tuple[StrategyQueryUse, ...]
  support_alternatives: tuple[StrategySupportAlternative, ...]
  constraint_obligations: tuple[IdentifiedDeferredConstraint, ...]
  temporal_derivations: tuple[SupplementalDateDerivation, ...]
  positioning_dependencies: tuple[PositioningDependency, ...]
  positioning_receipts: tuple[PositioningPolicyReceipt, ...]
  relationship_dispositions: tuple[RelationshipDisposition, ...]
  discovery_receipt: GatewayDiscoveryCompilationReceipt
  coverage: CompilationCoverage
  budget_receipts: tuple[CompilationBudgetReceipt, ...]
  issues: tuple[StrategyCompilationIssue, ...]
  plan_digest: sha256
```

The current `SearchPlan` has invariants tying endpoint probes to `AwardSearchItem`, physical
components to route-evidenced `ExplicitPathHypothesis`, six fixed budget receipt kinds, and every
endpoint pair to a topology-exploration receipt. It also records `repositioning_allowed` as ignored.
Those meanings do not fit 2C. Replace that active artifact rather than wrapping it, embedding it, or
maintaining a second public entry point. Preserve useful grounding and endpoint atomics, but remove
obsolete route-expansion output and update in-repository callers, fixtures, and tests deliberately.

`CompiledPlanIdentity` must bind:

- source session ID, revision, computed `EffectiveRequest` digest, canonicalization version, and
  digest-algorithm version;
- compiler contract version and the current `PlanningPolicy` version/digest;
- Cached Search capability ID/version/content digest and source receipts;
- complete catalog release receipt;
- endpoint selection source kind, ordered selected-airport identities, endpoint record digests, and
  cap/distance policy identities when present;
- `GatewayDiscoveryResult.result_digest` and `.input_digest`;
- 2B market-policy version/digest and generator configuration/invocation identity already preserved
  by the replayed record; and
- a contract feature tag stating that route-topology expansion is absent from this compiler version.

The plan digest is the canonical digest of the complete plan excluding only `plan_digest` itself.
IDs below are content-derived from canonical semantic payloads, never list position alone.

All new hashes use SHA-256 over UTF-8 canonical JSON (`sort_keys=True`, compact separators,
`ensure_ascii=False`, no nonfinite numbers), ISO dates, enum values, and an explicit domain/version
tag. Multi-argument hash notation means a canonical JSON array, not concatenated strings.
`CompiledPlanIdentity.compilation_binding_digest` hashes its complete input/policy binding fields
excluding that digest itself. The query key includes `logical-query-semantics-v1`. Plan construction
must not add a current timestamp. Performance measurements belong in the evaluation report outside
the canonical plan. Serialize query/strategy/use/dependency/derivation collections by their IDs,
dispositions by relationship ID, and budget receipts by budget kind. Preserve meaningful source
array ordering inside bound source records. Store `allocation_sequence` on visited dispositions so
decision-time marginal costs remain auditable despite canonical output sorting.

The replacement contract uses one neutral endpoint projection and extends the active selection enum
with an explicit reviewed-mapping value rather than mislabeling human-reviewed selections:

```text
EndpointSelectionProjection
  role: origin | destination
  resolution: ResolvedLocation
  airports: tuple[SelectedAirport, ...]
  source_kind: direct_grounding | reviewed_mapping | m2a_replay
  source_record_digest: sha256 | None
  selection_kind: AirportSelectionKind
  freshness: FreshnessClass
  field_provenance: FieldProvenance | None
```

Reviewed mappings require a source record digest and `selection_kind=REVIEWED_MAPPING`; they establish
a reviewed experimental choice, never a catalog serving relation. Direct and M2A projections preserve
their actual selection kind. Direct grounding has no record digest; M2A's supplied geographic
selections require `MODEL_PROPOSED` and their record digest, while direct airport locations in that
same request retain their direct projections. All projections are nonempty and correspond to one
canonical request location/role. Reviewed mappings must validate entity identity, airport identity
and source IDs, freshness, and their own digest; any supplied relation/policy evidence must reproduce
from the catalog, never be invented. Preserve meaningful selection order. Update all in-repository
callers and fixtures to the replacement enum; no compatibility adapter is required.

`MandatoryQueryUse` is exactly `{probe_id, query_id, role="mandatory_endpoint"}` and enforces one use
for each mandatory probe. `IdentifiedDeferredConstraint` wraps the existing
`DeferredConstraintObligation` as `{obligation_id, obligation, applies_to_query_ids}`; it preserves
the original text, field provenance, field-level granularity, unverified evidence status, and later
validation owner. `StrategySupportAlternative` is a typed per-original-pair record:

```text
support_id
strategy_id
original_origin_airport_fact_id
original_destination_airport_fact_id
query_use_ids
positioning_dependency_ids
separate_ticket_tolerance: Literal["unknown"]
result_status: Literal["research_only_pending_result_validation"]
```

These records prevent a multi-anchor strategy from collapsing several alternative original endpoint
pairs into one conjunctive dependency.

`support_id = hash("support-v1", strategy_id, original_origin_airport_fact_id,
original_destination_airport_fact_id)`. Every support alternative links to all query uses of its
strategy and only its own positioning dependencies. Separate-ticket tolerance is always unknown
for supplemental strategies in this slice: no supported typed input supplies it. Positioning true,
ordinary connecting results, and free text cannot change that state.

`PositioningDependency` has `dependency_id`, `support_id`, `source_access_relationship_id`,
`side=origin|destination`, `from_airport_fact_id`, `to_airport_fact_id`,
`requested_permission: bool | None`, `field_provenance: FieldProvenance | None`,
`transport_mode="unknown"`, `payment_mode="unknown"`, and `feasibility="not_verified"`.
Its ID hashes its support ID, side, endpoint IDs, and source access relationship ID. A hub dependency
references the accepted source access relationship for that original pair even if its standalone
strategy was omitted. `PositioningPolicyReceipt` links the relationship ID and relevant dependency
descriptions to the original permission and `not_required|allowed_research|conditional_research|
suppressed_explicit_refusal`. Suppressed work retains its dependency description in its disposition
receipt, without creating an admitted strategy, query use, or dangling support link.

### B3. Supplemental strategy vocabulary

The first compiler version has exactly three strategy types:

```text
ORIGIN_ACCESS       alternate origin gateway G -> selected destination D
DESTINATION_ACCESS  selected origin O -> alternate destination gateway A
SCOPED_HUB          typed origin-side ref X -> hub H, plus H -> typed destination-side ref Y
```

Do not compile standalone G -> A from independently accepted origin- and destination-access
relationships. A hub scope may explicitly name G and/or A, which permits G -> H and H -> A within
that scope. This limited vocabulary is a versioned scope choice, not a judgment that later
composition is impossible.

Proposed `SupplementalStrategy` fields:

```text
relationship_id: sha256(relationship-identity-version + exact source coordinate)
strategy_id: "supplemental:" + sha256(relationship_id + compiler-policy-digest)
strategy_type: origin_access | destination_access | scoped_hub
phase: supplemental
eligibility: eligible | conditional_permission
source_candidate: {gateway_result_digest, pool, candidate_index, airport_iata, airport_fact_id}
source_relationship: exact RelationshipIdentity
source_scope: {scope_index, typed_origin_ref?, typed_destination_ref?}
supported_original_endpoint_pairs: tuple[{origin_airport_id, destination_airport_id}, ...]
allocation_pair_lanes: tuple[{origin_airport_id, destination_airport_id}, ...]
reason: str
material_uncertainty: str | None
market_comparison: GatewayMarketComparison
query_roles: tuple[first_component | later_component | access_main, ...]
deferred_constraint_ids: tuple[str, ...]
support_alternative_ids: tuple[str, ...]
required_validations: tuple[SupplementalValidationObligation, ...]
```

`reason`, source order, and model confidence-like language are provenance only. The compiler must not
parse or use them as usefulness scores.

`SupplementalValidationObligation` is `{kind, responsible_stage, disposition="not_verified"}`.
Kinds are `original_departure_compliance`, `positioning_feasibility`,
`separate_ticket_permission`, and `complete_journey_validation`. All supplemental strategies retain
original-departure and complete-journey obligations; access-dependent strategies additionally retain
positioning feasibility; hubs and access strategies retain separate-ticket permission as unknown.
Responsibility is `future_result_or_journey_validation` for factual checks and `owner_review` for
permission. These are unresolved checks, not an execution graph. Suppressed relationships create only
disposition/permission receipts, never a `SupplementalStrategy` marked admitted-but-incompatible.

Relationship identities and bundles are:

- Origin access: one bundle per accepted `(candidate_index, G, supported original O,
  applicable original D)` relationship. It uses one G -> D query and creates an O -> G pre-departure
  positioning obligation.
- Destination access: one bundle per accepted `(candidate_index, A, applicable original O,
  supported original D)` relationship. It uses one O -> A query and creates an A -> D onward
  positioning obligation.
- Scoped hub: one bundle for each accepted hub candidate, accepted scope index, typed origin-reference,
  and typed destination-reference pair. Its two queries are `origin_ref.airport -> H` and
  `H -> destination_ref.airport`. The relationship identity retains both reference kinds and IATA
  codes, not just their expanded originals.

Recover original `candidate_index` and `scope_index` from the accepted candidate/scope decisions, not
from filtered accepted-list positions. Use a discriminated `RelationshipIdentity`: origin and
destination access coordinates include `(gateway result digest, pool, candidate_index, candidate
airport fact ID, original origin airport fact ID, original destination airport fact ID)`; the scoped
hub coordinate includes `(gateway result digest, pool, candidate_index, hub airport fact ID,
scope_index, typed origin kind/IATA, typed destination kind/IATA)`. Including O and D prevents one
multi-applicability access candidate's relationships from colliding. Do not derive identity from a
lossy accepted-airport summary.

For a hub typed-reference pair, derive support anchors from each reference separately:

- an `original_origin(O)` reference anchors exactly O;
- an `origin_access_gateway(G)` reference anchors only that accepted gateway's
  `supported_original_origin_iata_codes`;
- an `original_destination(D)` reference anchors exactly D; and
- a `destination_access_gateway(A)` reference anchors only that accepted gateway's
  `supported_original_destination_iata_codes`.

Form the supported original O×D pairs from those per-reference sets, retaining the already validated
applicability. Never use the accepted scope's whole expanded-origin and expanded-destination unions to
credit one typed pair with another reference's support. Admission of a standalone G -> D or O -> A
strategy is not a prerequisite for a hub strategy that explicitly references G or A; the source
relationship and positioning dependency remain sufficient.

For a multi-anchor access reference, obligations are alternatives attached to each supported original
O×D pair, not a conjunction requiring positioning from every supported original airport at once.

### B4. Logical query semantics and many-to-many provenance

`LogicalAwardQuery` is the shared unit of planned provider-neutral work:

```text
query_id: "logical-award:" + sha256(semantic key)
origin_airport_fact_id: str
destination_airport_fact_id: str
scope: Literal["endpoint_market"]
date_envelope: DateEnvelope
requested_cabins: canonical tuple[CabinClass, ...]
award_mode: Literal["award"]
connection_semantics: Literal["provider_returned_connections_allowed"]
filter_obligations: canonical tuple[FilterObligation, ...]
result_validation_obligations: canonical tuple[ResultValidationObligation, ...]
```

The semantic deduplication key is a purpose-built canonical payload, not a full Pydantic dump. It
includes airport fact IDs; scope; inclusive start/end, basis, and airport-origin timezone; canonical
cabins; award mode; explicit connection semantics; each filter kind and canonical operands; and each
result-validation kind and canonical parameters, including minimum traveler/seat count. It excludes
IDs, source provenance, request precision, reasons, source order, confidence, market advisories,
strategy role, and derivation receipts. Those excluded fields remain on probes, uses, strategies, or
receipts. Including provenance-bearing model dumps would prevent legitimate reuse. A baseline and a
supplement share only when all executable search and validation semantics match; airport pair alone is
never enough.

All logical queries use `scope="endpoint_market"`. For first-slice gateway/hub queries, do not add
`DIRECT_FLIGHT_AVAILABLE=true` and do not reuse the current route-evidenced
`EXACT_PHYSICAL_COMPONENT_STRUCTURE` obligation. Those belong to a route-evidenced physical-path
contract. `provider_returned_connections_allowed` expressly allows the provider to return a connecting
itinerary within each query boundary. All queries retain the inherited baseline cabin filter when
requested and the
minimum-award-seat validation obligation for the request's traveler count. Free-text hard constraints
remain deferred, field-level obligations; they are neither parsed into provider filters nor declared
satisfied by 2C.

`StrategyQueryUse` preserves the many-to-many relationship:

```text
query_use_id: sha256("query-use-v1", strategy_id, role, query_id)
strategy_id: str
query_id: str
role: access_main | hub_first | hub_second
sequence: 1 | 2
source_relationship_id: str
date_derivation_id: str
```

A query may be referenced by mandatory coverage and several supplemental strategies. Store mandatory
probe -> query linkage in `MandatoryQueryUse` and supplemental linkage in `StrategyQueryUse`. Every strategy must link
to its complete one-query or two-query bundle; every non-mandatory query must be reachable from at
least one admitted strategy; and dangling links are contract errors.

### B5. Dates and timezones

The source `EffectiveRequest.departure_window` is immutable. Every envelope derives directly from
that original window; offsets never compound from another expanded envelope.

| Query role | Envelope | Date basis/timezone |
| --- | --- | --- |
| Mandatory O -> D | original start through original end | first-origin local; O airport IANA zone |
| Destination access O -> A | original start through original end | first-origin local; O airport IANA zone |
| Origin access G -> D | original start - 1 through original end + 2 | later-component origin local; G airport IANA zone |
| Hub X -> H where X is original origin | original start through original end | first-origin local; X airport IANA zone |
| Hub G -> H where G is origin-access ref | original start - 1 through original end + 2 | later-component origin local; G airport IANA zone |
| Hub H -> Y | original start - 1 through original end + 2 | later-component origin local; H airport IANA zone |

Add `SupplementalDateDerivation` rather than forcing the superseded two-index `TemporalDerivation` into these
roles. It records `date_derivation_id`, `strategy_id`, query role, origin airport fact ID, original window/provenance,
offsets, derived dates, basis, airport IANA timezone, precision, policy version, and the literal note
`not_schedule_or_connection_evidence`. The 2B outbound context timezone is
generation context only and must not determine compiled query dates.

`date_derivation_id` hashes the derivation version, strategy ID, query role, source window,
origin airport ID/timezone, basis, offsets, and derived dates. Query IDs do not depend on derivation
IDs, avoiding an ID cycle. Every use must resolve its derivation, and the derivation's dates/basis/zone
must equal its query's envelope. Mandatory uses derive directly from their existing probe envelopes.

Catch date arithmetic overflow deterministically. A missing/invalid catalog IANA timezone or overflow
on a supplemental query yields `unsupported_rule` for the entire access/hub bundle and no partial
query materialization. The same problem on a mandatory query is an evidence failure because complete
mandatory coverage cannot be represented truthfully. Preserve the original window precision and
provenance on the derivation/use receipt even though they are not part of query execution deduplication.

The wider envelope is permission to search, not permission to accept a journey whose actual departure
violates the user's window. Future validation must reconstruct the complete journey where supported
and enforce the original departure constraint. The first provider slice must label independently
returned hub/access components as research leads, including across date-line changes; 2C cannot prove
connection feasibility from local-date envelopes.

### B6. Positioning and eligibility

Distinguish three concepts:

- ordinary connections wholly inside one provider-returned itinerary;
- positioning between an original endpoint and an alternate access gateway; and
- separate tickets between independently observed query results.

An origin-access strategy and any hub strategy whose origin ref is an access gateway requires
pre-departure positioning. A destination-access strategy and any hub strategy whose destination ref
is an access gateway requires onward positioning. A hub strategy also carries a separate-ticket or
cross-query-assembly obligation regardless of whether its refs are original or access airports.
`repositioning_allowed` does not authorize separate tickets.

Each access dependency is attached per supported original-pair alternative and records from/to
airports, origin/destination side, typed permission value/provenance, unknown travel mode/payment, and
unknown feasibility. It is never materialized as an invented cash or award query. Every supplemental
strategy is `research_only_pending_result_validation`; an original-only hub still has unknown
separate-ticket tolerance and deferred cross-query assembly.

Proposed compiler policy:

| Effective request value | Compilation behavior |
| --- | --- |
| `false` | Suppress every strategy requiring access positioning; retain a disposition and explicit-refusal receipt; do not spend relationship/query/date budget on it |
| unknown/absent | Strategy may be admitted as `conditional_permission`; preserve unresolved positioning and suitability obligations |
| `true` | Strategy may be admitted, but access feasibility and separate-ticket tolerance remain unresolved unless independently known |

This changes the implemented planner behavior, which records repositioning but deliberately does not consume it.
It requires owner approval before implementation. It must apply only to positioning-dependent
supplements; it must never suppress mandatory queries or ordinary provider-returned connections.
Only the frozen typed `EffectiveRequest.repositioning_allowed=false` and its provenance can trigger
suppression. Free-text such as “no positioning” or “nonstop only” remains a deferred constraint and
must not be reparsed into a typed field or provider filter by 2C.

### B7. Budget units, deduplication, and atomic allocation

Replace the active `PlanningPolicy` with one current policy containing the grounding controls still
used by the compiler plus these compilation fields:

```text
policy_version: "search-planning-compilation-v1"
max_input_window_days: 31
max_mandatory_endpoint_pairs: 100
max_supplemental_relationship_bundles: 24
max_unique_logical_queries: 128
max_query_date_days: 4000
strategy_type_priority: explicit ordered tuple
later_component_start_offset_days: -1
later_component_end_offset_days: +2
```

These are the selected defaults under the owner's delegated architecture decision. The 100-pair
cap is global across the actual selected origin×destination cross-product. It admits every product of
two current single-location selection maxima, including 10×5, 10×6, 8×8, and 10×10, without claiming
that arbitrary multi-location requests fit. The 128-query cap leaves at least 28 distinct supplemental
queries at the maximum mandatory baseline, enough for 14 completely unshared two-query hub bundles
by query count; the date-day budget can bind earlier.
The 4,000 query-date-day cap admits 100 mandatory queries across the full 31-day input window (3,100
days), then up to 26 unshared widened 34-day queries (3,984 total); the 27th would exceed it. The
24-relationship cap still bounds admitted supplemental provenance/bundles even when queries are fully
shared. These are local planning guardrails, not Seats.aero airport, result, or request limits and not
empirical usefulness thresholds. Identity-bind them and change them only through a policy version.

A request over 100 mandatory pairs remains explicitly `UNPLANNABLE`; do not trim endpoints. This most
visibly affects multiple requested locations whose combined selected sets exceed the current maximum
for one location per side. Remove the superseded 25/40/1,400 path/item limits from the active policy;
they remain only in historical evidence. There is no limit-projection adapter or competing policy
digest. Validate the one current policy at construction and identity-bind its complete digest.

Budget definitions:

- `mandatory_endpoint_pairs`: count of selected O×D pairs. Every pair reserves one mandatory query.
- `supplemental_relationship_bundles`: count of admitted one-query access bundles plus admitted
  two-query typed hub-reference bundles. A hub bundle costs one relationship unit, not two.
- `unique_logical_queries`: count after complete semantic deduplication across mandatory and admitted
  supplemental work.
- `query_date_days`: sum of inclusive envelope days over unique logical queries. Shared queries are
  charged once.

Mandatory work reserves query and date-day capacity first. If selected endpoints, the source window,
mandatory unique queries, or mandatory query-date-days exceed a cap, return `UNPLANNABLE`. Do not trim
endpoints, downgrade explicit user alternatives, or return a partial mandatory plan.

For each optional bundle, compute incremental unique queries and incremental query-date-days against
the already admitted shared collection. Admit the entire bundle only if the relationship, query, and
date-day budgets all remain within their limits. A two-query hub is never half-admitted. If both
queries already exist, the bundle still consumes one relationship unit and zero incremental query or
date-day units. A bundle omitted by one limit remains accepted 2B evidence with a budget-omission
disposition; it is not rejected or semantically invalid.

Use the versioned allocator `balanced-types-pairs-v1`. Reserve mandatory work, then repeatedly cycle through
origin access, destination access, and scoped hub in that order, taking at most one relationship per
type turn. Each type maintains a round-robin cursor over canonical original endpoint-pair lanes. A
multi-anchor hub appears in every supported lane; the first visit disposes it globally from all lanes,
so it is charged once rather than per pair. Within a lane, order by candidate airport fact ID, typed
reference pair, and canonical source coordinate. These are stable serialization/tie-break fields,
not usefulness scores.

On its single visit, compute a bundle's marginal unique-query/date-day cost against the currently
admitted global query map. Atomically admit it when all limits fit; otherwise immediately record the
violated query/date budget and continue to cheaper candidates. There is no retry queue: the admitted
set only grows, so a bundle that does not fit an additive query/date cap cannot become affordable
later. When 24 relationships are admitted, mark every remaining policy-eligible bundle as relationship
budget exhausted without attempting query admission. Permission-suppressed and unsupported bundles
are accounted before allocation and consume no budget.

The exact scheduler is:

```text
types = [origin_access, destination_access, scoped_hub]
pairs = sorted(unique mandatory (origin_fact_id, destination_fact_id) pairs)
cursor[type] = 0
queues[type, pair] = eligible supported relationships sorted by
                    (candidate_fact_id, typed_reference_pair_or_empty, source_coordinate)
visited = empty set
while any queue contains an unvisited relationship:
    for type in types:
        starting at cursor[type], scan at most len(pairs) lanes, wrapping around
        discard already-visited queue heads; skip empty lanes
        if no lane has an unvisited head: continue to next type
        take exactly the first unvisited head from the first nonempty lane
        mark its relationship visited globally
        set cursor[type] = (that lane index + 1) modulo len(pairs)
        record that pair as the allocation anchor
        if admitted_relationships == configured_relationship_limit:
            emit relationship-budget omission
        else:
            compute union of existing queries and the complete bundle
            admit all uses if both unique-query and query-date-day totals fit
            otherwise emit all violated budget limits and decision-time costs
        advance to next type, whether this visit admitted or omitted the bundle
```

The outer loop stops when every relationship is visited, not after a cycle with no admissions.
No queue order, type priority, or cursor uses model confidence/reason text. This is deterministic
spread of opportunities, not an optimization or fairness guarantee about travel usefulness.

`CompilationBudgetReceipt` records for each budget: configured limit, mandatory reserved amount,
supplemental admitted amount, shared/reused amount where applicable, total materialized amount, and
omitted bundle IDs. `RelationshipDisposition` records exactly one of:

```text
admitted
omitted_budget
suppressed_positioning_refusal
unsupported_rule
```

`admitted` stores query IDs plus marginal query/date cost (including zero-cost full sharing).
`omitted_budget` stores the violated limits, decision-time marginal costs, and candidate totals;
`unsupported_rule` has only finite representability reasons in this first compiler: missing/invalid query-origin
timezone or date-envelope overflow. It must not become a hook for topology, geography, or usefulness
re-judgment. The accounting invariant is exactly:

```text
accepted 2B relationships
  = admitted + omitted_budget + suppressed_positioning_refusal + unsupported_rule
```

On a result carrying a plan, result-level budget receipts must exactly equal the plan receipts. On an
unplannable no-plan result, they still contain the failed mandatory admission measurement.

Use these exact five budget kinds: `input_window_days`, `mandatory_endpoint_pairs`,
`supplemental_relationship_bundles`, `unique_logical_queries`, and `query_date_days`. For a successful
plan, `observed = mandatory_reserved + supplemental_admitted`; `shared_reused` is informational and
must not be added to observed work. For query count it is total mandatory/supplemental query uses
minus unique queries; for date-days it is the sum over uses minus the sum over unique queries; it is
zero for the other units. Counts and shared work are recomputed from uses, not trusted receipt fields.
`input_window_days` records the original window once, not once per query. In no-plan mandatory
failures, `observed` is required work and `disposition="exceeded"` for each failed limit.

`CompilationCoverage` records `mandatory_required_pairs`, `mandatory_covered_pairs`,
`mandatory_complete`, `accepted_relationships`, and the four disposition counts. It also records
`discovery_outcome` and separate `market_coverage`; a plan requires exact mandatory equality.
`GatewayDiscoveryCompilationReceipt` carries input/result digests, `replay_status="verified"`,
generation/outcome statuses, the market gate, market coverage, endpoint assessment decisions,
candidate/scope decisions, issues, and limitations. Preserve advisories even for budget-omitted or
permission-suppressed candidates. Source records remain required companion evidence for replay.

`RelationshipDisposition` additionally carries its full source identity, source candidate/scope
references, supported original pairs, finite reason codes, optional allocation sequence/anchor, and
query keys and marginal costs when representable. Pre-allocation suppression/unsupported receipts
have no allocation sequence. Relationship-budget exhaustion need not materialize queries, but must
identify the omitted relationship. Never invent numeric query costs for an unrepresentable date.

Separate self-contained structural validation from source-aware verification: Pydantic validates
IDs, links, sums, outcomes, dates, and digest consistency; compiler/evaluator verification additionally
replays the pinned source bundle and checks exact endpoint and accepted-relationship set equality.
A recomputed hash alone cannot prove that a relationship was accepted by 2B. Saving/reloading a plan
for verification therefore needs its bound source artifacts, not only a lossy public summary.

### B8. Replay, bindings, discovery outcomes, and advisory evidence

The compiler must never consume only `accepted_*` fields from a stored 2B record. Its admission order
is:

1. Validate the frozen request and recompute its digest.
2. Replay endpoint-selection records when used, then exact-match the selected airports and all
   endpoint policy/catalog identities.
3. Compare each 2B side against the actual grounded baseline projection using canonicalized full
   `SelectedAirport` payloads, including fact and source IDs. Preserve stored tuple order in the 2B
   input digest, but do not require incidental planner traversal order to match when the canonical
   side-specific payload sets are identical.
4. Exact-match `record.input.outbound_date` start/end/precision to the frozen
   `EffectiveRequest.departure_window` and its context timezone to
   `EffectiveRequest.context.timezone`. This is a binding check only; query timezones still come from
   their origin airports.
5. Exact-match optional upstream selector IDs/digests, catalog receipt, and market-policy identity.
6. Call the existing 2B replay function, which verifies result/input digests, gate, complete proposal,
   decisions, accepted subsets, and result equality.
7. Only then compile the accepted relationships or a mandatory-only outcome.

Fail-fast precedence is input schema/admission, endpoint source validation/grounding, mandatory work
admission, external gateway bindings, replay, then optional compilation. Mandatory admission uses
the existing semantic distinction between unplannable request/coverage and evidence failure. For example,
110 mandatory pairs (for example, a 10×11 product) under the default cap return unplannable before
replay; this does not claim the
unexamined gateway record was verified. Every result containing a plan must have completed replay.

Any exception, digest mismatch, endpoint/date/selector/catalog/policy mismatch, failed replay, or plan
contract failure is `EVIDENCE_FAILURE` with no plan. Do not catch these as optional discovery failure.

For 2A provenance, record digests are authoritative because `AirportSelectionRecord` has no record-ID
field. Nonempty 2B upstream IDs require caller-supplied ID-to-digest bindings and must never be
fabricated. Empty 2B upstream IDs may bind supplied record digests; both IDs and digests may be empty
only for the reviewed/direct endpoint provenance mode.

Specifically, M2A mode requires the 2B digest tuple to equal the validated M2A record-digest set.
Reviewed-mapping records created to describe an already frozen diagnostic endpoint set may have no
2B upstream references; their mapping digests are then bound by plan identity and full endpoint equality.
If a reviewed record is named by nonempty 2B upstream references, those references must exactly match
the supplied reviewed records. Reject unused/duplicate caller ID bindings. All comparisons preserve
the original bound 2B input bytes/order for replay; they never rewrite the record.

After successful replay and all external bindings:

| 2B outcome | Valid 2C behavior |
| --- | --- |
| `POLICY_SKIPPED` | Mandatory-only `PLANNED`, with policy-skip receipt |
| `SUCCESS_EMPTY` | Mandatory-only `PLANNED`, with successful-empty receipt |
| `SUCCESS_NONEMPTY` | Compile/account every accepted relationship |
| `PARTIAL_ACCEPTANCE` | Compile/account accepted relationships, preserve rejected-candidate limitations, and return reduced coverage even if all accepted work fits |
| `REJECTED_ALL` | Mandatory-only `REDUCED_COVERAGE`; proposal rejection is not proof no useful supplement exists |
| `GENERATION_FAILURE` | Mandatory-only `REDUCED_COVERAGE`, preserving the operational failure |
| `VALIDATION_FAILURE` | Recommended: mandatory-only `REDUCED_COVERAGE` with a distinct system-validation-failure receipt, but only because replay proved this is the authentic stored terminal result |
| `INPUT_ERROR` | `EVIDENCE_FAILURE`; the supplied discovery input cannot be treated as optional success |

`REJECTED_ALL`, `PARTIAL_ACCEPTANCE`, budget omission, or `unsupported_rule` also yields
`REDUCED_COVERAGE`. Market gaps/advisories and unknown positioning alone do not. Treating replay-valid
`VALIDATION_FAILURE` as fail-soft is a new approval choice. The approved record
distinguishes it from candidate-level rejection, but current review direction only clearly guarantees
fail-soft generation failure. If the owner declines this recommendation, map it to
`EVIDENCE_FAILURE`; do not merge it with `REJECTED_ALL`.

Preserve `GatewayMarketCoverage`, endpoint mapping issues, candidate `policy_unknown`, model/policy
`mismatch_advisory`, both policy and model market claims, generator limitations, and candidate-level
issues. They are disclosure/provenance only in this version and cannot influence admission order,
ranking, or suppression. A future market-aware lane requires a new policy version. They also cannot
become a hidden rejection rule. Mandatory-only output is valid only after all bindings/replay succeed and the
2B terminal outcome is one of the explicitly fail-soft states above.

Existing replay eagerly validates finite wire products before compiler budgets: up to 20 candidates
per pool, 40 scopes, and 40 references per side, with scope products materialized during validation.
The structural maximum can be large (1.28 million typed hub pairs). Compiler relationship/query/date
limits bound admitted strategies, materialized queries, and query-date work. They do not bound replay
CPU/memory, relationship enumeration, total receipt count, or serialized plan bytes because
every accepted relationship needs a disposition, including omissions. That receipt/enumeration size
is finite only through 2B's source limits. Do not truncate receipts. Verification must separately
measure replay, compiler enumeration/admission, and serialized receipt bytes, and must not claim a
pre-replay operational bound. A future pre-replay admission or receipt-compaction change requires
measured need and a separately scoped decision.

### B9. Topology boundary

The replacement compiler does not accept route topology as an input. Remove `_build_explicit_paths`
from active orchestration, do not create `ExplicitPathHypothesis`, and do not emit missing-topology
exclusions. Therefore absent topology cannot reduce a compiled plan. Record this boundary through the
compiler contract version rather than a dormant legacy switch. Route-backed expansion, direct-flight
component filters, and missing-topology reductions are retired from the active planner and their
runtime-only fixtures may be removed or rewritten. Historical evidence remains unchanged. A future
route-evidenced source requires a new, separately budgeted contract; 2B hypotheses must never be
stuffed into `ExplicitPathHypothesis`.

### B10. Worked examples

The examples use a three-day original window, so original queries cost 3 date-days and later-component
queries cost 6 date-days (`start - 1` through `end + 2`, inclusive).

#### Mandatory-only success

Selected endpoints are SFO and NRT. The replayed 2B record is `SUCCESS_EMPTY`.
The compiler emits one mandatory SFO -> NRT probe and one logical query using the original window and
SFO timezone. Budgets record 1/100 pairs, 1/128 queries, and 3/4000 query-date-days. The discovery
receipt records the exact empty outcome. There are no supplemental strategies or relationship
omissions, and absent topology evidence creates no reduction.

An independent SFO -> LAX example may demonstrate `POLICY_SKIPPED` under the active market policy; do
not label the SFO -> NRT case a single-market skip.

#### Shared-query access and hub supplements

Use selected origins SFO and SJC, selected destination NRT, and a synthetic schema-valid 2B proposal:
origin-access LAX supports both original origins and applies to NRT; hub YVR has one accepted scope
whose origin side contains `original_origin(SFO)` and `origin_access_gateway(LAX)` and whose
destination side contains `original_destination(NRT)`. This demonstrates compiler mechanics only; it
does not claim the scenario is owner-reviewed or useful.

The compiler emits two mandatory queries (SFO -> NRT and SJC -> NRT), two access relationships that
share LAX -> NRT, and two hub typed-ref bundles (SFO -> YVR -> NRT and LAX -> YVR -> NRT) that share
YVR -> NRT. The result has four supplemental relationships and six supplemental uses. Its six unique
queries and inclusive date-day total are:

| Query | Days | Uses |
| --- | ---: | --- |
| SFO -> NRT | 3 | mandatory |
| SJC -> NRT | 3 | mandatory |
| LAX -> NRT | 6 | two origin-access relationships |
| SFO -> YVR | 3 | original-ref hub first |
| LAX -> YVR | 6 | access-ref hub first |
| YVR -> NRT | 6 | two hub second components |

That is 27 unique query-date-days, not the sum over eight uses. Both access relationships retain their
own original-pair positioning alternative. The LAX-ref hub remains eligible even if a standalone LAX
-> NRT relationship was omitted; its dependency comes from accepted 2B support rather than another
strategy's admission.

#### Budget omission

Mandatory work reserves 100 queries. Assume admitted supplements have materialized 28 more unique
queries, reaching the 128-query cap, while relationship capacity remains. The next two-query hub shares
one existing query but needs one new query. The allocator omits the whole hub as `omitted_budget`
with reason `unique_query_budget_exhausted`; it does not leave a one-component strategy, consume a relationship
unit, or call the 2B candidate invalid. Its relationship disposition, source scope, both would-be
query keys, and incremental cost are retained for inspection.

#### Explicitly refused and unknown positioning

With `repositioning_allowed=false`, an SFO-origin request suppresses origin-access LAX -> NRT and any
hub scope using LAX as its origin ref. Mandatory SFO -> NRT and hub scopes beginning at SFO remain
eligible. Suppressed bundles consume no optional budgets and receive explicit-refusal dispositions.

With permission unknown, those strategies may be admitted as conditional research. Their obligations
state that positioning permission, timing, transport, and cost are unresolved; downstream output
cannot describe them as suitable for the traveler. A hub also retains a separate-ticket-tolerance
obligation. Ordinary connections within a provider-returned SFO -> NRT itinerary are unaffected in
both cases.

#### Optional discovery failure versus invalid replay evidence

A replay-valid `GENERATION_FAILURE` produces a complete mandatory-only plan with reduced supplemental
coverage and the preserved failure. Under the recommended new rule, a replay-valid terminal
`VALIDATION_FAILURE` does the same with a different system-failure receipt.

If the record digest is forged, its catalog differs, its endpoints/date context do not match the
current request, selector digests do not match, or replay raises, compilation returns
`EVIDENCE_FAILURE` and no plan. It must not disguise untrusted evidence as an ordinary optional
failure.

## C. Code-level implementation map

### Files and interfaces to add or change

| File | Proposed change |
| --- | --- |
| `src/award_agent/search_planning/contracts.py` | Replace the active top-level plan, identity, result, selection-source, strategy, logical-query, link, date, positioning, discovery, disposition, coverage, and budget contracts. Reuse stable atomics such as `EndpointProbe`, `SelectedAirport`, `DateEnvelope`, and obligation types where their meanings still fit. Extract a focused contract module only if file size/import direction warrants it; do not create a compatibility artifact. |
| `src/award_agent/search_planning/policy.py` | Replace obsolete path/item limits with the current 31/100/24/128/4,000 compiler limits; retain grounding/freshness controls that are still consumed; add explicit type priority, lane rule, and date offsets; produce one policy digest. |
| `src/award_agent/search_planning/planner.py` | Replace `plan_searches` orchestration with input revalidation, endpoint-source validation, mandatory-query construction, exact bindings/2B replay, relationship enumeration, semantic deduplication, permission classification, deterministic allocation, receipts, and final validation. Remove active route-expansion and manual-cash branches. Keep internal pure helpers where they make invariants testable. No model/provider seam. |
| `src/award_agent/search_planning/gateway_discovery.py` | Reuse replay and existing accepted contracts unchanged. Add no prompt/schema/validator behavior. A read-only helper that exposes canonical source relationship identities is acceptable only if it preserves current record digests. |
| `src/award_agent/search_planning/airport_selector.py` | Keep selector evidence/replay behavior unchanged, but migrate any `SearchPlanningResult` integration wrapper to the replacement plan and copy the validated selector receipt into plan identity. |
| `src/award_agent/search_planning/__init__.py` | Export only the current planner/contracts and remove obsolete public planner symbols after repository reference checks. |
| `src/award_agent/search_planning/handoff.py` | Replace the current plan handoff validator with the compilation-binding check. Compare session/revision and request digest before a caller-computed trusted binding digest; remove legacy-only branches. |
| `src/award_agent/evaluation/search_planning.py` and `src/award_agent/cli/search_planning_eval.py` | Revise the existing evaluator around the replacement policy and plan, or retire its superseded cases. It must not pin the old policy digest or invoke the old planner as a current gate. |
| `src/award_agent/cli/search_strategy_compile_eval.py` | Add an offline-only evaluator with explicit `portable-offline` and `local-original-records` modes; missing prerequisites fail and no mode may regenerate evidence live. |
| `tests/unit/test_search_strategy_compiler.py` | New focused compiler tests using frozen fakes/fixtures only. |
| `tests/unit/test_search_strategy_contracts.py` | New invariant, canonicalization, digest, and forged-link/budget tests if splitting keeps compiler tests readable. |
| `tests/unit/test_search_planning_endpoint.py` | Port applicable grounding, mandatory coverage, immutable-input, and failure assertions to the replacement output. Remove serialization-compatibility assertions. |
| `tests/unit/test_search_planning_paths.py` | Retire active-planner expectations for route expansion and missing-topology reductions. Preserve independently useful route-evidence validator tests only if their types remain used elsewhere. |
| `tests/unit/test_gateway_discovery.py` | Add only missing synthetic source records needed by compiler tests if builders cannot live with compiler fixtures; do not change 2B acceptance expectations. |
| `tests/unit/test_airport_selector.py` | Add integration binding cases for M2A receipt mismatch without adopting M2A. |
| `tests/unit/test_search_planning_handoff.py` | Rewrite around current/stale/forged cases for request, endpoint/selector, gateway record, catalog/policies, and compiler identity. |
| Existing planner/evaluator fixtures and goldens | Classify each as retained semantically, revised for the replacement contract, or retired because its behavior is removed. Generate new expected digests only from reviewed offline results; never rewrite historical evaluation reports. |
| `evals/search_strategy_compilation/casebook-v1.json` | Add the pinned offline compiler casebook and expected structural summaries; no live call path. |
| `docs/adr/0021-*.md` | Before implementation, record the in-place replacement, first-slice vocabulary, positioning change, fail-soft outcome policy, budgets, and no-topology-input boundary. |
| `docs/project-state.md`, milestone roadmap, `DEFERRED.md`, and the relevant build log | Update only after decisions/implementation evidence exist; preserve recommendations versus owner decisions. |

### Explicitly untouched

- ADR 0016 request semantics and the intent/clarification runtime.
- M2A model prompt/adapter/policies, diagnostic evidence, and adoption status.
- M2B prompt-v6, generator/schema, planning-market policy, validation rules, replay record shape, final
  diagnostic, and closeout.
- Historical M2A/M2B and prior planner evidence artifacts. If `ExplicitPathHypothesis` remains in
  historical/catalog tooling, its route-evidenced meaning does not change.
- Provider adapters, live SDKs, ranking, RAG, persistence, and UI.

### Replacement and repository migration

This is an in-place development-contract replacement. There are no deployed or external consumers to
protect. Migrate every in-repository caller to the new input, plan, policy, and handoff validator;
delete compatibility adapters and obsolete runtime paths once reference searches prove they are
unused. Do not auto-convert stored old plans because they lack bound 2B evidence; prior reports remain
historical records. Current fixtures and expected outputs may change deliberately, with each old
assertion classified as retained, revised, or retired in the build log.

### Ordered implementation cuts

1. **Decision record and contract skeleton.** Approve the genuine choices in Section E, add ADR 0021,
   then replace the active contracts/policy, canonical IDs, and validator tests. Inventory all current
   planner callers and classify old fixtures before deleting obsolete symbols.
2. **Single mandatory-only compiler.** Reuse/refactor grounding and endpoint admission into internal
   pure helpers, migrate in-repository callers/tests, and prove complete coverage, explicit overflow,
   immutable-input rejection, and no topology-induced reduction. Remove the old route-expansion path.
3. **Bindings and outcome bridge.** Add endpoint/2B exact bindings, replay-before-consume, discovery
   receipts, mapping/advisory preservation, and the approved fail-soft matrix. Test corruption versus
   authentic optional failure.
4. **Relationship enumeration and dates.** Compile origin access, destination access, and typed hub
   bundles; implement per-reference support anchors, positioning/separate-ticket obligations, and
   airport-timezone derivations. Keep all relationships initially accounted without budget admission.
5. **Deduplication and allocation.** Materialize semantic query keys, many-to-many links, permission
   suppression, deterministic lane scheduling, atomic bundle admission, and all budget receipts.
6. **Replay corpus and completion report.** Run available original high-fanout records in an explicit
   local-artifact mode plus checked-in sanitized/synthetic access-referenced, long-window, and failure
   fixtures in portable mode. Record replay and compiler costs separately, inspect canonical plan
   summaries, and prepare the owner preview. Stop before provider integration.

Each cut should leave offline tests passing and have its own build-log evidence. Do not combine a
runtime/provider pilot with 2C implementation.

The internal mandatory helper should be concrete and provider-call-free:

```python
def build_mandatory_baseline(
    envelope: PlanningInputEnvelope,
    *,
    policy: PlanningPolicy,
    capability: CachedSearchCapability,
    repository: PlanningKnowledgeRepository,
    endpoint_selections: tuple[EndpointSelectionProjection, ...],
) -> MandatoryBaselineBuildResult:
    ...
```

Endpoint-source validation precedes this helper. The source validator produces direct, reviewed, or
replayed-M2A projections. The helper never chooses airports and reads admission limits from the one
validated current policy.

`MandatoryBaselineBuildResult` contains validated/reparsed input identity, endpoint projections,
selected origin/destination payloads, canonical selected pairs, endpoint probes,
logical-query-ready mandatory semantics, deferred constraints, capability/catalog receipts, baseline
issues, and mandatory budget counts. It does not construct a `SearchPlan` or path receipts. The single
compiler builds the current artifact around this immutable baseline data.
Represent a failed build as its typed outcome, issues, and mandatory admission receipts with no
baseline payload. No compatibility adapter preserves obsolete failure text.
Reparse frozen Pydantic inputs from round-trip dumps at this boundary because `model_copy(update=...)`
can bypass validation.

The replacement `check_plan_handoff` must reject before any provider execution. It compares current session
ID/revision first, then recomputes the current `EffectiveRequest` digest, then compares a caller
`expected_compilation_binding_digest` computed from trusted current endpoint selections/replay
receipt, 2B record, catalog/capability, planning/market policies, and contract versions. It must
never accept a binding digest merely echoed from the plan being checked. A request that is unchanged
while a selector record, gateway result, catalog, or policy changes returns typed status
`stale_planning_bindings`; stale request/session keeps the existing stale-source meaning.

## D. Verification plan

All tests use checked-in fixtures, in-memory repositories, or immutable replay records. No test may
instantiate a live model or provider client.

### Required coverage and acceptance criteria

| Area | Offline cases | Acceptance criterion |
| --- | --- | --- |
| Mandatory coverage | singleton, 10×5, 10×6, 8×8, exactly 100 pairs, 10×11 = 110 pairs, mandatory query/date cap overflow | Every admitted O×D pair has exactly one probe/use; no endpoint trimming; overflow is typed `UNPLANNABLE` with no partial plan |
| Semantic dedup | same query from mandatory/access/hub; same pair with different date basis/timezone/filter/validation | Exact semantics share one query and retain every use; any executable semantic difference yields separate IDs |
| Atomic bundles | hub adds 2/1/0 incremental queries; first or second query crosses query/date cap | Both links appear or neither appears; shared incremental cost is exact; omission names the binding limit |
| Allocation | shuffled JSON object-key serialization, multiple endpoint lanes, more than 24 bundles, equal-cost bundles | Object-key order does not change canonical output; changing ordered proposal candidate/scope arrays changes bound 2B identity; explicit type priority/lane rule holds; no reason/confidence-based priority |
| Date/timezone | original first leg, origin access, both hub roles, DST-adjacent dates, International Date Line airports, 31-day window | Every envelope derives from the original window; offsets never compound; timezone is query-origin airport IANA zone; inclusive date-day counts are exact |
| Date representability | missing/invalid airport zone; `date.min`/`date.max` offset overflow on access and hub queries | Supplemental bundle is wholly `unsupported_rule`; a mandatory failure is typed evidence failure; no exception escapes or partial query survives |
| Positioning | true, false, unknown; ordinary connection; origin/destination access; access-referenced hub | False suppresses only positioning-dependent strategies; unknown remains conditional; separate-ticket obligation remains independent |
| Replay identity | endpoint order, request/date context, selector digest/policy, catalog, market policy, result/input digest mismatch | Any mismatch/exception is `EVIDENCE_FAILURE` with no plan; exact authentic record is replayed before accepted fields are used |
| Handoff freshness | current/stale session and request; unchanged request with changed endpoint receipt, 2B record, catalog/capability, or policies; forged plan binding | Trusted recomputation accepts only exact current bindings; changed planning evidence returns `stale_planning_bindings`; no provider execution occurs |
| Discovery outcomes | skip, empty, nonempty, partial, rejected-all, generation failure, validation failure, input error | Outcome matrix in B8 is exact; approved fail-soft terminal failures retain distinct receipts; invalid input/evidence never becomes mandatory-only success |
| Mapping/advisories | endpoint/candidate gaps, `policy_unknown`, model/policy mismatch | All claims/issues survive; none silently rejects an otherwise accepted relationship |
| Relationship semantics | origin/destination access, original-ref hub, origin-access-ref hub, destination-access-ref hub, both-access hub | Hub bundle is one typed ref pair; support derives from each ref, not union; standalone access admission is not required; no standalone G -> A appears |
| High fanout | available original v6 high-fanout private records and a checked-in saturated synthetic valid record | Output caps hold; every accepted relationship is disposed exactly once; compiler is deterministic; replay and compile time/memory are reported separately without a pre-replay-bound claim |
| Long windows | 31 days, 32 days, 100 mandatory queries at 31 days, then 26 versus 27 unshared widened queries | Original input cap and total inclusive date-day budget are independently enforced; wider envelopes are recorded approximations; 3,984 fits and 4,018 exceeds the selected default |
| Topology retirement | no route topology, migrated route-evidence fixtures | Compiled output has no route-absence reduction and creates no `ExplicitPathHypothesis`; obsolete active-planner expectations are explicitly revised or retired rather than preserved through a second runtime |
| Contract integrity | duplicate IDs, dangling links, noncanonical ordering, forged costs/dispositions/digest | Pydantic validation rejects every inconsistent artifact; canonical round-trip reproduces the digest |

The public tracked v6 baseline contains summaries and private trace paths, not the 46 complete
`GatewayDiscoveryResult` records. Original records live under ignored local trace artifacts. The
portable gate therefore needs newly checked-in sanitized/synthetic replay-valid records for high
fanout, origin-access, destination-access, both-access hub references, and long windows. Such records
have their own identities; never claim a redacted or rebound fixture preserves an original live
record digest. When original local artifacts are available, a separate local mode may replay them
against their exact catalog/market-policy prerequisites without exposing them. Missing original
artifacts must fail that requested mode explicitly, never silently skip or trigger live regeneration.
The final diagnostic's 43 hub scopes all reference original endpoints, and its three-day windows do
not cover the synthetic boundaries above.

### Proposed commands

These are future verification commands, not claimed results:

```bash
.venv/bin/pytest -q \
  tests/unit/test_search_strategy_contracts.py \
  tests/unit/test_search_strategy_compiler.py \
  tests/unit/test_search_planning_handoff.py

.venv/bin/pytest -q \
  tests/unit/test_search_planning_endpoint.py \
  tests/unit/test_airport_selector.py \
  tests/unit/test_gateway_discovery.py \
  tests/unit/test_market_policy.py

.venv/bin/pytest -q tests/unit/test_search_planning_evaluation.py

.venv/bin/ruff check \
  src/award_agent/search_planning/contracts.py \
  src/award_agent/search_planning/policy.py \
  src/award_agent/search_planning/planner.py \
  src/award_agent/search_planning/handoff.py \
  tests/unit/test_search_strategy_contracts.py \
  tests/unit/test_search_strategy_compiler.py

.venv/bin/mypy \
  src/award_agent/search_planning/contracts.py \
  src/award_agent/search_planning/policy.py \
  src/award_agent/search_planning/planner.py \
  src/award_agent/search_planning/handoff.py

.venv/bin/pytest -q

git diff --check
```

Add the compiler offline evaluator named in the implementation map, with these exact no-network modes and
flags. Run it against the pinned casebook:

```bash
PYTHONPATH=src .venv/bin/python -m award_agent.cli.search_strategy_compile_eval \
  --casebook evals/search_strategy_compilation/casebook-v1.json \
  --output /tmp/m2c-compilation-eval.json \
  --mode portable-offline

PYTHONPATH=src .venv/bin/python -m award_agent.cli.search_strategy_compile_eval \
  --casebook evals/search_strategy_compilation/casebook-v1.json \
  --output /tmp/m2c-original-record-replay.json \
  --mode local-original-records \
  --original-record-root evals/gateway_discovery/traces-live
```

Acceptance requires: all scoped tests pass; every old planner assertion is classified as retained,
revised, or retired; historical evidence files remain untouched; the compiler evaluator makes zero
SDK/provider calls; repeated runs have identical canonical plans/digests
and semantic accounting (performance measurements are outside those stable payloads);
every case reconciles mandatory pairs, relationships, queries, date-days, dispositions, and bindings;
and `git diff --check` is clean. Record actual results only after running them.

The existing default-capability golden CLI depends on exact ignored
`.provider-docs/seats-aero/cached-search.md` bytes. A tracked-export inspection failed because that
regular file was absent while the local workspace passed with it present. Treat the pinned capability
artifact as an explicit prerequisite; do not remove its hash check or call a local-only pass a clean
export handoff. The repository also has recorded mypy failures, so this plan makes no universal
type-check-green claim; define and report the active scoped gate truthfully.

The scoped Ruff and mypy targets above must pass for the replacement compiler modules. Record any imported
pre-existing errors separately with an exact baseline; do not suppress new errors or call a failing
command green. Full pytest is the final repository integration check, with existing historical skips reported
as skips rather than new qualification. No broad historical cleanup is required unless this change
causes a regression or the declared scoped gate depends on it.

The new casebook pins compiler/base/market/capability identities and, per case, the frozen request,
endpoint source, repository fixture or catalog manifest path/digest, gateway record path/digest, and
expected outcome, counts, specific links/dispositions, and coverage tags. Local-original mode also
pins the selected public diagnostic and case/trial-to-private-record mapping; do not scan arbitrary
trace files and call them the final v6 run. Relative artifact paths resolve from the casebook and are
validated against the declared root. Missing required catalog/market/capability bytes are explicit
prerequisite failures in either mode. Fixture-mode local capability evidence must be declared as
fixture evidence; the actual reviewed capability qualification retains its source-byte checks.
The output report records these identities, per-case structural checks, expected/actual counts,
passed/failed totals, and separate replay, enumeration/admission, and receipt-size measurements.
Zero failed checks is the offline compiler gate; measured latency/memory is disclosed without an
invented performance threshold. Missing original records leave the original-replay gate outstanding,
even if the portable structural gate passes.

Planning baseline already observed by the parent on 2026-09-19:

```text
.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py \
  tests/unit/test_search_planning_paths.py \
  tests/unit/test_gateway_discovery.py \
  tests/unit/test_airport_selection_foundation.py

107 passed in 1.09s
```

This establishes the focused pre-implementation baseline only. It is not compiler evidence and does
not create a compatibility requirement for the replacement contract.

## E. Open decisions

### Existing approved behavior to preserve

- ADR 0016's one-way, award-only ready boundary and immutable outbound departure constraint.
- Deterministic date arithmetic, validation, budgets, state reduction, and offline tests.
- Complete selected-endpoint cross-product coverage or an explicit required-budget failure.
- M2A remains diagnostic-only; reviewed fixtures or supplied records are allowed without adoption.
- M2B is owner-closed: its candidates are unverified hypotheses, pool caps are independent, unknown
  market mapping forces generation, and market mismatch is advisory.
- Replay revalidates the complete 2B proposal and exact bound identities before consumption.
- Optional generation failure cannot erase mandatory endpoint coverage.
- `ExplicitPathHypothesis` remains route-evidenced and cannot contain 2B model proposals.
- Current free-text hard constraints remain unresolved post-search-validation obligations.
- Provider execution, itinerary assembly, ranking, RAG, persistence, and product multi-agent
  orchestration remain outside 2C.

### Concrete recommendations that fit existing authority

These choices specify how to implement the owner-requested first slice but should still be recorded in
the new ADR/policy:

| Recommendation | Default | Tradeoff |
| --- | --- | --- |
| Top-level artifact | Replace current `SearchPlan` in place with `CompiledSearchPlan`; keep one active entry point and policy | Requires deliberate caller/test migration, but avoids maintaining an unused runtime and compatibility layer |
| Strategy vocabulary | Origin access, destination access, and one atomic bundle per typed hub-ref pair; no standalone G -> A | Small and auditable; delays potentially useful access-to-access composition |
| Query semantics | Provider-returned itinerary per airport pair, with no implicit direct filter | Preserves ordinary connections and provider result boundaries; later assembly must decide component topology explicitly |
| Topology | No topology input or route expansion in the compiler contract | Avoids false reduced coverage and removes a dormant switch; future route evidence requires a new explicit contract |
| Dates | Original window for original-origin first searches; direct-from-original -1/+2 later envelopes with query-origin airport timezone | Consistent with approved exploration convention; remains an approximation requiring later journey validation |
| Accounting | Deduplicate full query semantics; many-to-many uses; mandatory reserve; atomic supplemental bundles | Maximizes shared work and traceability; the replacement contract needs explicit receipts |
| Replay resource claim | Bound admitted work; measure replay, enumeration, and receipt bytes separately | Truthful with current implementation; does not promise a bound on the full evidence artifact from query caps |

### Material choices requiring owner approval

The owner delegated the numerical limit decision to the parent/architect after the batching review
and subsequently chose in-place replacement rather than V1 compatibility. Those decisions are closed
for implementation planning: 31 input days, 100 mandatory pairs,
24 supplemental relationships, 128 total unique logical queries, and 4,000 query-date-days. It is
not repeated in the approval table below. Changing those values later requires a new policy identity
and evidence, not another implicit implementation choice.

| Decision | Recommended default | Tradeoff / alternative |
| --- | --- | --- |
| Supplemental date mapping | Use B5's direct-from-original envelopes and query-origin zones | Extends the approved -1/+2 convention to access/hub hypotheses; this bounds research but cannot prove complete temporal recall or actual departure compliance. Narrower windows lose leads; wider windows spend more work and require a later policy version. |
| Positioning refusal | `false` suppresses positioning-dependent supplements; unknown remains conditional | Changes the implemented ignored-policy behavior. Alternative is to compile incompatible research, but it could spend budget on explicitly refused work and needs very prominent labeling. |
| Replay-valid `VALIDATION_FAILURE` | Permit mandatory-only `REDUCED_COVERAGE` with a distinct system-validation receipt | Preserves mandatory work for an authentic optional terminal failure. Stricter alternative maps it to `EVIDENCE_FAILURE`; never merge it with candidate rejection. |
| Type priority and lane rule | Version an explicit type order and round-robin original-pair allocation; use content IDs only for stable ties | Deterministic and avoids model confidence as value. Any order expresses policy; useful-yield evidence may later justify changing it. |
| Unknown positioning research | Admit as conditional within the same optional budget | Collects possible leads without claiming suitability. Alternative suppression reduces work but treats missing preference like refusal and may hide value. |

No decision is needed now on automatic cross-query assembly, adaptive result-driven execution,
a second provider, RAG, or broad endpoint-policy adoption. Section G gives provider batching a concrete
advisory direction; its executable adapter remains a separate downstream scope.

## F. First downstream pilot

Keep the pilot separate from 2C's completion gate. A static/mock plan preview can happen during
implementation so owner feedback can shape presentation and policy. Any provider-backed pilot remains
separately opened and follows 2C's offline contract/replay evidence. The pilot's purpose is to show
what a later provider slice would need to establish and whether supplements reduce manual search work.

### Reviewed scenario

Prepare this scenario for owner review: one-way award, explicit SFO to NRT, two travelers, business
cabin, unknown positioning permission, context timezone `America/Los_Angeles`, and the historical spike
window 2027-03-10 through 2027-03-12, plus a reviewed/supplied endpoint set that fits mandatory limits.
The prior provider spike used `take=10` and `include_trips=false`; only a sanitized field summary was
retained and the raw response was discarded. It is not replayable trip evidence. Build a proposed
reviewed/synthetic gateway fixture that exactly matches the frozen request context, then ask the owner
to review that scenario. Do not rewrite a stored 2B record, make a new 2B call, imply previous access
proof qualified this SFO/NRT journey or gateway usefulness, or treat any M2A output as adopted.

Use an explicitly synthetic 2B fixture with LAX origin access supporting SFO/applying to NRT and YVR
hub scoped to original SFO/NRT. Validate it offline with the existing proposal validator and catalog;
label its configuration/record as fixture evidence, not a model invocation or a historical live
result. Its planned preview is:

| Logical query | Inclusive dates | Origin zone | Meaning |
| --- | --- | --- | --- |
| SFO -> NRT | 2027-03-10 to 2027-03-12 | America/Los_Angeles | Mandatory endpoint market |
| LAX -> NRT | 2027-03-09 to 2027-03-14 | America/Los_Angeles | Conditional access research; SFO -> LAX unresolved |
| SFO -> YVR | 2027-03-10 to 2027-03-12 | America/Los_Angeles | Hub first research component |
| YVR -> NRT | 2027-03-09 to 2027-03-14 | America/Vancouver | Hub later research component |

Expected planning accounting is one mandatory pair, two supplemental bundles, four unique queries,
and 18 query-date-days. These are worked-example arithmetic, not executed compiler results.
Preview cards contain placeholders for future observations, never invented availability/prices.
Owner review should assess whether the extra searches and their remaining manual checks are worth
attempting; acceptance of this fixture must not be represented as gateway or provider qualification.

The owner preview should show:

1. frozen request, endpoint source/review status, and complete mandatory coverage;
2. the replay/catalog/market/compiler identities;
3. unique logical queries with original versus later envelopes and airport timezones;
4. each supplemental strategy beside its exact 2B relationship, query uses, and obligations;
5. shared-query reuse and incremental budget cost;
6. omissions/suppressions and why they occurred;
7. a provider-execution mock layout that keeps validated baseline observed options separate from
   supplemental access/hub research leads; and
8. explicit text that hub component hits are not completed-journey lift or a through-ticket price.

Do not require automatic cross-query assembly for the first provider slice. Preserve each returned
itinerary boundary, validate mandatory-query results against travelers, cabin, dates, source, and
freshness, and label incomplete access/hub components as research leads.

### Evidence missing before any real provider integration

The repository has one narrow Cached Search access/response-shape spike, but no application adapter
or accepted fixtures for provider success, empty, timeout, unauthorized, rate-limit, malformed,
partial/page, and stale-result outcomes. It also lacks accepted trip-detail evidence for segment
topology, operating/marketing carrier, airport continuity, local/UTC chronology, cabin by segment,
seat count, award price/taxes, program, source link, observation timestamp, and freshness. The pilot
must not invent these semantics from provider documentation or old exploratory responses.

Before a live pilot, separately approve and implement a capability-bound adapter, immutable sanitized
success/error fixtures, bounded retries/timeouts/pages, raw-source provenance, and deterministic
normalization/result validation. Compare baseline-only and baseline-plus-supplemental work under the
same maximum budget, counting completed qualifying options separately from useful research leads and
manual checking. Do not score unqueried alternatives as empty.

The pilot may reveal that a supplement should be kept, restricted, or dropped. It must not reopen the
generic M2B prompt, claim broad access feasibility, or become a hidden prerequisite for closing the
deterministic 2C compiler.

## Evidence basis and known limits

This plan was grounded in the current planner/contracts/policies, endpoint-selection replay,
gateway-discovery validation/replay, focused tests, ADRs 0016-0020, project state, milestone roadmap,
2B closeout, architecture/adversarial reviews, deferred-work register, and the workbook's product and
provider-contract sections. The workbook's older round-trip/cash/product ambitions are subordinate to
the newer ADR 0016 and repository decisions.

The final v6 diagnostic recorded 400 accepted relationships and high fanout, but it does not prove a
useful allocation order or the proposed 24-bundle cap. It also contains no access-referenced hub
scopes and no long-window stress case. Those gaps are the reason for explicit owner decisions and
synthetic offline verification, not a reason to reopen 2B or make new live calls during planning.

### Repository evidence index

| Evidence | Relevant boundary |
| --- | --- |
| [ADR 0016](../adr/0016-one-way-award-request-boundary.md), [ADR 0017](../adr/0017-llm-owned-initial-intent-semantics.md) | Frozen request scope and semantic ownership |
| [ADR 0018](../adr/0018-sqlite-geographic-catalog.md) | Catalog receipts and read-only serving |
| [ADR 0019](../adr/0019-llm-proposed-endpoint-airport-selection.md) | Diagnostic selection, replay receipts, explicit pair overflow |
| [ADR 0020](../adr/0020-market-aware-model-proposed-gateway-candidates.md), [2B closeout](2026-09-19-m2b-gateway-airport-discovery-closeout.md) | Hypotheses, gate, advisories, closed stage |
| [Planner](../../src/award_agent/search_planning/planner.py), [contracts](../../src/award_agent/search_planning/contracts.py), [policy](../../src/award_agent/search_planning/policy.py) | Current mandatory coverage, date/item keys, validators, defaults, and obsolete topology paths to replace |
| [Selector integration](../../src/award_agent/search_planning/airport_selector.py), [handoff](../../src/award_agent/search_planning/handoff.py) | Existing record shapes and request freshness |
| [Gateway replay](../../src/award_agent/search_planning/gateway_discovery.py), [wire contracts](../../src/award_agent/search_planning/gateway_generator.py) | Typed scope products, source indices, replay, finite input bounds |
| [Architecture review](../reviews/2026-09-19-search-planning-architecture-review.md), [adversarial review record](../build-log/2026-09-19-astra-adversarial-review.md) | Advisory design input, challenged here against code |
| [Future-stage review](../reviews/2026-09-19-future-stage-goals.md), [deferred register](../../DEFERRED.md) | Sequencing alternatives and claim-specific gates; no progressive-coverage adoption |
| [Provider intake](../provider-feasibility/2026-09-08-initial-provider-intake.md), [sanitized success summary](../../evidence/provider-feasibility/2026-09-08-seats-aero-cached-search-success.json) | Access already evidenced; trip/error semantics still missing |
| [This planning session](../build-log/2026-09-19-m2c-planning.md) | Investigation, parent corrections, baseline tests, documentation checks |

## G. Cached Search batching reconsideration

Status: planning amendment following the owner's 2026-09-19 question. The owner delegated and the
architecture review selected B7's numerical compiler limits. No runtime policy changed, and the
provider batching design remains advisory downstream scope. This section does not discard mandatory
pair coverage or the strategy/query distinction.

### Finding and design consequence

The saved [Cached Search reference](../../.provider-docs/seats-aero/cached-search.md) documents lists
for both airport parameters, one common date range/filter set, and a maximum of 1,000 returned records
per page. It does not document a numerical airport-list limit, explicitly guarantee exhaustive O×D
evaluation, or provide per-pair completion markers. The saved concepts guidance describes pagination
with skip/cursor and possible duplicate records. The historical access spike exercised one airport
on each side. Multi-airport operation and its coverage interpretation still need adapter acceptance.

The intended execution should combine compatible work into list requests. Six logical pairs do not
require six API calls. Preserve this mapping:

```text
strategy/support -> logical pair query -> Cached Search batch -> pages/attempts -> observed records
```

Keep pair-valued logical queries as the coverage/provenance ledger. Replacing them with list-valued
logical queries would move overlap/deduplication and sparse-scope handling into more complicated set
algebra without reducing actual search coverage. The display can show one grouped search while the
ledger retains six pair identities. This is bookkeeping, not six independent network requests.

### Exact grouping, with no new search pairs

For the examples below, assume identical mapped dates/filters and the same execution cohort:

| Admitted logical pairs | Proposed initial request grouping |
| --- | --- |
| `{SFO,LAX} × {NRT,HND,KIX}` | One request with two origin and three destination codes |
| `SFO→NRT`, `SFO→HND`, `LAX→NRT` | Two requests: `SFO→{NRT,HND}` and `LAX→NRT` |
| A complete 6×6 mandatory set | One candidate batch expressing 36 pairs, subject to future adapter input/size policy |

In the sparse example, `{SFO,LAX}→{NRT,HND}` would also request `LAX→HND`, which was never admitted.
Do not silently introduce it, count it as authorized coverage, or use its results as a supported
strategy. The first slice should require exact grouping; deliberate extra searches would need their
own policy and accounting.

A small deterministic packer is sufficient:

1. Translate each eligible logical query under a reviewed provider-mapping policy.
2. Partition by identical mapped request parameters and execution/activation cohort.
3. Within each bucket, calculate each origin's exact destination set.
4. Group origins with identical destination sets, then emit sorted origin/destination lists.
5. Verify the expanded pair set of all batches equals the intended pair set, with no duplicate
   pair ownership within a bucket. Each pair retains its logical-query IDs.

This groups a complete mandatory rectangle naturally and handles sparse supplemental work without
an optimizer. It need not minimize the number of requests. Separate first/later date envelopes unless
their actual mapped parameters match; do not widen a mandatory query merely to merge it with a
supplement. Preserve mandatory and optional cohorts: optional results must not consume the mandatory
cohort's paging budget. A query shared with a mandatory strategy belongs to mandatory work and keeps
its supplemental provenance without a second execution.

Batch compatibility is different from semantic deduplication. Query-origin timezone, date basis,
traveler validation, and obligations remain attached to each logical query even when the provider
does not accept them as request parameters. Different zones do not automatically prohibit batching,
but the mapping must preserve each query's meaning; the saved capability leaves timezone and date
inclusivity unresolved. Do not convert local windows to UTC or assert cross-zone date semantics from
the list syntax. Use the same-zone SFO/LAX example for the initial preview and validate the broader
mapping during adapter acceptance.

### Budget and outcome changes

Keep separate measurements for structural work and provider execution:

- Compiler: mandatory pairs, admitted relationships, unique logical queries, query-date-days, and
  receipt size. These bound coverage and downstream result/validation work, not HTTP calls.
- Executor: initial batches, pages, attempts/retries, returned rows/bytes, trip-detail calls, and
  elapsed time. One batched query may require several page requests.

The delegated architecture decision therefore replaces the inherited 25/40/1,400 proposal with
100 mandatory pairs, 128 unique logical queries, and 4,000 query-date-days while retaining 31 input
days and 24 supplemental relationships. This covers every product of two current single-location
selection maxima but still rejects larger combined multi-location sets explicitly. It does not claim
unlimited provider input or make pair/result work free. Section B7 gives the exact derivation and
overflow examples. The old 25/40/1,400 limits are retired from the active policy rather than preserved
behind a compatibility entry point.

Do not replace the additive query budget with batch count inside B7's allocator. Batch count can
decrease as pairs are added: three edges of a 2×2 set need two exact batches, while adding the fourth
permits one. The monotonic no-retry proof applies to unique queries/date-days, not packed request
count. The smallest design is structural admission first, then packing and separate execution budgets.

The saved response identifies each returned pair through `Route.OriginAirport` and
`Route.DestinationAirport`. Attribute each result to its matching logical-query IDs and their strategy
uses. A page with no result for one requested pair does not establish that pair is empty. Global
sorting can concentrate early pages on one market. Preserve positive observations from partial runs,
but mark batch enumeration incomplete after page/time/row exhaustion or a later-page error. Even
completed pagination supports only the accepted filtered-cache coverage claim, never complete airline
inventory or bookability. A batch-wide error affects every member query; do not invent per-pair errors.

### Where this belongs and what to verify

Specify a downstream pure `CachedSearchBatchPlan` with batch ID, provider/operation,
capability/mapping/packing-policy identities, sorted airport lists, common mapped parameters,
activation cohort, and exact pair-to-logical-query links. Actual HTTP payload construction, pagination,
attempt records, and observed results remain the adapter's responsibility. Bind the batch plan to the
compiled-plan digest; never rewrite the compiler's query IDs or dispositions during packing.

The replacement plan includes a complete, catalog-pinned airport directory for materialized
query/dependency airports: `PlanningAirportIdentity {airport_fact_id, iata, timezone: str | None,
airport_evidence_source_ids, catalog_receipt_digest}`. Populate it from the bound catalog, require
unique fact IDs and unambiguous IATA mappings, and ensure every query endpoint resolves. A query
origin must satisfy its existing timezone validation; a missing destination-only zone remains
explicit. The adapter should not recover IATA codes from prose or infer new airport facts.

Recommendation: record this boundary now and include a labeled batch preview in the owner walkthrough.
Keep executable provider batching in the downstream provider slice rather than expanding 2C's current
completion gate. That slice must add execution-capability evidence; the existing capability v1 is
planning evidence and does not establish full multi-airport/pagination semantics.

Offline cases should cover the complete 2×3 and sparse examples, a relaxed-policy synthetic 6×6 plan,
deterministic airport order, parameter/phase/date incompatibility, exact pair attribution, stable IDs,
multi-page duplicate IDs, missing-pair results, page-budget truncation, later-page failure, unexpected
returned pairs, and deterministic splitting under configured local request-size guards. A local guard
is not a claimed provider maximum. Show default-profile overflow and relaxed-profile exact coverage
separately; do not silently change policy within a test.

When provider-contract work is separately opened, compare a small fully paged 2×2 batch with four
singleton searches under the same parameters. Record inventory timing differences and avoid claiming
a perfect live counterfactual. Verify list behavior, result attribution, date mapping, pagination,
error handling, and absent-pair interpretation. Do not probe for an undocumented maximum or reopen
generic authenticated access feasibility. No such calls were performed for this amendment.

The parent and architect independently ran tiny standalone grouping checks: six pairs packed into
one rectangle, the sparse three-pair set into two, and completing a rectangle reduced batch count.
Exact pair equality/no-overlap assertions passed. These are offline arithmetic demonstrations of the
proposed packer, not implemented 2C output or measured provider behavior.
