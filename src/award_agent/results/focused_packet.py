"""Exact model selection and selected-source packet for two-task Results authoring."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import combinations
from typing import Any, Literal

from award_agent.ranking.projection_contracts import SolutionProjection

from .interactive_packet_v3 import reference_grammar_mode
from .interactive_packet_v4 import build_packet as build_joined_packet
from .structured_contracts import StructuredPreparedInput, StructuredSelection
from .workspace_contracts import WorkspaceEvidence

MAX_JOURNEYS = 8
MAX_LEADS = 8
MAX_TOTAL_REFERENCES = 8


def _roles(prepared: StructuredPreparedInput,
           source: SolutionProjection) -> tuple[list[str], list[str], list[str]]:
    refs = prepared.references
    eligible = {item.candidate_id for item in source.view.alternatives
                if item.status in {"admitted", "conditional"}}
    benchmarks = set(source.view.direct_cash_observation_ids)
    leads = (set(source.view.award_summary_observation_ids) |
             set(source.view.unmatched_award_observation_ids) |
             set(source.view.unpaired_positioning_observation_ids))
    journeys = [alias for alias, canonical in refs.journeys.items() if canonical in eligible]
    cash = [alias for alias, canonical in refs.cash.items() if canonical in benchmarks]
    incomplete = [alias for alias, canonical in (refs.awards | refs.cash).items()
                  if canonical in leads]
    if len(journeys) != len(eligible) or len(cash) != len(benchmarks) or len(incomplete) != len(leads):
        raise ValueError("selection references do not cover every source role")
    return journeys, cash, incomplete


def _enum_or_string(aliases: list[str], *, all_count: int) -> dict[str, object]:
    if aliases and all_count <= 1000 and (len(aliases) <= 250 or
                                          sum(map(len, aliases)) <= 15000):
        return {"type": "string", "enum": aliases}
    return {"type": "string"}


def selection_schema(prepared: StructuredPreparedInput,
                     source: SolutionProjection) -> dict[str, object]:
    journeys, cash, leads = _roles(prepared, source)
    total = len(journeys) + len(cash) + len(leads)
    j_item = _enum_or_string(journeys, all_count=total)
    l_item = _enum_or_string(leads, all_count=total)
    benchmark: dict[str, object] = ({"anyOf": [
        _enum_or_string(cash, all_count=total), {"type": "null"}]}
        if cash else {"type": "null"})
    return {"type": "object", "additionalProperties": False,
            "properties": {
                "journeys": {"type": "array", "items": j_item,
                             "minItems": 1 if journeys else 0,
                             "maxItems": MAX_JOURNEYS if journeys else 0},
                "benchmark": benchmark,
                "leads": {"type": "array", "items": l_item,
                          "minItems": 1 if not journeys and leads else 0,
                          "maxItems": MAX_LEADS if leads else 0},
            }, "required": ["journeys", "benchmark", "leads"]}


def selection_schema_v2(prepared: StructuredPreparedInput,
                        source: SolutionProjection) -> dict[str, object]:
    """Bound the entire selection with one array, independent of role mix."""
    journeys, cash, leads = _roles(prepared, source)
    roles = (("j", journeys), ("b", cash), ("l", leads))
    kind_count = sum(bool(aliases) for _, aliases in roles)
    all_count = sum(len(aliases) for _, aliases in roles) + kind_count
    branches: list[dict[str, object]] = []
    for kind, aliases in roles:
        if aliases:
            branches.append({"type": "object", "additionalProperties": False,
                             "properties": {"k": {"type": "string", "enum": [kind]},
                                            "r": _enum_or_string(aliases, all_count=all_count)},
                             "required": ["k", "r"]})
    # An empty array needs a valid item schema even though maxItems is zero.
    item_schema: dict[str, object] = ({"anyOf": branches} if branches else
        {"type": "object", "additionalProperties": False,
         "properties": {"k": {"type": "string"}, "r": {"type": "string"}},
         "required": ["k", "r"]})
    return {"type": "object", "additionalProperties": False,
            "properties": {"choices": {"type": "array", "items": item_schema,
                                       "minItems": 1 if branches else 0,
                                       "maxItems": MAX_TOTAL_REFERENCES if branches else 0}},
            "required": ["choices"]}


def selection_instructions_v2(prepared: StructuredPreparedInput,
                              source: SolutionProjection) -> str:
    journeys, cash, leads = _roles(prepared, source)
    text = (
        "Choose source references for one traveler answer from the COMPLETE indexed "
        "decision packet. Return only JSON choices, no prose or copied source facts. "
        "Every choice is {k:'j'|'b'|'l',r:exact packet alias}: j is an eligible "
        "complete journey, b is one direct cash benchmark, and l is an incomplete "
        "award or positioning lead. Use each source role exactly. The choices array "
        "has a strict maximum of eight references TOTAL, including any cash benchmark; "
        "that is a ceiling, not a target to fill. Use no duplicate references and "
        "at most one b. Prefer a small useful set, typically 2–3 meaningfully "
        "different complete journeys plus one cash benchmark when available. "
        "When complete journeys exist, include a partial lead only if it adds "
        "distinct decision value; usually none is needed. With no complete "
        "journey, choose 2–3 relevant leads plus cash context when available. "
        "Select defensibly from route, timing, "
        "reported cabin scope, traveler and seat evidence, fare scope, costs and "
        "caveats. Points across programs are not comparable economic costs. "
        "The selected choices will receive exact source facts before writing.")
    if not journeys:
        text += (" No complete eligible journey exists; choose a relevant l when "
                 "leads exist. Do not treat a date-only lead as a timed itinerary.")
    if not leads:
        text += " No incomplete lead exists; do not choose l."
    if not cash:
        text += " No direct cash benchmark exists; do not choose b."
    return text


def decode_selection_v2(raw: str | dict[str, Any], prepared: StructuredPreparedInput,
                        source: SolutionProjection) -> StructuredSelection:
    """Validate exact role membership and preserve the model's chosen order."""
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"choices"}:
        raise ValueError("selection must have exactly a choices array")
    choices = value["choices"]
    if not isinstance(choices, list) or len(choices) > MAX_TOTAL_REFERENCES:
        raise ValueError("selection choices exceed the eight-reference bundle")
    selected: dict[str, list[str]] = {"j": [], "b": [], "l": []}
    for index, item in enumerate(choices):
        if not isinstance(item, dict) or set(item) != {"k", "r"} or \
                item.get("k") not in selected or not isinstance(item.get("r"), str):
            raise ValueError(f"choice {index} has invalid role or reference fields")
        selected[item["k"]].append(item["r"])
    if len(selected["b"]) > 1:
        raise ValueError("selection has more than one cash benchmark")
    return decode_selection({"journeys": selected["j"],
                             "benchmark": selected["b"][0] if selected["b"] else None,
                             "leads": selected["l"]}, prepared, source)


def selection_instructions(prepared: StructuredPreparedInput,
                           source: SolutionProjection) -> str:
    journeys, cash, leads = _roles(prepared, source)
    basis = (
        "Choose source references for one traveler answer from the COMPLETE indexed "
        "decision packet. This is selection only: return JSON aliases, no prose. "
        "You own the choices. Each journey is eligible but may be conditional; "
        "award summaries and partial components are leads, not complete journeys. "
        "Use exact J aliases for journeys, one exact direct cash C alias or null, "
        "and exact A/C lead aliases for partial observations. Every alias must "
        "match its source role. Prefer 2–4 meaningfully different journeys when "
        "the evidence supports them, plus relevant cash context and a few leads "
        "when useful. Do not choose a cash benchmark as an award journey. "
        "Selection must be defensible from route, timing, cabin scope, traveler "
        "support, fare scope, costs and relevant caveats; avoid unsupported "
        "cross-program economic ordering. Return no more than eight journeys "
        "and eight leads, and no more than eight references total including "
        "the benchmark; exceeding a bound is a failure, not truncation.")
    if not journeys:
        basis += (" No complete eligible journey exists; return journeys=[] and "
                  "select relevant incomplete leads when available. Do not imply "
                  "a date-only summary is a timed complete itinerary.")
    elif not leads:
        basis += " No incomplete leads are present; return leads=[]."
    if not cash:
        basis += " No direct cash benchmark is present; return benchmark=null."
    return basis


def decode_selection(raw: str | dict[str, Any], prepared: StructuredPreparedInput,
                     source: SolutionProjection) -> StructuredSelection:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(value, dict) or set(value) != {"journeys", "benchmark", "leads"}:
        raise ValueError("selection must have exactly journeys, benchmark and leads")
    journeys, cash, leads = _roles(prepared, source)
    chosen_j, chosen_b, chosen_l = value["journeys"], value["benchmark"], value["leads"]
    if not isinstance(chosen_j, list) or not isinstance(chosen_l, list):
        raise TypeError("selection journeys and leads must be arrays")
    if not (1 if journeys else 0) <= len(chosen_j) <= (MAX_JOURNEYS if journeys else 0):
        raise ValueError("selection journey count is outside source-specific bounds")
    if not (1 if not journeys and leads else 0) <= len(chosen_l) <= (MAX_LEADS if leads else 0):
        raise ValueError("selection lead count is outside source-specific bounds")
    if len(chosen_j) + len(chosen_l) + (chosen_b is not None) > MAX_TOTAL_REFERENCES:
        raise ValueError("selection exceeds the eight-reference authoring bundle")
    if (any(not isinstance(item, str) for item in (*chosen_j, *chosen_l)) or
            len(set(chosen_j)) != len(chosen_j) or len(set(chosen_l)) != len(chosen_l)):
        raise ValueError("selection has non-string or duplicate aliases")
    if not set(chosen_j) <= set(journeys) or not set(chosen_l) <= set(leads):
        raise ValueError("selection has unknown or wrong-role references")
    if chosen_b is not None and (not isinstance(chosen_b, str) or chosen_b not in cash):
        raise ValueError("selection has an unknown or wrong-role cash benchmark")
    refs = prepared.references
    return StructuredSelection(
        journey_ids=tuple(refs.journeys[item] for item in chosen_j),
        benchmark_observation_id=refs.cash[chosen_b] if chosen_b else None,
        incomplete_observation_ids=tuple((refs.awards | refs.cash)[item]
                                             for item in chosen_l))


def _observed_path(facts: dict[str, Any]) -> list[str] | None:
    topology = facts["topology"]
    if topology not in {"award_only", "cash_access_award", "award_cash_egress"}:
        raise ValueError("selected journey has an unsupported packet topology")
    award = facts["award"]
    award_airports = award.get("airports")
    if not isinstance(award_airports, list) or len(award_airports) < 2:
        return None
    if topology == "award_only":
        result = award_airports
    elif topology in {"cash_access_award", "award_cash_egress"}:
        cash_facts = facts["cash"]
        if not isinstance(cash_facts, dict):
            raise ValueError("selected mixed journey lacks a cash component")
        cash_airports = cash_facts.get("airports")
        if not isinstance(cash_airports, list) or len(cash_airports) < 2:
            return None
        if topology == "cash_access_award":
            if cash_airports[-1] != award_airports[0]:
                raise ValueError("selected cash access and award do not join exactly")
            result = [*cash_airports, *award_airports[1:]]
        else:
            if award_airports[-1] != cash_airports[0]:
                raise ValueError("selected award and cash egress do not join exactly")
            result = [*award_airports, *cash_airports[1:]]
    route = facts["route"]
    if result[0] != route["origin"] or result[-1] != route["destination"]:
        raise ValueError("selected observed path differs from journey route")
    return result


def _selected_cross_cabin(row: list[str], selected: set[str],
                          cabins: dict[str, str | None]) -> list[str] | None:
    members = [item for item in row if item in selected]
    known = {cabins.get(item) for item in members if cabins.get(item) not in
             {None, "unknown", "absent", "null", "-"}}
    return members if len(known) >= 2 else None


def _exact_minutes(value: object) -> Decimal | None:
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() and number >= 0 else None


def _aware_instant(value: object) -> datetime | None:
    if not isinstance(value, dict) or not isinstance(value.get("local_iso"), str):
        return None
    try:
        instant = datetime.fromisoformat(value["local_iso"])
    except ValueError:
        return None
    return instant if instant.tzinfo is not None and instant.utcoffset() is not None else None


def _minute_difference(left: datetime, right: datetime) -> Decimal:
    delta = right - left
    microseconds = ((delta.days * 86400 + delta.seconds) * 1000000 +
                    delta.microseconds)
    return Decimal(microseconds) / Decimal(60000000)


def _duration_label(minutes: Decimal) -> str:
    if minutes == minutes.to_integral_value():
        hours, remainder = divmod(int(minutes), 60)
        if hours:
            return f"{hours}h {remainder}m" if remainder else f"{hours}h"
    return f"{minutes} min"


def _comparison(metric: str, left: dict[str, Any],
                right: dict[str, Any]) -> tuple[int, Decimal] | None:
    if metric == "elapsed_minutes":
        left_value = _exact_minutes(left.get("elapsed_minutes"))
        right_value = _exact_minutes(right.get("elapsed_minutes"))
        if left_value is None or right_value is None:
            return None
        return ((-1 if left_value < right_value else 1 if left_value > right_value else 0),
                abs(right_value - left_value))
    endpoint = "origin" if metric == "departure_instant" else "destination"
    left_route, right_route = left.get("route"), right.get("route")
    if (not isinstance(left_route, dict) or not isinstance(right_route, dict) or
            not isinstance(left_route.get(endpoint), str) or
            left_route[endpoint] != right_route.get(endpoint)):
        return None
    field = "departure" if metric == "departure_instant" else "arrival"
    left_instant = _aware_instant(left.get(field))
    right_instant = _aware_instant(right.get(field))
    if left_instant is None or right_instant is None:
        return None
    return ((-1 if left_instant < right_instant else 1 if left_instant > right_instant else 0),
            _minute_difference(min(left_instant, right_instant),
                               max(left_instant, right_instant)))


def selected_comparisons(journeys: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Compute exact pair facts for shown journeys; missing facts yield no comparison."""
    if sum(len(group["members"]) for group in journeys) > MAX_JOURNEYS:
        raise ValueError("comparison pool exceeds focused journey bound")
    rows = [(member["ref"], group["facts"]) for group in journeys
            for member in group["members"]]
    comparisons: dict[str, list[dict[str, str]]] = {
        "elapsed_minutes": [], "departure_instant": [], "arrival_instant": []}
    for (left_ref, left), (right_ref, right) in combinations(rows, 2):
        for metric, records in comparisons.items():
            compared = _comparison(metric, left, right)
            if compared is None:
                continue
            direction, difference = compared
            if direction == 0:
                records.append({"relation": "equal", "first": left_ref,
                                            "second": right_ref, "difference_minutes": "0",
                                            "difference_display": "0 min"})
            else:
                first_ref, second_ref = ((left_ref, right_ref) if direction < 0 else
                                         (right_ref, left_ref))
                records.append({
                    "relation": "shorter_than" if metric == "elapsed_minutes" else "earlier_than",
                    "first": first_ref, "second": second_ref,
                    "difference_minutes": str(difference),
                    "difference_display": _duration_label(difference)})
    return comparisons


def build_packet(selection: StructuredSelection, prepared: StructuredPreparedInput,
                 source: SolutionProjection, evidence: WorkspaceEvidence, *,
                 selection_format: Literal["roles-v1", "roles-v2"] = "roles-v1",
                 composition_format: Literal["source-v1", "comparisons-v1"] = "source-v1",
                 ) -> dict[str, Any]:
    """Expose only the model-selected exact source facts to the composer."""
    _roles(prepared, source)
    refs = prepared.references
    reverse = {canonical: alias for alias, canonical in
               (refs.journeys | refs.awards | refs.cash).items()}
    selected_j = [reverse[item] for item in selection.journey_ids]
    selected_b = None
    if selection.benchmark_observation_id is not None:
        if selection.benchmark_observation_id not in reverse:
            raise ValueError("selected benchmark has no exact source reference")
        selected_b = reverse[selection.benchmark_observation_id]
    selected_l = [reverse[item] for item in selection.incomplete_observation_ids]
    # Reapply exact role/count validation without silently fixing malformed input.
    decode_selection({"journeys": selected_j, "benchmark": selected_b,
                      "leads": selected_l}, prepared, source)
    full = build_joined_packet(prepared, source, evidence)
    by_short = {short: new for new, short in full["wire_aliases"].items()}
    selected_new_j = {by_short[item] for item in selected_j}
    selected_new_b = {by_short[selected_b]} if selected_b else set()
    selected_new_l = {by_short[item] for item in selected_l}
    packet = deepcopy(full)

    for section, allowed in (("journeys", selected_new_j),
                             ("benchmarks", selected_new_b), ("leads", selected_new_l)):
        filtered = []
        for group in full[section]:
            members = [member for member in group["members"] if member["ref"] in allowed]
            if members:
                facts = deepcopy(group["facts"])
                if section == "journeys":
                    facts["observed_airport_path"] = _observed_path(facts)
                filtered.append({"members": members, "facts": facts})
        packet[section] = filtered
        if {member["ref"] for group in filtered for member in group["members"]} != allowed:
            raise ValueError(f"selected {section} has no exact joined source facts")
    packet["ranking_hints"] = {key: [item for item in value if item in selected_new_j]
                               for key, value in full["ranking_hints"].items()}
    # Relations are evidence about the complete source pool. Stage two may make
    # comparisons only among shown choices, so keep only selected members.
    relations = full["relations"]
    selected_cabins = {member["ref"]: group["facts"].get("award_cabin")
                       for group in packet["journeys"] for member in group["members"]}
    packet["relations"] = {
        "same_award_arrival_alternatives": [
            {**row, "journey_refs": [item for item in row["journey_refs"]
                                     if item in selected_new_j]}
            for row in relations["same_award_arrival_alternatives"]
            if len([item for item in row["journey_refs"] if item in selected_new_j]) >= 2],
        "timing_match_cross_cabin": [cross_members for row in
            relations["timing_match_cross_cabin"]
            if (cross_members := _selected_cross_cabin(row, selected_new_j,
                                                        selected_cabins)) is not None],
        "lead_relevance": [
            {**row, "lead_refs": [item for item in row["lead_refs"]
                                if item in selected_new_l]}
            for row in relations["lead_relevance"]
            if any(item in selected_new_l for item in row["lead_refs"])],
    }
    # The decoder's local map is retained in the prepared artifact; the runtime
    # removes it from the writer payload, leaving only selected visible facts.
    used_refs = {member[key] for section in ("journeys", "benchmarks", "leads")
                 for group in packet[section] for member in group["members"]
                 for key in ("ref", "award_ref", "cash_ref")
                 if key in member and member[key] is not None}
    packet["wire_aliases"] = {new: old for new, old in full["wire_aliases"].items()
                              if new in used_refs}
    packet["format"] = "focused-v1"
    packet["outcome_mode"] = "complete_choices" if selected_j else "no_complete_journey"
    packet["wire_reference_grammar"] = reference_grammar_mode(packet)
    if selection_format == "roles-v2":
        packet["selection_format"] = "roles-v2"
        packet["legend"]["observed_airport_path"] = (
            "Ordered airport sequence joined only at an equal cash/award boundary "
            "when both source component sequences exist; null means the full "
            "observed sequence is unknown. It does not prove same aircraft, "
            "ticket protection or bookability.")
    elif selection_format == "roles-v1":
        # Keep saved V8 v1 packets byte-for-byte replayable.
        packet["legend"]["observed_airport_path"] = (
            "Ordered airport sequence joined only at equal cash-access/award boundary; "
            "it does not prove same aircraft, ticket protection or bookability.")
    else:
        raise ValueError("unknown focused selection format")
    packet["selection_scope"] = {
        "journey_count": len(selected_j), "lead_count": len(selected_l),
        "benchmark_selected": selected_b is not None,
        "meaning": "These are the model-selected facts only; comparisons and superlatives "
                   "must be limited to shown choices, not the unseen eligible pool."}
    if composition_format == "comparisons-v1":
        packet["composition_format"] = composition_format
        packet["selected_comparisons"] = selected_comparisons(packet["journeys"])
    elif composition_format != "source-v1":
        raise ValueError("unknown focused composition format")
    return packet
