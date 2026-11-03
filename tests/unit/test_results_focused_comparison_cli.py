"""CLI routing and source-owned comparison cards for focused-v11."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    FocusedResultsArtifactV11,
    InputTokenReceipt,
    ResultsConfig,
    WriterReceipt,
    format_focused_comparison_block,
    parse_focused_artifact,
    prepare_focused_selector,
)
from award_agent.results.focused_comparison_contracts import ResolvedFocusedComparisonBlock


class FakeMeasurer:
    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        return InputTokenReceipt(request_digest=content_digest(request), input_tokens=100,
            raw_response={"object": "response.input_tokens", "input_tokens": 100})


class FakeComparisonWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        self.calls += 1
        packet = json.loads(str(request["input"]))["packet"]
        if self.calls == 1:
            refs = (list(packet["journey_records"])[:2] if
                    "journey_records" in packet else
                    [row[0] for row in packet["journey_rows"][:2]])
            assert len(refs) == 2
            raw = json.dumps({"choices": ([
                {"k": "j", "r": ref, "purpose": "Compare a supported tradeoff",
                 "compare_to": refs[1 - index]} for index, ref in enumerate(refs)]
                if packet.get("selection_format") in {"roles-v13", "roles-v14", "roles-v15"} else
                [{"k": "j", "r": ref} for ref in refs])})
        else:
            comparisons = packet["temporal_comparisons"]
            assert comparisons
            pair = comparisons[0]
            first, second = pair["first_ref"], pair["second_ref"]
            blocks = [{"k": "p", "r": first, "n": "First option",
                       "v": "A complete journey with a useful schedule."}]
            if self.calls == 3:
                blocks.append({"k": "a", "r": second, "n": "Alternative",
                               "v": "A second complete journey with a different schedule."})
            blocks.append({"k": "x", "r": pair["id"]})
            raw = json.dumps({"blocks": blocks})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


@pytest.mark.parametrize("profile", ["focused-v11", "focused-v12", "focused-v13",
                                     "focused-v14", "focused-v15", "focused-v16"])
def test_comparison_cli_corrects_missing_endpoint_and_replays(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str) -> None:
    source = SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())
    config = ResultsConfig.model_validate_json(Path("data/results/fast-default.json").read_bytes())
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", profile,
              "--projection", str(source_path), "--config", str(config_path)]
    measured_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measured_path)]) == 0
    expected_format: Literal["roles-v10", "roles-v11", "roles-v12", "roles-v13", "roles-v14", "roles-v15"] = (
        "roles-v15" if profile == "focused-v16" else
        "roles-v14" if profile == "focused-v15" else
        "roles-v13" if profile == "focused-v14" else
        "roles-v12" if profile == "focused-v13" else
        "roles-v11" if profile == "focused-v12" else "roles-v10")
    assert json.loads(measured_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format=expected_format).packet_digest

    from award_agent.results import adapter, interactive_adapter

    writer = FakeComparisonWriter()
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    artifact = parse_focused_artifact(artifact_path.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == expected_format
    assert artifact.selector_settings.reasoning_effort == (
        "medium" if profile == "focused-v14" else "low")
    assert artifact.composer_settings.reasoning_effort == (
        "low" if profile == "focused-v12" else "medium")
    assert [item.phase for item in artifact.passes] == ["selection", "composition", "correction"]
    if profile in {"focused-v13", "focused-v14", "focused-v15", "focused-v16"}:
        assert artifact.passes[2].request["reasoning"] == {"effort": "low"}
    assert any(f.code == "comparison_endpoint_not_visible" and f.outcome == "failed"
               for f in artifact.passes[1].findings)
    assert artifact.selected_pass_index == 2
    assert writer.calls == 3
    assert artifact.resolved is not None
    comparison_blocks = [block for block in artifact.resolved.blocks
                         if isinstance(block, ResolvedFocusedComparisonBlock)]
    assert len(comparison_blocks) == 1
    assert "Journey duration:" in format_focused_comparison_block(comparison_blocks[0]) or \
           "Departure:" in format_focused_comparison_block(comparison_blocks[0]) or \
           "Arrival:" in format_focused_comparison_block(comparison_blocks[0])

    replay_path = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(replay_path)]) == 0
    resolved = json.loads(replay_path.read_text())
    assert resolved["contract_version"] == "results-focused-resolved-v1"
    assert any(block["kind"] == "comparison" for block in resolved["blocks"])
