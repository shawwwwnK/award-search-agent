"""Offline fidelity and role audit for the two-task Luna Results candidate."""

from __future__ import annotations

import json
from pathlib import Path

from award_agent.providers.contracts import content_digest
from award_agent.results.focused_packet import (
    _enum_or_string,
    _observed_path,
    _roles,
    _selected_cross_cabin,
    build_packet,
    decode_selection,
    decode_selection_v2,
    selection_instructions,
    selection_instructions_v2,
    selection_schema,
    selection_schema_v2,
)
from award_agent.results.focused_wire import decode, instructions, schema
from award_agent.results.interactive_contracts import InteractivePreparedInput
from award_agent.results.interactive_packet import build_packet as build_indexed
from award_agent.results.interactive_packet_v4 import build_packet as build_full_joined
from award_agent.results.structured_contracts import StructuredResultsArtifact, StructuredSelection

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def _must_fail(call: object, *args: object) -> None:
    try:
        call(*args)  # type: ignore[operator]
    except (ValueError, TypeError):
        return
    raise AssertionError("malformed or out-of-scope reference was accepted")


def _case(name: str) -> dict[str, object]:
    artifact = StructuredResultsArtifact.model_validate_json(
        (SOURCE / name / "artifact.json").read_text(encoding="utf-8"))
    prepared, source, evidence = artifact.prepared, artifact.evidence.source, artifact.evidence
    before = (prepared.model_dump(mode="json"), source.model_dump(mode="json"),
              evidence.model_dump(mode="json"))
    indexed = build_indexed(prepared, source, evidence)
    journeys, cash, leads = _roles(prepared, source)
    assert len(indexed["journey_rows"]) == len(journeys)
    assert len(indexed["benchmark_refs"]) == len(cash)
    assert len(indexed["lead_rows"]) == len(leads)
    stage1 = selection_schema(prepared, source)
    stage1_v2 = selection_schema_v2(prepared, source)
    v2_choices = stage1_v2["properties"]["choices"]
    assert v2_choices["maxItems"] == 8
    assert "eight references TOTAL" in selection_instructions_v2(prepared, source)
    assert {branch["properties"]["k"]["enum"][0]
            for branch in v2_choices["items"]["anyOf"]} == (
                ({"j"} if journeys else set()) |
                ({"b"} if cash else set()) |
                ({"l"} if leads else set()))
    assert "no prose" in selection_instructions(prepared, source)
    assert stage1["properties"]["journeys"]["minItems"] == (1 if journeys else 0)
    assert stage1["properties"]["leads"]["minItems"] == (1 if not journeys and leads else 0)
    if not journeys:
        assert stage1["properties"]["journeys"] == {
            "type": "array", "items": {"type": "string"},
            "minItems": 0, "maxItems": 0}
    assert _enum_or_string(["J1"] * 1001, all_count=1001) == {"type": "string"}
    assert _enum_or_string(["J1"], all_count=1)["enum"] == ["J1"]
    assert _enum_or_string([], all_count=0) == {"type": "string"}
    # An otherwise valid source can have no partial leads, and a no-result
    # source can have no role at all. Neither schema may contain enum: [].
    no_leads_view = source.view.model_copy(update={
        "award_summary_observation_ids": (), "unmatched_award_observation_ids": (),
        "unpaired_positioning_observation_ids": ()})
    no_leads_source = source.model_copy(update={"view": no_leads_view})
    no_leads_schema = selection_schema(prepared, no_leads_source)
    assert no_leads_schema["properties"]["leads"] == {
        "type": "array", "items": {"type": "string"},
        "minItems": 0, "maxItems": 0}
    empty_view = no_leads_view.model_copy(update={
        "alternatives": (), "direct_cash_observation_ids": ()})
    empty_source = source.model_copy(update={"view": empty_view})
    empty_schema = selection_schema(prepared, empty_source)
    empty_v2_schema = selection_schema_v2(prepared, empty_source)
    assert empty_v2_schema["properties"]["choices"]["maxItems"] == 0
    assert "enum" not in str(empty_v2_schema)
    assert empty_schema["properties"]["journeys"]["items"] == {"type": "string"}
    assert empty_schema["properties"]["leads"]["items"] == {"type": "string"}
    assert empty_schema["properties"]["benchmark"] == {"type": "null"}
    assert empty_schema["properties"]["journeys"]["maxItems"] == 0
    assert empty_schema["properties"]["leads"]["maxItems"] == 0

    chosen_j = journeys[:3]
    chosen_b = cash[0] if cash else None
    chosen_l = leads[:2] if not journeys else leads[:1]
    raw = {"journeys": chosen_j, "benchmark": chosen_b, "leads": chosen_l}
    selection = decode_selection(raw, prepared, source)
    v2_rows = ([{"k": "j", "r": item} for item in chosen_j] +
               ([{"k": "b", "r": chosen_b}] if chosen_b else []) +
               [{"k": "l", "r": item} for item in chosen_l])
    assert decode_selection_v2({"choices": v2_rows}, prepared, source) == selection
    _must_fail(decode_selection_v2,
               {"choices": [*v2_rows, *([{"k": "l", "r": leads[2]}] * 8)]},
               prepared, source)
    assert len(chosen_j) + bool(chosen_b) + len(chosen_l) <= 8
    if journeys:
        _must_fail(decode_selection, {**raw, "journeys": []}, prepared, source)
        _must_fail(decode_selection, {**raw, "journeys": [leads[0]] if leads else ["A1"]},
                   prepared, source)
        _must_fail(decode_selection, {**raw, "journeys": [journeys[0]] * 2}, prepared,
                   source)
        if len(journeys) >= 8:
            _must_fail(decode_selection, {**raw, "journeys": journeys[:8],
                                          "leads": leads[:1]}, prepared, source)
    else:
        _must_fail(decode_selection, {**raw, "journeys": ["J1"]}, prepared, source)
        if leads:
            _must_fail(decode_selection, {**raw, "leads": []}, prepared, source)
    if cash:
        _must_fail(decode_selection, {**raw, "benchmark": leads[0] if leads else "A1"},
                   prepared, source)
        _must_fail(build_packet,
                   StructuredSelection(journey_ids=selection.journey_ids,
                       benchmark_observation_id="not-a-source-benchmark",
                       incomplete_observation_ids=selection.incomplete_observation_ids),
                   prepared, source, evidence)
    _must_fail(decode_selection, {**raw, "leads": ["A999999"]}, prepared, source)

    full = build_full_joined(prepared, source, evidence)
    focused = build_packet(selection, prepared, source, evidence)
    assert focused["format"] == "focused-v1"
    focus_v2 = build_packet(selection, prepared, source, evidence,
                            selection_format="roles-v2")
    assert focus_v2["selection_format"] == "roles-v2"
    for section in ("journeys", "benchmarks", "leads"):
        assert focus_v2[section] == focused[section]
    for key in ("request", "policy", "comparison", "source_context", "finding_meanings"):
        assert focused[key] == full[key], f"global {key} changed"
    assert focused["outcome_mode"] == ("complete_choices" if journeys else
                                       "no_complete_journey")
    by_short = {old: new for new, old in full["wire_aliases"].items()}
    expected = {"journeys": {by_short[item] for item in chosen_j},
                "benchmarks": {by_short[chosen_b]} if chosen_b else set(),
                "leads": {by_short[item] for item in chosen_l}}
    for section, selected_aliases in expected.items():
        seen = set()
        for group in focused[section]:
            facts = {key: value for key, value in group["facts"].items()
                     if key != "observed_airport_path"}
            old_group = next(item for item in full[section]
                             if item["facts"] == facts and
                             {member["ref"] for member in group["members"]} <=
                             {member["ref"] for member in item["members"]})
            assert old_group["facts"] == facts
            if section == "journeys":
                observed = group["facts"]["observed_airport_path"]
                award = facts["award"]["airports"]
                if facts["topology"] == "award_only":
                    assert observed == award
                elif facts["topology"] == "cash_access_award":
                    access = facts["cash"]["airports"]
                    assert access[-1] == award[0]
                    assert observed == access + award[1:]
                elif facts["topology"] == "award_cash_egress":
                    egress = facts["cash"]["airports"]
                    assert award[-1] == egress[0]
                    assert observed == award + egress[1:]
                else:
                    raise AssertionError("unknown topology")
            seen.update(member["ref"] for member in group["members"])
        assert seen == selected_aliases
    assert all(set(value) <= expected["journeys"] for value in
               focused["ranking_hints"].values())
    assert set(focused["wire_aliases"]) <= set(full["wire_aliases"])
    visible = {key: value for key, value in focused.items() if key != "wire_aliases"}
    visible_bytes = len(json.dumps(visible, ensure_ascii=False).encode())
    assert visible_bytes < 60000, "selected writer packet exceeds rough 15k-token target"
    assert (prepared.model_dump(mode="json"), source.model_dump(mode="json"),
            evidence.model_dump(mode="json")) == before

    composer = InteractivePreparedInput(structured=prepared, packet=focused,
        packet_digest=content_digest(focused), source_digest=source.receipt.view_digest)
    brief = instructions(composer)
    assert "Compare only shown choices" in brief
    assert "Do not claim overall best" in brief
    wire = schema(composer)
    choices = wire["properties"]["blocks"]["items"]["anyOf"]
    assert bool(chosen_j) == any(option["properties"]["k"]["enum"] == ["p", "a"]
                                 for option in choices)
    if chosen_j:
        valid = {"blocks": [{"k": "p", "r": next(iter(expected["journeys"])),
                             "n": "Choice", "v": "Context"}]}
        result = decode(valid, composer, source)
        assert result.selection.journey_ids
        unselected = next((by_short[item] for item in journeys if item not in chosen_j), None)
        if unselected:
            _must_fail(decode, {"blocks": [{"k": "p", "r": unselected,
                                            "n": "Wrong", "v": "Context"}]},
                       composer, source)
    else:
        valid = {"blocks": [{"k": "l", "r": next(iter(expected["leads"])),
                             "n": "Lead", "v": "Context"}]}
        result = decode(valid, composer, source)
        assert result.selection.incomplete_observation_ids
        _must_fail(decode, {"blocks": [{"k": "p", "r": next(iter(expected["leads"])),
                                        "n": "Wrong", "v": "Context"}]}, composer, source)
    return {"stage1_journeys": len(journeys), "stage1_benchmarks": len(cash),
            "stage1_leads": len(leads), "stage2_journeys": len(chosen_j),
            "stage2_benchmarks": bool(chosen_b), "stage2_leads": len(chosen_l),
            "stage2_visible_bytes": visible_bytes, "source_fidelity": "passed",
            "exact_selected_roles": "passed", "v2_total_schema_limit": "passed"}


def main() -> None:
    assert _selected_cross_cabin(["J1", "J2", "J3"], {"J1", "J2"},
                                 {"J1": "economy", "J2": "economy",
                                  "J3": "business"}) is None
    assert _selected_cross_cabin(["J1", "J2", "J3"], {"J1", "J3"},
                                 {"J1": "economy", "J2": "economy",
                                  "J3": "business"}) == ["J1", "J3"]
    assert _selected_cross_cabin(["J1", "J2"], {"J1", "J2"},
                                 {"J1": "unknown", "J2": "economy"}) is None
    egress = {"topology": "award_cash_egress",
              "route": {"origin": "SFO", "destination": "BKK"},
              "award": {"airports": ["SFO", "HKG"]},
              "cash": {"airports": ["HKG", "BKK"]}}
    assert _observed_path(egress) == ["SFO", "HKG", "BKK"]
    broken = {**egress, "cash": {"airports": ["TPE", "BKK"]}}
    _must_fail(_observed_path, broken)
    assert _observed_path({"topology": "award_only", "award": {},
                           "route": {"origin": "SFO", "destination": "BKK"}}) is None
    cases = {name: _case(name) for name in ("admitted", "conditional", "incomplete")}
    result = {"cases": cases,
              "source_scope": "full eligible indexed selection; only model-selected exact facts "
              "in composer; canonical source/explorer intact", "no_truncation": "passed"}
    (HERE / "focused-audit.json").write_text(json.dumps(result, indent=2) + "\n",
                                            encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
