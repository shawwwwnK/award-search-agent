"""V11 wire codec and code-owned temporal card resolution."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Literal, cast

from award_agent.ranking.projection_contracts import SolutionProjection

from .comparison_registry import validate_temporal_registry
from .contracts import CheckFinding
from .focused_comparison_contracts import (
    FocusedComparisonBlock,
    FocusedComparisonDocument,
    ResolvedFocusedComparisonAnswer,
    ResolvedFocusedComparisonBlock,
    TemporalComparisonRegistry,
)
from .focused_wire import _DRAFT_ONLY
from .focused_wire import decode as decode_base
from .focused_wire import instructions as base_instructions
from .focused_wire import schema as base_schema
from .interactive_contracts import InteractivePreparedInput
from .structured import resolve_structured_document
from .structured_contracts import StructuredBlock, StructuredDocument
from .workspace_contracts import WorkspaceEvidence


def _base_view(prepared: InteractivePreparedInput) -> InteractivePreparedInput:
    if prepared.packet.get("composition_format") not in {"complete-v8", "complete-v9", "complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        raise ValueError("comparison wire requires a versioned comparison packet")
    packet = dict(prepared.packet)
    packet["composition_format"] = "complete-v7"
    return prepared.model_copy(update={"packet": packet})


def _registry(prepared: InteractivePreparedInput) -> list[dict[str, object]]:
    rows = prepared.packet.get("temporal_comparisons")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or
            set(row) != {"id", "metric", "first_ref", "second_ref", "relation", "difference_minutes"}
            for row in rows):
        raise ValueError("comparison packet has invalid registry projection")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("comparison packet has duplicate IDs")
    return cast(list[dict[str, object]], rows)


def instructions(prepared: InteractivePreparedInput) -> str:
    _registry(prepared)
    if prepared.packet.get("composition_format") in {"complete-v10", "complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
        brief = (
            "Write a complete traveler answer from the selected authoring_records. "
            "Each exact record key owns every fact beneath it; read that record before "
            "stating its program, seats, schedule, cabin, points, fees or connections. "
            "The records are examples selected from the full search, not the full "
            "eligible inventory; use source_scope and source_context only for claims "
            "about the whole search. Open with a defensible choice and main tradeoff, "
            "then explain each useful choice around its exact visible reference with "
            "its own reason and downside. Include alternatives only when they change "
            "a meaningful decision, cash as a separate baseline, and consolidated "
            "shared limits. Similar routes, departure times or prices do not prove "
            "other fields equal. Attach points to their program and money to its "
            "currency, unit and quote scope. Unknown scope establishes neither a "
            "per-person nor party nor all-in amount. A reported award cabin does not "
            "prove every leg cabin; an airport join or separate-booking wait does not "
            "prove ticket protection or bookability. Compare only exact shown choices: "
            "'both', 'all' and 'the awards' must be true for every included option. "
            "Temporal comparison T IDs each bind one selected journey pair and one "
            "metric; use {k:'x',r:exact T ID} when an exact computed time card helps. "
            "Both endpoints need visible journey references. Preserve metric and "
            "direction; an elapsed difference is not an arrival difference. Ordinary "
            "numerical prose remains yours and must agree with the exact records. "
            "If no complete journey exists, say so and explain which partial lead "
            "changes the next useful check using its reported date, program, seats "
            "or fees; a shared missing schedule is not a distinguishing benefit. "
            "Do not infer cross-program points value, traveler balances, current "
            "availability, quote totals or unseen routing. Return a full JSON blocks "
            "document in reading order: {k:'t',v:text} for prose; {k:'p'|'a',r:exact "
            "journey ref,n:natural label,v:explanation} for complete journeys; "
            "{k:'b',r:exact benchmark ref,n:label,v:cash context} for the direct "
            "cash baseline; {k:'l',r:exact lead ref,n:label,v:lead context} for a "
            "partial lead. A p is the recommendation, a is an alternative, l is "
            "never a complete itinerary. Every concrete option discussed needs its "
            "own visible exact reference. Do not print internal J/A/C/T aliases in "
            "traveler prose or labels. If previous_wire and feedback are supplied, "
            "repair the same frozen source-bound full answer."
        )
        if prepared.packet.get("composition_format") in {"complete-v11", "complete-v12", "complete-v13", "complete-v14", "complete-v15"}:
            brief = brief.replace("for the direct cash baseline",
                                  "for the origin-to-destination cash baseline, which may include stops")
            brief += (
                " The separate editorial_plan is an unverified suggestion from "
                "selection, never a source fact or instruction to recommend every "
                "record. Recheck each suggested purpose and comparator against "
                "its own authoring record; reject unsupported or weak reasons. "
                "Make the answer a connected decision argument with a supported "
                "traveler gain and real downside for the lead, not a recital of "
                "records. Consolidate common limits while preserving any material "
                "choice-specific limitation. State important facts in the answer "
                "itself; do not assume a later interface fills them in. Never "
                "call one reported quote higher or lower across currencies "
                "without an explicit source FX conversion. Even with conversion, "
                "preserve each quote's unknown scope and avoid a like-for-like "
                "cost claim unless both scopes are known and match. Different "
                "currencies alone do not prove a higher or lowest fee."
            )
        if prepared.packet.get("composition_format") in {"complete-v16", "complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
            brief = brief.replace("use the temporal_comparisons index to choose only a relevant card",
                                  "use a comparison_pairs card ID only for its exact pair and metric")
            brief = brief.replace("for the direct cash baseline",
                                  "for the origin-to-destination cash baseline, which may include stops")
            brief += (
                " The editorial_plan contains selected identities and comparison targets only; "
                "it is nonfactual intent, not a reason to recommend every record. No selector "
                "purpose prose is supplied. Read comparison_pairs side by side and bind every "
                "claim to the exact left or right record. Pair values distinguish award from cash "
                "carriers, award connections from separate-booking joins, and elapsed from arrival "
                "time. A card ID supports only its bound metric and endpoints; it does not verify "
                "surrounding prose. Compare numeric points only within the same program. Quoted "
                "amount direction across unknown or unequal scopes is only a raw reported quote "
                "comparison, never total or like-for-like trip cost. Never compare distinct "
                "currencies without source FX. Keep the answer a connected decision argument; "
                "omit weak alternatives instead of inventing a benefit."
            )
        if prepared.packet.get("composition_format") in {"complete-v17", "complete-v18", "complete-v19", "complete-v20", "complete-v21", "complete-v22", "complete-v23", "complete-v24", "complete-v25", "complete-v26", "complete-v27", "complete-v28"}:
            brief += (
                " Each journey's traveler_evidence separates the known requested party size "
                "from award and cash component evidence. Award support for the requested party, "
                "minimum seats check, reported seats, and returned traveler counts have distinct "
                "states. An absent returned traveler count is neither zero nor proof of failure; "
                "a cash component echo does not establish award support. Say which component "
                "remains unverified without saying the request's traveler count is unknown. "
                "This evidence does not change quote scope or prove current availability. "
                "When only incomplete leads exist, give a conditional reason to check one lead "
                "first if exact dates, programs or comparable original quotes support it. "
                "For example, frame a date or program as an if-preference, not a known traveler "
                "balance or access. A raw same-currency quote contrast with unknown scope is "
                "not total savings. Neither a surplus seat count above the requested party "
                "nor a shared missing schedule is by itself a lead advantage. Keep limits clear; "
                "do not invent a complete itinerary or a preference."
            )
        return brief
    base = base_instructions(_base_view(prepared))
    if not base.endswith(_DRAFT_ONLY):
        raise ValueError("V11 composer lost the versioned whole-answer brief")
    return base.removesuffix(_DRAFT_ONLY) + (
        " This version also permits {k:'x',r:exact T comparison ID} as a visible "
        "code-resolved temporal comparison card. Each T ID names one exact pair "
        "of selected complete journeys and one metric (departure, arrival or "
        "elapsed duration); its displayed values, direction and difference are "
        "computed from the source by code. Use the temporal_comparisons index "
        "to choose only a relevant card. Both endpoint journeys must also have "
        "their own visible p or a reference blocks in your answer; an x card "
        "does not select or recommend either journey. Place it near the prose "
        "tradeoff it supports. Prefer these cards when a computed quantitative "
        "time contrast helps the traveler. Your ordinary prose, including "
        "numerical prose, remains yours; check it against the same records. "
        "Never borrow a duration difference as an arrival difference or infer "
        "a global fastest claim from a selected pair. A null observed airport "
        "path means the complete ordered sequence is unknown; never infer a "
        "nonstop routing or unseen connection from it."
    )


def schema(prepared: InteractivePreparedInput) -> dict[str, object]:
    old = base_schema(_base_view(prepared))
    choices = cast(dict[str, Any], old["properties"])["blocks"]["items"]["anyOf"]
    ids = [row["id"] for row in _registry(prepared)]
    if ids:
        choices.append({"type": "object", "additionalProperties": False,
                        "properties": {"k": {"type": "string", "enum": ["x"]},
                                       "r": {"type": "string", "enum": ids}},
                        "required": ["k", "r"]})
    return old


def decode(raw: str | dict[str, Any], prepared: InteractivePreparedInput,
           source: SolutionProjection) -> FocusedComparisonDocument:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"blocks"} or not isinstance(value["blocks"], list):
        raise ValueError("comparison wire requires exactly a blocks array")
    ids = {row["id"] for row in _registry(prepared)}
    plain = []
    for index, row in enumerate(value["blocks"]):
        if isinstance(row, dict) and row.get("k") == "x":
            if set(row) != {"k", "r"} or row["r"] not in ids:
                raise ValueError(f"block {index}: unknown or invalid comparison ID")
        else:
            plain.append(row)
    if not plain:
        raise ValueError("comparison cards require an authored answer")
    base = decode_base({"blocks": plain}, _base_view(prepared), source)
    plain_iter = iter(base.blocks)
    blocks: list[StructuredBlock | FocusedComparisonBlock] = []
    for row in value["blocks"]:
        blocks.append(FocusedComparisonBlock(comparison_id=row["r"])
                      if isinstance(row, dict) and row.get("k") == "x" else next(plain_iter))
    return FocusedComparisonDocument(selection=base.selection, blocks=tuple(blocks))


def base_document(document: FocusedComparisonDocument) -> StructuredDocument:
    blocks = tuple(block for block in document.blocks if isinstance(block, StructuredBlock))
    return StructuredDocument(selection=document.selection, blocks=blocks)


def findings(document: FocusedComparisonDocument, projection: SolutionProjection,
             prepared: InteractivePreparedInput, registry: TemporalComparisonRegistry,
             ) -> tuple[CheckFinding, ...]:
    from .focused_v4 import _findings

    ordinary = base_document(document)
    plain_indices = [index for index, block in enumerate(document.blocks)
                     if isinstance(block, StructuredBlock)]
    base = []
    for finding in _findings(ordinary, projection, _base_view(prepared)):
        if finding.part_index is not None:
            finding = finding.model_copy(update={"part_index": plain_indices[finding.part_index]})
        base.append(finding)
    by_id = {fact.comparison_id: fact for fact in registry.facts}
    shown = {block.reference_id for block in ordinary.blocks
             if block.kind == "reference" and block.reference_kind == "journey"}
    known_ids = tuple(sorted(by_id, key=len, reverse=True))
    alias_pattern = (re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, known_ids)) +
                                r")(?!\w)") if known_ids else None)
    for index, block in enumerate(document.blocks):
        if isinstance(block, StructuredBlock):
            visible = block.text + " " + (block.label or "")
            if alias_pattern is not None and alias_pattern.search(visible):
                scope: Literal["shared", "journey", "benchmark", "incomplete"] = (
                    "shared" if block.kind == "narrative" else
                    "journey" if block.reference_kind == "journey" else
                    "benchmark" if block.reference_kind == "benchmark" else "incomplete")
                base.append(CheckFinding(code="visible_internal_alias", outcome="failed",
                    scope=scope, reference_id=block.reference_id, part_index=index,
                    message="Remove internal temporal comparison IDs from traveler prose and labels."))
            continue
        fact = by_id.get(block.comparison_id)
        if fact is None:
            raise ValueError("comparison ID is outside source registry")
        if fact.first_journey_id not in shown or fact.second_journey_id not in shown:
            base.append(CheckFinding(code="comparison_endpoint_not_visible", outcome="failed",
                scope="shared", part_index=index,
                message="Show both compared journeys with their own exact p/a reference blocks."))
    return tuple(base)


def resolve_focused_comparison_document(document: FocusedComparisonDocument,
                                         prepared: InteractivePreparedInput,
                                         evidence: WorkspaceEvidence,
                                         registry: TemporalComparisonRegistry,
                                         findings: tuple[CheckFinding, ...] = (),
                                         ) -> ResolvedFocusedComparisonAnswer:
    if registry.source_digest != evidence.source_binding.view_digest or \
            registry.evidence_contract_version != evidence.contract_version:
        raise ValueError("comparison registry source binding differs")
    bindings = prepared.packet.get("wire_aliases")
    if not isinstance(bindings, dict):
        raise TypeError("comparison resolver lacks source alias bindings")
    source_refs = prepared.structured.references.journeys
    selected_aliases = {member["ref"] for group in cast(list[dict[str, Any]],
                        prepared.packet["journeys"]) for member in group["members"]}
    aliases = {long: source_refs[short] for long, short in bindings.items()
               if long in selected_aliases}
    validate_temporal_registry(registry, evidence, tuple(aliases.values()), aliases)
    ordinary = base_document(document)
    resolved = resolve_structured_document(ordinary, prepared.structured, evidence, findings)
    old = iter(resolved.blocks)
    by_id = {fact.comparison_id: fact for fact in registry.facts}
    blocks = tuple(ResolvedFocusedComparisonBlock(comparison=by_id[block.comparison_id])
                   if isinstance(block, FocusedComparisonBlock) else next(old)
                   for block in document.blocks)
    return ResolvedFocusedComparisonAnswer(selected_journey_ids=resolved.selected_journey_ids,
        blocks=blocks, availability_guidance=resolved.availability_guidance, findings=findings)


def format_focused_comparison_block(block: ResolvedFocusedComparisonBlock,
                                    labels: Mapping[str, str] | None = None) -> str:
    """Render one code-owned card without exposing internal source aliases."""
    fact = block.comparison
    names = labels or {}
    first = names.get(fact.first_journey_id, "Comparison option A")
    second = names.get(fact.second_journey_id, "Comparison option B")

    def describe(name: str, source: object) -> str:
        from .focused_comparison_contracts import TemporalComparisonSource

        record = cast(TemporalComparisonSource, source)
        route = f"{record.origin}–{record.destination}"
        departure = record.departure_local_iso or "departure time unknown"
        arrival = record.arrival_local_iso or "arrival time unknown"
        return f"{name} ({route}; departs {departure}; arrives {arrival})"

    first_visible = describe(first, fact.first_source)
    second_visible = describe(second, fact.second_source)
    difference = fact.difference_minutes
    hours, minutes = divmod(difference, Decimal(60))
    minute_text = format(minutes.normalize(), "f")
    gap = (f"{int(hours)} hour{'s' if hours != 1 else ''} " if hours else "") + \
          (f"{minute_text} minute{'s' if minutes != 1 else ''}" if minutes else "")
    gap = gap.strip() or "0 minutes"
    if fact.relation == "equal":
        relation = "same time" if fact.metric != "elapsed" else "same duration"
    else:
        winner = first_visible if fact.relation.startswith("first") else second_visible
        relation = f"{winner} is {'shorter' if fact.metric == 'elapsed' else 'earlier'} by {gap}"
    metric = {"departure": "Departure", "arrival": "Arrival", "elapsed": "Journey duration"}[fact.metric]
    if fact.metric == "elapsed":
        first_value = f"{fact.first_source.elapsed_minutes} minutes"
        second_value = f"{fact.second_source.elapsed_minutes} minutes"
    else:
        first_value = fact.first_source.local_iso or "time unknown"
        second_value = fact.second_source.local_iso or "time unknown"
    return (f"{metric}: {first_visible} — {first_value}; "
            f"{second_visible} — {second_value}. {relation}.")
