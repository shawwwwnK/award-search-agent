"""Offline lossless-meaning audit for the experimental joined semantic packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from decision_packet_v2 import build_packet as build_v2_packet
from decision_packet_v2 import join_v1_packet
from verify_packet import ROOT
from verify_packet import audit_case as audit_v1_case

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.interactive_packet import build_packet as build_v1_packet
from award_agent.results.structured_contracts import StructuredPreparedInput
from award_agent.results.workspace_contracts import WorkspaceEvidence


def _time(value: Any, zones: dict[str, str]) -> Any:
    if not isinstance(value, dict):
        return value
    assert set(value) == {"local_iso", "timezone"}
    code = next((key for key, name in zones.items() if name == value["timezone"]),
                value["timezone"])
    return f"{value['local_iso']}@{code}"


def _route(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    assert set(value) == {"origin", "destination"}
    return [value["origin"], value["destination"]]


def _component(facts: dict[str, Any], original: dict[str, Any],
               whole: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(facts)
    for key in original["legend"]["component_profile"]:
        if key not in ("depart", "arrive"):
            result.setdefault(key, "-")
    result["route"] = _route(result["route"])
    for field, legacy in (("departure", "depart"), ("arrival", "arrive")):
        value = result.pop(field, "-")
        if value == "same_as_journey":
            assert whole is not None
            value = whole[field]
        result[legacy] = _time(value, original["legend"]["timezones"])
    findings = result["findings"]
    assert all(code in original["finding_catalog"] for code in findings)
    result["findings"] = findings or "-"
    return result


def _journey(facts: dict[str, Any], original: dict[str, Any],
             alias: str) -> dict[str, Any]:
    result = {key: value for key, value in facts.items()
              if key not in ("award", "cash", "ranking_memberships")}
    result["route"] = _route(result["route"])
    result["depart"] = _time(result.pop("departure"), original["legend"]["timezones"])
    result["arrive"] = _time(result.pop("arrival"), original["legend"]["timezones"])
    result["transfer"] = [result["transfer"][key]
                          for key in ("airport", "minutes", "local_day_offset")]
    result["heuristic_cost"] = [result["heuristic_cost"][key]
                                 for key in original["legend"]["heuristic_cost"]]
    result["styles"] = [result["styles"][key] for key in original["legend"]["styles"]]
    caveats = [(item["code"] if item["state"] == "unknown" else
                [item["code"], item["state"]]) for item in result["caveats"]]
    assert caveats in original["caveat_profiles"]
    result["caveats"] = original["caveat_profiles"].index(caveats)
    expected_memberships = [key for key, aliases in original["ranking_hints"].items()
                            if alias in aliases]
    assert facts["ranking_memberships"] == expected_memberships
    return result


def _lead(facts: dict[str, Any], original: dict[str, Any],
          alias: str) -> list[Any]:
    result = dict(facts)
    result["route"] = _route(result["route"])
    timing = result["timing"]
    if isinstance(timing, dict):
        result["timing"] = [
            _time(timing["departure"], original["legend"]["timezones"]),
            _time(timing["arrival"], original["legend"]["timezones"]),
            timing["duration_minutes"],
        ]
    assert all(code in original["finding_catalog"] for code in result["findings"])
    result["A_or_C"] = alias
    return [result[key] for key in original["legend"]["lead_row"]]


def _members(groups: list[dict[str, Any]], label: str) -> list[tuple[str, dict[str, Any]]]:
    seen: set[str] = set()
    expanded = []
    fact_keys: set[str] = set()
    for group in groups:
        assert set(group) == {"members", "facts"}
        key = json.dumps(group["facts"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False)
        assert key not in fact_keys, f"byte-equal {label} facts split across groups"
        fact_keys.add(key)
        assert group["members"]
        for member in group["members"]:
            alias = member["ref"]
            assert alias not in seen, f"duplicate {label} alias {alias}"
            seen.add(alias)
            expanded.append((alias, group))
    return expanded


def audit_case(name: str) -> dict[str, object]:
    audit_v1_case(name)
    artifact = json.loads((ROOT / name / "artifact.json").read_text())
    prepared = StructuredPreparedInput.model_validate(artifact["prepared"])
    evidence = WorkspaceEvidence.model_validate(artifact["evidence"])
    source = SolutionProjection.model_validate(artifact["evidence"]["source"])
    before = [item.model_dump(mode="json") for item in (prepared, source, evidence)]
    original = build_v1_packet(prepared, source, evidence)
    packet = build_v2_packet(prepared, source, evidence)
    assert packet == join_v1_packet(original)
    assert packet["format"] == "decision-joined-v2"
    assert packet["finding_meanings"] == original["finding_catalog"]
    assert [item.model_dump(mode="json") for item in (prepared, source, evidence)] == before
    assert not {"journey_profiles", "journey_rows", "component_profiles",
                "component_rows", "lead_rows", "caveat_profiles", "finding_catalog"} & set(packet)
    for key in ("request", "policy", "comparison", "ranking_hints"):
        assert packet[key] == original[key]
    original_components = {alias: dict(zip(original["legend"]["component_profile"],
        original["component_profiles"][profile_id]))
        for alias, profile_id in original["component_rows"]}
    original_journeys = {alias: (profile_id, award, cash)
                         for alias, profile_id, award, cash in original["journey_rows"]}
    journey_members = _members(packet["journeys"], "journey")
    assert {alias for alias, _ in journey_members} == set(original_journeys)
    assert len(journey_members) == len(evidence.journeys)
    for alias, group in journey_members:
        member = next(member for member in group["members"] if member["ref"] == alias)
        profile_id, award, cash = original_journeys[alias]
        assert member == {"ref": alias, "award_ref": award, "cash_ref": cash}
        facts = group["facts"]
        assert _journey(facts, original, alias) == dict(zip(
            original["legend"]["journey_profile"], original["journey_profiles"][profile_id]))
        assert _component(facts["award"], original, facts) == original_components[award]
        assert (_component(facts["cash"], original, facts) if cash else None) == (
            original_components[cash] if cash else None)
        assert prepared.references.journeys[alias] in {
            journey.candidate_id for journey in evidence.journeys}
        assert prepared.references.awards[award] in {
            component.observation_id for component in evidence.components}
        if cash:
            assert prepared.references.cash[cash] in {
                component.observation_id for component in evidence.components}
    benchmark_members = _members(packet["benchmarks"], "benchmark")
    assert {alias for alias, _ in benchmark_members} == set(original["benchmark_refs"])
    for alias, group in benchmark_members:
        assert {member["ref"] for member in group["members"]} <= set(original["benchmark_refs"])
        assert _component(group["facts"], original) == original_components[alias]
        assert prepared.references.cash[alias] in evidence.direct_cash_benchmark_ids
    lead_members = _members(packet["leads"], "lead")
    original_leads = {row[0]: row for row in original["lead_rows"]}
    assert {alias for alias, _ in lead_members} == set(original_leads)
    assert len(lead_members) == len(evidence.leads)
    for alias, group in lead_members:
        assert {member["ref"] for member in group["members"]} <= set(original_leads)
        assert _lead(group["facts"], original, alias) == original_leads[alias]
        canonical = prepared.references.awards.get(alias, prepared.references.cash.get(alias))
        assert canonical in {lead.reference_id for lead in evidence.leads}
    expected_limits = [dict(zip(("kind", "status", "reason", "routes_and_dates"), row))
                       for row in original["source_context"]["coverage_limits"]]
    assert packet["source_context"] == {**original["source_context"],
                                         "coverage_limits": expected_limits}
    expected_relations = original["relations"]
    actual_relations = packet["relations"]
    assert actual_relations["timing_match_cross_cabin"] == expected_relations[
        "timing_match_cross_cabin"]
    assert [[item["award_ref"], _time(item["arrival"], original["legend"]["timezones"]),
             item["journey_refs"]] for item in actual_relations[
        "same_award_arrival_alternatives"]] == expected_relations[
            "same_award_arrival_alternatives"]
    assert [[item["request_route_match"], item["in_departure_window"],
             item["schedule_state"], item["lead_refs"]]
            for item in actual_relations["lead_relevance"]] == expected_relations["lead_relevance"]
    wire = json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    old_wire = json.dumps(original, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"journey_groups": len(packet["journeys"]), "journey_aliases": len(journey_members),
            "benchmark_groups": len(packet["benchmarks"]),
            "benchmark_aliases": len(benchmark_members),
            "lead_groups": len(packet["leads"]), "lead_aliases": len(lead_members),
            "wire_bytes": len(wire), "v1_wire_bytes": len(old_wire),
            "packet_sha256": hashlib.sha256(wire).hexdigest(),
            "rough_tokens_bytes_div_4": len(wire) // 4,
            "self_contained_source_join": "passed",
            "byte_equal_grouping_only": "passed",
            "source_unchanged": "passed"}


def main() -> None:
    cases = {name: audit_case(name) for name in ("admitted", "conditional", "incomplete")}
    output = {"cases": cases,
              "token_note": "Byte/4 is a rough size proxy, not an API token count.",
              "source_note": "Every exact alias and expanded field was audited against frozen v1 and typed canonical source; v1 source audit also passed.",
              "semantic_omissions": "None relative to v1's writer-visible decision fields; this is a representation-only expansion."}
    Path(__file__).with_name("packet-v2-audit.json").write_text(
        json.dumps(output, indent=2) + "\n")
    print(json.dumps(cases, indent=2))


if __name__ == "__main__":
    main()
