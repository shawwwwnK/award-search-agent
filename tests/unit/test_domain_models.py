from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    DateExpression,
    DateExpressionKind,
    DateWindow,
    DateWindowPrecision,
    RequestContext,
)


def test_request_context_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="unknown IANA timezone"):
        RequestContext(reference_date=date(2026, 8, 30), timezone="Mars/Olympus")


def test_date_window_rejects_reverse_order() -> None:
    with pytest.raises(ValidationError, match="date window end precedes start"):
        DateWindow(
            start=date(2026, 8, 31),
            end=date(2026, 8, 30),
            precision=DateWindowPrecision.WINDOW,
            raw_text="the wrong way around",
        )


def test_date_expression_discards_components_from_another_kind() -> None:
    expression = DateExpression(
        kind=DateExpressionKind.EXACT,
        raw_text="October 5",
        month=10,
        day=5,
        year=2026,
        count=2,
    )

    assert expression.count is None
    assert expression.year is None


def test_date_expression_normalizes_an_explicit_supported_holiday() -> None:
    expression = DateExpression(
        kind=DateExpressionKind.HOLIDAY_WINDOW,
        raw_text="Labor Day weekend",
    )

    assert expression.holiday == "labor_day"
