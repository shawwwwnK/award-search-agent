"""Offline integration tests for the current deterministic planning boundary."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    CabinClass,
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
    CatalogKnowledgeRepository,
    DirectGroundingSource,
    GatewayCandidateProposal,
    GatewayDiscoveryInput,
    GatewayOutboundDateContext,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningInput,
    SearchPlanningOutcome,
    SearchPlanningResult,
    StrategyCompilationIssueCode,
    check_plan_handoff,
    discover_gateway_candidates,
    effective_request_digest,
    ground_endpoint,
    load_default_cached_search_capability,
    load_default_planning_market_policy,
    plan_searches,
)

CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")
US_ORIGINS = ("ABE", "ABI", "ABQ", "ABR", "ACK", "ACT", "ACV", "ADK", "ADQ", "AEX")
US_DESTINATIONS = ("AGS", "AIA", "AKN", "AKP", "ALB", "ALO", "ALS", "ALW", "ANC", "ANI", "ANV")
_REPOSITORY: CatalogKnowledgeRepository | None = None


def _repository() -> CatalogKnowledgeRepository:
    """Open and verify the large checked-in catalog only once per test process."""

    global _REPOSITORY
    if _REPOSITORY is None:
        _REPOSITORY = CatalogKnowledgeRepository(CATALOG)
    return _REPOSITORY


class _Generator:
    def __init__(self, proposal: GatewayCandidateProposal | Exception) -> None:
        self.proposal = proposal

    def propose(self, _: object) -> GatewayCandidateProposal:
        if isinstance(self.proposal, Exception):
            raise self.proposal
        return self.proposal


def _request(
    origins: tuple[str, ...] = ("SFO",),
    destinations: tuple[str, ...] = ("LAX",),
    *,
    start: date = date(2026, 10, 5),
    end: date = date(2026, 10, 7),
    repositioning_allowed: bool | None = None,
    cabins: tuple[CabinClass, ...] = (),
) -> EffectiveRequest:
    return EffectiveRequest(
        raw_text="offline compiler fixture",
        context=RequestContext(
            reference_date=date(2026, 9, 19), timezone="America/Los_Angeles"
        ),
        travelers=2,
        origins=tuple(
            LocationRef(kind=LocationKind.AIRPORT, value=iata, raw_text=iata)
            for iata in origins
        ),
        destinations=tuple(
            LocationRef(kind=LocationKind.AIRPORT, value=iata, raw_text=iata)
            for iata in destinations
        ),
        departure_window=DateWindow(
            start=start,
            end=end,
            precision=DateWindowPrecision.WINDOW,
            raw_text="offline window",
        ),
        cabins=cabins,
        search_modes=(SearchMode.AWARD,),
        repositioning_allowed=repositioning_allowed,
    )


def _proposal() -> GatewayCandidateProposal:
    return GatewayCandidateProposal.model_validate(
        {
            "endpoint_market_assessments": [],
            "origin_access_gateways": [],
            "destination_access_gateways": [],
            "intermediate_hubs": [],
        }
    )


def _compile(
    request: EffectiveRequest,
    *,
    policy: PlanningPolicy | None = None,
    expected_digest: str | None = None,
) -> SearchPlanningResult:
    policy = policy or PlanningPolicy()
    market_policy = load_default_planning_market_policy()
    with nullcontext(_repository()) as repository:
        origins = tuple(
            ground_endpoint(location, "origin", repository, policy).selection
            for location in request.origins
        )
        destinations = tuple(
            ground_endpoint(location, "destination", repository, policy).selection
            for location in request.destinations
        )
        assert all(item is not None for item in (*origins, *destinations))
        assert request.departure_window is not None
        origin_airports = {
            airport.airport_id: airport
            for item in origins if item is not None for airport in item.airports
        }
        destination_airports = {
            airport.airport_id: airport
            for item in destinations if item is not None for airport in item.airports
        }
        discovery_input = GatewayDiscoveryInput(
            origin_endpoints=tuple(origin_airports[key] for key in sorted(origin_airports)),
            destination_endpoints=tuple(
                destination_airports[key] for key in sorted(destination_airports)
            ),
            outbound_date=GatewayOutboundDateContext(
                start=request.departure_window.start,
                end=request.departure_window.end,
                timezone=request.context.timezone,
                effective_window_precision="window",
            ),
        )
        discovery = discover_gateway_candidates(
            discovery_input=discovery_input,
            policy=market_policy,
            repository=repository,
            generator_factory=lambda: _Generator(_proposal()),
            generator_configuration=DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
        )
        envelope = PlanningInputEnvelope(
            source=PlanningSource(
                session_id="endpoint-tests",
                revision=4,
                expected_effective_request_digest=expected_digest,
            ),
            effective_request=request,
        )
        return plan_searches(
            SearchPlanningInput(
                envelope=envelope,
                endpoint_source=DirectGroundingSource(),
                gateway_discovery_result=discovery,
                capability=load_default_cached_search_capability(),
            ),
            repository=repository,
            policy=policy,
            market_policy=market_policy,
        )


def test_mandatory_plan_is_complete_traceable_and_provider_neutral() -> None:
    result = _compile(_request())
    assert result.outcome is SearchPlanningOutcome.PLANNED
    assert result.plan is not None
    plan = result.plan
    assert plan.coverage.mandatory_complete
    assert plan.coverage.mandatory_required_pairs == 1
    assert len(plan.mandatory_endpoint_probes) == len(plan.mandatory_query_uses) == 1
    assert len(plan.logical_queries) == 1
    query = plan.logical_queries[0]
    assert query.connection_semantics == "provider_returned_connections_allowed"
    assert query.requested_cabins == ()
    assert not hasattr(query, "provider_payload")
    assert plan.plan_digest


def test_duplicate_endpoint_alternatives_deduplicate_complete_query_semantics() -> None:
    result = _compile(_request(("SFO", "SFO"), ("LAX", "LAX")))
    assert result.plan is not None
    assert result.plan.coverage.mandatory_required_pairs == 1
    assert len(result.plan.logical_queries) == 1


def test_exactly_100_mandatory_pairs_are_admitted_and_110_fail_without_pruning() -> None:
    admitted = _compile(_request(US_ORIGINS, US_DESTINATIONS[:10]))
    assert admitted.outcome is SearchPlanningOutcome.PLANNED
    assert admitted.plan is not None
    assert admitted.plan.coverage.mandatory_required_pairs == 100
    assert len(admitted.plan.logical_queries) == 100

    rejected = _compile(_request(US_ORIGINS, US_DESTINATIONS))
    assert rejected.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert rejected.plan is None
    assert rejected.issues[0].code is StrategyCompilationIssueCode.MANDATORY_ENDPOINT_PAIR_BUDGET_EXCEEDED
    assert rejected.budget_receipts[0].observed == 110
    assert rejected.budget_receipts[0].limit == 100


def test_window_and_date_work_limits_are_exact() -> None:
    long_window = _compile(_request(start=date(2026, 10, 1), end=date(2026, 11, 1)))
    assert long_window.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert long_window.issues[0].code is StrategyCompilationIssueCode.INPUT_WINDOW_EXCEEDS_BUDGET

    date_work = _compile(
        _request(
            US_ORIGINS,
            US_DESTINATIONS[:10],
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
        ),
        policy=PlanningPolicy(max_query_date_days=3100),
    )
    assert date_work.outcome is SearchPlanningOutcome.PLANNED
    assert date_work.plan is not None
    assert date_work.plan.budget_receipts[-1].observed == 3100


def test_request_digest_binding_and_handoff_freshness_are_immutable() -> None:
    request = _request()
    result = _compile(request, expected_digest=effective_request_digest(request))
    assert result.plan is not None
    before = result.plan.model_dump(mode="json", round_trip=True)
    current = check_plan_handoff(
        result.plan,
        current_session_id="endpoint-tests",
        current_revision=4,
        current_effective_request=request,
        expected_compilation_binding_digest=result.plan.identity.compilation_binding_digest,
    )
    stale = check_plan_handoff(
        result.plan,
        current_session_id="endpoint-tests",
        current_revision=5,
        current_effective_request=request,
        expected_compilation_binding_digest=result.plan.identity.compilation_binding_digest,
    )
    assert current.executable is True
    assert stale.executable is False
    assert result.plan.model_dump(mode="json", round_trip=True) == before

    mismatch = _compile(request, expected_digest="0" * 64)
    assert mismatch.outcome is SearchPlanningOutcome.EVIDENCE_FAILURE
    assert mismatch.plan is None
    assert mismatch.issues[0].code == "request_digest_mismatch"


def test_capability_and_catalog_identities_are_bound_into_plan() -> None:
    result = _compile(_request())
    assert result.plan is not None
    identity = result.plan.identity
    assert identity.capability_receipt.capability_id == "seats_aero.cached_search.v1"
    assert identity.catalog_receipt.release_id == CATALOG.name
    assert identity.route_topology_feature == "absent"
    assert identity.compilation_binding_digest


def test_compiled_plan_is_copy_isolated() -> None:
    result = _compile(_request())
    assert result.plan is not None
    serialized = result.plan.model_dump(mode="json", round_trip=True)
    with pytest.raises(ValidationError):
        result.plan.logical_queries[0].query_id = "forged"  # type: ignore[misc]
    assert result.plan.model_dump(mode="json", round_trip=True) == serialized
