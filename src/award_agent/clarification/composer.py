"""Least-authority post-reduction prompt-composition boundary (ADR 0012)."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field, model_validator

from award_agent.domain import BlockingRequirement, ClarificationIssue
from award_agent.domain.clarification_session import SessionContractModel


class ClarificationCompositionError(ValueError):
    """A composer result cannot safely present the canonical prompt policy."""


class ClarificationPromptComposerInput(SessionContractModel):
    """Only active requirements and post-reduction issues cross this boundary."""

    requirements: tuple[BlockingRequirement, ...]
    issues: tuple[ClarificationIssue, ...]

    @model_validator(mode="after")
    def validate_issue_coverage(self) -> ClarificationPromptComposerInput:
        requirement_ids = [item.requirement_id for item in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("composer requirements must have unique IDs")
        if {item.requirement_id for item in self.issues} != set(requirement_ids):
            raise ValueError("composer issues must exactly cover active requirements")
        return self


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
    issue_ids_by_requirement: dict[str, set[str]] = {}
    for issue in input.issues:
        issue_ids_by_requirement.setdefault(issue.requirement_id, set()).add(issue.issue_id)
    for item in composition.question_items:
        if set(item.issue_ids) != issue_ids_by_requirement[item.requirement_id]:
            raise ClarificationCompositionError(
                "composer question items must exactly cover their requirement issues"
            )
    return composition


def compose_prompt(
    composer: ClarificationPromptComposer,
    input: ClarificationPromptComposerInput,
) -> ClarificationPromptComposition:
    return validate_prompt_composition(input, composer.compose(input))


__all__ = [
    "ClarificationCompositionError",
    "ClarificationPromptComposer",
    "ClarificationPromptComposerInput",
    "ClarificationPromptComposition",
    "ClarificationQuestionItem",
    "compose_prompt",
    "validate_prompt_composition",
]
