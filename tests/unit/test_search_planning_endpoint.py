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
    load_default_planning_market_policy,
    plan_searches,
)

CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")
US_ORIGINS = ("ABE", "ABI", "ABQ", "ABR", "ACK", "ACT", "ACV", "ADK", "ADQ", "AEX")
US_DESTINATIONS = ("AGS", "AIA", "AKN", "AKP", "ALB", "ALO", "ALS", "ALW", "ANC", "ANI", "ANV")
JAPAN_DESTINATIONS = ("NRT", "HND", "KIX", "NGO", "FUK", "CTS", "OKA", "ITM", "HIJ", "KOJ")
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
    proposal: GatewayCandidateProposal | None = None,
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
            generator_factory=lambda: _Generator(proposal or _proposal()),
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


def test_exactly_100_mandatory_pairs_compile_and_overflow_is_all_or_nothing() -> None:
    compiled = _compile(_request(US_ORIGINS, US_DESTINATIONS[:10]))
    assert compiled.outcome is SearchPlanningOutcome.PLANNED
    assert compiled.plan is not None
    assert compiled.plan.coverage.mandatory_required_pairs == 100
    assert len(compiled.plan.logical_queries) == 100

    rejected = _compile(_request(US_ORIGINS, US_DESTINATIONS))
    assert rejected.outcome is SearchPlanningOutcome.UNPLANNABLE
    assert rejected.plan is None
    assert (
        rejected.issues[0].code
        is StrategyCompilationIssueCode.ENDPOINT_PAIR_STRUCTURAL_LIMIT_EXCEEDED
    )
    assert rejected.structural_limit_receipts[0].observed == 110
    assert rejected.structural_limit_receipts[0].limit == 100
    assert rejected.structural_limit_receipts[0].classification == (
        "compiler_structural_safety"
    )


def test_finite_window_longer_than_31_days_compiles_without_execution_budgeting() -> None:
    long_window = _compile(_request(start=date(2026, 10, 1), end=date(2026, 11, 1)))
    assert long_window.outcome is SearchPlanningOutcome.PLANNED
    assert long_window.plan is not None
    assert long_window.plan.logical_queries[0].date_envelope.start == date(2026, 10, 1)
    assert long_window.plan.logical_queries[0].date_envelope.end == date(2026, 11, 1)


def test_every_replay_valid_relationship_compiles_without_the_old_24_bundle_cap() -> None:
    origins = ("SFO", "SJC")
    proposal = GatewayCandidateProposal.model_validate(
        {
            "endpoint_market_assessments": [],
            "origin_access_gateways": [
                {
                    "airport_iata": gateway,
                    "reason": "alternate departure search endpoint for the supplied Japan markets",
                    "supported_original_origin_iata_codes": list(origins),
                    "applicable_original_destination_iata_codes": list(JAPAN_DESTINATIONS),
                }
                for gateway in ("LAX", "SEA")
            ],
            "destination_access_gateways": [],
            "intermediate_hubs": [],
        }
    )

    result = _compile(
        _request(origins, JAPAN_DESTINATIONS),
        proposal=proposal,
    )

    assert result.outcome is SearchPlanningOutcome.PLANNED
    assert result.plan is not None
    assert result.plan.coverage.accepted_relationships == 40
    assert result.plan.coverage.compiled_relationships == 40
    assert len(result.plan.supplemental_strategies) == 40
    assert all(
        disposition.disposition.value == "compiled"
        for disposition in result.plan.relationship_dispositions
    )


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


def test_provider_capability_is_absent_and_catalog_identity_is_bound() -> None:
    result = _compile(_request())
    assert result.plan is not None
    identity = result.plan.identity
    assert "capability_receipt" not in identity.model_dump()
    assert identity.catalog_receipt.release_id == CATALOG.name
    assert identity.route_topology_feature == "absent"
    assert identity.accepted_relationship_ledger_digest
    assert identity.relationship_disposition_digest
    assert identity.compilation_binding_digest


def test_compiled_plan_is_copy_isolated() -> None:
    result = _compile(_request())
    assert result.plan is not None
    serialized = result.plan.model_dump(mode="json", round_trip=True)
    with pytest.raises(ValidationError):
        result.plan.logical_queries[0].query_id = "forged"
    assert result.plan.model_dump(mode="json", round_trip=True) == serialized
