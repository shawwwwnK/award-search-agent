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

_DRAFT_ONLY = (
    " Write the full first draft from the selected comparison pool. "
    "Put its main traveler decision in the opening, then make each "
    "referenced explanation and limitation consistent with that opening. "
    "An editorial pass will review the draft against these same exact "
    "facts, so keep source associations explicit.")


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
    if prepared.packet.get("selection_format") in {"roles-v2", "roles-v3", "roles-v4", "roles-v5", "roles-v6", "roles-v7", "roles-v8", "roles-v9"}:
        guidance += (" The observed airport path may be null because the source did "
                     "not provide a complete ordered sequence; preserve that unknown "
                     "and do not infer a nonstop flight or an unseen connection.")
    if prepared.packet.get("composition_format") in {"comparisons-v1", "complete-v1", "complete-v2", "complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7"}:
        comparison_scope = ("quantitative journey time comparisons" if
                            prepared.packet.get("composition_format") in {"complete-v1", "complete-v2", "complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7"}
                            else "any quantitative journey comparison")
        guidance += (" The selected_comparisons section contains exact source-computed "
                     "pair facts for selected J references only. For elapsed_minutes, "
                     "first is shorter than second by difference_minutes. For departure "
                     "and arrival instants, first is earlier than second by "
                     "difference_minutes; timezone offsets are already accounted for. "
                     "Equal means the two source values tie. Use these pair facts for "
                     f"{comparison_scope}. Do not reverse direction, "
                     "do mental subtraction to create a new difference, or infer a "
                     "comparison where no pair fact exists. These facts do not rank "
                     "the unseen eligible pool and do not make points from different "
                     "programs comparable. You still own the answer's prose, layout "
                     "and choice of which selected journeys to emphasize.")
    if prepared.packet.get("composition_format") in {"complete-v1", "complete-v2", "complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7"}:
        guidance += (
            " Write a complete, naturally flowing decision aid, with a connected "
            "opening recommendation and meaningful tradeoff among the shown choices. "
            "Explain each highlighted journey's own reason to choose it and its real "
            "downside, placing its source-resolved card inside that explanation. "
            "Mention an alternative only if its different route, timing, cabin, "
            "program, known cash component or limitation helps a traveler decide. "
            "One highlighted journey is enough if the others add no material value. "
            "Do not say an option is recommended while also saying it has no "
            "distinguishing benefit. Treat the direct cash search as a baseline, "
            "never an all-in award price or a like-for-like valuation when scope is "
            "unknown. Consolidate applicable limitations in readable prose and "
            "identify which shown choices they affect. If there is no complete "
            "journey, say so plainly, explain the most useful partial lead and its "
            "specific gap, then give a concrete next check. Your answer should help "
            "someone decide what to investigate next, not just enumerate cards. "
            "Use natural labels and prose; never expose internal J/A/C identifiers.")
    if prepared.packet.get("composition_format") in {"complete-v2", "complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7"}:
        guidance += (
            " Separate query traveler count and returned traveler support from "
            "the price scope of each quote. An observed cash or award amount whose "
            "price_scope is unknown is an amount returned for that search; it is "
            "not a per-person fare, party total or all-in price. Never attach "
            "'for one traveler', 'per traveler', or a party total to that amount "
            "unless its own quote scope explicitly supports the claim. You may "
            "state independently supported traveler or seat evidence in a separate "
            "sentence. Compare why each shown journey is useful: route simplicity "
            "versus arrival and elapsed time, cabin, observed same-program cost "
            "with matching scope, separate cash access and its connection buffer. "
            "For a recommended option, state its concrete traveler advantage "
            "against the most relevant shown alternative and its material downside. "
            "If two shown options are nearly the same, explain the practical "
            "difference once; do not inflate a few minutes into a major choice. "
            "Across programs, numerical point totals do not establish an economic "
            "winner. Preserve source-specific unknowns rather than smoothing them.")
    if prepared.packet.get("composition_format") in {"complete-v3", "complete-v4", "complete-v5", "complete-v6", "complete-v7"}:
        guidance += (
            " The selected records are a comparison pool, not a mandate to "
            "recommend each one. Choose the defensible lead and use the others "
            "to explain its real benefit and downside. Support a comparative "
            "benefit from BOTH records' reported facts and scopes; an absent "
            "cash-benchmark cabin cannot establish that an award is better "
            "cabin value. A reported business award cabin does not prove the "
            "whole mixed journey, positioning flight or every award leg is "
            "business. If the chosen award arrives later or involves more "
            "separate-ticket risk, give its positive supported reason for "
            "investigation or choose a stronger comparator. Use a few exact "
            "source facts where they make the tradeoff tangible, including "
            "same-program schedule and observed fees, reported seats, or the "
            "specific cash-access quote when useful. State the unit and unknown "
            "scope; never turn an observed quote into a per-person or all-in "
            "total. For incomplete leads, compare any reported dates, seats "
            "and tax/fee observations that guide which provider detail to check, "
            "while saying that a date-only summary is not a timed itinerary. "
            "Write a connected decision argument, with each highlighted option's "
            "own useful reason and downside, relevant cash context and "
            "consolidated applicable limitations.")
    if prepared.packet.get("composition_format") in {"complete-v4", "complete-v5", "complete-v6", "complete-v7"}:
        guidance += (
            " Every concrete journey, lead or benchmark you discuss or compare "
            "must have its own visible exact reference block (p, a, l or b as "
            "appropriate) in the traveler answer. The selected source pool is "
            "not itself visible to the traveler. If you do not show a pool "
            "member with its own reference block, remove prose comparisons to "
            "that member; do not write 'the TPE option' or give its time gap "
            "without its visible card. When several options share a route or "
            "date, give each a distinct natural label that lets the traveler "
            "identify the referenced record, without internal aliases. This "
            "rule does not require showing every pool member; choose the "
            "smallest set that supports the decision argument.")
    if prepared.packet.get("composition_format") in {"complete-v6", "complete-v7"}:
        guidance += (
            " The selected_details index binds each selected long reference "
            "to its exact award/cash components, award-itinerary connections, "
            "per-journey separate-booking waits and original-currency quote "
            "displays. Use those displayed major-unit amounts and currencies "
            "directly; do not divide raw minor units mentally or call them "
            "all-in prices. Distinguish a short award-itinerary connection "
            "from a separate-ticket wait: the former is within the reported "
            "award, the latter lacks confirmed protection. A null wait is "
            "unknown, never zero. Compare exact selected option buffers and "
            "reported fees/cash only when both source records and scopes "
            "support the contrast; preserve unknown quote scope even when "
            "the query or returned traveler count is known. Use these exact "
            "facts where they change a useful next decision, not as a field "
            "checklist or a substitute for your own connected explanation.")
    if prepared.packet.get("composition_format") in {"complete-v5", "complete-v6", "complete-v7"}:
        guidance += _DRAFT_ONLY
    return text + guidance


def revision_instructions(prepared: InteractivePreparedInput) -> str:
    if prepared.packet.get("composition_format") not in {"complete-v5", "complete-v6", "complete-v7"}:
        raise ValueError("editorial revision requires the versioned complete-v5 packet")
    draft_instructions = instructions(prepared)
    if not draft_instructions.endswith(_DRAFT_ONLY):
        raise ValueError("editorial revision has no draft-only suffix to remove")
    return draft_instructions.removesuffix(_DRAFT_ONLY) + (
        " This is the final editorial revision. The supplied previous_wire is "
        "a recoverable draft, not verified truth. Recheck EVERY factual and "
        "comparative claim in its opening, prose, labels and referenced blocks "
        "against the SAME exact source record and its reported scope. Reconcile "
        "the opening with the body: do not call an option earlier, cheaper, "
        "better cabin or simpler if its actual evidence does not establish it. "
        "Use selected_comparisons for exact time differences and direction, "
        "and compare same-program fees or seats only with proper units and "
        "source-specific unknowns. Where the pool supplies a useful direct "
        "comparator or connection buffer, use it to explain the recommended "
        "choice's positive reason and real downside. Remove any unshown or "
        "ambiguous option comparison unless that option has its own visible "
        "exact reference block and distinct natural label. Do not invent cash "
        "or whole-journey cabin, per-person price, party total, traveler support "
        "or connection protection from absent/unknown evidence. Treat any "
        "feedback as specific check failures; an empty feedback list still "
        "requires this complete independent source review. Return ONLY a full "
        "final JSON blocks document in the same wire schema and frozen alias "
        "namespace, not commentary or a patch.")


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
