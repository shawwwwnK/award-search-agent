"""Offline controller tests for additive clarification sessions."""

from datetime import date

import pytest

from award_agent.clarification.controller import (
    ClarificationCommandError,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import ClarificationAnswerInterpretation
from award_agent.domain import (
    AmendmentTarget,
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSession,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateWindow,
    DateWindowPrecision,
    LocationAmendment,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RejectedFragment,
    RejectedFragmentReason,
    RequestContext,
    RequestUnderstandingResult,
    TemporalAmendment,
    TravelersAmendment,
)


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output = output
        self.calls = 0

    def interpret(self, _input: object) -> ClarificationAnswerInterpretation:
        self.calls += 1
        return self.output


_CONTEXT = RequestContext(reference_date=date(2026, 9, 8), timezone="America/Los_Angeles")


def _initial(*, all_unknown: bool = True) -> RequestUnderstandingResult:
    unknowns = []
    if all_unknown:
        from award_agent.domain import UnknownField, UnknownReason

        unknowns = [
            UnknownField(field=field, reason=UnknownReason.MISSING, detail=f"{field} missing")
            for field in ("origin", "destination", "departure", "return_or_duration", "travelers")
        ]
    parsed = ParsedRequest(
        raw_text="Need a trip.",
        context=_CONTEXT,
        travelers=None,
        origins=[],
        destinations=[],
        departure_expression=None,
        return_expression=None,
        departure_window=None,
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=unknowns,
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK if all_unknown else ClarificationAction.NONE,
            field="origin" if all_unknown else None,
            question="Where from?" if all_unknown else None,
        ),
    )


def _span(text: str, value: str) -> MessageSpan:
    start = text.index(value)
    return MessageSpan(message_id="m1", start=start, end=start + len(value), text=value)


def _command(
    session: ClarificationSession,
    text: str,
    *,
    message_id: str = "m1",
    revision: int | None = None,
) -> ClarificationAnswerCommand:
    current = session.current_revision
    assert current.prompt is not None
    return ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=current.revision if revision is None else revision,
        prompt_id=current.prompt.prompt_id,
        message_id=message_id,
        text=text,
    )


def test_all_blockers_can_be_resolved_atomically_and_ready() -> None:
    session = start_clarification(_initial(), session_id="s1")
    assert session.status is ClarificationSessionStatus.AWAITING_ANSWER
    prompt = session.current_revision.prompt
    assert prompt is not None
    assert [item.requirement_id for item in prompt.requirements] == [
        "origin",
        "destination",
        "departure",
        "return_or_duration",
        "travelers",
    ]
    text = "SFO to Tokyo, two travelers, depart October 6 and return October 16"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-1",
                    target=AmendmentTarget.ORIGIN,
                    requirement_ids=("origin",),
                    span=_span(text, "SFO"),
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
                ),
                LocationAmendment(
                    amendment_id="destination-1",
                    target=AmendmentTarget.DESTINATION,
                    requirement_ids=("destination",),
                    span=_span(text, "Tokyo"),
                    locations=(LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo"),),
                ),
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
                TemporalAmendment(
                    amendment_id="departure-1",
                    target=AmendmentTarget.DEPARTURE,
                    requirement_ids=("departure",),
                    span=_span(text, "depart October 6"),
                    temporal_text="October 6",
                ),
                TemporalAmendment(
                    amendment_id="return-1",
                    target=AmendmentTarget.RETURN_OR_DURATION,
                    requirement_ids=("return_or_duration",),
                    span=_span(text, "return October 16"),
                    temporal_text="October 16",
                ),
            )
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), fake)

    assert transition.session.status is ClarificationSessionStatus.READY
    assert transition.revision.outcome is not None
    assert len(transition.revision.outcome.accepted_amendments) == 5
    assert transition.session.effective_request.travelers == 2
    assert transition.session.effective_request.departure_window == DateWindow(
        start=date(2026, 10, 6),
        end=date(2026, 10, 6),
        precision=DateWindowPrecision.EXACT,
        raw_text="October 6",
    )


def test_replay_precedes_freshness_and_message_reuse_with_new_text_fails() -> None:
    session = start_clarification(_initial(), session_id="s1")
    text = "two travelers"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
            )
        )
    )
    first = apply_clarification_answer(session, _command(session, text), fake)
    replay_command = _command(first.session, text, revision=0)
    replay = apply_clarification_answer(first.session, replay_command, fake)

    assert replay.replayed is True
    assert replay.revision.revision == 1
    assert replay.session.current_revision.revision == 1
    assert fake.calls == 1
    with pytest.raises(ClarificationCommandError, match="different text"):
        apply_clarification_answer(
            first.session, _command(first.session, "three travelers", revision=0), fake
        )


def test_cancel_does_not_call_interpreter_and_no_progress_stops_on_second_answer() -> None:
    session = start_clarification(_initial(), session_id="s1")
    fake = FakeInterpreter(ClarificationAnswerInterpretation())
    cancelled = apply_clarification_answer(session, _command(session, "cancel"), fake)
    assert cancelled.session.status is ClarificationSessionStatus.STOPPED
    assert cancelled.revision.stop_reason is ClarificationStopReason.CANCELLED
    assert fake.calls == 0

    session = start_clarification(_initial(), session_id="s2")
    first = apply_clarification_answer(session, _command(session, "I do not know"), fake)
    assert first.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    second = apply_clarification_answer(
        first.session, _command(first.session, "I still do not know", message_id="m2"), fake
    )
    assert second.session.status is ClarificationSessionStatus.STOPPED
    assert second.revision.stop_reason is ClarificationStopReason.NO_PROGRESS_LIMIT


def test_unsupported_revision_stops_without_discarding_valid_sibling() -> None:
    session = start_clarification(_initial(), session_id="s1")
    text = "two travelers and add first class"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
            ),
            rejected_fragments=(
                RejectedFragment(
                    span=_span(text, "first class"),
                    reason=RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION,
                    detail="cabin revision is deferred",
                ),
            ),
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), fake)

    assert transition.session.status is ClarificationSessionStatus.STOPPED
    assert transition.revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION
    assert transition.session.effective_request.travelers == 2


def test_correction_cannot_fill_an_unresolved_field_and_duplicate_field_writes_reask() -> None:
    session = start_clarification(_initial(), session_id="s1")
    correction_text = "Actually change the origin to SFO"
    correction = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-correction",
                    target=AmendmentTarget.ORIGIN,
                    is_correction=True,
                    span=_span(correction_text, "Actually change the origin to SFO"),
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
                ),
            )
        )
    )
    stopped = apply_clarification_answer(session, _command(session, correction_text), correction)
    assert stopped.session.status is ClarificationSessionStatus.STOPPED
    assert stopped.revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION
    assert not stopped.session.effective_request.origins

    session = start_clarification(_initial(), session_id="s2")
    text = "two travelers or three travelers"
    duplicate = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="two",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
                TravelersAmendment(
                    amendment_id="three",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "three"),
                    travelers=3,
                ),
            )
        )
    )
    reasked = apply_clarification_answer(session, _command(session, text), duplicate)
    assert reasked.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert reasked.session.effective_request.travelers is None
    assert reasked.revision.outcome is not None
    assert [item.reason for item in reasked.revision.outcome.rejected_fragments] == [
        RejectedFragmentReason.AMBIGUOUS,
        RejectedFragmentReason.AMBIGUOUS,
    ]


def test_stale_wrong_prompt_and_terminal_commands_do_not_call_interpreter() -> None:
    session = start_clarification(_initial(), session_id="s1")
    fake = FakeInterpreter(ClarificationAnswerInterpretation())
    with pytest.raises(ClarificationCommandError, match="stale"):
        apply_clarification_answer(session, _command(session, "hello", revision=4), fake)
    current = session.current_revision
    assert current.prompt is not None
    wrong_prompt = ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=0,
        prompt_id="wrong",
        message_id="m1",
        text="hello",
    )
    with pytest.raises(ClarificationCommandError, match="prompt ID"):
        apply_clarification_answer(session, wrong_prompt, fake)
    stopped = apply_clarification_answer(session, _command(session, "Please cancel."), fake)
    terminal_command = ClarificationAnswerCommand(
        session_id=stopped.session.session_id,
        expected_revision=stopped.revision.revision,
        prompt_id="former-prompt",
        message_id="m2",
        text="hello",
    )
    with pytest.raises(ClarificationCommandError, match="terminal"):
        apply_clarification_answer(stopped.session, terminal_command, fake)
    assert fake.calls == 0
