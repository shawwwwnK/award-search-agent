"""Single semantic receiver contract for initial request understanding.

The receiver is the only component which reads request language.  It returns
groundable facts and generic calendar calculations; the workflow below it is
deliberately unable to infer a meaning from a phrase.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import Field, model_validator

from award_agent.domain import CabinClass, ContractModel, Holiday, LocationKind, SearchMode


class SemanticIntentInput(ContractModel):
    request_text: str = Field(min_length=1)


class SemanticFactTarget(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"
    TRAVELERS = "travelers"
    CABIN = "cabin"
    SEARCH_MODE = "search_mode"
    REPOSITIONING = "repositioning"
    HARD_CONSTRAINT = "hard_constraint"


class SemanticFact(ContractModel):
    # Opaque receiver component identity.  It is deliberately not derived from
    # the request text: the adapter uses it only to preserve independent
    # siblings during a bounded semantic repair.
    component_id: str | None = Field(default=None, min_length=1, max_length=100)
    target: SemanticFactTarget
    quote: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)
    location_kind: LocationKind | None = None
    location_value: str | None = None
    travelers: int | None = Field(default=None, ge=1)
    cabin: CabinClass | None = None
    search_mode: SearchMode | None = None
    repositioning_allowed: bool | None = None
    hard_constraint: str | None = None

    @model_validator(mode="after")
    def closed_shape(self) -> SemanticFact:
        values = (
            self.location_kind,
            self.location_value,
            self.travelers,
            self.cabin,
            self.search_mode,
            self.repositioning_allowed,
            self.hard_constraint,
        )
        expected = {
            SemanticFactTarget.ORIGIN: self.location_kind is not None and bool(self.location_value),
            SemanticFactTarget.DESTINATION: self.location_kind is not None
            and bool(self.location_value),
            SemanticFactTarget.TRAVELERS: self.travelers is not None,
            SemanticFactTarget.CABIN: self.cabin is not None,
            SemanticFactTarget.SEARCH_MODE: self.search_mode is not None,
            SemanticFactTarget.REPOSITIONING: self.repositioning_allowed is not None,
            SemanticFactTarget.HARD_CONSTRAINT: bool(self.hard_constraint),
        }[self.target]
        allowed_counts = {
            SemanticFactTarget.ORIGIN: 2,
            SemanticFactTarget.DESTINATION: 2,
            SemanticFactTarget.TRAVELERS: 1,
            SemanticFactTarget.CABIN: 1,
            SemanticFactTarget.SEARCH_MODE: 1,
            SemanticFactTarget.REPOSITIONING: 1,
            SemanticFactTarget.HARD_CONSTRAINT: 1,
        }
        if (
            not expected
            or sum(value is not None for value in values) != allowed_counts[self.target]
        ):
            raise ValueError("semantic fact has an invalid typed value shape")
        return self


class CalendarOperationKind(str, Enum):
    LITERAL_INTERVAL = "literal_interval"
    CALENDAR_PERIOD = "calendar_period"
    RECURRING_INTERVAL = "recurring_interval"
    OFFSET_INTERVAL = "offset_interval"
    UNRESOLVED = "unresolved"


class CalendarAnchorKind(str, Enum):
    REQUEST_DATE = "request_date"
    HOLIDAY = "holiday"
    PRIOR_FACT = "prior_fact"


class CalendarAnchorEdge(str, Enum):
    START = "start"
    END = "end"


class CalendarPeriodSlice(str, Enum):
    WHOLE = "whole"
    FIRST_WEEK = "first_week"
    EARLY = "early"
    MID = "mid"
    LATE = "late"


class CalendarComposition(str, Enum):
    INTERSECT = "intersect"
    UNION = "union"


class SemanticTemporalTarget(str, Enum):
    DEPARTURE = "departure"
    RETURN = "return"
    DURATION = "duration"


class SemanticTemporalFact(ContractModel):
    """Flat provider-safe generic calendar operation.

    It intentionally has no English relation labels.  A weekday after a
    holiday is a recurring interval with a holiday anchor, regardless of how
    the customer happened to say it.
    """

    fact_id: str = Field(min_length=1, max_length=100)
    component_id: str | None = Field(default=None, min_length=1, max_length=100)
    target: SemanticTemporalTarget
    quote: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)
    operation: CalendarOperationKind
    start_year: int | None = Field(default=None, ge=1000, le=9999)
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_day: int | None = Field(default=None, ge=1, le=31)
    end_year: int | None = Field(default=None, ge=1000, le=9999)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_day: int | None = Field(default=None, ge=1, le=31)
    period_month: int | None = Field(default=None, ge=1, le=12)
    period_year: int | None = Field(default=None, ge=1000, le=9999)
    # Zero is the current request-relative month; positive values are future
    # months.  The receiver owns recognizing wording such as "this month".
    period_offset_months: int | None = Field(default=None, ge=0, le=24)
    period_slice: CalendarPeriodSlice | None = None
    anchor_kind: CalendarAnchorKind | None = None
    anchor_holiday: Holiday | None = None
    anchor_year: int | None = Field(default=None, ge=1000, le=9999)
    anchor_fact_id: str | None = None
    anchor_edge: CalendarAnchorEdge | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    strictly_after: bool | None = None
    cycles_after_anchor: int | None = Field(default=None, ge=0, le=104)
    span_days: int | None = Field(default=None, ge=1, le=31)
    start_offset_days: int | None = Field(default=None, ge=-730, le=730)
    end_offset_days: int | None = Field(default=None, ge=-730, le=730)
    approximate: bool = False
    composition: CalendarComposition = CalendarComposition.INTERSECT
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def operation_shape(self) -> SemanticTemporalFact:
        operation_fields = {
            CalendarOperationKind.LITERAL_INTERVAL: {
                "start_year",
                "start_month",
                "start_day",
                "end_year",
                "end_month",
                "end_day",
            },
            CalendarOperationKind.CALENDAR_PERIOD: {
                "period_month",
                "period_year",
                "period_offset_months",
                "period_slice",
            },
            CalendarOperationKind.RECURRING_INTERVAL: {
                "anchor_kind",
                "anchor_holiday",
                "anchor_year",
                "anchor_fact_id",
                "anchor_edge",
                "weekday",
                "strictly_after",
                "cycles_after_anchor",
                "span_days",
            },
            CalendarOperationKind.OFFSET_INTERVAL: {
                "anchor_kind",
                "anchor_holiday",
                "anchor_year",
                "anchor_fact_id",
                "anchor_edge",
                "start_offset_days",
                "end_offset_days",
            },
            CalendarOperationKind.UNRESOLVED: {"reason"},
        }
        all_fields = set().union(*operation_fields.values())
        present = {name for name in all_fields if getattr(self, name) is not None}
        irrelevant = present - operation_fields[self.operation]
        if irrelevant:
            raise ValueError(
                f"calendar operation has irrelevant fields: {', '.join(sorted(irrelevant))}"
            )
        if self.operation is CalendarOperationKind.LITERAL_INTERVAL:
            if self.start_month is None or self.start_day is None:
                raise ValueError("literal interval requires start month and day")
            if (self.end_month is None) != (self.end_day is None):
                raise ValueError("literal interval end must have month and day together")
            if self.end_year is not None and self.end_month is None:
                raise ValueError("literal interval end year requires month and day")
        elif self.operation is CalendarOperationKind.CALENDAR_PERIOD:
            if self.period_slice is None or (self.period_month is None) == (
                self.period_offset_months is None
            ):
                raise ValueError(
                    "calendar period requires exactly one of month or request-relative month offset, plus a slice"
                )
            if self.period_offset_months is not None and self.period_year is not None:
                raise ValueError("request-relative calendar period cannot provide a year")
        elif self.operation is CalendarOperationKind.RECURRING_INTERVAL:
            if self.anchor_kind is None or self.weekday is None:
                raise ValueError("recurring interval requires anchor and weekday")
            if self.anchor_kind is CalendarAnchorKind.HOLIDAY and self.anchor_holiday is None:
                raise ValueError("holiday anchor requires holiday")
            if self.anchor_kind is CalendarAnchorKind.PRIOR_FACT and not self.anchor_fact_id:
                raise ValueError("prior-fact anchor requires fact ID")
        elif self.operation is CalendarOperationKind.OFFSET_INTERVAL:
            if self.anchor_kind is None or self.start_offset_days is None:
                raise ValueError("offset interval requires anchor and start offset")
            if self.anchor_kind is CalendarAnchorKind.HOLIDAY and self.anchor_holiday is None:
                raise ValueError("holiday anchor requires holiday")
            if self.anchor_kind is CalendarAnchorKind.PRIOR_FACT and not self.anchor_fact_id:
                raise ValueError("prior-fact anchor requires fact ID")
            if self.end_offset_days is not None and self.end_offset_days < self.start_offset_days:
                raise ValueError("offset interval end precedes start")
        elif not self.reason:
            raise ValueError("unresolved temporal fact requires reason")
        return self


class SemanticUnresolved(ContractModel):
    component_id: str | None = Field(default=None, min_length=1, max_length=100)
    field: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1, max_length=300)
    # The receiver can explicitly request one generic-operation recheck
    # without deterministic code reading the quote or reason for meaning.
    operation_recheck: bool = False


class SemanticValidationIssue(ContractModel):
    code: str = Field(min_length=1, max_length=120)
    path: tuple[str, ...] = Field(min_length=1)
    detail: str = Field(min_length=1, max_length=500)


class SemanticScopeKind(str, Enum):
    RETURN = "return"
    DURATION = "duration"


class SemanticScopeNotice(ContractModel):
    """A separately grounded one-way scope notice, never an active date fact."""

    component_id: str | None = Field(default=None, min_length=1, max_length=100)
    kind: SemanticScopeKind
    quote: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class SemanticIntentProposal(ContractModel):
    facts: tuple[SemanticFact, ...] = ()
    temporal_facts: tuple[SemanticTemporalFact, ...] = ()
    unresolved: tuple[SemanticUnresolved, ...] = ()
    scope_notices: tuple[SemanticScopeNotice, ...] = ()

    @model_validator(mode="after")
    def unique_temporal_ids(self) -> SemanticIntentProposal:
        ids = [item.fact_id for item in self.temporal_facts]
        if len(ids) != len(set(ids)):
            raise ValueError("temporal fact IDs must be unique")
        return self


class SemanticIntentInterpreter(Protocol):
    def interpret(self, input: SemanticIntentInput) -> SemanticIntentProposal: ...


class SemanticIntentRepairer(Protocol):
    def repair(
        self,
        input: SemanticIntentInput,
        *,
        proposal: SemanticIntentProposal,
        errors: tuple[SemanticValidationIssue, ...],
    ) -> SemanticIntentProposal: ...
