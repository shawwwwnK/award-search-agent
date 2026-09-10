"""Closed semantic facts for the clarification receiver.

This module is deliberately not an answer parser.  The receiver owns the
meaning of natural language; this module validates its closed output and
compiles temporal AST nodes using hidden request context.
"""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import date, timedelta
from enum import Enum

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


class SemanticTarget(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"
    TRAVELERS = "travelers"
    DEPARTURE_WINDOW = "departure_window"
    RETURN_WINDOW = "return_window"
    DURATION = "duration"


class SemanticOperation(str, Enum):
    SET = "set"
    REPLACE = "replace"


class TemporalAstKind(str, Enum):
    CALENDAR_DATE = "calendar_date"
    DATE_RANGE = "date_range"
    MONTH_PORTION = "month_portion"
    RELATIVE_WEEKDAY = "relative_weekday"
    RELATIVE_WEEKEND = "relative_weekend"
    RELATIVE_TO_PRIOR_FACT = "relative_to_prior_fact"
    DURATION = "duration"


WEEKDAY_ENCODING = (
    "Use ISO/Python weekday indexes: Monday=0, Tuesday=1, Wednesday=2, "
    "Thursday=3, Friday=4, Saturday=5, Sunday=6."
)


class TemporalSemanticAst(SessionContractModel):
    """Date-free receiver meaning; concrete calendar values never cross LLM boundary."""

    kind: TemporalAstKind
    year: int | None = Field(default=None, ge=2000, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    portion: str | None = None
    end_year: int | None = Field(default=None, ge=2000, le=2100)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_day: int | None = Field(default=None, ge=1, le=31)
    weekday: int | None = Field(default=None, ge=0, le=6, description=WEEKDAY_ENCODING)
    relation: str | None = None
    quantity: int | None = Field(default=None, ge=1, le=365)
    unit: str | None = None
    anchor_fact_id: str | None = Field(default=None, min_length=1)
    approximate: bool = False

    @model_validator(mode="after")
    def closed_shape(self) -> TemporalSemanticAst:
        if self.kind is TemporalAstKind.CALENDAR_DATE:
            if (
                self.month is None
                or self.day is None
                or any(
                    value is not None
                    for value in (
                        self.portion,
                        self.weekday,
                        self.relation,
                        self.quantity,
                        self.unit,
                        self.end_year,
                        self.end_month,
                        self.end_day,
                        self.anchor_fact_id,
                    )
                )
            ):
                raise ValueError("calendar_date requires only month/day and optional year")
        elif self.kind is TemporalAstKind.DATE_RANGE:
            if (
                self.month is None
                or self.day is None
                or self.end_month is None
                or self.end_day is None
                or any(
                    value is not None
                    for value in (
                        self.portion,
                        self.weekday,
                        self.relation,
                        self.quantity,
                        self.unit,
                        self.anchor_fact_id,
                    )
                )
            ):
                raise ValueError(
                    "date_range requires start month/day, end month/day, and optional endpoint years"
                )
        elif self.kind is TemporalAstKind.MONTH_PORTION:
            if (
                self.month is None
                or self.portion not in {"early", "mid", "late", "whole"}
                or any(
                    value is not None
                    for value in (
                        self.day,
                        self.weekday,
                        self.relation,
                        self.quantity,
                        self.unit,
                        self.end_year,
                        self.end_month,
                        self.end_day,
                        self.anchor_fact_id,
                    )
                )
            ):
                raise ValueError("month_portion requires month and a closed portion")
        elif self.kind is TemporalAstKind.RELATIVE_WEEKDAY:
            if (
                self.weekday is None
                or self.relation not in {"this", "next", "upcoming"}
                or any(
                    value is not None
                    for value in (
                        self.year,
                        self.month,
                        self.day,
                        self.portion,
                        self.quantity,
                        self.unit,
                        self.end_year,
                        self.end_month,
                        self.end_day,
                        self.anchor_fact_id,
                    )
                )
            ):
                raise ValueError("relative_weekday requires weekday and closed relation")
        elif self.kind is TemporalAstKind.RELATIVE_WEEKEND:
            if self.relation not in {"this", "next"} or any(
                value is not None
                for value in (
                    self.year,
                    self.month,
                    self.day,
                    self.portion,
                    self.weekday,
                    self.quantity,
                    self.unit,
                    self.end_year,
                    self.end_month,
                    self.end_day,
                    self.anchor_fact_id,
                )
            ):
                raise ValueError("relative_weekend requires a closed relation")
        elif self.kind is TemporalAstKind.RELATIVE_TO_PRIOR_FACT:
            if (
                self.anchor_fact_id is None
                or self.relation != "after"
                or self.quantity is None
                or self.unit not in {"day", "week"}
                or any(
                    value is not None
                    for value in (
                        self.year,
                        self.month,
                        self.day,
                        self.portion,
                        self.weekday,
                        self.end_year,
                        self.end_month,
                        self.end_day,
                    )
                )
            ):
                raise ValueError(
                    "relative_to_prior_fact requires an earlier fact ID and an after day/week offset"
                )
        elif self.kind is TemporalAstKind.DURATION and (
            self.quantity is None
            or self.unit not in {"day", "week"}
            or any(
                value is not None
                for value in (
                    self.year,
                    self.month,
                    self.day,
                    self.portion,
                    self.weekday,
                    self.relation,
                    self.end_year,
                    self.end_month,
                    self.end_day,
                    self.anchor_fact_id,
                )
            )
        ):
            raise ValueError("duration requires quantity and day/week unit")
        if (
            self.kind not in {TemporalAstKind.DURATION, TemporalAstKind.RELATIVE_TO_PRIOR_FACT}
            and self.approximate
        ):
            raise ValueError("only duration and relative offsets may be approximate")
        return self


class CompiledSemanticTemporalFact(SessionContractModel):
    amendment_id: str = Field(min_length=1)
    contribution: TemporalContribution


class SemanticTemporalCompileError(ValueError):
    pass


def _future_year(context: RequestContext, month: int, day: int) -> int:
    year = context.reference_date.year
    if (month, day) < (context.reference_date.month, context.reference_date.day):
        year += 1
    return year


def compile_temporal_ast(
    *,
    amendment_id: str,
    target: SemanticTarget,
    ast: TemporalSemanticAst,
    span: MessageSpan,
    context: RequestContext,
    prior_compiled_facts: Mapping[str, CompiledSemanticTemporalFact] | None = None,
) -> CompiledSemanticTemporalFact:
    """Compile receiver-selected closed semantics; never inspect ``span.text``."""
    if target is SemanticTarget.DURATION:
        if ast.kind is not TemporalAstKind.DURATION:
            raise SemanticTemporalCompileError("duration target requires duration AST")
        assert ast.quantity is not None and ast.unit is not None
        days = ast.quantity * (7 if ast.unit == "week" else 1)
        slack = 1 if ast.approximate else 0
        contribution = TemporalContribution(
            contribution_id=f"answer:{amendment_id}:duration",
            kind=TemporalContributionKind.DURATION,
            source=AnswerMessageSource(span=span),
            raw_text=span.text,
            amendment_id=amendment_id,
            interpreted_duration=InterpretedDuration(
                raw_text=span.text, minimum_days=max(1, days - slack), maximum_days=days + slack
            ),
            interpretation_provenance=(
                _approximate_duration_provenance(
                    amendment_id=amendment_id,
                    span=span,
                    minimum_days=max(1, days - slack),
                    maximum_days=days + slack,
                )
                if ast.approximate
                else None
            ),
        )
        return CompiledSemanticTemporalFact(amendment_id=amendment_id, contribution=contribution)
    if target not in {SemanticTarget.DEPARTURE_WINDOW, SemanticTarget.RETURN_WINDOW}:
        raise SemanticTemporalCompileError("non-temporal target cannot compile temporal AST")
    if ast.kind is TemporalAstKind.DURATION:
        raise SemanticTemporalCompileError("date target cannot use duration AST")
    if ast.kind is TemporalAstKind.CALENDAR_DATE:
        assert ast.month is not None and ast.day is not None
        year = ast.year if ast.year is not None else _future_year(context, ast.month, ast.day)
        try:
            start = date(year, ast.month, ast.day)
        except ValueError as exc:
            raise SemanticTemporalCompileError("invalid calendar date AST") from exc
        end, precision = start, DateWindowPrecision.EXACT
    elif ast.kind is TemporalAstKind.DATE_RANGE:
        assert (
            ast.month is not None
            and ast.day is not None
            and ast.end_month is not None
            and ast.end_day is not None
        )
        start_year = ast.year if ast.year is not None else _future_year(context, ast.month, ast.day)
        try:
            start = date(start_year, ast.month, ast.day)
            end_year = ast.end_year if ast.end_year is not None else start_year
            end = date(end_year, ast.end_month, ast.end_day)
            if ast.end_year is None and end < start:
                end = date(start_year + 1, ast.end_month, ast.end_day)
        except ValueError as exc:
            raise SemanticTemporalCompileError("invalid date range AST") from exc
        precision = DateWindowPrecision.WINDOW
    elif ast.kind is TemporalAstKind.MONTH_PORTION:
        assert ast.month is not None and ast.portion is not None
        year = ast.year if ast.year is not None else _future_year(context, ast.month, 1)
        last = calendar.monthrange(year, ast.month)[1]
        start_day, end_day = {
            "early": (1, 10),
            "mid": (11, 20),
            "late": (21, last),
            "whole": (1, last),
        }[ast.portion]
        start, end, precision = (
            date(year, ast.month, start_day),
            date(year, ast.month, end_day),
            DateWindowPrecision.WINDOW,
        )
    elif ast.kind is TemporalAstKind.RELATIVE_TO_PRIOR_FACT:
        if target is not SemanticTarget.RETURN_WINDOW:
            raise SemanticTemporalCompileError(
                "relative prior-fact AST may only target return_window"
            )
        assert ast.anchor_fact_id is not None and ast.quantity is not None and ast.unit is not None
        prior = (prior_compiled_facts or {}).get(ast.anchor_fact_id)
        if prior is None:
            raise SemanticTemporalCompileError(
                "relative prior-fact AST requires an earlier same-answer fact"
            )
        anchor = prior.contribution
        if (
            anchor.kind is not TemporalContributionKind.DEPARTURE_WINDOW
            or anchor.date_window is None
        ):
            raise SemanticTemporalCompileError(
                "relative prior-fact AST must reference an earlier departure-window fact"
            )
        offset = ast.quantity * (7 if ast.unit == "week" else 1)
        slack = 1 if ast.approximate else 0
        start = anchor.date_window.start + timedelta(days=max(1, offset - slack))
        end = anchor.date_window.end + timedelta(days=offset + slack)
        precision = DateWindowPrecision.DERIVED
    elif ast.kind is TemporalAstKind.RELATIVE_WEEKDAY:
        assert ast.weekday is not None and ast.relation is not None
        delta = (ast.weekday - context.reference_date.weekday()) % 7
        if ast.relation == "next":
            delta += 7
        start = context.reference_date + timedelta(days=delta)
        end, precision = start, DateWindowPrecision.EXACT
    elif ast.kind is TemporalAstKind.RELATIVE_WEEKEND:
        assert ast.relation is not None
        delta = (5 - context.reference_date.weekday()) % 7
        if ast.relation == "next":
            delta += 7
        start = context.reference_date + timedelta(days=delta)
        end, precision = start + timedelta(days=2), DateWindowPrecision.WINDOW
    else:  # pragma: no cover - closed enum exhaustiveness
        raise SemanticTemporalCompileError("unsupported temporal AST")
    kind = (
        TemporalContributionKind.DEPARTURE_WINDOW
        if target is SemanticTarget.DEPARTURE_WINDOW
        else TemporalContributionKind.RETURN_WINDOW
    )
    interpretation_provenance = None
    if ast.kind is TemporalAstKind.MONTH_PORTION and ast.portion != "whole":
        assert ast.portion is not None
        interpretation_provenance = _month_portion_provenance(
            amendment_id=amendment_id,
            span=span,
            portion=ast.portion,
            start=start,
            end=end,
        )
    elif ast.kind is TemporalAstKind.RELATIVE_TO_PRIOR_FACT and ast.approximate:
        interpretation_provenance = _relative_offset_provenance(
            amendment_id=amendment_id,
            span=span,
            start=start,
            end=end,
        )
    contribution = TemporalContribution(
        contribution_id=f"answer:{amendment_id}:{kind.value}",
        kind=kind,
        source=AnswerMessageSource(span=span),
        raw_text=span.text,
        amendment_id=amendment_id,
        date_window=DateWindow(start=start, end=end, precision=precision, raw_text=span.text),
        interpretation_provenance=interpretation_provenance,
    )
    return CompiledSemanticTemporalFact(amendment_id=amendment_id, contribution=contribution)


def _assumption_provenance(
    *, amendment_id: str, interpretation_id: str, message: str
) -> TemporalAnswerInterpretationProvenance:
    """Make accepting compiler policies visible without entrusting prose to the LLM."""
    return TemporalAnswerInterpretationProvenance(
        policy_version="clarification-semantic-temporal-v1",
        interpretation_id=interpretation_id,
        candidate_ids=(f"semantic:{amendment_id}",),
        assumption_disclosure=AssumptionDisclosure(
            disclosure_id=f"semantic:{amendment_id}:{interpretation_id}", message=message
        ),
    )


def _month_portion_provenance(
    *, amendment_id: str, span: MessageSpan, portion: str, start: date, end: date
) -> TemporalAnswerInterpretationProvenance:
    return _assumption_provenance(
        amendment_id=amendment_id,
        interpretation_id=f"month_{portion}",
        message=(
            f"I’ll interpret “{span.text}” as {portion} month, "
            f"from {start.isoformat()} through {end.isoformat()}."
        ),
    )


def _approximate_duration_provenance(
    *, amendment_id: str, span: MessageSpan, minimum_days: int, maximum_days: int
) -> TemporalAnswerInterpretationProvenance:
    return _assumption_provenance(
        amendment_id=amendment_id,
        interpretation_id="approximate_duration_plus_or_minus_one_day",
        message=(
            f"I’ll interpret “{span.text}” as a trip of {minimum_days} to {maximum_days} days."
        ),
    )


def _relative_offset_provenance(
    *, amendment_id: str, span: MessageSpan, start: date, end: date
) -> TemporalAnswerInterpretationProvenance:
    return _assumption_provenance(
        amendment_id=amendment_id,
        interpretation_id="approximate_relative_offset_plus_or_minus_one_day",
        message=(
            f"I’ll interpret “{span.text}” as a return from {start.isoformat()} through {end.isoformat()}."
        ),
    )
