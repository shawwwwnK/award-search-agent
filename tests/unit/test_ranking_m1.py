"""Ranking M1: plan-backed matching, explicit status, and transfer boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pytest

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import CabinClass
from award_agent.providers.contracts import ProviderResultSet, RawField
from award_agent.ranking import MatchedJourneySet, assemble_matched_journeys
from award_agent.ranking.matching import _build_candidate, _local_date, _price_completeness


@lru_cache(maxsize=2)
def _sources(name: str) -> tuple[ProviderInputBundle, ProviderResultSet]:
    root = Path("evidence/provider-stage/saved-searches/runs") / name
    return (
        ProviderInputBundle.model_validate_json((root / "bundle.json").read_text()),
        ProviderResultSet.model_validate_json((root / "result.json").read_text()),
    )


def _match(name: str = "mixed_access", **overrides: object) -> MatchedJourneySet:
    bundle, result = _sources(name)
    options = {
        "current_session_id": bundle.current_session_id,
        "current_revision": bundle.current_revision,
        "current_effective_request": bundle.current_effective_request,
        "expected_compilation_binding_digest": bundle.expected_compilation_binding_digest,
        "policy": bundle.policy,
        "award_capability": bundle.award_capability,
        "cash_capability": bundle.cash_capability,
    }
    options.update(overrides)
    return assemble_matched_journeys(bundle.plan, result, **options)


def test_saved_plan_enumerates_all_access_pairs_and_separates_benchmark() -> None:
    matched = _match()
    assert matched.accounting.award_itineraries == 23
    assert matched.accounting.cash_positioning_observations == 76
    assert matched.accounting.direct_cash_observations == 4
    assert matched.accounting.scoped_pairs == 456
    assert matched.accounting.retained_mixed == 456
    assert sum(r.enumerated_pairs for r in matched.pairing_receipts) == 456
    assert len(matched.direct_cash_observation_ids) == 4
    assert all(j.cash_observation_id not in matched.direct_cash_observation_ids
               for j in matched.journeys)
    assert any(j.status == "conditional" and j.transfer_minutes == 138
               for j in matched.journeys)
    assert any(j.status == "rejected" for j in matched.journeys)
    assert matched.provider_result_digest
    assert MatchedJourneySet.model_validate_json(matched.model_dump_json()) == matched


def test_exact_business_preserves_unknown_party_and_award_leg_cabin() -> None:
    matched = _match("exact_business")
    assert matched.matching_policy_version == "m1-v2"
    assert matched.accounting.cash_positioning_observations == 66
    assert matched.accounting.direct_cash_observations == 6
    assert matched.accounting.scoped_pairs == 396
    assert any(j.status == "conditional" and
               {r.code for r in j.reasons} >= {
                   "award_travelers_unknown", "cash_travelers_unknown",
                   "award_leg_cabin_unreported",
               } for j in matched.journeys)
    assert any("transfer_negative" in {r.code for r in j.reasons}
               for j in matched.journeys)
    # The confirmed journey-level cabin keeps unreported leg cabins from blocking
    # admission, but it does not fabricate per-leg proof: the reason stays unknown.
    for j in matched.journeys:
        leg_cabin = [r for r in j.reasons if r.code == "award_leg_cabin_unreported"]
        if leg_cabin:
            assert all(r.dimension == "cabin" and r.state == "unknown"
                       for r in leg_cabin)
            assert not any(r.code == "award_leg_cabin_unknown"
                           for r in j.reasons)


def test_fanout_and_stale_authority_fail_closed() -> None:
    with pytest.raises(ValueError, match="fanout"):
        _match(max_combinations=455)
    with pytest.raises(ValueError, match="stale"):
        _match(current_revision=_sources("mixed_access")[0].current_revision + 1)


def _synthetic_candidate(*, minutes: int = 180, seconds: int = 0,
                         day_shift: int = 0, cash_stops: RawField | None = None,
                         cash_change: dict[str, object] | None = None,
                         award_change: dict[str, object] | None = None,
                         permission_known: bool = False,
                         request_change: dict[str, object] | None = None):
    bundle, result = _sources("mixed_access")
    queries = {q.query_id: q for q in result.execution_plan.queries}
    award = next(o for o in result.observations if o.kind == "award_itinerary"
                 and o.origin == "LAX")
    if award_change:
        award = award.model_copy(update=award_change)
    cash = next(o for o in result.observations if
                queries[o.query_id].role == "cash_access")
    plan = bundle.plan
    dependency = next(d for d in plan.positioning_dependencies)
    if permission_known:
        dependency = dependency.model_copy(update={"requested_permission": True})
    support = next(s for s in plan.support_alternatives if s.support_id == dependency.support_id)
    strategy = next(s for s in plan.supplemental_strategies if s.strategy_id == support.strategy_id)
    arrival = award.departure_instant - timedelta(minutes=minutes, seconds=seconds,
                                                  days=day_shift)
    changes = {"arrival_instant": arrival,
               "departure_instant": arrival - timedelta(hours=1)}
    if cash_stops is not None:
        changes["stops"] = cash_stops
    if cash_change:
        changes.update(cash_change)
    cash = cash.model_copy(update=changes)
    airport = {a.airport_id: a.airport_iata for a in plan.airport_directory}
    request = bundle.current_effective_request
    if day_shift:
        request = request.model_copy(update={
            "departure_window": request.departure_window.model_copy(update={
                "start": request.departure_window.start - timedelta(days=3),
            }),
        })
    request_updates: dict[str, object] = {}
    if permission_known:
        request_updates["repositioning_allowed"] = True
    if request_change:
        request_updates.update(request_change)
    if request_updates:
        request = request.model_copy(update=request_updates)
    return _build_candidate(
        award=award, cash=cash, cash_query=queries[cash.query_id],
        topology="cash_access_award", request=request,
        timezones={a.airport_iata: a.timezone for a in plan.airport_directory},
        plan=plan, airport=airport, original_origin="SFO", original_destination="BKK",
        strategy=strategy, support=support, dependency=dependency,
    )


@pytest.mark.parametrize(("minutes", "seconds", "expected"), [
    (119, 59, "rejected"), (120, 0, "conditional"), (121, 0, "conditional"),
])
def test_elapsed_transfer_boundary(minutes: int, seconds: int, expected: str) -> None:
    candidate = _synthetic_candidate(minutes=minutes, seconds=seconds)
    assert candidate.status == expected
    code = "transfer_under_120_minutes" if minutes == 119 else "transfer_at_least_120_minutes"
    assert code in {r.code for r in candidate.reasons}


@pytest.mark.parametrize(("day_shift", "expected_offset", "expected_code"), [
    (0, 0, "transfer_same_or_next_local_day"),
    (1, 1, "transfer_same_or_next_local_day"),
    (2, 2, "transfer_local_day_outside_rule"),
])
def test_local_calendar_day_rule(day_shift: int, expected_offset: int,
                                 expected_code: str) -> None:
    candidate = _synthetic_candidate(minutes=180, day_shift=day_shift)
    assert candidate.transfer_local_day_offset == expected_offset
    assert expected_code in {r.code for r in candidate.reasons}
    assert (candidate.status == "rejected") == (day_shift == 2)


@pytest.mark.parametrize("stops", [RawField(), RawField(state="value", value=1)])
def test_cash_without_proven_nonstop_or_timed_legs_is_research_lead(stops: RawField) -> None:
    candidate = _synthetic_candidate(cash_stops=stops)
    assert candidate.status == "research_lead"
    assert "cash_internal_legs_unknown" in {r.code for r in candidate.reasons}


def test_cash_sequence_contradicting_nonstop_is_research_lead() -> None:
    candidate = _synthetic_candidate(cash_change={"airport_sequence": ("SFO", "PHX", "LAX")})
    assert candidate.status == "research_lead"
    assert "cash_internal_legs_unknown" in {r.code for r in candidate.reasons}
    missing = _synthetic_candidate(cash_change={"airport_sequence": ()})
    assert missing.status == "research_lead"


def test_fully_evidenced_access_schedule_can_be_admitted() -> None:
    known = RawField(state="value", value=1)
    candidate = _synthetic_candidate(
        award_change={"returned_travelers": known, "seats": known, "findings": ()},
        cash_change={"returned_travelers": known}, permission_known=True,
    )
    assert candidate.status == "admitted", [r.code for r in candidate.reasons]
    assert candidate.price_completeness != "known"
    assert candidate.booking_obligation == "separate_tickets_unverified"


def test_journey_level_cabin_accepts_unreported_leg_cabins() -> None:
    known = RawField(state="value", value=1)
    candidate = _synthetic_candidate(
        award_change={"returned_travelers": known, "seats": known, "findings": ()},
        cash_change={"returned_travelers": known}, permission_known=True,
        request_change={"cabins": (CabinClass.ECONOMY,)},
    )
    # A requested cabin plus a confirmed journey-level cabin admits even though
    # the provider did not report per-leg cabins; the unreported legs stay visible
    # as non-blocking cabin-dimension unknowns instead of blocking admission.
    assert candidate.status == "admitted", [r.code for r in candidate.reasons]
    codes = {r.code for r in candidate.reasons}
    assert "award_cabin_supported" in codes
    assert "award_leg_cabin_unreported" in codes
    assert "award_leg_cabin_unknown" not in codes
    unreported = [r for r in candidate.reasons if r.code == "award_leg_cabin_unreported"]
    assert all(r.dimension == "cabin" and r.state == "unknown" for r in unreported)


def test_reported_leg_cabin_outside_request_still_rejects() -> None:
    bundle, result = _sources("mixed_access")
    award = next(o for o in result.observations if o.kind == "award_itinerary"
                 and o.origin == "LAX")
    known = RawField(state="value", value=1)
    business_legs = tuple(
        leg.model_copy(update={"cabin": RawField(state="value", value="business")})
        for leg in award.legs
    )
    candidate = _synthetic_candidate(
        award_change={"returned_travelers": known, "seats": known, "findings": (),
                      "legs": business_legs},
        cash_change={"returned_travelers": known}, permission_known=True,
        request_change={"cabins": (CabinClass.ECONOMY,)},
    )
    # A leg that does report a cabin outside the requested set is affirmative
    # evidence of a mismatch and must still reject the journey.
    assert candidate.status == "rejected"
    assert "award_leg_cabin_mismatch" in {r.code for r in candidate.reasons}


def test_egress_uses_award_arrival_then_cash_departure() -> None:
    bundle, result = _sources("mixed_access")
    award = next(o for o in result.observations if o.kind == "award_itinerary"
                 and o.origin == "LAX")
    known = RawField(state="value", value=1)
    award = award.model_copy(update={"returned_travelers": known,
                                     "seats": known, "findings": ()})
    cash = next(o for o in result.observations if o.kind == "cash_itinerary")
    cash_start = award.arrival_instant + timedelta(hours=3)
    cash = cash.model_copy(update={
        "origin": "BKK", "destination": "SFO", "airport_sequence": ("BKK", "SFO"),
        "departure_instant": cash_start,
        "arrival_instant": cash_start + timedelta(hours=15),
        "returned_travelers": known,
        "stops": RawField(state="value", value=0),
    })
    plan = bundle.plan
    dependency = plan.positioning_dependencies[0].model_copy(update={
        "side": "destination", "requested_permission": True,
    })
    support = next(s for s in plan.support_alternatives if s.support_id == dependency.support_id)
    strategy = next(s for s in plan.supplemental_strategies if s.strategy_id == support.strategy_id)
    query = next(q for q in result.execution_plan.queries if q.query_id == cash.query_id)
    query = query.model_copy(update={"role": "cash_egress"})
    request = bundle.current_effective_request.model_copy(update={"repositioning_allowed": True})
    candidate = _build_candidate(
        award=award, cash=cash, cash_query=query, topology="award_cash_egress",
        request=request, timezones={a.airport_iata: a.timezone for a in plan.airport_directory},
        plan=plan, airport={a.airport_id: a.airport_iata for a in plan.airport_directory},
        original_origin="LAX", original_destination="SFO",
        strategy=strategy, support=support, dependency=dependency,
    )
    assert candidate.status == "admitted", [r.code for r in candidate.reasons]
    assert candidate.transfer_airport == "BKK"
    assert candidate.transfer_minutes == 180


def test_unknown_award_price_scope_cannot_be_called_complete() -> None:
    award = next(o for o in _sources("mixed_access")[1].observations
                 if o.kind == "award_itinerary")
    known = RawField(state="value", value=1)
    award = award.model_copy(update={"points": known, "taxes_fees": known,
                                     "tax_currency": RawField(state="value", value="USD"),
                                     "program": RawField(state="value", value="test"),
                                     "taxes_fees_unit": "major", "price_scope": "unknown"})
    assert _price_completeness(award, None) == "partial"


@pytest.mark.parametrize("mutation", [
    lambda d: d["journeys"][0].update(candidate_id="f" * 64),
    lambda d: d["accounting"].update(award_itineraries=999),
    lambda d: d.update(award_summary_observation_ids=[]),
    lambda d: d["pairing_receipts"][0].update(cash_observation_ids=[]),
    lambda d: next(j for j in d["journeys"] if j["cash_observation_id"] is not None).update(
        strategy_id="invented"),
    lambda d: next(j for j in d["journeys"] if j["cash_observation_id"] is not None).update(
        activation_observation_ids=["invented"]),
    lambda d: next(j for j in d["journeys"] if j["cash_observation_id"] is not None).update(
        logical_award_query_ids=["invented"]),
])
def test_matched_contract_rejects_forged_identity_or_accounting(mutation) -> None:
    document = _match().model_dump(mode="json")
    mutation(document)
    with pytest.raises(ValueError):
        MatchedJourneySet.model_validate(document)


def test_award_internal_overlap_and_cabin_mismatch_are_rejected() -> None:
    bundle, result = _sources("exact_business")
    award = next(o for o in result.observations if o.kind == "award_itinerary")
    first, second = award.legs
    bad_second = second.model_copy(update={
        "departure_instant": first.arrival_instant - timedelta(minutes=1),
        "cabin": RawField(state="value", value="economy"),
    })
    # This checks the result-facing obligation even when the provider itinerary
    # still advertises business at its top level.
    changed = award.model_copy(update={"legs": (first, bad_second)})
    plan = bundle.plan
    candidate = _build_candidate(
        award=changed, cash=None, cash_query=None, topology="direct_award",
        request=bundle.current_effective_request,
        timezones={a.airport_iata: a.timezone for a in plan.airport_directory},
        plan=plan, airport={a.airport_id: a.airport_iata for a in plan.airport_directory},
        original_origin=changed.origin, original_destination=changed.destination,
    )
    assert candidate.status == "rejected"
    assert {"award_internal_nonpositive_layover", "award_leg_cabin_mismatch"} <= {
        reason.code for reason in candidate.reasons
    }
    missing_timed_gap = second.model_copy(update={
        "origin": "SFO", "departure_instant": None,
    })
    gapped = _synthetic_candidate(award_change={"legs": (first, missing_timed_gap)})
    assert gapped.status == "rejected"
    assert "award_internal_airport_gap" in {r.code for r in gapped.reasons}


def test_local_dates_follow_catalog_zone_across_dst_and_date_line() -> None:
    zones = {"LAX": "America/Los_Angeles", "APW": "Pacific/Apia"}
    assert _local_date(datetime(2026, 11, 1, 8, 30, tzinfo=UTC), "LAX", zones) == date(2026, 11, 1)
    assert _local_date(datetime(2026, 11, 1, 9, 30, tzinfo=UTC), "LAX", zones) == date(2026, 11, 1)
    assert _local_date(datetime(2026, 10, 5, 12, 0, tzinfo=UTC), "APW", zones) == date(2026, 10, 6)
