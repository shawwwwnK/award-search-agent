from datetime import date

import pytest

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    GroundedTemporalEvidence,
    InterpretedDuration,
    ProposedDateWindow,
    RawRequest,
    RequestContext,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    ValidatedSourceSpan,
)
from award_agent.intent.conflicts import detect_conflicts
from award_agent.intent.evidence import (
    EvidenceErrorCode,
    TemporalEvidenceValidationError,
    ground_date_resolution_evidence,
    ground_temporal_evidence,
    resolve_source_quote,
    validate_source_span,
)
from award_agent.intent.evidence_eval import (
    EvalFixtureValidationError,
    compile_evidence_expectations,
    evaluate_evidence_support,
)

LABOR_REQUEST = (
    "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend "
    "for about 10 days. We are flexible to leave on the Thursday as well."
)


def raw_request(text: str = LABOR_REQUEST) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
    )


def phrase(
    quote: str,
    *claims: TemporalEvidenceClaim,
    occurrence_index: int | None = None,
) -> TemporalPhrase:
    return TemporalPhrase(
        applies_to=TemporalPhraseTarget.UNSPECIFIED,
        raw_text=quote,
        claim_ids=list(claims),
        occurrence_index=occurrence_index,
    )


def grounded(
    quote: str,
    *claims: TemporalEvidenceClaim,
    source: str = LABOR_REQUEST,
) -> list[GroundedTemporalEvidence]:
    return ground_temporal_evidence(
        raw_request(source),
        CoarseIntentExtraction(temporal_phrases=[phrase(quote, *claims)]),
    )


def labor_expectations() -> dict[str, object]:
    return {
        "departure_period": {
            "allowed_envelopes": ["leaving on Labor Day weekend"],
            "required_all": ["weekend"],
            "preferred_spans": ["weekend"],
        },
        "approximate_duration": {
            "allowed_envelopes": ["for about 10 days"],
            "required_all": ["about", "10", "days"],
            "preferred_spans": ["for about 10 days"],
        },
        "alternate_departure_day": {
            "allowed_envelopes": ["We are flexible to leave on the Thursday as well."],
            "required_all": ["Thursday"],
            "required_any_groups": [["flexible", "as well"]],
            "preferred_spans": ["the Thursday as well"],
        },
    }


def test_exact_quote_resolves_to_exclusive_offsets_and_source_derived_text() -> None:
    span = resolve_source_quote(
        LABOR_REQUEST,
        "on the Thursday as well",
        claim_id="alternate_departure_day",
    )

    assert span.start == LABOR_REQUEST.index("on the Thursday as well")
    assert span.end == span.start + len("on the Thursday as well")
    assert span.text == LABOR_REQUEST[span.start : span.end]
    assert span.source_id == "original_request"


@pytest.mark.parametrize(
    ("quote", "code"),
    [
        ("leaving on the Thursday as well", EvidenceErrorCode.UNGROUNDED_QUOTE),
        ("Thursday is also okay", EvidenceErrorCode.UNGROUNDED_QUOTE),
        ("On the Thursday as well", EvidenceErrorCode.UNGROUNDED_QUOTE),
        ("on  the Thursday as well", EvidenceErrorCode.UNGROUNDED_QUOTE),
        ("", EvidenceErrorCode.UNGROUNDED_QUOTE),
    ],
)
def test_nonexact_quotes_are_rejected_without_normalization(
    quote: str, code: EvidenceErrorCode
) -> None:
    with pytest.raises(TemporalEvidenceValidationError) as captured:
        resolve_source_quote(
            LABOR_REQUEST,
            quote,
            claim_id="alternate_departure_day",
        )

    assert captured.value.code is code
    assert captured.value.quote == quote
    assert captured.value.claim_id == "alternate_departure_day"
    assert captured.value.ambiguous is False


def test_repeated_quote_requires_occurrence_disambiguation() -> None:
    source = "Friday works; Friday is better."

    with pytest.raises(TemporalEvidenceValidationError) as captured:
        resolve_source_quote(source, "Friday", claim_id="departure_period")

    assert captured.value.code is EvidenceErrorCode.AMBIGUOUS_QUOTE
    assert captured.value.ambiguous is True


def test_valid_occurrence_resolves_and_invalid_occurrence_fails() -> None:
    source = "Friday works; Friday is better."
    second = resolve_source_quote(
        source,
        "Friday",
        claim_id="departure_period",
        occurrence_index=1,
    )

    assert second.start == source.rindex("Friday")
    with pytest.raises(TemporalEvidenceValidationError) as captured:
        resolve_source_quote(
            source,
            "Friday",
            claim_id="departure_period",
            occurrence_index=2,
        )
    assert captured.value.code is EvidenceErrorCode.INVALID_OCCURRENCE


def test_mismatched_external_span_cannot_be_revalidated() -> None:
    span = ValidatedSourceSpan(start=0, end=2, text="xx")

    with pytest.raises(TemporalEvidenceValidationError, match="does not equal"):
        validate_source_span("Friday", span, claim_id="departure_period")


def test_legacy_plain_temporal_phrase_uses_the_same_strict_grounding_path() -> None:
    evidence = ground_temporal_evidence(
        raw_request("Travel next weekend"),
        CoarseIntentExtraction(
            temporal_phrases=[
                TemporalPhrase(
                    applies_to=TemporalPhraseTarget.DEPARTURE,
                    raw_text="next weekend",
                )
            ]
        ),
    )

    assert evidence[0].claim_ids == [TemporalEvidenceClaim.DEPARTURE_PERIOD]
    assert evidence[0].span.text == "next weekend"


def test_second_pass_quote_is_also_canonicalized_to_source_offsets() -> None:
    source = "Travel in early May"
    proposal = DateResolutionProposal(
        departure=ProposedDateWindow(
            start=date(2027, 5, 1),
            end=date(2027, 5, 10),
            supporting_text=["early May"],
            interpretation="Early month.",
        )
    )

    evidence = ground_date_resolution_evidence(raw_request(source), proposal, [])

    assert evidence[0].claim_ids == [TemporalEvidenceClaim.DEPARTURE_PERIOD]
    assert evidence[0].span.text == source[evidence[0].span.start : evidence[0].span.end]


def test_duration_evidence_is_not_reclassified_as_an_explicit_return_phrase() -> None:
    source = "Travel for about 10 days"
    first_pass = grounded(
        "about 10 days",
        TemporalEvidenceClaim.APPROXIMATE_DURATION,
        source=source,
    )
    proposal = DateResolutionProposal(
        return_date=ProposedDateWindow(
            start=date(2026, 9, 10),
            end=date(2026, 9, 12),
            supporting_text=["about 10 days"],
            interpretation="Derived from duration.",
        ),
        interpreted_duration=InterpretedDuration(
            raw_text="about 10 days",
            minimum_days=9,
            maximum_days=11,
        ),
    )

    evidence = ground_date_resolution_evidence(raw_request(source), proposal, first_pass)

    assert evidence[0].claim_ids == [TemporalEvidenceClaim.APPROXIMATE_DURATION]


@pytest.mark.parametrize(
    "quote",
    ["weekend", "Labor Day weekend", "leaving on Labor Day weekend"],
)
def test_preferred_shorter_and_longer_grounded_weekend_boundaries_pass(
    quote: str,
) -> None:
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"departure_period": labor_expectations()["departure_period"]},
    )
    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded(quote, TemporalEvidenceClaim.DEPARTURE_PERIOD),
        expectations,
    )

    assert result.evidence_support_valid is True
    assert result.preferred_boundary_exact_match is (quote == "weekend")


@pytest.mark.parametrize(
    "quote",
    ["the Thursday as well", "on the Thursday as well", "Thursday as well"],
)
def test_alternate_departure_accepts_sufficient_grounded_boundaries(quote: str) -> None:
    rule = labor_expectations()["alternate_departure_day"]
    expectations = compile_evidence_expectations(LABOR_REQUEST, {"alternate_departure_day": rule})

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded(quote, TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY),
        expectations,
    )

    assert result.evidence_support_valid is True


def test_grounded_but_semantically_insufficient_thursday_fails() -> None:
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"alternate_departure_day": labor_expectations()["alternate_departure_day"]},
    )

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded("Thursday", TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY),
        expectations,
    )

    assert result.evidence_support_valid is False
    assert result.failures[0].code == "missing_required_any_group"


@pytest.mark.parametrize("quote", ["for about 10 days", "about 10 days"])
def test_approximate_duration_accepts_grounded_sufficient_boundaries(quote: str) -> None:
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"approximate_duration": labor_expectations()["approximate_duration"]},
    )

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded(quote, TemporalEvidenceClaim.APPROXIMATE_DURATION),
        expectations,
    )

    assert result.evidence_support_valid is True


def test_approximate_duration_without_modifier_fails() -> None:
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"approximate_duration": labor_expectations()["approximate_duration"]},
    )

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded("10 days", TemporalEvidenceClaim.APPROXIMATE_DURATION),
        expectations,
    )

    assert result.evidence_support_valid is False
    assert "about" in result.insufficient_spans


@pytest.mark.parametrize(
    "quote",
    [LABOR_REQUEST, "Labor Day weekend for about 10 days"],
)
def test_overbroad_or_cross_claim_span_fails_narrow_weekend_envelope(quote: str) -> None:
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"departure_period": labor_expectations()["departure_period"]},
    )

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        grounded(quote, TemporalEvidenceClaim.DEPARTURE_PERIOD),
        expectations,
    )

    assert result.evidence_support_valid is False
    assert result.failures[0].code == "outside_allowed_envelope"


def test_multiple_exact_spans_can_jointly_satisfy_one_claim() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            phrase("flexible", TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY),
            phrase("Thursday", TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY),
        ]
    )
    expectations = compile_evidence_expectations(
        LABOR_REQUEST,
        {"alternate_departure_day": labor_expectations()["alternate_departure_day"]},
    )

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        ground_temporal_evidence(raw_request(), extraction),
        expectations,
    )

    assert result.evidence_support_valid is True


def test_spans_from_unrelated_envelopes_cannot_be_combined() -> None:
    source = "Friday is flexible. Sunday is also possible."
    rules = {
        "departure_period": {
            "allowed_envelopes": ["Friday is flexible", "Sunday is also possible"],
            "required_all": ["Friday"],
        }
    }
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            phrase("Friday", TemporalEvidenceClaim.DEPARTURE_PERIOD),
            phrase("also", TemporalEvidenceClaim.DEPARTURE_PERIOD),
        ]
    )

    result = evaluate_evidence_support(
        source,
        ground_temporal_evidence(raw_request(source), extraction),
        compile_evidence_expectations(source, rules),
    )

    assert result.evidence_support_valid is False
    assert result.failures[0].code == "outside_allowed_envelope"


def test_one_canonical_span_can_support_multiple_explicit_claims() -> None:
    evidence = grounded(
        "leaving on Labor Day weekend",
        TemporalEvidenceClaim.DEPARTURE_ANCHOR,
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    )
    rules = {
        "departure_anchor": {
            "allowed_envelopes": ["leaving on Labor Day weekend"],
            "required_all": ["Labor Day"],
        },
        "departure_period": labor_expectations()["departure_period"],
    }

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        evidence,
        compile_evidence_expectations(LABOR_REQUEST, rules),
    )

    assert len(evidence) == 1
    assert result.evidence_support_valid is True


def test_evidence_linked_to_one_claim_cannot_satisfy_another_claim() -> None:
    evidence = grounded(
        "leaving on Labor Day weekend",
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
    )
    rules = {
        "departure_anchor": {
            "allowed_envelopes": ["leaving on Labor Day weekend"],
            "required_all": ["Labor Day"],
        }
    }

    result = evaluate_evidence_support(
        LABOR_REQUEST,
        evidence,
        compile_evidence_expectations(LABOR_REQUEST, rules),
    )

    assert result.evidence_support_valid is False
    assert result.missing_expected_claims == ["departure_anchor"]
    assert any(failure.code == "evidence_not_linked_to_claim" for failure in result.failures)


def test_ungrounded_evidence_never_reaches_semantic_scoring() -> None:
    extraction = CoarseIntentExtraction(
        temporal_phrases=[
            phrase(
                "leaving on the Thursday as well",
                TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
            )
        ]
    )

    with pytest.raises(TemporalEvidenceValidationError):
        ground_temporal_evidence(raw_request(), extraction)


@pytest.mark.parametrize(
    ("rules", "reason"),
    [
        (
            {"departure_period": {"allowed_envelopes": ["not in source"]}},
            "ungrounded_quote",
        ),
        (
            {
                "departure_period": {
                    "allowed_envelopes": ["Labor Day weekend"],
                    "required_all": ["about"],
                }
            },
            "outside every allowed envelope",
        ),
        (
            {
                "departure_period": {
                    "allowed_envelopes": ["Labor Day weekend"],
                    "preferred_spans": ["not in source"],
                }
            },
            "ungrounded_quote",
        ),
    ],
)
def test_malformed_fixture_strings_fail_compilation(rules: dict[str, object], reason: str) -> None:
    with pytest.raises(EvalFixtureValidationError, match=reason):
        compile_evidence_expectations(LABOR_REQUEST, rules)


def test_ambiguous_fixture_quote_requires_occurrence() -> None:
    source = "Friday then Friday"
    rules = {"departure_period": {"allowed_envelopes": ["Friday"]}}

    with pytest.raises(EvalFixtureValidationError, match="ambiguous_quote"):
        compile_evidence_expectations(source, rules)

    compiled = compile_evidence_expectations(
        source,
        {"departure_period": {"allowed_envelopes": [{"quote": "Friday", "occurrence_index": 1}]}},
    )
    assert compiled[0].allowed_envelopes[0].start == source.rindex("Friday")


def test_missing_unknown_has_no_fabricated_evidence() -> None:
    from award_agent.domain import UnknownField, UnknownReason

    unknown = UnknownField(
        field="return_or_duration",
        reason=UnknownReason.MISSING,
        detail="Not mentioned.",
    )

    assert unknown.evidence == []


def test_conflicting_alternatives_keep_separate_grounded_evidence() -> None:
    source = "Leave July 10 and return July 8."
    evidence = ground_temporal_evidence(
        raw_request(source),
        CoarseIntentExtraction(
            temporal_phrases=[
                phrase("July 10", TemporalEvidenceClaim.DEPARTURE_PERIOD),
                phrase("July 8", TemporalEvidenceClaim.RETURN_PERIOD),
            ]
        ),
    )
    conflicts = detect_conflicts(
        DateWindow(
            start=date(2026, 7, 10),
            end=date(2026, 7, 10),
            precision=DateWindowPrecision.EXACT,
            raw_text="July 10",
        ),
        DateWindow(
            start=date(2026, 7, 8),
            end=date(2026, 7, 8),
            precision=DateWindowPrecision.EXACT,
            raw_text="July 8",
        ),
        None,
        evidence,
    )

    assert conflicts[0].code == "return_before_departure"
    assert conflicts[0].evidence_by_alternative["departure"][0].span.text == "July 10"
    assert conflicts[0].evidence_by_alternative["return_date"][0].span.text == "July 8"
