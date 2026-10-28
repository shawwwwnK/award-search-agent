"""Experimental self-contained semantic writer packet built from frozen v1 facts.

This module changes representation only. It does not filter or select eligible
journeys and it does not alter the canonical workspace or Ranking evidence.
"""

from __future__ import annotations

import json
from typing import Any

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.interactive_packet import build_packet as build_v1_packet
from award_agent.results.structured_contracts import StructuredPreparedInput
from award_agent.results.workspace_contracts import WorkspaceEvidence


def _named(columns: list[str] | tuple[str, ...], values: list[Any]) -> dict[str, Any]:
    if len(columns) != len(values):
        raise ValueError("packet row and column names have different lengths")
    return dict(zip(columns, values))


def _time(value: Any, timezones: dict[str, str]) -> Any:
    if not isinstance(value, str) or "@" not in value:
        return value
    local_iso, zone_code = value.rsplit("@", 1)
    return {"local_iso": local_iso, "timezone": timezones.get(zone_code, zone_code)}


def _route(value: Any) -> Any:
    if not isinstance(value, list) or len(value) != 2:
        return value
    return {"origin": value[0], "destination": value[1]}


def _findings(codes: Any) -> list[str]:
    if codes in ("-", None):
        return []
    return list(codes)


def _component(values: list[Any], packet: dict[str, Any]) -> dict[str, Any]:
    facts = _named(packet["legend"]["component_profile"], values)
    zones = packet["legend"]["timezones"]
    facts["route"] = _route(facts["route"])
    facts["departure"] = _time(facts.pop("depart"), zones)
    facts["arrival"] = _time(facts.pop("arrive"), zones)
    facts["findings"] = _findings(facts["findings"])
    # The source's absent fields carry no decision value; unknown/null/zero
    # remain explicit. Missing fields have a declared local default in legend.
    return {key: value for key, value in facts.items() if value != "-"}


def _journey(values: list[Any], packet: dict[str, Any],
             alias: str) -> dict[str, Any]:
    facts = _named(packet["legend"]["journey_profile"], values)
    zones = packet["legend"]["timezones"]
    facts["route"] = _route(facts["route"])
    facts["departure"] = _time(facts.pop("depart"), zones)
    facts["arrival"] = _time(facts.pop("arrive"), zones)
    transfer = facts["transfer"]
    facts["transfer"] = _named(("airport", "minutes", "local_day_offset"), transfer)
    facts["heuristic_cost"] = _named(packet["legend"]["heuristic_cost"],
                                     facts["heuristic_cost"])
    facts["styles"] = _named(packet["legend"]["styles"], facts["styles"])
    caveats = packet["caveat_profiles"][facts["caveats"]]
    facts["caveats"] = [({"code": item, "state": "unknown"} if isinstance(item, str)
                         else {"code": item[0], "state": item[1]}) for item in caveats]
    facts["ranking_memberships"] = [key for key, refs in packet["ranking_hints"].items()
                                    if alias in refs]
    return facts


def _lead(values: list[Any], packet: dict[str, Any]) -> dict[str, Any]:
    facts = _named(packet["legend"]["lead_row"], values)
    facts.pop("A_or_C")
    facts["route"] = _route(facts["route"])
    timing = facts["timing"]
    if timing != "-":
        facts["timing"] = {
            "departure": _time(timing[0], packet["legend"]["timezones"]),
            "arrival": _time(timing[1], packet["legend"]["timezones"]),
            "duration_minutes": timing[2],
        }
    facts["findings"] = _findings(facts["findings"])
    return facts


def _group(groups: list[dict[str, Any]], facts: dict[str, Any],
           member: dict[str, Any]) -> None:
    key = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    for group in groups:
        if group["_key"] == key:
            group["members"].append(member)
            return
    groups.append({"_key": key, "facts": facts, "members": [member]})


def _finish(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"members": group["members"], "facts": group["facts"]}
            for group in groups]


def join_v1_packet(original: dict[str, Any]) -> dict[str, Any]:
    """Join a frozen v1 packet without reinterpreting or filtering its facts."""
    component_by_ref = {}
    for alias, profile_id in original["component_rows"]:
        component_by_ref[alias] = _component(original["component_profiles"][profile_id],
                                             original)
    journeys: list[dict[str, Any]] = []
    for alias, profile_id, award_ref, cash_ref in original["journey_rows"]:
        facts = _journey(original["journey_profiles"][profile_id], original, alias)
        award = dict(component_by_ref[award_ref])
        cash = dict(component_by_ref[cash_ref]) if cash_ref is not None else None
        for component in (award, cash):
            if component is None:
                continue
            for field in ("departure", "arrival"):
                if component.get(field) == facts[field]:
                    component[field] = "same_as_journey"
        facts["award"] = award
        facts["cash"] = cash
        _group(journeys, facts, {"ref": alias, "award_ref": award_ref,
                                 "cash_ref": cash_ref})
    benchmarks: list[dict[str, Any]] = []
    for alias in original["benchmark_refs"]:
        _group(benchmarks, component_by_ref[alias], {"ref": alias})
    leads: list[dict[str, Any]] = []
    for values in original["lead_rows"]:
        _group(leads, _lead(values, original), {"ref": values[0]})
    context = dict(original["source_context"])
    context["coverage_limits"] = [
        _named(("kind", "status", "reason", "routes_and_dates"), row)
        for row in context["coverage_limits"]
    ]
    relations = original["relations"]
    return {
        "format": "decision-joined-v2",
        "legend": {
            "grouping": "Only complete byte-equal facts share a group; each member remains an exact source reference.",
            "eligibility": "Every J member is eligible; benchmarks and incomplete leads have separate roles.",
            "raw": "A missing component field means source absent/empty. Explicit null/unknown and zero remain present. A lead's '-' means absent/empty.",
            "timeline": "A component departure/arrival value same_as_journey inherits that exact whole-journey time in the same record.",
            "findings": "Finding codes remain next to their source facts; finding_meanings gives the source's severity, field and meaning.",
            "scope": "Journey cabin does not prove all leg cabins; leg_cabins follows successive airport pairs.",
            "relations": "Schedule matches are source timing evidence, not physical-flight identity or a selection.",
            "lead_window": "The lead flag compares its own departure date with the request window, not complete journey compatibility.",
        },
        "request": original["request"],
        "policy": original["policy"],
        "comparison": original["comparison"],
        "ranking_hints": original["ranking_hints"],
        "finding_meanings": original["finding_catalog"],
        "journeys": _finish(journeys),
        "benchmarks": _finish(benchmarks),
        "leads": _finish(leads),
        "relations": {
            "same_award_arrival_alternatives": [
                {"award_ref": award, "arrival": _time(arrival, original["legend"]["timezones"]),
                 "journey_refs": members}
                for award, arrival, members in relations["same_award_arrival_alternatives"]],
            "timing_match_cross_cabin": relations["timing_match_cross_cabin"],
            "lead_relevance": [
                {"request_route_match": route, "in_departure_window": window,
                 "schedule_state": schedule, "lead_refs": members}
                for route, window, schedule, members in relations["lead_relevance"]],
        },
        "source_context": context,
    }


def build_packet(prepared: StructuredPreparedInput, source: SolutionProjection,
                 evidence: WorkspaceEvidence) -> dict[str, Any]:
    """Expand all canonical v1 references into named, source-bound records."""
    return join_v1_packet(build_v1_packet(prepared, source, evidence))
