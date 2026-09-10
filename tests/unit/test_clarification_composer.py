"""ADR 0012 post-reduction issue and prompt-composition tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from award_agent.clarification.composer import (
    ClarificationCompositionError,
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
    validate_prompt_composition,
)
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.openai_composer import (
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
    _ClarificationPromptComposerWireOutput,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    EffectiveField,
    MessageSpan,
    RejectedFragment,
    RejectedFragmentReason,
)


def _requirements() -> tuple[BlockingRequirement, ...]:
    return (
        BlockingRequirement(
            requirement_id="departure",
            kind=BlockingRequirementKind.DEPARTURE,
            field=EffectiveField.DEPARTURE,
        ),
        BlockingRequirement(
            requirement_id="travelers",
            kind=BlockingRequirementKind.TRAVELERS,
            field=EffectiveField.TRAVELERS,
        ),
    )


def test_issues_keep_answer_local_rejection_on_its_remaining_requirement() -> None:
    rejected = RejectedFragment(
        span=MessageSpan(message_id="answer-1", start=0, end=13, text="early October"),
        reason=RejectedFragmentReason.AMBIGUOUS,
        detail="needs a range",
        requirement_ids=("departure",),
        reason_code="temporal.fuzzy_choice",
    )

    issues = derive_clarification_issues(_requirements(), rejected_fragments=(rejected,))

    assert [(issue.requirement_id, issue.kind.value, issue.reason_code) for issue in issues] == [
        ("departure", "ambiguous", "temporal.fuzzy_choice"),
        ("travelers", "missing", "state.missing"),
    ]
    assert issues[0].span == rejected.span


def test_initial_missing_and_conflict_issues_have_no_answer_spans() -> None:
    requirements = (
        BlockingRequirement(
            requirement_id="conflict:dates",
            kind=BlockingRequirementKind.CONFLICT,
            conflict_code="dates",
        ),
        BlockingRequirement(
            requirement_id="departure",
            kind=BlockingRequirementKind.DEPARTURE,
            field=EffectiveField.DEPARTURE,
        ),
    )

    issues = derive_clarification_issues(requirements)

    assert [(item.kind.value, item.span, item.reason_code) for item in issues] == [
        ("conflict", None, "state.conflict"),
        ("missing", None, "state.missing"),
    ]


def test_conflict_linked_rejection_remains_a_conflict_issue_with_its_span() -> None:
    requirement = BlockingRequirement(
        requirement_id="conflict:dates",
        kind=BlockingRequirementKind.CONFLICT,
        conflict_code="dates",
    )
    fragment = RejectedFragment(
        span=MessageSpan(message_id="answer-1", start=0, end=6, text="Friday"),
        reason=RejectedFragmentReason.AMBIGUOUS,
        detail="ambiguous date",
        requirement_ids=("conflict:dates",),
        reason_code="registry.unresolved.ambiguous",
    )

    issue = derive_clarification_issues((requirement,), rejected_fragments=(fragment,))[0]

    assert issue.kind.value == "conflict"
    assert issue.span == fragment.span
    assert issue.reason_code == "registry.unresolved.ambiguous"


def test_composer_requires_exact_requirement_order_and_issue_coverage() -> None:
    input = ClarificationPromptComposerInput(
        requirements=_requirements(), issues=derive_clarification_issues(_requirements())
    )
    bad = ClarificationPromptComposition(
        question_items=(
            ClarificationQuestionItem(
                requirement_id="travelers",
                issue_ids=("travelers:missing",),
                question="How many people?",
            ),
            ClarificationQuestionItem(
                requirement_id="departure",
                issue_ids=("departure:missing",),
                question="When do you leave?",
            ),
        )
    )

    with pytest.raises(ClarificationCompositionError, match="canonical order"):
        validate_prompt_composition(input, bad)


class _Responses:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.output, usage=None)


class _Client:
    def __init__(self, output: object) -> None:
        self.responses = _Responses(output)


def test_openai_composer_receives_only_requirements_and_issues() -> None:
    requirements = _requirements()
    input = ClarificationPromptComposerInput(
        requirements=requirements, issues=derive_clarification_issues(requirements)
    )
    wire = _ClarificationPromptComposerWireOutput.model_validate(
        {
            "question_items": [
                {
                    "requirement_id": "departure",
                    "issue_ids": ["departure:missing"],
                    "question": "When would you like to leave?",
                },
                {
                    "requirement_id": "travelers",
                    "issue_ids": ["travelers:missing"],
                    "question": "How many people will be traveling?",
                },
            ]
        }
    )
    client = _Client(wire)
    composer = OpenAIClarificationPromptComposer(
        OpenAIClarificationComposerConfig(model="model"), client=client  # type: ignore[arg-type]
    )

    result = composer.compose(input)

    assert len(result.question_items) == 2
    call = client.responses.calls[0]
    assert call["store"] is False
    payload = json.loads(str(call["input"]))
    assert set(payload) == {"requirements", "issues"}
    assert "reference_date" not in str(payload)
    assert "effective_request" not in str(payload)
