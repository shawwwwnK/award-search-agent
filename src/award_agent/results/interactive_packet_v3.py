"""Source-bound readable references for the joined interactive writer packet."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_packet_v2 import build_packet as build_v2_packet
from .structured_contracts import StructuredPreparedInput
from .workspace_contracts import WorkspaceEvidence

_CABIN = {"economy": "E", "premium_economy": "P", "business": "B",
          "first": "F", "unknown": "?"}


def _when(facts: dict[str, Any], whole: dict[str, Any] | None = None) -> str:
    departure = facts.get("departure")
    if departure == "same_as_journey" and whole is not None:
        departure = whole.get("departure")
    if isinstance(departure, dict) and isinstance(departure.get("local_iso"), str):
        parsed = datetime.fromisoformat(departure["local_iso"])
        if parsed.microsecond:
            return parsed.isoformat(timespec="microseconds")
        if parsed.second:
            return parsed.isoformat(timespec="seconds")
        return parsed.isoformat(timespec="minutes")
    timing = facts.get("timing")
    if isinstance(timing, dict):
        departure = timing.get("departure")
        if isinstance(departure, dict) and isinstance(departure.get("local_iso"), str):
            parsed = datetime.fromisoformat(departure["local_iso"])
            if parsed.microsecond:
                return parsed.isoformat(timespec="microseconds")
            if parsed.second:
                return parsed.isoformat(timespec="seconds")
            return parsed.isoformat(timespec="minutes")
    date = facts.get("date")
    return date if isinstance(date, str) and date != "-" else "date-unknown"


def _alias(old: str, facts: dict[str, Any],
           whole: dict[str, Any] | None = None) -> str:
    route = facts.get("route")
    if not isinstance(route, dict):
        raise TypeError(f"source reference {old} lacks a route")
    origin, destination = route.get("origin"), route.get("destination")
    if not isinstance(origin, str) or not isinstance(destination, str):
        raise TypeError(f"source reference {old} has an invalid route")
    if (len(origin) != 3 or len(destination) != 3 or
            not origin.isupper() or not destination.isupper() or
            not origin.isalpha() or not destination.isalpha()):
        raise ValueError(f"source reference {old} has a non-airport route")
    cabin = facts.get("award_cabin", facts.get("cabin"))
    cabin_code = _CABIN.get(cabin, "?") if isinstance(cabin, str) else "?"
    suffix = f"/{cabin_code}" if old.startswith(("J", "A")) else ""
    return f"{old}@{_when(facts, whole)}/{origin}>{destination}{suffix}"


def alias_map(packet_v2: dict[str, Any]) -> dict[str, str]:
    """Map every source reference to a readable, exact and unique wire identity."""
    aliases: dict[str, str] = {}

    def add(old: str, facts: dict[str, Any], whole: dict[str, Any] | None = None) -> None:
        value = _alias(old, facts, whole)
        prior = aliases.setdefault(old, value)
        if prior != value:
            raise ValueError(f"source reference {old} has conflicting identity facts")

    for group in packet_v2["journeys"]:
        facts = group["facts"]
        for member in group["members"]:
            add(member["ref"], facts)
            add(member["award_ref"], facts["award"], facts)
            if member["cash_ref"] is not None:
                add(member["cash_ref"], facts["cash"], facts)
    for section in ("benchmarks", "leads"):
        for group in packet_v2[section]:
            for member in group["members"]:
                add(member["ref"], group["facts"])
    if len(set(aliases.values())) != len(aliases):
        raise ValueError("readable source references are not unique")
    return aliases


def _replace_refs(packet: dict[str, Any], aliases: dict[str, str]) -> None:
    """Rewrite declared reference paths only; source strings may equal short IDs."""
    def ref(old: str) -> str:
        if old not in aliases:
            raise ValueError(f"unbound source reference {old!r}")
        return aliases[old]

    for section in ("journeys", "benchmarks", "leads"):
        for group in packet[section]:
            for member in group["members"]:
                for key in ("ref", "award_ref", "cash_ref"):
                    if key in member and member[key] is not None:
                        member[key] = ref(member[key])
    for key, refs in packet["ranking_hints"].items():
        packet["ranking_hints"][key] = [ref(item) for item in refs]
    relations = packet["relations"]
    for row in relations["same_award_arrival_alternatives"]:
        row["award_ref"] = ref(row["award_ref"])
        row["journey_refs"] = [ref(item) for item in row["journey_refs"]]
    relations["timing_match_cross_cabin"] = [
        [ref(item) for item in row] for row in relations["timing_match_cross_cabin"]]
    for row in relations["lead_relevance"]:
        row["lead_refs"] = [ref(item) for item in row["lead_refs"]]


def reference_grammar_mode(packet: dict[str, Any]) -> str:
    """Declare whether exact role enums fit Structured Outputs' source limits."""
    roles = [[member["ref"] for group in packet[section]
              for member in group["members"]]
             for section in ("journeys", "benchmarks", "leads")]
    if any(len(set(refs)) != len(refs) for refs in roles):
        raise ValueError("duplicate references in a wire role")
    kind_values = 1 + (2 if roles[0] else 0) + bool(roles[1]) + bool(roles[2])
    eligible = sum(map(len, roles)) + kind_values <= 1000 and all(
        len(refs) <= 250 or sum(map(len, refs)) <= 15000 for refs in roles)
    return "exact_role_enums" if eligible else "role_only_exact_decoder"


def build_packet(prepared: StructuredPreparedInput, source: SolutionProjection,
                 evidence: WorkspaceEvidence) -> dict[str, Any]:
    original = build_v2_packet(prepared, source, evidence)
    aliases = alias_map(original)
    packet = deepcopy(original)
    _replace_refs(packet, aliases)
    packet["format"] = "decision-joined-v3"
    packet["outcome_mode"] = ("complete_choices" if any(group["members"]
                              for group in original["journeys"]) else "no_complete_journey")
    packet["wire_aliases"] = {new: old for old, new in aliases.items()}
    packet["wire_reference_grammar"] = reference_grammar_mode(packet)
    return packet
