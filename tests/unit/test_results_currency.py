"""Observed money and one-run FX controls at the Results public seam."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from award_agent.providers.contracts import RawField
from award_agent.ranking.projection_contracts import SolutionComponent, SolutionProjection
from award_agent.ranking.style_contracts import CurrencyConversionSnapshot
from award_agent.results.currency import acquire_fx_snapshot, journey_money


def _award() -> SolutionComponent:
    projection = SolutionProjection.model_validate_json(
        Path("evidence/ranking-stage/m2/solutions/mixed_access.json").read_bytes()
    )
    return next(component for component in projection.view.components
                if component.kind == "award_itinerary")


def _snapshot() -> CurrencyConversionSnapshot:
    return CurrencyConversionSnapshot(
        snapshot_id="test-snapshot", as_of=date(2026, 10, 22), source="fixture",
        source_digest="0" * 64, rates_to_usd={"USD": Decimal(1), "CAD": Decimal("0.75")},
    )


def test_observed_cash_excludes_points_valuation_and_estimated_taxes() -> None:
    award = _award().model_copy(update={
        "points": RawField(state="value", value=100000),
        "program": RawField(state="value", value="Aeroplan"),
        "taxes_fees": RawField(state="value", value=10000),
        "taxes_fees_unit": "minor", "tax_currency": RawField(state="value", value="CAD"),
        "price_scope": "party",
    })
    cash = award.model_copy(update={
        "kind": "cash_itinerary", "cash_amount": RawField(state="value", value=20),
        "cash_currency": RawField(state="value", value="USD"),
        "price_scope": "per_traveler",
    })
    money = journey_money(award, cash, _snapshot(), travelers=2)
    assert money.award_taxes.quoted_usd == Decimal(75)
    assert money.award_taxes.per_traveler_usd == Decimal("37.5")
    assert money.cash_fare is not None and money.cash_fare.per_traveler_usd == Decimal(20)
    assert money.observed_cash_per_traveler_usd == Decimal("57.5")
    assert money.points_per_traveler == Decimal(50000)
    assert money.points_program == "Aeroplan"

    unknown = award.model_copy(update={"taxes_fees": RawField(state="unknown")})
    incomplete = journey_money(unknown, cash, _snapshot(), travelers=2)
    assert incomplete.observed_cash_per_traveler_usd is None
    assert incomplete.award_taxes.reason == "amount_unknown"
    assert incomplete.cash_fare is not None and incomplete.cash_fare.per_traveler_usd == Decimal(20)


def test_fx_snapshot_uses_one_dated_provider_response_and_explicit_outage() -> None:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    calls: list[tuple[str, float]] = []
    payload = json.dumps([
        {"date": "2026-10-23", "base": "USD", "quote": "USD", "rate": 1},
        {"date": "2026-10-23", "base": "USD", "quote": "CAD", "rate": 1.25},
    ]).encode()

    def fetch(url: str, timeout: float) -> bytes:
        calls.append((url, timeout))
        return payload

    result = acquire_fx_snapshot(("USD", "CAD"), fetch=fetch, now=now, timeout=4)
    assert len(calls) == 1
    assert "/v2/providers/ecb/rates?" in calls[0][0]
    assert result.receipt.status == "success"
    assert result.snapshot.as_of == date(2026, 10, 23)
    assert result.snapshot.rates_to_usd["CAD"] == Decimal("0.8")

    def outage(_url: str, _timeout: float) -> bytes:
        raise TimeoutError("fixture timeout")

    failed = acquire_fx_snapshot(("USD", "CAD"), fetch=outage, now=now, timeout=4)
    assert failed.receipt.status == "unavailable"
    assert failed.receipt.missing_currencies == ("CAD",)
    assert failed.snapshot.rates_to_usd == {"USD": Decimal(1)}


def test_known_zero_and_unknown_scope_have_distinct_comparison_meanings() -> None:
    zero = _award().model_copy(update={
        "taxes_fees": RawField(state="value", value=0),
        "taxes_fees_unit": "major", "tax_currency": RawField(state="value", value="USD"),
        "price_scope": "per_traveler",
    })
    result = journey_money(zero, None, _snapshot(), travelers=2)
    assert result.observed_cash_per_traveler_usd == Decimal(0)

    unknown_scope = zero.model_copy(update={"price_scope": "unknown"})
    result = journey_money(unknown_scope, None, _snapshot(), travelers=2)
    assert result.award_taxes.quoted_usd == Decimal(0)
    assert result.award_taxes.per_traveler_usd is None
    assert result.observed_cash_per_traveler_usd is None
    assert result.points_per_traveler is None

    unsupported = zero.model_copy(update={
        "taxes_fees": RawField(state="value", value=1000),
        "taxes_fees_unit": "minor", "tax_currency": RawField(state="value", value="JPY"),
    })
    result = journey_money(unsupported, None, _snapshot(), travelers=2)
    assert result.award_taxes.reason == "minor_unit_unsupported"
    assert result.observed_cash_per_traveler_usd is None


def test_fx_partial_and_malformed_responses_never_create_parity() -> None:
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)

    def payload(rows: list[dict[str, object]]) -> Callable[[str, float], bytes]:
        return lambda _url, _timeout: json.dumps(rows).encode()

    identity = {"date": "2026-10-23", "base": "USD", "quote": "USD", "rate": 1}
    cad = {"date": "2026-10-23", "base": "USD", "quote": "CAD", "rate": 1.25}
    partial = acquire_fx_snapshot(("USD", "CAD"), now=now, fetch=payload([identity]))
    assert partial.receipt.status == "partial"
    assert partial.snapshot.rates_to_usd == {"USD": Decimal(1)}
    assert partial.receipt.effective_date == date(2026, 10, 23)

    for rows in (
        [identity, {**cad, "date": "2026-10-22"}],
        [identity, {**cad, "rate": 0}],
        [identity, {**cad, "rate": "NaN"}],
        [identity, {**cad, "date": "2026-10-25"}],
        [identity, cad, cad],
    ):
        failed = acquire_fx_snapshot(("USD", "CAD"), now=now, fetch=payload(rows))
        assert failed.receipt.status == "unavailable"
        assert failed.snapshot.rates_to_usd == {"USD": Decimal(1)}
