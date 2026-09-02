from datetime import date

import pytest

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    Holiday,
    HolidayAnchor,
    InterpretedDuration,
    MonthAnchor,
    ProposedDateWindow,
    RawRequest,
    RequestContext,
    ResolvedTemporalAnchor,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalTarget,
    UnresolvedTemporalConstraint,
)
from award_agent.intent.evidence import EvidenceErrorCode, TemporalEvidenceValidationError
from award_agent.intent.temporal import (
    TemporalResolutionValidationError,
    enrich_temporal_anchors,
    sanitize_temporal_extraction,
    validate_date_resolution_proposal,
)


def request(text: str = "Travel in May") -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
    )


def resolved_holiday(anchor: HolidayAnchor, anchor_date: date) -> ResolvedTemporalAnchor:
    return ResolvedTemporalAnchor(
        anchor=anchor,
        start=anchor_date,
        end=anchor_date,
        source="holiday_provider",
        source_detail="test fixture",
    )


def test_enrichment_rejects_anchor_evidence_not_found_in_request() -> None:
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="invented",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="June",
                month=6,
            )
        ]
    )

    with pytest.raises(TemporalEvidenceValidationError) as captured:
        enrich_temporal_anchors(request(), extraction)

    assert captured.value.code is EvidenceErrorCode.UNGROUNDED_QUOTE
    assert captured.value.quote == "June"
    assert captured.value.claim_id == "departure_anchor"


def test_enrichment_preserves_verbatim_relative_phrase() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="two weekends after",
            )
        ]
    )

    assert (
        enrich_temporal_anchors(request("Travel two weekends after the holiday"), extraction) == []
    )


def test_sanitization_discards_a_year_not_explicit_in_anchor_evidence() -> None:
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="may",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="May",
                month=5,
                year=2027,
            )
        ]
    )

    sanitized = sanitize_temporal_extraction(request(), extraction)

    assert sanitized.date_anchors[0].year is None


def test_sanitization_rejects_fabricated_month_anchor_evidence() -> None:
    text = "Come back the weekend afterwards"
    extraction = CoarseIntentExtraction(
        date_anchors=[
            MonthAnchor(
                kind="month",
                anchor_id="fabricated_september",
                applies_to=TemporalTarget.RETURN,
                raw_text="the weekend afterwards",
                month=9,
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError, match="does not name month"):
        sanitize_temporal_extraction(request(text), extraction)


def test_proposal_rejects_supporting_text_not_found_in_request() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="in May",
            )
        ]
    )
    proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2027, 5, 1),
            end=date(2027, 5, 31),
            supporting_text=["sometime in June"],
            interpretation="Invented month",
        )
    )

    with pytest.raises(TemporalEvidenceValidationError) as captured:
        validate_date_resolution_proposal(request(), extraction, proposal)

    assert captured.value.code is EvidenceErrorCode.UNGROUNDED_QUOTE
    assert captured.value.claim_id == "departure_period"
    assert captured.value.quote == "sometime in June"


def test_proposal_rejects_dates_when_request_has_no_temporal_evidence() -> None:
    proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2027, 5, 1),
            end=date(2027, 5, 31),
            supporting_text=["Travel"],
            interpretation="Invented timing",
        )
    )

    with pytest.raises(TemporalResolutionValidationError, match="without temporal evidence"):
        validate_date_resolution_proposal(
            request("Travel to Paris"),
            CoarseIntentExtraction(),
            proposal,
        )


def test_proposal_rejects_unresolved_annotations_without_request_evidence() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="in May",
            )
        ]
    )
    proposal = DateResolutionProposal(
        unresolved=[
            UnresolvedTemporalConstraint(
                field="departure",
                raw_text="invented phrase",
                reason="Not grounded",
            )
        ]
    )

    with pytest.raises(TemporalEvidenceValidationError) as captured:
        validate_date_resolution_proposal(request(), extraction, proposal)

    assert captured.value.code is EvidenceErrorCode.UNGROUNDED_QUOTE
    assert captured.value.claim_id == "departure_period"
    assert captured.value.quote == "invented phrase"


def test_duration_interpretation_has_deterministic_return_arithmetic() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="for 2 weeks",
            )
        ]
    )
    proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
            supporting_text=["October"],
            interpretation="Any departure in October",
        ),
        return_date=ProposedDateWindow(
            start=date(2026, 10, 15),
            end=date(2026, 10, 31),
            supporting_text=["for 2 weeks"],
            interpretation="Model proposal with incorrect upper bound",
        ),
        interpreted_duration=InterpretedDuration(
            raw_text="for 2 weeks",
            minimum_days=14,
            maximum_days=14,
        ),
    )

    validated = validate_date_resolution_proposal(
        request("Travel in October for 2 weeks"), extraction, proposal
    )

    assert validated.return_date is not None
    assert validated.return_date.start == date(2026, 10, 15)
    assert validated.return_date.end == date(2026, 11, 14)


def test_unbounded_holiday_relation_overrides_an_invented_departure_window() -> None:
    text = "Travel for 1 or 2 weeks after new year"
    extraction = CoarseIntentExtraction(
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
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="for 1 or 2 weeks",
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="after new year",
            ),
        ],
    )
    proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2027, 1, 2),
            end=date(2027, 1, 15),
            supporting_text=["after new year"],
            interpretation="Arbitrary bounded period",
        )
    )

    validated = validate_date_resolution_proposal(request(text), extraction, proposal)

    assert validated.departure is None
    assert validated.return_date is None
    assert validated.unresolved[0].field == "departure"


def test_bounded_weekend_after_holiday_is_not_forced_to_clarification() -> None:
    text = "Travel the weekend after new year"
    extraction = CoarseIntentExtraction(
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
                raw_text="the weekend after new year",
            )
        ],
    )
    departure = ProposedDateWindow(
        start=date(2027, 1, 2),
        end=date(2027, 1, 3),
        supporting_text=["the weekend after new year"],
        interpretation="Bounded weekend",
    )

    validated = validate_date_resolution_proposal(
        request(text),
        extraction,
        DateResolutionProposal(departure=departure),
    )

    assert validated.departure == departure
    assert validated.unresolved == []


def test_christmas_weekend_boundary_is_enforced_deterministically() -> None:
    text = "Christmas weekend would work."
    anchor = HolidayAnchor(
        kind="holiday",
        anchor_id="christmas",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="Christmas",
        holiday=Holiday.CHRISTMAS,
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[anchor],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="weekend",
            )
        ],
    )
    model_proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2026, 12, 24),
            end=date(2026, 12, 26),
            supporting_text=[text],
            interpretation="Model confused this with over Christmas.",
        )
    )

    validated = validate_date_resolution_proposal(
        request(text),
        extraction,
        model_proposal,
        [resolved_holiday(anchor, date(2026, 12, 25))],
    )

    assert validated.departure is not None
    assert validated.departure.start == date(2026, 12, 24)
    assert validated.departure.end == date(2026, 12, 27)
    assert "Deterministic holiday-weekend policy" in validated.departure.interpretation


def test_over_christmas_uses_distinct_three_day_policy() -> None:
    text = "I can travel over Christmas."
    anchor = HolidayAnchor(
        kind="holiday",
        anchor_id="christmas",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="Christmas",
        holiday=Holiday.CHRISTMAS,
    )
    extraction = CoarseIntentExtraction(date_anchors=[anchor])
    model_proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2026, 12, 24),
            end=date(2026, 12, 25),
            supporting_text=["over Christmas"],
            interpretation="Model proposal ended too early.",
        )
    )

    validated = validate_date_resolution_proposal(
        request(text),
        extraction,
        model_proposal,
        [resolved_holiday(anchor, date(2026, 12, 25))],
    )

    assert validated.departure is not None
    assert validated.departure.start == date(2026, 12, 24)
    assert validated.departure.end == date(2026, 12, 26)
    assert "Christmas-period policy" in validated.departure.interpretation


def test_labor_day_weekend_includes_friday_and_explicit_thursday_flexibility() -> None:
    text = "Labor Day weekend works, and the Thursday as well."
    anchor = HolidayAnchor(
        kind="holiday",
        anchor_id="labor_day",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="Labor Day",
        holiday=Holiday.LABOR_DAY,
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[anchor],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="weekend",
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="the Thursday as well",
            ),
        ],
    )

    validated = validate_date_resolution_proposal(
        request(text),
        extraction,
        DateResolutionProposal(),
        [resolved_holiday(anchor, date(2026, 9, 7))],
    )

    assert validated.departure is not None
    assert validated.departure.start == date(2026, 9, 3)
    assert validated.departure.end == date(2026, 9, 7)


def test_weekend_following_christmas_is_not_reclassified_as_christmas_weekend() -> None:
    text = "The first weekend following Christmas would be good."
    anchor = HolidayAnchor(
        kind="holiday",
        anchor_id="christmas",
        applies_to=TemporalTarget.DEPARTURE,
        raw_text="Christmas",
        holiday=Holiday.CHRISTMAS,
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[anchor],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="first weekend following",
            )
        ],
    )
    model_departure = ProposedDateWindow(
        start=date(2026, 12, 26),
        end=date(2026, 12, 27),
        supporting_text=[text],
        interpretation="First following weekend.",
    )

    validated = validate_date_resolution_proposal(
        request(text),
        extraction,
        DateResolutionProposal(departure=model_departure),
        [resolved_holiday(anchor, date(2026, 12, 25))],
    )

    assert validated.departure == model_departure
