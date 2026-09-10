"""Deterministic blocker collection and prompt rendering for continuation sessions.

The initial clarification policy in :mod:`award_agent.intent.clarification` is
intentionally left unchanged.  This module owns the additive session policy:
one prompt covers every active conflict and every required unknown, in a
stable order.  Details copied from a request are not rendered into the prompt;
the answer interpreter receives the typed requirements separately.
"""

from __future__ import annotations

from collections.abc import Iterable

from award_agent.clarification.issues import derive_clarification_issues
from award_agent.domain.clarification_session import (
    BlockingRequirement,
    BlockingRequirementKind,
    ClarificationIssue,
    ClarificationPrompt,
    EffectiveField,
    EffectiveRequest,
    PromptCompositionSource,
)

# This is the closed continuation blocker policy.  The order is part of the
# session contract and must not be inferred from the order in which unknowns
# happened to be produced by the initial workflow.
_REQUIRED_FIELDS: tuple[tuple[str, BlockingRequirementKind, EffectiveField], ...] = (
    ("origin", BlockingRequirementKind.ORIGIN, EffectiveField.ORIGIN),
    ("destination", BlockingRequirementKind.DESTINATION, EffectiveField.DESTINATION),
    ("departure", BlockingRequirementKind.DEPARTURE, EffectiveField.DEPARTURE),
    (
        "return_or_duration",
        BlockingRequirementKind.RETURN_OR_DURATION,
        EffectiveField.RETURN_OR_DURATION,
    ),
    ("travelers", BlockingRequirementKind.TRAVELERS, EffectiveField.TRAVELERS),
)

_REQUIRED_FIELD_ORDER = {field: index for index, (field, _, _) in enumerate(_REQUIRED_FIELDS)}

_PROMPT_LABELS: dict[BlockingRequirementKind, str] = {
    BlockingRequirementKind.CONFLICT: "Could you clarify the dates that conflict?",
    BlockingRequirementKind.ORIGIN: "Where will you be departing from?",
    BlockingRequirementKind.DESTINATION: "Where would you like to go?",
    BlockingRequirementKind.DEPARTURE: (
        "When would you like to leave? A month, date, or date range all work."
    ),
    BlockingRequirementKind.RETURN_OR_DURATION: (
        "When would you like to return, or how long would you like the trip to be?"
    ),
    BlockingRequirementKind.TRAVELERS: "How many people will be traveling?",
}

_PROMPT_INTRO = "I’d be happy to help plan this trip. To narrow it down, could you share:"


def _safe_phrase(text: str) -> str:
    """Bound quoted answer context in a fallback prompt."""

    normalized = " ".join(text.split())
    return normalized[:120] + ("…" if len(normalized) > 120 else "")


def _fallback_question(requirement: BlockingRequirement, issues: tuple[ClarificationIssue, ...]) -> str:
    answer_issue = next((item for item in issues if item.span is not None), None)
    if answer_issue is not None:
        assert answer_issue.span is not None
        phrase = _safe_phrase(answer_issue.span.text)
        if answer_issue.kind.value == "ambiguous":
            return f"When you said “{phrase},” what should I use for that detail?"
        return f"I couldn’t safely use “{phrase}.” Could you clarify that detail?"
    if requirement.kind is BlockingRequirementKind.CONFLICT:
        return "Which of the conflicting details should I use?"
    return _PROMPT_LABELS[requirement.kind]


def collect_blocking_requirements(
    effective_request: EffectiveRequest,
) -> tuple[BlockingRequirement, ...]:
    """Collect the active continuation blockers in their canonical order.

    Only the five required fields in the closed policy are blocking.  Other
    ``UnknownField`` entries (for example cabin, search mode, repositioning,
    or unsupported preferences) remain on the effective request for later
    policy decisions and do not produce a clarification requirement.

    Conflict codes and required field names are semantic identifiers, not
    request text.  Repeated conflicts with the same code and repeated unknown
    entries for the same required field are represented once.
    """

    # Conflict order is independent of incidental list order in a source
    # result.  A conflict code is the stable semantic identity for the closed
    # conflict requirement, and duplicate codes are suppressed.
    conflicts_by_code = {conflict.code: conflict for conflict in effective_request.conflicts}
    requirements: list[BlockingRequirement] = [
        BlockingRequirement(
            requirement_id=f"conflict:{code}",
            kind=BlockingRequirementKind.CONFLICT,
            conflict_code=code,
        )
        for code in sorted(conflicts_by_code)
    ]

    unknown_fields = {unknown.field for unknown in effective_request.unknowns}
    requirements.extend(
        BlockingRequirement(
            requirement_id=field,
            kind=kind,
            field=effective_field,
        )
        for field, kind, effective_field in _REQUIRED_FIELDS
        if field in unknown_fields
    )
    return tuple(requirements)


def _requirement_sort_key(requirement: BlockingRequirement) -> tuple[int, str]:
    if requirement.kind is BlockingRequirementKind.CONFLICT:
        # ``collect_blocking_requirements`` validates this through the domain
        # contract.  Keep a defensive fallback for callers that construct a
        # requirement-like iterable before validation.
        return (0, requirement.conflict_code or requirement.requirement_id)
    assert requirement.field is not None
    return (1 + _REQUIRED_FIELD_ORDER[requirement.field.value], requirement.field.value)


def render_clarification_prompt(
    requirements: Iterable[BlockingRequirement],
    *,
    revision: int,
    prompt_id: str | None = None,
    issues: Iterable[ClarificationIssue] | None = None,
    question_items: tuple[str, ...] | None = None,
    composition_source: PromptCompositionSource = PromptCompositionSource.FALLBACK,
    fallback_code: str | None = None,
) -> ClarificationPrompt | None:
    """Render one all-blockers prompt, or ``None`` when no prompt is needed.

    The fallback prompt deliberately excludes conflict details, unknown
    details, raw request text, and location/date evidence. A validated
    model-authored follow-up may replace its copy after a response, but the
    typed ``requirements`` tuple remains the machine-readable coverage
    contract.
    """

    ordered_requirements = tuple(sorted(requirements, key=_requirement_sort_key))
    if not ordered_requirements:
        return None

    ordered_issues = tuple(issues or derive_clarification_issues(ordered_requirements))
    issues_by_requirement: dict[str, tuple[ClarificationIssue, ...]] = {
        requirement.requirement_id: tuple(
            issue for issue in ordered_issues if issue.requirement_id == requirement.requirement_id
        )
        for requirement in ordered_requirements
    }
    if question_items is not None and len(question_items) != len(ordered_requirements):
        raise ValueError("prompt question items must cover every active requirement")
    rendered_questions = question_items or tuple(
        _fallback_question(requirement, issues_by_requirement[requirement.requirement_id])
        for requirement in ordered_requirements
    )
    message_lines = [_PROMPT_INTRO]
    message_lines.extend(
        f"{index}. {question}"
        for index, question in enumerate(rendered_questions, start=1)
    )
    rendered_message = "\n".join(message_lines)
    return ClarificationPrompt(
        prompt_id=prompt_id or f"prompt-{revision}",
        revision=revision,
        requirements=ordered_requirements,
        message=rendered_message,
        issues=ordered_issues,
        composition_source=composition_source,
        fallback_code=fallback_code,
    )


def build_clarification_prompt(
    effective_request: EffectiveRequest,
    *,
    revision: int,
    prompt_id: str | None = None,
    issues: Iterable[ClarificationIssue] | None = None,
    question_items: tuple[str, ...] | None = None,
    composition_source: PromptCompositionSource = PromptCompositionSource.FALLBACK,
    fallback_code: str | None = None,
) -> ClarificationPrompt | None:
    """Collect blockers and render the session's single pending prompt."""

    return render_clarification_prompt(
        collect_blocking_requirements(effective_request),
        revision=revision,
        prompt_id=prompt_id,
        issues=issues,
        question_items=question_items,
        composition_source=composition_source,
        fallback_code=fallback_code,
    )


__all__ = [
    "build_clarification_prompt",
    "collect_blocking_requirements",
    "render_clarification_prompt",
]
