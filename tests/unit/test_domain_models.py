from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    CoarseIntentExtraction,
    DateExpression,
    DateExpressionAnchor,
    DateExpressionKind,
    DateFlexibility,
    DateFlexibilityMode,
    DateFlexibilityTarget,
    DateWindow,
    DateWindowPrecision,
    Holiday,
    IntentExtraction,
    OneWayDateResolutionProposal,
    ParsedRequest,
    RequestContext,
    TemporalPhrase,
    TemporalPhraseTarget,
    UnknownField,
    UnknownReason,
    Weekday,
)


def test_request_context_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="unknown IANA timezone"):
        RequestContext(reference_date=date(2026, 8, 30), timezone="Mars/Olympus")


def test_mvp_request_contracts_exclude_points_and_budget_constraints() -> None:
    for contract in (IntentExtraction, ParsedRequest):
        properties = contract.model_json_schema()["properties"]

        assert "points_balances" not in properties
        assert "cash_budget_usd" not in properties


def test_active_parsed_request_contract_is_outbound_only() -> None:
    parsed_properties = ParsedRequest.model_json_schema()["properties"]
    resolution_properties = OneWayDateResolutionProposal.model_json_schema()["properties"]

    assert {"return_expression", "return_window", "duration"}.isdisjoint(parsed_properties)
    assert {"return_date", "interpreted_duration"}.isdisjoint(resolution_properties)


def test_active_parsed_request_rejects_nested_return_temporal_state() -> None:
    with pytest.raises(ValidationError, match="cannot expose return or duration extraction"):
        ParsedRequest(
            raw_text="Leave October 5 and return next month.",
            context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
            travelers=1,
            origins=[],
            destinations=[],
            departure_expression=None,
            departure_window=None,
            cabins=[],
            search_modes=[],
            date_flexibility=[],
            repositioning_allowed=None,
            hard_constraints=[],
            unknowns=[],
            conflicts=[],
            temporal_extraction=CoarseIntentExtraction(
                temporal_phrases=[
                    TemporalPhrase(
                        applies_to=TemporalPhraseTarget.RETURN,
                        raw_text="return next month",
                    )
                ]
            ),
        )


def test_active_parsed_request_rejects_retired_return_blocker() -> None:
    with pytest.raises(ValidationError, match="cannot expose a return or duration blocker"):
        ParsedRequest(
            raw_text="Travel from SFO to BKK.",
            context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
            travelers=1,
            origins=[],
            destinations=[],
            departure_expression=None,
            departure_window=None,
            cabins=[],
            search_modes=[],
            date_flexibility=[],
            repositioning_allowed=None,
            hard_constraints=[],
            unknowns=[
                UnknownField(
                    field="return_or_duration",
                    reason=UnknownReason.MISSING,
                    detail="retired blocker",
                )
            ],
            conflicts=[],
        )


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


def test_holiday_contract_includes_all_us_federal_holidays() -> None:
    assert [holiday.value for holiday in Holiday] == [
        "new_years_day",
        "martin_luther_king_jr_day",
        "washingtons_birthday",
        "memorial_day",
        "juneteenth",
        "independence_day",
        "labor_day",
        "columbus_day",
        "veterans_day",
        "thanksgiving",
        "christmas",
    ]


def test_flexibility_contains_a_validated_nested_date_expression() -> None:
    flexibility = DateFlexibility(
        applies_to=DateFlexibilityTarget.DEPARTURE,
        mode=DateFlexibilityMode.INCLUDE,
        expression=DateExpression(
            kind=DateExpressionKind.PRECEDING_WEEKDAY,
            raw_text="the Thursday as well",
            weekday=Weekday.THURSDAY,
            month=9,
        ),
    )

    assert flexibility.expression.weekday is Weekday.THURSDAY
    assert flexibility.expression.month is None


def test_relative_weekend_requires_exactly_one_anchor() -> None:
    departure_relative = DateExpression(
        kind=DateExpressionKind.RELATIVE_WEEKEND,
        raw_text="the weekend afterwards",
        count=1,
        relative_to=DateExpressionAnchor.DEPARTURE,
    )

    assert departure_relative.relative_to is DateExpressionAnchor.DEPARTURE
    with pytest.raises(ValidationError, match="exactly one anchor"):
        DateExpression(
            kind=DateExpressionKind.RELATIVE_WEEKEND,
            raw_text="an unanchored weekend",
            count=1,
        )
    with pytest.raises(ValidationError, match="exactly one anchor"):
        DateExpression(
            kind=DateExpressionKind.RELATIVE_WEEKEND,
            raw_text="the weekend after Labor Day and departure",
            count=1,
            holiday=Holiday.LABOR_DAY,
            relative_to=DateExpressionAnchor.DEPARTURE,
        )


def test_coarse_temporal_schema_uses_kind_specific_anchor_variants() -> None:
    schema = CoarseIntentExtraction.model_json_schema()
    anchor_variants = schema["properties"]["date_anchors"]["items"]["anyOf"]

    assert {variant["$ref"] for variant in anchor_variants} == {
        "#/$defs/ExactDateAnchor",
        "#/$defs/HolidayAnchor",
        "#/$defs/MonthAnchor",
    }
    assert set(schema["$defs"]["ExactDateAnchor"]["required"]) >= {
        "kind",
        "month",
        "day",
    }
    assert set(schema["$defs"]["MonthAnchor"]["required"]) >= {"kind", "month"}
    assert set(schema["$defs"]["HolidayAnchor"]["required"]) >= {
        "kind",
        "holiday",
    }
