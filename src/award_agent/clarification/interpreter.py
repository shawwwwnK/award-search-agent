"""Least-authority semantic receiver boundary for clarification answers.

Natural-language interpretation belongs exclusively to the receiver. Local
code validates closed, grounded semantic facts; it does not recover meaning
from answer text.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import Field, model_validator

from award_agent.clarification.semantic import (
    SemanticTarget,
    TemporalSemanticAst,
)
from award_agent.domain import BlockingRequirement, LocationKind, MessageSpan
from award_agent.domain.clarification_session import SessionContractModel

TEMPORAL_AFFORDANCE_CATALOG_VERSION = "clarification-semantic-temporal-v1"


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
    temporal_affordance_catalog_version: str = TEMPORAL_AFFORDANCE_CATALOG_VERSION

    @model_validator(mode="after")
    def valid_scope(self) -> ClarificationAnswerInterpreterInput:
        identifiers = [item.requirement_id for item in self.ordered_requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("receiver requirements must have unique IDs")
        if len(self.correction_eligible_targets) != len(set(self.correction_eligible_targets)):
            raise ValueError("receiver correction-eligible targets must be unique")
        if self.temporal_affordance_catalog_version != TEMPORAL_AFFORDANCE_CATALOG_VERSION:
            raise ValueError("unsupported temporal affordance catalog version")
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
    temporal: TemporalSemanticAst | None = None

    @model_validator(mode="after")
    def closed_value_shape(self) -> ClarificationSemanticFact:
        if self.target in {SemanticTarget.ORIGIN, SemanticTarget.DESTINATION}:
            valid = self.location_kind is not None and bool(self.location_value)
            invalid = self.travelers is not None or self.temporal is not None
        elif self.target is SemanticTarget.TRAVELERS:
            valid = self.travelers is not None
            invalid = any(
                value is not None
                for value in (self.location_kind, self.location_value, self.temporal)
            )
        else:
            valid = self.temporal is not None
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


class ClarificationAnswerInterpreter(Protocol):
    def interpret(
        self, input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation: ...


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
    input: ClarificationAnswerInterpreterInput, interpretation: ClarificationAnswerInterpretation
) -> ClarificationAnswerInterpretation:
    """Validate grounding and authority only; never inspect words for meaning."""
    for fact in interpretation.facts:
        validate_message_span(message_id=input.message_id, text=input.text, span=fact.span)
    for fragment in interpretation.unresolved_fragments:
        validate_message_span(message_id=input.message_id, text=input.text, span=fragment.span)
    return interpretation


def interpret_answer(
    interpreter: ClarificationAnswerInterpreter, input: ClarificationAnswerInterpreterInput
) -> ClarificationAnswerInterpretation:
    return validate_answer_interpretation(input, interpreter.interpret(input))


__all__ = [
    "TEMPORAL_AFFORDANCE_CATALOG_VERSION",
    "ClarificationAnswerInterpretation",
    "ClarificationAnswerInterpreter",
    "ClarificationAnswerInterpreterInput",
    "ClarificationDiscourseAct",
    "ClarificationInterpretationError",
    "ClarificationSemanticFact",
    "ClarificationUnresolvedFragment",
    "interpret_answer",
    "validate_answer_interpretation",
    "validate_message_span",
]
