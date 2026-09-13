"""Tests for the typed calendar-plan evaluator, with deliberately opaque evidence."""

from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.clarification.calendar_plan import (
    MAX_OFFSET_DAYS,
    CalendarAnchorEdge,
    CalendarAnchorInclusion,
    CalendarCalculationError,
    CalendarCalculationOperation,
    CalendarCalculationProposal,
    CalendarDay,
    CalendarProposalTarget,
    LiteralIntervalOperation,
    OffsetIntervalOperation,
    PriorFactAnchor,
    RecurringIntervalOperation,
    RequestDateAnchor,
    evaluate_calendar_proposals,
)
from award_agent.domain import MessageSpan, RequestContext


def _context() -> RequestContext:
    return RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")


def _evidence(fact_id: str) -> MessageSpan:
    # The evaluator must retain this evidence, but never parse it.
    return MessageSpan(message_id="opaque-answer", start=0, end=len(fact_id), text=fact_id)


def _proposal(
    fact_id: str,
    target: CalendarProposalTarget,
    operation: CalendarCalculationOperation,
) -> CalendarCalculationProposal:
    return CalendarCalculationProposal(
        fact_id=fact_id,
        target=target,
        evidence=_evidence(fact_id),
        operation=operation,
    )


def test_literal_intervals_resolve_from_context_without_reading_evidence_text() -> None:
    proposal = _proposal(
        "not-a-date",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(
            start=CalendarDay(month=10, day=12), end=CalendarDay(month=10, day=18)
        ),
    )
    (receipt,) = evaluate_calendar_proposals(proposals=(proposal,), context=_context())

    assert receipt.contribution.date_window is not None
    assert (receipt.contribution.date_window.start, receipt.contribution.date_window.end) == (
        date(2026, 10, 12),
        date(2026, 10, 18),
    )
    assert receipt.contribution.raw_text == "not-a-date"


def test_literal_interval_rolls_an_unqualified_end_across_year_boundary() -> None:
    proposal = _proposal(
        "opaque-range",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(
            start=CalendarDay(month=12, day=30), end=CalendarDay(month=1, day=2)
        ),
    )
    (receipt,) = evaluate_calendar_proposals(proposals=(proposal,), context=_context())

    assert receipt.contribution.date_window is not None
    assert receipt.contribution.date_window.end == date(2027, 1, 2)


def test_recurring_interval_from_request_date_uses_typed_weekday_and_span() -> None:
    proposal = _proposal(
        "opaque-recurrence",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        RecurringIntervalOperation(
            anchor=RequestDateAnchor(),
            weekday=5,
            cycles_after_anchor=1,
            span_days=3,
        ),
    )
    (receipt,) = evaluate_calendar_proposals(proposals=(proposal,), context=_context())

    assert receipt.contribution.date_window is not None
    assert (receipt.contribution.date_window.start, receipt.contribution.date_window.end) == (
        date(2026, 9, 19),
        date(2026, 9, 21),
    )


def test_wire_shape_selects_the_closed_discriminated_operation() -> None:
    proposal = CalendarCalculationProposal.model_validate(
        {
            "fact_id": "wire-recurrence",
            "target": "departure_window",
            "evidence": _evidence("opaque-wire").model_dump(mode="python"),
            "operation": {
                "kind": "recurring_interval",
                "anchor": {"kind": "request_date"},
                "weekday": 0,
                "inclusion": "strictly_after",
            },
        }
    )
    (receipt,) = evaluate_calendar_proposals(proposals=(proposal,), context=_context())

    assert isinstance(proposal.operation, RecurringIntervalOperation)
    assert receipt.contribution.date_window is not None
    assert receipt.contribution.date_window.start == date(2026, 9, 14)


def test_prior_fact_edge_is_topologically_evaluated_even_if_submitted_later() -> None:
    departure = _proposal(
        "departure-fact",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(
            start=CalendarDay(month=10, day=5), end=CalendarDay(month=10, day=7)
        ),
    )
    later_departure = _proposal(
        "later-departure-fact",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        RecurringIntervalOperation(
            anchor=PriorFactAnchor(fact_id="departure-fact", edge=CalendarAnchorEdge.END),
            weekday=2,
            inclusion=CalendarAnchorInclusion.STRICTLY_AFTER,
        ),
    )
    receipts = evaluate_calendar_proposals(proposals=(later_departure, departure), context=_context())

    assert [receipt.fact_id for receipt in receipts] == ["departure-fact", "later-departure-fact"]
    assert receipts[1].contribution.date_window is not None
    assert receipts[1].contribution.date_window.start == date(2026, 10, 14)


def test_offset_interval_uses_prior_fact_edge_and_is_marked_derived() -> None:
    departure = _proposal(
        "departure",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(start=CalendarDay(month=10, day=5)),
    )
    later_departure = _proposal(
        "later-departure",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        OffsetIntervalOperation(
            anchor=PriorFactAnchor(fact_id="departure", edge=CalendarAnchorEdge.START),
            start_offset_days=7,
            end_offset_days=9,
        ),
    )
    receipts = evaluate_calendar_proposals(proposals=(departure, later_departure), context=_context())

    assert receipts[1].contribution.date_window is not None
    assert (
        receipts[1].contribution.date_window.start,
        receipts[1].contribution.date_window.end,
    ) == (
        date(2026, 10, 12),
        date(2026, 10, 14),
    )
    assert receipts[1].contribution.date_window.precision.value == "derived"


def test_approximate_date_operation_has_generic_disclosure_without_phrase_parsing() -> None:
    proposal = _proposal(
        "opaque-approximate-date",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(
            start=CalendarDay(month=10, day=1), end=CalendarDay(month=10, day=10), approximate=True
        ),
    )
    (receipt,) = evaluate_calendar_proposals(proposals=(proposal,), context=_context())

    assert receipt.contribution.interpretation_provenance is not None
    disclosure = receipt.contribution.interpretation_provenance.assumption_disclosure
    assert disclosure is not None
    assert disclosure.message == (
        "I’ll use an approximate date interval from 2026-10-01 through 2026-10-10."
    )


def test_out_of_bounds_offset_is_rejected_by_contract() -> None:
    with pytest.raises(ValidationError):
        OffsetIntervalOperation(anchor=RequestDateAnchor(), start_offset_days=MAX_OFFSET_DAYS + 1)


def test_invalid_calendar_date_is_a_deterministic_calculation_error() -> None:
    proposal = _proposal(
        "opaque-invalid-date",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        LiteralIntervalOperation(start=CalendarDay(year=2026, month=2, day=29)),
    )
    with pytest.raises(CalendarCalculationError, match="invalid calendar date"):
        evaluate_calendar_proposals(proposals=(proposal,), context=_context())


def test_unknown_prior_fact_is_an_explicit_error() -> None:
    unknown_anchor = _proposal(
        "later-departure",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        OffsetIntervalOperation(
            anchor=PriorFactAnchor(fact_id="absent", edge=CalendarAnchorEdge.END),
            start_offset_days=7,
        ),
    )
    with pytest.raises(CalendarCalculationError, match="unknown prior fact"):
        evaluate_calendar_proposals(proposals=(unknown_anchor,), context=_context())

def test_same_batch_cycle_is_rejected_without_evaluating_any_fact() -> None:
    first = _proposal(
        "first",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        OffsetIntervalOperation(
            anchor=PriorFactAnchor(fact_id="second", edge=CalendarAnchorEdge.START),
            start_offset_days=1,
        ),
    )
    second = _proposal(
        "second",
        CalendarProposalTarget.DEPARTURE_WINDOW,
        OffsetIntervalOperation(
            anchor=PriorFactAnchor(fact_id="first", edge=CalendarAnchorEdge.START),
            start_offset_days=1,
        ),
    )
    with pytest.raises(CalendarCalculationError, match="dependency cycle"):
        evaluate_calendar_proposals(proposals=(first, second), context=_context())
