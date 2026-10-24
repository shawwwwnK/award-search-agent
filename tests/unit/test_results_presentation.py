"""Schedule interpretation uses source instants and frozen airport-local display facts."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from award_agent.providers.contracts import RawField, content_digest
from award_agent.ranking.projection_contracts import (
    ProjectedLeg,
    ProjectedTime,
    SolutionProjection,
)
from award_agent.ranking.style_contracts import CurrencyConversionSnapshot
from award_agent.results.currency import FxAcquisition, FxAcquisitionReceipt
from award_agent.results.presentation import resolve_workspace


def _projected_time(instant: str | None, local: str | None, zone: str | None) -> ProjectedTime:
    return ProjectedTime(
        instant=datetime.fromisoformat(instant) if instant else None,
        local_iso=local, timezone=zone,
    )


def _complex_projection(*, unknown_middle: bool = False,
                        broken_airport: bool = False,
                        unknown_zone: bool = False) -> tuple[SolutionProjection, str]:
    path = Path("evidence/end-to-end/presentation/iterations/006/admitted/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    alternative = next(item for item in projection.view.alternatives
                       if item.status in {"admitted", "conditional"}
                       and item.topology == "cash_access_award")
    source = {item.observation_id: item for item in projection.view.components}
    award = source[alternative.award_observation_id]
    assert alternative.cash_observation_id is not None
    cash = source[alternative.cash_observation_id]
    carrier = award.legs[0].carrier
    flight_number = award.legs[0].flight_number
    cabin = award.legs[0].cabin

    def leg(origin: str, destination: str, dep: ProjectedTime,
            arr: ProjectedTime) -> ProjectedLeg:
        return ProjectedLeg(origin=origin, destination=destination,
                            departure=dep, arrival=arr, carrier=carrier,
                            flight_number=flight_number, cabin=cabin)

    cash_dep = _projected_time("2027-01-01T08:00:00+00:00",
                               "2027-01-01T00:00:00-08:00", "America/Los_Angeles")
    cash_arr = _projected_time("2027-01-01T09:00:00+00:00",
                               "2027-01-01T01:00:00-08:00", "America/Los_Angeles")
    lax_dep = _projected_time("2027-01-01T10:00:00+00:00",
                              "2027-01-01T02:00:00-08:00", "America/Los_Angeles")
    nrt_arr = _projected_time("2027-01-02T10:00:00+00:00",
                              "2027-01-02T19:00:00+09:00", "Asia/Tokyo")
    nrt_dep = _projected_time(
        None if unknown_middle else "2027-01-02T12:00:00+00:00",
        None if unknown_middle or unknown_zone else "2027-01-02T21:00:00+09:00",
        None if unknown_zone else "Asia/Tokyo",
    )
    sin_arr = _projected_time("2027-01-02T18:00:00+00:00",
                              "2027-01-03T02:00:00+08:00", "Asia/Singapore")
    sin_dep = _projected_time("2027-01-02T21:00:00+00:00",
                              "2027-01-03T05:00:00+08:00", "Asia/Singapore")
    bkk_arr = _projected_time("2027-01-03T00:00:00+00:00",
                              "2027-01-03T07:00:00+07:00", "Asia/Bangkok")
    changed_cash = cash.model_copy(update={
        "departure": cash_dep, "arrival": cash_arr,
        "legs": (leg("SFO", "LAX", cash_dep, cash_arr),),
    })
    changed_award = award.model_copy(update={
        "departure": lax_dep, "arrival": bkk_arr,
        "legs": (
            leg("LAX", "NRT", lax_dep, nrt_arr),
            leg("ICN" if broken_airport else "NRT", "SIN", nrt_dep, sin_arr),
            leg("SIN", "BKK", sin_dep, bkk_arr),
        ),
    })
    changed_alternative = alternative.model_copy(update={
        "departure": cash_dep, "arrival": bkk_arr,
        "elapsed_minutes": Decimal(2400), "elapsed_microseconds": 144000000000,
        "transfer_minutes": 999,
    })
    view = projection.view.model_copy(update={
        "components": tuple(changed_cash if item.observation_id == cash.observation_id
                            else changed_award if item.observation_id == award.observation_id
                            else item for item in projection.view.components),
        "alternatives": tuple(changed_alternative if item.candidate_id == alternative.candidate_id
                              else item for item in projection.view.alternatives),
    })
    receipt = projection.receipt.model_copy(update={"view_digest": content_digest(view)})
    changed = SolutionProjection.model_validate({"view": view, "receipt": receipt})
    return changed, alternative.candidate_id


def test_connections_are_each_derived_from_adjacent_instants() -> None:
    projection, candidate_id = _complex_projection()
    journey = next(item for item in resolve_workspace(projection).journeys
                   if item.candidate_id == candidate_id)
    assert [(item.airport, item.wait_minutes, item.kind) for item in journey.connections] == [
        ("LAX", 60, "separate_booking"),
        ("NRT", 120, "award_connection"),
        ("SIN", 180, "award_connection"),
    ]
    assert journey.arrival.local_iso == "2027-01-03T07:00:00+07:00"
    assert journey.arrival.day_change == 2
    assert journey.departure.day_change == 0


def test_unknown_time_or_airport_continuity_never_invents_wait() -> None:
    for kwargs, expected in [
        ({"unknown_middle": True}, "timing_unknown"),
        ({"broken_airport": True}, "airport_continuity_unknown"),
    ]:
        projection, candidate_id = _complex_projection(**kwargs)
        journey = next(item for item in resolve_workspace(projection).journeys
                       if item.candidate_id == candidate_id)
        assert journey.connections[1].wait_minutes is None
        assert journey.connections[1].unknown_reason == expected


def test_missing_local_zone_preserves_instant_wait_but_not_local_clock() -> None:
    projection, candidate_id = _complex_projection(unknown_zone=True)
    journey = next(item for item in resolve_workspace(projection).journeys
                   if item.candidate_id == candidate_id)
    assert journey.connections[1].wait_minutes == 120
    assert journey.legs[2].departure.local_iso is None
    assert journey.legs[2].departure.day_change is None


def test_direct_cash_benchmark_uses_frozen_rate_and_retains_original_quote() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/incomplete/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    benchmark_id = projection.view.direct_cash_observation_ids[0]
    benchmark = next(item for item in projection.view.components
                     if item.observation_id == benchmark_id)
    changed = benchmark.model_copy(update={
        "cash_amount": RawField(state="value", value=100),
        "cash_currency": RawField(state="value", value="CAD"),
        "price_scope": "per_traveler",
    })

    def with_rates(rates: dict[str, Decimal]) -> SolutionProjection:
        snapshot = CurrencyConversionSnapshot(
            snapshot_id="cad-benchmark-control", as_of=projection.view.fx_snapshot.as_of,
            source="synthetic-rate-control", source_digest="a" * 64,
            rates_to_usd=rates,
        )
        view = projection.view.model_copy(update={
            "components": tuple(changed if item.observation_id == benchmark_id else item
                                for item in projection.view.components),
            "fx_snapshot": snapshot,
        })
        receipt = projection.receipt.model_copy(update={
            "view_digest": content_digest(view),
            "fx_snapshot_digest": content_digest(snapshot),
        })
        return SolutionProjection.model_validate({"view": view, "receipt": receipt})

    converted = resolve_workspace(with_rates({"USD": Decimal(1), "CAD": Decimal("0.75")}))
    cash = next(item for item in converted.components if item.observation_id == benchmark_id)
    assert cash.money.per_traveler_usd == Decimal(75)
    assert cash.money.approximate_conversion is True
    assert cash.money.raw_amount.value == 100
    assert cash.money.raw_currency.value == "CAD"
    assert cash.money.conversion_snapshot_id == "cad-benchmark-control"

    missing = resolve_workspace(with_rates({"USD": Decimal(1)}))
    cash = next(item for item in missing.components if item.observation_id == benchmark_id)
    assert cash.money.per_traveler_usd is None
    assert cash.money.reason == "rate_unavailable"
    assert cash.money.raw_amount.value == 100
    assert cash.money.raw_currency.value == "CAD"


def test_supplied_fx_provenance_is_preserved_and_must_match_source_snapshot() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/incomplete/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    retrieved_at = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
    acquisition = FxAcquisition(
        snapshot=projection.view.fx_snapshot,
        receipt=FxAcquisitionReceipt(
            status="partial", source="fixture-rate-source", request_url="https://example.test/rates",
            requested_currencies=("USD", "CAD", "EUR"),
            received_currencies=("USD", "CAD"), missing_currencies=("EUR",),
            retrieved_at=retrieved_at, effective_date=projection.view.fx_snapshot.as_of,
            raw_response_digest="b" * 64, reason="EUR unavailable",
        ),
    )
    evidence = resolve_workspace(projection, fx_acquisition=acquisition)
    assert evidence.fx_acquisition is not None
    assert evidence.fx_acquisition.receipt.retrieved_at == retrieved_at
    assert evidence.fx_acquisition.receipt.reason == "EUR unavailable"
    assert resolve_workspace(projection).fx_acquisition is None

    different = acquisition.model_copy(update={"snapshot": CurrencyConversionSnapshot(
        snapshot_id="different", as_of=projection.view.fx_snapshot.as_of,
        source="fixture-rate-source", source_digest="c" * 64,
        rates_to_usd={"USD": Decimal(1)},
    )})
    with pytest.raises(ValueError, match="FX acquisition snapshot"):
        resolve_workspace(projection, fx_acquisition=different)

    fallback = CurrencyConversionSnapshot(
        snapshot_id="outage-control", as_of=projection.view.fx_snapshot.as_of,
        source="fx-acquisition-unavailable", source_digest="d" * 64,
        rates_to_usd={"USD": Decimal(1)},
    )
    view = projection.view.model_copy(update={"fx_snapshot": fallback})
    receipt = projection.receipt.model_copy(update={
        "view_digest": content_digest(view), "fx_snapshot_digest": content_digest(fallback),
    })
    outage_projection = SolutionProjection.model_validate({"view": view, "receipt": receipt})
    outage = FxAcquisition(
        snapshot=fallback,
        receipt=FxAcquisitionReceipt(
            status="unavailable", source="fixture-rate-source", request_url="https://example.test/rates",
            requested_currencies=("USD", "CAD"), received_currencies=("USD",),
            missing_currencies=("CAD",), retrieved_at=retrieved_at,
            effective_date=None, raw_response_digest=None, reason="rate source timed out",
        ),
    )
    retained = resolve_workspace(outage_projection, fx_acquisition=outage)
    assert retained.fx_acquisition is not None
    assert retained.fx_acquisition.receipt.retrieved_at == retrieved_at
    assert retained.fx_acquisition.receipt.reason == "rate source timed out"


def test_award_summary_lead_retains_material_cabin_and_stop_evidence() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/incomplete/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    observation_id = projection.view.award_summary_observation_ids[0]
    source = next(item for item in projection.view.components
                  if item.observation_id == observation_id)
    evidence = resolve_workspace(projection)
    lead = next(item for item in evidence.leads if item.reference_id == observation_id)
    component = next(item for item in evidence.components if item.observation_id == observation_id)
    assert lead.award_observation_id == source.observation_id
    assert lead.explanations == ("This award observation lacks a complete itinerary schedule.",)
    assert component.mixed_cabin_pct == source.mixed_cabin_pct
    assert component.airport_sequence == source.airport_sequence
    assert component.stops == source.stops
    assert component.duration_minutes == source.duration_minutes
