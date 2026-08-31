from datetime import date

from award_agent.domain import (
    Ambiguity,
    ClarificationAction,
    CoarseIntentExtraction,
    DateResolutionProposal,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    LocationKind,
    LocationRef,
    MonthAnchor,
    ProposedDateWindow,
    RawRequest,
    RequestContext,
    ResolvedTemporalAnchor,
    SearchMode,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalTarget,
    UnresolvedTemporalConstraint,
)
from award_agent.intent.workflow import understand_request


class FakePipeline:
    def __init__(
        self,
        extraction: CoarseIntentExtraction,
        proposal: DateResolutionProposal,
    ) -> None:
        self.extraction = extraction
        self.proposal = proposal
        self.resolved_anchors: list[ResolvedTemporalAnchor] | None = None

    def extract(self, request: RawRequest) -> CoarseIntentExtraction:
        return self.extraction

    def resolve_dates(
        self,
        request: RawRequest,
        extraction: CoarseIntentExtraction,
        resolved_anchors: list[ResolvedTemporalAnchor],
    ) -> DateResolutionProposal:
        self.resolved_anchors = resolved_anchors
        return self.proposal


class FakeHolidayProvider:
    def holiday_date(self, holiday: Holiday, year: int) -> date:
        if holiday is Holiday.NEW_YEARS_DAY:
            return date(year, 1, 1)
        if holiday is Holiday.LABOR_DAY:
            return date(year, 9, 7)
        raise AssertionError(f"unexpected holiday: {holiday}")


def request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(
            reference_date=date(2026, 8, 29),
            timezone="America/Los_Angeles",
        ),
    )


def location(kind: LocationKind, value: str, raw_text: str) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=raw_text)


def window(
    start: date,
    end: date,
    supporting_text: str,
    *,
    assumptions: list[str] | None = None,
) -> ProposedDateWindow:
    return ProposedDateWindow(
        start=start,
        end=end,
        supporting_text=[supporting_text],
        interpretation="test proposal",
        assumptions=assumptions or [],
    )


def test_early_may_is_coarse_first_then_proposed_as_a_range() -> None:
    text = "My boyfriend and I want to go to Thailand from SF for about 10 days in early May"
    extraction = CoarseIntentExtraction(
        travelers=2,
        origins=[location(LocationKind.CITY, "San Francisco", "SF")],
        destinations=[location(LocationKind.COUNTRY, "Thailand", "Thailand")],
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="departure_month",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="May",
                month=5,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="early",
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="about 10 days",
            ),
        ],
    )
    proposal = DateResolutionProposal(
        departure=window(
            date(2027, 5, 1),
            date(2027, 5, 10),
            "early May",
            assumptions=["Interpreted early May as May 1 through May 10."],
        ),
        return_date=window(date(2027, 5, 10), date(2027, 5, 21), "about 10 days"),
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2027, 5, 1)
    assert result.parsed_request.return_window is not None
    assert result.clarification.action is ClarificationAction.NONE
    assert pipeline.resolved_anchors is not None
    assert pipeline.resolved_anchors[0].end == date(2027, 5, 31)


def test_after_new_year_stays_unresolved_instead_of_inventing_a_week() -> None:
    text = "My boyfriend and I want to go to Europe from LA for 1 or 2 weeks after new year"
    extraction = CoarseIntentExtraction(
        travelers=2,
        origins=[location(LocationKind.CITY, "Los Angeles", "LA")],
        destinations=[location(LocationKind.REGION, "Europe", "Europe")],
        date_anchors=[
            HolidayAnchor(
                kind="holiday",
                anchor_id="new_year",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="new year",
                holiday=Holiday.NEW_YEARS_DAY,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="after new year",
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="1 or 2 weeks",
            ),
        ],
    )
    proposal = DateResolutionProposal(
        unresolved=[
            UnresolvedTemporalConstraint(
                field="departure",
                raw_text="after new year",
                reason="The phrase has no bounded departure period.",
            ),
            UnresolvedTemporalConstraint(
                field="return_or_duration",
                raw_text="1 or 2 weeks",
                reason="A return range needs a bounded departure range.",
            ),
        ]
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(
        request(text),
        pipeline,
        pipeline,
        FakeHolidayProvider(),
    )

    assert result.parsed_request.departure_window is None
    assert result.clarification.field == "departure"
    assert pipeline.resolved_anchors is not None
    assert pipeline.resolved_anchors[0].start == date(2027, 1, 1)


def test_october_and_two_weeks_produce_bounded_ranges() -> None:
    text = "My boyfriend and I want to go to South East Asia from New York for 2 weeks in October"
    extraction = CoarseIntentExtraction(
        travelers=2,
        origins=[location(LocationKind.CITY, "New York", "New York")],
        destinations=[location(LocationKind.REGION, "Southeast Asia", "South East Asia")],
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="october",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="October",
                month=10,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="2 weeks",
            )
        ],
    )
    proposal = DateResolutionProposal(
        departure=window(date(2026, 10, 1), date(2026, 10, 31), "October"),
        return_date=window(date(2026, 10, 15), date(2026, 11, 14), "2 weeks"),
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.end == date(2026, 10, 31)
    assert result.parsed_request.return_window is not None
    assert result.parsed_request.return_window.end == date(2026, 11, 14)
    assert result.clarification.action is ClarificationAction.NONE


def test_tentative_sao_paulo_and_january_are_preserved_without_a_return() -> None:
    text = (
        "I want to go on a solo trip to Brazil from SF. Probably I want to go to Sao Paolo. "
        "Maybe sometime in January"
    )
    extraction = CoarseIntentExtraction(
        travelers=1,
        origins=[location(LocationKind.CITY, "San Francisco", "SF")],
        destinations=[
            location(LocationKind.COUNTRY, "Brazil", "Brazil"),
            location(LocationKind.CITY, "São Paulo", "Sao Paolo"),
        ],
        ambiguities=[
            Ambiguity(
                field="destination_preference",
                detail="São Paulo is tentative rather than a hard destination.",
                raw_text="Probably I want to go to Sao Paolo",
            )
        ],
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="january",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="January",
                month=1,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="Maybe sometime in January",
            )
        ],
    )
    proposal = DateResolutionProposal(
        departure=window(
            date(2027, 1, 1),
            date(2027, 1, 31),
            "Maybe sometime in January",
        ),
        unresolved=[
            UnresolvedTemporalConstraint(
                field="return_or_duration",
                raw_text="Maybe sometime in January",
                reason="No return timing or trip duration was stated.",
            )
        ],
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.destinations[1].value == "São Paulo"
    assert result.clarification.field == "return_or_duration"
    assert any(
        unknown.field == "destination_preference"
        for unknown in result.parsed_request.unknowns
    )


def test_missing_origin_is_still_the_highest_priority_question() -> None:
    text = "I want to go to Paris for a week in May using points."
    extraction = CoarseIntentExtraction(
        travelers=1,
        destinations=[location(LocationKind.CITY, "Paris", "Paris")],
        search_modes=[SearchMode.AWARD],
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="may",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="May",
                month=5,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="a week",
            )
        ],
    )
    proposal = DateResolutionProposal(
        departure=window(date(2027, 5, 1), date(2027, 5, 31), "May"),
        return_date=window(date(2027, 5, 8), date(2027, 6, 7), "a week"),
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.clarification.field == "origin"


def test_conflicting_proposed_dates_are_preserved_and_clarified() -> None:
    text = "Leave Boston for Rome July 10 and come back July 8."
    extraction = CoarseIntentExtraction(
        travelers=1,
        origins=[location(LocationKind.CITY, "Boston", "Boston")],
        destinations=[location(LocationKind.CITY, "Rome", "Rome")],
        date_anchors=[
            ExactDateAnchor(
                kind="exact_date",
                anchor_id="depart",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="July 10",
                month=7,
                day=10,
            ),
            ExactDateAnchor(
                kind="exact_date",
                anchor_id="return",
                applies_to=TemporalTarget.RETURN,
                raw_text="July 8",
                month=7,
                day=8,
            ),
        ],
    )
    proposal = DateResolutionProposal(
        departure=window(date(2027, 7, 10), date(2027, 7, 10), "July 10"),
        return_date=window(date(2027, 7, 8), date(2027, 7, 8), "July 8"),
    )
    pipeline = FakePipeline(extraction, proposal)

    result = understand_request(request(text), pipeline, pipeline)

    assert [conflict.code for conflict in result.parsed_request.conflicts] == [
        "return_before_departure"
    ]
    assert result.clarification.field == "dates"
