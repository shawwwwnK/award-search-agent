from datetime import date

from award_agent.domain import (
    Ambiguity,
    AnchorReference,
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    ClarificationAction,
    CoarseIntentExtraction,
    DurationModifier,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    LocationKind,
    LocationRef,
    ModelPassRepairTrace,
    MonthAnchor,
    MonthPortionConstraint,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeWeekendConstraint,
    RequestContext,
    RequestFieldReference,
    SearchMode,
    SemanticDurationConstraint,
    SymbolicContextReference,
    TemporalDirection,
    TemporalEdge,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    UnboundedBoundaryConstraint,
)
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
)
from award_agent.intent.workflow import understand_request


class FakePipeline:
    def __init__(
        self,
        extraction: CoarseIntentExtraction,
        relations: TemporalRelationGraph,
    ) -> None:
        self.extraction = extraction
        self.relations = relations
        self.coarse_input: CoarseExtractionInput | None = None
        self.temporal_input: TemporalInterpretationInput | None = None

    def extract(self, model_input: CoarseExtractionInput) -> CoarseIntentExtraction:
        self.coarse_input = model_input
        return self.extraction

    def repair_extract(self, model_input: CoarseExtractionRepairInput) -> CoarseIntentExtraction:
        return self.extraction

    def resolve_dates(
        self,
        model_input: TemporalInterpretationInput,
    ) -> TemporalResolutionResult:
        self.temporal_input = model_input
        anchor_ids = {
            original.anchor_id: catalog.anchor_id
            for original, catalog in zip(
                self.extraction.date_anchors,
                model_input.explicit_anchor_catalog,
                strict=True,
            )
        }
        constraints = []
        for constraint in self.relations.constraints:
            updates: dict[str, object] = {}
            constraint_anchor_id = getattr(constraint, "anchor_id", None)
            if constraint_anchor_id is not None:
                updates["anchor_id"] = anchor_ids[constraint_anchor_id]
            reference = getattr(constraint, "reference", None)
            if isinstance(reference, AnchorReference):
                updates["reference"] = reference.model_copy(
                    update={"anchor_id": anchor_ids[reference.anchor_id]}
                )
            constraints.append(constraint.model_copy(update=updates))
        return TemporalResolutionResult(
            relations=self.relations.model_copy(update={"constraints": constraints}),
            repair_trace=ModelPassRepairTrace(
                first_attempt_valid=True,
                repair_ran=False,
                repair_succeeded=False,
            ),
        )

    def repair_dates(
        self,
        model_input: TemporalInterpretationInput,
        rejected_output: TemporalRelationGraph,
        validation_errors: list[StructuredValidationErrorView],
    ) -> TemporalRelationGraph:
        return rejected_output


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


def anchor_window(
    target: TemporalTarget,
    anchor_id: str,
    raw_text: str,
) -> AnchorWindowConstraint:
    return AnchorWindowConstraint(
        kind="anchor_window",
        target=target,
        anchor_id=anchor_id,
        window="anchor",
        raw_text=raw_text,
    )


def duration(
    raw_text: str,
    minimum: int,
    maximum: int,
    unit: TemporalUnit,
    modifier: DurationModifier = DurationModifier.EXACT,
) -> SemanticDurationConstraint:
    return SemanticDurationConstraint(
        kind="duration",
        reference=RequestFieldReference(
            kind="request_field",
            field=TemporalTarget.DEPARTURE,
            edge=TemporalEdge.END,
        ),
        stated_minimum_quantity=minimum,
        stated_maximum_quantity=maximum,
        unit=unit,
        modifier=modifier,
        raw_text=raw_text,
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
    relations = TemporalRelationGraph(
        constraints=[
            MonthPortionConstraint(
                kind="month_portion",
                target=TemporalTarget.DEPARTURE,
                anchor_id="departure_month",
                portion="early",
                raw_text="early",
            ),
            duration(
                "about 10 days",
                10,
                10,
                TemporalUnit.DAY,
                DurationModifier.APPROXIMATE,
            ),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.start == date(2027, 5, 1)
    assert result.parsed_request.return_window is not None
    assert result.clarification.action is ClarificationAction.NONE
    assert pipeline.coarse_input == CoarseExtractionInput(request_text=text)
    assert pipeline.temporal_input is not None
    assert pipeline.temporal_input.explicit_anchor_catalog[0].anchor_id == (
        "anchor:month:departure:77:80"
    )
    assert "2027-05-31" not in pipeline.temporal_input.model_dump_json()


def test_explicit_airport_code_is_preserved_for_downstream_workflows() -> None:
    text = "Help me find award flights from LAX to Sydney."
    extraction = CoarseIntentExtraction(
        origins=[
            location(
                LocationKind.AIRPORT,
                "Los Angeles International Airport",
                "LAX",
            )
        ],
        destinations=[location(LocationKind.CITY, "Sydney", "Sydney")],
        search_modes=[SearchMode.AWARD],
    )
    pipeline = FakePipeline(extraction, TemporalRelationGraph())

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.origins == [location(LocationKind.AIRPORT, "LAX", "LAX")]
    assert result.clarification.field == "departure"


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
    relations = TemporalRelationGraph(
        constraints=[
            UnboundedBoundaryConstraint(
                kind="unbounded_boundary",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="new_year"),
                direction=TemporalDirection.AFTER,
                raw_text="after new year",
            ),
            duration(
                "1 or 2 weeks",
                1,
                2,
                TemporalUnit.WEEK,
                DurationModifier.ALTERNATIVE,
            ),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(
        request(text),
        pipeline,
        pipeline,
        FakeHolidayProvider(),
    )

    assert result.parsed_request.departure_window is None
    assert result.parsed_request.date_resolution is not None
    assert result.parsed_request.date_resolution.interpreted_duration is not None
    assert result.parsed_request.date_resolution.interpreted_duration.minimum_days == 7
    assert result.parsed_request.date_resolution.interpreted_duration.maximum_days == 14
    assert result.clarification.field == "departure"
    assert pipeline.temporal_input is not None
    assert pipeline.temporal_input.explicit_anchor_catalog[0].anchor_id == (
        "anchor:holiday:departure:71:79"
    )
    assert "2027-01-01" not in pipeline.temporal_input.model_dump_json()


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
    relations = TemporalRelationGraph(
        constraints=[
            anchor_window(TemporalTarget.DEPARTURE, "october", "October"),
            duration("2 weeks", 2, 2, TemporalUnit.WEEK),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.departure_window.end == date(2026, 10, 31)
    assert result.parsed_request.return_window is not None
    assert result.parsed_request.return_window.end == date(2026, 11, 14)
    assert result.clarification.action is ClarificationAction.NONE


def test_one_month_duration_crosses_year_with_calendar_arithmetic_in_workflow() -> None:
    text = "Leave December 31 for 1 month."
    extraction = CoarseIntentExtraction(
        date_anchors=[
            ExactDateAnchor(
                kind="exact_date",
                anchor_id="new_years_eve",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="December 31",
                month=12,
                day=31,
                year=2026,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="1 month",
            )
        ],
    )
    relations = TemporalRelationGraph(
        constraints=[
            anchor_window(TemporalTarget.DEPARTURE, "new_years_eve", "December 31"),
            duration("1 month", 1, 1, TemporalUnit.MONTH),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.return_window is not None
    assert (
        result.parsed_request.return_window.start,
        result.parsed_request.return_window.end,
    ) == (date(2027, 1, 31), date(2027, 1, 31))
    assert result.parsed_request.date_resolution is not None
    assert result.parsed_request.date_resolution.interpreted_duration is not None
    assert (
        result.parsed_request.date_resolution.interpreted_duration.minimum_days,
        result.parsed_request.date_resolution.interpreted_duration.maximum_days,
    ) == (31, 31)


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
    relations = TemporalRelationGraph(
        constraints=[
            anchor_window(
                TemporalTarget.DEPARTURE,
                "january",
                "Maybe sometime in January",
            )
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline)

    assert result.parsed_request.departure_window is not None
    assert result.parsed_request.destinations[1].value == "São Paulo"
    assert result.clarification.field == "return_or_duration"
    assert any(
        unknown.field == "destination_preference" for unknown in result.parsed_request.unknowns
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
    relations = TemporalRelationGraph(
        constraints=[
            anchor_window(TemporalTarget.DEPARTURE, "may", "May"),
            duration("a week", 1, 1, TemporalUnit.WEEK),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

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
    relations = TemporalRelationGraph(
        constraints=[
            anchor_window(TemporalTarget.DEPARTURE, "depart", "July 10"),
            anchor_window(TemporalTarget.RETURN, "return", "July 8"),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline)

    assert [conflict.code for conflict in result.parsed_request.conflicts] == [
        "return_before_departure"
    ]
    assert result.clarification.field == "dates"


def test_return_weekend_after_departure_is_evaluated_from_relation_graph() -> None:
    text = "Leave on Labor Day weekend and come back the weekend afterwards."
    extraction = CoarseIntentExtraction(
        date_anchors=[
            HolidayAnchor(
                kind="holiday",
                anchor_id="labor_day",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="Labor Day",
                holiday=Holiday.LABOR_DAY,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="Labor Day weekend",
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.RETURN,
                raw_text="the weekend afterwards",
            ),
        ],
    )
    relations = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id="labor_day",
                window="holiday_weekend",
                raw_text="Labor Day weekend",
            ),
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field",
                    field=TemporalTarget.DEPARTURE,
                    edge=TemporalEdge.END,
                ),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text="the weekend afterwards",
            ),
        ]
    )
    pipeline = FakePipeline(extraction, relations)

    result = understand_request(request(text), pipeline, pipeline, FakeHolidayProvider())

    assert result.parsed_request.departure_window is not None
    assert (
        result.parsed_request.departure_window.start,
        result.parsed_request.departure_window.end,
    ) == (date(2026, 9, 4), date(2026, 9, 7))
    assert result.parsed_request.return_window is not None
    assert (
        result.parsed_request.return_window.start,
        result.parsed_request.return_window.end,
    ) == (date(2026, 9, 12), date(2026, 9, 13))


def test_next_month_model_semantics_are_context_invariant_but_calendar_output_varies() -> None:
    text = "Travel next month."
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="next month",
            )
        ]
    )
    relations = TemporalRelationGraph(
        constraints=[
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context",
                    key="context:request_date",
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next month",
            )
        ]
    )
    august_pipeline = FakePipeline(extraction, relations)
    november_pipeline = FakePipeline(extraction, relations)

    august_result = understand_request(
        RawRequest(
            text=text,
            context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
        ),
        august_pipeline,
        august_pipeline,
    )
    november_result = understand_request(
        RawRequest(
            text=text,
            context=RequestContext(reference_date=date(2026, 11, 15), timezone="Asia/Tokyo"),
        ),
        november_pipeline,
        november_pipeline,
    )

    assert august_pipeline.coarse_input == november_pipeline.coarse_input
    assert august_pipeline.temporal_input == november_pipeline.temporal_input
    assert august_pipeline.temporal_input is not None
    payload = august_pipeline.temporal_input.model_dump_json()
    assert "2026-08-30" not in payload
    assert "UTC" not in payload
    assert august_result.parsed_request.departure_window is not None
    assert november_result.parsed_request.departure_window is not None
    assert (
        august_result.parsed_request.departure_window.start,
        august_result.parsed_request.departure_window.end,
    ) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (
        november_result.parsed_request.departure_window.start,
        november_result.parsed_request.departure_window.end,
    ) == (date(2026, 12, 1), date(2026, 12, 31))
