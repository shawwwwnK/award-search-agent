"""One-way temporal amendment checks."""

from datetime import date

import pytest

from award_agent.clarification.calendar_plan import (
    CalendarCalculationProposal,
    CalendarDay,
    CalendarProposalTarget,
    LiteralIntervalOperation,
    evaluate_calendar_proposals,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import MessageSpan, RequestContext


def test_only_departure_calendar_proposals_materialize() -> None:
    receipt = evaluate_calendar_proposals(
        proposals=(
            CalendarCalculationProposal(
                fact_id="departure",
                target=CalendarProposalTarget.DEPARTURE_WINDOW,
                evidence=MessageSpan(message_id="m1", start=0, end=9, text="October 6"),
                operation=LiteralIntervalOperation(start=CalendarDay(month=10, day=6)),
            ),
        ),
        context=RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
    )[0]
    assert receipt.contribution.date_window is not None
    with pytest.raises(ValueError):
        SemanticTarget("return_window")
