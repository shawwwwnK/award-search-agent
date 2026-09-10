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

from award_agent.clarification.temporal_approximations import (
    REGISTRY_VERSION as APPROXIMATION_REGISTRY_VERSION,
)
from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationBinding,
    ClarificationTemporalApproximationProjection,
    ClarificationTemporalApproximationSelection,
    ClarificationTemporalApproximationUnresolved,
    approximation_selectable_surface,
    legacy_unresolved_surface,
    validate_temporal_approximation_selection,
)
from award_agent.clarification.temporal_templates import (
    REGISTRY_VERSION,
    ClarificationTemporalTemplateBinding,
    ClarificationTemporalTemplateProjection,
    ClarificationTemporalTemplateSelection,
    ClarificationTemporalTemplateUnresolved,
    template_selectable_surface,
    validate_temporal_template_selection,
)
from award_agent.domain import (
    AmendmentTarget,
    BlockingRequirement,
    BlockingRequirementKind,
    MessageSpan,
    RejectedFragment,
    RejectedFragmentReason,
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
    temporal_template_projection: ClarificationTemporalTemplateProjection = Field(
        default_factory=lambda: ClarificationTemporalTemplateProjection(
            registry_version=REGISTRY_VERSION,
            choices=(),
        )
    )
    temporal_approximation_projection: ClarificationTemporalApproximationProjection = Field(
        default_factory=lambda: ClarificationTemporalApproximationProjection(
            registry_version=APPROXIMATION_REGISTRY_VERSION,
            choices=(),
        )
    )

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
    # A receiver may also supply the next prompt while it interprets this
    # answer.  The controller only presents these items after reduction when
    # their IDs exactly equal the authoritative remaining blockers.  They
    # therefore save a round trip without granting the receiver state
    # authority.  ``next_question`` is retained only to read older records.
    next_question: str | None = Field(default=None, min_length=1, max_length=500)
    next_question_requirement_ids: tuple[str, ...] = ()
    next_question_items: tuple[str, ...] = ()
    temporal_template_selection: ClarificationTemporalTemplateSelection = Field(
        default_factory=lambda: ClarificationTemporalTemplateSelection(complete=True)
    )
    temporal_approximation_selection: ClarificationTemporalApproximationSelection = Field(
        default_factory=lambda: ClarificationTemporalApproximationSelection(complete=True)
    )

    @model_validator(mode="after")
    def validate_unique_amendment_ids(self) -> ClarificationAnswerInterpretation:
        identifiers = [item.amendment_id for item in self.amendments]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("answer interpretation amendment IDs must be unique")
        question_ids = self.next_question_requirement_ids
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("next-question requirement IDs must be unique")
        if self.next_question is None and question_ids and not self.next_question_items:
            raise ValueError("next-question requirement IDs require question items")
        if self.next_question_items and len(self.next_question_items) != len(question_ids):
            raise ValueError("next-question items must match requirement IDs")
        if self.next_question is not None and self.next_question_items:
            raise ValueError("use either legacy next_question or next_question_items")
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
_SINGULAR_TRAVELER_ALIASES = re.compile(
    r"\b(?:just|only)\s+(?:myself|me)\b|\bby\s+myself\b|\bsolo\b",
    re.IGNORECASE,
)
_DISCRETE_TEMPORAL_DISJUNCTION = re.compile(r"\b(?:or|either)\b", re.IGNORECASE)


def _overlaps(left: MessageSpan, right: MessageSpan) -> bool:
    return left.start < right.end and right.start < left.end


def _line(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    return text[line_start:] if line_end < 0 else text[line_start:line_end]


def _discrete_line_span(text: str, span: MessageSpan) -> MessageSpan:
    """Use the complete answer line so every alternative stays unresolved."""

    start = text.rfind("\n", 0, span.start) + 1
    end = text.find("\n", span.end)
    end = len(text) if end < 0 else end
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return MessageSpan(message_id=span.message_id, start=start, end=end, text=text[start:end])


def _active_temporal_requirement_ids(
    requirements: tuple[BlockingRequirement, ...],
) -> tuple[str, ...]:
    return tuple(
        requirement.requirement_id
        for requirement in requirements
        if requirement.kind
        in {
            BlockingRequirementKind.DEPARTURE,
            BlockingRequirementKind.RETURN_OR_DURATION,
        }
    )


def _normalize_temporal_registry_classifications(
    input: ClarificationAnswerInterpreterInput,
    interpretation: ClarificationAnswerInterpretation,
) -> ClarificationAnswerInterpretation:
    """Repair conservative registry-routing mistakes before validation.

    The answer model can recognize a temporal phrase while selecting the
    sibling registry's unresolved bucket.  Unresolved records have no
    semantics, so lexical rehoming preserves their evidence, links, and closed
    reason without broadening what either registry may accept. A positive
    selection in a discrete alternative is downgraded before compilation;
    rejecting the whole answer would make a reasonable partial answer block.
    """

    temporal_ids = _active_temporal_requirement_ids(input.requirements)
    template_selected: list[ClarificationTemporalTemplateBinding] = []
    template_unresolved = list(interpretation.temporal_template_selection.unresolved)
    approximation_selected: list[ClarificationTemporalApproximationBinding] = []
    approximation_unresolved = list(interpretation.temporal_approximation_selection.unresolved)

    template_downgraded: dict[tuple[int, int], MessageSpan] = {}
    for template_binding in interpretation.temporal_template_selection.selected:
        if _DISCRETE_TEMPORAL_DISJUNCTION.search(_line(input.text, template_binding.span.start)):
            line_span = _discrete_line_span(input.text, template_binding.span)
            template_downgraded[(line_span.start, line_span.end)] = line_span
        else:
            template_selected.append(template_binding)
    approximation_downgraded: dict[tuple[int, int], MessageSpan] = {}
    for approximation_binding in interpretation.temporal_approximation_selection.selected:
        if _DISCRETE_TEMPORAL_DISJUNCTION.search(_line(input.text, approximation_binding.span.start)):
            line_span = _discrete_line_span(input.text, approximation_binding.span)
            approximation_downgraded[(line_span.start, line_span.end)] = line_span
        else:
            approximation_selected.append(approximation_binding)

    # A line can contain several selected alternatives. Collapse every one
    # into a single answer-local ambiguity and union any existing unresolved
    # ownership from that same line before reconstructing frozen contracts.
    for line_span in template_downgraded.values():
        template_overlapping = [item for item in template_unresolved if _overlaps(item.span, line_span)]
        template_unresolved = [item for item in template_unresolved if item not in template_overlapping]
        template_unresolved.append(
            ClarificationTemporalTemplateUnresolved(
                span=line_span,
                requirement_ids=tuple(
                    requirement_id
                    for requirement_id in temporal_ids
                    if requirement_id
                    in set(temporal_ids).union(
                        *(set(item.requirement_ids) for item in template_overlapping)
                    )
                ),
                reason="ambiguous",
            )
        )
    for line_span in approximation_downgraded.values():
        approximation_overlapping = [
            item for item in approximation_unresolved if _overlaps(item.span, line_span)
        ]
        approximation_unresolved = [
            item for item in approximation_unresolved if item not in approximation_overlapping
        ]
        approximation_unresolved.append(
            ClarificationTemporalApproximationUnresolved(
                span=line_span,
                requirement_ids=tuple(
                    requirement_id
                    for requirement_id in temporal_ids
                    if requirement_id
                    in set(temporal_ids).union(
                        *(set(item.requirement_ids) for item in approximation_overlapping)
                    )
                ),
                reason="ambiguous",
            )
        )

    # Rehome only if the sibling has no competing classification over that
    # evidence. This keeps an existing selected interpretation authoritative.
    retained_template: list[ClarificationTemporalTemplateUnresolved] = []
    for template_unresolved_item in template_unresolved:
        sibling_spans = [item.span for item in approximation_selected + approximation_unresolved]
        if (
            approximation_selectable_surface(template_unresolved_item.span.text)
            and not template_selectable_surface(template_unresolved_item.span.text)
            and not any(_overlaps(template_unresolved_item.span, span) for span in sibling_spans)
        ):
            approximation_unresolved.append(
                ClarificationTemporalApproximationUnresolved(
                    span=template_unresolved_item.span,
                    requirement_ids=template_unresolved_item.requirement_ids,
                    reason=template_unresolved_item.reason,
                )
            )
        else:
            retained_template.append(template_unresolved_item)

    retained_approximation: list[ClarificationTemporalApproximationUnresolved] = []
    for approximation_unresolved_item in approximation_unresolved:
        sibling_spans = [item.span for item in template_selected + retained_template]
        if (
            template_selectable_surface(approximation_unresolved_item.span.text)
            and not approximation_selectable_surface(approximation_unresolved_item.span.text)
            and not any(_overlaps(approximation_unresolved_item.span, span) for span in sibling_spans)
        ):
            retained_template.append(
                ClarificationTemporalTemplateUnresolved(
                    span=approximation_unresolved_item.span,
                    requirement_ids=approximation_unresolved_item.requirement_ids,
                    reason=approximation_unresolved_item.reason,
                )
            )
        else:
            retained_approximation.append(approximation_unresolved_item)

    # Legacy months and bounded exact-date forms are meaningful user input but
    # have no approved positive affordance in either registry. Route an
    # unresolved record through the ordinary generic rejection channel rather
    # than inventing a selection or scanning it as an accepting approximation.
    generic_rejections = list(interpretation.rejected_fragments)

    def route_legacy_surface(
        unresolved: ClarificationTemporalTemplateUnresolved
        | ClarificationTemporalApproximationUnresolved,
    ) -> bool:
        if not legacy_unresolved_surface(unresolved.span.text):
            return False
        generic_rejections.append(
            RejectedFragment(
                span=unresolved.span,
                reason=(
                    RejectedFragmentReason.AMBIGUOUS
                    if unresolved.reason == "ambiguous"
                    else RejectedFragmentReason.INVALID
                ),
                detail="legacy temporal wording needs clarification",
                requirement_ids=unresolved.requirement_ids,
                reason_code=f"clarification-temporal-generic-v1.unresolved.{unresolved.reason}",
            )
        )
        return True

    retained_template = [
        item for item in retained_template if not route_legacy_surface(item)
    ]
    retained_approximation = [
        item for item in retained_approximation if not route_legacy_surface(item)
    ]

    return interpretation.model_copy(
        update={
            "temporal_template_selection": ClarificationTemporalTemplateSelection(
                selected=tuple(template_selected),
                unresolved=tuple(retained_template),
                complete=interpretation.temporal_template_selection.complete,
            ),
            "temporal_approximation_selection": ClarificationTemporalApproximationSelection(
                selected=tuple(approximation_selected),
                unresolved=tuple(retained_approximation),
                complete=interpretation.temporal_approximation_selection.complete,
            ),
            "rejected_fragments": tuple(generic_rejections),
        }
    )


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
        # A bare temporal answer can itself be the ambiguity between active
        # departure and return slots; retain it for deterministic normalization
        # rather than turning a conservative model classification into a
        # transport-shaped interpreter error.
        compatible = [
            item
            for item in linked
            if item.kind in {
                BlockingRequirementKind.CONFLICT,
                BlockingRequirementKind.DEPARTURE,
                BlockingRequirementKind.RETURN_OR_DURATION,
            }
        ]
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
        stated = (
            str(amendment.travelers) in source
            or any(
                value == amendment.travelers and re.search(rf"\b{word}\b", source)
                for word, value in _TRAVELER_WORDS.items()
            )
            or (amendment.travelers == 1 and _SINGULAR_TRAVELER_ALIASES.search(source) is not None)
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

    interpretation = _normalize_temporal_registry_classifications(input, interpretation)
    requirements = {item.requirement_id: item for item in input.requirements}
    for amendment in interpretation.amendments:
        validate_message_span(message_id=input.message_id, text=input.text, span=amendment.span)
        _validate_requirement_links(amendment, requirements)
        _validate_non_temporal_value(amendment)
        if (
            hasattr(amendment, "temporal_text")
            and amendment.temporal_text not in amendment.span.text
        ):
            raise ClarificationInterpretationError(
                f"temporal amendment {amendment.amendment_id} text is not grounded in its span"
            )
    for fragment in interpretation.rejected_fragments:
        validate_message_span(message_id=input.message_id, text=input.text, span=fragment.span)
        if not set(fragment.requirement_ids).issubset(requirements):
            raise ClarificationInterpretationError("rejected fragment links an inactive requirement")
    for binding in interpretation.temporal_template_selection.selected:
        validate_message_span(message_id=input.message_id, text=input.text, span=binding.span)
    for unresolved in interpretation.temporal_template_selection.unresolved:
        validate_message_span(message_id=input.message_id, text=input.text, span=unresolved.span)
    for approximation_binding in interpretation.temporal_approximation_selection.selected:
        validate_message_span(
            message_id=input.message_id, text=input.text, span=approximation_binding.span
        )
    for approximation_unresolved in interpretation.temporal_approximation_selection.unresolved:
        validate_message_span(
            message_id=input.message_id, text=input.text, span=approximation_unresolved.span
        )
    # The receiver can propose follow-up copy, but can only name requirements
    # that were active for this answer.  The controller later checks exact
    # equality against the recomputed blocker set before it renders anything.
    unknown_next_question_ids = set(interpretation.next_question_requirement_ids) - set(
        requirements
    )
    if unknown_next_question_ids:
        raise ClarificationInterpretationError("next question links an inactive requirement")
    # Every harvested registry group is an explicit model-classification task.
    # Defaults are valid only for an empty projection; omitting the field must
    # never silently bypass a non-empty candidate catalog.
    try:
        validate_temporal_template_selection(
            input.temporal_template_projection,
            interpretation.temporal_template_selection,
            text=input.text,
            requirements=input.requirements,
            additional_classified_spans=tuple(
                item.span
                for item in (
                    interpretation.temporal_approximation_selection.selected
                    + interpretation.temporal_approximation_selection.unresolved
                    + interpretation.rejected_fragments
                )
            ),
        )
    except ValueError as exc:
        raise ClarificationInterpretationError("invalid temporal template selection") from exc
    try:
        validate_temporal_approximation_selection(
            input.temporal_approximation_projection,
            interpretation.temporal_approximation_selection,
            text=input.text,
            requirements=input.requirements,
            additional_classified_spans=tuple(
                item.span
                for item in (
                    interpretation.temporal_template_selection.selected
                    + interpretation.temporal_template_selection.unresolved
                    + interpretation.rejected_fragments
                )
            ),
            require_coverage=True,
        )
    except ValueError as exc:
        raise ClarificationInterpretationError("invalid temporal approximation selection") from exc
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
