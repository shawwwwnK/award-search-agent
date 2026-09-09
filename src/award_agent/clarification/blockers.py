"""Deterministic blocker collection and prompt rendering for continuation sessions.

The initial clarification policy in :mod:`award_agent.intent.clarification` is
intentionally left unchanged.  This module owns the additive session policy:
one prompt covers every active conflict and every required unknown, in a
stable order.  Details copied from a request are not rendered into the prompt;
the answer interpreter receives the typed requirements separately.
"""

from __future__ import annotations

from collections.abc import Iterable

from award_agent.domain.clarification_session import (
    BlockingRequirement,
    BlockingRequirementKind,
    ClarificationPrompt,
    EffectiveField,
    EffectiveRequest,
)

# This is the closed continuation blocker policy.  The order is part of the
# session contract and must not be inferred from the order in which unknowns
# happened to be produced by the initial workflow.
_REQUIRED_FIELDS: tuple[
    tuple[str, BlockingRequirementKind, EffectiveField], ...
] = (
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
    BlockingRequirementKind.CONFLICT: "Resolve the conflicting date constraints.",
    BlockingRequirementKind.ORIGIN: "Where would you like to depart from?",
    BlockingRequirementKind.DESTINATION: "Where would you like to travel to?",
    BlockingRequirementKind.DEPARTURE: "What departure date or date range should I use?",
    BlockingRequirementKind.RETURN_OR_DURATION: (
        "When should you return, or how long should the trip be?"
    ),
    BlockingRequirementKind.TRAVELERS: "How many travelers need seats?",
}

_PROMPT_INTRO = "Please provide or confirm the following trip details:"


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
) -> ClarificationPrompt | None:
    """Render one all-blockers prompt, or ``None`` when no prompt is needed.

    Prompt text is template-only and deliberately excludes conflict details,
    unknown details, raw request text, and location/date evidence.  The typed
    ``requirements`` tuple remains the machine-readable coverage contract.
    """

    ordered_requirements = tuple(sorted(requirements, key=_requirement_sort_key))
    if not ordered_requirements:
        return None

    message_lines = [_PROMPT_INTRO]
    message_lines.extend(
        f"{index}. {_PROMPT_LABELS[requirement.kind]}"
        for index, requirement in enumerate(ordered_requirements, start=1)
    )
    return ClarificationPrompt(
        prompt_id=prompt_id or f"prompt-{revision}",
        revision=revision,
        requirements=ordered_requirements,
        message="\n".join(message_lines),
    )


def build_clarification_prompt(
    effective_request: EffectiveRequest,
    *,
    revision: int,
    prompt_id: str | None = None,
) -> ClarificationPrompt | None:
    """Collect blockers and render the session's single pending prompt."""

    return render_clarification_prompt(
        collect_blocking_requirements(effective_request),
        revision=revision,
        prompt_id=prompt_id,
    )


__all__ = [
    "build_clarification_prompt",
    "collect_blocking_requirements",
    "render_clarification_prompt",
]
