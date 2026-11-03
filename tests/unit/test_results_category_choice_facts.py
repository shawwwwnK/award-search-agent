"""C12 selected choice facts are source observations, not coded advantages."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from award_agent.results.category import (
    _PROFILE_INSTRUCTIONS,
    _requests,
    _selected_choice_facts,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

RUNS = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((RUNS / case / "artifact.json").read_bytes())


def _choices(case: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    artifact = _saved(case)
    assert artifact.focus_prepared is not None
    packet = cast(dict[str, Any], _writer_input(artifact.focus_prepared, profile="category-c12"))
    return (cast(dict[str, dict[str, Any]], packet["authoring_records"]),
            cast(list[dict[str, Any]], packet["selected_choice_facts"]))


def test_c12_q035_exact_program_cabin_points_scope_and_all_connection_kinds() -> None:
    records, choices = _choices("confirm-c11-prior-conditional")
    assert [row["alias"] for row in choices] == [
        alias for alias, record in records.items() if record["role"] != "benchmark"]
    assert len(choices) == 3
    by_alias = {row["alias"].split("@")[0]: row for row in choices}
    economy, business, lead = by_alias["J18"], by_alias["J63"], by_alias["A1"]
    assert [(economy["program"], economy["reported_cabin"],
             economy["points"], economy["price_scope"]),
            (business["program"], business["reported_cabin"],
             business["points"], business["price_scope"])] == [
        ("turkish", "economy", 110000, "unknown"),
        ("turkish", "business", 275000, "unknown")]
    assert economy["component_kind"] == business["component_kind"] == "award_itinerary"
    assert economy["journey_connections"] == [{
        "kind": "separate_booking", "airport": "LAX", "wait_minutes": 301,
        "unknown_reason": None}]
    assert business["journey_connections"] == [{
        "kind": "separate_booking", "airport": "LAX", "wait_minutes": 150,
        "unknown_reason": None}]
    assert economy["award_connections"] == [{
        "kind": "award_connection", "airport": "IST", "wait_minutes": 60,
        "unknown_reason": None}]
    assert business["award_connections"] == [{
        "kind": "award_connection", "airport": "IST", "wait_minutes": 140,
        "unknown_reason": None}]
    assert (lead["role"], lead["program"], lead["reported_cabin"],
            lead["points"], lead["price_scope"], lead["component_kind"]) == (
                "lead", "aeroplan", "economy", 65000, "unknown", "award_summary")
    assert not any("connections" in key or key in {"departure", "styles"}
                   for key in lead)
    assert not any(key in row for row in choices for key in (
        "benefit", "best", "advantage", "recommended_for", "omission_reason"))


def test_c12_mixed_program_and_lead_only_keep_original_roles_and_order() -> None:
    for case in ("c11-scout-prior-admitted", "c11-scout-prior-incomplete"):
        records, choices = _choices(case)
        expected = [(alias, record["role"]) for alias, record in records.items()
                    if record["role"] != "benchmark"]
        assert [(row["alias"], row["role"]) for row in choices] == expected
        for row in choices:
            original = records[row["alias"]]
            facts = original["facts"]
            award = facts["award"] if row["role"] == "journey" else facts
            for source, target in (("program", "program"), ("points", "points"),
                                   ("price_scope", "price_scope"),
                                   ("cabin", "reported_cabin")):
                assert row.get(target) == award.get(source)
            if row["role"] == "lead":
                assert "award_connections" not in row
                assert "journey_connections" not in row
            else:
                assert row["award_connections"] == original["award_component"][
                    "award_itinerary_connections"]
                assert row["journey_connections"] == original["journey_connections"]


def test_c12_single_option_unknown_wait_and_absent_null_values_are_not_rewritten() -> None:
    journey: dict[str, Any] = {"role": "journey", "facts": {
        "date": "2027-01-08", "route": {"origin": "SFO", "destination": "BKK"},
        "award": {"kind": "award_itinerary", "program": "turkish",
                  "cabin": "business", "points": None, "price_scope": "unknown",
                  "leg_cabins": ["absent", "unknown"]}},
        "award_component": {"award_itinerary_connections": [{
            "kind": "award_connection", "airport": "IST", "wait_minutes": None,
            "unknown_reason": "schedule_unreported"}]},
        "journey_connections": [{"kind": "separate_booking", "airport": "LAX",
                                 "wait_minutes": 0, "unknown_reason": None}]}
    lead: dict[str, Any] = {"role": "lead", "facts": {
        "kind": "award_summary", "program": "aeroplan", "cabin": "economy",
        "points": "absent", "price_scope": "unknown", "leg_cabins": "absent"}}
    before = deepcopy({"J": journey, "A": lead})
    rows = _selected_choice_facts({"J": journey, "A": lead})
    assert rows[0]["points"] is None
    assert rows[0]["reported_leg_cabins"] == ["absent", "unknown"]
    assert cast(list[dict[str, Any]], rows[0]["award_connections"])[0]["wait_minutes"] is None
    assert cast(list[dict[str, Any]], rows[0]["journey_connections"])[0]["wait_minutes"] == 0
    assert rows[1]["points"] == "absent"
    assert rows[1]["reported_leg_cabins"] == "absent"
    assert "date" not in rows[1] and "route" not in rows[1]
    assert {"J": journey, "A": lead} == before


def test_c12_request_only_adds_choice_table_and_replaces_competing_cue() -> None:
    saved = _saved("confirm-c11-prior-conditional")
    focus = saved.focus_prepared
    assert focus is not None
    old = _requests(saved.evidence.source, saved.config, saved.selector_prepared,
                    focus, "category-c11")
    new = _requests(saved.evidence.source, saved.config, saved.selector_prepared,
                    focus, "category-c12")
    assert old.request["reasoning"] == new.request["reasoning"] == {"effort": "medium"}
    assert old.request["text"] == new.request["text"]
    old_input = json.loads(cast(str, old.request["input"]))
    new_input = json.loads(cast(str, new.request["input"]))
    assert new_input["packet"].pop("selected_choice_facts")
    assert new_input == old_input
    old_cue = "do not repeat those facts in prose as a card recap"
    new_cue = "Briefly reuse a fact when it explains that reason"
    assert old_cue in cast(str, old.request["instructions"])
    assert old_cue not in cast(str, new.request["instructions"])
    assert new_cue in cast(str, new.request["instructions"])
    assert _PROFILE_INSTRUCTIONS["category-c11"][0] == _PROFILE_INSTRUCTIONS[
        "category-c12"][0]
    assert replay_category_results(saved) == saved.resolved


def test_c12_offline_two_pass_request_replay_and_table_tamper_rejected() -> None:
    saved = _saved("confirm-c11-prior-conditional")
    wires = [part.raw_wire for part in saved.passes]
    assert len(wires) == 2 and all(isinstance(wire, str) for wire in wires)

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            wire = wires[self.calls]
            assert isinstance(wire, str)
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": wire}]}]}))
            return wire

        def take_receipt(self) -> WriterReceipt | None:
            pending, self.pending = self.pending, None
            return pending

    artifact = run_category_results(saved.evidence.source, saved.config,
                                    SavedWriter(), profile="category-c12")
    assert artifact.resolved == saved.resolved
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
    tampered = json.loads(artifact.model_dump_json())
    packet = json.loads(tampered["passes"][1]["request"]["input"])["packet"]
    packet["selected_choice_facts"][0]["points"] = 1
    request = json.loads(tampered["passes"][1]["request"]["input"])
    request["packet"] = packet
    tampered["passes"][1]["request"]["input"] = json.dumps(request)
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(tampered)))
