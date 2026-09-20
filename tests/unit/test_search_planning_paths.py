"""Offline supplemental-strategy compilation tests.

The old route-expansion tests intentionally disappeared with the in-place 2C
replacement. These tests exercise the accepted 2B record as hypotheses, never
as route evidence or completed itineraries.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext

import pytest
from pydantic import ValidationError
from test_search_planning_endpoint import _Generator, _repository, _request

from award_agent.search_planning import (
    DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
    CompiledSearchPlan,
    DirectGroundingSource,
    GatewayCandidateProposal,
    GatewayDiscoveryInput,
    GatewayDiscoveryOutcome,
    GatewayOutboundDateContext,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    RelationshipDispositionKind,
    SearchPlanningInput,
    SearchPlanningOutcome,
    SupplementalStrategyType,
    discover_gateway_candidates,
    ground_endpoint,
    load_default_cached_search_capability,
    load_default_planning_market_policy,
    plan_searches,
)


def _proposal(**changes: object) -> GatewayCandidateProposal:
    payload: dict[str, object] = {
        "endpoint_market_assessments": [],
        "origin_access_gateways": [],
        "destination_access_gateways": [],
        "intermediate_hubs": [],
    }
    payload.update(changes)
    return GatewayCandidateProposal.model_validate(payload)


def _compile(proposal: GatewayCandidateProposal | Exception, *, repositioning: bool | None = None, policy: PlanningPolicy | None = None, origins: tuple[str, ...] = ("SFO",)):
    request = _request(origins, ("CDG",), repositioning_allowed=repositioning)
    policy = policy or PlanningPolicy()
    market_policy = load_default_planning_market_policy()
    with nullcontext(_repository()) as repository:
        origin_selections = tuple(
            ground_endpoint(location, "origin", repository, policy).selection
            for location in request.origins
        )
        destination = ground_endpoint(request.destinations[0], "destination", repository, policy)
        assert all(item is not None for item in origin_selections)
        assert destination.selection is not None and request.departure_window is not None
        discovery = discover_gateway_candidates(
            discovery_input=GatewayDiscoveryInput(
                origin_endpoints=tuple(
                    airport
                    for selection in origin_selections
                    if selection is not None
                    for airport in selection.airports
                ),
                destination_endpoints=destination.selection.airports,
                outbound_date=GatewayOutboundDateContext(
                    start=request.departure_window.start,
                    end=request.departure_window.end,
                    timezone=request.context.timezone,
                    effective_window_precision=request.departure_window.precision.value,
                ),
            ),
            policy=market_policy,
            repository=repository,
            generator_factory=lambda: _Generator(proposal),
            generator_configuration=DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
        )
        result = plan_searches(
            SearchPlanningInput(
                envelope=PlanningInputEnvelope(
                    source=PlanningSource(session_id="supplement-tests", revision=1),
                    effective_request=request,
                ),
                endpoint_source=DirectGroundingSource(),
                gateway_discovery_result=discovery,
                capability=load_default_cached_search_capability(),
            ),
            repository=repository,
            policy=policy,
            market_policy=market_policy,
        )
    return discovery, result


def _origin_access(*origins: str) -> dict[str, object]:
    return {
        "airport_iata": "LAX",
        "reason": "alternate origin gateway worth researching",
        "material_uncertainty": "positioning remains unverified",
        "model_asserted_market_id": "us_west",
        "supported_original_origin_iata_codes": list(origins),
        "applicable_original_destination_iata_codes": ["CDG"],
    }


def _direct_hub() -> dict[str, object]:
    return {
        "airport_iata": "ORD",
        "reason": "scoped connection hypothesis",
        "material_uncertainty": "no route evidence",
        "model_asserted_market_id": "us_midwest",
        "scopes": [
            {
                "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                "destination_side": [
                    {"kind": "original_destination", "airport_iata": "CDG"}
                ],
                "reason": "research only",
            }
        ],
    }


def test_shared_access_query_is_deduplicated_with_many_to_many_provenance() -> None:
    discovery, result = _compile(
        _proposal(origin_access_gateways=[_origin_access("SFO", "SEA")]),
        origins=("SFO", "SEA"),
    )
    assert discovery.outcome is GatewayDiscoveryOutcome.SUCCESS_NONEMPTY
    assert result.outcome is SearchPlanningOutcome.PLANNED
    assert result.plan is not None
    plan = result.plan
    assert len(plan.supplemental_strategies) == 2
    assert len(plan.strategy_query_uses) == 2
    assert plan.strategy_query_uses[0].query_id == plan.strategy_query_uses[1].query_id
    assert len(plan.logical_queries) == 3  # two mandatory plus one shared supplemental
    unique_budget = plan.budget_receipts[3]
    assert unique_budget.supplemental_admitted == 1
    assert unique_budget.shared_reused == 1


def test_explicit_positioning_refusal_suppresses_access_without_losing_mandatory_work() -> None:
    _, result = _compile(
        _proposal(origin_access_gateways=[_origin_access("SFO")]),
        repositioning=False,
    )
    assert result.outcome is SearchPlanningOutcome.PLANNED
    assert result.plan is not None
    assert len(result.plan.logical_queries) == 1
    assert not result.plan.supplemental_strategies
    assert result.plan.relationship_dispositions[0].disposition is RelationshipDispositionKind.SUPPRESSED_POSITIONING_REFUSAL
    assert result.plan.positioning_receipts[0].decision == "suppressed_explicit_refusal"


def test_unknown_positioning_permission_remains_conditional_and_traceable() -> None:
    _, result = _compile(_proposal(origin_access_gateways=[_origin_access("SFO")]))
    assert result.plan is not None
    strategy = result.plan.supplemental_strategies[0]
    assert strategy.eligibility == "conditional_permission"
    assert result.plan.positioning_dependencies[0].requested_permission is None
    assert result.plan.positioning_receipts[0].decision == "conditional_research"


def test_scoped_hub_is_two_queries_with_explicit_dates_and_connection_semantics() -> None:
    _, result = _compile(_proposal(intermediate_hubs=[_direct_hub()]))
    assert result.plan is not None
    strategy = result.plan.supplemental_strategies[0]
    assert strategy.strategy_type is SupplementalStrategyType.SCOPED_HUB
    uses = [item for item in result.plan.strategy_query_uses if item.strategy_id == strategy.strategy_id]
    assert [item.role for item in uses] == ["hub_first", "hub_second"]
    assert len(result.plan.temporal_derivations) == 2
    first, second = result.plan.temporal_derivations
    assert (first.start_offset_days, first.end_offset_days) == (0, 0)
    assert (second.start_offset_days, second.end_offset_days) == (-1, 2)
    assert all(
        query.connection_semantics == "provider_returned_connections_allowed"
        for query in result.plan.logical_queries
    )


def test_hub_bundle_admission_is_atomic_under_unique_query_budget() -> None:
    _, result = _compile(
        _proposal(intermediate_hubs=[_direct_hub()]),
        policy=PlanningPolicy(
            max_mandatory_endpoint_pairs=1,
            max_unique_logical_queries=2,
        ),
    )
    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert len(result.plan.logical_queries) == 1
    assert not result.plan.strategy_query_uses
    disposition = result.plan.relationship_dispositions[0]
    assert disposition.disposition is RelationshipDispositionKind.OMITTED_BUDGET
    assert disposition.candidate_unique_queries == 2
    assert disposition.marginal_unique_queries == 2


def test_access_referenced_hub_preserves_dependency_in_synthetic_scope() -> None:
    proposal = _proposal(
        origin_access_gateways=[_origin_access("SFO", "SEA")],
        intermediate_hubs=[
            {
                **_direct_hub(),
                "scopes": [
                    {
                        "origin_side": [
                            {"kind": "origin_access_gateway", "airport_iata": "LAX"}
                        ],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": "access-referenced synthetic scope",
                    }
                ],
            }
        ],
    )
    _, result = _compile(proposal, origins=("SFO", "SEA"))
    assert result.plan is not None
    hubs = [
        item
        for item in result.plan.supplemental_strategies
        if item.strategy_type is SupplementalStrategyType.SCOPED_HUB
    ]
    assert len(hubs) == 1
    assert len(hubs[0].supported_original_endpoint_pairs) == 2
    alternative = next(
        item for item in result.plan.support_alternatives if item.strategy_id == hubs[0].strategy_id
    )
    assert alternative.positioning_dependency_ids
    assert any(item.source_scope is not None for item in result.plan.relationship_dispositions)


def _rehashed(payload: dict[str, object]) -> dict[str, object]:
    payload["plan_digest"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "plan_digest"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return payload


def test_rehashed_graph_tampering_cannot_remove_hub_use_or_positioning_dependency() -> None:
    proposal = _proposal(
        origin_access_gateways=[_origin_access("SFO")],
        intermediate_hubs=[
            {
                **_direct_hub(),
                "scopes": [
                    {
                        "origin_side": [
                            {"kind": "origin_access_gateway", "airport_iata": "LAX"}
                        ],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                    }
                ],
            }
        ],
    )
    _, result = _compile(proposal)
    assert result.plan is not None

    missing_hub_use = result.plan.model_dump(mode="json", round_trip=True)
    hub_strategy = next(
        item for item in result.plan.supplemental_strategies
        if item.strategy_type is SupplementalStrategyType.SCOPED_HUB
    )
    missing_hub_use["strategy_query_uses"] = [
        item
        for item in missing_hub_use["strategy_query_uses"]
        if item["strategy_id"] != hub_strategy.strategy_id or item["sequence"] != 2
    ]
    with pytest.raises(ValidationError):
        CompiledSearchPlan.model_validate(_rehashed(missing_hub_use))

    missing_dependency = result.plan.model_dump(mode="json", round_trip=True)
    missing_dependency["positioning_dependencies"] = []
    with pytest.raises(ValidationError):
        CompiledSearchPlan.model_validate(_rehashed(missing_dependency))


def test_rehashed_graph_tampering_cannot_add_disposition_or_exceeded_success_budget() -> None:
    _, result = _compile(_proposal(origin_access_gateways=[_origin_access("SFO")]))
    assert result.plan is not None

    extra_disposition = result.plan.model_dump(mode="json", round_trip=True)
    extra = dict(extra_disposition["relationship_dispositions"][0])
    extra["relationship_id"] = "f" * 64
    extra_disposition["relationship_dispositions"].append(extra)
    extra_disposition["coverage"]["accepted_relationships"] += 1
    extra_disposition["coverage"]["admitted_relationships"] += 1
    with pytest.raises(ValidationError):
        CompiledSearchPlan.model_validate(_rehashed(extra_disposition))

    exceeded = result.plan.model_dump(mode="json", round_trip=True)
    exceeded["budget_receipts"][3]["limit"] = 0
    exceeded["budget_receipts"][3]["disposition"] = "exceeded"
    with pytest.raises(ValidationError):
        CompiledSearchPlan.model_validate(_rehashed(exceeded))


def test_optional_generation_failure_keeps_mandatory_plan_with_reduced_receipt() -> None:
    discovery, result = _compile(RuntimeError("offline generator unavailable"))
    assert discovery.outcome is GatewayDiscoveryOutcome.GENERATION_FAILURE
    assert result.outcome is SearchPlanningOutcome.REDUCED_COVERAGE
    assert result.plan is not None
    assert result.plan.coverage.mandatory_complete
    assert len(result.plan.logical_queries) == 1
    assert result.issues[0].code == "gateway_generation_failure"


def test_result_contains_no_observed_itinerary_claims() -> None:
    _, result = _compile(_proposal(intermediate_hubs=[_direct_hub()]))
    assert result.plan is not None
    rendered = result.plan.model_dump_json()
    assert "observed_itinerary" not in rendered
    assert "research_only_pending_result_validation" in rendered
    assert "not_schedule_or_connection_evidence" in rendered
