"""Offline integrity and size audit for the experimental decision packet."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from decision_packet import TIMEZONE_CODES, build_packet

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection, SolutionView
from award_agent.results.structured_contracts import StructuredPreparedInput
from award_agent.results.workspace_contracts import WorkspaceEvidence

ROOT = Path(__file__).resolve().parents[1] / (
    "2026-10-25-cost-experiments/luna-retest/round-1"
)
KNOWN_DIGESTS = {
    "admitted": "ce57bc6e2b6ae3dc959dfc7c7df16150d4ccda7089329b37eb466c456468c33e",
    "conditional": "335593ff8ab01ce63f82d661f47b435ba9e9935ae88eefcd7c4baa9595bd6ecb",
    "incomplete": "86d80485bc1ba8600ebba3874cc2758d9f756300ee8cd8f26bc9420e6f8a4a39",
}


def raw(field: object) -> object:
    return field.value if field.state == "value" else field.state


def profile_raw(field: object) -> object:
    value = raw(field)
    return "-" if value in (None, "absent", []) else value


def time_value(projected: object) -> str | None:
    if projected.local_iso is None:
        return None
    return f"{projected.local_iso}@{TIMEZONE_CODES.get(projected.timezone, projected.timezone)}"


def audit_case(name: str) -> dict[str, object]:
    artifact = json.loads((ROOT / name / "artifact.json").read_text())
    prepared = StructuredPreparedInput.model_validate(artifact["prepared"])
    evidence = WorkspaceEvidence.model_validate(artifact["evidence"])
    source = SolutionProjection.model_validate(artifact["evidence"]["source"])
    packet = build_packet(prepared, source, evidence)
    refs = prepared.references
    jrows = packet["journey_rows"]
    crows = packet["component_rows"]
    lead_rows = packet["lead_rows"]
    assert len(jrows) == len(evidence.journeys) == len(refs.journeys)
    assert {row[0] for row in jrows} == set(refs.journeys)
    expected_component_aliases = (set(packet["benchmark_refs"]) |
        {row[2] for row in jrows} | {row[3] for row in jrows if row[3]})
    assert len(crows) == len(expected_component_aliases)
    assert {canonical for canonical in refs.awards.values()} | set(refs.cash.values()) <= {
        component.observation_id for component in evidence.components
    }
    assert {row[0] for row in crows} == expected_component_aliases
    assert len(lead_rows) == len(evidence.leads)
    assert {refs.awards.get(row[0], refs.cash.get(row[0])) for row in lead_rows} == {
        lead.reference_id for lead in evidence.leads
    }
    assert set(packet["benchmark_refs"]) == {
        alias for alias, canonical in refs.cash.items()
        if canonical in evidence.direct_cash_benchmark_ids
    }
    assert {ref for group in packet["relations"]["lead_relevance"]
            for ref in group[3]} == {row[0] for row in lead_rows}
    assert packet["source_context"]["observed_at_range"] == [
        min(component.retrieved_at.isoformat().replace("+00:00", "Z")
            for component in evidence.components
            if component.observation_id in set(refs.awards.values()) | set(refs.cash.values())),
        max(component.retrieved_at.isoformat().replace("+00:00", "Z")
            for component in evidence.components
            if component.observation_id in set(refs.awards.values()) | set(refs.cash.values())),
    ]
    by_j = {row[0]: row for row in jrows}
    by_c = {row[0]: row for row in crows}
    component_profiles = packet["component_profiles"]
    journey_profiles = packet["journey_profiles"]
    journey_columns = packet["legend"]["journey_profile"]
    component_columns = packet["legend"]["component_profile"]
    source_components = {c.observation_id: c for c in source.view.components}
    for key, aliases in packet["ranking_hints"].items():
        assert [refs.journeys[alias] for alias in aliases] == list(
            getattr(source.view.indexes, key))
    expected_findings = {}
    for component in source.view.components:
        for finding in component.findings:
            meaning = {key: getattr(finding, key) for key in ("severity", "field", "message")}
            assert expected_findings.setdefault(finding.code, meaning) == meaning
    assert packet["finding_catalog"] == expected_findings
    assert packet["source_context"]["coverage_limits"] == [
        [group.kind, group.status, group.reason, list(group.routes_and_dates)]
        for group in source.view.coverage_groups if group.status != "completed"
    ]
    for journey in evidence.journeys:
        row = by_j[next(alias for alias, cid in refs.journeys.items()
                        if cid == journey.candidate_id)]
        profile = dict(zip(journey_columns, journey_profiles[row[1]]))
        assert refs.awards[row[2]] == journey.award_observation_id
        assert (refs.cash[row[3]] if row[3] else None) == journey.cash_observation_id
        assert profile["route"] == [journey.origin, journey.destination]
        assert profile["status"] == journey.internal.status
        assert profile["elapsed_minutes"] == (str(journey.elapsed_minutes)
                                                if journey.elapsed_minutes is not None else None)
        assert profile["booking"] == journey.booking_obligation
        assert profile["price_completeness"] == journey.price_completeness
        source_alternative = next(a for a in source.view.alternatives
                                  if a.candidate_id == journey.candidate_id)
        reasons = next(r.reasons for r in source.view.reason_sets
                       if r.reason_set_id == source_alternative.reason_set_id)
        assert profile["traveler_support"] == next(
            (r.state for r in reasons if r.code.startswith("award_travelers_")), "unknown")
        assert profile["seat_support"] == next(
            (r.state for r in reasons
             if r.code == "result_validation_minimum_award_seats"), "unknown")
    for alias in expected_component_aliases:
        canonical = refs.awards.get(alias, refs.cash.get(alias))
        row = by_c[alias]
        profile = dict(zip(component_columns, component_profiles[row[1]]))
        source_component = source_components[canonical]
        assert profile["route"] == [source_component.origin, source_component.destination]
        assert profile["date"] == (source_component.departure_date.isoformat()
                                   if source_component.departure_date else None)
        assert profile["price_scope"] == source_component.price_scope
        assert profile["depart"] == (time_value(source_component.departure) or "-")
        assert profile["arrive"] == (time_value(source_component.arrival) or "-")
        assert profile["airports"] == (list(source_component.airport_sequence) or "-")
        assert profile["program"] == profile_raw(source_component.program)
        assert profile["cabin"] == profile_raw(source_component.cabin)
        assert profile["carriers"] == (list(source_component.carriers) or "-")
        assert profile["fee_unit"] == source_component.taxes_fees_unit
        assert profile["fee_currency"] == profile_raw(source_component.tax_currency)
        assert profile["cash_currency"] == profile_raw(source_component.cash_currency)
        assert profile["mixed_cabin_pct"] == profile_raw(source_component.mixed_cabin_pct)
        assert profile["duration_minutes"] == profile_raw(source_component.duration_minutes)
        for key, field in (("points", source_component.points),
                           ("fees", source_component.taxes_fees),
                           ("cash", source_component.cash_amount),
                           ("returned_travelers", source_component.returned_travelers),
                           ("seats", source_component.seats)):
            expected = field.value if field.state == "value" else field.state
            assert profile.get(key, "-") == ("-" if expected in (None, "absent") else expected)
        assert profile["leg_cabins"] == (
            [raw(leg.cabin) for leg in source_component.legs] or "-")
        assert profile.get("findings", "-") == (
            [finding.code for finding in source_component.findings] or "-")
    for row in lead_rows:
        alias = row[0]
        canonical = refs.awards.get(alias, refs.cash.get(alias))
        component = source_components[canonical]
        assert row[2] == [component.origin, component.destination]
        assert row[3] == (component.departure_date.isoformat()
                          if component.departure_date else None)
        assert row[4] == (component.program.value if component.program.state == "value"
                          else component.program.state)
        assert row[5] == (component.cabin.value if component.cabin.state == "value"
                          else component.cabin.state)
        assert row[6] == (component.points.value if component.points.state == "value"
                          else component.points.state)
        for index, field in ((7, component.taxes_fees), (9, component.tax_currency),
                             (10, component.cash_amount), (11, component.cash_currency)):
            assert row[index] == (field.value if field.state == "value" else field.state)
        assert row[8] == component.taxes_fees_unit
        assert row[12] == component.price_scope
        assert row[16] == raw(component.seats)
        assert row[17] == raw(component.returned_travelers)
        assert row[18] == [finding.code for finding in component.findings]
        assert row[19] == ([time_value(component.departure),
                            time_value(component.arrival), raw(component.duration_minutes)]
                           if row[15] == "timed" else "-")
        assert row[20] == list(component.airport_sequence)
        assert row[21] == list(component.carriers)
        assert row[22] == ([raw(leg.cabin) for leg in component.legs] or "absent")
        request = source.view.request
        assert row[13] == (component.origin in {x.value for x in request.origins}
                           and component.destination in {x.value for x in request.destinations})
        assert row[14] == bool(component.departure_date and request.departure_window and
            request.departure_window.start <= component.departure_date <=
            request.departure_window.end)
        assert row[15] == ("timed" if component.departure.local_iso and
                           component.arrival.local_iso else
                           "date_only" if component.departure_date else "unknown")
    if name == "admitted":
        assert dict(zip(component_columns, component_profiles[by_c["A145"][1]]))[
            "leg_cabins"] == ["absent", "absent"]
        assert "resource_budget_exhausted" in str(packet["source_context"]["coverage_limits"])
    if name == "conditional":
        assert dict(zip(component_columns, component_profiles[by_c["A170"][1]]))[
            "leg_cabins"] == ["absent", "absent"]
        timed = [row for row in lead_rows if row[0] in
                 {"A163", "A164", "A165", "A166", "A167"}]
        assert len(timed) == 5 and all(row[15] == "timed" and row[19] != "-" for row in timed)
        assert len({tuple(row[19]) for row in timed}) == 5
    if name == "incomplete":
        assert "pagination_budget_exhausted" in str(packet["source_context"]["coverage_limits"])
    zero_ref = {"admitted": "A9", "conditional": "A14", "incomplete": "A11"}[name]
    zero_row = next(row for row in lead_rows if row[0] == zero_ref)
    assert zero_row[16] == 0 and "seats_zero_ambiguous" in zero_row[18]
    # Independently recompute relation memberships from canonical workspace/source.
    alias_by_candidate = {candidate: alias for alias, candidate in refs.journeys.items()}
    arrival_groups = defaultdict(list)
    schedule_groups = defaultdict(list)
    for journey in evidence.journeys:
        alias = alias_by_candidate[journey.candidate_id]
        award_alias = next(a for a, canonical in refs.awards.items()
                           if canonical == journey.award_observation_id)
        arrival = time_value(journey.arrival)
        if arrival:
            arrival_groups[(award_alias, arrival)].append(alias)
        award = source_components[journey.award_observation_id]
        key = (raw(award.program), time_value(journey.departure), arrival,
               journey.origin, journey.destination)
        if (award.program.state == "value" and journey.award_cabin.state == "value"
                and time_value(journey.departure) and arrival):
            schedule_groups[key].append(alias)
    expected_arrival = {(award, arrival, frozenset(members))
        for (award, arrival), members in arrival_groups.items() if len(members) > 1}
    assert {(award, arrival, frozenset(members)) for award, arrival, members in
            packet["relations"]["same_award_arrival_alternatives"]} == expected_arrival
    cabin_by_alias = {alias_by_candidate[j.candidate_id]: raw(j.award_cabin)
                      for j in evidence.journeys}
    expected_cross = {frozenset(members) for members in schedule_groups.values()
                      if len({cabin_by_alias[alias] for alias in members}) > 1}
    assert {frozenset(members) for members in packet["relations"]["timing_match_cross_cabin"]} \
        == expected_cross
    # Controlled quote/unknown probes: the lead must follow its own component,
    # including same-route/date rows and source unknown states.
    modified_data = prepared.model_dump(mode="json")
    modified_view = modified_data["authoring_view"]["view"]
    first_ref = modified_view["incomplete_leads"][0]["ref"]
    for group in modified_view["components"]:
        if any(member["ref"] == first_ref for member in group["members"]):
            group["facts"]["points"] = {"state": "absent", "value": None}
            group["facts"]["seats"] = {"state": "value", "value": 0}
            group["facts"]["returned_travelers"] = {"state": "unknown", "value": None}
            group["facts"]["findings"].append({"code": "seats_zero_ambiguous",
                "severity": "unknown", "field": "seats",
                "message": "zero may mean seat count is unavailable"})
            break
    modified = StructuredPreparedInput.model_validate(modified_data)
    changed = build_packet(modified, source, evidence)
    changed_lead = next(row for row in changed["lead_rows"] if row[0] == first_ref)
    assert changed_lead[6] == "absent"
    assert changed_lead[16:19] == [0, "unknown", ["seats_zero_ambiguous"]]
    assert next(row for row in packet["lead_rows"] if row[0] == first_ref)[6] != "absent"
    if name == "admitted":
        scoped_data = prepared.model_dump(mode="json")
        for group in scoped_data["authoring_view"]["view"]["components"]:
            if any(member["ref"] == "A145" for member in group["members"]):
                group["facts"]["legs"][0]["cabin"] = {"state": "value", "value": "business"}
                group["facts"]["mixed_cabin_pct"] = {"state": "value", "value": 50}
                break
        scoped = build_packet(StructuredPreparedInput.model_validate(scoped_data),
                              source, evidence)
        scoped_c = {row[0]: row for row in scoped["component_rows"]}
        scoped_profile = dict(zip(scoped["legend"]["component_profile"],
                                  scoped["component_profiles"][scoped_c["A145"][1]]))
        assert scoped_profile["leg_cabins"] == ["business", "absent"]
        assert scoped_profile["mixed_cabin_pct"] == 50
        assert any(row[2] == "A145" and
            dict(zip(scoped["legend"]["journey_profile"],
                     scoped["journey_profiles"][row[1]]))["award_cabin"] == "business"
            for row in scoped["journey_rows"])
        cross_ref = packet["relations"]["timing_match_cross_cabin"][0][0]
        cross_award = by_j[cross_ref][2]
        for field in ("program", "timeline", "cabin"):
            negative_data = prepared.model_dump(mode="json")
            negative_view = negative_data["authoring_view"]["view"]
            if field == "program":
                for group in negative_view["components"]:
                    if any(member["ref"] == cross_award for member in group["members"]):
                        group["facts"]["program"] = {"state": "unknown", "value": None}
                        break
            else:
                for group in negative_view["journeys"]:
                    if any(member["ref"] == cross_ref for member in group["members"]):
                        if field == "timeline":
                            group["facts"]["departure"]["local_iso"] = None
                        else:
                            group["facts"]["award_cabin"] = {"state": "unknown", "value": None}
                        break
            negative = build_packet(StructuredPreparedInput.model_validate(negative_data),
                                    source, evidence)
            assert not any(cross_ref in members for members in
                           negative["relations"]["timing_match_cross_cabin"])
    wire = json.dumps(packet, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(wire.encode("utf-8")).hexdigest()
    assert digest == KNOWN_DIGESTS[name]
    return {
        "journeys": len(jrows), "journey_profiles": len(journey_profiles),
        "components": len(crows), "component_profiles": len(component_profiles),
        "leads": len(lead_rows), "benchmarks": len(packet["benchmark_refs"]),
        "coverage_limits": len(packet["source_context"]["coverage_limits"]),
        "timed_leads": sum(row[15] == "timed" for row in lead_rows),
        "zero_seat_leads": sum(row[16] == 0 for row in lead_rows),
        "finding_codes": sorted(packet["finding_catalog"]),
        "wire_bytes": len(wire.encode("utf-8")),
        "packet_sha256": digest,
        "rough_tokens_bytes_div_4": len(wire.encode("utf-8")) // 4,
        "synthetic_unknown_zero_quote_association": "passed",
        "synthetic_leg_cabin_scope_and_mixed_pct": "passed" if name == "admitted" else "not_run",
        "synthetic_unknown_relation_guard": "passed" if name == "admitted" else "not_run",
    }


def audit_empty_and_missing_date() -> dict[str, str]:
    original = json.loads((ROOT / "incomplete" / "artifact.json").read_text())
    empty = json.loads(json.dumps(original))
    source_data = empty["evidence"]["source"]
    view_data = source_data["view"]
    for key in ("components", "alternatives", "reason_sets", "cost_components",
                "costs", "assessments", "comparison_pool_ids", "direct_cash_observation_ids",
                "award_summary_observation_ids", "unmatched_award_observation_ids",
                "unpaired_positioning_observation_ids", "pairing_receipts", "coverage_groups"):
        view_data[key] = []
    for key in view_data["indexes"]:
        view_data["indexes"][key] = []
    receipt_data = source_data["receipt"]
    for key in ("candidate_sources", "observation_sources", "coverage_sources"):
        receipt_data[key] = []
    receipt_data["total_candidates"] = 0
    receipt_data["eligible_alternatives"] = 0
    receipt_data["view_digest"] = content_digest(SolutionView.model_validate(view_data))
    source = SolutionProjection.model_validate(source_data)
    evidence_data = empty["evidence"]
    for key in ("journeys", "groups", "components", "direct_cash_benchmark_ids", "leads"):
        evidence_data[key] = []
    evidence_data["source_binding"]["view_digest"] = receipt_data["view_digest"]
    evidence = WorkspaceEvidence.model_validate(evidence_data)
    prepared_data = empty["prepared"]
    prepared_data["source_digest"] = receipt_data["view_digest"]
    authoring = prepared_data["authoring_view"]
    authoring["source_digest"] = receipt_data["view_digest"]
    for key in ("journeys", "components", "benchmarks", "incomplete_leads"):
        authoring["view"][key] = []
    authoring["view"]["comparison"]["eligible_count"] = 0
    for key in authoring["references"]:
        authoring["references"][key] = {}
    authoring["binding_digest"] = content_digest({
        "source_digest": authoring["source_digest"], "view": authoring["view"],
        "references": authoring["references"]})
    prepared = StructuredPreparedInput.model_validate(prepared_data)
    packet = build_packet(prepared, source, evidence)
    assert packet["source_context"]["observed_at_range"] == [None, None]
    assert packet["journey_rows"] == packet["component_rows"] == packet["lead_rows"] == []

    missing = json.loads(json.dumps(original))
    prepared_data = missing["prepared"]
    authoring = prepared_data["authoring_view"]
    alias = authoring["view"]["incomplete_leads"][0]["ref"]
    canonical = authoring["references"]["awards"][alias]
    for group in authoring["view"]["components"]:
        if any(member["ref"] == alias for member in group["members"]):
            group["facts"]["departure_date"] = None
            break
    authoring["view"]["incomplete_leads"][0]["identity"]["departure_date"] = None
    source_data = missing["evidence"]["source"]
    for component in source_data["view"]["components"]:
        if component["observation_id"] == canonical:
            component["departure_date"] = None
            break
    source_data["receipt"]["view_digest"] = content_digest(
        SolutionView.model_validate(source_data["view"]))
    source = SolutionProjection.model_validate(source_data)
    evidence_data = missing["evidence"]
    evidence_data["source_binding"]["view_digest"] = source_data["receipt"]["view_digest"]
    for component in evidence_data["components"]:
        if component["observation_id"] == canonical:
            component["departure_date"] = None
            break
    evidence = WorkspaceEvidence.model_validate(evidence_data)
    prepared_data["source_digest"] = source_data["receipt"]["view_digest"]
    authoring["source_digest"] = source_data["receipt"]["view_digest"]
    authoring["binding_digest"] = content_digest({
        "source_digest": authoring["source_digest"], "view": authoring["view"],
        "references": authoring["references"]})
    prepared = StructuredPreparedInput.model_validate(prepared_data)
    packet = build_packet(prepared, source, evidence)
    lead = next(row for row in packet["lead_rows"] if row[0] == alias)
    assert lead[3] is None and lead[14:16] == [False, "unknown"]
    return {"valid_empty_source_workspace": "passed", "valid_missing_date_lead": "passed"}


def main() -> None:
    results = {name: audit_case(name) for name in
               ("admitted", "conditional", "incomplete")}
    output = {
        "cases": results,
        "edge_controls": audit_empty_and_missing_date(),
        "token_note": "Byte/4 is a rough size proxy, not an API token count.",
        "omission_inventory": {
            "intentional": ["passed reason prose other than traveler/seat outcomes",
                            "provider query lineage", "per-alias retrieval timestamps (range retained)",
                            "per-leg flight numbers and times (airport sequence, whole schedule, and each leg cabin state retained)",
                            "duplicate lead-only component profiles", "full explorer metadata",
                            "completed coverage-group detail (all incomplete groups retained)"],
            "retained_locally": "Original prepared input and canonical workspace/source in each artifact.",
        },
    }
    target = Path(__file__).with_name("packet-audit.json")
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
