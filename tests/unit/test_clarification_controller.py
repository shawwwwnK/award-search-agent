"""Core reducer tests for semantic clarification answers."""

from datetime import date

import pytest

from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import (
    ClarificationCompositionPending,
    ClarificationPromptCompositionFailedError,
    apply_clarification_answer,
    retry_prompt_composition,
    start_clarification,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationDiscourseAct,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import (
    SemanticOperation,
    SemanticTarget,
    TemporalAstKind,
    TemporalSemanticAst,
)
from award_agent.domain import (
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    DateWindow,
    DateWindowPrecision,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output, self.inputs = output, []

    def interpret(self, input: object) -> ClarificationAnswerInterpretation:
        self.inputs.append(input)
        return self.output


class FakeComposer:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error, self.inputs = error, []

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
        origins=[{"kind": "airport", "value": "SFO", "raw_text": "SFO"}],
        destinations=[{"kind": "country", "value": "England", "raw_text": "England"}],
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


def _command(session: object, text: str) -> ClarificationAnswerCommand:
    current = session.current_revision  # type: ignore[attr-defined]
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
    operation: SemanticOperation,
    temporal: TemporalSemanticAst,
    requirement_ids: tuple[str, ...] = (),
) -> ClarificationSemanticFact:
    start = text.index(quote)
    from award_agent.domain import MessageSpan

    return ClarificationSemanticFact(
        fact_id=identifier,
        span=MessageSpan(message_id="m1", start=start, end=start + len(quote), text=quote),
        operation=operation,
        target=target,
        requirement_ids=requirement_ids,
        temporal=temporal,
    )


def test_typo_correction_and_duration_are_independent_receiver_facts() -> None:
    session = start_clarification(_initial(), session_id="semantic", composer=FakeComposer())
    text = "Actually mid october for depature and the trip will be about 12 days"
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(
            facts=(
                _fact(
                    "departure",
                    text,
                    "Actually mid october for depature",
                    SemanticTarget.DEPARTURE_WINDOW,
                    SemanticOperation.REPLACE,
                    TemporalSemanticAst(
                        kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"
                    ),
                ),
                _fact(
                    "duration",
                    text,
                    "about 12 days",
                    SemanticTarget.DURATION,
                    SemanticOperation.SET,
                    TemporalSemanticAst(
                        kind=TemporalAstKind.DURATION, quantity=12, unit="day", approximate=True
                    ),
                    ("return_or_duration",),
                ),
            )
        )
    )
    transition = apply_clarification_answer(session, _command(session, text), receiver)
    effective = transition.revision.effective_request
    assert transition.revision.status.value == "ready"
    assert (effective.departure_window.start, effective.departure_window.end) == (
        date(2026, 10, 11),
        date(2026, 10, 20),
    )  # type: ignore[union-attr]
    assert (
        effective.interpreted_duration.minimum_days,
        effective.interpreted_duration.maximum_days,
    ) == (11, 13)  # type: ignore[union-attr]
    assert len(transition.revision.outcome.accepted_amendments) == 2  # type: ignore[union-attr]


def test_cancellation_is_receiver_classification_not_controller_text_parsing() -> None:
    session = start_clarification(_initial(), session_id="cancel", composer=FakeComposer())
    receiver = FakeInterpreter(
        ClarificationAnswerInterpretation(discourse_act=ClarificationDiscourseAct.CANCEL)
    )
    transition = apply_clarification_answer(session, _command(session, "whatever words"), receiver)
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
                    SemanticTarget.DURATION,
                    SemanticOperation.SET,
                    TemporalSemanticAst(
                        kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"
                    ),
                    ("return_or_duration",),
                ),
            )
        )
    )
    transition = apply_clarification_answer(
        session, _command(session, text), receiver, composer=FakeComposer()
    )
    assert transition.revision.status.value == "awaiting_answer"
    assert transition.revision.outcome is not None
    assert transition.revision.outcome.accepted_amendments == ()
    assert (
        transition.revision.outcome.rejected_fragments[0].reason_code == "receiver.semantic_compile"
    )


def test_composer_receives_authoritative_post_reduction_requirements_and_issues() -> None:
    composer = FakeComposer()
    session = start_clarification(_initial(), session_id="composed", composer=composer)
    initial_input = composer.inputs[-1]
    assert [item.requirement_id for item in initial_input.requirements] == ["return_or_duration"]
    assert [item.issue_id for item in initial_input.issues] == ["return_or_duration:missing"]

    transition = apply_clarification_answer(
        session,
        _command(session, "I do not know"),
        FakeInterpreter(ClarificationAnswerInterpretation()),
        composer,
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
