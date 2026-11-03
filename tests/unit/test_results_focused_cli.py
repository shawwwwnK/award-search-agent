"""Explicit focused CLI profiles preserve V9 routing and exact replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    FocusedResultsArtifactV9,
    FocusedResultsArtifactV10,
    InputTokenReceipt,
    ResultsConfig,
    WriterReceipt,
    parse_focused_artifact,
    prepare_focused_selector,
)


class FakeMeasurer:
    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        return InputTokenReceipt(request_digest=content_digest(request), input_tokens=100,
            raw_response={"object": "response.input_tokens", "input_tokens": 100})


class FakeWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        self.calls += 1
        packet = json.loads(str(request["input"]))["packet"]
        if self.calls == 1:
            raw = json.dumps({"choices": [{"k": "j", "r": packet["journey_rows"][0][0]}]})
        else:
            ref = packet["journeys"][0]["members"][0]["ref"]
            raw = json.dumps({"blocks": [{"k": "p", "r": ref, "n": "Journey",
                                          "v": "A complete award journey with a useful schedule."}]})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


@pytest.mark.parametrize("profile", ["focused-v4", "focused-v5", "focused-v6",
                                     "focused-v7", "focused-v8", "focused-v9",
                                     "focused-v10"])
def test_explicit_focused_cli_measure_author_and_replay(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str) -> None:
    source = SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())
    config = ResultsConfig(model="gpt-6-luna", max_output_tokens=1000,
                           timeout_seconds=10, context_limit_tokens=10_000_000,
                           prompt_overhead_tokens=0)
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", profile,
              "--projection", str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measurement.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    measured = json.loads(measure_path.read_text())
    assert measured["source_digest"] == source.receipt.view_digest
    expected_format: Literal["roles-v3", "roles-v4", "roles-v5", "roles-v6",
                             "roles-v7", "roles-v8", "roles-v9"] = (
        "roles-v9" if profile == "focused-v10" else
        "roles-v8" if profile == "focused-v9" else
        "roles-v7" if profile == "focused-v8" else
        "roles-v6" if profile == "focused-v7" else
        "roles-v5" if profile == "focused-v6" else
        "roles-v4" if profile == "focused-v5" else "roles-v3")
    assert measured["packet_digest"] == prepare_focused_selector(
        source, config, selection_format=expected_format).packet_digest

    from award_agent.results import interactive_adapter

    writer = FakeWriter()
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda: writer)
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: FakeMeasurer())
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    artifact = parse_focused_artifact(artifact_path.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV10 if profile in {
        "focused-v8", "focused-v9", "focused-v10"}
                      else FocusedResultsArtifactV9)
    assert artifact.selector_prepared.packet["selection_format"] == expected_format
    assert artifact.selector_settings.reasoning_effort == (
        "medium" if profile == "focused-v6" else
        "low" if profile in {"focused-v5", "focused-v7", "focused-v8", "focused-v9",
                             "focused-v10"}
        else "none")
    assert artifact.composer_settings.reasoning_effort == (
        "medium" if profile in {"focused-v6", "focused-v7"} else
        "none" if profile == "focused-v10" else "low")
    if profile in {"focused-v8", "focused-v9", "focused-v10"}:
        assert isinstance(artifact, FocusedResultsArtifactV10)
        assert artifact.revision_settings.reasoning_effort == (
            "low" if profile == "focused-v9" else "medium")
        assert [item.phase for item in artifact.passes] == [
            "selection", "composition", "revision"]
    assert artifact.delivery_outcome == "delivered"
    assert writer.calls == (3 if profile in {"focused-v8", "focused-v9", "focused-v10"}
                            else 2)
    answer_path = tmp_path / "answer.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(answer_path)]) == 0
    assert json.loads(answer_path.read_text())["contract_version"] == "results-resolved-v2"


def test_v4_rejects_external_effort_override(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        results_cli.main(["measure", "--interactive", "--packet-profile", "focused-v4",
                          "--reasoning-effort", "medium", "--projection", "unused",
                          "--config", "unused", "--output", str(tmp_path / "out.json")])


def test_fast_default_config_is_valid_luna_settings() -> None:
    config = ResultsConfig.model_validate_json(Path("data/results/fast-default.json").read_bytes())
    assert config.model == "gpt-6-luna"
    assert config.max_output_tokens == 8192
    assert config.authoring_guidance == (
        "Write for the traveler. Call the supplied material search results, "
        "not a packet or an internal validation workflow. Report amounts as source quotes "
        "and preserve unknown scope. Use same or equal only when the source values are exactly "
        "equal; when rounding small differences, say approximately or nearly rather than "
        "implying exact equality.")
