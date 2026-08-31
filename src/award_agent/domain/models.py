"""Typed contracts for the request-understanding workflow."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestContext(ContractModel):
    reference_date: date
    timezone: str

    @model_validator(mode="after")
    def validate_timezone(self) -> RequestContext:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown IANA timezone: {self.timezone}") from exc
        return self


class RawRequest(ContractModel):
    text: str = Field(min_length=1)
    context: RequestContext


class LocationKind(str, Enum):
    AIRPORT = "airport"
    CITY = "city"
    COUNTRY = "country"
    REGION = "region"


class LocationRef(ContractModel):
    kind: LocationKind
    value: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class SearchMode(str, Enum):
    AWARD = "award"
    CASH = "cash"


class Holiday(str, Enum):
    CHRISTMAS = "christmas"
    LABOR_DAY = "labor_day"
    THANKSGIVING = "thanksgiving"


class DateExpressionKind(str, Enum):
    EXACT = "exact"
    RANGE = "range"
    HOLIDAY_WINDOW = "holiday_window"
    RELATIVE_WEEKEND = "relative_weekend"
    MONTH = "month"
    RELATIVE_MONTH = "relative_month"
    BOUND = "bound"
    UNRESOLVED = "unresolved"


class DateExpression(ContractModel):
    """Flat schema compatible with Structured Outputs; validated by ``kind``."""

    kind: DateExpressionKind = Field(description="Semantic form of the user's date phrase.")
    raw_text: str = Field(min_length=1, description="Exact supporting phrase from the request.")
    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Literal month for exact, month, or bound kinds; null otherwise.",
    )
    day: int | None = Field(
        default=None,
        ge=1,
        le=31,
        description="Literal day for exact or bound kinds; null otherwise.",
    )
    year: int | None = Field(
        default=None,
        description="Year only when the request explicitly states it; null otherwise.",
    )
    start_month: int | None = Field(default=None, ge=1, le=12, description="Range only.")
    start_day: int | None = Field(default=None, ge=1, le=31, description="Range only.")
    end_month: int | None = Field(default=None, ge=1, le=12, description="Range only.")
    end_day: int | None = Field(default=None, ge=1, le=31, description="Range only.")
    start_year: int | None = Field(default=None, description="Explicit range year only.")
    end_year: int | None = Field(default=None, description="Explicit range year only.")
    holiday: Holiday | None = Field(
        default=None,
        description="Holiday-window and relative-weekend kinds only.",
    )
    count: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Number of weekends after a holiday; relative-weekend only.",
    )
    portion: Literal["whole", "first_week"] | None = Field(
        default=None,
        description="Month kind only.",
    )
    approximate: bool = Field(
        default=False,
        description="True only when the user's date phrase is approximate.",
    )
    offset_months: int | None = Field(
        default=None,
        ge=1,
        le=24,
        description="Relative-month kind only; do not calculate a calendar month.",
    )
    boundary: Literal["before", "after"] | None = Field(
        default=None,
        description="Bound kind only.",
    )
    reason: str | None = Field(default=None, description="Unresolved kind only.")

    @model_validator(mode="before")
    @classmethod
    def discard_irrelevant_components(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        try:
            kind = DateExpressionKind(data.get("kind"))
        except (TypeError, ValueError):
            return data
        allowed_by_kind = {
            DateExpressionKind.EXACT: {"month", "day", "year"},
            DateExpressionKind.RANGE: {
                "start_month",
                "start_day",
                "end_month",
                "end_day",
                "start_year",
                "end_year",
            },
            DateExpressionKind.HOLIDAY_WINDOW: {"holiday", "year"},
            DateExpressionKind.RELATIVE_WEEKEND: {"holiday", "count", "year"},
            DateExpressionKind.MONTH: {"month", "year", "portion"},
            DateExpressionKind.RELATIVE_MONTH: {"offset_months"},
            DateExpressionKind.BOUND: {"boundary", "month", "day", "year"},
            DateExpressionKind.UNRESOLVED: {"reason"},
        }
        component_fields = {
            "month",
            "day",
            "year",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
            "start_year",
            "end_year",
            "holiday",
            "count",
            "portion",
            "offset_months",
            "boundary",
            "reason",
        }
        cleaned = dict(data)
        for field_name in component_fields - allowed_by_kind[kind]:
            cleaned[field_name] = None

        raw_text = str(cleaned.get("raw_text", ""))
        normalized_raw_text = raw_text.casefold()
        if kind in {
            DateExpressionKind.HOLIDAY_WINDOW,
            DateExpressionKind.RELATIVE_WEEKEND,
        } and cleaned.get("holiday") is None:
            explicit_holidays = {
                "christmas": Holiday.CHRISTMAS,
                "labor day": Holiday.LABOR_DAY,
                "thanksgiving": Holiday.THANKSGIVING,
            }
            for holiday_name, holiday in explicit_holidays.items():
                if holiday_name in normalized_raw_text:
                    cleaned["holiday"] = holiday
                    break
        for year_field in ("year", "start_year", "end_year"):
            year = cleaned.get(year_field)
            if year is not None and str(year) not in raw_text:
                cleaned[year_field] = None
        return cleaned

    @model_validator(mode="after")
    def validate_components(self) -> DateExpression:
        required_by_kind = {
            DateExpressionKind.EXACT: ("month", "day"),
            DateExpressionKind.RANGE: (
                "start_month",
                "start_day",
                "end_month",
                "end_day",
            ),
            DateExpressionKind.HOLIDAY_WINDOW: ("holiday",),
            DateExpressionKind.RELATIVE_WEEKEND: ("holiday", "count"),
            DateExpressionKind.MONTH: ("month",),
            DateExpressionKind.RELATIVE_MONTH: ("offset_months",),
            DateExpressionKind.BOUND: ("boundary", "month", "day"),
            DateExpressionKind.UNRESOLVED: ("reason",),
        }
        missing = [
            field_name
            for field_name in required_by_kind[self.kind]
            if getattr(self, field_name) is None
        ]
        if missing:
            raise ValueError(f"{self.kind.value} expression requires: {', '.join(missing)}")
        return self


class DurationConstraint(ContractModel):
    raw_text: str = Field(min_length=1)
    days: int = Field(ge=1, le=365)
    approximate: bool = False


class PointBalance(ContractModel):
    program: str = Field(min_length=1)
    amount: int | None = Field(default=None, ge=0)
    raw_text: str = Field(min_length=1)


class Ambiguity(ContractModel):
    field: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    raw_text: str | None = None


class IntentExtraction(ContractModel):
    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    departure: DateExpression | None = None
    return_date: DateExpression | None = None
    duration: DurationConstraint | None = None
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    points_balances: list[PointBalance] = Field(default_factory=list)
    cash_budget_usd: int | None = Field(default=None, ge=0)
    date_flexibility_days: int | None = Field(default=None, ge=0, le=365)
    repositioning_allowed: bool | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


class DateWindowPrecision(str, Enum):
    EXACT = "exact"
    WINDOW = "window"
    MONTH = "month"
    BOUND = "bound"
    DERIVED = "derived"


class DateWindow(ContractModel):
    start: date
    end: date
    precision: DateWindowPrecision
    raw_text: str

    @model_validator(mode="after")
    def validate_order(self) -> DateWindow:
        if self.end < self.start:
            raise ValueError("date window end precedes start")
        return self


class UnknownReason(str, Enum):
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class UnknownField(ContractModel):
    field: str
    reason: UnknownReason
    detail: str
    raw_text: str | None = None


class Conflict(ContractModel):
    code: str
    fields: list[str]
    detail: str


class ParsedRequest(ContractModel):
    raw_text: str
    context: RequestContext
    travelers: int | None
    origins: list[LocationRef]
    destinations: list[LocationRef]
    departure_expression: DateExpression | None
    return_expression: DateExpression | None
    departure_window: DateWindow | None
    return_window: DateWindow | None
    duration: DurationConstraint | None
    cabins: list[CabinClass]
    search_modes: list[SearchMode]
    points_balances: list[PointBalance]
    cash_budget_usd: int | None
    date_flexibility_days: int | None
    repositioning_allowed: bool | None
    hard_constraints: list[str]
    unknowns: list[UnknownField]
    conflicts: list[Conflict]


class ClarificationAction(str, Enum):
    ASK = "ask"
    NONE = "none"


class ClarificationDecision(ContractModel):
    action: ClarificationAction
    field: str | None = None
    question: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_action(self) -> ClarificationDecision:
        has_question = self.field is not None and self.question is not None
        if self.action is ClarificationAction.ASK and not has_question:
            raise ValueError("ask decisions require a field and question")
        if self.action is ClarificationAction.NONE and any(
            value is not None for value in (self.field, self.question)
        ):
            raise ValueError("none decisions cannot include a field or question")
        return self


class RequestUnderstandingResult(ContractModel):
    parsed_request: ParsedRequest
    clarification: ClarificationDecision
