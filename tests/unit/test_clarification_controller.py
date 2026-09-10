"""Core reducer tests for semantic clarification answers."""

from datetime import date

import pytest

from award_agent.clarification.calendar_plan import (
    CalendarAnchorEdge,
    CalendarCalculationOperation,
    CalendarDay,
    DurationOperation,
    LiteralIntervalOperation,
    OffsetIntervalOperation,
    PriorFactAnchor,
)
from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import (
    ClarificationCompositionPending,
    ClarificationInterpretationPending,
    ClarificationPromptCompositionFailedError,
    ClarificationTransition,
    apply_clarification_answer,
    retry_prompt_composition,
    start_clarification,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationDiscourseAct,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import (
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSession,
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


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output = output
        self.inputs: list[object] = []

    def interpret(self, input: object) -> ClarificationAnswerInterpretation:
        self.inputs.append(input)
        return self.output


class RepairingFakeInterpreter(FakeInterpreter):
    def __init__(
        self, output: ClarificationAnswerInterpretation, repaired: ClarificationAnswerInterpretation
    ) -> None:
        super().__init__(output)
        self.repaired = repaired
        self.repair_calls: list[tuple[object, dict[str, object]]] = []

    def repair_calendar_proposals(
        self, input: object, **kwargs: object
    ) -> ClarificationAnswerInterpretation:
        self.repair_calls.append((input, kwargs))
        return self.repaired


class FakeComposer:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.inputs: list[ClarificationPromptComposerInput] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.inputs.append(input)
        if self.error is not None:
            raise self.error
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question=f"Question for {requirement.requirement_id}?",
                )
                for requirement in input.requirements
            )
        )


CONTEXT = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")


def _initial() -> RequestUnderstandingResult:
    parsed = ParsedRequest(
        raw_text="SFO to England next month",
        context=CONTEXT,
        travelers=1,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.COUNTRY, value="England", raw_text="England")],
        departure_expression=None,
        return_expression=None,
        departure_window=DateWindow(
            start=date(2026, 10, 1),
            end=date(2026, 10, 31),
            precision=DateWindowPrecision.WINDOW,
            raw_text="next month",
        ),
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[
            UnknownField(field="return_or_duration", reason=UnknownReason.MISSING, detail="missing")
        ],
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK, field="return_or_duration", question="How long?"
        ),
    )


def _command(session: ClarificationSession, text: str) -> ClarificationAnswerCommand:
    current = session.current_revision
    assert current.prompt is not None
    return ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=current.revision,
        prompt_id=current.prompt.prompt_id,
        message_id="m1",
        text=text,
    )


def _fact(
    identifier: str,
    text: str,
    quote: str,
    target: SemanticTarget,
    calendar_operation: CalendarCalculationOperation,
) -> ClarificationSemanticFact:
    start = text.index(quote)
    return ClarificationSemanticFact(
        fact_id=identifier,
        span=MessageSpan(message_id="m1", start=start, end=start + len(quote), text=quote),
        target=target,
        calendar_operation=calendar_operation,
    )


def _committed(value: object) -> ClarificationTransition:
    assert isinstance(value, ClarificationTransition)
    return value


def test_resolved_departure_correction_and_return_duration_become_ready() -> None:
    session = start_clarification(_initial(), session_id="semantic", composer=FakeComposer())
    text = "I want to leave early October and go for about a week"
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "departure",
                    text,
                    "leave early October",
                    SemanticTarget.DEPARTURE_WINDOW,
                    LiteralIntervalOperation(
                        start=CalendarDay(month=10, day=1), end=CalendarDay(month=10, day=10)
                    ),
                ),
                _fact(
                    "duration",
                    text,
                    "about a week",
                    SemanticTarget.DURATION,
                    DurationOperation(minimum_days=6, maximum_days=8, approximate=True),
                ),
            )
        )
    )
    transition = _committed(apply_clarification_answer(session, _command(session, text), receiver))
    effective = transition.revision.effective_request
    assert transition.revision.status.value == "ready"
    assert effective.departure_window is not None
    assert (effective.departure_window.start, effective.departure_window.end) == (
        date(2026, 10, 1),
        date(2026, 10, 10),
    )
    assert effective.interpreted_duration is not None
    assert (
        effective.interpreted_duration.minimum_days,
        effective.interpreted_duration.maximum_days,
    ) == (6, 8)
    assert transition.revision.outcome is not None
    assert len(transition.revision.outcome.accepted_amendments) == 2


def test_cancellation_is_receiver_classification_not_controller_text_parsing() -> None:
    session = start_clarification(_initial(), session_id="cancel", composer=FakeComposer())
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(discourse_act=ClarificationDiscourseAct.CANCEL)
    )
    transition = _committed(
        apply_clarification_answer(session, _command(session, "whatever words"), receiver)
    )
    assert receiver.inputs
    assert transition.revision.stop_reason.value == "cancelled"  # type: ignore[union-attr]


def test_invalid_semantic_fact_is_rejected_while_session_can_continue() -> None:
    session = start_clarification(_initial(), session_id="bad", composer=FakeComposer())
    text = "twelve-ish"
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "bad",
                    text,
                    text,
                    SemanticTarget.DEPARTURE_WINDOW,
                    LiteralIntervalOperation(start=CalendarDay(year=2026, month=2, day=29)),
                ),
            )
        )
    )
    transition = apply_clarification_answer(
        session, _command(session, text), receiver, composer=FakeComposer()
    )
    assert isinstance(transition, ClarificationInterpretationPending)
    assert transition.session is session
    assert transition.outcome is not None
    assert transition.outcome.accepted_amendments == ()


def test_invalid_sibling_does_not_discard_a_valid_duration_fact() -> None:
    session = start_clarification(_initial(), session_id="valid-sibling", composer=FakeComposer())
    text = "about a week and the other date thing"
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "duration",
                    text,
                    "about a week",
                    SemanticTarget.DURATION,
                    DurationOperation(minimum_days=6, maximum_days=8, approximate=True),
                ),
                _fact(
                    "bad-return",
                    text,
                    "other date thing",
                    SemanticTarget.RETURN_WINDOW,
                    LiteralIntervalOperation(start=CalendarDay(year=2026, month=2, day=29)),
                ),
            )
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), receiver)

    assert isinstance(transition, ClarificationInterpretationPending)
    assert transition.outcome is not None
    assert {item.amendment_id for item in transition.outcome.accepted_amendments} == {"duration"}


def test_calendar_compile_failure_gets_one_model_owned_repair_without_losing_valid_sibling() -> (
    None
):
    session = start_clarification(
        _initial(), session_id="repaired-sibling", composer=FakeComposer()
    )
    text = "about a week and replace the departure"
    invalid = _fact(
        "departure",
        text,
        "replace the departure",
        SemanticTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(start=CalendarDay(year=2026, month=2, day=29)),
    )
    valid_duration = _fact(
        "duration",
        text,
        "about a week",
        SemanticTarget.DURATION,
        DurationOperation(minimum_days=6, maximum_days=8, approximate=True),
    )
    repaired_departure = _fact(
        "departure",
        text,
        "replace the departure",
        SemanticTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(start=CalendarDay(month=10, day=6)),
    )
    receiver = RepairingFakeInterpreter(
        ClarificationAnswerInterpretation(facts=(valid_duration, invalid)),
        ClarificationAnswerInterpretation(facts=(repaired_departure,)),
    )

    transition = _committed(apply_clarification_answer(session, _command(session, text), receiver))

    assert transition.revision.status.value == "ready"
    assert len(receiver.repair_calls) == 1
    assert transition.revision.outcome is not None
    assert {item.amendment_id for item in transition.revision.outcome.accepted_amendments} == {
        "departure",
        "duration",
    }
    assert transition.revision.outcome.rejected_fragments == ()


def test_same_answer_prior_fact_dependency_is_order_independent() -> None:
    session = start_clarification(_initial(), session_id="permuted", composer=FakeComposer())
    text = "return after departure"
    departure = _fact(
        "departure",
        text,
        "departure",
        SemanticTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(start=CalendarDay(month=10, day=6)),
    )
    returned = _fact(
        "return",
        text,
        "return",
        SemanticTarget.RETURN_WINDOW,
        OffsetIntervalOperation(
            anchor=PriorFactAnchor(fact_id="departure", edge=CalendarAnchorEdge.START),
            start_offset_days=7,
        ),
    )
    transition = _committed(
        apply_clarification_answer(
            session,
            _command(session, text),
            FakeInterpreter(ClarificationAnswerInterpretation(facts=(returned, departure))),
        )
    )

    assert transition.revision.status.value == "ready"
    assert transition.revision.effective_request.return_window is not None
    assert transition.revision.effective_request.return_window.start == date(2026, 10, 13)


def test_failed_calendar_repair_returns_pending_with_valid_sibling_payload() -> None:
    from award_agent.clarification.interpreter import ClarificationInterpretationUnavailable

    class RepairUnavailableFake(FakeInterpreter):
        def repair_calendar_proposals(
            self, _input: object, **_kwargs: object
        ) -> ClarificationInterpretationUnavailable:
            return ClarificationInterpretationUnavailable(
                code="receiver_repair_unavailable", detail="offline", repair_attempted=True
            )

    session = start_clarification(_initial(), session_id="repair-pending", composer=FakeComposer())
    text = "about a week and impossible departure"
    receiver = RepairUnavailableFake(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "duration",
                    text,
                    "about a week",
                    SemanticTarget.DURATION,
                    DurationOperation(minimum_days=6, maximum_days=8, approximate=True),
                ),
                _fact(
                    "departure",
                    text,
                    "impossible departure",
                    SemanticTarget.DEPARTURE_WINDOW,
                    LiteralIntervalOperation(start=CalendarDay(year=2026, month=2, day=29)),
                ),
            )
        )
    )
    pending = apply_clarification_answer(session, _command(session, text), receiver)

    assert isinstance(pending, ClarificationInterpretationPending)
    assert pending.session is session
    assert pending.outcome is not None
    assert [item.amendment_id for item in pending.outcome.accepted_amendments] == ["duration"]
    assert pending.effective_request is not None
    assert pending.effective_request.interpreted_duration is not None


def test_unavailable_receiver_returns_non_mutating_retryable_pending_result() -> None:
    session = start_clarification(
        _initial(), session_id="pending-receiver", composer=FakeComposer()
    )
    from award_agent.clarification.interpreter import ClarificationInterpretationUnavailable

    class UnavailableFake:
        def interpret(self, _input: object) -> ClarificationInterpretationUnavailable:
            return ClarificationInterpretationUnavailable(
                code="receiver_call_unavailable", detail="offline"
            )

    pending = apply_clarification_answer(
        session,
        _command(session, "a reasonable answer"),
        UnavailableFake(),
    )
    assert isinstance(pending, ClarificationInterpretationPending)
    assert pending.session is session
    assert pending.code == "receiver_call_unavailable"


def test_unauthorized_target_sibling_does_not_terminally_stop_valid_duration() -> None:
    initial = _initial()
    session = start_clarification(
        initial.model_copy(
            update={"parsed_request": initial.parsed_request.model_copy(update={"travelers": None})}
        ),
        session_id="unauthorized-sibling",
        composer=FakeComposer(),
    )
    text = "about a week and a different other thing"
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "duration",
                    text,
                    "about a week",
                    SemanticTarget.DURATION,
                    DurationOperation(minimum_days=6, maximum_days=8, approximate=True),
                ),
                ClarificationSemanticFact(
                    fact_id="unsupported-return",
                    span=MessageSpan(
                        message_id="m1",
                        start=text.index("different other thing"),
                        end=text.index("different other thing") + len("different other thing"),
                        text="different other thing",
                    ),
                    target=SemanticTarget.TRAVELERS,
                    travelers=2,
                ),
            )
        )
    )

    transition = _committed(apply_clarification_answer(session, _command(session, text), receiver))

    assert transition.revision.status.value == "ready"
    assert transition.revision.outcome is not None
    assert {item.amendment_id for item in transition.revision.outcome.accepted_amendments} == {
        "duration"
    }
    rejected = transition.revision.outcome.rejected_fragments
    assert len(rejected) == 1
    assert rejected[0].reason.value == "invalid"
    assert rejected[0].reason_code == "receiver.target_not_authorized"


def test_composer_receives_authoritative_post_reduction_requirements_and_issues() -> None:
    composer = FakeComposer()
    session = start_clarification(_initial(), session_id="composed", composer=composer)
    initial_input = composer.inputs[-1]
    assert [item.requirement_id for item in initial_input.requirements] == ["return_or_duration"]
    assert [item.issue_id for item in initial_input.issues] == ["return_or_duration:missing"]

    transition = _committed(
        apply_clarification_answer(
            session,
            _command(session, "I do not know"),
            FakeInterpreter(ClarificationAnswerInterpretation()),
            composer,
        )
    )

    assert transition.revision.status.value == "awaiting_answer"
    assert transition.revision.prompt is not None
    assert transition.revision.prompt.composition_source.value == "model"
    assert transition.revision.prompt.message.endswith("Question for return_or_duration?")
    next_input = composer.inputs[-1]
    assert [item.requirement_id for item in next_input.requirements] == ["return_or_duration"]
    assert [item.issue_id for item in next_input.issues] == ["return_or_duration:missing"]


def test_composer_failure_is_retryable_and_does_not_append_a_revision() -> None:
    session = start_clarification(
        _initial(), session_id="composition-failure", composer=FakeComposer()
    )
    receiver = FakeInterpreter(ClarificationAnswerInterpretation())

    pending = apply_clarification_answer(
        session,
        _command(session, "I do not know"),
        receiver,
        FakeComposer(error=RuntimeError("model unavailable")),
    )
    assert isinstance(pending, ClarificationCompositionPending)
    assert len(session.revisions) == 1
    assert session.current_revision.status.value == "awaiting_answer"
    completed = retry_prompt_composition(session, pending.pending, FakeComposer())
    assert not isinstance(completed, ClarificationCompositionPending)
    assert completed.revision.status.value == "awaiting_answer"
    assert len(receiver.inputs) == 1


def test_initial_composer_failure_is_explicit_and_retryable() -> None:
    with pytest.raises(
        ClarificationPromptCompositionFailedError,
        match="prompt_composition_failed",
    ) as error:
        start_clarification(
            _initial(),
            session_id="initial-composition-failure",
            composer=FakeComposer(error=RuntimeError("model unavailable")),
        )

    assert isinstance(error.value.__cause__, RuntimeError)
