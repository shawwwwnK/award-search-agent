"""V4 writer instructions with existing exact source-role grammar and decoder."""

from __future__ import annotations

from typing import Any

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_contracts import InteractivePreparedInput
from .interactive_wire_v3 import alias_for_canonical as _alias_for_canonical
from .interactive_wire_v3 import decode as _decode
from .interactive_wire_v3 import instructions as _instructions
from .interactive_wire_v3 import schema as _schema
from .structured_contracts import StructuredDocument


def _v3_view(prepared: InteractivePreparedInput) -> InteractivePreparedInput:
    if prepared.packet.get("format") != "decision-joined-v4":
        raise ValueError("v4 wire requires a v4 joined packet")
    # The existing source-role codec reads the prepared registry locally. Only
    # the marker changes in this temporary view; no saved v3 request changes.
    packet = dict(prepared.packet)
    packet["format"] = "decision-joined-v3"
    return prepared.model_copy(update={"packet": packet})


def instructions(prepared: InteractivePreparedInput) -> str:
    text = _instructions(_v3_view(prepared))
    text = text.replace("direct cash context", "origin-to-destination cash benchmark context")
    return text + (
        " In this packet, award_only means one award itinerary without separate "
        "cash positioning; it can have stops and flight changes. Do not describe "
        "an award or cash itinerary as a direct flight, nonstop, or direct routing "
        "unless its own stop and leg evidence supports that claim. Describe the "
        "connection when material. For arrival-time comparisons, read the exact "
        "arrival on each cited journey; when citing a relation group, verify both "
        "references are its members. Never borrow a neighboring candidate's time. "
        "A complete eligible journey is assembled source "
        "evidence, not a confirmed booking or currently bookable option. For points "
        "from different programs, do not present a smaller numeric total as an "
        "economic advantage; if mentioning the difference, say the programs' points "
        "are not directly comparable.")


def schema(prepared: InteractivePreparedInput) -> dict[str, object]:
    return _schema(_v3_view(prepared))


def alias_for_canonical(prepared: InteractivePreparedInput,
                        canonical_id: str) -> str | None:
    return _alias_for_canonical(_v3_view(prepared), canonical_id)


def decode(raw: str | dict[str, Any], prepared: InteractivePreparedInput,
           source: SolutionProjection) -> StructuredDocument:
    return _decode(raw, _v3_view(prepared), source)
