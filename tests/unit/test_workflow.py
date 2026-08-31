from datetime import date

from award_agent.domain import (
    ClarificationAction,
    DateExpression,
    DateExpressionKind,
    DurationConstraint,
    Holiday,
    IntentExtraction,
    LocationKind,
    LocationRef,
    RawRequest,
    RequestContext,
    SearchMode,
)
from award_agent.intent.workflow import understand_request


class FakeExtractor:
    def __init__(self, extraction: IntentExtraction) -> None:
        self._extraction = extraction

    def extract(self, request: RawRequest) -> IntentExtraction:
        return self._extraction


def request(text: str = "test request") -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(
            reference_date=date(2026, 8, 30),
            timezone="America/Los_Angeles",
        ),
    )


def test_representative_request_is_grounded_and_needs_no_clarification() -> None:
    extraction = IntentExtraction(
        travelers=2,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[
            LocationRef(kind=LocationKind.COUNTRY, value="Thailand", raw_text="Thailand")
        ],
        departure=DateExpression(
            kind=DateExpressionKind.HOLIDAY_WINDOW,
            raw_text="Labor Day weekend",
            holiday=Holiday.LABOR_DAY,
        ),
        duration=DurationConstraint(raw_text="about 10 days", days=10, approximate=True),
        search_modes=[SearchMode.AWARD, SearchMode.CASH],
    )

    result = understand_request(request(), FakeExtractor(extraction))

    assert result.clarification.action is ClarificationAction.NONE
    assert result.parsed_request.origins[0].kind is LocationKind.CITY
    assert result.parsed_request.origins[0].value == "San Francisco"
    assert result.parsed_request.return_window is not None
    assert {unknown.field for unknown in result.parsed_request.unknowns} >= {
        "cabin",
        "points_balances",
    }


def test_missing_origin_is_the_single_highest_priority_question() -> None:
    extraction = IntentExtraction(
        destinations=[LocationRef(kind=LocationKind.CITY, value="Paris", raw_text="Paris")],
        departure=DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="May 5",
            month=5,
            day=5,
        ),
        duration=DurationConstraint(raw_text="a week", days=7),
        search_modes=[SearchMode.AWARD],
    )

    result = understand_request(request(), FakeExtractor(extraction))

    assert result.clarification.action is ClarificationAction.ASK
    assert result.clarification.field == "origin"
    assert result.clarification.question == "Where would you like to depart from?"


def test_conflicting_dates_are_preserved_and_clarified_before_missing_fields() -> None:
    extraction = IntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="Boston", raw_text="Boston")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Rome", raw_text="Rome")],
        departure=DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="July 10",
            month=7,
            day=10,
            year=2027,
        ),
        return_date=DateExpression(
            kind=DateExpressionKind.BOUND,
            raw_text="before July 8",
            boundary="before",
            month=7,
            day=8,
            year=2027,
        ),
        duration=DurationConstraint(raw_text="10-day trip", days=10),
    )

    result = understand_request(request(), FakeExtractor(extraction))

    assert [conflict.code for conflict in result.parsed_request.conflicts] == [
        "return_before_departure"
    ]
    assert result.clarification.field == "dates"


def test_unresolved_date_is_not_silently_normalized() -> None:
    extraction = IntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="Portland", raw_text="Portland")],
        destinations=[LocationRef(kind=LocationKind.REGION, value="Europe", raw_text="Europe")],
        departure=DateExpression(
            kind=DateExpressionKind.UNRESOLVED,
            raw_text="next spring",
            reason="Spring is not a single bounded travel period.",
        ),
        duration=DurationConstraint(raw_text="a week", days=7),
    )

    result = understand_request(request(), FakeExtractor(extraction))

    assert result.parsed_request.departure_window is None
    assert result.clarification.field == "departure"
    unknown = next(item for item in result.parsed_request.unknowns if item.field == "departure")
    assert unknown.raw_text == "next spring"


def test_yearless_return_date_is_resolved_after_departure_across_new_year() -> None:
    extraction = IntentExtraction(
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="Seattle", raw_text="Seattle")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure=DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="December 20",
            month=12,
            day=20,
        ),
        return_date=DateExpression(
            kind=DateExpressionKind.EXACT,
            raw_text="January 5",
            month=1,
            day=5,
        ),
    )

    result = understand_request(request(), FakeExtractor(extraction))

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.return_window is not None
    assert result.parsed_request.departure_window.start == date(2026, 12, 20)
    assert result.parsed_request.return_window.start == date(2027, 1, 5)
    assert result.parsed_request.conflicts == []
