"""Typed contracts for the request-understanding workflow."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal
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
    value: str = Field(
        min_length=1,
        description=(
            "Model-proposed normalized semantic name. This is a resolver candidate, not an "
            "authoritative canonical name or stable location identifier. Explicit airport codes "
            "are preserved as uppercase codes by deterministic workflow policy."
        ),
    )
    raw_text: str = Field(
        min_length=1,
        description="Exact location wording copied from the request.",
    )


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class SearchMode(str, Enum):
    AWARD = "award"
    CASH = "cash"


class Holiday(str, Enum):
    NEW_YEARS_DAY = "new_years_day"
    MARTIN_LUTHER_KING_JR_DAY = "martin_luther_king_jr_day"
    WASHINGTONS_BIRTHDAY = "washingtons_birthday"
    MEMORIAL_DAY = "memorial_day"
    JUNETEENTH = "juneteenth"
    INDEPENDENCE_DAY = "independence_day"
    LABOR_DAY = "labor_day"
    COLUMBUS_DAY = "columbus_day"
    VETERANS_DAY = "veterans_day"
    THANKSGIVING = "thanksgiving"
    CHRISTMAS = "christmas"


class DateExpressionKind(str, Enum):
    EXACT = "exact"
    RANGE = "range"
    HOLIDAY_WINDOW = "holiday_window"
    RELATIVE_WEEKEND = "relative_weekend"
    MONTH = "month"
    RELATIVE_MONTH = "relative_month"
    PRECEDING_WEEKDAY = "preceding_weekday"
    FOLLOWING_WEEKDAY = "following_weekday"
    BOUND = "bound"
    UNRESOLVED = "unresolved"


class Weekday(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class DateExpressionAnchor(str, Enum):
    DEPARTURE = "departure"


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
        description="Number of weekends after the selected anchor; relative-weekend only.",
    )
    relative_to: DateExpressionAnchor | None = Field(
        default=None,
        description="Departure anchor for a departure-relative weekend; null otherwise.",
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
    weekday: Weekday | None = Field(
        default=None,
        description="Preceding- and following-weekday kinds only.",
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
            DateExpressionKind.RELATIVE_WEEKEND: {
                "holiday",
                "count",
                "year",
                "relative_to",
            },
            DateExpressionKind.MONTH: {"month", "year", "portion"},
            DateExpressionKind.RELATIVE_MONTH: {"offset_months"},
            DateExpressionKind.PRECEDING_WEEKDAY: {"weekday"},
            DateExpressionKind.FOLLOWING_WEEKDAY: {"weekday"},
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
            "relative_to",
            "portion",
            "offset_months",
            "weekday",
            "boundary",
            "reason",
        }
        cleaned = dict(data)
        for field_name in component_fields - allowed_by_kind[kind]:
            cleaned[field_name] = None

        raw_text = str(cleaned.get("raw_text", ""))
        normalized_raw_text = raw_text.casefold()
        if (
            kind
            in {
                DateExpressionKind.HOLIDAY_WINDOW,
                DateExpressionKind.RELATIVE_WEEKEND,
            }
            and cleaned.get("holiday") is None
        ):
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
            DateExpressionKind.RELATIVE_WEEKEND: ("count",),
            DateExpressionKind.MONTH: ("month",),
            DateExpressionKind.RELATIVE_MONTH: ("offset_months",),
            DateExpressionKind.PRECEDING_WEEKDAY: ("weekday",),
            DateExpressionKind.FOLLOWING_WEEKDAY: ("weekday",),
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
        if self.kind is DateExpressionKind.RELATIVE_WEEKEND:
            anchors = [self.holiday is not None, self.relative_to is not None]
            if sum(anchors) != 1:
                raise ValueError(
                    "relative_weekend expression requires exactly one anchor: "
                    "holiday or relative_to"
                )
        return self


class DurationConstraint(ContractModel):
    raw_text: str = Field(min_length=1)
    days: int = Field(ge=1, le=365)
    approximate: bool = False


class Ambiguity(ContractModel):
    field: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    raw_text: str | None = None


class TemporalTarget(str, Enum):
    DEPARTURE = "departure"
    RETURN = "return"


class TemporalPhraseTarget(str, Enum):
    """Coarse role of verbatim temporal evidence, not a calendar relation."""

    DEPARTURE = "departure"
    RETURN = "return"
    DURATION = "duration"
    UNSPECIFIED = "unspecified"


class TemporalEvidenceClaim(str, Enum):
    """Meaning supported by one verbatim quote.

    Anchor claims identify literally named dates, months, or holidays. Period claims identify
    windows, modifiers, and relative timing for departure or return. Duration claims describe trip
    length; they are not point offsets. ``temporal_unspecified`` is only for genuinely unclear
    targets, not merely unsupported calendar vocabulary.
    """

    DEPARTURE_ANCHOR = "departure_anchor"
    RETURN_ANCHOR = "return_anchor"
    DEPARTURE_PERIOD = "departure_period"
    RETURN_PERIOD = "return_period"
    APPROXIMATE_DURATION = "approximate_duration"
    DURATION = "duration"
    ALTERNATE_DEPARTURE_DAY = "alternate_departure_day"
    ALTERNATE_RETURN_DAY = "alternate_return_day"
    UNSPECIFIED = "temporal_unspecified"


class ExactDateAnchor(ContractModel):
    """A month and day literally present in the request; never inferred from context."""

    kind: Literal["exact_date"]
    anchor_id: str = Field(
        min_length=1,
        description="Unique pass-one local label. This is not an evidence_id or reference_key.",
    )
    applies_to: TemporalTarget = Field(
        description="Trip endpoint directly constrained by the date."
    )
    raw_text: str = Field(description="Shortest exact quote that literally names month and day.")
    occurrence_index: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based occurrence only when this exact raw_text repeats; otherwise null.",
    )
    month: int = Field(ge=1, le=12, description="Month number literally named by raw_text.")
    day: int = Field(ge=1, le=31, description="Day number literally named by raw_text.")
    year: int | None = Field(
        default=None,
        ge=1000,
        le=9999,
        description="Four-digit year only if raw_text explicitly includes it; otherwise null.",
    )


class MonthAnchor(ContractModel):
    """A calendar month literally named in the request, never a deictic month."""

    kind: Literal["month"]
    anchor_id: str = Field(
        min_length=1,
        description="Unique pass-one local label. This is not an evidence_id or reference_key.",
    )
    applies_to: TemporalTarget = Field(
        description="Trip endpoint directly constrained by the month."
    )
    raw_text: str = Field(description="Exact quote containing the literal month name only.")
    occurrence_index: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based occurrence only when this exact raw_text repeats; otherwise null.",
    )
    month: int = Field(ge=1, le=12, description="Month number literally named by raw_text.")
    year: int | None = Field(
        default=None,
        ge=1000,
        le=9999,
        description="Four-digit year only if raw_text explicitly includes it; otherwise null.",
    )


class HolidayAnchor(ContractModel):
    """A supported holiday literally named in the request; no holiday window is inferred here."""

    kind: Literal["holiday"]
    anchor_id: str = Field(
        min_length=1,
        description="Unique pass-one local label. This is not an evidence_id or reference_key.",
    )
    applies_to: TemporalTarget = Field(
        description="Trip endpoint directly constrained by the holiday."
    )
    raw_text: str = Field(description="Shortest exact quote that literally names the holiday.")
    occurrence_index: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based occurrence only when this exact raw_text repeats; otherwise null.",
    )
    holiday: Holiday = Field(description="Supported holiday literally named by raw_text.")
    year: int | None = Field(
        default=None,
        ge=1000,
        le=9999,
        description="Four-digit year only if raw_text explicitly includes it; otherwise null.",
    )


TemporalAnchor = ExactDateAnchor | MonthAnchor | HolidayAnchor


class TemporalPhrase(ContractModel):
    """One shortest sufficient verbatim quote plus its coarse semantic role and claims."""

    applies_to: TemporalPhraseTarget = Field(
        description=(
            "Coarse role: departure or return timing, trip duration, or unspecified only when the "
            "request truly gives no endpoint cue. Unsupported seasons still use departure/return."
        )
    )
    raw_text: str = Field(
        description=(
            "Verbatim temporal wording that is not an explicit exact-date, month, or holiday "
            "anchor. Do not normalize offsets, alternatives, approximations, or relations."
        ),
    )
    claim_ids: list[TemporalEvidenceClaim] = Field(
        default_factory=list,
        description=(
            "Every meaning directly supported by this quote. Use *_anchor only for a literal date, "
            "month, or holiday; *_period for relative/window/modifier wording; duration for exact "
            "trip length; approximate_duration when approximation words modify trip length; "
            "alternate_* only for explicit endpoint alternatives; temporal_unspecified only when "
            "the endpoint is genuinely unclear. Never label trip length as a point offset."
        ),
    )
    occurrence_index: int | None = Field(
        default=None,
        ge=0,
        description="Zero-based occurrence when the quote appears more than once.",
    )


class ValidatedSourceSpan(ContractModel):
    """Canonical request span using Python start-inclusive/end-exclusive offsets."""

    source_id: Literal["original_request"] = "original_request"
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order(self) -> ValidatedSourceSpan:
        if self.end <= self.start:
            raise ValueError("source span end must be greater than start")
        return self


class GroundedTemporalEvidence(ContractModel):
    """One canonical span explicitly linked to one or more temporal claims."""

    evidence_id: str = Field(min_length=1)
    claim_ids: list[TemporalEvidenceClaim] = Field(min_length=1)
    span: ValidatedSourceSpan


class CoarseIntentExtraction(ContractModel):
    """Request-text-only extraction; empty temporal lists mean no temporal evidence was stated."""

    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    repositioning_allowed: bool | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    date_anchors: list[TemporalAnchor] = Field(
        default_factory=list,
        description=(
            "Only literally named exact dates, named months, and supported named holidays. Never "
            "create an anchor for next month, a season, a weekday, a duration, or inferred dates."
        ),
    )
    temporal_phrases: list[TemporalPhrase] = Field(
        default_factory=list,
        description=(
            "Shortest sufficient verbatim temporal evidence not fully represented by a literal "
            "anchor. Empty when the request states no temporal meaning; never invent a relation."
        ),
    )


class ResolvedTemporalAnchor(ContractModel):
    anchor: TemporalAnchor
    start: date
    end: date
    source: Literal["calendar", "holiday_provider"]
    source_detail: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_order(self) -> ResolvedTemporalAnchor:
        if self.end < self.start:
            raise ValueError("resolved temporal anchor end precedes start")
        return self


class ProposedDateWindow(ContractModel):
    start: date
    end: date
    supporting_text: list[str] = Field(min_length=1)
    interpretation: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_order(self) -> ProposedDateWindow:
        if self.end < self.start:
            raise ValueError("proposed date window end precedes start")
        return self


class UnresolvedTemporalConstraint(ContractModel):
    field: Literal["departure", "return_or_duration", "dates"]
    raw_text: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class InterpretedDuration(ContractModel):
    raw_text: str = Field(min_length=1)
    minimum_days: int = Field(ge=1, le=365)
    maximum_days: int = Field(ge=1, le=365)

    @model_validator(mode="after")
    def validate_order(self) -> InterpretedDuration:
        if self.maximum_days < self.minimum_days:
            raise ValueError("maximum duration precedes minimum duration")
        return self


class DateResolutionProposal(ContractModel):
    """Deterministically evaluated temporal result retained for trace compatibility."""

    departure: ProposedDateWindow | None = None
    return_date: ProposedDateWindow | None = None
    interpreted_duration: InterpretedDuration | None = None
    unresolved: list[UnresolvedTemporalConstraint] = Field(default_factory=list)


class TemporalDirection(str, Enum):
    BEFORE = "before"
    AFTER = "after"


class TemporalEdge(str, Enum):
    START = "start"
    END = "end"


class TemporalComposition(str, Enum):
    """How a relation changes the window already selected for its target.

    This is deliberately a small, executable vocabulary rather than a general temporal-logic
    language. The values are compiler-authored and interpreted only by deterministic code.
    """

    BASE = "base"
    INTERSECT = "intersect"
    UNION = "union"
    EXTEND_START = "extend_start"
    EXTEND_END = "extend_end"
    EXCLUDE = "exclude"
    ALTERNATIVE = "alternative"


class DurationReferenceScope(str, Enum):
    """Whether a duration applies to one date edge or every date in a departure interval."""

    EDGE = "edge"
    WHOLE_INTERVAL = "whole_interval"


class TemporalUnit(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class DurationModifier(str, Enum):
    """Literal linguistic shape of a stated duration.

    Deterministic normalization applies a one-day tolerance to approximate
    durations after converting the stated quantity. Thus ``about a week`` is
    six through eight days. Alternative durations preserve their literal
    endpoints without adding approximation tolerance.
    """

    EXACT = "exact"
    APPROXIMATE = "approximate"
    ALTERNATIVE = "alternative"


class CalendarPeriodSemantics(str, Enum):
    WHOLE = "whole"
    PARTIAL = "partial"


class AnchorReference(ContractModel):
    kind: Literal["anchor"]
    anchor_id: str = Field(min_length=1)
    edge: TemporalEdge = TemporalEdge.END


class RequestFieldReference(ContractModel):
    kind: Literal["request_field"]
    field: TemporalTarget
    scope: DurationReferenceScope = DurationReferenceScope.EDGE
    edge: TemporalEdge | None = TemporalEdge.END

    @model_validator(mode="after")
    def validate_scope(self) -> RequestFieldReference:
        if self.scope is DurationReferenceScope.WHOLE_INTERVAL and self.edge is not None:
            raise ValueError("whole_interval request-field references cannot select an edge")
        if self.scope is DurationReferenceScope.EDGE and self.edge is None:
            raise ValueError("edge request-field references require an edge")
        return self


class DecisionReference(ContractModel):
    """Reference the evaluated output of an earlier canonical relation."""

    kind: Literal["decision"]
    constraint_id: str = Field(min_length=1)
    edge: TemporalEdge


class SymbolicContextReference(ContractModel):
    """Opaque context reference whose concrete value remains outside model-facing data."""

    kind: Literal["symbolic_context"]
    key: Literal["context:request_date"]


TemporalReference = Annotated[
    AnchorReference | RequestFieldReference | DecisionReference,
    Field(discriminator="kind"),
]


class TemporalConstraintBase(ContractModel):
    """Canonical graph metadata supplied by deterministic Pass-2 assembly."""

    constraint_id: str | None = Field(default=None, min_length=1)
    combine: TemporalComposition = TemporalComposition.BASE
    combine_with: str | None = Field(default=None, min_length=1)


class AnchorWindowConstraint(TemporalConstraintBase):
    kind: Literal["anchor_window"]
    target: TemporalTarget
    anchor_id: str = Field(min_length=1)
    window: Literal["anchor", "holiday_weekend", "christmas_period"]
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class RelativeWeekendConstraint(TemporalConstraintBase):
    kind: Literal["relative_weekend"]
    target: TemporalTarget
    reference: TemporalReference
    direction: TemporalDirection
    ordinal: int = Field(ge=1, le=52)
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class RelativeWeekdayConstraint(TemporalConstraintBase):
    kind: Literal["relative_weekday"]
    target: TemporalTarget
    reference: TemporalReference
    direction: TemporalDirection
    ordinal: int = Field(default=1, ge=1, le=52)
    weekday: Weekday
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class RelativeOffsetConstraint(TemporalConstraintBase):
    kind: Literal["relative_offset"]
    target: TemporalTarget
    reference: TemporalReference
    direction: TemporalDirection
    amount: int = Field(ge=1, le=365)
    unit: TemporalUnit
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class RelativeCalendarPeriodConstraint(TemporalConstraintBase):
    """A calendar period relative to hidden context, not a point offset."""

    kind: Literal["relative_calendar_period"]
    target: TemporalTarget
    reference: SymbolicContextReference
    direction: TemporalDirection
    unit: Literal[TemporalUnit.MONTH]
    ordinal: int = Field(ge=1, le=120)
    period_semantics: CalendarPeriodSemantics
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class SemanticDurationConstraint(TemporalConstraintBase):
    kind: Literal["duration"]
    target: Literal[TemporalTarget.RETURN] = TemporalTarget.RETURN
    reference: RequestFieldReference
    stated_minimum_quantity: int = Field(ge=1, le=365)
    stated_maximum_quantity: int = Field(ge=1, le=365)
    unit: TemporalUnit
    modifier: DurationModifier
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> SemanticDurationConstraint:
        if self.stated_maximum_quantity < self.stated_minimum_quantity:
            raise ValueError("maximum stated duration precedes minimum stated duration")
        quantities_differ = self.stated_maximum_quantity != self.stated_minimum_quantity
        if self.modifier is DurationModifier.ALTERNATIVE and not quantities_differ:
            raise ValueError("alternative duration requires distinct stated quantities")
        if self.modifier is not DurationModifier.ALTERNATIVE and quantities_differ:
            raise ValueError("exact and approximate durations require one stated quantity")
        if self.reference.field is not TemporalTarget.DEPARTURE:
            raise ValueError("duration reference must be the departure request field")
        # Legacy graphs may retain an edge reference while being migrated.  Pass-2 Contract v2
        # assembly always emits ``whole_interval``; deterministic evaluation preserves the
        # historical full-window behavior for old, persisted test graphs.
        return self


class MonthPortionConstraint(TemporalConstraintBase):
    kind: Literal["month_portion"]
    target: TemporalTarget
    anchor_id: str = Field(min_length=1)
    portion: Literal["early", "mid", "late", "whole"]
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class UnboundedBoundaryConstraint(TemporalConstraintBase):
    kind: Literal["unbounded_boundary"]
    target: TemporalTarget
    reference: TemporalReference
    direction: TemporalDirection
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)


class UnresolvedRelationConstraint(TemporalConstraintBase):
    kind: Literal["unresolved"]
    target: TemporalTarget | None = None
    raw_text: str = Field(min_length=1)
    occurrence_index: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=1)


TemporalConstraint = Annotated[
    AnchorWindowConstraint
    | RelativeWeekendConstraint
    | RelativeWeekdayConstraint
    | RelativeOffsetConstraint
    | RelativeCalendarPeriodConstraint
    | SemanticDurationConstraint
    | MonthPortionConstraint
    | UnboundedBoundaryConstraint
    | UnresolvedRelationConstraint,
    Field(discriminator="kind"),
]


class TemporalRelationGraph(ContractModel):
    """Grounded semantic constraints emitted by the second model pass."""

    constraints: list[TemporalConstraint] = Field(default_factory=list)


class DateFlexibilityTarget(str, Enum):
    DEPARTURE = "departure"
    RETURN = "return"


class DateFlexibilityMode(str, Enum):
    INCLUDE = "include"


class DateFlexibility(ContractModel):
    applies_to: DateFlexibilityTarget
    mode: DateFlexibilityMode
    expression: DateExpression = Field(
        description=(
            "Additional date meaning included relative to the primary date expression. "
            "preceding_weekday is strictly before the primary window; following_weekday "
            "is strictly after it."
        )
    )


class IntentExtraction(ContractModel):
    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    departure: DateExpression | None = None
    return_date: DateExpression | None = Field(
        default=None,
        description="An explicit return-date phrase only; never derive this from trip duration.",
    )
    duration: DurationConstraint | None = Field(
        default=None,
        description="Stated trip length; deterministic code derives return dates from this.",
    )
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    date_flexibility: list[DateFlexibility] = Field(default_factory=list)
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
    evidence: list[GroundedTemporalEvidence] = Field(default_factory=list)


class Conflict(ContractModel):
    code: str
    fields: list[str]
    detail: str
    evidence_by_alternative: dict[str, list[GroundedTemporalEvidence]] = Field(default_factory=dict)


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
    date_flexibility: list[DateFlexibility]
    repositioning_allowed: bool | None
    hard_constraints: list[str]
    unknowns: list[UnknownField]
    conflicts: list[Conflict]
    temporal_extraction: CoarseIntentExtraction | None = None
    temporal_evidence: list[GroundedTemporalEvidence] = Field(default_factory=list)
    resolved_date_anchors: list[ResolvedTemporalAnchor] = Field(default_factory=list)
    temporal_relations: TemporalRelationGraph | None = None
    date_resolution: DateResolutionProposal | None = None


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
