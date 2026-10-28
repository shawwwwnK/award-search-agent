"""Isolated, reversible writer-input candidate for the Luna latency diagnostic.

The four-field factoring follows ../2026-10-25-latency/factor.py. All added
identity and schedule facts are copies of the existing compact authoring view;
the canonical Ranking projection and Results runtime are untouched.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from award_agent.results.structured_contracts import StructuredPreparedInput

FACT_FIELDS = ("reasons", "cost", "assessments", "positioning_reason")
SCHEDULE_FIELDS = ("origin", "destination", "departure", "arrival", "elapsed_minutes",
                   "transfer_airport", "transfer_minutes", "transfer_local_day_offset")
AWARD_FIELDS = ("program", "points", "taxes_fees", "taxes_fees_unit", "tax_currency",
                "price_scope", "returned_travelers", "seats")
CASH_FIELDS = ("cash_amount", "cash_currency", "price_scope", "returned_travelers")
GUIDE = (
    "\n\nExact-choice reading guide: each journey group's facts give the whole-journey "
    "route, full dated departure/arrival, duration, cabin and booking obligation "
    "for every member in that group. Each member's choice.award_quote and "
    "choice.cash_quote copy only its exact referenced component's reported facts; "
    "state=unknown or absent and unknown price_scope remain unknown. Never move a "
    "quote, cabin, seat or booking fact between J members. reasons_ref, cost_ref, "
    "assessments_ref and positioning_reason_ref are zero-based indexes into the "
    "same-named journey_fact_catalog arrays; use each full indexed value as the "
    "group fact. same_schedule lists all J members by matching reported route, "
    "full timestamps, duration and transfer facts. An unknown schedule is listed "
    "alone and proves no timing relationship; matching does not prove the "
    "same physical flights, price, cabin, booking or availability. Compare cabins "
    "and arrival timing separately across meaningful alternatives, especially an "
    "economy option matching a business option's schedule. Do not assume a "
    "schedule improvement is purchased by a cabin upgrade when an eligible "
    "same-schedule economy choice exists.\n"
    "Reference contract: journey references are exact J aliases from journey "
    "members. Direct cash benchmark references must be aliases listed in "
    "benchmarks, never a positioning component; select at most one benchmark "
    "and emit only that selected benchmark's reference. Incomplete lead references "
    "must be aliases listed in incomplete_leads; another component is not a lead. "
    "An eligible unselected J may appear as a supported alternative reference; "
    "every selected journey still needs its own labeled reference block. Every "
    "lead reference block must match a selected incomplete lead. Narrative blocks must "
    "have null reference_kind and reference_id and claims=[]. Empty claims are "
    "valid on reference blocks too. If a "
    "claim is declared, copy its literal into that reference block's text, use "
    "its exact supported scope aliases, and use P1 only for a supported full-pool "
    "comparison. Do not add an unsupported claim merely to describe a choice.\n"
)


def compact(value: Any, *, sort_keys: bool = True) -> str:
    return json.dumps(value, sort_keys=sort_keys, ensure_ascii=False, separators=(",", ":"))


def inventories(view: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "journeys": sorted(member["ref"] for group in view["journeys"]
                           for member in group["members"]),
        "components": sorted(member["ref"] for group in view["components"]
                             for member in group["members"]),
        "benchmarks": sorted(view["benchmarks"]),
        "leads": sorted(lead["ref"] for lead in view["incomplete_leads"]),
    }


def _component_by_ref(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in view["components"]:
        for member in group["members"]:
            alias = member["ref"]
            if alias in result:
                raise ValueError(f"duplicate component alias: {alias}")
            result[alias] = group["facts"]
    return result


def _choice(member: dict[str, Any], components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    award = components[member["award"]]
    if award["kind"] == "cash_itinerary":
        raise ValueError("journey award alias points to cash component")
    cash_alias = member["cash"]
    cash = components[cash_alias] if cash_alias is not None else None
    if cash is not None and cash["kind"] != "cash_itinerary":
        raise ValueError("journey cash alias points to noncash component")
    return {
        "award_quote": {field: copy.deepcopy(award[field]) for field in AWARD_FIELDS},
        "cash_quote": (None if cash is None else
                       {field: copy.deepcopy(cash[field]) for field in CASH_FIELDS}),
    }


def _schedule(facts: dict[str, Any]) -> dict[str, Any]:
    return {field: copy.deepcopy(facts[field]) for field in SCHEDULE_FIELDS}


def schedule_is_complete(schedule: dict[str, Any]) -> bool:
    """Null timestamps/duration cannot substantiate a matching schedule."""
    return (all(schedule[field] is not None for field in
                ("origin", "destination", "elapsed_minutes")) and
            all(schedule[clock].get(field) is not None
                for clock in ("departure", "arrival")
                for field in ("local_iso", "timezone")))


def _catalog(view: dict[str, Any]) -> dict[str, list[Any]]:
    catalog: dict[str, list[Any]] = {}
    for field in FACT_FIELDS:
        seen: dict[str, int] = {}
        values: list[Any] = []
        for group in view["journeys"]:
            facts = group["facts"]
            value = facts.pop(field)
            key = compact(value)
            if key not in seen:
                seen[key] = len(values)
                values.append(value)
            facts[f"{field}_ref"] = seen[key]
        catalog[field] = values
    return catalog


def transform(request: dict[str, Any], prepared: StructuredPreparedInput) -> dict[str, Any]:
    """Return the token-bearing request; callers add explicit effort/stream controls.

    The input shape is the existing structured payload. Preparation is serialized
    first so a possible correction keeps its large stable prefix. This bundle is
    a diagnostic candidate, not a new canonical prepared-input version.
    """
    result = copy.deepcopy(request)
    body = json.loads(result["input"])
    view = body["prepared"]["view"]
    if view != prepared.authoring_view.view:
        raise ValueError("request view differs from exact prepared writer view")
    components = _component_by_ref(view)
    schedules: dict[str, dict[str, Any]] = {}
    for group in view["journeys"]:
        facts = group["facts"]
        schedule = _schedule(facts)
        for member in group["members"]:
            if "choice" in member:
                raise ValueError("candidate transform already applied")
            member["choice"] = _choice(member, components)
            complete = schedule_is_complete(schedule)
            key = compact(schedule) if complete else f"unknown:{member['ref']}"
            if key not in schedules:
                schedules[key] = {"schedule": schedule, "choices": []}
                if not complete:
                    schedules[key]["relationship"] = "schedule_unknown_singleton"
            schedules[key]["choices"].append({
                "ref": member["ref"], "cabin": copy.deepcopy(facts["award_cabin"]),
                "program": copy.deepcopy(member["choice"]["award_quote"]["program"]),
                "points": copy.deepcopy(member["choice"]["award_quote"]["points"]),
                "booking_obligation": facts["booking_obligation"],
            })
    # Index covers each exact eligible member once. Stable order is inherited from
    # the authoring view; the index does not identify physical flights.
    view["same_schedule"] = list(schedules.values())
    view["journey_fact_catalog"] = _catalog(view)
    result["instructions"] += GUIDE
    result["input"] = compact({"prepared": body["prepared"],
                               "feedback": body["feedback"],
                               "previous_document": body["previous_document"]},
                              sort_keys=False)
    return result


def restore(request: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the complete original token request for preservation audits."""
    result = copy.deepcopy(request)
    if not result["instructions"].endswith(GUIDE):
        raise ValueError("candidate guide missing")
    result["instructions"] = result["instructions"][:-len(GUIDE)]
    body = json.loads(result["input"])
    view = body["prepared"]["view"]
    view.pop("same_schedule")
    catalog = view.pop("journey_fact_catalog")
    for group in view["journeys"]:
        facts = group["facts"]
        for field in FACT_FIELDS:
            facts[field] = copy.deepcopy(catalog[field][facts.pop(f"{field}_ref")])
        for member in group["members"]:
            member.pop("choice")
    result["input"] = compact(body)
    return result
