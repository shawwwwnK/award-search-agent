"""Focused Step-1 contracts for additive clarification sessions."""

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from award_agent.clarification import project_initial_request
from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    AnswerTurn,
    ClarificationAction,
    ClarificationDecision,
    ClarificationPrompt,
    ClarificationSession,
    ClarificationSessionRevision,
    ClarificationSessionStatus,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    FieldProvenance,
    InitialSnapshotSource,
    InterpretedDuration,
    LocationAmendment,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingResult,
    ResolutionOutcome,
    TemporalAmendment,
    TravelersAmendment,
    TypedAmendment,
)


def _parsed_request() -> ParsedRequest:
    return ParsedRequest(
        raw_text="Two travelers from SFO to Tokyo October 6 through October 16.",
        context=RequestContext(reference_date=date(2026, 9, 8), timezone="America/Los_Angeles"),
        travelers=2,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        return_expression=None,
        departure_window=DateWindow(
            start=date(2026, 10, 6),
            end=date(2026, 10, 6),
            precision=DateWindowPrecision.EXACT,
            raw_text="October 6",
        ),
        return_window=DateWindow(
            start=date(2026, 10, 16),
            end=date(2026, 10, 16),
            precision=DateWindowPrecision.EXACT,
            raw_text="October 16",
        ),
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[],
        conflicts=[],
        date_resolution=DateResolutionProposal(
            interpreted_duration=InterpretedDuration(
                raw_text="10 days", minimum_days=10, maximum_days=10
            )
        ),
    )


def test_initial_projection_is_additive_and_does_not_mutate_frozen_initial_snapshot() -> None:
    parsed = _parsed_request()
    before = parsed.model_dump(mode="python")

    effective = project_initial_request(parsed)

    assert parsed.model_dump(mode="python") == before
    assert parsed.date_resolution is not None
    assert effective.departure_window == parsed.departure_window
    assert effective.interpreted_duration == parsed.date_resolution.interpreted_duration
    assert [item.contribution_id for item in effective.temporal_contributions] == [
        "initial:departure_window",
        "initial:return_window",
        "initial:duration",
    ]
    assert {item.field for item in effective.field_provenance} == {
        EffectiveField.ORIGIN,
        EffectiveField.DESTINATION,
        EffectiveField.DEPARTURE,
        EffectiveField.RETURN_OR_DURATION,
        EffectiveField.TRAVELERS,
    }

    parsed.origins[0].value = "LAX"
    assert effective.origins[0].value == "SFO"


def test_projection_retains_valid_frozen_v1_empty_raw_text() -> None:
    parsed = _parsed_request()
    parsed.raw_text = ""
    assert parsed.departure_window is not None
    parsed.departure_window.raw_text = ""

    effective = project_initial_request(parsed)

    assert effective.raw_text == ""
    assert effective.temporal_contributions[0].raw_text == ""


def test_message_span_and_typed_amendments_require_turn_grounding_and_scope() -> None:
    span = MessageSpan(message_id="message-1", start=4, end=7, text="SFO")

    with pytest.raises(ValidationError, match="greater than start"):
        MessageSpan(message_id="message-1", start=4, end=4, text="SFO")
    with pytest.raises(ValidationError, match="require a requirement link"):
        LocationAmendment(
            amendment_id="amendment-1",
            target=AmendmentTarget.ORIGIN,
            span=span,
            locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
        )

    amendment: TypedAmendment = TypeAdapter(TypedAmendment).validate_python(
        {
            "amendment_id": "amendment-2",
            "target": "travelers",
            "requirement_ids": ["travelers"],
            "span": span.model_dump(mode="python"),
            "travelers": 2,
        }
    )
    correction = TemporalAmendment(
        amendment_id="amendment-3",
        target=AmendmentTarget.DEPARTURE,
        span=span,
        is_correction=True,
        temporal_text="October 6",
    )

    assert isinstance(amendment, TravelersAmendment)
    assert correction.requirement_ids == ()


def test_revision_ledger_is_contiguous_and_session_exposes_current_projection() -> None:
    parsed = _parsed_request()
    effective = project_initial_request(parsed)
    revision = ClarificationSessionRevision(
        revision=0,
        effective_request=effective,
        status=ClarificationSessionStatus.READY,
    )
    initial_result = RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.NONE,
            reason="Initial snapshot remains frozen.",
        ),
    )
    session = ClarificationSession(
        session_id="session-1",
        initial_result=initial_result,
        revisions=(revision,),
    )

    assert session.current_revision == revision
    assert session.current_revision is not revision
    assert session.effective_request == effective
    initial_result.parsed_request.origins[0].value = "LAX"
    revision.effective_request.origins[0].value = "JFK"
    assert session.initial_result.parsed_request.origins[0].value == "SFO"
    assert session.effective_request.origins[0].value == "SFO"
    skipped_revision = ClarificationSessionRevision(
        revision=2,
        effective_request=effective,
        prompt=ClarificationPrompt(
            prompt_id="prompt-2",
            revision=2,
            requirements=(),
            message="This placeholder is unreachable because the ledger has a revision gap.",
        ),
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    with pytest.raises(ValidationError, match="contiguous"):
        ClarificationSession(
            session_id="session-2",
            initial_result=session.initial_result,
            revisions=(revision, skipped_revision),
        )


def test_initial_revision_must_be_the_exact_projection_of_the_initial_snapshot() -> None:
    parsed = _parsed_request()
    effective = project_initial_request(parsed)
    mismatched_revision = ClarificationSessionRevision(
        revision=0,
        effective_request=effective.model_copy(update={"travelers": 3}),
        status=ClarificationSessionStatus.READY,
    )

    with pytest.raises(ValidationError, match="must match the initial snapshot"):
        ClarificationSession(
            session_id="session-mismatch",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(mismatched_revision,),
        )


def test_accepted_amendments_and_effective_provenance_are_retained_and_linked() -> None:
    parsed = _parsed_request()
    initial_effective = project_initial_request(parsed)
    initial_prompt = ClarificationPrompt(
        prompt_id="prompt-0",
        revision=0,
        requirements=(),
        message="Please confirm your request.",
    )
    initial_revision = ClarificationSessionRevision(
        revision=0,
        effective_request=initial_effective,
        prompt=initial_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    message = MessageSpan(message_id="answer-1", start=0, end=12, text="three people")
    amendment = TravelersAmendment(
        amendment_id="amendment-1",
        target=AmendmentTarget.TRAVELERS,
        span=message,
        is_correction=True,
        travelers=3,
    )
    amended_provenance = tuple(
        FieldProvenance(
            field=item.field,
            source=(
                AnswerMessageSource(span=message)
                if item.field is EffectiveField.TRAVELERS
                else item.source
            ),
            amendment_id="amendment-1" if item.field is EffectiveField.TRAVELERS else None,
        )
        for item in initial_effective.field_provenance
    )
    amended_effective = initial_effective.model_copy(
        update={"travelers": 3, "field_provenance": amended_provenance}
    )
    outcome = ResolutionOutcome(accepted_amendments=(amendment,))
    answer_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=1,
            expected_revision=0,
            prompt_id="prompt-0",
            message=message,
        ),
        outcome=outcome,
        status=ClarificationSessionStatus.READY,
    )
    session = ClarificationSession(
        session_id="session-amendment",
        initial_result=RequestUnderstandingResult(
            parsed_request=parsed,
            clarification=ClarificationDecision(
                action=ClarificationAction.NONE,
                reason="Initial snapshot remains frozen.",
            ),
        ),
        revisions=(initial_revision, answer_revision),
    )

    assert session.current_revision.outcome is not None
    assert session.current_revision.outcome.accepted_amendments == (amendment,)
    assert session.current_revision.outcome.accepted_amendment_ids == ("amendment-1",)

    mismatched_message = MessageSpan(message_id="answer-1", start=0, end=5, text="three")
    mismatched_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=1,
            expected_revision=0,
            prompt_id="prompt-0",
            message=message,
        ),
        outcome=ResolutionOutcome(
            accepted_amendments=(amendment.model_copy(update={"span": mismatched_message}),)
        ),
        status=ClarificationSessionStatus.READY,
    )
    with pytest.raises(ValidationError, match="span must match"):
        ClarificationSession(
            session_id="session-mismatched-provenance",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(initial_revision, mismatched_revision),
        )

    second_prompt = ClarificationPrompt(
        prompt_id="prompt-1",
        revision=1,
        requirements=(),
        message="Anything else?",
    )
    awaiting_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=answer_revision.answer_turn,
        outcome=outcome,
        prompt=second_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    duplicate_message_revision = ClarificationSessionRevision(
        revision=2,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=2,
            expected_revision=1,
            prompt_id="prompt-1",
            message=message,
        ),
        outcome=ResolutionOutcome(),
        status=ClarificationSessionStatus.READY,
    )
    with pytest.raises(ValidationError, match="message IDs must be unique"):
        ClarificationSession(
            session_id="session-duplicate-message",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(initial_revision, awaiting_revision, duplicate_message_revision),
        )


def test_new_contracts_do_not_widen_the_frozen_parsed_request_schema() -> None:
    parsed_properties = ParsedRequest.model_json_schema()["properties"]

    assert "effective_request" not in parsed_properties
    assert "revisions" not in parsed_properties
    assert "message_id" not in parsed_properties
    assert InitialSnapshotSource(field=EffectiveField.ORIGIN).kind == "initial_snapshot"
