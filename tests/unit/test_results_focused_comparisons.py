"""Focused-v3 arithmetic and exact saved-profile replay."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.results.contracts import InputTokenReceipt, ResultsConfig, WriterReceipt
from award_agent.results.focused import (
    COMPOSER_SETTINGS,
    SELECTOR_SETTINGS,
    _request,
    prepare_focused_composer,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_contracts import FocusedResultsArtifact
from award_agent.results.focused_packet import selected_comparisons

RUNS = (Path(__file__).resolve().parents[2] /
        "evidence/results-stage/m2/structured/2026-10-26-under20/runs")


def _artifact(name: str) -> FocusedResultsArtifact:
    return FocusedResultsArtifact.model_validate_json((RUNS / name / "artifact.json").read_bytes())


def _pairs(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["first"].split("@")[0], row["second"].split("@")[0]): row
            for row in rows}


def test_actual_selected_admitted_journey_directions_and_exact_differences() -> None:
    prior = _artifact("focused2-a-recovery")
    selection = prior.passes[0].selection
    assert selection is not None
    focus = prepare_focused_composer(selection, prior.selector_prepared,
        prior.evidence.source, prior.evidence, composition_format="comparisons-v1")
    assert focus.packet["composition_format"] == "comparisons-v1"
    comparisons = focus.packet["selected_comparisons"]
    elapsed = _pairs(comparisons["elapsed_minutes"])
    arrival = _pairs(comparisons["arrival_instant"])
    assert elapsed[("J1", "J17")]["difference_minutes"] == "40"
    assert elapsed[("J1", "J7")]["difference_minutes"] == "125"
    assert elapsed[("J1", "J7")]["difference_display"] == "2h 5m"
    assert arrival[("J1", "J17")]["difference_minutes"] == "55"
    assert arrival[("J7", "J1")]["difference_minutes"] == "550"
    assert arrival[("J7", "J1")]["difference_display"] == "9h 10m"
    assert all(row["relation"] == "shorter_than" for row in elapsed.values())
    assert all(row["relation"] == "earlier_than" for row in arrival.values())
    assert "cost" not in comparisons and "seats" not in comparisons
    assert "comparison" in _request(focus, prior.config, COMPOSER_SETTINGS,
                                     "composition", prior.evidence.source).request["instructions"]
    old_selector = _request(prior.selector_prepared, prior.config, SELECTOR_SETTINGS,
                            "selection", prior.evidence.source)
    assert old_selector.request == prior.passes[0].request
    assert prior.focus_prepared is not None
    assert "composition_format" not in prior.focus_prepared.packet
    assert "selected_comparisons" not in prior.focus_prepared.packet


def test_comparison_skips_missing_naive_and_mismatched_endpoints_preserves_ties() -> None:
    def row(ref: str, elapsed: object, departure: object, arrival: object,
            *, origin: str = "SFO", destination: str = "BKK") -> dict[str, object]:
        return {"members": [{"ref": ref}], "facts": {
            "elapsed_minutes": elapsed, "departure": {"local_iso": departure},
            "arrival": {"local_iso": arrival},
            "route": {"origin": origin, "destination": destination}}}

    rows = [
        row("J1", "1220", "2027-01-15T23:15:00-08:00", "2027-01-17T10:35:00+07:00"),
        row("J2", "1220", "2027-01-16T07:15:00+00:00", "2027-01-17T03:35:00+00:00"),
        row("J3", "unknown", "2027-01-15T22:00:00", "2027-01-17T10:00:00"),
        row("J4", "1300", "2027-01-15T20:00:00-08:00", "2027-01-17T12:00:00+07:00",
            origin="LAX", destination="NRT"),
    ]
    result = selected_comparisons(rows)
    assert [item for item in result["elapsed_minutes"] if item["relation"] == "equal"] == [
        {"relation": "equal", "first": "J1", "second": "J2",
         "difference_minutes": "0", "difference_display": "0 min"}]
    assert len(result["departure_instant"]) == 1
    assert result["departure_instant"][0]["relation"] == "equal"
    assert len(result["arrival_instant"]) == 1
    assert result["arrival_instant"][0]["relation"] == "equal"
    assert all("J3" not in str(value) for value in result.values())
    assert all("J4" not in str(value) for key, value in result.items()
               if key != "elapsed_minutes")
    reverse = selected_comparisons(list(reversed(deepcopy(rows))))
    def normalized(value: dict[str, list[dict[str, str]]]) -> dict[str, set[tuple[str, ...]]]:
        return {key: {(item["relation"], *(sorted((item["first"], item["second"]))
                      if item["relation"] == "equal" else (item["first"], item["second"])),
                       item["difference_minutes"]) for item in items}
                for key, items in value.items()}
    assert normalized(result) == normalized(reverse)


def test_v3_two_call_binding_keeps_v2_selector_request() -> None:
    prior = _artifact("focused2-a-recovery")
    raw = [item.raw_wire for item in prior.passes]
    receipts = [item.writer_receipt for item in prior.passes]
    assert all(item is not None for item in raw + receipts)

    class FakeWriter:
        def __init__(self) -> None:
            self.requests: list[dict[str, object]] = []
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            index = len(self.requests)
            self.requests.append(request)
            self.pending = receipts[index]
            assert raw[index] is not None
            return raw[index]

        def take_receipt(self) -> WriterReceipt | None:
            result, self.pending = self.pending, None
            return result

    class FakeMeasurer:
        def __init__(self) -> None:
            self.requests: list[dict[str, object]] = []

        def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
            self.requests.append(request)
            return InputTokenReceipt(request_digest=content_digest(request), input_tokens=100,
                                     raw_response={"object": "response.input_tokens",
                                                   "input_tokens": 100})

    old_writer, new_writer = FakeWriter(), FakeWriter()
    old = run_focused_results(prior.evidence.source, prior.config, old_writer, FakeMeasurer(),
                              selection_format="roles-v2")
    new = run_focused_results(prior.evidence.source, prior.config, new_writer, FakeMeasurer(),
                              selection_format="roles-v2", composition_format="comparisons-v1")
    assert old.delivery_outcome == "delivered"
    assert old_writer.requests[0] == new_writer.requests[0] == prior.passes[0].request
    assert old_writer.requests[1] == prior.passes[1].request
    assert new_writer.requests[1] != old_writer.requests[1]
    assert new.focus_prepared is not None
    assert new.focus_prepared.packet["composition_format"] == "comparisons-v1"
    assert replay_focused_results(new) == new.resolved


def test_cli_v3_measure_uses_same_selector_packet_as_v2(tmp_path: Path) -> None:
    prior = _artifact("focused2-a-recovery")
    projection_path = tmp_path / "projection.json"
    config_path = tmp_path / "config.json"
    projection_path.write_text(prior.evidence.source.model_dump_json(), encoding="utf-8")
    config_path.write_text(prior.config.model_dump_json(), encoding="utf-8")
    common = ["measure", "--interactive", "--projection", str(projection_path),
              "--config", str(config_path)]
    outputs = []
    for profile in ("focused-v2", "focused-v3"):
        output = tmp_path / f"{profile}.json"
        assert results_cli.main([*common, "--packet-profile", profile,
                                 "--output", str(output)]) == 0
        outputs.append(json.loads(output.read_text(encoding="utf-8")))
    assert outputs[0]["packet_digest"] == outputs[1]["packet_digest"]


@pytest.mark.parametrize("name", ("focus-a", "focus-b", "focus-c", "focused2-a-recovery",
                                  "focused2-b", "focused2-c"))
def test_saved_focused_profiles_replay_exactly(name: str) -> None:
    artifact = _artifact(name)
    assert replay_focused_results(artifact) == artifact.resolved
