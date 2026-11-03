"""Default Results authoring routes through the provisional Luna V27 channel."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_results_focused_v23 import SavedWriter
from test_results_focused_v24 import RUNS

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    DEFAULT_RESULTS_PROFILE,
    FocusedResultsArtifactV11,
    InputTokenReceipt,
    ResultsConfig,
    WriterReceipt,
    prepare_focused_selector,
    run_default_results,
)
from award_agent.results import default as default_results
from award_agent.results.focused import parse_focused_artifact, replay_focused_results

SOURCE = Path("evidence/ranking-stage/m2/solutions/exact_business.json")
CONFIG = Path("data/results/fast-default.json")


class FakeWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        self.calls += 1
        packet = json.loads(str(request["input"]))["packet"]
        if self.calls == 1:
            ref = next(iter(packet["journey_records"]))
            raw = json.dumps({"choices": [{"k": "j", "r": ref,
                                          "purpose": "Explain this selected journey",
                                          "compare_to": None}]})
        else:
            if self.calls == 2:
                ref = next(ref for ref, record in packet["authoring_records"].items()
                           if record["role"] == "journey")
                raw = json.dumps({"blocks": [{"k": "p", "r": ref, "n": "Journey",
                                              "v": "A complete journey with a useful schedule."}]})
            else:
                raw = '{"edits":[]}'
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


class FakeMeasurer:
    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        return InputTokenReceipt(request_digest=content_digest(request), input_tokens=100,
            raw_response={"object": "response.input_tokens", "input_tokens": 100})


def _inputs(tmp_path: Path) -> tuple[Path, Path, SolutionProjection, ResultsConfig]:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    return source_path, config_path, source, config


def test_public_default_uses_v27_without_automatic_count_for_injected_writer(
        monkeypatch: pytest.MonkeyPatch) -> None:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    writer = FakeWriter()
    monkeypatch.setattr("openai.OpenAI", lambda **_: pytest.fail("injected writer created a client"))
    artifact = run_default_results(source, config, writer)
    assert DEFAULT_RESULTS_PROFILE == "focused-v27"
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.delivery_outcome == "delivered"
    assert len(artifact.passes) == writer.calls == 2
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v21"
    assert artifact.focus_prepared is not None
    assert artifact.focus_prepared.packet["composition_format"] == "complete-v19"
    assert [item.request["reasoning"] for item in artifact.passes] == [
        {"effort": "none"}, {"effort": "low"}]
    assert all(item.input_token_receipt is None for item in artifact.passes)


def test_public_default_rejects_other_model_before_creating_live_adapters(
        monkeypatch: pytest.MonkeyPatch) -> None:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes()).model_copy(
        update={"model": "gpt-6.1-sol"})
    from award_agent.results import adapter, interactive_adapter

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("live adapter was constructed")

    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer", forbidden)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", forbidden)
    with pytest.raises(ValueError, match="gpt-6-luna"):
        run_default_results(source, config)


def test_cli_default_measure_and_live_authoring_use_v27(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path, config_path, source, config = _inputs(tmp_path)
    common = ["--projection", str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v21").packet_digest
    explicit_path = tmp_path / "explicit-measure.json"
    assert results_cli.main(["measure", "--interactive", *common,
                             "--output", str(explicit_path)]) == 0
    assert json.loads(explicit_path.read_text()) == json.loads(measure_path.read_text())

    from award_agent.results import adapter, interactive_adapter

    clients: list[object] = []
    class FakeClient:
        def __init__(self, *, max_retries: int, timeout: float) -> None:
            assert max_retries == 0 and timeout == config.timeout_seconds
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    injected: list[tuple[str, object]] = []
    writer = FakeWriter()
    monkeypatch.setattr("openai.OpenAI", FakeClient)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter",
                        lambda client: injected.append(("writer", client)) or writer)
    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer",
                        lambda client: injected.append(("measurer", client)) or FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["contract_version"] == "results-artifact-v11"
    assert writer.calls == 2
    assert len(clients) == 1 and injected == [("writer", clients[0]), ("measurer", clients[0])]
    assert clients[0].closed
    interactive_writer = FakeWriter()
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter",
                        lambda client: injected.append(("writer", client)) or interactive_writer)
    interactive_output = tmp_path / "interactive-artifact.json"
    assert results_cli.main(["author", "--interactive", *common, "--live",
                             "--output", str(interactive_output)]) == 0
    assert json.loads(interactive_output.read_text())["contract_version"] == "results-artifact-v11"
    assert interactive_writer.calls == 2
    assert len(clients) == 2 and clients[1].closed
    assert injected[-2:] == [("writer", clients[1]), ("measurer", clients[1])]


def test_public_default_closes_owned_client_on_failure(
        monkeypatch: pytest.MonkeyPatch) -> None:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    closed: list[bool] = []

    class FakeClient:
        def __init__(self, *, max_retries: int, timeout: float) -> None:
            assert max_retries == 0 and timeout == config.timeout_seconds

        def close(self) -> None:
            closed.append(True)

    from award_agent.results import adapter, interactive_adapter

    monkeypatch.setattr("openai.OpenAI", FakeClient)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda client: FakeWriter())
    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer", lambda client: FakeMeasurer())
    monkeypatch.setattr(default_results, "run_focused_results",
                        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failed")))
    with pytest.raises(RuntimeError, match="failed"):
        run_default_results(source, config)
    assert closed == [True]


def test_default_client_init_failure_propagates_without_authoring(
        monkeypatch: pytest.MonkeyPatch) -> None:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    from award_agent.results import interactive_adapter

    def failed_client(**kwargs: object) -> None:
        raise RuntimeError("client initialization failed")

    monkeypatch.setattr("openai.OpenAI", failed_client)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter",
                        lambda client: pytest.fail("authoring adapter created after client failure"))
    with pytest.raises(RuntimeError, match="client initialization failed"):
        run_default_results(source, config)


def test_default_does_not_close_caller_measurer(
        monkeypatch: pytest.MonkeyPatch) -> None:
    source = SolutionProjection.model_validate_json(SOURCE.read_bytes())
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    closed: list[str] = []
    from award_agent.results import interactive_adapter

    class FakeClient:
        def close(self) -> None:
            closed.append("client")

    class CallerMeasurer(FakeMeasurer):
        def close(self) -> None:
            closed.append("measurer")

    monkeypatch.setattr("openai.OpenAI", lambda **_: FakeClient())
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter",
                        lambda client: FakeWriter())
    artifact = run_default_results(source, config, input_measurer=CallerMeasurer())
    assert artifact.delivery_outcome == "delivered"
    assert closed == ["client"]


def test_partial_default_api_and_cli_measure_author_replay(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = parse_focused_artifact((RUNS / "scout-v24-incomplete-1" / "artifact.json").read_bytes())
    assert isinstance(old, FocusedResultsArtifactV11)
    assert old.passes[0].raw_wire is not None and old.passes[1].raw_wire is not None
    source, config = old.evidence.source, old.config
    wires = [old.passes[0].raw_wire, old.passes[1].raw_wire]
    offline = run_default_results(source, config, SavedWriter(wires), FakeMeasurer())
    assert isinstance(offline, FocusedResultsArtifactV11)
    assert offline.selector_prepared.packet["selection_format"] == "roles-v25"
    assert offline.focus_prepared is not None
    assert offline.focus_prepared.packet["composition_format"] == "complete-v23"
    assert [item.request["reasoning"]["effort"] for item in offline.passes] == [
        "medium", "medium"]
    assert replay_focused_results(offline) == offline.resolved
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--projection", str(source_path), "--config", str(config_path)]
    measure = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure)]) == 0
    assert json.loads(measure.read_text())["packet_digest"] == prepare_focused_selector(
        source, config, selection_format="roles-v25").packet_digest
    monkeypatch.setattr("openai.OpenAI", lambda **_: SimpleNamespace(close=lambda: None))
    from award_agent.results import adapter, interactive_adapter

    writer = SavedWriter(wires)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda client: writer)
    monkeypatch.setattr(adapter, "OpenAIResultsInputMeasurer", lambda client: FakeMeasurer())
    output = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(output)]) == 0
    artifact = parse_focused_artifact(output.read_bytes())
    assert isinstance(artifact, FocusedResultsArtifactV11)
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v25"
    assert [request["reasoning"]["effort"] for request in writer.requests] == [
        "medium", "medium"]
    replay = tmp_path / "replay.json"
    assert results_cli.main(["replay", "--artifact", str(output), "--output", str(replay)]) == 0


def test_cli_legacy_live_dispatch_remains_explicit(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    source_path, config_path, _, _ = _inputs(tmp_path)
    called: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        called.append((args, kwargs))
        return SimpleNamespace(model_dump_json=lambda **_: '{"contract_version":"results-artifact-v5"}',
            generation_outcome="success", validation_outcome="clean", delivery_outcome="delivered",
            attempts=())

    monkeypatch.setattr(results_cli, "run_results", fake_run)
    monkeypatch.setattr(results_cli, "OpenAIResultsWriter", lambda: object())
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda: object())
    output = tmp_path / "legacy.json"
    assert results_cli.main(["author", "--legacy", "--projection", str(source_path),
                             "--config", str(config_path), "--live", "--output", str(output)]) == 0
    assert len(called) == 1
    assert json.loads(output.read_text())["contract_version"] == "results-artifact-v5"
