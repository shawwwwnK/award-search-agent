"""Generic, model-authored calendar calculation proposals for clarification.

This is deliberately a *calculation* boundary, not a natural-language parser.
An LLM may describe a literal interval, a recurrence, an offset from a typed
anchor, or a duration.  This module reads only that typed proposal, the
immutable request context, and prior typed receipts.  In particular, it never
looks at ``MessageSpan.text`` to decide what a user meant.

The contract intentionally avoids a growing taxonomy of English phrases.  For
example, a model can express a weekday after an earlier fact as a recurring
interval anchored at that fact's end; it need not invent a new operation for
"Wednesday afterwards".
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from award_agent.domain import (
    AnswerMessageSource,
    AssumptionDisclosure,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    MessageSpan,
    RequestContext,
    TemporalAnswerInterpretationProvenance,
    TemporalContribution,
    TemporalContributionKind,
)
from award_agent.domain.clarification_session import SessionContractModel

CALENDAR_PLAN_VERSION = "clarification-calendar-plan-v1"
MAX_OFFSET_DAYS = 730
MAX_RECURRENCE_CYCLES = 104


class CalendarProposalTarget(str, Enum):
    """The temporal value a calendar proposal materializes."""

    DEPARTURE_WINDOW = "departure_window"
    RETURN_WINDOW = "return_window"
    DURATION = "duration"


class CalendarAnchorEdge(str, Enum):
    START = "start"
    END = "end"


class CalendarAnchorInclusion(str, Enum):
    ON_OR_AFTER = "on_or_after"
    STRICTLY_AFTER = "strictly_after"


class CalendarDay(SessionContractModel):
    """A calendar day whose year may be resolved relative to request context."""

    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)


class RequestDateAnchor(SessionContractModel):
    kind: Literal["request_date"] = "request_date"


class PriorFactAnchor(SessionContractModel):
    kind: Literal["prior_fact"] = "prior_fact"
    fact_id: str = Field(min_length=1, max_length=100)
    edge: CalendarAnchorEdge


CalendarAnchor = Annotated[
    RequestDateAnchor | PriorFactAnchor,
    Field(discriminator="kind"),
]


class LiteralIntervalOperation(SessionContractModel):
    """A literal point or bounded calendar interval.

    An omitted end is an exact one-day interval.  Omitting a year asks the
    evaluator to choose the next occurrence from the immutable request date;
    it does not accept a model-calculated date.
    """

    kind: Literal["literal_interval"] = "literal_interval"
    start: CalendarDay
    end: CalendarDay | None = None
    approximate: bool = False


class RecurringIntervalOperation(SessionContractModel):
    """An interval on a weekly recurrence anchored at context or another fact.

    ``weekday`` is the ISO/Python index (Monday=0 through Sunday=6).  The
    operation finds the matching weekday on/after (or strictly after) the
    anchor, then advances ``cycles_after_anchor`` weekly cycles.  ``span_days``
    keeps the operation general enough for multi-day recurring intervals.
    """

    kind: Literal["recurring_interval"] = "recurring_interval"
    anchor: CalendarAnchor
    weekday: int = Field(ge=0, le=6)
    inclusion: CalendarAnchorInclusion = CalendarAnchorInclusion.ON_OR_AFTER
    cycles_after_anchor: int = Field(default=0, ge=0, le=MAX_RECURRENCE_CYCLES)
    span_days: int = Field(default=1, ge=1, le=31)
    approximate: bool = False


class OffsetIntervalOperation(SessionContractModel):
    """A typed bounded offset interval anchored at context or another fact."""

    kind: Literal["offset_interval"] = "offset_interval"
    anchor: CalendarAnchor
    start_offset_days: int = Field(ge=-MAX_OFFSET_DAYS, le=MAX_OFFSET_DAYS)
    end_offset_days: int | None = Field(default=None, ge=-MAX_OFFSET_DAYS, le=MAX_OFFSET_DAYS)
    approximate: bool = False

    @model_validator(mode="after")
    def validate_offsets(self) -> OffsetIntervalOperation:
        if self.end_offset_days is not None and self.end_offset_days < self.start_offset_days:
            raise ValueError("offset interval end cannot precede start")
        return self


class DurationOperation(SessionContractModel):
    """A model-selected duration envelope, with an explicit approximation flag."""

    kind: Literal["duration"] = "duration"
    minimum_days: int = Field(ge=1, le=365)
    maximum_days: int = Field(ge=1, le=365)
    approximate: bool = False

    @model_validator(mode="after")
    def validate_duration(self) -> DurationOperation:
        if self.maximum_days < self.minimum_days:
            raise ValueError("duration maximum cannot precede minimum")
        return self


CalendarCalculationOperation = Annotated[
    LiteralIntervalOperation
    | RecurringIntervalOperation
    | OffsetIntervalOperation
    | DurationOperation,
    Field(discriminator="kind"),
]


class CalendarCalculationProposal(SessionContractModel):
    """One LLM-authored, grounded calculation request.

    ``evidence`` is retained for provenance only.  It is opaque to the
    evaluator, which is intentionally unable to parse or normalize its text.
    """

    fact_id: str = Field(min_length=1, max_length=100)
    target: CalendarProposalTarget
    evidence: MessageSpan
    operation: CalendarCalculationOperation

    @model_validator(mode="after")
    def validate_target_shape(self) -> CalendarCalculationProposal:
        if self.target is CalendarProposalTarget.DURATION:
            if not isinstance(self.operation, DurationOperation):
                raise ValueError("duration target requires a duration operation")
        elif isinstance(self.operation, DurationOperation):
            raise ValueError("date-window target cannot use a duration operation")
        return self


class CalendarCalculationReceipt(SessionContractModel):
    """A materialized fact that may safely serve as a later typed anchor."""

    fact_id: str = Field(min_length=1, max_length=100)
    target: CalendarProposalTarget
    contribution: TemporalContribution

    @model_validator(mode="after")
    def validate_target_contribution(self) -> CalendarCalculationReceipt:
        expected_kind = _contribution_kind_for_target(self.target)
        if self.contribution.kind is not expected_kind:
            raise ValueError("receipt target does not match temporal contribution kind")
        return self


class CalendarCalculationError(ValueError):
    """A deterministic calculation/validation failure, never a text judgement."""


def evaluate_calendar_proposals(
    *,
    proposals: tuple[CalendarCalculationProposal, ...],
    context: RequestContext,
    prior_receipts: Mapping[str, CalendarCalculationReceipt] | None = None,
) -> tuple[CalendarCalculationReceipt, ...]:
    """Evaluate typed proposals in dependency order.

    The caller can submit facts in any order.  Same-batch prior-fact edges are
    topologically sorted; missing anchors and cycles are explicit errors.  No
    supplied answer text is inspected.
    """

    receipts: dict[str, CalendarCalculationReceipt] = dict(prior_receipts or {})
    _validate_prior_receipts(receipts)
    by_id: dict[str, CalendarCalculationProposal] = {}
    for proposal in proposals:
        if proposal.fact_id in receipts:
            raise CalendarCalculationError(f"proposal fact ID already exists: {proposal.fact_id}")
        if proposal.fact_id in by_id:
            raise CalendarCalculationError(f"duplicate proposal fact ID: {proposal.fact_id}")
        by_id[proposal.fact_id] = proposal

    dependencies = {
        fact_id: _local_dependency_ids(proposal, by_id, receipts)
        for fact_id, proposal in by_id.items()
    }
    order = _topological_order(tuple(proposal.fact_id for proposal in proposals), dependencies)
    evaluated: list[CalendarCalculationReceipt] = []
    for fact_id in order:
        proposal = by_id[fact_id]
        contribution = _evaluate_proposal(proposal=proposal, context=context, receipts=receipts)
        receipt = CalendarCalculationReceipt(
            fact_id=proposal.fact_id,
            target=proposal.target,
            contribution=contribution,
        )
        receipts[fact_id] = receipt
        evaluated.append(receipt)
    return tuple(evaluated)


def _validate_prior_receipts(receipts: Mapping[str, CalendarCalculationReceipt]) -> None:
    for fact_id, receipt in receipts.items():
        if fact_id != receipt.fact_id:
            raise CalendarCalculationError("prior receipt mapping key must equal receipt fact ID")


def _local_dependency_ids(
    proposal: CalendarCalculationProposal,
    proposals: Mapping[str, CalendarCalculationProposal],
    receipts: Mapping[str, CalendarCalculationReceipt],
) -> tuple[str, ...]:
    anchor = _operation_anchor(proposal.operation)
    if not isinstance(anchor, PriorFactAnchor):
        return ()
    if anchor.fact_id in receipts:
        return ()
    if anchor.fact_id not in proposals:
        raise CalendarCalculationError(
            f"proposal {proposal.fact_id} references unknown prior fact {anchor.fact_id}"
        )
    return (anchor.fact_id,)


def _topological_order(
    submitted_ids: tuple[str, ...], dependencies: Mapping[str, tuple[str, ...]]
) -> tuple[str, ...]:
    remaining = {fact_id: set(needs) for fact_id, needs in dependencies.items()}
    ordered: list[str] = []
    while remaining:
        ready = [
            fact_id for fact_id in submitted_ids if fact_id in remaining and not remaining[fact_id]
        ]
        if not ready:
            cycle_ids = ", ".join(sorted(remaining))
            raise CalendarCalculationError(f"calendar proposal dependency cycle: {cycle_ids}")
        for fact_id in ready:
            ordered.append(fact_id)
            del remaining[fact_id]
        completed = set(ready)
        for needs in remaining.values():
            needs.difference_update(completed)
    return tuple(ordered)


def _operation_anchor(operation: CalendarCalculationOperation) -> CalendarAnchor | None:
    if isinstance(operation, (RecurringIntervalOperation, OffsetIntervalOperation)):
        return operation.anchor
    return None


def _evaluate_proposal(
    *,
    proposal: CalendarCalculationProposal,
    context: RequestContext,
    receipts: Mapping[str, CalendarCalculationReceipt],
) -> TemporalContribution:
    operation = proposal.operation
    if isinstance(operation, DurationOperation):
        return _duration_contribution(proposal, operation)
    if isinstance(operation, LiteralIntervalOperation):
        start, end, precision = _evaluate_literal(operation, context)
    elif isinstance(operation, RecurringIntervalOperation):
        start, end, precision = _evaluate_recurring(operation, context, receipts)
    elif isinstance(operation, OffsetIntervalOperation):
        start, end, precision = _evaluate_offset(operation, context, receipts)
    else:  # pragma: no cover - discriminated union is closed
        raise CalendarCalculationError("unsupported calendar calculation operation")
    kind = _contribution_kind_for_target(proposal.target)
    return TemporalContribution(
        contribution_id=f"answer:{proposal.fact_id}:{kind.value}",
        kind=kind,
        source=AnswerMessageSource(span=proposal.evidence),
        raw_text=proposal.evidence.text,
        amendment_id=proposal.fact_id,
        date_window=DateWindow(
            start=start, end=end, precision=precision, raw_text=proposal.evidence.text
        ),
        interpretation_provenance=_provenance(proposal, start=start, end=end),
    )


def _duration_contribution(
    proposal: CalendarCalculationProposal, operation: DurationOperation
) -> TemporalContribution:
    return TemporalContribution(
        contribution_id=f"answer:{proposal.fact_id}:duration",
        kind=TemporalContributionKind.DURATION,
        source=AnswerMessageSource(span=proposal.evidence),
        raw_text=proposal.evidence.text,
        amendment_id=proposal.fact_id,
        interpreted_duration=InterpretedDuration(
            raw_text=proposal.evidence.text,
            minimum_days=operation.minimum_days,
            maximum_days=operation.maximum_days,
        ),
        interpretation_provenance=_provenance(proposal),
    )


def _evaluate_literal(
    operation: LiteralIntervalOperation, context: RequestContext
) -> tuple[date, date, DateWindowPrecision]:
    start = _resolve_calendar_day(operation.start, context)
    if operation.end is None:
        return start, start, DateWindowPrecision.EXACT
    end = _resolve_interval_end(operation.end, start, context)
    return start, end, DateWindowPrecision.WINDOW


def _resolve_calendar_day(value: CalendarDay, context: RequestContext) -> date:
    year = value.year
    if year is None:
        year = context.reference_date.year
        if (value.month, value.day) < (context.reference_date.month, context.reference_date.day):
            year += 1
    return _make_date(year, value.month, value.day)


def _resolve_interval_end(value: CalendarDay, start: date, context: RequestContext) -> date:
    if value.year is not None:
        end = _make_date(value.year, value.month, value.day)
        if end < start:
            raise CalendarCalculationError("literal interval end precedes start")
        return end
    end = _make_date(start.year, value.month, value.day)
    if end < start:
        end = _make_date(start.year + 1, value.month, value.day)
    return end


def _make_date(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise CalendarCalculationError("invalid calendar date in proposal") from exc


def _evaluate_recurring(
    operation: RecurringIntervalOperation,
    context: RequestContext,
    receipts: Mapping[str, CalendarCalculationReceipt],
) -> tuple[date, date, DateWindowPrecision]:
    anchor = _resolve_anchor_date(operation.anchor, context, receipts)
    delta = (operation.weekday - anchor.weekday()) % 7
    if operation.inclusion is CalendarAnchorInclusion.STRICTLY_AFTER and delta == 0:
        delta = 7
    start = anchor + timedelta(days=delta + (operation.cycles_after_anchor * 7))
    end = start + timedelta(days=operation.span_days - 1)
    precision = (
        DateWindowPrecision.EXACT if operation.span_days == 1 else DateWindowPrecision.WINDOW
    )
    return start, end, precision


def _evaluate_offset(
    operation: OffsetIntervalOperation,
    context: RequestContext,
    receipts: Mapping[str, CalendarCalculationReceipt],
) -> tuple[date, date, DateWindowPrecision]:
    anchor = _resolve_anchor_date(operation.anchor, context, receipts)
    end_offset = (
        operation.start_offset_days
        if operation.end_offset_days is None
        else operation.end_offset_days
    )
    start = anchor + timedelta(days=operation.start_offset_days)
    end = anchor + timedelta(days=end_offset)
    precision = DateWindowPrecision.EXACT if start == end else DateWindowPrecision.DERIVED
    return start, end, precision


def _resolve_anchor_date(
    anchor: CalendarAnchor,
    context: RequestContext,
    receipts: Mapping[str, CalendarCalculationReceipt],
) -> date:
    if isinstance(anchor, RequestDateAnchor):
        return context.reference_date
    receipt = receipts.get(anchor.fact_id)
    if receipt is None:
        raise CalendarCalculationError(f"prior fact receipt is unavailable: {anchor.fact_id}")
    window = receipt.contribution.date_window
    if window is None:
        raise CalendarCalculationError("prior fact anchor must reference a date-window receipt")
    return window.start if anchor.edge is CalendarAnchorEdge.START else window.end


def _contribution_kind_for_target(target: CalendarProposalTarget) -> TemporalContributionKind:
    if target is CalendarProposalTarget.DEPARTURE_WINDOW:
        return TemporalContributionKind.DEPARTURE_WINDOW
    if target is CalendarProposalTarget.RETURN_WINDOW:
        return TemporalContributionKind.RETURN_WINDOW
    return TemporalContributionKind.DURATION


def _provenance(
    proposal: CalendarCalculationProposal,
    *,
    start: date | None = None,
    end: date | None = None,
) -> TemporalAnswerInterpretationProvenance:
    operation = proposal.operation
    disclosure = None
    if isinstance(operation, DurationOperation) and operation.approximate:
        disclosure = AssumptionDisclosure(
            disclosure_id=f"calendar-plan:{proposal.fact_id}:approximate-duration",
            message=(
                "I’ll use an approximate trip duration of "
                f"{operation.minimum_days} to {operation.maximum_days} days."
            ),
        )
    elif not isinstance(operation, DurationOperation) and operation.approximate:
        assert start is not None and end is not None
        disclosure = AssumptionDisclosure(
            disclosure_id=f"calendar-plan:{proposal.fact_id}:approximate-interval",
            message=(
                "I’ll use an approximate date interval from "
                f"{start.isoformat()} through {end.isoformat()}."
            ),
        )
    return TemporalAnswerInterpretationProvenance(
        policy_version=CALENDAR_PLAN_VERSION,
        interpretation_id=f"calendar_plan_{operation.kind}",
        candidate_ids=(f"calendar-plan:{proposal.fact_id}",),
        assumption_disclosure=disclosure,
    )


__all__ = [
    "CALENDAR_PLAN_VERSION",
    "MAX_OFFSET_DAYS",
    "MAX_RECURRENCE_CYCLES",
    "CalendarAnchor",
    "CalendarAnchorEdge",
    "CalendarAnchorInclusion",
    "CalendarCalculationError",
    "CalendarCalculationOperation",
    "CalendarCalculationProposal",
    "CalendarCalculationReceipt",
    "CalendarDay",
    "CalendarProposalTarget",
    "DurationOperation",
    "LiteralIntervalOperation",
    "OffsetIntervalOperation",
    "PriorFactAnchor",
    "RecurringIntervalOperation",
    "RequestDateAnchor",
    "evaluate_calendar_proposals",
]
