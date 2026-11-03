"""V16 full-inventory named selector facts and frozen profile replay."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer, _config
from test_results_focused_v14 import PlannedWriter

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.focused import (
    _request,
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_comparison_contracts import FocusedResultsArtifactV11
from award_agent.results.focused_selector_records import selector_packet
from award_agent.results.focused_v4 import LOW_SELECTOR_SETTINGS

RUNS = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs")


@pytest.mark.parametrize("case", ["admitted", "conditional", "incomplete"])
def test_named_selector_inventory_reconstructs_every_source_fact(case: str) -> None:
    archived = parse_focused_artifact((RUNS / f"scout-v15-{case}" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(archived.evidence.source.model_dump(mode="json"))
    prepared = prepare_focused_selector(source, _config(), archived.evidence,
                                        selection_format="roles-v15")
    original = prepared.packet
    named = selector_packet(prepared)
    assert len(named["journey_records"]) == len(original["journey_rows"])
    assert len(named["component_records"]) == len(original["component_rows"])
    assert set(named) - {"journey_records", "component_records"} == (
        set(original) - {"journey_rows", "component_rows"})
    for key in original:
        if key not in {"legend", "journey_rows", "journey_profiles", "component_rows",
                       "component_profiles"}:
            assert named[key] == original[key]
    j_columns = original["legend"]["journey_profile"]
    c_columns = original["legend"]["component_profile"]
    assert list(named["journey_records"]) == [row[0] for row in original["journey_rows"]]
    assert list(named["component_records"]) == [row[0] for row in original["component_rows"]]
    for ref, index, award, cash in original["journey_rows"]:
        record = named["journey_records"][ref]
        assert (record["profile_ref"], record["award_ref"], record["cash_ref"]) == (
            f"JP{index}", award, cash)
        profile = named["journey_profiles"][record["profile_ref"]]
        assert [profile[column] for column in j_columns] == original["journey_profiles"][index]
        award_profile = named["component_profiles"][
            named["component_records"][award]["profile_ref"]]
        assert (record["award_cabin"], record["award_program"], record["award_points"]) == (
            profile["award_cabin"], award_profile["program"], award_profile["points"])
    for ref, index in original["component_rows"]:
        profile_ref = named["component_records"][ref]["profile_ref"]
        assert profile_ref == f"CP{index}"
        assert [named["component_profiles"][profile_ref][column] for column in c_columns] == (
            original["component_profiles"][index])
    assert list(named["journey_profiles"]) == [
        f"JP{index}" for index in range(len(original["journey_profiles"]))]
    assert list(named["component_profiles"]) == [
        f"CP{index}" for index in range(len(original["component_profiles"]))]
    if case == "conditional":
        for ref in ("J75", "J115"):
            row = named["journey_records"][ref]
            assert row["award_cabin"] == "business"
            assert row["award_program"] == "turkish"
            assert row["award_points"] == 275000


@pytest.mark.parametrize("missing_endpoint", [False, True])
def test_v16_two_or_three_calls_replay_and_request_projection(missing_endpoint: bool) -> None:
    archived = parse_focused_artifact((RUNS / "scout-v15-admitted" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(archived.evidence.source.model_dump(mode="json"))
    writer = PlannedWriter(missing_endpoint=missing_endpoint, selector_effort="low")
    artifact = run_focused_results(source, _config(), writer, FakeMeasurer(), profile="focused-v16")
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v15"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v13"
    assert [item.request["reasoning"]["effort"] for item in artifact.passes] == (
        ["low", "medium", "low"] if missing_endpoint else ["low", "medium"])
    first_input = json.loads(artifact.passes[0].request["input"])["packet"]
    assert first_input == selector_packet(artifact.selector_prepared)
    assert "journey_rows" not in first_input and "component_rows" not in first_input
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    changed = artifact.model_dump(mode="json")
    changed["passes"][0]["request"]["input"] = json.dumps({"packet": {"journey_records": {}}})
    with pytest.raises(ValueError):
        replay_focused_results(FocusedResultsArtifactV11.model_validate(changed))


def test_v16_projection_rejects_missing_source_profile_and_keeps_v15_unchanged() -> None:
    archived = parse_focused_artifact((RUNS / "scout-v15-admitted" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(archived.evidence.source.model_dump(mode="json"))
    old = prepare_focused_selector(source, _config(), archived.evidence,
                                   selection_format="roles-v14")
    old_request = _request(old, _config(), LOW_SELECTOR_SETTINGS, "selection", source)
    assert json.loads(old_request.request["input"])["packet"] == old.packet
    new = prepare_focused_selector(source, _config(), archived.evidence,
                                   selection_format="roles-v15")
    for section, bad in (("journey_rows", 999999), ("journey_rows", "1"),
                         ("journey_rows", True), ("component_rows", 1.0),
                         ("component_rows", -1)):
        damaged = deepcopy(new.packet)
        damaged[section][0][1] = bad
        with pytest.raises(ValueError, match="profile index"):
            selector_packet(new.model_copy(update={"packet": damaged}))
