"""Source-specific typed wire for the readable joined Results packet."""

from __future__ import annotations

import json
from typing import Any, cast

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_contracts import InteractivePreparedInput
from .interactive_packet_v3 import reference_grammar_mode
from .interactive_wire import decode_wire as decode_original_wire
from .structured_contracts import StructuredDocument

_INTRO = ("Write one concise, natural traveler answer using only this source packet. "
          "You own selection, order and prose. Explain each chosen choice with a defensible "
          "reason and a real downside, embed its exact source reference, mention useful "
          "alternatives and direct cash context where supported, and consolidate limitations. "
          "The source-resolved cards carry exact facts; concentrate on useful interpretation "
          "instead of recopying schedules, prices and durations. When you state a number, "
          "date, carrier or comparison, verify it against the SAME referenced record. "
          "Do not order points across programs as economic cost, infer a total from unknown "
          "quote scope, or claim an unverified connection, protection, flight identity or "
          "bookability. Preserve unknowns. Generally stay under 450 words, shorter when "
          "there are fewer choices. Return JSON blocks in reading order only. "
          "{k:'t',v:text} is ordinary prose; {k:'p',r:exact journey alias,n:short "
          "nonblank label,v:explanation} selects a complete journey; {k:'a',r:exact "
          "journey alias,n:label,v:explanation} mentions an eligible alternative; "
          "{k:'b',r:exact benchmark alias,n:label,v:cash context} selects at most one "
          "distinct direct cash benchmark; {k:'l',r:exact lead alias,n:label,v:lead "
          "context} selects an incomplete lead. Every r must copy the ENTIRE exact alias "
          "from its own packet role, including its date/time and route. Never print aliases "
          "to the traveler. A p selects globally; an a never unselects it. "
          "If feedback and previous_wire are supplied, revise the same source-bound answer, "
          "rechecking every source claim. This wire has no declared claim annotations; "
          "numerical prose still needs independent review.")


def _role_aliases(prepared: InteractivePreparedInput) -> dict[str, list[str]]:
    packet = prepared.packet
    if packet.get("format") != "decision-joined-v3":
        raise ValueError("v3 wire requires a v3 packet")
    roles: dict[str, list[str]] = {}
    for role, section in (("journey", "journeys"), ("benchmark", "benchmarks"),
                          ("lead", "leads")):
        rows = packet.get(section)
        if not isinstance(rows, list):
            raise TypeError(f"v3 packet lacks {section}")
        refs = [member["ref"] for group in rows for member in group["members"]]
        if any(not isinstance(ref, str) for ref in refs) or len(refs) != len(set(refs)):
            raise ValueError(f"v3 packet has invalid {role} references")
        roles[role] = sorted(refs)
    mode = packet.get("outcome_mode")
    if mode != ("complete_choices" if roles["journey"] else "no_complete_journey"):
        raise ValueError("v3 packet outcome mode disagrees with journey role")
    mapping = packet.get("wire_aliases")
    if not isinstance(mapping, dict) or any(not isinstance(key, str) or
            not isinstance(value, str) for key, value in mapping.items()):
        raise ValueError("v3 packet has invalid source alias registry")
    if any(ref not in mapping for refs in roles.values() for ref in refs):
        raise ValueError("v3 packet role is missing an alias binding")
    if packet.get("wire_reference_grammar") != reference_grammar_mode(packet):
        raise ValueError("v3 packet grammar mode differs from role registry")
    return roles


def instructions(prepared: InteractivePreparedInput) -> str:
    roles = _role_aliases(prepared)
    if not roles["journey"]:
        guidance = (_INTRO + " No complete eligible journey exists in this packet. State that "
                    "plainly. Do not use p or a blocks.")
        if roles["lead"]:
            guidance += (" Leads are partial observations, not complete recommendations. "
                         "A date-only award summary lacks a full timed itinerary, while a "
                         "timed partial component still does not establish a complete journey. "
                         "Explain the most relevant leads and their specific limitations. "
                         "Do not generalize a chosen lead's missing time to every flight in "
                         "the packet.")
        else:
            guidance += " There are no incomplete leads either; explain the coverage limits."
        return guidance
    return (_INTRO + " Eligible complete journeys are the only p/a choices. "
            "A reference's cabin suffix summarizes the reported award cabin, not every leg cabin.")


def schema(prepared: InteractivePreparedInput) -> dict[str, object]:
    roles = _role_aliases(prepared)
    use_enums = prepared.packet["wire_reference_grammar"] == "exact_role_enums"

    def reference(kinds: list[str], aliases: list[str]) -> dict[str, object]:
        ref: dict[str, object] = {"type": "string"}
        if use_enums:
            ref["enum"] = aliases
        return {"type": "object", "additionalProperties": False,
                "properties": {"k": {"type": "string", "enum": kinds}, "r": ref,
                               "n": {"type": "string"}, "v": {"type": "string"}},
                "required": ["k", "r", "n", "v"]}

    choices: list[dict[str, object]] = [
        {"type": "object", "additionalProperties": False,
         "properties": {"k": {"type": "string", "enum": ["t"]},
                        "v": {"type": "string"}}, "required": ["k", "v"]}]
    if roles["journey"]:
        choices.append(reference(["p", "a"], roles["journey"]))
    if roles["benchmark"]:
        choices.append(reference(["b"], roles["benchmark"]))
    if roles["lead"]:
        choices.append(reference(["l"], roles["lead"]))
    return {"type": "object", "additionalProperties": False,
            "properties": {"blocks": {"type": "array", "minItems": 1,
                                      "items": {"anyOf": choices}}},
            "required": ["blocks"]}


def alias_for_canonical(prepared: InteractivePreparedInput,
                        canonical_id: str) -> str | None:
    _role_aliases(prepared)
    aliases = cast(dict[str, str], prepared.packet["wire_aliases"])
    refs = prepared.structured.references
    for old, canonical in (refs.journeys | refs.awards | refs.cash).items():
        if canonical == canonical_id:
            for new, bound in aliases.items():
                if bound == old:
                    return new
    return None


def decode(raw: str | dict[str, Any], prepared: InteractivePreparedInput,
           source: SolutionProjection) -> StructuredDocument:
    """Resolve only exact v3 aliases, then use the existing source-role decoder."""
    _role_aliases(prepared)
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict):
        raise TypeError("v3 wire document must be an object")
    mapping = cast(dict[str, str], prepared.packet["wire_aliases"])
    blocks = value.get("blocks")
    if not isinstance(blocks, list):
        raise TypeError("v3 wire document requires blocks")
    translated: list[Any] = []
    for index, row in enumerate(blocks):
        if not isinstance(row, dict):
            translated.append(row)
            continue
        item = dict(row)
        if "r" in item:
            alias = item["r"]
            if not isinstance(alias, str) or alias not in mapping:
                raise ValueError(f"block {index}: unknown exact v3 source alias")
            item["r"] = mapping[alias]
        translated.append(item)
    return decode_original_wire({**value, "blocks": translated},
                                prepared.structured, source)
