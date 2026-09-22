"""Focused offline checks for the Milestone 2C compiler boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    DateWindow,
    DateWindowPrecision,
    EffectiveRequest,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
)
from award_agent.search_planning import (
    DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
    AcceptedIntermediateHub,
    AcceptedIntermediateHubScope,
    AcceptedOriginAccessGateway,
    CatalogKnowledgeRepository,
    CompiledSearchPlan,
    DirectGroundingSource,
    GatewayCandidateDecision,
    GatewayDiscoveryInput,
    GatewayMarketComparison,
    GatewayMarketComparisonStatus,
    GatewayOutboundDateContext,
    GatewayScopeDecision,
    LogicalAwardQuery,
    PlanHandoffStatus,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningInput,
    SearchPlanningOutcome,
    SelectedAirport,
    check_plan_handoff,
    discover_gateway_candidates,
    effective_request_digest,
    load_default_planning_market_policy,
    plan_searches,
)
from award_agent.search_planning.gateway_discovery import GatewayDiscoveryResult
from award_agent.search_planning.gateway_generator import (
    GatewayScopeDestinationReference,
    GatewayScopeOriginReference,
)
from award_agent.search_planning.locations import ground_endpoint
from award_agent.search_planning.planner import _enumerate_bundles

_CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")


def _request() -> EffectiveRequest:
    origins = (LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),)
    destinations = (LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX"),)
    return EffectiveRequest(
        raw_text="Two award seats from SFO to LAX October 5 through 7.",
        context=RequestContext(reference_date=date(2026, 9, 19), timezone="America/Los_Angeles"),
        travelers=2,
        origins=origins,
        destinations=destinations,
        departure_window=DateWindow(start=date(2026, 10, 5), end=date(2026, 10, 7), precision=DateWindowPrecision.WINDOW, raw_text="October 5 through 7"),
        search_modes=(SearchMode.AWARD,),
    )


def test_mandatory_only_policy_skip_compiles_complete_plan_offline() -> None:
    request = _request()
    envelope = PlanningInputEnvelope(
        source=PlanningSource(session_id="session-2c", revision=1),
        effective_request=request,
    )
    policy = PlanningPolicy()
    market_policy = load_default_planning_market_policy()
    with CatalogKnowledgeRepository(_CATALOG) as repository:
        origin_result = ground_endpoint(request.origins[0], "origin", repository, policy)
        destination_result = ground_endpoint(request.destinations[0], "destination", repository, policy)
        assert origin_result.selection is not None
        assert destination_result.selection is not None
        discovery_input = GatewayDiscoveryInput(
            origin_endpoints=origin_result.selection.airports,
            destination_endpoints=destination_result.selection.airports,
            outbound_date=GatewayOutboundDateContext(
                start=date(2026, 10, 5),
                end=date(2026, 10, 7),
                timezone="America/Los_Angeles",
                effective_window_precision="window",
            ),
        )
        gateway = discover_gateway_candidates(
            discovery_input=discovery_input,
            policy=market_policy,
            repository=repository,
            generator_factory=lambda: (_ for _ in ()).throw(AssertionError("policy skip called generator")),
            generator_configuration=DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
        )
        result = plan_searches(
            SearchPlanningInput(
                envelope=envelope,
                endpoint_source=DirectGroundingSource(),
                gateway_discovery_result=gateway,
            ),
            repository=repository,
            policy=policy,
            market_policy=market_policy,
        )

    assert result.outcome is SearchPlanningOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.coverage.mandatory_complete
    assert result.plan.endpoint_selection_binding.source_kind == "direct_grounding"
    assert result.plan.endpoint_selection_binding.review_status == (
        "deterministic_approved_policy"
    )
    assert result.plan.coverage.mandatory_required_pairs == 1
    assert len(result.plan.logical_queries) == 1
    assert not result.plan.supplemental_strategies
    assert result.plan.discovery_receipt.outcome.value == "policy_skipped"
    current = check_plan_handoff(
        result.plan,
        current_session_id="session-2c",
        current_revision=1,
        current_effective_request=request,
        expected_compilation_binding_digest=result.plan.identity.compilation_binding_digest,
    )
    stale_binding = check_plan_handoff(
        result.plan,
        current_session_id="session-2c",
        current_revision=1,
        current_effective_request=request,
        expected_compilation_binding_digest="0" * 64,
    )
    assert current.status is PlanHandoffStatus.CURRENT
    assert stale_binding.status is PlanHandoffStatus.STALE_PLANNING_BINDINGS

    same_semantics = result.plan.logical_queries[0].model_dump(
        mode="json", round_trip=True
    )
    same_semantics["date_envelope"]["effective_window_precision"] = "exact"
    assert LogicalAwardQuery.model_validate(same_semantics).query_id == (
        result.plan.logical_queries[0].query_id
    )

    forged_query = result.plan.model_dump(mode="json", round_trip=True)
    forged_query["logical_queries"][0]["destination_airport_fact_id"] = (
        forged_query["logical_queries"][0]["origin_airport_fact_id"]
    )
    with pytest.raises(ValidationError, match="logical query ID"):
        CompiledSearchPlan.model_validate(forged_query)

    forged_boundary = result.plan.model_dump(mode="json", round_trip=True)
    pair_receipt = next(
        item
        for item in forged_boundary["structural_limit_receipts"]
        if item["kind"] == "endpoint_pair_cross_product"
    )
    pair_receipt["observed"] = 0
    digest_payload = dict(forged_boundary)
    digest_payload.pop("plan_digest")
    forged_boundary["plan_digest"] = hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    with pytest.raises(ValidationError, match="structural-limit receipt does not recompute"):
        CompiledSearchPlan.model_validate(forged_boundary)

    exceeded_boundary = result.plan.model_dump(mode="json", round_trip=True)
    exceeded_receipt = next(
        item
        for item in exceeded_boundary["structural_limit_receipts"]
        if item["kind"] == "endpoint_pair_cross_product"
    )
    exceeded_receipt["limit"] = 0
    exceeded_receipt["disposition"] = "exceeded"
    _rehash_plan(exceeded_boundary)
    with pytest.raises(ValidationError, match="structural-limit receipt does not recompute"):
        CompiledSearchPlan.model_validate(exceeded_boundary)

    dumped_input = SearchPlanningInput(
        envelope=envelope,
        endpoint_source=DirectGroundingSource(),
        gateway_discovery_result=gateway,
    ).model_dump()
    assert "capability" not in dumped_input
    assert "capability_receipt" not in result.plan.identity.model_dump()


def test_effective_request_digest_canonicalizes_location_alternative_order() -> None:
    request = _request()
    sjc = LocationRef(kind=LocationKind.AIRPORT, value="SJC", raw_text="SJC")
    bur = LocationRef(kind=LocationKind.AIRPORT, value="BUR", raw_text="BUR")
    first = request.model_copy(
        update={
            "origins": (*request.origins, sjc),
            "destinations": (*request.destinations, bur),
        }
    )
    second = request.model_copy(
        update={
            "origins": tuple(reversed(first.origins)),
            "destinations": tuple(reversed(first.destinations)),
        }
    )
    assert effective_request_digest(first) == effective_request_digest(second)


def test_hub_keeps_source_scope_and_exact_pair_access_dependencies() -> None:
    def selected(iata: str) -> SelectedAirport:
        return SelectedAirport(
            airport_id=f"airport:{iata}",
            airport_iata=iata,
            airport_evidence_source_ids=(f"source:{iata}",),
        )

    origins = (selected("SFO"), selected("SJC"))
    destinations = (selected("NRT"), selected("KIX"))
    access = selected("LAX")
    hub = selected("YVR")
    comparison = GatewayMarketComparison(
        status=GatewayMarketComparisonStatus.MATCH,
        policy_market_id="test",
        model_asserted_market_id="test",
        advisory=False,
        message="matches",
    )
    gateway = GatewayDiscoveryResult.model_construct(
        result_digest="a" * 64,
        accepted_origin_access_gateways=(
            AcceptedOriginAccessGateway(
                airport=access,
                reason="alternate",
                market_comparison=comparison,
                supported_original_origin_iata_codes=("SFO", "SJC"),
                applicable_original_destination_iata_codes=("NRT", "KIX"),
            ),
        ),
        accepted_destination_access_gateways=(),
        accepted_intermediate_hubs=(
            AcceptedIntermediateHub(
                airport=hub,
                reason="hub",
                market_comparison=comparison,
                scopes=(
                    AcceptedIntermediateHubScope(
                        origin_side=(GatewayScopeOriginReference(kind="origin_access_gateway", airport_iata="LAX"),),
                        destination_side=(
                            GatewayScopeDestinationReference(kind="original_destination", airport_iata="NRT"),
                            GatewayScopeDestinationReference(kind="original_destination", airport_iata="KIX"),
                        ),
                        expanded_original_origin_iata_codes=("SFO", "SJC"),
                        expanded_original_destination_iata_codes=("KIX", "NRT"),
                    ),
                ),
            ),
        ),
        candidate_decisions=(
            GatewayCandidateDecision(
                pool="origin_access_gateways",
                candidate_index=0,
                proposed_airport_iata="LAX",
                accepted=True,
                market_comparison=comparison,
            ),
            GatewayCandidateDecision(
                pool="intermediate_hubs",
                candidate_index=2,
                proposed_airport_iata="YVR",
                accepted=True,
                market_comparison=comparison,
                scope_decisions=(
                    GatewayScopeDecision(scope_index=1, accepted=False),
                    GatewayScopeDecision(scope_index=3, accepted=True),
                ),
            ),
        ),
    )

    bundles = _enumerate_bundles(gateway, origins, destinations)
    access_relationships = {
        (
            bundle.source_relationship.original_origin_airport_fact_id,
            bundle.source_relationship.original_destination_airport_fact_id,
        ): bundle.relationship_id
        for bundle in bundles
        if bundle.strategy_type.value == "origin_access"
    }
    hub_bundles = [bundle for bundle in bundles if bundle.strategy_type.value == "scoped_hub"]

    assert {bundle.source_scope.scope_index for bundle in hub_bundles if bundle.source_scope} == {3}
    for bundle in hub_bundles:
        for pair in bundle.pairs:
            dependency = bundle.positioning_specs_by_pair[
                (pair.origin_airport_fact_id, pair.destination_airport_fact_id)
            ][0]
            assert dependency[3] == access_relationships[
                (pair.origin_airport_fact_id, pair.destination_airport_fact_id)
            ]


def _rehash_plan(payload: dict[str, object]) -> None:
    digest_payload = dict(payload)
    digest_payload.pop("plan_digest")
    payload["plan_digest"] = hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
