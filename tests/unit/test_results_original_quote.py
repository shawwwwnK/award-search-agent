"""Original currency quote parsing independent of FX and price scope."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import JsonValue

from award_agent.providers.contracts import RawField
from award_agent.results.currency import original_quote_major


def _field(value: JsonValue) -> RawField:
    return RawField(state="value", value=value)


def test_minor_quotes_convert_only_supported_currencies() -> None:
    assert original_quote_major(_field(11650), _field("CAD"), "minor") == Decimal("116.5")
    assert original_quote_major(_field(2820), _field("USD"), "minor") == Decimal("28.2")
    assert original_quote_major(_field(0), _field("CAD"), "minor") == Decimal(0)
    assert original_quote_major(_field(2820), _field("JPY"), "minor") is None


def test_major_quotes_are_preserved_for_supported_and_other_currencies() -> None:
    assert original_quote_major(_field("116.50"), _field("CAD")) == Decimal("116.50")
    assert original_quote_major(_field("28.20"), _field("USD")) == Decimal("28.20")
    assert original_quote_major(_field(2820), _field("JPY"), "major") == Decimal(2820)


@pytest.mark.parametrize(
    ("amount", "currency", "unit"),
    [
        (RawField(state="unknown"), _field("USD"), "major"),
        (RawField(state="absent"), _field("USD"), "major"),
        (_field(True), _field("USD"), "major"),
        (_field("not-a-number"), _field("USD"), "major"),
        (_field("NaN"), _field("USD"), "major"),
        (_field("Infinity"), _field("USD"), "major"),
        (_field(-1), _field("USD"), "major"),
        (_field(1), RawField(state="absent"), "major"),
        (_field(1), _field("usd"), "major"),
        (_field(1), _field("USD"), "unknown"),
    ],
)
def test_invalid_or_unsupported_original_quotes_are_unavailable(
    amount: RawField, currency: RawField, unit: str,
) -> None:
    assert original_quote_major(amount, currency, unit) is None


def test_original_quote_does_not_depend_on_scope_or_fx_availability() -> None:
    # Scope and FX are deliberately not inputs: the reported quote remains available
    # when either is unknown or unavailable to the caller.
    assert original_quote_major(_field(11650), _field("CAD"), "minor") == Decimal("116.5")
