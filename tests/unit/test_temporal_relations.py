from datetime import date

import pytest

from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    DateWindow,
    DateWindowPrecision,
    DurationModifier,
    ExactDateAnchor,
    Holiday,
    HolidayAnchor,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeOffsetConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestContext,
    RequestFieldReference,
    ResolvedTemporalAnchor,
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
    UnresolvedRelationConstraint,
    Weekday,
)
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.evidence import TemporalEvidenceValidationError
from award_agent.intent.temporal import (
    TemporalResolutionValidationError,
    evaluate_temporal_relation_graph,
)


def request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
    )


def request_on(text: str, reference_date: date) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=reference_date, timezone="UTC"),
    )


def holiday_anchor(anchor_id: str, raw_text: str, holiday: Holiday) -> HolidayAnchor:
    return HolidayAnchor(
        kind="holiday",
        anchor_id=anchor_id,
        applies_to=TemporalTarget.DEPARTURE,
        raw_text=raw_text,
        holiday=holiday,
    )


def exact_anchor(
    anchor_id: str,
    raw_text: str,
    month: int,
    day: int,
    target: TemporalTarget = TemporalTarget.DEPARTURE,
) -> ExactDateAnchor:
    return ExactDateAnchor(
        kind="exact_date",
        anchor_id=anchor_id,
        applies_to=target,
        raw_text=raw_text,
        month=month,
        day=day,
        year=2026,
    )


def resolved(anchor: ExactDateAnchor | HolidayAnchor, value: date) -> ResolvedTemporalAnchor:
    return ResolvedTemporalAnchor(
        anchor=anchor,
        start=value,
        end=value,
        source="calendar" if isinstance(anchor, ExactDateAnchor) else "holiday_provider",
        source_detail="offline fixture",
    )


def extraction(
    *anchors: ExactDateAnchor | HolidayAnchor, phrases: list[str]
) -> CoarseIntentExtraction:
    return CoarseIntentExtraction(
        date_anchors=list(anchors),
        temporal_phrases=[
            TemporalPhrase(applies_to=TemporalPhraseTarget.UNSPECIFIED, raw_text=phrase)
            for phrase in phrases
        ],
    )


def anchor_window(anchor_id: str, raw_text: str) -> AnchorWindowConstraint:
    return AnchorWindowConstraint(
        kind="anchor_window",
        target=TemporalTarget.DEPARTURE,
        anchor_id=anchor_id,
        window="anchor",
        raw_text=raw_text,
    )


def duration(
    raw_text: str,
    minimum: int,
    maximum: int,
    unit: TemporalUnit,
    modifier: DurationModifier,
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


@pytest.mark.parametrize(
    ("ordinal", "expected"),
    [
        (1, (date(2026, 11, 28), date(2026, 11, 29))),
        (2, (date(2026, 12, 5), date(2026, 12, 6))),
    ],
)
def test_first_and_second_weekends_after_holiday(
    ordinal: int,
    expected: tuple[date, date],
) -> None:
    text = f"Leave {ordinal} weekends after Thanksgiving"
    anchor = holiday_anchor("thanksgiving", "Thanksgiving", Holiday.THANKSGIVING)
    relation_text = f"{ordinal} weekends after Thanksgiving"
    coarse = extraction(anchor, phrases=[relation_text])
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="thanksgiving"),
                direction=TemporalDirection.AFTER,
                ordinal=ordinal,
                raw_text=relation_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text), coarse, graph, [resolved(anchor, date(2026, 11, 26))]
    )

    assert result.departure is not None
    assert (result.departure.start, result.departure.end) == expected


def test_relative_departure_weekend_after_holiday_anchor() -> None:
    text = "Leave the weekend after Labor Day."
    anchor = holiday_anchor("labor_day", "Labor Day", Holiday.LABOR_DAY)
    raw_text = "the weekend after Labor Day"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="labor_day"),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text=raw_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=[raw_text]),
        graph,
        [resolved(anchor, date(2026, 9, 7))],
    )

    assert result.departure is not None
    assert (result.departure.start, result.departure.end) == (
        date(2026, 9, 12),
        date(2026, 9, 13),
    )


def test_return_weekend_after_resolved_departure() -> None:
    text = "Leave Labor Day weekend and return the weekend afterwards."
    anchor = holiday_anchor("labor_day", "Labor Day", Holiday.LABOR_DAY)
    graph = TemporalRelationGraph(
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
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text="the weekend afterwards",
            ),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["Labor Day weekend", "the weekend afterwards"]),
        graph,
        [resolved(anchor, date(2026, 9, 7))],
    )

    assert result.departure is not None
    assert (result.departure.start, result.departure.end) == (
        date(2026, 9, 4),
        date(2026, 9, 7),
    )
    assert result.return_date is not None
    assert (result.return_date.start, result.return_date.end) == (
        date(2026, 9, 12),
        date(2026, 9, 13),
    )


def test_relative_weekday_after_anchor() -> None:
    text = "Leave the Thursday after Thanksgiving."
    anchor = holiday_anchor("thanksgiving", "Thanksgiving", Holiday.THANKSGIVING)
    raw_text = "the Thursday after Thanksgiving"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="thanksgiving"),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                raw_text=raw_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=[raw_text]),
        graph,
        [resolved(anchor, date(2026, 11, 26))],
    )

    assert result.departure is not None
    assert result.departure.start == result.departure.end == date(2026, 12, 3)


def test_relative_weekday_after_departure_window() -> None:
    text = "Leave August 29 and return the following Thursday."
    anchor = exact_anchor("departure", "August 29", 8, 29)
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", "August 29"),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                raw_text="the following Thursday",
            ),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["the following Thursday"]),
        graph,
        [resolved(anchor, date(2026, 8, 29))],
    )

    assert result.return_date is not None
    assert result.return_date.start == result.return_date.end == date(2026, 9, 3)


def test_before_direction_weekend_and_weekday() -> None:
    text = "Leave the weekend before Labor Day or the Thursday before that."
    anchor = holiday_anchor("labor_day", "Labor Day", Holiday.LABOR_DAY)
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(
                    kind="anchor", anchor_id="labor_day", edge=TemporalEdge.START
                ),
                direction=TemporalDirection.BEFORE,
                ordinal=1,
                raw_text="the weekend before Labor Day",
            ),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(
                    kind="anchor", anchor_id="labor_day", edge=TemporalEdge.START
                ),
                direction=TemporalDirection.BEFORE,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                raw_text="the Thursday before that",
            ),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(
            anchor,
            phrases=["the weekend before Labor Day", "the Thursday before that"],
        ),
        graph,
        [resolved(anchor, date(2026, 9, 7))],
    )

    assert result.departure is not None
    assert (result.departure.start, result.departure.end) == (
        date(2026, 9, 3),
        date(2026, 9, 6),
    )


def test_weekend_after_departure_ending_saturday_selects_following_weekend() -> None:
    text = "Leave August 29 and return the weekend after."
    anchor = exact_anchor("departure", "August 29", 8, 29)
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", "August 29"),
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text="the weekend after",
            ),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["the weekend after"]),
        graph,
        [resolved(anchor, date(2026, 8, 29))],
    )

    assert result.return_date is not None
    assert (result.return_date.start, result.return_date.end) == (
        date(2026, 9, 5),
        date(2026, 9, 6),
    )


def test_missing_anchor_reference_fails_explicitly() -> None:
    text = "Leave the weekend after the holiday."
    raw_text = "the weekend after the holiday"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="missing"),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text=raw_text,
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError, match="missing anchor"):
        evaluate_temporal_relation_graph(request(text), extraction(phrases=[raw_text]), graph, [])


def test_missing_request_field_dependency_fails_explicitly() -> None:
    text = "Return the following Thursday."
    raw_text = "the following Thursday"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field",
                    field=TemporalTarget.DEPARTURE,
                    edge=TemporalEdge.END,
                ),
                direction=TemporalDirection.AFTER,
                weekday=Weekday.THURSDAY,
                raw_text=raw_text,
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError, match="unresolved request field"):
        evaluate_temporal_relation_graph(request(text), extraction(phrases=[raw_text]), graph, [])


def test_relative_day_offset_before_anchor() -> None:
    text = "Leave two days before Thanksgiving."
    anchor = holiday_anchor("thanksgiving", "Thanksgiving", Holiday.THANKSGIVING)
    raw_text = "two days before Thanksgiving"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeOffsetConstraint(
                kind="relative_offset",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="thanksgiving"),
                direction=TemporalDirection.BEFORE,
                amount=2,
                unit=TemporalUnit.DAY,
                raw_text=raw_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=[raw_text]),
        graph,
        [resolved(anchor, date(2026, 11, 26))],
    )

    assert result.departure is not None
    assert result.departure.start == result.departure.end == date(2026, 11, 24)


@pytest.mark.parametrize(
    ("reference_date", "expected"),
    [
        (date(2026, 8, 30), (date(2026, 9, 1), date(2026, 9, 30))),
        (date(2026, 11, 15), (date(2026, 12, 1), date(2026, 12, 31))),
        (date(2026, 12, 31), (date(2027, 1, 1), date(2027, 1, 31))),
    ],
)
def test_next_month_resolves_as_next_whole_calendar_month(
    reference_date: date,
    expected: tuple[date, date],
) -> None:
    text = "Travel next month."
    raw_text = "next month"
    graph = TemporalRelationGraph(
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
                raw_text=raw_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request_on(text, reference_date),
        extraction(phrases=[raw_text]),
        graph,
        [],
    )

    assert result.departure is not None
    assert (result.departure.start, result.departure.end) == expected


def test_relative_month_point_offset_is_not_a_calendar_period() -> None:
    text = "Leave August 30 and travel one month after this date."
    anchor = exact_anchor("departure", "August 30", 8, 30)
    raw_text = "one month after this date"
    graph = TemporalRelationGraph(
        constraints=[
            RelativeOffsetConstraint(
                kind="relative_offset",
                target=TemporalTarget.RETURN,
                reference=AnchorReference(kind="anchor", anchor_id="departure"),
                direction=TemporalDirection.AFTER,
                amount=1,
                unit=TemporalUnit.MONTH,
                raw_text=raw_text,
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=[raw_text]),
        graph,
        [resolved(anchor, date(2026, 8, 30))],
    )

    assert result.return_date is not None
    assert result.return_date.start == result.return_date.end == date(2026, 9, 30)


def test_next_spring_remains_explicitly_unresolved() -> None:
    text = "Travel next spring."
    graph = TemporalRelationGraph(
        constraints=[
            UnresolvedRelationConstraint(
                kind="unresolved",
                target=TemporalTarget.DEPARTURE,
                raw_text="next spring",
                reason="No deterministic season policy is approved.",
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text), extraction(phrases=["next spring"]), graph, []
    )

    assert result.departure is None
    assert result.unresolved[0].raw_text == "next spring"
    assert "season policy" in result.unresolved[0].reason


def test_cyclic_request_field_dependencies_fail_explicitly() -> None:
    text = "Leave the Thursday after the return and return the Friday after departure."
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.DEPARTURE,
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.RETURN, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                weekday=Weekday.THURSDAY,
                raw_text="the Thursday after the return",
            ),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                weekday=Weekday.FRIDAY,
                raw_text="the Friday after departure",
            ),
        ]
    )

    with pytest.raises(TemporalResolutionValidationError, match="cyclic"):
        evaluate_temporal_relation_graph(
            request(text),
            extraction(phrases=["the Thursday after the return", "the Friday after departure"]),
            graph,
            [],
        )


def test_ungrounded_relation_raw_text_fails_strictly() -> None:
    text = "Leave after Labor Day."
    anchor = holiday_anchor("labor_day", "Labor Day", Holiday.LABOR_DAY)
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="labor_day"),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text="invented weekend wording",
            )
        ]
    )

    with pytest.raises(TemporalEvidenceValidationError):
        evaluate_temporal_relation_graph(
            request(text),
            extraction(anchor, phrases=["after Labor Day"]),
            graph,
            [resolved(anchor, date(2026, 9, 7))],
        )


def test_after_new_year_remains_unbounded() -> None:
    text = "Travel after New Year."
    anchor = holiday_anchor("new_year", "New Year", Holiday.NEW_YEARS_DAY)
    graph = TemporalRelationGraph(
        constraints=[
            UnboundedBoundaryConstraint(
                kind="unbounded_boundary",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(kind="anchor", anchor_id="new_year"),
                direction=TemporalDirection.AFTER,
                raw_text="after New Year",
            )
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["after New Year"]),
        graph,
        [resolved(anchor, date(2027, 1, 1))],
    )

    assert result.departure is None
    assert result.unresolved[0].field == "departure"


def test_explicit_return_relation_remains_authoritative_and_duration_conflicts() -> None:
    text = "Leave August 29, return the following Thursday, for 10 days."
    anchor = exact_anchor("departure", "August 29", 8, 29)
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", "August 29"),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                target=TemporalTarget.RETURN,
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                direction=TemporalDirection.AFTER,
                weekday=Weekday.THURSDAY,
                raw_text="the following Thursday",
            ),
            SemanticDurationConstraint(
                kind="duration",
                reference=RequestFieldReference(
                    kind="request_field", field=TemporalTarget.DEPARTURE, edge=TemporalEdge.END
                ),
                stated_minimum_quantity=10,
                stated_maximum_quantity=10,
                unit=TemporalUnit.DAY,
                modifier=DurationModifier.EXACT,
                raw_text="10 days",
            ),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["the following Thursday", "10 days"]),
        graph,
        [resolved(anchor, date(2026, 8, 29))],
    )

    assert result.return_date is not None
    assert result.return_date.start == date(2026, 9, 3)
    assert result.interpreted_duration is not None
    conflicts = detect_conflicts(
        DateWindow(
            start=date(2026, 8, 29),
            end=date(2026, 8, 29),
            precision=DateWindowPrecision.EXACT,
            raw_text="August 29",
        ),
        DateWindow(
            start=date(2026, 9, 3),
            end=date(2026, 9, 3),
            precision=DateWindowPrecision.EXACT,
            raw_text="the following Thursday",
        ),
        result.interpreted_duration,
    )
    assert [conflict.code for conflict in conflicts] == ["duration_date_mismatch"]


@pytest.mark.parametrize(
    (
        "raw_text",
        "minimum",
        "maximum",
        "unit",
        "modifier",
        "expected_days",
        "expected_return",
    ),
    [
        (
            "2 weeks",
            2,
            2,
            TemporalUnit.WEEK,
            DurationModifier.EXACT,
            (14, 14),
            (date(2026, 9, 12), date(2026, 9, 12)),
        ),
        (
            "about 10 days",
            10,
            10,
            TemporalUnit.DAY,
            DurationModifier.APPROXIMATE,
            (9, 11),
            (date(2026, 9, 7), date(2026, 9, 9)),
        ),
        (
            "1 or 2 weeks",
            1,
            2,
            TemporalUnit.WEEK,
            DurationModifier.ALTERNATIVE,
            (7, 14),
            (date(2026, 9, 5), date(2026, 9, 12)),
        ),
        (
            "about a week",
            1,
            1,
            TemporalUnit.WEEK,
            DurationModifier.APPROXIMATE,
            (6, 8),
            (date(2026, 9, 4), date(2026, 9, 6)),
        ),
    ],
)
def test_literal_duration_semantics_are_normalized_deterministically(
    raw_text: str,
    minimum: int,
    maximum: int,
    unit: TemporalUnit,
    modifier: DurationModifier,
    expected_days: tuple[int, int],
    expected_return: tuple[date, date],
) -> None:
    text = f"Leave August 29 for {raw_text}."
    anchor = exact_anchor("departure", "August 29", 8, 29)
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", "August 29"),
            duration(raw_text, minimum, maximum, unit, modifier),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=[raw_text]),
        graph,
        [resolved(anchor, date(2026, 8, 29))],
    )

    assert result.interpreted_duration is not None
    assert (
        result.interpreted_duration.minimum_days,
        result.interpreted_duration.maximum_days,
    ) == expected_days
    assert result.return_date is not None
    assert (result.return_date.start, result.return_date.end) == expected_return


@pytest.mark.parametrize(
    ("departure", "expected_return", "expected_days"),
    [
        (date(2026, 1, 31), date(2026, 2, 28), 28),
        (date(2026, 12, 31), date(2027, 1, 31), 31),
    ],
)
def test_exact_month_duration_uses_calendar_addition_across_boundaries(
    departure: date,
    expected_return: date,
    expected_days: int,
) -> None:
    raw_anchor = departure.strftime("%B %d")
    text = f"Leave {raw_anchor} for 1 month."
    anchor = exact_anchor("departure", raw_anchor, departure.month, departure.day)
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", raw_anchor),
            duration("1 month", 1, 1, TemporalUnit.MONTH, DurationModifier.EXACT),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["1 month"]),
        graph,
        [resolved(anchor, departure)],
    )

    assert result.return_date is not None
    assert (result.return_date.start, result.return_date.end) == (
        expected_return,
        expected_return,
    )
    assert result.interpreted_duration is not None
    assert (
        result.interpreted_duration.minimum_days,
        result.interpreted_duration.maximum_days,
    ) == (expected_days, expected_days)


def test_month_duration_over_flexible_departure_uses_calendar_endpoints_and_valid_day_bounds() -> (
    None
):
    text = "Leave January for 1 month."
    anchor = exact_anchor("departure", "January", 1, 1)
    resolved_departure = ResolvedTemporalAnchor(
        anchor=anchor,
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
        source="calendar",
        source_detail="offline flexible fixture",
    )
    graph = TemporalRelationGraph(
        constraints=[
            anchor_window("departure", "January"),
            duration("1 month", 1, 1, TemporalUnit.MONTH, DurationModifier.EXACT),
        ]
    )

    result = evaluate_temporal_relation_graph(
        request(text),
        extraction(anchor, phrases=["1 month"]),
        graph,
        [resolved_departure],
    )

    assert result.return_date is not None
    assert (result.return_date.start, result.return_date.end) == (
        date(2026, 2, 1),
        date(2026, 2, 28),
    )
    assert result.interpreted_duration is not None
    assert (
        result.interpreted_duration.minimum_days,
        result.interpreted_duration.maximum_days,
    ) == (28, 31)


@pytest.mark.parametrize(
    ("minimum", "maximum", "modifier", "message"),
    [
        (1, 2, DurationModifier.EXACT, "require one stated quantity"),
        (1, 2, DurationModifier.APPROXIMATE, "require one stated quantity"),
        (1, 1, DurationModifier.ALTERNATIVE, "requires distinct stated quantities"),
    ],
)
def test_duration_domain_rejects_modifier_quantity_mismatches(
    minimum: int,
    maximum: int,
    modifier: DurationModifier,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        duration("duration", minimum, maximum, TemporalUnit.DAY, modifier)
