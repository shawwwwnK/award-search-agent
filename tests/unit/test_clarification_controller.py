"""One-way clarification controller behavior."""

from datetime import date

from award_agent.clarification.calendar_plan import CalendarDay, LiteralIntervalOperation
from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import (
    ClarificationTransition,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationOneWayScopeKind,
    ClarificationOneWayScopeNotice,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import (
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSession,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateWindow,
    DateWindowPrecision,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)

CONTEXT = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")


class FakeComposer:
    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=item.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id for issue in input.issues if issue.requirement_id == item.requirement_id
                    ),
                    question=f"Question for {item.requirement_id}?",
                )
                for item in input.requirements
            )
        )


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output = output

    def interpret(self, input: object) -> ClarificationAnswerInterpretation:
        return self.output


def _initial(*, unknowns: list[UnknownField], decision: ClarificationDecision | None = None) -> RequestUnderstandingResult:
    parsed = ParsedRequest(
        raw_text="SFO to Tokyo",
        context=CONTEXT,
        travelers=1,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        departure_window=None,
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
        clarification=decision or ClarificationDecision(action=ClarificationAction.ASK, field="departure", question="When?"),
    )


def _command(session: ClarificationSession, text: str) -> ClarificationAnswerCommand:
    prompt = session.current_revision.prompt
    assert prompt is not None
    return ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=session.current_revision.revision,
        prompt_id=prompt.prompt_id,
        message_id="m1",
        text=text,
    )


def _span(text: str, quote: str) -> MessageSpan:
    start = text.index(quote)
    return MessageSpan(message_id="m1", start=start, end=start + len(quote), text=quote)


def _departure_fact(text: str, quote: str = "October 6") -> ClarificationSemanticFact:
    return ClarificationSemanticFact(
        fact_id="departure",
        span=_span(text, quote),
        target=SemanticTarget.DEPARTURE_WINDOW,
        calendar_operation=LiteralIntervalOperation(start=CalendarDay(month=10, day=6)),
    )


def test_one_way_departure_answer_becomes_ready() -> None:
    session = start_clarification(
        _initial(unknowns=[UnknownField(field="departure", reason=UnknownReason.MISSING, detail="missing")]),
        session_id="one-way",
        composer=FakeComposer(),
    )
    text = "October 6"
    transition = apply_clarification_answer(
        session, _command(session, text), FakeInterpreter(ClarificationAnswerInterpretation(facts=(_departure_fact(text),)))
    )
    assert isinstance(transition, ClarificationTransition)
    assert transition.revision.status is ClarificationSessionStatus.READY
    assert transition.revision.effective_request.departure_window == DateWindow(
        start=date(2026, 10, 6), end=date(2026, 10, 6), precision=DateWindowPrecision.EXACT, raw_text="October 6"
    )


def test_return_scope_notice_stops_without_accepting_an_outbound_sibling() -> None:
    session = start_clarification(
        _initial(unknowns=[UnknownField(field="departure", reason=UnknownReason.MISSING, detail="missing")]),
        session_id="return-notice",
        composer=FakeComposer(),
    )
    text = "Leave October 6 and return October 15"
    output = ClarificationAnswerInterpretation(
        facts=(_departure_fact(text),),
        one_way_scope_notices=(
            ClarificationOneWayScopeNotice(
                kind=ClarificationOneWayScopeKind.RETURN_OR_DURATION,
                span=_span(text, "return October 15"),
            ),
        ),
    )
    transition = apply_clarification_answer(
        session, _command(session, text), FakeInterpreter(output), composer=FakeComposer()
    )
    assert isinstance(transition, ClarificationTransition)
    assert transition.revision.status is ClarificationSessionStatus.STOPPED
    assert transition.revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_SCOPE
    assert transition.revision.effective_request == session.effective_request
    assert transition.revision.outcome is not None
    assert transition.revision.outcome.accepted_amendments == ()
    assert [notice.code for notice in transition.revision.outcome.scope_notices] == ["one_way.return_or_duration"]
    assert "separate one-way request" in transition.revision.outcome.scope_notices[0].message
    assert transition.revision.terminal_message == transition.revision.outcome.scope_notices[0].message


def test_return_scope_notice_stops_without_composing_a_follow_up() -> None:
    session = start_clarification(
        _initial(
            unknowns=[
                UnknownField(field="departure", reason=UnknownReason.MISSING, detail="missing"),
                UnknownField(field="travelers", reason=UnknownReason.MISSING, detail="missing"),
            ]
        ),
        session_id="follow-up-notice",
        composer=FakeComposer(),
    )
    text = "October 6 and return October 15"
    output = ClarificationAnswerInterpretation(
        facts=(_departure_fact(text),),
        one_way_scope_notices=(
            ClarificationOneWayScopeNotice(
                kind=ClarificationOneWayScopeKind.RETURN_OR_DURATION,
                span=_span(text, "return October 15"),
            ),
        ),
    )
    transition = apply_clarification_answer(session, _command(session, text), FakeInterpreter(output))
    assert isinstance(transition, ClarificationTransition)
    assert transition.revision.status is ClarificationSessionStatus.STOPPED
    assert transition.revision.effective_request == session.effective_request
    assert transition.revision.prompt is None


def test_initial_unsupported_scope_stops_with_its_explicit_message() -> None:
    initial = _initial(
        unknowns=[],
        decision=ClarificationDecision(
            action=ClarificationAction.UNSUPPORTED,
            field="one_way_award_scope",
            question="Please submit the return leg as a separate one-way request.",
        ),
    )
    session = start_clarification(initial, session_id="initial-scope", composer=FakeComposer())
    assert session.status is ClarificationSessionStatus.STOPPED
    assert session.current_revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_SCOPE
    assert session.current_revision.terminal_message == initial.clarification.question
