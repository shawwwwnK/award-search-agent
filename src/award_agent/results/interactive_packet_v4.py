"""Traveler-facing composition labels for the source-bound joined packet."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_packet_v3 import _replace_refs, reference_grammar_mode
from .interactive_packet_v3 import build_packet as build_v3_packet
from .structured_contracts import StructuredPreparedInput
from .workspace_contracts import WorkspaceEvidence


def present_v3_packet(packet_v3: dict[str, Any]) -> dict[str, Any]:
    """Translate one internal composition term without altering its source facts."""
    if packet_v3.get("format") != "decision-joined-v3":
        raise ValueError("v4 presentation requires a v3 joined packet")
    packet = deepcopy(packet_v3)
    aliases = {old: old for old in packet_v3["wire_aliases"]}
    for group in packet["journeys"]:
        arrival = group["facts"].get("arrival")
        if isinstance(arrival, dict) and isinstance(arrival.get("local_iso"), str):
            parsed = datetime.fromisoformat(arrival["local_iso"]).replace(tzinfo=None)
            precision = ("microseconds" if parsed.microsecond else
                         "seconds" if parsed.second else "minutes")
            arrival_label = parsed.isoformat(timespec=precision)
        else:
            arrival_label = "arrival-unknown"
        for member in group["members"]:
            old_alias = member["ref"]
            aliases[old_alias] = f"{old_alias}>{arrival_label}"
        if group["facts"]["topology"] == "direct_award":
            group["facts"]["topology"] = "award_only"
    if len(set(aliases.values())) != len(aliases):
        raise ValueError("arrival-qualified journey aliases are not unique")
    _replace_refs(packet, aliases)
    packet["wire_aliases"] = {aliases[old]: short for old, short in
                              packet_v3["wire_aliases"].items()}
    packet["wire_reference_grammar"] = reference_grammar_mode(packet)
    packet["format"] = "decision-joined-v4"
    packet["legend"]["award_only"] = (
        "One award itinerary without a separate cash positioning component; "
        "it may contain connecting flights. Read award stops, airports, and flights "
        "for the actual connection pattern.")
    return packet


def build_packet(prepared: StructuredPreparedInput, source: SolutionProjection,
                 evidence: WorkspaceEvidence) -> dict[str, Any]:
    return present_v3_packet(build_v3_packet(prepared, source, evidence))
