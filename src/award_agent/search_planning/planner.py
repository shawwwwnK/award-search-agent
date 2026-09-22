"""Deterministic Milestone 2C search-strategy compiler.

The compiler consumes frozen endpoint and gateway-discovery evidence.  It does
not propose airports, call a model/provider, or claim that component queries
form a bookable itinerary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any, Protocol, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from award_agent.domain import (
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    LocationRef,
    SearchMode,
)
from award_agent.search_planning.airport_selection_policy import (
    AirportSelectionCapPolicy,
    airport_selection_cap_policy_digest,
    context_for_resolved_location,
)
from award_agent.search_planning.airport_selector import (
    AIRPORT_SELECTOR_ADAPTER_VERSION,
    AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION,
    AIRPORT_SELECTOR_PROMPT_VERSION,
    AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256,
    AirportSelectionRecord,
    airport_selection_distance_policy_digest,
    airport_selection_record_digest,
    validate_airport_selection_proposal,
)
from award_agent.search_planning.compilation_contracts import (
    CompilationCoverage,
    CompiledPlanIdentity,
    CompiledSearchPlan,
    CompilerStructuralLimitKind,
    CompilerStructuralLimitReceipt,
    EndpointPair,
    EndpointSelectionBinding,
    EndpointSelectionProjection,
    GatewayDiscoveryCompilationReceipt,
    IdentifiedDeferredConstraint,
    LogicalAwardQuery,
    M2ASelectionRecordSource,
    MandatoryQueryUse,
    PlanningAirportIdentity,
    PositioningDependency,
    PositioningPolicyReceipt,
    RelationshipDisposition,
    RelationshipDispositionKind,
    RelationshipIdentity,
    SearchPlanningInput,
    SearchPlanningOutcome,
    SearchPlanningResult,
    SourceCandidateIdentity,
    SourceScopeIdentity,
    StrategyCompilationIssue,
    StrategyCompilationIssueCode,
    StrategyQueryUse,
    StrategySupportAlternative,
    SupplementalDateDerivation,
    SupplementalStrategy,
    SupplementalStrategyType,
    SupplementalValidationKind,
    SupplementalValidationObligation,
    accepted_relationship_ledger_digest,
    relationship_disposition_ledger_digest,
)
from award_agent.search_planning.contracts import (
    AirportSelection,
    AirportSelectionKind,
    CatalogKnowledgeReceipt,
    DateBasis,
    DateEnvelope,
    DeferredConstraintObligation,
    EndpointProbe,
    FilterObligation,
    FilterObligationKind,
    FreshnessClass,
    GroundedEndpointResult,
    LocationResolutionStatus,
    ResolvedLocation,
    ResultValidationKind,
    ResultValidationObligation,
    SelectedAirport,
)
from award_agent.search_planning.distance_consistency import CityAirportDistanceConsistency
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryCatalogRepository,
    GatewayDiscoveryOutcome,
    GatewayDiscoveryReplayError,
    GatewayDiscoveryResult,
    replay_gateway_discovery_result,
)
from award_agent.search_planning.knowledge import (
    Airport,
    PlanningKnowledgeRepository,
)
from award_agent.search_planning.locations import ground_endpoint
from award_agent.search_planning.market_policy import (
    PlanningMarketPolicy,
    planning_market_policy_digest,
)
from award_agent.search_planning.policy import PlanningPolicy

_CANONICALIZATION_VERSION = "effective-request-canonical-json-v1"
_DIGEST_ALGORITHM_VERSION = "sha256-v1"
_CORE_UNKNOWN_FIELDS = frozenset({"origin", "destination", "departure", "travelers"})


class StrategyCompilationRepository(PlanningKnowledgeRepository, GatewayDiscoveryCatalogRepository, Protocol):
    """Catalog repository surface required by compilation and 2B replay."""

    @property
    def knowledge_receipt(self) -> CatalogKnowledgeReceipt: ...

    def airport(self, airport_id: str) -> Airport | None: ...


class _Bundle:
    def __init__(
        self,
        *,
        relationship_id: str,
        strategy_type: SupplementalStrategyType,
        source_candidate: SourceCandidateIdentity,
        source_relationship: RelationshipIdentity,
        source_scope: SourceScopeIdentity | None,
        pairs: tuple[EndpointPair, ...],
        reason: str,
        uncertainty: str | None,
        market_comparison: Any,
        query_specs: tuple[tuple[str, str, str, int, int], ...],
        positioning_specs_by_pair: dict[
            tuple[str, str], tuple[tuple[str, str, str, str], ...]
        ],
    ) -> None:
        self.relationship_id = relationship_id
        self.strategy_type = strategy_type
        self.source_candidate = source_candidate
        self.source_relationship = source_relationship
        self.source_scope = source_scope
        self.pairs = pairs
        self.reason = reason
        self.uncertainty = uncertainty
        self.market_comparison = market_comparison
        self.query_specs = query_specs
        self.positioning_specs_by_pair = positioning_specs_by_pair

    @property
    def positioning_specs(self) -> tuple[tuple[str, str, str, str], ...]:
        return tuple(
            dict.fromkeys(
                spec
                for specs in self.positioning_specs_by_pair.values()
                for spec in specs
            )
        )


def plan_searches(
    planning_input: SearchPlanningInput,
    *,
    repository: StrategyCompilationRepository,
    policy: PlanningPolicy,
    market_policy: PlanningMarketPolicy,
    selection_cap_policy: AirportSelectionCapPolicy | None = None,
    selection_distance_policy: CityAirportDistanceConsistency | None = None,
) -> SearchPlanningResult:
    """Compile frozen request/evidence into a bounded provider-neutral plan."""

    try:
        planning_input = SearchPlanningInput.model_validate(
            planning_input.model_dump(mode="python", round_trip=True)
        )
        policy = PlanningPolicy.model_validate(policy.model_dump(mode="python", round_trip=True))
    except ValidationError as exc:
        return _failure(StrategyCompilationIssueCode.COMPILER_CONTRACT_FAILURE, "input", str(exc))

    request = planning_input.envelope.effective_request
    digest = effective_request_digest(request)
    admission = _admission_failure(planning_input, policy, digest)
    if admission is not None:
        return admission
    if not isinstance(repository.knowledge_receipt, CatalogKnowledgeReceipt):
        return _failure(
            StrategyCompilationIssueCode.UNSUPPORTED_KNOWLEDGE_SOURCE,
            "binding",
            "strategy compilation requires a catalog-backed knowledge receipt",
        )

    try:
        projections, binding = _resolve_endpoint_source(
            planning_input,
            repository,
            policy,
            selection_cap_policy,
            selection_distance_policy,
        )
    except (ValueError, ValidationError) as exc:
        return _failure(
            StrategyCompilationIssueCode.ENDPOINT_SELECTION_BINDING_MISMATCH,
            "binding",
            str(exc),
        )

    origins = _unique_selected(projections, "origin")
    destinations = _unique_selected(projections, "destination")
    pairs = tuple((origin, destination) for origin in origins for destination in destinations)
    mandatory_pair_count = len(pairs)
    if mandatory_pair_count > policy.max_structural_endpoint_pairs:
        return _structural_limit_failure(
            CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT,
            mandatory_pair_count,
            policy.max_structural_endpoint_pairs,
        )

    try:
        probes, mandatory_queries, mandatory_uses = _mandatory_baseline(pairs, request, repository)
    except (ValueError, OverflowError) as exc:
        return _failure(
            StrategyCompilationIssueCode.COMPILER_CONTRACT_FAILURE,
            "compilation",
            str(exc),
        )

    gateway = planning_input.gateway_discovery_result
    try:
        _validate_gateway_binding(planning_input, binding, origins, destinations, request)
        replay_gateway_discovery_result(
            record=gateway,
            policy=market_policy,
            repository=repository,
        )
    except (ValueError, GatewayDiscoveryReplayError) as exc:
        return _failure(
            StrategyCompilationIssueCode.GATEWAY_REPLAY_FAILED,
            "replay",
            str(exc),
        )
    if gateway.outcome is GatewayDiscoveryOutcome.INPUT_ERROR:
        return _failure(
            StrategyCompilationIssueCode.GATEWAY_INPUT_BINDING_MISMATCH,
            "replay",
            "gateway discovery input-error evidence cannot yield a search plan",
        )

    bundles = _enumerate_bundles(gateway, origins, destinations)
    relationship_ledger_digest = accepted_relationship_ledger_digest(
        (
            bundle.relationship_id,
            bundle.source_relationship,
            bundle.source_candidate,
            bundle.source_scope,
            bundle.pairs,
        )
        for bundle in bundles
    )
    query_map = {query.query_id: query for query in mandatory_queries}
    query_semantics = {_query_semantic_key(query): query.query_id for query in mandatory_queries}
    dispositions: list[RelationshipDisposition] = []
    compiled_strategies: list[SupplementalStrategy] = []
    strategy_uses: list[StrategyQueryUse] = []
    alternatives: list[StrategySupportAlternative] = []
    dependencies: list[PositioningDependency] = []
    position_receipts: list[PositioningPolicyReceipt] = []
    derivations: list[SupplementalDateDerivation] = []

    suppressed: list[_Bundle] = []
    eligible: list[_Bundle] = []
    for bundle in bundles:
        if request.repositioning_allowed is False and bundle.positioning_specs:
            suppressed.append(bundle)
        else:
            eligible.append(bundle)
    for bundle in suppressed:
        dispositions.append(_disposition(bundle, RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL, ("positioning_explicitly_refused",)))
        position_receipts.append(
            PositioningPolicyReceipt(
                relationship_id=bundle.relationship_id,
                dependency_descriptions=tuple(f"{side}:{src}->{dst}" for side, src, dst, _ in bundle.positioning_specs),
                requested_permission=False,
                decision="suppressed_explicit_refusal",
            )
        )

    representable: list[_Bundle] = []
    materialized_candidates: dict[
        str, tuple[tuple[LogicalAwardQuery, SupplementalDateDerivation], ...]
    ] = {}
    for bundle in eligible:
        try:
            candidates = tuple(
                _supplemental_query_spec(spec, bundle, request, repository, policy)
                for spec in bundle.query_specs
            )
        except OverflowError:
            dispositions.append(
                _disposition(
                    bundle,
                    RelationshipDispositionKind.UNSUPPORTED_RULE,
                    ("supplemental_date_overflow",),
                )
            )
            continue
        except ValueError as exc:
            return _failure(
                StrategyCompilationIssueCode.COMPILER_CONTRACT_FAILURE,
                "compilation",
                f"supplemental relationship {bundle.relationship_id} is bound to invalid "
                f"catalog airport evidence: {exc}",
            )
        representable.append(bundle)
        materialized_candidates[bundle.relationship_id] = candidates

    for bundle in sorted(representable, key=lambda item: item.relationship_id):
        candidates = materialized_candidates[bundle.relationship_id]
        strategy_id = "supplemental:" + _digest({"relationship_id": bundle.relationship_id, "policy": _digest(policy)})
        support_ids: list[str] = []
        bundle_use_ids: list[str] = []
        role_names: list[str] = []
        query_ids: list[str] = []
        for sequence, ((candidate_query, derivation), spec) in enumerate(zip(candidates, bundle.query_specs, strict=True), start=1):
            semantic = _query_semantic_key(candidate_query)
            query_id = query_semantics.get(semantic, candidate_query.query_id)
            if query_id not in query_map:
                query_map[query_id] = candidate_query
                query_semantics[semantic] = query_id
            role = "access_main" if bundle.strategy_type is not SupplementalStrategyType.SCOPED_HUB else ("hub_first" if sequence == 1 else "hub_second")
            use_id = _digest({"strategy": strategy_id, "query": query_id, "role": role, "relationship": bundle.relationship_id})
            strategy_uses.append(
                StrategyQueryUse(
                    query_use_id=use_id,
                    strategy_id=strategy_id,
                    query_id=query_id,
                    role=cast(Any, role),
                    sequence=cast(Any, sequence),
                    source_relationship_id=bundle.relationship_id,
                    date_derivation_id=derivation.date_derivation_id,
                )
            )
            derivations.append(derivation)
            bundle_use_ids.append(use_id)
            query_ids.append(query_id)
            role_names.append("access_main" if role == "access_main" else ("first_component" if role == "hub_first" else "later_component"))
        for pair in bundle.pairs:
            support_id = _digest({"strategy": strategy_id, "pair": pair.model_dump(mode="json")})
            dependency_ids: list[str] = []
            pair_positioning_specs = bundle.positioning_specs_by_pair.get(
                (pair.origin_airport_fact_id, pair.destination_airport_fact_id), ()
            )
            for side, src, dst, access_relationship in pair_positioning_specs:
                dependency_id = _digest({"support": support_id, "side": side, "from": src, "to": dst, "access": access_relationship})
                dependencies.append(
                    PositioningDependency(
                        dependency_id=dependency_id,
                        support_id=support_id,
                        source_access_relationship_id=access_relationship,
                        side=cast(Any, side),
                        from_airport_fact_id=src,
                        to_airport_fact_id=dst,
                        requested_permission=request.repositioning_allowed,
                        field_provenance=_provenance_for(request, EffectiveField.REPOSITIONING),
                    )
                )
                dependency_ids.append(dependency_id)
            alternatives.append(
                StrategySupportAlternative(
                    support_id=support_id,
                    strategy_id=strategy_id,
                    original_origin_airport_fact_id=pair.origin_airport_fact_id,
                    original_destination_airport_fact_id=pair.destination_airport_fact_id,
                    query_use_ids=tuple(bundle_use_ids),
                    positioning_dependency_ids=tuple(dependency_ids),
                )
            )
            support_ids.append(support_id)
        validations = [
            SupplementalValidationObligation(kind=SupplementalValidationKind.ORIGINAL_DEPARTURE_COMPLIANCE, responsible_stage="future_result_or_journey_validation"),
            SupplementalValidationObligation(kind=SupplementalValidationKind.COMPLETE_JOURNEY_VALIDATION, responsible_stage="future_result_or_journey_validation"),
        ]
        if bundle.positioning_specs:
            validations.append(
                SupplementalValidationObligation(kind=SupplementalValidationKind.POSITIONING_FEASIBILITY, responsible_stage="future_result_or_journey_validation")
            )
        if bundle.strategy_type is SupplementalStrategyType.SCOPED_HUB or bundle.positioning_specs:
            validations.append(
                SupplementalValidationObligation(kind=SupplementalValidationKind.SEPARATE_TICKET_PERMISSION, responsible_stage="owner_review")
            )
        compiled_strategies.append(
            SupplementalStrategy(
                relationship_id=bundle.relationship_id,
                strategy_id=strategy_id,
                strategy_type=bundle.strategy_type,
                eligibility="conditional_permission" if bundle.positioning_specs and request.repositioning_allowed is None else "eligible",
                source_candidate=bundle.source_candidate,
                source_relationship=bundle.source_relationship,
                source_scope=bundle.source_scope,
                supported_original_endpoint_pairs=bundle.pairs,
                reason=bundle.reason,
                material_uncertainty=bundle.uncertainty,
                market_comparison=bundle.market_comparison,
                query_roles=cast(Any, tuple(role_names)),
                deferred_constraint_ids=tuple(
                    _constraint_obligation_id(text, request)
                    for text in request.hard_constraints
                ),
                support_alternative_ids=tuple(support_ids),
                required_validations=tuple(validations),
            )
        )
        decision = "conditional_research" if bundle.positioning_specs and request.repositioning_allowed is None else ("allowed_research" if bundle.positioning_specs else "not_required")
        position_receipts.append(
            PositioningPolicyReceipt(
                relationship_id=bundle.relationship_id,
                dependency_descriptions=tuple(f"{side}:{src}->{dst}" for side, src, dst, _ in bundle.positioning_specs),
                requested_permission=request.repositioning_allowed,
                decision=cast(Any, decision),
            )
        )
        dispositions.append(
            _disposition(
                bundle,
                RelationshipDispositionKind.COMPILED,
                ("compiled",),
                tuple(query_ids),
            )
        )

    issues = _reduced_issues(gateway, dispositions)
    disposition_digest = relationship_disposition_ledger_digest(dispositions)
    outcome = SearchPlanningOutcome.REDUCED_COVERAGE if issues else SearchPlanningOutcome.PLANNED
    obligations = _constraint_obligations(request, tuple(query_map))
    receipts = _structural_limit_receipts(
        policy,
        mandatory_pair_count,
    )
    coverage = CompilationCoverage(
        mandatory_required_pairs=mandatory_pair_count,
        mandatory_covered_pairs=len(mandatory_uses),
        mandatory_complete=len(mandatory_uses) == mandatory_pair_count,
        accepted_relationships=len(bundles),
        compiled_relationships=len(compiled_strategies),
        suppressed_positioning_refusal_relationships=sum(item.disposition is RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL for item in dispositions),
        unsupported_rule_relationships=sum(item.disposition is RelationshipDispositionKind.UNSUPPORTED_RULE for item in dispositions),
        discovery_outcome=gateway.outcome,
        market_coverage=gateway.market_coverage,
    )
    endpoint_binding_digest = _digest(binding)
    policy_digest = _digest(policy)
    market_policy_digest = planning_market_policy_digest(market_policy)
    compilation_binding_digest = _digest({
        "compilation_binding_version": "search-strategy-compilation-binding-v2",
        "request": digest,
        "endpoint": endpoint_binding_digest,
        "gateway_input": gateway.input_digest,
        "gateway_result": gateway.result_digest,
        "compiler_contract_version": "search-strategy-compilation-v3",
        "canonicalization_version": _CANONICALIZATION_VERSION,
        "digest_algorithm_version": _DIGEST_ALGORITHM_VERSION,
        "policy": policy_digest,
        "catalog": repository.knowledge_receipt,
        "market_policy_version": market_policy.policy_version,
        "market_policy_digest": market_policy_digest,
        "accepted_relationship_ledger": relationship_ledger_digest,
        "relationship_dispositions": disposition_digest,
        "route_topology_feature": "absent",
    })
    identity = CompiledPlanIdentity(
        session_id=planning_input.envelope.source.session_id,
        revision=planning_input.envelope.source.revision,
        effective_request_digest=digest,
        canonicalization_version=_CANONICALIZATION_VERSION,
        digest_algorithm_version=_DIGEST_ALGORITHM_VERSION,
        policy_version=policy.policy_version,
        policy_digest=policy_digest,
        catalog_receipt=repository.knowledge_receipt,
        endpoint_selection_binding=binding,
        gateway_result_digest=gateway.result_digest,
        gateway_input_digest=gateway.input_digest,
        market_policy_version=market_policy.policy_version,
        market_policy_digest=market_policy_digest,
        accepted_relationship_ledger_digest=relationship_ledger_digest,
        relationship_disposition_digest=disposition_digest,
        compilation_binding_digest=compilation_binding_digest,
    )
    discovery_receipt = GatewayDiscoveryCompilationReceipt(
        input_digest=gateway.input_digest,
        result_digest=gateway.result_digest,
        generation_status=gateway.generation_status,
        outcome=gateway.outcome,
        market_gate=gateway.market_gate,
        market_coverage=gateway.market_coverage,
        endpoint_assessment_decisions=gateway.endpoint_market_assessment_decisions,
        candidate_decisions=gateway.candidate_decisions,
        scope_decisions=tuple(scope for decision in gateway.candidate_decisions for scope in decision.scope_decisions),
        issues=gateway.issues,
        limitations=gateway.limitations,
    )
    airport_ids = {query.origin_airport_fact_id for query in query_map.values()} | {query.destination_airport_fact_id for query in query_map.values()}
    airport_directory = tuple(_airport_identity(airport_id, repository) for airport_id in sorted(airport_ids))
    plan_payload = {
        "identity": identity,
        "location_resolutions": tuple(item.resolution for item in projections),
        "endpoint_selections": projections,
        "endpoint_selection_binding": binding,
        "airport_directory": airport_directory,
        "mandatory_endpoint_probes": probes,
        "mandatory_query_uses": mandatory_uses,
        "supplemental_strategies": tuple(compiled_strategies),
        "logical_queries": tuple(query_map.values()),
        "strategy_query_uses": tuple(strategy_uses),
        "support_alternatives": tuple(alternatives),
        "constraint_obligations": obligations,
        "temporal_derivations": tuple(derivations),
        "positioning_dependencies": tuple(dependencies),
        "positioning_receipts": tuple(position_receipts),
        "relationship_dispositions": tuple(dispositions),
        "discovery_receipt": discovery_receipt,
        "coverage": coverage,
        "structural_limit_receipts": receipts,
        "issues": issues,
    }
    try:
        plan = CompiledSearchPlan.model_validate(
            {**plan_payload, "plan_digest": _digest(plan_payload)}
        )
    except (ValidationError, ValueError) as exc:
        return _failure(StrategyCompilationIssueCode.COMPILER_CONTRACT_FAILURE, "compilation", str(exc))
    return SearchPlanningResult(outcome=outcome, plan=plan, issues=issues, structural_limit_receipts=receipts)


def effective_request_digest(effective_request: EffectiveRequest) -> str:
    return _digest(_canonical_request_payload(effective_request))


def _canonical_request_payload(request: EffectiveRequest) -> dict[str, object]:
    payload = request.model_dump(mode="json", round_trip=True)
    for key in ("origins", "destinations"):
        values = payload.get(key)
        if isinstance(values, list):
            payload[key] = sorted(values, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    for key in ("cabins", "search_modes"):
        values = payload.get(key)
        if isinstance(values, list):
            payload[key] = sorted(values)
    return payload


def _admission_failure(inp: SearchPlanningInput, policy: PlanningPolicy, digest: str) -> SearchPlanningResult | None:
    request = inp.envelope.effective_request
    expected = inp.envelope.source.expected_effective_request_digest
    if expected is not None and expected != digest:
        return _failure("request_digest_mismatch", "input", "expected EffectiveRequest digest does not match")
    missing = []
    if not request.origins: missing.append("origin")
    if not request.destinations: missing.append("destination")
    if request.departure_window is None: missing.append("departure")
    if request.travelers is None: missing.append("travelers")
    if missing:
        return _failure("required_input_missing", "input", "missing required fields: " + ", ".join(missing), "unplannable")
    if request.conflicts or any(item.field in _CORE_UNKNOWN_FIELDS for item in request.unknowns):
        return _failure("unresolved_request", "input", "request retains a core unknown or active conflict", "unplannable")
    if SearchMode.AWARD not in request.search_modes:
        return _failure("award_mode_required", "input", "award search mode is required", "unplannable")
    return None


def _resolve_endpoint_source(
    inp: SearchPlanningInput,
    repository: StrategyCompilationRepository,
    policy: PlanningPolicy,
    cap_policy: AirportSelectionCapPolicy | None,
    distance_policy: CityAirportDistanceConsistency | None,
) -> tuple[tuple[EndpointSelectionProjection, ...], EndpointSelectionBinding]:
    source = inp.endpoint_source
    if isinstance(source, M2ASelectionRecordSource):
        if cap_policy is None or distance_policy is None:
            raise ValueError("M2A replay requires selection cap and distance policies")
        records = {(record.role, record.resolved_entity.entity_id): record for record in source.selection_records}
        source_kind = "m2a_replay"
    else:
        if cap_policy is not None or distance_policy is not None:
            raise ValueError("selector policies are only valid for M2A replay")
        records = {}
        source_kind = "direct_grounding"
    used: set[tuple[str, str]] = set()
    projections: list[EndpointSelectionProjection] = []
    request = inp.envelope.effective_request
    for role, locations, field in (("origin", request.origins, EffectiveField.ORIGIN), ("destination", request.destinations, EffectiveField.DESTINATION)):
        for location in _canonical_locations(locations):
            grounded = ground_endpoint(location, role, repository, policy)
            resolution = grounded.resolution
            selected: tuple[SelectedAirport, ...] | None = None
            selection_kind: AirportSelectionKind | None = None
            record_digest: str | None = None
            projection_source_kind = "direct_grounding"
            freshness = grounded.freshness
            entity_id = resolution.resolved_entity_id
            if entity_id is not None and source_kind == "m2a_replay":
                selection_record = records.get((cast(Any, role), entity_id))
                if selection_record is None:
                    raise ValueError("each geographic endpoint requires one M2A record")
                assert cap_policy is not None and distance_policy is not None
                replayed = _replay_selection_record(role, location, resolution, selection_record, cap_policy, distance_policy, repository, policy)
                selected = replayed.selection.airports if replayed.selection else None
                selection_kind = AirportSelectionKind.MODEL_PROPOSED
                record_digest = airport_selection_record_digest(selection_record)
                projection_source_kind = "m2a_replay"
                freshness = replayed.freshness
                used.add((role, entity_id))
            elif grounded.selection is not None:
                selected = grounded.selection.airports
                selection_kind = grounded.selection.kind
            if selected is None or selection_kind is None or resolution.status is not LocationResolutionStatus.RESOLVED:
                raise ValueError("endpoint source did not produce a complete grounded selection")
            projections.append(
                EndpointSelectionProjection(
                    role=cast(Any, role),
                    resolution=resolution,
                    airports=selected,
                    source_kind=cast(Any, projection_source_kind),
                    source_record_digest=record_digest,
                    selection_kind=selection_kind,
                    freshness=freshness,
                    field_provenance=_provenance_for(request, field),
                )
            )
    supplied = set(records)
    if supplied != used:
        raise ValueError("endpoint records must be consumed exactly once")
    digests = tuple(sorted(item.source_record_digest for item in projections if item.source_record_digest is not None))
    binding = EndpointSelectionBinding(
        source_kind=cast(Any, source_kind),
        selected_origin_ids=tuple(item.airport_id for item in _unique_selected(tuple(projections), "origin")),
        selected_destination_ids=tuple(item.airport_id for item in _unique_selected(tuple(projections), "destination")),
        record_digests=digests,
        cap_policy_version=cap_policy.policy_version if cap_policy else None,
        cap_policy_digest=airport_selection_cap_policy_digest(cap_policy) if cap_policy else None,
        distance_policy_version=distance_policy.policy_version if distance_policy else None,
        distance_policy_digest=airport_selection_distance_policy_digest(distance_policy) if distance_policy else None,
        catalog_release_identity=repository.knowledge_receipt,
        review_status=cast(Any, {"direct_grounding": "deterministic_approved_policy", "m2a_replay": "owner_qualified_model_proposed"}[source_kind]),
    )
    return tuple(projections), binding


def _replay_selection_record(role: str, location: LocationRef, resolution: ResolvedLocation, record: AirportSelectionRecord, cap_policy: AirportSelectionCapPolicy, distance_policy: CityAirportDistanceConsistency, repository: StrategyCompilationRepository, policy: PlanningPolicy) -> GroundedEndpointResult:
    context = context_for_resolved_location(resolution, repository)
    if record.resolved_entity != context or record.catalog_receipt != repository.knowledge_receipt:
        raise ValueError("M2A record context or catalog identity differs")
    if record.cap_policy_digest != airport_selection_cap_policy_digest(cap_policy) or record.distance_policy != distance_policy:
        raise ValueError("M2A selector policy identity differs")
    rebuilt = validate_airport_selection_proposal(role=cast(Any, role), context=context, cap_policy=cap_policy, distance_policy=distance_policy, proposal=record.proposal, model=record.model, prompt_version=record.prompt_version, repository=repository)
    if record.accepted_airports != rebuilt.accepted_airports or record.candidate_validations != rebuilt.candidate_validations or record.applicable_cap != rebuilt.applicable_cap or record.selector_adapter_version != AIRPORT_SELECTOR_ADAPTER_VERSION or record.prompt_version not in {AIRPORT_SELECTOR_PROMPT_VERSION, AIRPORT_SELECTOR_ORIGINAL_SIMPLE_PROMPT_VERSION} or record.response_schema_sha256 != AIRPORT_SELECTOR_RESPONSE_SCHEMA_SHA256:
        raise ValueError("M2A record does not reproduce")
    freshness = repository.freshness_for_source_ids(tuple({*resolution.evidence_source_ids, *(source for airport in record.accepted_airports for source in airport.airport_evidence_source_ids)}), max_source_evidence_age_days=policy.max_source_evidence_age_days)
    if freshness is FreshnessClass.STALE or not record.accepted_airports:
        raise ValueError("M2A replay is stale or empty")
    return GroundedEndpointResult(role=cast(Any, role), snapshot_id=repository.snapshot_id, freshness=freshness, resolution=resolution, selection=AirportSelection(kind=AirportSelectionKind.MODEL_PROPOSED, resolved_location=resolution, airports=record.accepted_airports))


def _mandatory_baseline(pairs: tuple[tuple[SelectedAirport, SelectedAirport], ...], request: EffectiveRequest, repository: StrategyCompilationRepository) -> tuple[tuple[EndpointProbe, ...], tuple[LogicalAwardQuery, ...], tuple[MandatoryQueryUse, ...]]:
    assert request.departure_window is not None and request.travelers is not None
    probes: list[EndpointProbe] = []
    queries: list[LogicalAwardQuery] = []
    uses: list[MandatoryQueryUse] = []
    for origin, destination in pairs:
        envelope = _date_envelope(request, repository, origin.airport_id, 0, 0, DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL)
        query = _logical_query(origin.airport_id, destination.airport_id, envelope, request)
        probe_id = "endpoint-market:" + _digest({"origin": origin.airport_id, "destination": destination.airport_id, "date": envelope})
        probes.append(EndpointProbe(probe_id=probe_id, origin_endpoint=origin, destination_endpoint=destination, date_envelope=envelope, requested_cabins=query.requested_cabins, traveler_count=request.travelers))
        queries.append(query)
        uses.append(MandatoryQueryUse(probe_id=probe_id, query_id=query.query_id))
    return tuple(probes), tuple(queries), tuple(uses)


def _logical_query(origin_id: str, destination_id: str, envelope: DateEnvelope, request: EffectiveRequest) -> LogicalAwardQuery:
    assert request.travelers is not None
    validations = (ResultValidationObligation(kind=ResultValidationKind.MINIMUM_AWARD_SEATS, minimum_seats=request.travelers, field_provenance=_provenance_for(request, EffectiveField.TRAVELERS)),)
    requested_cabins = tuple(sorted(set(request.cabins), key=lambda item: item.value))
    filters = (
        (
            FilterObligation(
                kind=FilterObligationKind.CABIN_AVAILABLE_IN,
                values=tuple(cabin.value for cabin in requested_cabins),
                origin="user_requirement",
                field_provenance=_provenance_for(request, EffectiveField.CABIN),
            ),
        )
        if requested_cabins
        else ()
    )
    query_payload = {
        "origin_airport_fact_id": origin_id,
        "destination_airport_fact_id": destination_id,
        "scope": "endpoint_market",
        "date_envelope": envelope,
        "requested_cabins": requested_cabins,
        "award_mode": "award",
        "connection_semantics": "provider_returned_connections_allowed",
        "filter_obligations": filters,
        "result_validation_obligations": validations,
    }
    return LogicalAwardQuery(
        query_id="logical-award:" + _digest(_query_identity_payload(query_payload)),
        origin_airport_fact_id=origin_id,
        destination_airport_fact_id=destination_id,
        date_envelope=envelope,
        requested_cabins=requested_cabins,
        filter_obligations=filters,
        result_validation_obligations=validations,
    )


def _validate_gateway_binding(inp: SearchPlanningInput, binding: EndpointSelectionBinding, origins: tuple[SelectedAirport, ...], destinations: tuple[SelectedAirport, ...], request: EffectiveRequest) -> None:
    gateway_input = inp.gateway_discovery_result.input
    if (
        _canonical_selected_airports(gateway_input.origin_endpoints)
        != _canonical_selected_airports(origins)
        or _canonical_selected_airports(gateway_input.destination_endpoints)
        != _canonical_selected_airports(destinations)
    ):
        raise ValueError("gateway endpoint input differs from compiled endpoint selection")
    assert request.departure_window is not None
    if gateway_input.outbound_date.start != request.departure_window.start or gateway_input.outbound_date.end != request.departure_window.end or gateway_input.outbound_date.effective_window_precision != request.departure_window.precision.value or gateway_input.outbound_date.timezone != request.context.timezone:
        raise ValueError("gateway outbound date input differs from EffectiveRequest")
    expected_digests = tuple(sorted(binding.record_digests))
    if gateway_input.upstream_selection_record_digests != expected_digests:
        raise ValueError("gateway upstream selection digests differ")
    bindings = {item.upstream_record_id: item.record_digest for item in inp.upstream_selection_id_bindings}
    if (
        gateway_input.upstream_selection_record_ids or inp.upstream_selection_id_bindings
    ) and (
        tuple(gateway_input.upstream_selection_record_ids) != tuple(bindings)
        or tuple(sorted(bindings.values())) != expected_digests
    ):
        raise ValueError("gateway upstream selection ID bindings differ")


def _canonical_selected_airports(
    airports: tuple[SelectedAirport, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            json.dumps(
                airport.model_dump(mode="json", round_trip=True),
                sort_keys=True,
                separators=(",", ":"),
            )
            for airport in airports
        )
    )


def _enumerate_bundles(gateway: GatewayDiscoveryResult, origins: tuple[SelectedAirport, ...], destinations: tuple[SelectedAirport, ...]) -> tuple[_Bundle, ...]:
    origin_by_iata = {item.airport_iata: item for item in origins}
    destination_by_iata = {item.airport_iata: item for item in destinations}
    origin_access = {item.airport.airport_iata: item for item in gateway.accepted_origin_access_gateways}
    destination_access = {item.airport.airport_iata: item for item in gateway.accepted_destination_access_gateways}
    decision_index = {(item.pool, item.proposed_airport_iata): item.candidate_index for item in gateway.candidate_decisions if item.accepted}
    bundles: list[_Bundle] = []
    access_relationships: dict[tuple[str, str, str, str], str] = {}
    for candidate in gateway.accepted_origin_access_gateways:
        idx = decision_index[("origin_access_gateways", candidate.airport.airport_iata)]
        source = _source_candidate(gateway, "origin_access_gateways", idx, candidate.airport)
        for origin_iata in candidate.supported_original_origin_iata_codes:
            for destination_iata in candidate.applicable_original_destination_iata_codes:
                origin, destination = origin_by_iata[origin_iata], destination_by_iata[destination_iata]
                relationship = RelationshipIdentity(relationship_type=SupplementalStrategyType.ORIGIN_ACCESS, gateway_result_digest=gateway.result_digest, pool="origin_access_gateways", candidate_index=idx, candidate_airport_fact_id=candidate.airport.airport_id, original_origin_airport_fact_id=origin.airport_id, original_destination_airport_fact_id=destination.airport_id)
                rel_id = _digest(relationship)
                access_relationships[
                    ("origin", candidate.airport.airport_iata, origin_iata, destination_iata)
                ] = rel_id
                pair = EndpointPair(origin_airport_fact_id=origin.airport_id, destination_airport_fact_id=destination.airport_id)
                bundles.append(_Bundle(relationship_id=rel_id, strategy_type=SupplementalStrategyType.ORIGIN_ACCESS, source_candidate=source, source_relationship=relationship, source_scope=None, pairs=(pair,), reason=candidate.reason, uncertainty=candidate.material_uncertainty, market_comparison=candidate.market_comparison, query_specs=((candidate.airport.airport_id, destination.airport_id, "access_main", -1, 2),), positioning_specs_by_pair={(origin.airport_id, destination.airport_id): (("origin", origin.airport_id, candidate.airport.airport_id, rel_id),)}))
    for destination_candidate in gateway.accepted_destination_access_gateways:
        idx = decision_index[("destination_access_gateways", destination_candidate.airport.airport_iata)]
        source = _source_candidate(gateway, "destination_access_gateways", idx, destination_candidate.airport)
        for destination_iata in destination_candidate.supported_original_destination_iata_codes:
            for origin_iata in destination_candidate.applicable_original_origin_iata_codes:
                origin, destination = origin_by_iata[origin_iata], destination_by_iata[destination_iata]
                relationship = RelationshipIdentity(relationship_type=SupplementalStrategyType.DESTINATION_ACCESS, gateway_result_digest=gateway.result_digest, pool="destination_access_gateways", candidate_index=idx, candidate_airport_fact_id=destination_candidate.airport.airport_id, original_origin_airport_fact_id=origin.airport_id, original_destination_airport_fact_id=destination.airport_id)
                rel_id = _digest(relationship)
                access_relationships[
                    (
                        "destination",
                        destination_candidate.airport.airport_iata,
                        destination_iata,
                        origin_iata,
                    )
                ] = rel_id
                pair = EndpointPair(origin_airport_fact_id=origin.airport_id, destination_airport_fact_id=destination.airport_id)
                bundles.append(_Bundle(relationship_id=rel_id, strategy_type=SupplementalStrategyType.DESTINATION_ACCESS, source_candidate=source, source_relationship=relationship, source_scope=None, pairs=(pair,), reason=destination_candidate.reason, uncertainty=destination_candidate.material_uncertainty, market_comparison=destination_candidate.market_comparison, query_specs=((origin.airport_id, destination_candidate.airport.airport_id, "access_main", 0, 0),), positioning_specs_by_pair={(origin.airport_id, destination.airport_id): (("destination", destination_candidate.airport.airport_id, destination.airport_id, rel_id),)}))
    for hub_candidate in gateway.accepted_intermediate_hubs:
        idx = decision_index[("intermediate_hubs", hub_candidate.airport.airport_iata)]
        source = _source_candidate(gateway, "intermediate_hubs", idx, hub_candidate.airport)
        decision = next(
            item
            for item in gateway.candidate_decisions
            if item.pool == "intermediate_hubs" and item.candidate_index == idx
        )
        accepted_scope_indexes = tuple(
            item.scope_index for item in decision.scope_decisions if item.accepted
        )
        if len(accepted_scope_indexes) != len(hub_candidate.scopes):
            raise ValueError("accepted hub scopes do not align with source scope decisions")
        for source_scope_index, scope in zip(
            accepted_scope_indexes, hub_candidate.scopes, strict=True
        ):
            for origin_ref in scope.origin_side:
                for destination_ref in scope.destination_side:
                    origin_airport = origin_by_iata[origin_ref.airport_iata] if origin_ref.kind == "original_origin" else origin_access[origin_ref.airport_iata].airport
                    destination_airport = destination_by_iata[destination_ref.airport_iata] if destination_ref.kind == "original_destination" else destination_access[destination_ref.airport_iata].airport
                    supported_origins = (origin_ref.airport_iata,) if origin_ref.kind == "original_origin" else origin_access[origin_ref.airport_iata].supported_original_origin_iata_codes
                    supported_destinations = (destination_ref.airport_iata,) if destination_ref.kind == "original_destination" else destination_access[destination_ref.airport_iata].supported_original_destination_iata_codes
                    pairs = tuple(EndpointPair(origin_airport_fact_id=origin_by_iata[o].airport_id, destination_airport_fact_id=destination_by_iata[d].airport_id) for o in supported_origins for d in supported_destinations)
                    relationship = RelationshipIdentity(relationship_type=SupplementalStrategyType.SCOPED_HUB, gateway_result_digest=gateway.result_digest, pool="intermediate_hubs", candidate_index=idx, candidate_airport_fact_id=hub_candidate.airport.airport_id, scope_index=source_scope_index, typed_origin_kind=origin_ref.kind, typed_origin_iata=origin_ref.airport_iata, typed_destination_kind=destination_ref.kind, typed_destination_iata=destination_ref.airport_iata)
                    rel_id = _digest(relationship)
                    scope_identity = SourceScopeIdentity(scope_index=source_scope_index, typed_origin_kind=origin_ref.kind, typed_origin_iata=origin_ref.airport_iata, typed_destination_kind=destination_ref.kind, typed_destination_iata=destination_ref.airport_iata)
                    specs_by_pair: dict[tuple[str, str], tuple[tuple[str, str, str, str], ...]] = {}
                    for original_origin in supported_origins:
                        for original_destination in supported_destinations:
                            pair_specs: list[tuple[str, str, str, str]] = []
                            if origin_ref.kind == "origin_access_gateway":
                                pair_specs.append(("origin", origin_by_iata[original_origin].airport_id, origin_airport.airport_id, access_relationships[("origin", origin_ref.airport_iata, original_origin, original_destination)]))
                            if destination_ref.kind == "destination_access_gateway":
                                pair_specs.append(("destination", destination_airport.airport_id, destination_by_iata[original_destination].airport_id, access_relationships[("destination", destination_ref.airport_iata, original_destination, original_origin)]))
                            specs_by_pair[(origin_by_iata[original_origin].airport_id, destination_by_iata[original_destination].airport_id)] = tuple(pair_specs)
                    bundles.append(_Bundle(relationship_id=rel_id, strategy_type=SupplementalStrategyType.SCOPED_HUB, source_candidate=source, source_relationship=relationship, source_scope=scope_identity, pairs=pairs, reason=scope.reason or hub_candidate.reason, uncertainty=hub_candidate.material_uncertainty, market_comparison=hub_candidate.market_comparison, query_specs=((origin_airport.airport_id, hub_candidate.airport.airport_id, "hub_first", -1 if origin_ref.kind == "origin_access_gateway" else 0, 2 if origin_ref.kind == "origin_access_gateway" else 0), (hub_candidate.airport.airport_id, destination_airport.airport_id, "hub_second", -1, 2)), positioning_specs_by_pair=specs_by_pair))
    return tuple(bundles)


def _source_candidate(gateway: GatewayDiscoveryResult, pool: str, index: int, airport: SelectedAirport) -> SourceCandidateIdentity:
    return SourceCandidateIdentity(gateway_result_digest=gateway.result_digest, pool=cast(Any, pool), candidate_index=index, airport_iata=airport.airport_iata, airport_fact_id=airport.airport_id)


def _supplemental_query_spec(spec: tuple[str, str, str, int, int], bundle: _Bundle, request: EffectiveRequest, repository: StrategyCompilationRepository, policy: PlanningPolicy) -> tuple[LogicalAwardQuery, SupplementalDateDerivation]:
    origin, destination, role, start_offset, end_offset = spec
    basis = DateBasis.FIRST_ORIGIN_AIRPORT_LOCAL if start_offset == 0 and end_offset == 0 else DateBasis.LATER_COMPONENT_ORIGIN_AIRPORT_LOCAL
    envelope = _date_envelope(request, repository, origin, start_offset, end_offset, basis)
    query = _logical_query(origin, destination, envelope, request)
    assert request.departure_window is not None
    derivation_id = _digest({"strategy": bundle.relationship_id, "role": role, "origin": origin, "start": envelope.start, "end": envelope.end, "policy": policy.policy_version})
    derivation = SupplementalDateDerivation(date_derivation_id=derivation_id, strategy_id="supplemental:" + _digest({"relationship_id": bundle.relationship_id, "policy": _digest(policy)}), query_role=cast(Any, role), origin_airport_fact_id=origin, source_window_start=request.departure_window.start, source_window_end=request.departure_window.end, source_window_precision=request.departure_window.precision.value, field_provenance=_provenance_for(request, EffectiveField.DEPARTURE), start_offset_days=start_offset, end_offset_days=end_offset, derived_start=envelope.start, derived_end=envelope.end, basis=basis, timezone=envelope.timezone, policy_version=policy.policy_version)
    return query, derivation


def _date_envelope(request: EffectiveRequest, repository: StrategyCompilationRepository, origin_id: str, start_offset: int, end_offset: int, basis: DateBasis) -> DateEnvelope:
    assert request.departure_window is not None
    airport = repository.airport(origin_id)
    if airport is None or not airport.timezone:
        raise ValueError("query origin airport has no catalog timezone")
    try:
        ZoneInfo(airport.timezone)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("query origin airport has an invalid catalog timezone") from exc
    return DateEnvelope(start=request.departure_window.start + timedelta(days=start_offset), end=request.departure_window.end + timedelta(days=end_offset), basis=basis, timezone=airport.timezone, effective_window_precision=request.departure_window.precision.value, field_provenance=_provenance_for(request, EffectiveField.DEPARTURE))


def _disposition(
    bundle: _Bundle,
    kind: RelationshipDispositionKind,
    reasons: tuple[str, ...],
    query_ids: tuple[str, ...] = (),
) -> RelationshipDisposition:
    return RelationshipDisposition(
        relationship_id=bundle.relationship_id,
        disposition=kind,
        source_relationship=bundle.source_relationship,
        source_candidate=bundle.source_candidate,
        source_scope=bundle.source_scope,
        supported_original_endpoint_pairs=bundle.pairs,
        reason_codes=reasons,
        query_ids=query_ids,
    )


def _constraint_obligations(request: EffectiveRequest, query_ids: tuple[str, ...]) -> tuple[IdentifiedDeferredConstraint, ...]:
    provenance = _provenance_for(request, EffectiveField.HARD_CONSTRAINTS)
    return tuple(IdentifiedDeferredConstraint(obligation_id=_constraint_obligation_id(text, request), obligation=DeferredConstraintObligation(text=text, field_provenance=provenance), applies_to_query_ids=query_ids) for text in request.hard_constraints)


def _constraint_obligation_id(text: str, request: EffectiveRequest) -> str:
    return _digest(
        {
            "text": text,
            "provenance": _provenance_for(request, EffectiveField.HARD_CONSTRAINTS),
        }
    )


def _structural_limit_receipts(
    policy: PlanningPolicy,
    pair_count: int,
) -> tuple[CompilerStructuralLimitReceipt, ...]:
    values = (
        (
            CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT,
            policy.max_structural_endpoint_pairs,
            pair_count,
        ),
    )
    return tuple(
        CompilerStructuralLimitReceipt(
            kind=kind,
            classification="compiler_structural_safety",
            limit=limit,
            observed=observed,
            disposition="within_limit",
        )
        for kind, limit, observed in values
    )


def _reduced_issues(gateway: GatewayDiscoveryResult, dispositions: list[RelationshipDisposition]) -> tuple[StrategyCompilationIssue, ...]:
    issues: list[StrategyCompilationIssue] = []
    if gateway.outcome in {GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE, GatewayDiscoveryOutcome.REJECTED_ALL, GatewayDiscoveryOutcome.GENERATION_FAILURE, GatewayDiscoveryOutcome.VALIDATION_FAILURE}:
        issues.append(StrategyCompilationIssue(code=f"gateway_{gateway.outcome.value}", stage="compilation", severity="reduced_coverage", message=f"gateway discovery ended with {gateway.outcome.value}; mandatory coverage is retained"))
    for item in dispositions:
        if item.disposition is RelationshipDispositionKind.UNSUPPORTED_RULE:
            issues.append(StrategyCompilationIssue(code=item.reason_codes[0], stage="compilation", severity="reduced_coverage", message="accepted supplemental relationship was not materialized", source_relationship_id=item.relationship_id))
    return tuple(issues)


def _airport_identity(airport_id: str, repository: StrategyCompilationRepository) -> PlanningAirportIdentity:
    airport = repository.airport(airport_id)
    if airport is None:
        raise ValueError("logical query cites an airport absent from the catalog")
    return PlanningAirportIdentity(airport_id=airport.airport_id, airport_iata=airport.iata, timezone=airport.timezone, evidence_source_ids=airport.source_ids)


def _structural_limit_failure(kind: CompilerStructuralLimitKind, observed: int, limit: int) -> SearchPlanningResult:
    code = {
        CompilerStructuralLimitKind.ENDPOINT_PAIR_CROSS_PRODUCT: StrategyCompilationIssueCode.ENDPOINT_PAIR_STRUCTURAL_LIMIT_EXCEEDED,
    }[kind]
    receipt = CompilerStructuralLimitReceipt(
        kind=kind,
        classification="compiler_structural_safety",
        limit=limit,
        observed=observed,
        disposition="exceeded",
    )
    issue = StrategyCompilationIssue(
        code=code,
        stage="compilation",
        severity="unplannable",
        message=(
            f"{kind.value} observed {observed}, exceeding the compiler_structural_safety "
            f"limit {limit}; "
            "no plan was compiled"
        ),
    )
    return SearchPlanningResult(outcome=SearchPlanningOutcome.UNPLANNABLE, issues=(issue,), structural_limit_receipts=(receipt,))


def _failure(code: StrategyCompilationIssueCode | str, stage: str, message: str, severity: str = "evidence_failure") -> SearchPlanningResult:
    issue = StrategyCompilationIssue(code=code, stage=cast(Any, stage), severity=cast(Any, severity), message=message)
    outcome = SearchPlanningOutcome.UNPLANNABLE if severity == "unplannable" else SearchPlanningOutcome.EVIDENCE_FAILURE
    return SearchPlanningResult(outcome=outcome, issues=(issue,))


def _unique_selected(projections: tuple[EndpointSelectionProjection, ...], role: str) -> tuple[SelectedAirport, ...]:
    result: dict[str, SelectedAirport] = {}
    for projection in projections:
        if projection.role == role:
            for airport in projection.airports:
                result.setdefault(airport.airport_id, airport)
    return tuple(result.values())


def _canonical_locations(locations: Iterable[LocationRef]) -> tuple[LocationRef, ...]:
    return tuple(sorted(locations, key=lambda item: (item.kind.value, item.value.casefold(), item.raw_text)))


def _provenance_for(request: EffectiveRequest, field: EffectiveField) -> FieldProvenance | None:
    return next((item for item in request.field_provenance if item.field is field), None)


def _query_semantic_key(query: LogicalAwardQuery) -> str:
    return _digest(_query_identity_payload(query))


def _query_identity_payload(query: LogicalAwardQuery | dict[str, Any]) -> dict[str, Any]:
    def field(name: str) -> Any:
        return query[name] if isinstance(query, dict) else getattr(query, name)

    envelope = field("date_envelope")
    envelope_value = (
        envelope
        if isinstance(envelope, dict)
        else envelope.model_dump(mode="json", round_trip=True)
    )
    filters = field("filter_obligations")
    validations = field("result_validation_obligations")

    def without_provenance(item: Any) -> dict[str, Any]:
        value = (
            dict(item)
            if isinstance(item, dict)
            else item.model_dump(mode="json", round_trip=True)
        )
        value.pop("field_provenance", None)
        return value

    return {
        "query_identity_version": "logical-award-query-semantics-v1",
        "origin_airport_fact_id": field("origin_airport_fact_id"),
        "destination_airport_fact_id": field("destination_airport_fact_id"),
        "scope": getattr(field("scope"), "value", field("scope")),
        "date_envelope": {
            key: envelope_value[key]
            for key in ("start", "end", "inclusive", "basis", "timezone")
        },
        "requested_cabins": [
            getattr(cabin, "value", cabin) for cabin in field("requested_cabins")
        ],
        "award_mode": field("award_mode"),
        "connection_semantics": field("connection_semantics"),
        "filter_obligations": [without_provenance(item) for item in filters],
        "result_validation_obligations": [
            without_provenance(item) for item in validations
        ],
    }


def _digest(value: Any) -> str:
    value = _canonical_json_value(value)
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _canonical_json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", round_trip=True)
    if isinstance(value, dict):
        return {str(key): _canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, (date,)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


__all__ = ["StrategyCompilationRepository", "effective_request_digest", "plan_searches"]
