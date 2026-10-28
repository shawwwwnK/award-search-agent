"""Composer wire restricted to the exact model-selected source bundle."""

from __future__ import annotations

import json
from typing import Any, cast

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_contracts import InteractivePreparedInput
from .interactive_wire_v4 import alias_for_canonical as _alias_for_canonical
from .interactive_wire_v4 import decode as _decode
from .interactive_wire_v4 import instructions as _instructions
from .interactive_wire_v4 import schema as _schema
from .structured_contracts import StructuredDocument


def _v4_view(prepared: InteractivePreparedInput) -> InteractivePreparedInput:
    if prepared.packet.get("format") != "focused-v1":
        raise ValueError("focused composer requires a focused packet")
    packet = dict(prepared.packet)
    packet["format"] = "decision-joined-v4"
    return prepared.model_copy(update={"packet": packet})


def _allowed(prepared: InteractivePreparedInput) -> dict[str, set[str]]:
    packet = cast(dict[str, Any], prepared.packet)
    groups = {section: {member["ref"] for group in packet[section]
                        for member in group["members"]}
              for section in ("journeys", "benchmarks", "leads")}
    return {"p": groups["journeys"], "a": groups["journeys"],
            "b": groups["benchmarks"], "l": groups["leads"]}


def instructions(prepared: InteractivePreparedInput) -> str:
    text = _instructions(_v4_view(prepared))
    guidance = (
        " You are writing from a small bundle that YOU selected from the full eligible "
        "pool in the preceding task. Own the prose, ordering, which selected journeys "
        "to highlight versus mention as alternatives, and how to explain them. "
        "Use only shown exact references. A selected partial lead is not a complete "
        "journey. Re-read each shown record's OWN program, complete airport sequence, "
        "departure and arrival, award/cash amount, currency unit and price scope "
        "before stating details. A cash access leg and award may be separate tickets; "
        "their airport join does not prove protection or bookability. Compare only "
        "shown choices. Do not claim overall best, only, necessary, or globally "
        "fastest from this selected bundle. Source-resolved cards already contain "
        "exact facts; provide a useful reason and downside for each highlighted "
        "choice, relevant alternatives, cash context and applicable limitations "
        "without duplicating fragile numbers.")
    if prepared.packet.get("selection_format") == "roles-v2":
        guidance += (" The observed airport path may be null because the source did "
                     "not provide a complete ordered sequence; preserve that unknown "
                     "and do not infer a nonstop flight or an unseen connection.")
    if prepared.packet.get("composition_format") == "comparisons-v1":
        guidance += (" The selected_comparisons section contains exact source-computed "
                     "pair facts for selected J references only. For elapsed_minutes, "
                     "first is shorter than second by difference_minutes. For departure "
                     "and arrival instants, first is earlier than second by "
                     "difference_minutes; timezone offsets are already accounted for. "
                     "Equal means the two source values tie. Use these pair facts for "
                     "any quantitative journey comparison. Do not reverse direction, "
                     "do mental subtraction to create a new difference, or infer a "
                     "comparison where no pair fact exists. These facts do not rank "
                     "the unseen eligible pool and do not make points from different "
                     "programs comparable. You still own the answer's prose, layout "
                     "and choice of which selected journeys to emphasize.")
    return text + guidance


def schema(prepared: InteractivePreparedInput) -> dict[str, object]:
    return _schema(_v4_view(prepared))


def alias_for_canonical(prepared: InteractivePreparedInput,
                        canonical_id: str) -> str | None:
    return _alias_for_canonical(_v4_view(prepared), canonical_id)


def decode(raw: str | dict[str, Any], prepared: InteractivePreparedInput,
           source: SolutionProjection) -> StructuredDocument:
    """Decode exact roles and reject any reference outside the selected bundle."""
    allowed = _allowed(prepared)
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or not isinstance(value.get("blocks"), list):
        raise TypeError("focused wire requires blocks")
    for index, row in enumerate(value["blocks"]):
        if (isinstance(row, dict) and row.get("k") in allowed and
                row.get("r") not in allowed[row["k"]]):
            raise ValueError(f"block {index}: reference outside selected source bundle")
    return _decode(value, _v4_view(prepared), source)
