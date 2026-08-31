"""Stable, deterministic clarification policy."""

from award_agent.domain import ClarificationAction, ClarificationDecision, ParsedRequest

_QUESTIONS = {
    "origin": "Where would you like to depart from?",
    "destination": "Where would you like to travel to?",
    "departure": "What departure date or date range should I use?",
    "return_or_duration": "When should you return, or how long should the trip be?",
    "travelers": "How many travelers need seats?",
}


def decide_clarification(parsed: ParsedRequest) -> ClarificationDecision:
    if parsed.conflicts:
        conflict = parsed.conflicts[0]
        return ClarificationDecision(
            action=ClarificationAction.ASK,
            field="dates",
            question="Your date constraints conflict. Which departure and return dates should I use?",
            reason=conflict.detail,
        )

    unknown_fields = {unknown.field for unknown in parsed.unknowns}
    for field in ("origin", "destination", "departure", "return_or_duration", "travelers"):
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
