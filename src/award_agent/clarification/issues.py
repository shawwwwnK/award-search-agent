"""Authoritative post-reduction explanation of remaining clarification work.

Issues are derived from deterministic state, not model prose.  They are the
only answer-history context a prompt composer may receive.
"""

from __future__ import annotations

from collections import defaultdict

from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    ClarificationIssue,
    ClarificationIssueKind,
    RejectedFragment,
    RejectedFragmentReason,
)


def _issue_kind(
    fragment: RejectedFragment, requirement: BlockingRequirement
) -> ClarificationIssueKind:
    # A conflict requirement remains a conflict even when an answer-model
    # classified its wording as ambiguous/unsupported. This preserves the
    # prompt contract and prevents answer presentation from relabeling state.
    if requirement.kind is BlockingRequirementKind.CONFLICT:
        return ClarificationIssueKind.CONFLICT
    if fragment.reason is RejectedFragmentReason.AMBIGUOUS:
        return ClarificationIssueKind.AMBIGUOUS
    if fragment.reason is RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION:
        return ClarificationIssueKind.UNSUPPORTED
    return ClarificationIssueKind.UNSUPPORTED


def _requirement_label(requirement: BlockingRequirement) -> str:
    return {
        BlockingRequirementKind.ORIGIN: "departure location",
        BlockingRequirementKind.DESTINATION: "destination",
        BlockingRequirementKind.DEPARTURE: "departure timing",
        BlockingRequirementKind.RETURN_OR_DURATION: "return date or trip length",
        BlockingRequirementKind.TRAVELERS: "traveler count",
        BlockingRequirementKind.CONFLICT: "conflicting travel details",
    }[requirement.kind]


def derive_clarification_issues(
    requirements: tuple[BlockingRequirement, ...],
    *,
    rejected_fragments: tuple[RejectedFragment, ...] = (),
) -> tuple[ClarificationIssue, ...]:
    """Produce one or more canonical issues for every remaining requirement.

    A rejection can be assigned only through its deterministic requirement
    links.  The sole exception is a single remaining requirement, where an
    unlinked answer-local rejection has an unambiguous owner.  This preserves
    useful quoted context without letting a composer infer field ownership.
    """

    active = {item.requirement_id: item for item in requirements}
    linked: dict[str, list[RejectedFragment]] = defaultdict(list)
    for fragment in rejected_fragments:
        owners = tuple(item for item in fragment.requirement_ids if item in active)
        if not owners and len(requirements) == 1:
            owners = (requirements[0].requirement_id,)
        for requirement_id in owners:
            linked[requirement_id].append(fragment)

    issues: list[ClarificationIssue] = []
    for requirement in requirements:
        fragments = linked[requirement.requirement_id]
        if fragments:
            for ordinal, fragment in enumerate(fragments, start=1):
                kind = _issue_kind(fragment, requirement)
                issues.append(
                    ClarificationIssue(
                        issue_id=f"{requirement.requirement_id}:answer:{ordinal}",
                        requirement_id=requirement.requirement_id,
                        kind=kind,
                        reason=f"The answer phrase needs a clearer {_requirement_label(requirement)}.",
                        span=fragment.span,
                        reason_code=fragment.reason_code or f"answer.{fragment.reason.value}",
                    )
                )
            continue
        if requirement.kind is BlockingRequirementKind.CONFLICT:
            issues.append(
                ClarificationIssue(
                    issue_id=f"{requirement.requirement_id}:conflict",
                    requirement_id=requirement.requirement_id,
                    kind=ClarificationIssueKind.CONFLICT,
                    reason="The travel details conflict and need one clear choice.",
                    reason_code="state.conflict",
                )
            )
        else:
            issues.append(
                ClarificationIssue(
                    issue_id=f"{requirement.requirement_id}:missing",
                    requirement_id=requirement.requirement_id,
                    kind=ClarificationIssueKind.MISSING,
                    reason=f"A {_requirement_label(requirement)} is still needed.",
                    reason_code="state.missing",
                )
            )
    return tuple(issues)


__all__ = ["derive_clarification_issues"]
