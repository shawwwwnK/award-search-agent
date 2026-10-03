"""Focused Ranking M2 normalization and assignment boundaries."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_UP, Context, Decimal, Inexact, localcontext
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import JsonValue, ValidationError

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import (
    DateWindow,
    DateWindowPrecision,
    EffectiveRequest,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
)
from award_agent.providers.contracts import (
    CoverageReceipt,
    EvidenceRef,
    ExecutionPolicy,
    ObservedLeg,
    ProviderCapability,
    ProviderObservation,
    ProviderResultSet,
    RawField,
    ResourceBudget,
    ResourceUsage,
    TransportReceipt,
)
from award_agent.providers.execution import build_execution_plan
from award_agent.ranking import (
    CurrencyConversionSnapshot,
    MatchedJourneySet,
    MatchReason,
    RankedJourneySet,
    RankingStylePolicy,
    assemble_matched_journeys,
    assign_journey_styles,
)
from award_agent.ranking.style_contracts import JourneyCost
from award_agent.ranking.styles import _amount, _assessment, _component
from award_agent.search_planning import (
    DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
    CatalogKnowledgeRepository,
    DirectGroundingSource,
    GatewayDiscoveryInput,
    GatewayOutboundDateContext,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningInput,
    discover_gateway_candidates,
    load_default_planning_market_policy,
    plan_searches,
)
from award_agent.search_planning.locations import ground_endpoint


def _snapshot() -> CurrencyConversionSnapshot:
    return CurrencyConversionSnapshot(
        snapshot_id="test-capture", as_of=date(2026, 9, 29), source="synthetic test",
        source_digest="a" * 64, rates_to_usd={"USD": Decimal(1), "CAD": Decimal("0.7")},
    )


def _matched() -> MatchedJourneySet:
    return MatchedJourneySet.model_validate_json(
        Path("evidence/ranking-stage/m1/exact_business.json").read_text()
    )


def _award() -> ProviderObservation:
    return next(item for item in _matched().provider_result.observations
                if item.kind == "award_itinerary")


def _synthetic_match(
    *, missing_cash_id: str | None = None, expensive_cash_id: str | None = None,
    premium_economy_award_id: str | None = None, shifted_cash_id: str | None = None,
    shifted_cash_delta: timedelta = timedelta(minutes=1),
) -> MatchedJourneySet:
    directory = Path("evidence/provider-stage/saved-searches/runs/mixed_access")
    bundle = ProviderInputBundle.model_validate_json((directory / "bundle.json").read_text())
    original = ProviderResultSet.model_validate_json((directory / "result.json").read_text())
    observations: list[ProviderObservation] = []
    for observation in original.observations:
        update: dict[str, object] = {}
        if observation.kind == "award_itinerary":
            update = {
                "price_scope": "per_traveler",
                "points": RawField(state="value", value=10000, source_field="synthetic_points"),
                "taxes_fees": RawField(state="value", value=0, source_field="synthetic_tax"),
                "tax_currency": RawField(state="value", value="USD"),
                "taxes_fees_unit": "major",
            }
            if observation.observation_id == premium_economy_award_id:
                update["cabin"] = RawField(state="value", value="premium_economy")
                update["legs"] = tuple(leg.model_copy(update={
                    "cabin": RawField(state="value", value="premium_economy"),
                }) for leg in observation.legs)
        elif observation.kind == "cash_itinerary":
            update = {
                "price_scope": "per_traveler",
                "cash_amount": RawField(
                    state="unknown" if observation.observation_id == missing_cash_id else "value",
                    value=None if observation.observation_id == missing_cash_id else
                    500 if observation.observation_id == expensive_cash_id else 100,
                    source_field="synthetic_cash",
                ),
                "cash_currency": RawField(state="value", value="USD"),
            }
            if observation.observation_id == shifted_cash_id:
                assert observation.departure_instant is not None
                assert observation.arrival_instant is not None
                shifted_legs: list[object] = []
                for leg in observation.legs:
                    assert leg.departure_instant is not None
                    assert leg.arrival_instant is not None
                    shifted_legs.append(leg.model_copy(update={
                        "departure_instant": leg.departure_instant + shifted_cash_delta,
                        "arrival_instant": leg.arrival_instant + shifted_cash_delta,
                    }))
                update["departure_instant"] = observation.departure_instant + shifted_cash_delta
                update["arrival_instant"] = observation.arrival_instant + shifted_cash_delta
                update["legs"] = tuple(shifted_legs)
        observations.append(ProviderObservation.model_validate(observation.model_copy(update=update)))
    result = ProviderResultSet.model_validate(original.model_copy(update={
        "observations": tuple(observations),
    }))
    return assemble_matched_journeys(
        bundle.plan, result, current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy, award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability,
    )


def _three_traveler_party_match() -> tuple[MatchedJourneySet, tuple[str, ...]]:
    travel_date = date(2026, 10, 5)
    request = EffectiveRequest(
        raw_text="Three award seats SFO to LAX October 5.",
        context=RequestContext(reference_date=date(2026, 9, 19),
                               timezone="America/Los_Angeles"),
        travelers=3,
        origins=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
        destinations=(LocationRef(kind=LocationKind.AIRPORT, value="LAX", raw_text="LAX"),),
        departure_window=DateWindow(start=travel_date, end=travel_date,
                                    precision=DateWindowPrecision.EXACT,
                                    raw_text="October 5"),
        search_modes=(SearchMode.AWARD,),
    )
    planning_policy = PlanningPolicy()
    market_policy = load_default_planning_market_policy()
    with CatalogKnowledgeRepository(
        Path("data/search_planning/catalogs/m1a-3cb7981519612945")
    ) as repository:
        origin = ground_endpoint(request.origins[0], "origin", repository, planning_policy)
        destination = ground_endpoint(request.destinations[0], "destination",
                                      repository, planning_policy)
        assert origin.selection is not None and destination.selection is not None
        discovery = discover_gateway_candidates(
            discovery_input=GatewayDiscoveryInput(
                origin_endpoints=origin.selection.airports,
                destination_endpoints=destination.selection.airports,
                outbound_date=GatewayOutboundDateContext(
                    start=travel_date, end=travel_date, timezone="America/Los_Angeles",
                    effective_window_precision="exact",
                ),
            ),
            policy=market_policy, repository=repository,
            generator_factory=lambda: (_ for _ in ()).throw(
                AssertionError("same-market fixture must skip gateway model")
            ),
            generator_configuration=DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
        )
        planning = plan_searches(
            SearchPlanningInput(
                envelope=PlanningInputEnvelope(
                    source=PlanningSource(session_id="ranking-m2-three-party", revision=0),
                    effective_request=request,
                ),
                endpoint_source=DirectGroundingSource(), gateway_discovery_result=discovery,
            ),
            repository=repository, policy=planning_policy, market_policy=market_policy,
        )
    assert planning.plan is not None
    plan = planning.plan
    assert len(plan.logical_queries) == 1
    assert plan.mandatory_endpoint_probes[0].traveler_count == 3
    budget = ResourceBudget(requests=2, attempts=2, pages=2, detail_calls=0,
                            rows=10, bytes=1000, elapsed_seconds=10)
    execution_policy = ExecutionPolicy(
        version="ranking-m2-synthetic", award_budget=budget, cash_budget=budget,
        budget_evidence=("offline-fixture",), direct_cash_samples=0,
        positioning_cash_samples=0, page_size=10, request_timeout_seconds=5,
    )
    award_capability = ProviderCapability(
        provider="seats_aero", version="synthetic", backend="fixture",
        operation="search", reviewed=True, evidence_digests=("a" * 64,),
    )
    cash_capability = ProviderCapability(
        provider="gfly", version="synthetic", backend="fixture",
        operation="search", reviewed=True, evidence_digests=("b" * 64,),
    )
    execution = build_execution_plan(
        plan, run_id="ranking-m2-three-party",
        current_session_id=plan.identity.session_id,
        current_revision=plan.identity.revision,
        current_effective_request=request,
        expected_compilation_binding_digest=plan.identity.compilation_binding_digest,
        policy=execution_policy, award_capability=award_capability,
        cash_capability=cash_capability,
    )
    award_query = next(query for query in execution.queries
                       if query.role == "mandatory_award")
    assert award_query.travelers == 3
    assert not any(query.provider == "gfly" for query in execution.queries)
    retrieved = datetime(2026, 10, 1, tzinfo=UTC)
    evidence = EvidenceRef(sha256="c" * 64, relative_path="synthetic-three-party.json",
                           retrieved_at=retrieved, synthetic=True)
    departure = datetime(2026, 10, 5, 17, tzinfo=UTC)
    arrival = departure + timedelta(hours=2)
    observation_ids = tuple(f"synthetic-award-{points}" for points in (100, 200, 201))
    observations = tuple(ProviderObservation(
        observation_id=observation_id, provider="seats_aero", backend="fixture",
        provider_version="synthetic", kind="award_itinerary", query_id=award_query.query_id,
        logical_query_ids=award_query.logical_query_ids,
        logical_use_ids=award_query.logical_use_ids,
        origin="SFO", destination="LAX", departure_date=travel_date,
        departure_instant=departure, arrival_instant=arrival,
        airport_sequence=("SFO", "LAX"),
        legs=(ObservedLeg(origin="SFO", destination="LAX", departure_instant=departure,
                          arrival_instant=arrival),),
        retrieved_at=retrieved, requested_travelers=3,
        returned_travelers=RawField(state="value", value=3),
        seats=RawField(state="value", value=3),
        program=RawField(state="value", value="synthetic-program"),
        points=RawField(state="value", value=points),
        taxes_fees=RawField(state="value", value=0),
        taxes_fees_unit="major", tax_currency=RawField(state="value", value="USD"),
        price_scope="party", evidence=(evidence,),
    ) for observation_id, points in zip(observation_ids, (100, 200, 201), strict=True))
    transport = TransportReceipt(
        transport_id="synthetic-award-transport", query_id=award_query.query_id,
        provider="seats_aero", attempt=1, page=1, status="completed", evidence=evidence,
        elapsed_seconds=0.1, byte_count=2, returned_rows=3,
        observation_ids=observation_ids,
    )
    coverage = tuple(CoverageReceipt(
        unit_id=unit.unit_id,
        status="completed" if unit.kind in {"logical_query", "mandatory_use"} else "omitted",
        query_ids=(award_query.query_id,) if unit.kind in {"logical_query", "mandatory_use"}
        else (),
        transport_ids=(transport.transport_id,) if unit.kind in {"logical_query", "mandatory_use"}
        else (),
        observation_ids=observation_ids if unit.kind in {"logical_query", "mandatory_use"}
        else (),
        reason="synthetic_observed" if unit.kind in {"logical_query", "mandatory_use"}
        else "not_scheduled",
        stream_complete=unit.kind in {"logical_query", "mandatory_use"},
        pair_coverage="observed" if unit.kind in {"logical_query", "mandatory_use"}
        else "not_attempted",
    ) for unit in execution.coverage_units)
    result = ProviderResultSet(
        execution_plan=execution, status="partial", observations=observations,
        transport_receipts=(transport,), coverage=coverage,
        award_usage=ResourceUsage(requests=1, attempts=1, pages=1, rows=3,
                                  bytes=2, elapsed_seconds=0.1),
    )
    def reassemble() -> MatchedJourneySet:
        return assemble_matched_journeys(
            plan, result, current_session_id=plan.identity.session_id,
            current_revision=plan.identity.revision,
            current_effective_request=request,
            expected_compilation_binding_digest=plan.identity.compilation_binding_digest,
            policy=execution_policy, award_capability=award_capability,
            cash_capability=cash_capability,
        )

    matched = reassemble()
    assert reassemble() == matched
    return matched, observation_ids


def test_snapshot_validation_and_copy_isolation() -> None:
    rates = {"USD": Decimal(1), "CAD": Decimal("0.7")}
    snapshot = CurrencyConversionSnapshot(
        snapshot_id="test-capture", as_of=date(2026, 9, 29), source="synthetic test",
        source_digest="a" * 64, rates_to_usd=rates,
    )
    rates["CAD"] = Decimal(2)
    assert snapshot.rates_to_usd["CAD"] == Decimal("0.7")
    readback = snapshot.rates_to_usd
    readback["CAD"] = Decimal(2)
    assert snapshot.rates_to_usd["CAD"] == Decimal("0.7")
    for rates in ({"USD": Decimal("1.01")}, {"USD": Decimal(1), "CAD": Decimal("NaN")},
                  {"USD": Decimal(1), "CAD": Decimal(0)}):
        with pytest.raises(ValidationError):
            CurrencyConversionSnapshot(snapshot_id="bad", as_of=date(2026, 9, 29),
                                       source="test", source_digest="a" * 64,
                                       rates_to_usd=rates)


@pytest.mark.parametrize("value", [True, -1, "NaN", "Infinity", "oops", []])
def test_malformed_known_amount_never_normalizes(value: JsonValue) -> None:
    amount, reason = _amount(RawField(state="value", value=value))
    assert amount is None and reason == "amount_malformed"


def test_tax_estimate_only_for_genuinely_missing_amount() -> None:
    award = _award()
    policy = RankingStylePolicy()
    missing = _component("award_taxes", award, RawField(), RawField(), "unknown",
                         policy, _snapshot(), 2)
    assert missing.state == "estimated"
    assert missing.per_traveler_usd == Decimal(150)
    malformed = _component("award_taxes", award, RawField(state="value", value="bad"),
                           RawField(), "unknown", policy, _snapshot(), 2)
    assert malformed.state == "unavailable"
    zero = _component("award_taxes", award, RawField(state="value", value=0),
                      RawField(state="value", value="USD"), "major", policy,
                      _snapshot(), 2)
    assert zero.state != "estimated"


def test_party_currency_minor_units_and_unknown_scope() -> None:
    award = _award().model_copy(update={"price_scope": "party"})
    field = RawField(state="value", value="100")
    currency = RawField(state="value", value="CAD")
    component = _component("award_taxes", award, field, currency, "minor",
                           RankingStylePolicy(), _snapshot(), 2)
    assert component.per_traveler_usd == Decimal("0.35")
    unknown = _component("award_taxes", award.model_copy(update={"price_scope": "unknown"}),
                         field, currency, "minor", RankingStylePolicy(), _snapshot(), 2)
    assert unknown.state == "unavailable" and unknown.raw_amount == field
    unsupported = _component("award_taxes", award, field,
                             RawField(state="value", value="JPY"), "minor",
                             RankingStylePolicy(), _snapshot(), 2)
    assert unsupported.reason == "tax_minor_scale_unsupported"


def test_saved_result_roundtrip_and_tamper_detection() -> None:
    ranked = assign_journey_styles(_matched(), policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    assert RankedJourneySet.model_validate_json(ranked.model_dump_json()) == ranked
    changed = ranked.model_dump(mode="json")
    changed["indexes"]["time"] = []
    with pytest.raises(ValidationError, match="derived features or indexes"):
        RankedJourneySet.model_validate(changed)
    changed = ranked.model_dump(mode="json")
    changed["matched_digest"] = "b" * 64
    with pytest.raises(ValidationError, match="source binding"):
        RankedJourneySet.model_validate(changed)


def test_source_order_does_not_change_style_indexes() -> None:
    matched = _matched()
    reversed_journeys = MatchedJourneySet.model_validate(
        matched.model_copy(update={"journeys": tuple(reversed(matched.journeys))})
    )
    policy = RankingStylePolicy()
    snapshot = _snapshot()
    first = assign_journey_styles(matched, policy=policy, fx_snapshot=snapshot)
    second = assign_journey_styles(reversed_journeys, policy=policy, fx_snapshot=snapshot)
    assert first.comparison_pool_ids == second.comparison_pool_ids
    assert first.features == second.features
    assert first.assessments == second.assessments
    assert first.indexes == second.indexes


def test_inclusive_thresholds_zero_reference_and_partial_cost() -> None:
    ranked = assign_journey_styles(_matched(), policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    feature = next(item for item in ranked.features
                   if item.status in {"admitted", "conditional"})
    timed = feature.model_copy(update={"elapsed_minutes": Decimal(120),
                                       "elapsed_microseconds": 120 * 60000000})
    assert _assessment(timed, "time", 100 * 60000000, None,
                       RankingStylePolicy()).state == "member"
    beyond = timed.model_copy(update={"elapsed_minutes": Decimal("120.000001"),
                                      "elapsed_microseconds": 120 * 60000000 + 60})
    assert _assessment(beyond, "time", 100 * 60000000, None,
                       RankingStylePolicy()).state == "not_member"
    complete = JourneyCost(components=(), known_subtotal_usd=Decimal(200),
                           complete_usd=Decimal(200), exact_subtotal_numerator=200,
                           exact_subtotal_denominator=1, missing_parts=(), completeness="complete")
    exact = feature.model_copy(update={"cost": complete})
    assert _assessment(exact, "cost", None, Fraction(100),
                       RankingStylePolicy()).state == "member"
    assert _assessment(exact, "cost", None, Fraction(0),
                       RankingStylePolicy()).state == "not_member"
    partial = JourneyCost(components=(), known_subtotal_usd=Decimal(200),
                          exact_subtotal_numerator=200, exact_subtotal_denominator=1,
                          missing_parts=("points",), completeness="partial")
    provisional = feature.model_copy(update={"cost": partial})
    assert _assessment(provisional, "cost", None, Fraction(100),
                       RankingStylePolicy()).state == "possible"
    assert _assessment(provisional, "cost", None, None,
                       RankingStylePolicy()).state == "undetermined"
    assert _assessment(provisional, "cost", None, Fraction(99),
                       RankingStylePolicy()).state == "not_member"


def test_synthetic_complete_costs_provisional_highlights_and_isolated_changes() -> None:
    policy = RankingStylePolicy()
    snapshot = _snapshot()
    baseline_match = _synthetic_match()
    baseline = assign_journey_styles(baseline_match, policy=policy, fx_snapshot=snapshot)
    assert baseline.cost_reference_usd == Decimal(100)
    assert set(baseline.indexes.cost) == set(baseline.comparison_pool_ids)
    assert baseline.indexes.definite_highlights
    observed_zero_tax = next(component for feature in baseline.features
                             if feature.status in {"admitted", "conditional"}
                             for component in feature.cost.components
                             if component.kind == "award_taxes")
    assert observed_zero_tax.state == "observed"
    assert observed_zero_tax.raw_amount.value == 0
    assert observed_zero_tax.per_traveler_usd == Decimal(0)
    target = next(feature for feature in baseline.features
                  if feature.candidate_id in baseline.indexes.premium
                  and feature.candidate_id not in baseline.indexes.time
                  and feature.cash_observation_id is not None
                  and feature.award_cabin.value == "business")
    modified = assign_journey_styles(
        _synthetic_match(missing_cash_id=target.cash_observation_id),
        policy=policy, fx_snapshot=snapshot,
    )
    target_cost = next(feature.cost for feature in modified.features
                       if feature.candidate_id == target.candidate_id)
    assert target_cost.completeness == "partial"
    assert target_cost.known_subtotal_usd == Decimal(100)
    assert "cash_fare" in target_cost.missing_parts
    missing_fare = next(component for component in target_cost.components
                        if component.kind == "cash_fare")
    assert missing_fare.state == "unavailable"
    assert missing_fare.raw_amount.state == "unknown"
    assert missing_fare.per_traveler_usd is None
    assert target.candidate_id in modified.indexes.possible_cost
    assert target.candidate_id in modified.indexes.possible_highlights
    assert target.candidate_id not in modified.indexes.cost
    assert modified.cost_reference_usd == Decimal(100)
    assert modified.indexes.time == baseline.indexes.time
    assert modified.indexes.premium == baseline.indexes.premium
    expensive = assign_journey_styles(
        _synthetic_match(expensive_cash_id=target.cash_observation_id),
        policy=policy, fx_snapshot=snapshot,
    )
    assert expensive.indexes.time == baseline.indexes.time
    assert expensive.indexes.premium == baseline.indexes.premium
    assert target.candidate_id not in expensive.indexes.cost
    addon_award = next(feature.award_observation_id for feature in baseline.features
                       if feature.status in {"admitted", "conditional"}
                       and feature.award_cabin.value == "economy"
                       and feature.award_observation_id != target.award_observation_id)
    addon = assign_journey_styles(
        _synthetic_match(premium_economy_award_id=addon_award),
        policy=policy, fx_snapshot=snapshot,
    )
    addon_ids = {feature.candidate_id for feature in addon.features
                 if feature.award_observation_id == addon_award
                 and feature.status in {"admitted", "conditional"}}
    assert addon_ids and addon_ids <= set(addon.indexes.premium_economy_addons)
    assert not addon_ids.intersection(addon.indexes.premium)
    shifted = assign_journey_styles(
        _synthetic_match(shifted_cash_id=target.cash_observation_id),
        policy=policy, fx_snapshot=snapshot,
    )
    original_costs = {feature.candidate_id: feature.cost for feature in baseline.features}
    assert {feature.candidate_id: feature.cost for feature in shifted.features} == original_costs
    shifted_target = next(feature for feature in shifted.features
                          if feature.candidate_id == target.candidate_id)
    assert shifted_target.elapsed_minutes != target.elapsed_minutes


def test_no_eligible_pool_and_attachment_tampering() -> None:
    matched = _synthetic_match()
    failed_reason = MatchReason(code="synthetic_scope_rejection", dimension="scope",
                                state="failed", detail="Synthetic test rejection")
    journeys = tuple(journey.model_copy(update={
        "reasons": (*journey.reasons, failed_reason), "status": "rejected",
    }) for journey in matched.journeys)
    accounting = matched.accounting.model_copy(update={
        "admitted": 0, "conditional": 0, "research_leads": 0,
        "rejected": len(journeys),
    })
    empty_pool = MatchedJourneySet.model_validate(matched.model_copy(update={
        "journeys": journeys, "accounting": accounting,
    }))
    ranked = assign_journey_styles(empty_pool, policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    assert not ranked.comparison_pool_ids
    assert ranked.time_reference_minutes is None and ranked.cost_reference_usd is None
    assert len(ranked.indexes.excluded) == len(journeys)
    assert not ranked.indexes.time and not ranked.indexes.cost and not ranked.indexes.premium
    for mutate in (
        lambda data: data["features"][0].update({"elapsed_minutes": "1"}),
        lambda data: data["assessments"][0].update({"state": "member"}),
        lambda data: data["fx_snapshot"]["rates_to_usd"].update({"CAD": "0.8"}),
        lambda data: data.update({"fx_snapshot_digest": "b" * 64}),
        lambda data: data.update({"policy_digest": "b" * 64}),
    ):
        changed = ranked.model_dump(mode="json")
        mutate(changed)
        with pytest.raises(ValidationError):
            RankedJourneySet.model_validate_json(json.dumps(changed))


def test_arithmetic_ignores_adversarial_ambient_decimal_context() -> None:
    policy = RankingStylePolicy()
    snapshot = _snapshot()
    matched = _synthetic_match()
    expected = assign_journey_styles(matched, policy=policy, fx_snapshot=snapshot)
    award = _award().model_copy(update={"price_scope": "party"})
    amount = RawField(state="value", value=100)
    expected_party = _component("points", award, amount, None, "points", policy, snapshot, 3)
    with localcontext(Context(prec=4, rounding=ROUND_UP, Emin=-5, Emax=5,
                              traps=[Inexact])):
        actual = assign_journey_styles(matched, policy=policy, fx_snapshot=snapshot)
        actual_party = _component("points", award, amount, None, "points", policy, snapshot, 3)
        assert actual == expected
        assert actual_party == expected_party
        assert RankedJourneySet.model_validate_json(actual.model_dump_json()) == actual


def test_m1_time_and_transfer_forgery_fail_against_attached_components() -> None:
    matched = _synthetic_match()
    target = next(journey for journey in matched.journeys
                  if journey.status in {"admitted", "conditional"}
                  and journey.cash_observation_id is not None)
    assert target.departure_instant is not None
    assert target.transfer_minutes is not None
    for update in ({"departure_instant": target.departure_instant - timedelta(minutes=1)},
                   {"transfer_minutes": target.transfer_minutes + 1}):
        forged = target.model_copy(update=update)
        journeys = tuple(forged if journey.candidate_id == target.candidate_id else journey
                         for journey in matched.journeys)
        forged_match = MatchedJourneySet.model_validate(
            matched.model_copy(update={"journeys": journeys})
        )
        with pytest.raises(ValueError, match="differ.*component evidence"):
            assign_journey_styles(forged_match, policy=RankingStylePolicy(),
                                  fx_snapshot=_snapshot())


def test_exact_party_thirds_include_double_and_exclude_above() -> None:
    policy = RankingStylePolicy()
    snapshot = _snapshot()
    award = _award().model_copy(update={"price_scope": "party"})
    normalized = [
        _component("points", award, RawField(state="value", value=points), None,
                   "points", policy, snapshot, 3)
        for points in (100, 200, 201)
    ]
    assert [(item.exact_numerator, item.exact_denominator) for item in normalized] == [
        (1, 3), (2, 3), (67, 100),
    ]
    ranked = assign_journey_styles(_synthetic_match(), policy=policy, fx_snapshot=snapshot)
    feature = next(item for item in ranked.features
                   if item.status in {"admitted", "conditional"})
    states = []
    for component in normalized:
        cost = JourneyCost(
            components=(component,), known_subtotal_usd=component.per_traveler_usd,
            complete_usd=component.per_traveler_usd,
            exact_subtotal_numerator=component.exact_numerator,
            exact_subtotal_denominator=component.exact_denominator,
            missing_parts=(), completeness="complete",
        )
        states.append(_assessment(feature.model_copy(update={"cost": cost}), "cost",
                                  None, Fraction(1, 3), policy).state)
    assert states == ["member", "member", "not_member"]


def test_three_traveler_party_boundary_through_public_assignment() -> None:
    matched, award_ids = _three_traveler_party_match()
    ranked = assign_journey_styles(matched, policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    assert matched.request.travelers == 3
    assert matched.accounting.retained_direct == 3
    assert matched.accounting.retained_mixed == 0
    assert {journey.award_observation_id for journey in matched.journeys} == set(award_ids)
    assert ranked.cost_reference_numerator == 1
    assert ranked.cost_reference_denominator == 3
    assessments = {item.candidate_id: item for item in ranked.assessments
                   if item.style == "cost"}
    by_award = {award_id: next(feature for feature in ranked.features
                               if feature.award_observation_id == award_id
                               and feature.status in {"admitted", "conditional"})
                for award_id in award_ids}
    assert [assessments[by_award[award_id].candidate_id].state for award_id in award_ids] == [
        "member", "member", "not_member",
    ]
    assert [(by_award[award_id].cost.exact_subtotal_numerator,
             by_award[award_id].cost.exact_subtotal_denominator)
            for award_id in award_ids] == [(1, 3), (2, 3), (67, 100)]


def test_exact_utc_microseconds_include_six_seconds_and_exclude_more() -> None:
    policy = RankingStylePolicy()
    ranked = assign_journey_styles(_synthetic_match(), policy=policy, fx_snapshot=_snapshot())
    feature = next(item for item in ranked.features
                   if item.status in {"admitted", "conditional"})
    states = []
    for microseconds in (5000000, 6000000, 6000001):
        timed = feature.model_copy(update={
            "elapsed_microseconds": microseconds,
            "elapsed_minutes": Decimal(microseconds) / Decimal(60000000),
        })
        states.append(_assessment(timed, "time", 5000000, None, policy).state)
    assert states == ["member", "member", "not_member"]


def test_source_microseconds_are_bound_to_whole_journey_elapsed() -> None:
    policy = RankingStylePolicy()
    snapshot = _snapshot()
    baseline = assign_journey_styles(_synthetic_match(), policy=policy, fx_snapshot=snapshot)
    target = next(feature for feature in baseline.features
                  if feature.status in {"admitted", "conditional"}
                  and feature.cash_observation_id is not None)
    changed = assign_journey_styles(
        _synthetic_match(shifted_cash_id=target.cash_observation_id,
                         shifted_cash_delta=timedelta(seconds=1, microseconds=1)),
        policy=policy, fx_snapshot=snapshot,
    )
    revised = next(feature for feature in changed.features
                   if feature.candidate_id == target.candidate_id)
    assert revised.elapsed_microseconds is not None
    assert target.elapsed_microseconds is not None
    if target.topology == "cash_access_award":
        assert revised.elapsed_microseconds == target.elapsed_microseconds - 1000001
    else:
        assert revised.elapsed_microseconds == target.elapsed_microseconds + 1000001
    assert revised.cost == target.cost
