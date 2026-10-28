"""Experimental lean Results wire format; no runtime contract changes."""

from __future__ import annotations

import json
from typing import Any

from award_agent.results.structured_contracts import (
    StructuredBlock,
    StructuredDocument,
    StructuredPreparedInput,
    StructuredSelection,
)

WIRE_SCHEMA: dict[str, object] = {
    "type": "object", "additionalProperties": False,
    "properties": {"blocks": {"type": "array", "minItems": 1, "items": {
        "anyOf": [
            {"type": "object", "additionalProperties": False,
             "properties": {"k": {"type": "string", "enum": ["t"]},
                            "v": {"type": "string"}}, "required": ["k", "v"]},
            {"type": "object", "additionalProperties": False,
             "properties": {"k": {"type": "string", "enum": ["p", "a", "b", "l"]},
                            "r": {"type": "string"}, "n": {"type": "string"},
                            "v": {"type": "string"}}, "required": ["k", "r", "n", "v"]},
        ]}}}, "required": ["blocks"],
}

INSTRUCTIONS = """Write one complete, natural traveler answer from the supplied decision packet. You own the order, selection and wording; there is no fixed count or layout. Keep it concise, generally under 450 words and shorter when the evidence offers fewer choices. Choose meaningful recommendations and explain each individually with exact embedded journey references, useful alternatives, direct cash context where supported, and consolidated limitations. Preserve unknowns and distinguish source facts from interpretation. The packet's relations are prompts to compare, not evidence of necessity, cross-program points ordering, identical flights, or bookability. Its cards carry the source facts; check them before any claim. Do not invent missing facts or imply an unknown is known.

If feedback and previous_wire are supplied, revise the prior draft against the same packet. Feedback references use packet aliases. In both the prior draft and your revision, any 'p' selects that journey globally; an 'a' never unselects it. Recheck the source before changing a claim. Return only JSON blocks, in reading order. {k:'t',v:text} is ordinary connective prose. {k:'p',r:exact J alias,n:short nonblank traveler label,v:explanation} highlights and selects a journey. {k:'a',r:exact J alias,n:label,v:explanation} mentions an eligible alternative without selecting it. {k:'b',r:exact cash alias,n:label,v:cash context} selects the one direct cash benchmark. {k:'l',r:exact lead alias,n:label,v:incomplete lead context} selects an incomplete lead. References must use one exact packet alias with its correct role. A repeated 'p' still selects that journey, and a repeated 'a' never deselects it. Use at most one distinct cash benchmark. Do not print aliases to the traveler. Write limitations in the prose itself. This experimental wire deliberately omits declared claims; facts and numerical prose still require independent semantic review."""


def decode_wire(raw: str | dict[str, Any], prepared: StructuredPreparedInput,
                source: Any) -> StructuredDocument:
    """Validate exact aliases and roles before expanding to the existing document."""
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"blocks"} or not isinstance(value["blocks"], list) or not value["blocks"]:
        raise ValueError("wire document requires nonempty blocks")
    refs = prepared.references
    eligible = {x.candidate_id for x in source.view.alternatives if x.status in {"admitted", "conditional"}}
    benchmarks = set(source.view.direct_cash_observation_ids)
    leads = (set(source.view.award_summary_observation_ids) |
             set(source.view.unmatched_award_observation_ids) |
             set(source.view.unpaired_positioning_observation_ids))
    selected: list[str] = []
    selected_leads: list[str] = []
    benchmark: str | None = None
    blocks: list[StructuredBlock] = []
    for index, row in enumerate(value["blocks"]):
        if not isinstance(row, dict) or row.get("k") not in {"t", "p", "a", "b", "l"}:
            raise ValueError(f"block {index}: unknown wire kind")
        kind = row["k"]
        expected = {"k", "v"} if kind == "t" else {"k", "r", "n", "v"}
        if set(row) != expected or any(not isinstance(row[key], str) for key in expected):
            raise ValueError(f"block {index}: invalid wire fields")
        if kind == "t":
            blocks.append(StructuredBlock(kind="narrative", text=row["v"], claims=()))
            continue
        alias = row["r"]
        mapping = refs.journeys if kind in {"p", "a"} else refs.cash if kind == "b" else refs.awards | refs.cash
        canonical = mapping.get(alias)
        registry = eligible if kind in {"p", "a"} else benchmarks if kind == "b" else leads
        if canonical is None or canonical not in registry:
            raise ValueError(f"block {index}: unknown or wrong-role reference {alias!r} ({kind})")
        if kind == "p" and not row["n"].strip():
            raise ValueError(f"block {index}: selected journey needs a nonblank label")
        if kind == "p" and canonical not in selected:
            selected.append(canonical)
        if kind == "l" and canonical not in selected_leads:
            selected_leads.append(canonical)
        if kind == "b":
            if benchmark is not None and benchmark != canonical:
                raise ValueError("wire protocol permits one distinct benchmark")
            benchmark = canonical
        blocks.append(StructuredBlock(kind="reference", text=row["v"],
            reference_kind="journey" if kind in {"p", "a"} else "benchmark" if kind == "b" else "lead",
            reference_id=canonical, label=row["n"], claims=()))
    return StructuredDocument(selection=StructuredSelection(journey_ids=tuple(selected),
        benchmark_observation_id=benchmark, incomplete_observation_ids=tuple(selected_leads)),
        blocks=tuple(blocks))
