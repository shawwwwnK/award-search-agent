"""V19 grounded pair dossiers and atomic editorial repair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_results_focused import FakeMeasurer

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, WriterReceipt
from award_agent.results.focused import (
    parse_focused_artifact,
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_patch import apply_patch, decode_patch
from award_agent.results.focused_patch_contracts import FocusedResultsArtifactV12

RUNS = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/runs")
CONFIG = Path("data/results/fast-default.json")


class _FrozenV19Writer:
    def __init__(self, selection_wire: str, patch_wire: str = '{"edits":[]}', *,
                 draft_claim: str = "A selected source option for the traveler to check.") -> None:
        self.selection_wire = selection_wire
        self.patch_wire = patch_wire
        self.draft_claim = draft_claim
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        phase = len(self.requests)
        self.requests.append(request)
        if phase == 0:
            raw = self.selection_wire
        elif phase == 1:
            packet = json.loads(str(request["input"]))["packet"]
            records = packet["authoring_records"]
            blocks = []
            for ref, record in records.items():
                role = record["role"]
                if role == "journey":
                    kind = "p" if not any(item["k"] == "p" for item in blocks) else "a"
                elif role == "lead":
                    kind = "l"
                else:
                    kind = "b"
                blocks.append({"k": kind, "r": ref, "n": "Visible option",
                               "v": self.draft_claim})
            pairs = packet["comparison_pairs"]
            if pairs and pairs[0]["card_ids"]:
                blocks.append({"k": "x", "r": pairs[0]["card_ids"][0]["id"]})
            raw = json.dumps({"blocks": blocks})
        else:
            raw = self.patch_wire
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


def _run_from_archived(name: str, patch_wire: str = '{"edits":[]}', *,
                       draft_claim: str = "A selected source option for the traveler to check.") -> tuple[
        FocusedResultsArtifactV12, _FrozenV19Writer, object]:
    old = parse_focused_artifact((RUNS / name / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    assert old.passes[0].raw_wire is not None
    writer = _FrozenV19Writer(old.passes[0].raw_wire, patch_wire, draft_claim=draft_claim)
    artifact = run_focused_results(source, config, writer, FakeMeasurer(), profile="focused-v19")
    assert isinstance(artifact, FocusedResultsArtifactV12)
    return artifact, writer, old


def _pair(packet: dict[str, object], a: str, b: str) -> dict[str, object]:
    return next(row for row in packet["comparison_pairs"]
                if {row["left_ref"].split("@")[0], row["right_ref"].split("@")[0]} == {a, b})


@pytest.mark.parametrize("name,expected_pairs", [
    ("confirm-v18p-default-1-admitted", 6),
    ("confirm-v18p-default-1-conditional", 6),
    ("confirm-v18p-default-1-incomplete", 3),
])
def test_v19_omits_selector_purpose_and_replays_all_selected_pairs(
        name: str, expected_pairs: int) -> None:
    artifact, writer, old = _run_from_archived(name)
    assert len(writer.requests) == len(artifact.passes) == 3
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v18"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v16"
    assert [item.request["reasoning"] for item in artifact.passes] == [
        {"effort": "low"}] * 3
    draft_packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    editor_packet = json.loads(str(writer.requests[2]["input"]))["packet"]
    assert draft_packet == editor_packet
    assert draft_packet["format"] == "focused-authoring-records-v3"
    assert len(draft_packet["comparison_pairs"]) == expected_pairs
    assert "selected_comparisons" not in draft_packet
    assert "temporal_comparisons" not in draft_packet
    assert all(set(row) == {"role", "ref", "compare_to", "status"}
               for row in draft_packet["editorial_plan"])
    for choice in json.loads(old.passes[0].raw_wire)["choices"]:
        assert choice["purpose"] not in str(writer.requests[1]["input"])
        assert choice["purpose"] not in str(writer.requests[2]["input"])
    assert replay_focused_results(parse_focused_artifact(artifact.model_dump_json())) == artifact.resolved
    assert len(str(writer.requests[1]["input"])) < 2 * len(str(old.passes[1].request["input"]))


def test_v19_q063_pairs_bind_program_carrier_money_and_distinct_time_metrics() -> None:
    artifact, writer, _ = _run_from_archived("confirm-v18p-default-1-admitted")
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    pair = _pair(packet, "J7", "J20")
    assert {pair["left"]["award_points"], pair["right"]["award_points"]} == {65000, 92144}
    assert {pair["left"]["award_carriers"][0], pair["right"]["award_carriers"][0]} == {"BR", "AC"}
    quotes = {pair["left"]["award_quote"]["display"], pair["right"]["award_quote"]["display"]}
    assert quotes == {"CAD 116.50", "CAD 43.90"}
    assert pair["relations"]["award_points"]["comparison_scope"] == "reported_raw_points_same_program_only"
    assert pair["relations"]["award_quote"]["comparison_scope"] == "reported_raw_quote_amounts_only"
    assert pair["relations"]["arrival"]["difference_minutes"] == "305"
    assert pair["relations"]["elapsed_minutes"]["difference_minutes"] == "10"
    assert pair["relations"]["arrival"]["relation"] != pair["relations"]["elapsed_minutes"]["relation"]
    assert {row["metric"] for row in pair["card_ids"]} == {"arrival", "departure", "elapsed"}
    assert pair["relations"]["matching_connection_waits"] == []
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["editorial_plan"][2]["purpose"].find("previous evening") >= 0


def test_v19_q064_keeps_cash_carrier_and_wait_role_associations() -> None:
    _, writer, _ = _run_from_archived("confirm-v18p-default-1-conditional")
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    same = _pair(packet, "J105", "J115")
    other = _pair(packet, "J115", "J150")
    assert same["left"]["cash_carriers"] == same["right"]["cash_carriers"] == ["Alaska"]
    assert same["relations"]["cash_carriers"] == {"relation": "equal"}
    assert {tuple(other["left"]["cash_carriers"]), tuple(other["right"]["cash_carriers"])} == {
        ("Alaska",), ("United",)}
    assert other["relations"]["cash_carriers"] == {"relation": "different"}
    assert all(row["role"] in {"award_connections", "journey_connections"}
               for row in other["relations"]["matching_connection_waits"])
    time_pair = _pair(packet, "J63", "J150")
    assert time_pair["relations"]["arrival"]["difference_minutes"] == "275"
    assert time_pair["relations"]["elapsed_minutes"]["difference_minutes"] == "39"


def test_v19_incomplete_cross_program_currency_is_not_compared() -> None:
    _, writer, _ = _run_from_archived("confirm-v18p-default-1-incomplete")
    packet = json.loads(str(writer.requests[1]["input"]))["packet"]
    pair = _pair(packet, "A1", "A3")
    assert pair["left"]["role"] == pair["right"]["role"] == "lead"
    assert pair["relations"]["award_points"]["relation"] == "not_comparable"
    assert pair["relations"]["reported_quote"]["relation"] == "not_comparable"
    assert "elapsed_minutes" not in pair["relations"]


@pytest.mark.parametrize("bad", [
    '{"edits":[{"start":0,"end":0,"blocks":[{"k":"t","v":"Inserted"}]}]}',
    '{"edits":[{"start":0,"end":2,"blocks":[]}]}',
    '{"edits":[{"start":0,"end":1,"blocks":[{"k":"t","v":"One"},{"k":"t","v":"Two"}]}]}',
])
def test_v19_rejects_non_atomic_edits_while_retaining_draft(bad: str) -> None:
    with pytest.raises(ValueError, match="atomic editorial"):
        decode_patch(bad, atomic=True)
    assert decode_patch(bad).edits
    artifact, _, _ = _run_from_archived("confirm-v18p-default-1-admitted", bad)
    assert len(artifact.passes) == 3
    assert artifact.passes[2].failure_subtype == "schema_error"
    assert artifact.selected_pass_index == 1
    assert replay_focused_results(artifact) == artifact.resolved


def test_v19_allows_one_block_replacement_and_deletion() -> None:
    draft = '{"blocks":[{"k":"t","v":"First"},{"k":"t","v":"Second"}]}'
    replace = decode_patch('{"edits":[{"start":0,"end":1,"blocks":[{"k":"t","v":"New"}]}]}',
                           atomic=True)
    assert json.loads(apply_patch(draft, replace, atomic=True))["blocks"][0]["v"] == "New"
    delete = decode_patch('{"edits":[{"start":1,"end":2,"blocks":[]}]}', atomic=True)
    assert len(json.loads(apply_patch(draft, delete, atomic=True))["blocks"]) == 1


def test_v19_replay_recomputes_pair_dossier_from_canonical_source() -> None:
    artifact, _, _ = _run_from_archived("confirm-v18p-default-1-admitted")
    data = artifact.model_dump(mode="json")
    focus = data["focus_prepared"]
    focus["packet"]["comparison_pairs"][0]["relations"]["arrival"]["difference_minutes"] = "9999"
    focus["packet_digest"] = content_digest(focus["packet"])
    with pytest.raises(ValueError):
        replay_focused_results(FocusedResultsArtifactV12.model_validate(data))


def test_v19_valid_time_card_does_not_semantically_validate_false_adjacent_prose() -> None:
    artifact, writer, _ = _run_from_archived(
        "confirm-v18p-default-1-admitted", draft_claim="This option arrives on December 1.")
    draft = json.loads(artifact.passes[1].raw_wire)
    assert any(block["k"] == "x" for block in draft["blocks"])
    assert any("December 1" in block.get("v", "") for block in draft["blocks"])
    assert artifact.validation_outcome == "clean"
    assert replay_focused_results(artifact) == artifact.resolved
    assert writer.requests[1]["input"]


def test_v19_cli_explicit_measure_author_and_replay(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    old = parse_focused_artifact((RUNS / "confirm-v18p-default-1-admitted" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v19", "--projection",
              str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v18").packet_digest
    from award_agent.results import interactive_adapter

    assert old.passes[0].raw_wire is not None
    writer = _FrozenV19Writer(old.passes[0].raw_wire)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    assert len(writer.requests) == 3
    assert json.loads(artifact_path.read_text())["contract_version"] == "results-artifact-v12"
    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
    assert json.loads(replay_path.read_text())["contract_version"] == "results-focused-resolved-v1"
