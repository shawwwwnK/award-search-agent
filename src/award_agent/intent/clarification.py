"""Stable, deterministic clarification policy for the active one-way award workflow."""

from award_agent.domain import (
    ClarificationAction,
    ClarificationDecision,
    ParsedRequest,
    UnsupportedRequestPartCode,
)

_QUESTIONS = {
    "origin": "Where would you like to depart from?",
    "destination": "Where would you like to travel to?",
    "departure": "What departure date or date range should I use?",
    "travelers": "How many travelers need seats?",
}

_RETURN_SCOPE_MESSAGE = (
    "This release supports one-way award searches only. "
    "Please submit the return leg as a separate one-way request."
)
_CASH_SCOPE_MESSAGE = (
    "Cash-only searches are not supported in this release. Please submit an award request."
)


def decide_clarification(parsed: ParsedRequest) -> ClarificationDecision:
    unsupported_codes = {item.code for item in parsed.unsupported_request_parts}
    messages: list[str] = []
    if UnsupportedRequestPartCode.RETURN_OR_DURATION_NOT_SUPPORTED in unsupported_codes:
        messages.append(_RETURN_SCOPE_MESSAGE)
    if UnsupportedRequestPartCode.CASH_ONLY_NOT_SUPPORTED in unsupported_codes:
        messages.append(_CASH_SCOPE_MESSAGE)
    if messages:
        return ClarificationDecision(
            action=ClarificationAction.UNSUPPORTED,
            field="one_way_award_scope",
            question=" ".join(messages),
            reason=", ".join(sorted(code.value for code in unsupported_codes)),
        )

    if parsed.conflicts:
        conflict = parsed.conflicts[0]
        return ClarificationDecision(
            action=ClarificationAction.ASK,
            field="dates",
            question="Your departure-date constraints conflict. Which departure date should I use?",
            reason=conflict.detail,
        )

    unknown_fields = {unknown.field for unknown in parsed.unknowns}
    for field in ("origin", "destination", "departure", "travelers"):
        if field in unknown_fields:
            return ClarificationDecision(
                action=ClarificationAction.ASK,
                field=field,
                question=_QUESTIONS[field],
                reason=f"{field} is required to define a bounded flight search.",
            )

    return ClarificationDecision(
        action=ClarificationAction.NONE,
        reason="The request contains enough hard constraints for later search planning.",
    )
