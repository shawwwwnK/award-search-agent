"""V13 per-reference authoring records and standalone writer brief."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer, _config, _source

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_comparison_runtime import prepare_focused_v11_composer
from award_agent.results.focused_records import writer_packet


class RecordWriter:
    def __init__(self, *, missing_endpoint: bool = False) -> None:
        self.missing_endpoint = missing_endpoint
        self.requests = []
        self.pending = None

    def author(self, request, config, settings):
        index = len(self.requests)
        assert settings.reasoning_effort == ("medium" if index == 1 else "low")
        assert settings.service_tier == "fast"
        self.requests.append(request)
        packet = json.loads(request["input"])["packet"]
        if index == 0:
            refs = [row[0] for row in packet["journey_rows"][:2]]
            raw = json.dumps({"choices": [{"k": "j", "r": ref} for ref in refs]})
        else:
            journeys = [ref for ref, record in packet["authoring_records"].items()
                        if record["role"] == "journey"]
            blocks = [{"k": "p", "r": journeys[0], "n": "First", "v": "A useful option with a downside."}]
            if index == 2 or not self.missing_endpoint:
                blocks.append({"k": "a", "r": journeys[1], "n": "Alternative",
                               "v": "A different useful option with a downside."})
            if packet["temporal_comparisons"]:
                blocks.append({"k": "x", "r": packet["temporal_comparisons"][0]["id"]})
            raw = json.dumps({"blocks": blocks})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self):
        receipt, self.pending = self.pending, None
        return receipt


def _saved_packet(run: str):
    path = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs") / run / "artifact.json"
    old = parse_focused_artifact(path.read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    selector = prepare_focused_selector(source, old.config, old.evidence,
                                        selection_format="roles-v12")
    selection = old.passes[0].selection
    assert selection is not None
    focus, registry = prepare_focused_v11_composer(selection, selector, source, old.evidence)
    return focus, registry, writer_packet(focus)


def test_q026_q029_source_associations_are_owned_by_exact_records() -> None:
    focus26, _, packet26 = _saved_packet("confirm-v11-default-1-admitted")
    focus29, _, packet29 = _saved_packet("confirm-v11-default-2-admitted")
    for focus, packet in ((focus26, packet26), (focus29, packet29)):
        assert packet["format"] == "focused-authoring-records-v1"
        assert "journeys" not in packet and "benchmarks" not in packet
        assert "leads" not in packet and "selected_details" not in packet
        assert "wire_aliases" not in packet
        scope = packet["source_scope"]
        assert scope["full_selectable_journey_count"] > scope["selected_journey_count"]
        assert not any("date" in key for key in scope)
        local_groups = focus.packet["journeys"] + focus.packet["benchmarks"] + focus.packet["leads"]
        for group in local_groups:
            for member in group["members"]:
                record = packet["authoring_records"][member["ref"]]
                assert record["member"] == member
                assert record["facts"] == group["facts"]
    records29 = packet29["authoring_records"]
    j1 = next(record for ref, record in records29.items() if ref.startswith("J1@"))
    j14 = next(record for ref, record in records29.items() if ref.startswith("J14@"))
    assert j1["facts"]["award"]["seats"] == 2
    assert j14["facts"]["award"]["seats"] == 9
    assert j1["facts"]["departure"] == j14["facts"]["departure"]
    assert j1["award_component"]["quote"]["display"] == "CAD 107.40"
    assert j1["award_component"]["quote"]["price_scope"] == "unknown"
    assert j1["award_component"]["award_itinerary_connections"][0]["wait_minutes"] == 105
    assert j14["award_component"]["award_itinerary_connections"][0]["wait_minutes"] == 70
    assert j1["cash_component"] is None
    assert j1["facts"]["traveler_support"] == "passed"
    records26 = packet26["authoring_records"]
    cash = next(record for record in records26.values() if record["role"] == "benchmark")
    j8 = next(record for ref, record in records26.items() if ref.startswith("J8@"))
    j7 = next(record for ref, record in records26.items() if ref.startswith("J7@"))
    assert cash["facts"]["arrival"]["local_iso"] == "2027-01-17T08:25:00+07:00"
    assert j8["facts"]["arrival"]["local_iso"] == "2027-01-16T22:25:00+07:00"
    assert j7["facts"]["arrival"]["local_iso"] == "2027-01-17T01:25:00+07:00"
    assert cash["quote"]["display"] == "USD 440.00"
    assert cash["quote"]["price_scope"] == "unknown"


def test_empty_selected_inventory_remains_a_truthful_empty_authoring_packet() -> None:
    focus, _, _ = _saved_packet("confirm-v11-default-1-admitted")
    packet = deepcopy(focus.packet)
    packet["journeys"] = []
    packet["benchmarks"] = []
    packet["leads"] = []
    packet["selection_scope"] = {"journey_count": 0, "lead_count": 0,
                                  "benchmark_selected": False}
    packet["source_scope"] = {"full_selectable_journey_count": 0,
                              "full_selectable_lead_count": 0,
                              "full_direct_cash_benchmark_count": 0,
                              "selected_journey_count": 0,
                              "selected_lead_count": 0,
                              "selected_benchmark_count": 0}
    packet["selected_details"] = {"component_quotes": {}, "award_connections": {},
                                  "journey_connections": {}, "journey_components": {},
                                  "legend": focus.packet["selected_details"]["legend"]}
    packet["temporal_comparisons"] = []
    result = writer_packet(focus.model_copy(update={"packet": packet}))
    assert result["authoring_records"] == {}
    assert result["source_scope"]["full_selectable_journey_count"] == 0
    assert result["source_context"] == packet["source_context"]


def test_incomplete_only_selection_keeps_each_lead_and_cash_source_owned() -> None:
    focus, registry, packet = _saved_packet("confirm-v11-default-1-incomplete")
    assert registry.facts == ()
    assert packet["source_scope"]["selected_journey_count"] == 0
    assert packet["source_scope"]["selected_lead_count"] == 3
    assert packet["source_scope"]["full_selectable_lead_count"] > 3
    records = packet["authoring_records"]
    assert len(records) == 4
    assert [row["role"] for row in records.values()].count("lead") == 3
    assert [row["role"] for row in records.values()].count("benchmark") == 1
    for group in focus.packet["leads"] + focus.packet["benchmarks"]:
        for member in group["members"]:
            ref = member["ref"]
            assert records[ref]["facts"] == group["facts"]
            assert records[ref]["quote"] == \
                   focus.packet["selected_details"]["component_quotes"][ref]


@pytest.mark.parametrize("missing_endpoint", [False, True])
def test_v13_run_recovery_and_replay(missing_endpoint) -> None:
    writer = RecordWriter(missing_endpoint=missing_endpoint)
    artifact = run_focused_results(_source(), _config(), writer, FakeMeasurer(),
                                   profile="focused-v13")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v12"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v10"
    assert len(writer.requests) == (3 if missing_endpoint else 2)
    assert [p.request["reasoning"]["effort"] for p in artifact.passes] == (
        ["low", "medium", "low"] if missing_endpoint else ["low", "medium"])
    assert artifact.selected_pass_index == (2 if missing_endpoint else 1)
    assert "record key owns every fact" in artifact.passes[1].request["instructions"]
    assert "selected_comparisons" in json.loads(artifact.passes[1].request["input"])["packet"]
    if missing_endpoint:
        first = json.loads(artifact.passes[1].request["input"])["packet"]
        second = json.loads(artifact.passes[2].request["input"])["packet"]
        assert first == second
        assert artifact.passes[1].findings[-1].code == "comparison_endpoint_not_visible"
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["passes"][1]["request"]["input"] = "{}"
    with pytest.raises(ValueError, match="request differs"):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(changed))
