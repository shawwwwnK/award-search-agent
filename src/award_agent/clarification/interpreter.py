"""Least-authority semantic receiver boundary for clarification answers.

Natural-language interpretation belongs exclusively to the receiver. Local
code validates closed, grounded semantic facts; it does not recover meaning
from answer text.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from award_agent.clarification.calendar_plan import (
    CALENDAR_PLAN_VERSION,
    CalendarCalculationOperation,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import BlockingRequirement, LocationKind, MessageSpan
from award_agent.domain.clarification_session import SessionContractModel

CALENDAR_PROPOSAL_CONTRACT_VERSION = CALENDAR_PLAN_VERSION


class ClarificationInterpretationError(ValueError):
    """A model-facing interpretation violates the receiver contract."""


class ClarificationDiscourseAct(str, Enum):
    ANSWER = "answer"
    CANCEL = "cancel"
    DECLINE = "decline"
    NON_ANSWER = "non_answer"


class ClarificationAnswerInterpreterInput(SessionContractModel):
    """Only answer-local data and authority necessary for semantic extraction."""

    message_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    ordered_requirements: tuple[BlockingRequirement, ...]
    correction_eligible_targets: tuple[SemanticTarget, ...] = ()
    calendar_proposal_contract_version: str = CALENDAR_PROPOSAL_CONTRACT_VERSION

    @model_validator(mode="after")
    def valid_scope(self) -> ClarificationAnswerInterpreterInput:
        identifiers = [item.requirement_id for item in self.ordered_requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("receiver requirements must have unique IDs")
        if len(self.correction_eligible_targets) != len(set(self.correction_eligible_targets)):
            raise ValueError("receiver correction-eligible targets must be unique")
        if self.calendar_proposal_contract_version != CALENDAR_PROPOSAL_CONTRACT_VERSION:
            raise ValueError("unsupported calendar proposal contract version")
        return self

    @property
    def requirements(self) -> tuple[BlockingRequirement, ...]:
        return self.ordered_requirements


class ClarificationSemanticFact(SessionContractModel):
    """A receiver-owned, grounded semantic fact.

    This is deliberately not an amendment.  In particular, a receiver cannot
    choose whether it is a set or correction, or attach itself to an active
    blocker.  Those are authority decisions made from the current session
    state after the model has supplied only its semantic target and value.
    """

    fact_id: str = Field(min_length=1)
    span: MessageSpan
    target: SemanticTarget
    location_kind: LocationKind | None = None
    location_value: str | None = None
    travelers: int | None = Field(default=None, ge=1)
    calendar_operation: CalendarCalculationOperation | None = None

    @model_validator(mode="after")
    def closed_value_shape(self) -> ClarificationSemanticFact:
        if self.target in {SemanticTarget.ORIGIN, SemanticTarget.DESTINATION}:
            valid = self.location_kind is not None and bool(self.location_value)
            invalid = self.travelers is not None or self.calendar_operation is not None
        elif self.target is SemanticTarget.TRAVELERS:
            valid = self.travelers is not None
            invalid = any(
                value is not None
                for value in (self.location_kind, self.location_value, self.calendar_operation)
            )
        else:
            valid = self.calendar_operation is not None
            invalid = any(
                value is not None
                for value in (self.location_kind, self.location_value, self.travelers)
            )
        if not valid or invalid:
            raise ValueError("semantic fact has an invalid typed value shape")
        return self


class ClarificationUnresolvedFragment(SessionContractModel):
    span: MessageSpan
    target: SemanticTarget | None = None
    reason: str = Field(min_length=1, max_length=80)


class ClarificationAnswerInterpretation(SessionContractModel):
    discourse_act: ClarificationDiscourseAct = ClarificationDiscourseAct.ANSWER
    facts: tuple[ClarificationSemanticFact, ...] = ()
    unresolved_fragments: tuple[ClarificationUnresolvedFragment, ...] = ()

    @model_validator(mode="after")
    def unique_fact_ids(self) -> ClarificationAnswerInterpretation:
        identifiers = [item.fact_id for item in self.facts]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("semantic fact IDs must be unique")
        if self.discourse_act is not ClarificationDiscourseAct.ANSWER and self.facts:
            raise ValueError("non-answer discourse acts cannot carry facts")
        targets = [item.target for item in self.facts]
        allowed_pair = {SemanticTarget.RETURN_WINDOW, SemanticTarget.DURATION}
        if any(targets.count(target) > 1 for target in set(targets)) or (
            len([target for target in targets if target in allowed_pair]) > 2
        ):
            raise ValueError("semantic facts cannot write a target more than once")
        return self


class ClarificationInterpretationUnavailable(SessionContractModel):
    """A retryable receiver outcome that is safe to show as a pending state.

    This prevents a reasonable user response from becoming a user-visible
    schema exception when the model cannot provide usable semantics after its
    one bounded repair attempt.
    """

    code: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=500)
    repair_attempted: bool = False


class ClarificationCalendarProposalIssue(SessionContractModel):
    """Typed deterministic feedback for one model-owned calendar repair."""

    fact_id: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=120)
    path: tuple[str, ...] = Field(min_length=1)
    detail: str = Field(min_length=1, max_length=500)


class ClarificationAnswerInterpreter(Protocol):
    def interpret(
        self, input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable: ...


class ClarificationCalendarProposalRepairer(Protocol):
    """Optional extension used once when typed calendar evaluation rejects facts."""

    def repair_calendar_proposals(
        self,
        input: ClarificationAnswerInterpreterInput,
        *,
        facts: tuple[ClarificationSemanticFact, ...],
        issues: tuple[ClarificationCalendarProposalIssue, ...],
    ) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable: ...


@runtime_checkable
class ClarificationRepairBudget(Protocol):
    """Optional, narrow per-turn repair-budget observation capability.

    A receiver that spends its repair attempt before the controller sees a
    calendar failure exposes this boolean.  Interpreters without repair support
    deliberately need not implement it; the controller remains compatible
    with deterministic fakes and treats their missing repair capability as a
    retryable pending outcome only if a repair is actually needed.
    """

    def repair_budget_consumed(self) -> bool: ...


def validate_message_span(*, message_id: str, text: str, span: MessageSpan) -> None:
    if span.message_id != message_id:
        raise ClarificationInterpretationError(
            "answer span message ID does not match the interpreted answer"
        )
    if span.end > len(text) or text[span.start : span.end] != span.text:
        raise ClarificationInterpretationError(
            "answer span text does not equal answer text at its supplied offsets"
        )


def validate_answer_interpretation(
    input: ClarificationAnswerInterpreterInput,
    interpretation: ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable,
) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable:
    """Validate grounding and authority only; never inspect words for meaning."""
    if isinstance(interpretation, ClarificationInterpretationUnavailable):
        return interpretation
    for fact in interpretation.facts:
        validate_message_span(message_id=input.message_id, text=input.text, span=fact.span)
    for fragment in interpretation.unresolved_fragments:
        validate_message_span(message_id=input.message_id, text=input.text, span=fragment.span)
    return interpretation


def interpret_answer(
    interpreter: ClarificationAnswerInterpreter, input: ClarificationAnswerInterpreterInput
) -> ClarificationAnswerInterpretation | ClarificationInterpretationUnavailable:
    return validate_answer_interpretation(input, interpreter.interpret(input))


__all__ = [
    "CALENDAR_PROPOSAL_CONTRACT_VERSION",
    "ClarificationAnswerInterpretation",
    "ClarificationAnswerInterpreter",
    "ClarificationAnswerInterpreterInput",
    "ClarificationCalendarProposalIssue",
    "ClarificationCalendarProposalRepairer",
    "ClarificationDiscourseAct",
    "ClarificationInterpretationError",
    "ClarificationInterpretationUnavailable",
    "ClarificationRepairBudget",
    "ClarificationSemanticFact",
    "ClarificationUnresolvedFragment",
    "interpret_answer",
    "validate_answer_interpretation",
    "validate_message_span",
]
