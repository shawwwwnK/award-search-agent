"""Narrow, answer-only interpretation boundary for clarification sessions.

The initial request-understanding extractor deliberately cannot be reused for a
later answer: a clarification answer has its own message identity and only the
currently pending requirements are in scope.  This module defines that smaller
model-facing seam and validates all proposed evidence before a reducer sees it.
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import Field, model_validator

from award_agent.domain import (
    AmendmentTarget,
    BlockingRequirement,
    BlockingRequirementKind,
    MessageSpan,
    RejectedFragment,
    TypedAmendment,
)
from award_agent.domain.clarification_session import SessionContractModel


class ClarificationInterpretationError(ValueError):
    """A model-facing answer interpretation violates the continuation contract."""


class ClarificationAnswerInterpreterInput(SessionContractModel):
    """The intentionally minimal, model-facing clarification input.

    Calendar context deliberately remains outside this boundary.  The
    deterministic controller and temporal normalizer retain the original
    ``RequestContext`` for year selection and calendar evaluation.
    """

    message_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    requirements: tuple[BlockingRequirement, ...]

    @model_validator(mode="after")
    def validate_requirement_ids(self) -> ClarificationAnswerInterpreterInput:
        identifiers = [item.requirement_id for item in self.requirements]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("answer-interpreter requirements must have unique IDs")
        return self


class ClarificationAnswerInterpretation(SessionContractModel):
    """Typed, answer-grounded proposals; never a generic mutable patch."""

    amendments: tuple[TypedAmendment, ...] = ()
    rejected_fragments: tuple[RejectedFragment, ...] = ()

    @model_validator(mode="after")
    def validate_unique_amendment_ids(self) -> ClarificationAnswerInterpretation:
        identifiers = [item.amendment_id for item in self.amendments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("answer interpretation amendment IDs must be unique")
        return self


class ClarificationAnswerInterpreter(Protocol):
    """Model boundary for proposing typed clarification amendments."""

    def interpret(
        self,
        input: ClarificationAnswerInterpreterInput,
    ) -> ClarificationAnswerInterpretation: ...


_TARGET_REQUIREMENT_KIND = {
    AmendmentTarget.ORIGIN: BlockingRequirementKind.ORIGIN,
    AmendmentTarget.DESTINATION: BlockingRequirementKind.DESTINATION,
    AmendmentTarget.TRAVELERS: BlockingRequirementKind.TRAVELERS,
    AmendmentTarget.DEPARTURE: BlockingRequirementKind.DEPARTURE,
    AmendmentTarget.RETURN_OR_DURATION: BlockingRequirementKind.RETURN_OR_DURATION,
}
_CORRECTION_CUE = re.compile(
    r"\b(?:actually|instead|rather|change|update|move|make|correct)\b", re.IGNORECASE
)
_TRAVELER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def validate_message_span(
    *,
    message_id: str,
    text: str,
    span: MessageSpan,
) -> None:
    """Require an answer-local span to identify exactly one source substring."""

    if span.message_id != message_id:
        raise ClarificationInterpretationError(
            "answer span message ID does not match the interpreted answer"
        )
    if span.end > len(text) or text[span.start : span.end] != span.text:
        raise ClarificationInterpretationError(
            "answer span text does not equal answer text at its supplied offsets"
        )


def _validate_requirement_links(
    amendment: TypedAmendment,
    requirements: dict[str, BlockingRequirement],
) -> None:
    linked = []
    for requirement_id in amendment.requirement_ids:
        requirement = requirements.get(requirement_id)
        if requirement is None:
            raise ClarificationInterpretationError(
                f"amendment {amendment.amendment_id} links an inactive requirement"
            )
        linked.append(requirement)

    expected = _TARGET_REQUIREMENT_KIND.get(amendment.target)
    if amendment.target is AmendmentTarget.CONFLICTING_DATES:
        compatible = [item for item in linked if item.kind is BlockingRequirementKind.CONFLICT]
    else:
        compatible = [item for item in linked if item.kind is expected]
    if amendment.requirement_ids and len(compatible) != len(linked):
        raise ClarificationInterpretationError(
            f"amendment {amendment.amendment_id} links an incompatible requirement"
        )
    if not amendment.is_correction and not compatible:
        raise ClarificationInterpretationError(
            f"amendment {amendment.amendment_id} has no compatible active requirement"
        )
    if amendment.is_correction and _CORRECTION_CUE.search(amendment.span.text) is None:
        raise ClarificationInterpretationError(
            f"amendment {amendment.amendment_id} marks a correction without an explicit cue"
        )


def _validate_non_temporal_value(amendment: TypedAmendment) -> None:
    """Require literal answer support for values deterministic code can check."""

    source = amendment.span.text.casefold()
    if hasattr(amendment, "locations"):
        for location in amendment.locations:
            if location.raw_text.casefold() not in source:
                raise ClarificationInterpretationError(
                    f"location amendment {amendment.amendment_id} value is not grounded in its span"
                )
    if hasattr(amendment, "travelers"):
        stated = str(amendment.travelers) in source or any(
            value == amendment.travelers and re.search(rf"\b{word}\b", source)
            for word, value in _TRAVELER_WORDS.items()
        )
        if not stated:
            raise ClarificationInterpretationError(
                f"traveler amendment {amendment.amendment_id} value is not grounded in its span"
            )


def validate_answer_interpretation(
    input: ClarificationAnswerInterpreterInput,
    interpretation: ClarificationAnswerInterpretation,
) -> ClarificationAnswerInterpretation:
    """Validate model output against the exact answer and current prompt scope.

    This deliberately does not decide whether a correction replaces an already
    resolved effective field; that is reducer-owned state validation.  It does
    ensure the model can only *propose* a supported, explicitly cued correction.
    """

    requirements = {item.requirement_id: item for item in input.requirements}
    for amendment in interpretation.amendments:
        validate_message_span(message_id=input.message_id, text=input.text, span=amendment.span)
        _validate_requirement_links(amendment, requirements)
        _validate_non_temporal_value(amendment)
        if hasattr(amendment, "temporal_text") and amendment.temporal_text not in amendment.span.text:
            raise ClarificationInterpretationError(
                f"temporal amendment {amendment.amendment_id} text is not grounded in its span"
            )
    for fragment in interpretation.rejected_fragments:
        validate_message_span(message_id=input.message_id, text=input.text, span=fragment.span)
    return interpretation


def interpret_answer(
    interpreter: ClarificationAnswerInterpreter,
    input: ClarificationAnswerInterpreterInput,
) -> ClarificationAnswerInterpretation:
    """Call and validate the narrow interpreter boundary."""

    return validate_answer_interpretation(input, interpreter.interpret(input))


__all__ = [
    "ClarificationAnswerInterpretation",
    "ClarificationAnswerInterpreter",
    "ClarificationAnswerInterpreterInput",
    "ClarificationInterpretationError",
    "interpret_answer",
    "validate_answer_interpretation",
    "validate_message_span",
]
