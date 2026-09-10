"""Least-authority post-reduction prompt-composition boundary (ADR 0014).

The composer is deliberately a presentation-only model boundary.  The
controller supplies the deterministic, post-reduction blocker set and the
canonical issue records; the composer supplies customer-facing question copy
only.  In particular, this module has no session, effective-request, or
calendar input and contains no natural-language fallback renderer.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field, model_validator

from award_agent.domain import BlockingRequirement, ClarificationIssue
from award_agent.domain.clarification_session import SessionContractModel


class ClarificationCompositionError(ValueError):
    """A composer result cannot safely present the canonical prompt policy."""


class ClarificationPromptComposerInput(SessionContractModel):
    """Only active requirements and post-reduction issues cross this boundary.

    The domain models are retained here so the controller can pass the
    authoritative records without copying them into a second contract.  The
    OpenAI adapter uses :meth:`model_input` to project those records to a
    smaller model-facing payload, excluding offsets, message IDs, reason
    codes, and any future fields added to the session ledger.
    """

    requirements: tuple[BlockingRequirement, ...]
    issues: tuple[ClarificationIssue, ...]

    @model_validator(mode="after")
    def validate_issue_coverage(self) -> ClarificationPromptComposerInput:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("composer requirements must have unique IDs")
        issue_ids = [item.issue_id for item in self.issues]
        if len(issue_ids) != len(set(issue_ids)):
            raise ValueError("composer issues must have unique IDs")
        requirement_id_set = set(requirement_ids)
        if any(item.requirement_id not in requirement_id_set for item in self.issues):
            raise ValueError("composer issues must link active requirements")
        if {item.requirement_id for item in self.issues} != requirement_id_set:
            raise ValueError("composer issues must exactly cover active requirements")
        return self

    def model_input(self) -> dict[str, list[dict[str, Any]]]:
        """Return the least-authority payload intended for a composer model.

        ``BlockingRequirement`` and ``ClarificationIssue`` are session-domain
        contracts, so serializing them wholesale would accidentally expose
        implementation details such as conflict codes, provenance offsets, or
        message IDs.  The model needs only stable linkage, blocker kind, a
        safe deterministic explanation, and optional answer phrase text for a
        targeted question.
        """

        return {
            "requirements": [
                {
                    "requirement_id": requirement.requirement_id,
                    "kind": requirement.kind.value,
                }
                for requirement in self.requirements
            ],
            "issues": [
                {
                    "issue_id": issue.issue_id,
                    "requirement_id": issue.requirement_id,
                    "kind": issue.kind.value,
                    "reason": issue.reason,
                    "span": {"text": issue.span.text} if issue.span is not None else None,
                }
                for issue in self.issues
            ],
        }


class ClarificationQuestionItem(SessionContractModel):
    requirement_id: str = Field(min_length=1)
    issue_ids: tuple[str, ...] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_issue_ids(self) -> ClarificationQuestionItem:
        if len(self.issue_ids) != len(set(self.issue_ids)):
            raise ValueError("question issue IDs must be unique")
        if any(ord(character) < 32 and character not in "\n\t" for character in self.question):
            raise ValueError("question contains a control character")
        return self


class ClarificationPromptComposition(SessionContractModel):
    question_items: tuple[ClarificationQuestionItem, ...]


class ClarificationPromptComposer(Protocol):
    def compose(
        self, input: ClarificationPromptComposerInput
    ) -> ClarificationPromptComposition: ...


def validate_prompt_composition(
    input: ClarificationPromptComposerInput,
    composition: ClarificationPromptComposition,
) -> ClarificationPromptComposition:
    """Require exact canonical ordering and complete issue linkage."""

    expected_requirements = tuple(item.requirement_id for item in input.requirements)
    actual_requirements = tuple(item.requirement_id for item in composition.question_items)
    if actual_requirements != expected_requirements:
        raise ClarificationCompositionError(
            "composer question items must exactly match active requirements in canonical order"
        )
    issue_ids_by_requirement: dict[str, tuple[str, ...]] = {}
    for issue in input.issues:
        issue_ids_by_requirement[issue.requirement_id] = (
            *issue_ids_by_requirement.get(issue.requirement_id, ()),
            issue.issue_id,
        )
    for item in composition.question_items:
        if item.issue_ids != issue_ids_by_requirement[item.requirement_id]:
            raise ClarificationCompositionError(
                "composer question items must exactly cover their requirement issues"
            )
    return composition


def compose_prompt(
    composer: ClarificationPromptComposer,
    input: ClarificationPromptComposerInput,
) -> ClarificationPromptComposition:
    composition = composer.compose(input)
    if not isinstance(composition, ClarificationPromptComposition):
        raise ClarificationCompositionError(
            "composer must return a ClarificationPromptComposition"
        )
    return validate_prompt_composition(input, composition)


__all__ = [
    "ClarificationCompositionError",
    "ClarificationPromptComposer",
    "ClarificationPromptComposerInput",
    "ClarificationPromptComposition",
    "ClarificationQuestionItem",
    "compose_prompt",
    "validate_prompt_composition",
]
