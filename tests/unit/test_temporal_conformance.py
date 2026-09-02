from datetime import date

import pytest

from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    CalendarPeriodSemantics,
    CoarseIntentExtraction,
    MonthAnchor,
    MonthPortionConstraint,
    RawRequest,
    RelativeCalendarPeriodConstraint,
    RelativeWeekendConstraint,
    RequestContext,
    SymbolicContextReference,
    TemporalDirection,
    TemporalEdge,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    TemporalUnit,
    UnresolvedRelationConstraint,
)
from award_agent.intent.conformance import validate_temporal_conformance
from award_agent.intent.evidence import TemporalResolutionValidationError
from award_agent.intent.model_views import (
    ExplicitAnchorCatalogEntry,
    SymbolicReferenceCatalogEntry,
    TemporalEvidenceCatalogEntry,
    TemporalInterpretationInput,
)
from award_agent.intent.openai_extractor import (
    RelativeWeekendWire,
    TemporalRelationGraphWire,
    UnresolvedWire,
)
from award_agent.intent.temporal import sanitize_temporal_extraction


def request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="UTC"),
    )


def interpretation_input(
    text: str,
    quote: str,
    claim: TemporalEvidenceClaim,
) -> TemporalInterpretationInput:
    start = text.index(quote)
    end = start + len(quote)
    return TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{start}:{end}",
                text=quote,
                claim_labels=[claim],
                source_order=0,
                source_start=start,
                source_end=end,
            )
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry(key="request_field:departure:end")
        ],
    )


def test_explicit_named_month_anchor_is_accepted() -> None:
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="model-id",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="September",
                month=9,
            )
        ]
    )

    result = sanitize_temporal_extraction(request("Travel in September."), extraction)

    anchor = result.date_anchors[0]
    assert isinstance(anchor, MonthAnchor)
    assert anchor.month == 9


def test_deictic_next_month_cannot_support_explicit_september_anchor() -> None:
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="model-id",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="next month",
                month=9,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="next month",
                claim_ids=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
            )
        ],
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        sanitize_temporal_extraction(request("Travel next month."), extraction)

    assert captured.value.details.stage == "pass_one_anchor_validation"
    assert captured.value.details.error_code == "anchor_kind_evidence_mismatch"
    assert captured.value.details.contradictory_fields == ("kind", "month", "raw_text")


def test_relation_evidence_claim_must_match_relation_target() -> None:
    model_input = interpretation_input(
        "Return the weekend afterwards.",
        "the weekend afterwards",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    )
    wire = TemporalRelationGraphWire(
        relative_weekends=[
            RelativeWeekendWire(
                target=TemporalTarget.RETURN,
                reference_key="request_field:departure:end",
                direction=TemporalDirection.AFTER,
                ordinal=1,
                evidence_id=model_input.evidence_catalog[0].evidence_id,
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        wire.to_domain(model_input)

    details = captured.value.as_dict()
    assert details["stage"] == "pass_two_conformance"
    assert details["error_code"] == "incompatible_evidence_claim"
    assert details["collection"] == "relative_weekends"
    assert details["relation_index"] == 0
    assert details["constraint_index"] == 0
    assert details["selected_relation_kind"] == "relative_weekend"
    assert details["contradictory_fields"] == ("evidence_id", "target")
    assert details["evidence_id"] == model_input.evidence_catalog[0].evidence_id


def test_every_first_pass_claim_must_be_consumed_or_unresolved() -> None:
    model_input = interpretation_input(
        "Travel next month.",
        "next month",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        TemporalRelationGraphWire().to_domain(model_input)

    assert captured.value.details.error_code == "unconsumed_temporal_claim"
    assert captured.value.details.evidence_id == model_input.evidence_catalog[0].evidence_id

    graph = TemporalRelationGraphWire(
        unresolved=[
            UnresolvedWire(
                target="departure",
                evidence_id=model_input.evidence_catalog[0].evidence_id,
                reason="Preserved unresolved for this coverage test.",
            )
        ]
    ).to_domain(model_input)
    assert graph.constraints[0].kind == "unresolved"


def test_structured_error_serialization_has_stable_empty_fields() -> None:
    error = TemporalResolutionValidationError(
        "bad relation",
        stage="pass_two_wire_conversion",
        error_code="wire_relation_conversion_failed",
    )

    assert error.as_dict() == {
        "stage": "pass_two_wire_conversion",
        "error_code": "wire_relation_conversion_failed",
        "relation_index": None,
        "constraint_index": None,
        "selected_relation_kind": None,
        "collection": None,
        "missing_fields": (),
        "contradictory_fields": (),
        "evidence_id": None,
        "reference_id": None,
        "validation_cause": "bad relation",
    }


def test_next_spring_cannot_be_coerced_to_bounded_calendar_month() -> None:
    model_input = interpretation_input(
        "Travel next spring.",
        "next spring",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    ).model_copy(
        update={
            "allowed_symbolic_references": [
                SymbolicReferenceCatalogEntry(key="context:request_date")
            ]
        }
    )
    graph = TemporalRelationGraph(
        constraints=[
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context", key="context:request_date"
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next spring",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"


def test_first_week_of_named_month_cannot_be_coerced_to_whole_month() -> None:
    text = "Travel the first week of June."
    phrase = "first week of June"
    start = text.index(phrase)
    end = start + len(phrase)
    anchor_start = text.index("June")
    anchor_id = f"anchor:month:departure:{anchor_start}:{anchor_start + 4}"
    model_input = TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{start}:{end}",
                text=phrase,
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=start,
                source_end=end,
            ),
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{anchor_start}:{anchor_start + 4}",
                text="June",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                source_order=1,
                source_start=anchor_start,
                source_end=anchor_start + 4,
            ),
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id=anchor_id,
                kind="month",
                applies_to=TemporalTarget.DEPARTURE,
            )
        ],
    )
    graph = TemporalRelationGraph(
        constraints=[
            MonthPortionConstraint(
                kind="month_portion",
                target=TemporalTarget.DEPARTURE,
                anchor_id=anchor_id,
                portion="whole",
                raw_text=phrase,
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"


def test_literal_named_month_remains_a_supported_bounded_relation() -> None:
    text = "Travel in June."
    start = text.index("June")
    anchor_id = f"anchor:month:departure:{start}:{start + 4}"
    model_input = TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{start}:{start + 4}",
                text="June",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                source_order=0,
                source_start=start,
                source_end=start + 4,
            )
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id=anchor_id,
                kind="month",
                applies_to=TemporalTarget.DEPARTURE,
            )
        ],
    )
    graph = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id=anchor_id,
                window="anchor",
                raw_text="June",
            )
        ]
    )

    validate_temporal_conformance(model_input, graph)


@pytest.mark.parametrize("model_year", [1, 20, 26])
def test_short_model_year_does_not_survive_source_2026(model_year: int) -> None:
    anchor = MonthAnchor.model_construct(
        kind="month",
        anchor_id="model-id",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="June 2026",
        month=6,
        year=model_year,
        occurrence_index=None,
    )
    extraction = CoarseIntentExtraction(date_anchors=[anchor])

    sanitized = sanitize_temporal_extraction(request("Travel in June 2026."), extraction)

    assert sanitized.date_anchors[0].year is None


@pytest.mark.parametrize("model_year", [1, 20, 26, 10000])
def test_anchor_contract_rejects_unsupported_year_width(model_year: int) -> None:
    with pytest.raises(ValueError):
        MonthAnchor(
            kind="month",
            anchor_id="model-id",
            applies_to=TemporalTarget.DEPARTURE,
            raw_text="June 2026",
            month=6,
            year=model_year,
        )


def test_explicit_four_digit_year_is_preserved_and_partial_token_is_not() -> None:
    explicit = MonthAnchor(
        kind="month",
        anchor_id="model-id",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="June 2026",
        month=6,
        year=2026,
    )
    partial = explicit.model_copy(update={"raw_text": "June 20260"})

    preserved = sanitize_temporal_extraction(
        request("Travel in June 2026."), CoarseIntentExtraction(date_anchors=[explicit])
    )
    stripped = sanitize_temporal_extraction(
        request("Travel in June 20260."), CoarseIntentExtraction(date_anchors=[partial])
    )

    assert preserved.date_anchors[0].year == 2026
    assert stripped.date_anchors[0].year is None


def test_partial_next_evidence_cannot_hide_unresolved_spring_token() -> None:
    model_input = interpretation_input(
        "Travel next spring.",
        "next",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    ).model_copy(
        update={
            "allowed_symbolic_references": [
                SymbolicReferenceCatalogEntry(key="context:request_date")
            ]
        }
    )
    graph = TemporalRelationGraph(
        constraints=[
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context", key="context:request_date"
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"
    assert "not covered by unresolved" in captured.value.details.validation_cause


def test_first_week_of_month_cannot_be_coerced_to_relative_weekend() -> None:
    text = "Travel the first week of June."
    phrase_start = text.index("first week of June")
    phrase_end = phrase_start + len("first week of June")
    month_start = text.index("June")
    anchor_id = f"anchor:month:departure:{month_start}:{month_start + 4}"
    reference_key = f"anchor_ref:{anchor_id}:start"
    model_input = TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{phrase_start}:{phrase_end}",
                text="first week of June",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=phrase_start,
                source_end=phrase_end,
            ),
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{month_start}:{month_start + 4}",
                text="June",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                source_order=1,
                source_start=month_start,
                source_end=month_start + 4,
            ),
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id=anchor_id,
                kind="month",
                applies_to=TemporalTarget.DEPARTURE,
            )
        ],
        allowed_symbolic_references=[SymbolicReferenceCatalogEntry(key=reference_key)],
    )
    graph = TemporalRelationGraph(
        constraints=[
            RelativeWeekendConstraint(
                kind="relative_weekend",
                target=TemporalTarget.DEPARTURE,
                reference=AnchorReference(
                    kind="anchor",
                    anchor_id=anchor_id,
                    edge=TemporalEdge.START,
                ),
                direction=TemporalDirection.AFTER,
                ordinal=1,
                raw_text="first week of June",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"
    assert captured.value.details.selected_relation_kind == "relative_weekend"


def test_unresolved_season_can_coexist_with_unrelated_bounded_month() -> None:
    text = "Travel next spring or in June."
    season_start = text.index("next spring")
    month_start = text.index("June")
    anchor_id = f"anchor:month:departure:{month_start}:{month_start + 4}"
    model_input = TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{season_start}:{season_start + 11}",
                text="next spring",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=season_start,
                source_end=season_start + 11,
            ),
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{month_start}:{month_start + 4}",
                text="June",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                source_order=1,
                source_start=month_start,
                source_end=month_start + 4,
            ),
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id=anchor_id,
                kind="month",
                applies_to=TemporalTarget.DEPARTURE,
            )
        ],
    )
    graph = TemporalRelationGraph(
        constraints=[
            UnresolvedRelationConstraint(
                kind="unresolved",
                target=TemporalTarget.DEPARTURE,
                raw_text="next spring",
                reason="No approved deterministic season policy.",
            ),
            AnchorWindowConstraint(
                kind="anchor_window",
                target=TemporalTarget.DEPARTURE,
                anchor_id=anchor_id,
                window="anchor",
                raw_text="June",
            ),
        ]
    )

    validate_temporal_conformance(model_input, graph)


def test_unresolved_season_does_not_authorize_bounded_use_of_same_evidence() -> None:
    model_input = interpretation_input(
        "Travel next spring.",
        "next spring",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    ).model_copy(
        update={
            "allowed_symbolic_references": [
                SymbolicReferenceCatalogEntry(key="context:request_date")
            ]
        }
    )
    graph = TemporalRelationGraph(
        constraints=[
            UnresolvedRelationConstraint(
                kind="unresolved",
                target=TemporalTarget.DEPARTURE,
                raw_text="next spring",
                reason="No approved deterministic season policy.",
            ),
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context", key="context:request_date"
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next spring",
            ),
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"
    assert captured.value.details.constraint_index == 1
    assert captured.value.details.evidence_id == model_input.evidence_catalog[0].evidence_id


def test_unresolved_season_does_not_authorize_overlapping_bounded_evidence() -> None:
    text = "Travel next spring."
    phrase_start = text.index("next spring")
    next_end = phrase_start + len("next")
    season_end = phrase_start + len("next spring")
    model_input = TemporalInterpretationInput(
        temporal_transcript=text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{phrase_start}:{season_end}",
                text="next spring",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=0,
                source_start=phrase_start,
                source_end=season_end,
            ),
            TemporalEvidenceCatalogEntry(
                evidence_id=f"request:{phrase_start}:{next_end}",
                text="next",
                claim_labels=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                source_order=1,
                source_start=phrase_start,
                source_end=next_end,
            ),
        ],
        allowed_symbolic_references=[SymbolicReferenceCatalogEntry(key="context:request_date")],
    )
    graph = TemporalRelationGraph(
        constraints=[
            UnresolvedRelationConstraint(
                kind="unresolved",
                target=TemporalTarget.DEPARTURE,
                raw_text="next spring",
                reason="No approved deterministic season policy.",
            ),
            RelativeCalendarPeriodConstraint(
                kind="relative_calendar_period",
                target=TemporalTarget.DEPARTURE,
                reference=SymbolicContextReference(
                    kind="symbolic_context", key="context:request_date"
                ),
                direction=TemporalDirection.AFTER,
                unit=TemporalUnit.MONTH,
                ordinal=1,
                period_semantics=CalendarPeriodSemantics.WHOLE,
                raw_text="next",
            ),
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        validate_temporal_conformance(model_input, graph)

    assert captured.value.details.error_code == "unsupported_bounded_temporal_language"
    assert captured.value.details.constraint_index == 1
    assert captured.value.details.evidence_id == f"request:{phrase_start}:{next_end}"
