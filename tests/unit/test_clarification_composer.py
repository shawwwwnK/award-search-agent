"""ADR 0014 post-reduction issue and prompt-composition tests."""

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
    DEFAULT_CLARIFICATION_COMPOSER_MODEL,
    GPT_4O_MINI_CLARIFICATION_COMPOSER_MODEL,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationComposerError,
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


def test_composer_input_rejects_duplicate_or_unknown_issue_links() -> None:
    requirements = _requirements()
    issues = derive_clarification_issues(requirements)

    with pytest.raises(ValueError, match="unique IDs"):
        ClarificationPromptComposerInput(
            requirements=requirements,
            issues=(*issues, issues[0].model_copy(deep=True)),
        )

    with pytest.raises(ValueError, match="active requirements"):
        ClarificationPromptComposerInput(
            requirements=requirements,
            issues=(
                issues[0],
                issues[1].model_copy(update={"requirement_id": "not-active"}),
            ),
        )


def test_model_input_is_a_least_authority_projection() -> None:
    requirements = _requirements()
    input = ClarificationPromptComposerInput(
        requirements=requirements,
        issues=derive_clarification_issues(requirements),
    )

    payload = input.model_input()

    assert payload["requirements"] == [
        {"requirement_id": "departure", "kind": "departure"},
        {"requirement_id": "travelers", "kind": "travelers"},
    ]
    assert payload["issues"][0] == {
        "issue_id": "departure:missing",
        "requirement_id": "departure",
        "kind": "missing",
        "reason": "A departure timing is still needed.",
        "span": None,
    }
    serialized = json.dumps(payload)
    for forbidden in ("field", "conflict_code", "reason_code", "message_id", "start", "end"):
        assert forbidden not in serialized


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
    assert "message_id" not in str(payload)
    assert call["max_output_tokens"] == 300


def test_openai_composer_supports_experiment_model_configuration() -> None:
    assert OpenAIClarificationComposerConfig().model == DEFAULT_CLARIFICATION_COMPOSER_MODEL
    assert (
        OpenAIClarificationComposerConfig(model=GPT_4O_MINI_CLARIFICATION_COMPOSER_MODEL).model
        == "gpt-4o-mini"
    )
    assert OpenAIClarificationComposerConfig(temperature=0.2).temperature == 0.2
    with pytest.raises(ValueError, match="between 0 and 2"):
        OpenAIClarificationComposerConfig(temperature=2.1)


def test_openai_composer_reports_usage_less_attempts_for_evaluator_reconciliation() -> None:
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
    composer = OpenAIClarificationPromptComposer(
        OpenAIClarificationComposerConfig(model="model"), client=_Client(wire)  # type: ignore[arg-type]
    )

    composer.compose(input)

    assert composer.take_usage() == {
        "calls": 1,
        "captured_calls": 0,
        "missing_calls": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def test_openai_composer_rejects_unlinked_model_items() -> None:
    requirements = _requirements()
    input = ClarificationPromptComposerInput(
        requirements=requirements, issues=derive_clarification_issues(requirements)
    )
    wire = _ClarificationPromptComposerWireOutput.model_validate(
        {
            "question_items": [
                {
                    "requirement_id": "departure",
                    "issue_ids": ["travelers:missing"],
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
    composer = OpenAIClarificationPromptComposer(
        OpenAIClarificationComposerConfig(model="model"),
        client=_Client(wire),  # type: ignore[arg-type]
    )

    with pytest.raises(OpenAIClarificationComposerError, match="canonical validation"):
        composer.compose(input)
