# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined"
"""OpenAI adapter for the initial semantic receiver.

The provider sees ``WireIntentProposal``, not the stricter domain proposal.
Its fixed containers avoid tagged unions and an irrelevant nullable-field matrix.
Translation is structural only: it never reads request language or computes dates.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from award_agent.domain import CabinClass, Holiday, LocationKind, SearchMode
from award_agent.intent.semantic import (
    CalendarAnchorEdge,
    CalendarAnchorKind,
    CalendarOperationKind,
    CalendarPeriodSlice,
    SemanticFact,
    SemanticFactTarget,
    SemanticIntentInput,
    SemanticIntentProposal,
    SemanticScopeKind,
    SemanticScopeNotice,
    SemanticTemporalFact,
    SemanticTemporalTarget,
    SemanticUnresolved,
    SemanticValidationIssue,
)
from award_agent.observability.llm_trace import LLMCallTraceCollector, response_schema_sha256

OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION = "openai_semantic_intent_wire_v2"

_INSTRUCTIONS = """Interpret this initial award-travel request as structured data only.
You own natural-language meaning: reasonable paraphrases and typos should map to the same generic
fact or calendar calculation. Ground every component with its exact quote and a zero-based
occurrence only when that exact quote repeats. Do not invent missing values or calculate final
dates. Each output array identifies its component type; do not move a fact into another array.

For a stated calendar month and day with no explicit year, always use
literal_single_departures with start_year 0. For a stated date range without an explicit year,
use literal_range_departures with start_year and end_year 0. Missing year is not ambiguity and
must never be put in unresolved just because it is absent: deterministic code chooses the next
occurrence from private request context.

Return all non-temporal facts, explicit ambiguities/unresolved fragments, and generic outbound
calendar operations. A literal interval names calendar components; a recurring interval uses a
request-date, holiday, or earlier-fact anchor plus weekday; an offset interval uses a typed anchor
and day offsets. For example, Friday after Thanksgiving is a recurring interval anchored to
holiday Thanksgiving, weekday Friday, strictly_after true. Never create phrase-specific operation
names. Use unresolved only for genuinely ambiguous or unbounded timing. Classify return timing and
trip duration only with return_notices or duration_notices; never as outbound calendar operations.
Extract award and cash search modes explicitly. Do not expand cities into airports."""


class _WireModel(BaseModel):
    """Provider-safe DTO base: no unions, validators, or optional fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class _WireQuote(_WireModel):
    component_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1)
    # -1 is neutral for a quote that occurs only once.
    occurrence_index: int = Field(default=-1, ge=-1)


class WireOrigin(_WireQuote):
    location_kind: LocationKind
    location_value: str = Field(min_length=1)


class WireDestination(WireOrigin):
    pass


class WireTravelers(_WireQuote):
    travelers: int = Field(ge=1)


class WireCabin(_WireQuote):
    cabin: CabinClass


class WireMode(_WireQuote):
    search_mode: SearchMode


class WireRepositioning(_WireQuote):
    repositioning_allowed: bool


class WireConstraint(_WireQuote):
    hard_constraint: str = Field(min_length=1)


class WireLiteralSingleDeparture(_WireQuote):
    start_year: int = Field(
        default=0,
        ge=0,
        le=9999,
        description="Explicit year, or 0 when the request states only month and day; 0 means deterministic next occurrence.",
    )
    start_month: int = Field(ge=1, le=12)
    start_day: int = Field(ge=1, le=31)
    approximate: bool = False


class WireLiteralRangeDeparture(WireLiteralSingleDeparture):
    end_year: int = Field(default=0, ge=0, le=9999)
    end_month: int = Field(ge=1, le=12)
    end_day: int = Field(ge=1, le=31)


class WireCalendarPeriodDeparture(_WireQuote):
    basis: Literal["named_month", "request_relative"]
    period_month: int = Field(default=0, ge=0, le=12)
    period_year: int = Field(default=0, ge=0, le=9999)
    period_offset_months: int = Field(default=0, ge=0, le=24)
    period_slice: CalendarPeriodSlice
    approximate: bool = False


class WireRecurringDeparture(_WireQuote):
    anchor_kind: CalendarAnchorKind
    anchor_holiday: str = ""
    anchor_year: int = Field(default=0, ge=0, le=9999)
    anchor_fact_id: str = ""
    anchor_edge: Literal["start", "end"] = "start"
    weekday: int = Field(ge=0, le=6)
    strictly_after: bool = False
    cycles_after_anchor: int = Field(default=0, ge=0, le=104)
    span_days: int = Field(default=1, ge=1, le=31)
    approximate: bool = False


class WireOffsetDeparture(_WireQuote):
    anchor_kind: CalendarAnchorKind
    anchor_holiday: str = ""
    anchor_year: int = Field(default=0, ge=0, le=9999)
    anchor_fact_id: str = ""
    anchor_edge: Literal["start", "end"] = "start"
    start_offset_days: int = Field(ge=-730, le=730)
    # 10000 is neutral for omitted end offset (outside the valid day range).
    end_offset_days: int = Field(default=10000, ge=-730, le=10000)
    approximate: bool = False


class WireUnresolved(_WireQuote):
    field: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=300)
    operation_recheck: bool = False


class WireScopeNotice(_WireQuote):
    pass


class WireIntentProposal(_WireModel):
    origins: tuple[WireOrigin, ...] = ()
    destinations: tuple[WireDestination, ...] = ()
    travelers: tuple[WireTravelers, ...] = ()
    cabins: tuple[WireCabin, ...] = ()
    modes: tuple[WireMode, ...] = ()
    repositioning: tuple[WireRepositioning, ...] = ()
    constraints: tuple[WireConstraint, ...] = ()
    literal_single_departures: tuple[WireLiteralSingleDeparture, ...] = ()
    literal_range_departures: tuple[WireLiteralRangeDeparture, ...] = ()
    calendar_period_departures: tuple[WireCalendarPeriodDeparture, ...] = ()
    recurring_departures: tuple[WireRecurringDeparture, ...] = ()
    offset_departures: tuple[WireOffsetDeparture, ...] = ()
    unresolved: tuple[WireUnresolved, ...] = ()
    return_notices: tuple[WireScopeNotice, ...] = ()
    duration_notices: tuple[WireScopeNotice, ...] = ()


class OpenAISemanticIntentError(RuntimeError):
    pass


class OpenAISemanticIntentRepresentationError(OpenAISemanticIntentError):
    """Inference reached a wire/structural boundary which needs repair."""

    def __init__(
        self,
        wire: WireIntentProposal,
        errors: tuple[SemanticValidationIssue, ...],
        partial: SemanticIntentProposal | None = None,
    ):
        super().__init__("semantic wire proposal could not be structurally converted")
        self.wire, self.errors, self.partial = wire, errors, partial


def _occurrence(value: int) -> int | None:
    return None if value == -1 else value


def _component_issue(component_id: str, exc: Exception) -> SemanticValidationIssue:
    return SemanticValidationIssue(
        code="semantic_wire_conversion_failed",
        path=("components", component_id),
        detail=str(exc)[:500],
    )


def _anchor_values(item: WireRecurringDeparture | WireOffsetDeparture) -> dict[str, object]:
    # Do not accept inactive anchor payload as harmless noise.  The fixed wire
    # schema expresses absence with neutral values, and this structural check
    # turns a contradictory combination into the one semantic repair rather
    # than choosing an arbitrary populated field.
    if item.anchor_kind is CalendarAnchorKind.HOLIDAY and not item.anchor_holiday:
        raise ValueError("holiday anchor requires anchor_holiday")
    if item.anchor_kind is CalendarAnchorKind.PRIOR_FACT and not item.anchor_fact_id:
        raise ValueError("prior-fact anchor requires anchor_fact_id")
    if item.anchor_kind is CalendarAnchorKind.REQUEST_DATE and (
        item.anchor_holiday or item.anchor_year or item.anchor_fact_id
    ):
        raise ValueError("request-date anchor cannot carry another anchor value")
    if item.anchor_kind is CalendarAnchorKind.HOLIDAY and item.anchor_fact_id:
        raise ValueError("holiday anchor cannot carry anchor_fact_id")
    if item.anchor_kind is CalendarAnchorKind.PRIOR_FACT and (
        item.anchor_holiday or item.anchor_year
    ):
        raise ValueError("prior-fact anchor cannot carry holiday values")
    return {
        "anchor_kind": item.anchor_kind,
        "anchor_holiday": Holiday(item.anchor_holiday) if item.anchor_holiday else None,
        "anchor_year": item.anchor_year or None,
        "anchor_fact_id": item.anchor_fact_id or None,
        "anchor_edge": CalendarAnchorEdge(item.anchor_edge),
    }


def wire_to_semantic(wire: WireIntentProposal) -> SemanticIntentProposal:
    """Independently convert wire components without examining request text."""
    facts: list[SemanticFact] = []
    temporal: list[SemanticTemporalFact] = []
    unresolved: list[SemanticUnresolved] = []
    notices: list[SemanticScopeNotice] = []
    errors: list[SemanticValidationIssue] = []
    for items, target, names in (
        (wire.origins, SemanticFactTarget.ORIGIN, ("location_kind", "location_value")),
        (wire.destinations, SemanticFactTarget.DESTINATION, ("location_kind", "location_value")),
        (wire.travelers, SemanticFactTarget.TRAVELERS, ("travelers",)),
        (wire.cabins, SemanticFactTarget.CABIN, ("cabin",)),
        (wire.modes, SemanticFactTarget.SEARCH_MODE, ("search_mode",)),
        (wire.repositioning, SemanticFactTarget.REPOSITIONING, ("repositioning_allowed",)),
        (wire.constraints, SemanticFactTarget.HARD_CONSTRAINT, ("hard_constraint",)),
    ):
        for item in items:
            try:
                facts.append(SemanticFact(component_id=item.component_id, target=target, quote=item.quote,
                    occurrence_index=_occurrence(item.occurrence_index), **{name: getattr(item, name) for name in names}))
            except (ValidationError, ValueError) as exc:
                errors.append(_component_issue(item.component_id, exc))

    def add_temporal(item: _WireQuote, **values: object) -> None:
        try:
            temporal.append(SemanticTemporalFact(component_id=item.component_id, fact_id=item.component_id,
                target=SemanticTemporalTarget.DEPARTURE, quote=item.quote,
                occurrence_index=_occurrence(item.occurrence_index), **values))
        except (ValidationError, ValueError) as exc:
            errors.append(_component_issue(item.component_id, exc))

    for item in wire.literal_single_departures:
        add_temporal(item, operation=CalendarOperationKind.LITERAL_INTERVAL,
            start_year=item.start_year or None, start_month=item.start_month, start_day=item.start_day,
            approximate=item.approximate)
    for item in wire.literal_range_departures:
        add_temporal(item, operation=CalendarOperationKind.LITERAL_INTERVAL,
            start_year=item.start_year or None, start_month=item.start_month, start_day=item.start_day,
            end_year=item.end_year or None, end_month=item.end_month, end_day=item.end_day,
            approximate=item.approximate)
    for item in wire.calendar_period_departures:
        if (item.basis == "named_month" and item.period_offset_months) or (
            item.basis == "request_relative" and (item.period_month or item.period_year)
        ):
            errors.append(_component_issue(item.component_id, ValueError("calendar period has inactive populated fields")))
            continue
        add_temporal(item, operation=CalendarOperationKind.CALENDAR_PERIOD,
            period_month=(item.period_month or None) if item.basis == "named_month" else None,
            period_year=(item.period_year or None) if item.basis == "named_month" else None,
            period_offset_months=item.period_offset_months if item.basis == "request_relative" else None,
            period_slice=item.period_slice, approximate=item.approximate)
    for item in wire.recurring_departures:
        try:
            anchors = _anchor_values(item)
        except ValueError as exc:
            errors.append(_component_issue(item.component_id, exc)); continue
        add_temporal(item, operation=CalendarOperationKind.RECURRING_INTERVAL, **anchors,
            weekday=item.weekday, strictly_after=item.strictly_after,
            cycles_after_anchor=item.cycles_after_anchor, span_days=item.span_days, approximate=item.approximate)
    for item in wire.offset_departures:
        try:
            anchors = _anchor_values(item)
        except ValueError as exc:
            errors.append(_component_issue(item.component_id, exc)); continue
        add_temporal(item, operation=CalendarOperationKind.OFFSET_INTERVAL, **anchors,
            start_offset_days=item.start_offset_days,
            end_offset_days=None if item.end_offset_days == 10000 else item.end_offset_days,
            approximate=item.approximate)
    for item in wire.unresolved:
        try:
            unresolved.append(SemanticUnresolved(component_id=item.component_id, field=item.field, quote=item.quote,
                occurrence_index=_occurrence(item.occurrence_index), reason=item.reason,
                operation_recheck=item.operation_recheck))
        except (ValidationError, ValueError) as exc:
            errors.append(_component_issue(item.component_id, exc))
    for items, kind in ((wire.return_notices, SemanticScopeKind.RETURN), (wire.duration_notices, SemanticScopeKind.DURATION)):
        for item in items:
            try:
                notices.append(SemanticScopeNotice(component_id=item.component_id, kind=kind, quote=item.quote,
                    occurrence_index=_occurrence(item.occurrence_index)))
            except (ValidationError, ValueError) as exc:
                errors.append(_component_issue(item.component_id, exc))
    try:
        SemanticIntentProposal(facts=tuple(facts), temporal_facts=tuple(temporal), unresolved=tuple(unresolved), scope_notices=tuple(notices))
    except (ValidationError, ValueError) as exc:
        errors.append(SemanticValidationIssue(code="semantic_wire_conversion_failed", path=("proposal",), detail=str(exc)[:500]))
    if errors:
        partial = SemanticIntentProposal.model_construct(
            facts=tuple(facts), temporal_facts=tuple(temporal), unresolved=tuple(unresolved), scope_notices=tuple(notices)
        )
        raise OpenAISemanticIntentRepresentationError(wire, tuple(errors), partial)
    return SemanticIntentProposal(facts=tuple(facts), temporal_facts=tuple(temporal), unresolved=tuple(unresolved), scope_notices=tuple(notices))


def _component_ids(errors: tuple[SemanticValidationIssue, ...]) -> set[str]:
    return {item.path[-1] for item in errors if len(item.path) >= 2 and item.path[-2] == "components"}


def _merge_wire(original: WireIntentProposal, repaired: WireIntentProposal, errors: tuple[SemanticValidationIssue, ...]) -> WireIntentProposal:
    """Replace rejected component IDs, preserving every valid old sibling."""
    rejected = _component_ids(errors)
    if not rejected:
        if any(getattr(original, name) for name in WireIntentProposal.model_fields):
            raise ValueError("component repair requires rejected component IDs")
        return repaired
    data: dict[str, list[object]] = {name: [] for name in WireIntentProposal.model_fields}
    old_ids: set[str] = set()
    for name in WireIntentProposal.model_fields:
        for item in getattr(original, name):
            if item.component_id in old_ids:
                raise ValueError("wire proposal has duplicate component IDs")
            old_ids.add(item.component_id)
            if item.component_id not in rejected:
                data[name].append(item)
    replacement_ids: set[str] = set()
    for name in WireIntentProposal.model_fields:
        for item in getattr(repaired, name):
            if item.component_id not in rejected:
                # A repair is component-scoped: unrelated additions are never
                # accepted implicitly and cannot duplicate scalar facts.
                continue
            if item.component_id in replacement_ids:
                raise ValueError("wire repair has duplicate replacement component IDs")
            replacement_ids.add(item.component_id)
            data[name].append(item)
    return WireIntentProposal(**data)


def semantic_intent_adapter_contract_metadata() -> dict[str, str]:
    return {
        "adapter_contract_version": OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION,
        "adapter_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "strict_response_schema_sha256": response_schema_sha256(WireIntentProposal),
    }


@dataclass(frozen=True, slots=True)
class OpenAISemanticIntentConfig:
    model: str

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("model must not be empty")


class OpenAISemanticIntentInterpreter:
    def __init__(self, config: OpenAISemanticIntentConfig, client: OpenAI | None = None, *, capture_llm_io: bool = False) -> None:
        self.config, self._client = config, client or OpenAI()
        self._trace = LLMCallTraceCollector(enabled=capture_llm_io)
        self._usage: list[dict[str, int]] = []
        self._calls = 0

    def reset_capture(self) -> None:
        self._trace.reset(); self._usage = []; self._calls = 0

    def take_call_traces(self) -> list[dict[str, Any]]:
        return self._trace.take()

    def take_usage(self) -> dict[str, int] | None:
        records, calls = self._usage, self._calls
        self._usage, self._calls = [], 0
        if not records:
            return None
        return {"calls": calls, "captured_calls": len(records), "missing_calls": calls - len(records),
            "input_tokens": sum(x["input_tokens"] for x in records), "output_tokens": sum(x["output_tokens"] for x in records),
            "total_tokens": sum(x["total_tokens"] for x in records)}

    def _call(self, stage: str, input: SemanticIntentInput, instructions: str, *, payload_data: dict[str, object] | None = None) -> WireIntentProposal:
        payload = json.dumps(payload_data or input.model_dump(mode="json"), separators=(",", ":"))
        started = time.perf_counter(); self._calls += 1
        try:
            response = self._client.responses.parse(model=self.config.model, instructions=instructions, input=payload, text_format=WireIntentProposal, store=False)
        except ValidationError as exc:
            # The SDK reached response parsing but its DTO validation failed.
            # Treat that as a model-owned representation repair, not an
            # ordinary-language outage.  There is no trustworthy partial DTO
            # to merge in this exceptional SDK path, so use the empty wire
            # only as a typed repair envelope.
            self._trace.record(stage=stage, model=self.config.model, instructions=instructions, payload=payload, text_format=WireIntentProposal, adapter_version=OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION, provider_stage="inference_reached_parse_failed", error=exc, latency_seconds=time.perf_counter() - started)
            raise OpenAISemanticIntentRepresentationError(
                WireIntentProposal(),
                (SemanticValidationIssue(code="provider_wire_parse_failed", path=("provider_output",), detail=str(exc)[:500]),),
            ) from exc
        except Exception as exc:
            self._trace.record(stage=stage, model=self.config.model, instructions=instructions, payload=payload, text_format=WireIntentProposal, adapter_version=OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION, provider_stage="pre_inference_or_transport", error=exc, latency_seconds=time.perf_counter() - started)
            raise OpenAISemanticIntentError("OpenAI semantic intent interpretation failed") from exc
        if response.output_parsed is None:
            self._trace.record(stage=stage, model=self.config.model, instructions=instructions, payload=payload, text_format=WireIntentProposal, adapter_version=OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION, provider_stage="inference_reached_parse_failed", response=response, error=ValueError("provider_wire_output_missing"), latency_seconds=time.perf_counter() - started)
            raise OpenAISemanticIntentRepresentationError(
                WireIntentProposal(),
                (SemanticValidationIssue(code="provider_wire_output_missing", path=("provider_output",), detail="provider returned no parsed wire output"),),
            )
        if not isinstance(response.output_parsed, WireIntentProposal):
            self._trace.record(stage=stage, model=self.config.model, instructions=instructions, payload=payload, text_format=WireIntentProposal, adapter_version=OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION, provider_stage="inference_reached_parse_failed", response=response, error=ValueError("provider_wire_output_wrong_type"), latency_seconds=time.perf_counter() - started)
            raise OpenAISemanticIntentRepresentationError(
                WireIntentProposal(),
                (
                    SemanticValidationIssue(
                        code="provider_wire_output_wrong_type",
                        path=("provider_output",),
                        detail="provider returned a non-wire parsed output",
                    ),
                ),
            )
        self._trace.record(stage=stage, model=self.config.model, instructions=instructions, payload=payload, text_format=WireIntentProposal, adapter_version=OPENAI_SEMANTIC_INTENT_ADAPTER_VERSION, provider_stage="inference_reached", response=response, latency_seconds=time.perf_counter() - started)
        usage = getattr(response, "usage", None)
        if usage is not None:
            data = usage if isinstance(usage, dict) else usage.model_dump(mode="json")
            if isinstance(data.get("input_tokens"), int) and isinstance(data.get("output_tokens"), int):
                self._usage.append({"input_tokens": data["input_tokens"], "output_tokens": data["output_tokens"], "total_tokens": data.get("total_tokens", data["input_tokens"] + data["output_tokens"])})
        return response.output_parsed

    def interpret(self, input: SemanticIntentInput) -> SemanticIntentProposal:
        return wire_to_semantic(self._call("initial_semantic_intent", input, _INSTRUCTIONS))

    def repair_wire(self, input: SemanticIntentInput, *, wire: WireIntentProposal, errors: tuple[SemanticValidationIssue, ...]) -> SemanticIntentProposal:
        instructions = _INSTRUCTIONS + "\nRepair only rejected component IDs; preserve other IDs. Errors: " + json.dumps([x.model_dump(mode="json") for x in errors])
        repaired = self._call("initial_semantic_intent_repair", input, instructions, payload_data={"request": input.model_dump(mode="json"), "rejected_wire_proposal": wire.model_dump(mode="json"), "validation_errors": [x.model_dump(mode="json") for x in errors]})
        return wire_to_semantic(_merge_wire(wire, repaired, errors))

    def repair(self, input: SemanticIntentInput, *, proposal: SemanticIntentProposal, errors: tuple[SemanticValidationIssue, ...]) -> SemanticIntentProposal:
        return self.repair_wire(input, wire=_semantic_to_wire(proposal), errors=errors)


def _semantic_to_wire(proposal: SemanticIntentProposal) -> WireIntentProposal:
    """Lossless structural projection used only for a repair payload."""
    def cid(value: str | None, prefix: str, index: int) -> str: return value or f"{prefix}-{index}"
    values: dict[str, list[object]] = {name: [] for name in WireIntentProposal.model_fields}
    for index, fact in enumerate(proposal.facts):
        base = {"component_id": cid(fact.component_id, "fact", index), "quote": fact.quote, "occurrence_index": fact.occurrence_index if fact.occurrence_index is not None else -1}
        mapping = {
            SemanticFactTarget.ORIGIN: ("origins", WireOrigin, {"location_kind": fact.location_kind, "location_value": fact.location_value}),
            SemanticFactTarget.DESTINATION: ("destinations", WireDestination, {"location_kind": fact.location_kind, "location_value": fact.location_value}),
            SemanticFactTarget.TRAVELERS: ("travelers", WireTravelers, {"travelers": fact.travelers}),
            SemanticFactTarget.CABIN: ("cabins", WireCabin, {"cabin": fact.cabin}),
            SemanticFactTarget.SEARCH_MODE: ("modes", WireMode, {"search_mode": fact.search_mode}),
            SemanticFactTarget.REPOSITIONING: ("repositioning", WireRepositioning, {"repositioning_allowed": fact.repositioning_allowed}),
            SemanticFactTarget.HARD_CONSTRAINT: ("constraints", WireConstraint, {"hard_constraint": fact.hard_constraint}),
        }
        name, cls, extra = mapping[fact.target]; values[name].append(cls(**base, **extra))
    for index, fact in enumerate(proposal.temporal_facts):
        base = {"component_id": cid(fact.component_id or fact.fact_id, "temporal", index), "quote": fact.quote, "occurrence_index": fact.occurrence_index if fact.occurrence_index is not None else -1}
        if fact.operation is CalendarOperationKind.LITERAL_INTERVAL:
            if fact.end_month is None:
                values["literal_single_departures"].append(WireLiteralSingleDeparture(**base, start_year=fact.start_year or 0, start_month=fact.start_month or 1, start_day=fact.start_day or 1, approximate=fact.approximate))
            else:
                values["literal_range_departures"].append(WireLiteralRangeDeparture(**base, start_year=fact.start_year or 0, start_month=fact.start_month or 1, start_day=fact.start_day or 1, end_year=fact.end_year or 0, end_month=fact.end_month, end_day=fact.end_day or 1, approximate=fact.approximate))
        elif fact.operation is CalendarOperationKind.CALENDAR_PERIOD:
            relative = fact.period_offset_months is not None
            values["calendar_period_departures"].append(WireCalendarPeriodDeparture(**base, basis="request_relative" if relative else "named_month", period_month=0 if relative else fact.period_month or 0, period_year=0 if relative else fact.period_year or 0, period_offset_months=fact.period_offset_months or 0, period_slice=fact.period_slice or CalendarPeriodSlice.WHOLE, approximate=fact.approximate))
        elif fact.operation is CalendarOperationKind.RECURRING_INTERVAL:
            values["recurring_departures"].append(WireRecurringDeparture(**base, anchor_kind=fact.anchor_kind or CalendarAnchorKind.REQUEST_DATE, anchor_holiday=fact.anchor_holiday.value if fact.anchor_holiday else "", anchor_year=fact.anchor_year or 0, anchor_fact_id=fact.anchor_fact_id or "", anchor_edge=(fact.anchor_edge or CalendarAnchorEdge.START).value, weekday=fact.weekday or 0, strictly_after=bool(fact.strictly_after), cycles_after_anchor=fact.cycles_after_anchor or 0, span_days=fact.span_days or 1, approximate=fact.approximate))
        elif fact.operation is CalendarOperationKind.OFFSET_INTERVAL:
            values["offset_departures"].append(WireOffsetDeparture(**base, anchor_kind=fact.anchor_kind or CalendarAnchorKind.REQUEST_DATE, anchor_holiday=fact.anchor_holiday.value if fact.anchor_holiday else "", anchor_year=fact.anchor_year or 0, anchor_fact_id=fact.anchor_fact_id or "", anchor_edge=(fact.anchor_edge or CalendarAnchorEdge.START).value, start_offset_days=fact.start_offset_days or 0, end_offset_days=fact.end_offset_days if fact.end_offset_days is not None else 10000, approximate=fact.approximate))
    for index, item in enumerate(proposal.unresolved):
        values["unresolved"].append(WireUnresolved(component_id=cid(item.component_id, "unresolved", index), quote=item.quote, occurrence_index=item.occurrence_index if item.occurrence_index is not None else -1, field=item.field, reason=item.reason, operation_recheck=item.operation_recheck))
    for index, item in enumerate(proposal.scope_notices):
        name = "return_notices" if item.kind is SemanticScopeKind.RETURN else "duration_notices"
        values[name].append(WireScopeNotice(component_id=cid(item.component_id, "scope", index), quote=item.quote, occurrence_index=item.occurrence_index if item.occurrence_index is not None else -1))
    return WireIntentProposal(**values)
