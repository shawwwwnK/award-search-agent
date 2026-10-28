"""Interactive Results wire, request, and saved-source replay."""

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import httpx
import pytest

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive import (
    prepare_interactive_results,
    replay_interactive_results,
    run_interactive_results,
)
from award_agent.results.interactive_adapter import (
    OpenAIInteractiveResultsWriter,
    _safe_api_error_message,
)
from award_agent.results.interactive_contracts import (
    InteractiveResultsArtifact,
    InteractiveSettings,
)
from award_agent.results.interactive_packet import build_packet
from award_agent.results.presentation import resolve_workspace


def _projection() -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())


def _config() -> ResultsConfig:
    return ResultsConfig(model="gpt-6.1-luna", max_output_tokens=1000,
                         timeout_seconds=10, context_limit_tokens=10_000_000,
                         prompt_overhead_tokens=0)


class FakeWriter:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.requests: list[dict[str, object]] = []

    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: InteractiveSettings) -> str:
        self.requests.append(request)
        return self.raw

    def take_receipt(self) -> WriterReceipt:
        return WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": self.raw}]}]}))


def test_interactive_exact_source_replay_and_tamper_detection() -> None:
    projection = _projection()
    config = _config()
    prepared = prepare_interactive_results(projection, config)
    assert "format" not in prepared.packet
    assert prepared.packet == json.loads(json.dumps(build_packet(
        prepared.structured, projection, resolve_workspace(projection))))
    assert prepared.packet_digest == content_digest(prepared.packet)
    alias, candidate = next(iter(prepared.structured.references.journeys.items()))
    writer = FakeWriter(json.dumps({"blocks": [
        {"k": "t", "v": "This is one useful choice."},
        {"k": "p", "r": alias, "n": "Option A", "v": "Consider its timing and price."}]}))
    artifact = run_interactive_results(projection, config,
        InteractiveSettings(reasoning_effort="none"), writer)
    assert artifact.contract_version == "results-artifact-v7"
    assert artifact.runtime_seconds > 0
    assert artifact.resolved is not None
    assert artifact.resolved.selected_journey_ids == (candidate,)
    assert artifact.evidence.source == projection
    assert replay_interactive_results(artifact) == artifact.resolved
    assert replay_interactive_results(InteractiveResultsArtifact.model_validate_json(
        artifact.model_dump_json())) == artifact.resolved
    assert writer.requests[0]["reasoning"] == {"effort": "none"}
    assert writer.requests[0]["model"] == config.model
    assert "service_tier" not in writer.requests[0]
    assert artifact.attempts[0].request_digest == content_digest(writer.requests[0])

    raw = artifact.model_dump(mode="json")
    raw["attempts"][0]["raw_wire"] = '{"blocks":[{"k":"p","r":"J999","n":"x","v":"x"}]}'
    with pytest.raises(ValueError, match="wire|reference"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))

    raw = artifact.model_dump(mode="json")
    raw["attempts"][0]["request"]["input"] = "tampered"
    with pytest.raises(ValueError, match="request"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))

    raw = artifact.model_dump(mode="json")
    raw["resolved_digest"] = "tampered"
    with pytest.raises(ValueError, match="answer"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))

    raw = artifact.model_dump(mode="json")
    raw["prepared"]["packet"]["format"] = "decision-joined-v5"
    with pytest.raises(ValueError, match="packet format"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))

    raw = artifact.model_dump(mode="json")
    raw["prepared"]["packet"]["format"] = None
    with pytest.raises(ValueError, match="packet format"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))

    raw = artifact.model_dump(mode="json")
    raw["attempts"][0]["writer_receipt"]["raw_response"] = json.dumps({
        "status": "completed", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": "different"}]}]})
    with pytest.raises(ValueError, match="raw writer response"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_interactive_invalid_wire_is_not_delivered() -> None:
    projection = _projection()
    config = _config()
    writer = FakeWriter('{"blocks":[{"k":"b","r":"C999","n":"Cash","v":"x"}]}')
    artifact = run_interactive_results(projection, config,
        InteractiveSettings(reasoning_effort="low", service_tier="fast"), writer)
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.attempts[0].failure_subtype == "schema_error"
    assert artifact.attempts[0].raw_wire == writer.raw
    assert replay_interactive_results(artifact) is None
    raw = artifact.model_dump(mode="json")
    raw["generation_outcome"] = "success"
    with pytest.raises(ValueError, match="generation outcome"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_saved_markerless_v7_artifact_still_replays() -> None:
    artifact = InteractiveResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/structured/2026-10-26-under20/runs/"
        "confirm-1-admitted/artifact.json").read_bytes())
    assert "format" not in artifact.prepared.packet
    assert replay_interactive_results(artifact) == artifact.resolved


def test_saved_joined_v2_artifact_still_replays() -> None:
    artifact = InteractiveResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/structured/2026-10-26-under20/runs/"
        "joined-a/artifact.json").read_bytes())
    assert artifact.prepared.packet["format"] == "decision-joined-v2"
    assert replay_interactive_results(artifact) == artifact.resolved


def test_joined_packet_replays_and_rejects_payload_tamper() -> None:
    projection = _projection()
    config = _config()
    prepared = prepare_interactive_results(projection, config, packet_profile="joined-v2")
    assert prepared.packet["format"] == "decision-joined-v2"
    alias = next(iter(prepared.structured.references.journeys))
    writer = FakeWriter(json.dumps({"blocks": [
        {"k": "p", "r": alias, "n": "Useful option", "v": "Consider this journey."}]}))
    artifact = run_interactive_results(projection, config,
        InteractiveSettings(reasoning_effort="low"), writer, packet_profile="joined-v2")
    assert artifact.prepared.packet["format"] == "decision-joined-v2"
    assert replay_interactive_results(artifact) == artifact.resolved
    raw = artifact.model_dump(mode="json")
    raw["prepared"]["packet"]["format"] = "decision-joined-v2"
    raw["prepared"]["packet"]["journeys"] = []
    with pytest.raises(ValueError, match="preparation"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_joined_v3_source_aliases_schema_and_replay() -> None:
    projection = _projection()
    config = _config()
    prepared = prepare_interactive_results(projection, config, packet_profile="joined-v3")
    assert prepared.packet["format"] == "decision-joined-v3"
    old_journey = next(iter(prepared.structured.references.journeys))
    new_journey = next(new for new, old in prepared.packet["wire_aliases"].items()
                       if old == old_journey)
    assert new_journey.startswith(old_journey + "@")
    raw_wire = json.dumps({"blocks": [{"k": "p", "r": new_journey,
                                        "n": "Choice", "v": "Useful option."}]})
    artifact = run_interactive_results(projection, config,
        InteractiveSettings(reasoning_effort="low"), FakeWriter(raw_wire),
        packet_profile="joined-v3")
    assert artifact.delivery_outcome == "delivered"
    assert replay_interactive_results(artifact) == artifact.resolved
    schema = artifact.attempts[0].request["text"]["format"]["schema"]
    branches = schema["properties"]["blocks"]["items"]["anyOf"]
    journey_branch = next(branch for branch in branches if branch["properties"]["k"]["enum"] == ["p", "a"])
    assert new_journey in journey_branch["properties"]["r"]["enum"]
    assert old_journey not in journey_branch["properties"]["r"]["enum"]

    tampered = artifact.model_dump(mode="json")
    tampered["prepared"]["packet"]["wire_aliases"][new_journey] = "J999"
    with pytest.raises(ValueError, match="preparation"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(tampered))

    benchmark_alias = next((new for new, old in prepared.packet["wire_aliases"].items()
                            if old in prepared.structured.references.cash and
                            prepared.structured.references.cash[old] in
                            projection.view.direct_cash_observation_ids), None)
    if benchmark_alias is not None:
        bad = FakeWriter(json.dumps({"blocks": [{"k": "p", "r": benchmark_alias,
                                                 "n": "Wrong role", "v": "x"}]}))
        failed = run_interactive_results(projection, config,
            InteractiveSettings(reasoning_effort="low"), bad, packet_profile="joined-v3")
        assert failed.delivery_outcome == "not_delivered"
        assert failed.attempts[0].failure_subtype == "schema_error"


def test_interactive_only_cli_controls_do_not_leak_into_legacy(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        results_cli.main(["measure", "--projection", "source.json", "--config", "config.json",
                          "--output", str(tmp_path / "out.json"), "--reasoning-effort", "none"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        results_cli.main(["measure", "--structured", "--projection", "source.json",
                          "--config", "config.json", "--output", str(tmp_path / "out.json"),
                          "--packet-profile", "joined-v2"])
    assert exc.value.code == 2


def test_cli_joined_profile_reaches_measure_and_author(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _projection()
    config = _config()
    source_path = tmp_path / "source.json"
    config_path = tmp_path / "config.json"
    source_path.write_text(projection.model_dump_json())
    config_path.write_text(config.model_dump_json())
    measure_path = tmp_path / "measure.json"
    common = ["--interactive", "--reasoning-effort", "low", "--packet-profile", "joined-v2",
              "--projection", str(source_path), "--config", str(config_path)]
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["packet_digest"] == (
        prepare_interactive_results(projection, config, packet_profile="joined-v2").packet_digest)

    from award_agent.results import interactive as interactive_module

    captured: list[str] = []
    prepared = prepare_interactive_results(projection, config, packet_profile="joined-v2")
    alias = next(iter(prepared.structured.references.journeys))
    artifact = run_interactive_results(projection, config, InteractiveSettings(reasoning_effort="low"),
        FakeWriter(json.dumps({"blocks": [{"k": "p", "r": alias, "n": "Choice", "v": "Useful."}]})),
        packet_profile="joined-v2")

    def fake_run(*args: object, **kwargs: object) -> InteractiveResultsArtifact:
        captured.append(str(kwargs["packet_profile"]))
        return artifact

    monkeypatch.setattr(interactive_module, "run_interactive_results", fake_run)
    output_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(output_path)]) == 0
    assert captured == ["joined-v2"]
    assert InteractiveResultsArtifact.model_validate_json(
        output_path.read_bytes()).prepared.packet["format"] == "decision-joined-v2"


def test_streaming_adapter_records_tier_timing_and_transport_failure() -> None:
    wire = '{"blocks":[{"k":"t","v":"A concise answer."}]}'

    class Stream:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def __iter__(self) -> Iterator[SimpleNamespace]:
            yield SimpleNamespace(type="response.created")
            yield SimpleNamespace(type="response.output_text.delta")
            if self.fail:
                raise httpx.ReadTimeout("stream interrupted")

        def get_final_response(self):
            raw = {"status": "completed", "service_tier": "priority",
                   "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                   "output": [{"type": "message", "content": [
                       {"type": "output_text", "text": wire}]}]}
            return SimpleNamespace(model_dump=lambda **kwargs: raw, output_text=wire)

    class Client:
        def __init__(self, fail: bool) -> None:
            self.fail = fail
            self.kwargs: dict[str, object] = {}
            self.responses = self

        def with_options(self, **kwargs: object) -> "Client":
            assert kwargs["max_retries"] == 0
            return self

        def stream(self, **kwargs: object) -> Stream:
            self.kwargs = kwargs
            return Stream(self.fail)

    from award_agent.results.contracts import ResultsWriterError

    client = Client(False)
    writer = OpenAIInteractiveResultsWriter(client)  # type: ignore[arg-type]
    assert writer.author({"model": "gpt-6.1-luna"}, _config(),
                         InteractiveSettings(reasoning_effort="none", service_tier="fast")) == wire
    assert client.kwargs["service_tier"] == "fast"
    receipt = writer.take_receipt()
    assert receipt is not None
    assert receipt.usage["first_event_ms"] >= 0
    assert receipt.usage["first_text_ms"] >= 0
    assert json.loads(receipt.raw_response or "{}")["service_tier"] == "priority"

    writer = OpenAIInteractiveResultsWriter(Client(True))  # type: ignore[arg-type]
    with pytest.raises(ResultsWriterError) as exc:
        writer.author({"model": "gpt-6.1-luna"}, _config(),
                      InteractiveSettings(reasoning_effort="none"))
    assert exc.value.outcome == "api_error"
    assert str(exc.value) == "Interactive Results writer request failed. exception=ReadTimeout"
    assert "stream interrupted" not in str(exc.value)
    assert writer.take_receipt() is not None


def test_stream_terminal_events_and_unfinished_eof_are_preserved() -> None:
    from award_agent.results.contracts import ResultsWriterError

    wire = '{"blocks":[{"k":"t","v":"A concise answer."}]}'

    class Response:
        def __init__(self, status: str) -> None:
            self.status = status
            self.output_text = wire if status == "completed" else ""

        def model_dump(self, **kwargs: object) -> dict[str, object]:
            return {
                "status": self.status,
                "usage": {"input_tokens": 11, "output_tokens": 3, "total_tokens": 14},
                "output": ([{"type": "message", "content": [
                    {"type": "output_text", "text": wire}]}]
                    if self.status == "completed" else []),
            }

    class Stream:
        def __init__(self, status: str | None, final_error: str | None = None) -> None:
            self.status = status
            self.final_error = final_error
            self.final_response_calls = 0

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def __iter__(self) -> Iterator[SimpleNamespace]:
            yield SimpleNamespace(type="response.created")
            yield SimpleNamespace(type="response.output_text.delta")
            if self.status is not None:
                yield SimpleNamespace(type=f"response.{self.status}",
                                      response=Response(self.status))

        def get_final_response(self) -> Response:
            self.final_response_calls += 1
            if self.final_error is not None:
                raise RuntimeError(self.final_error)
            raise AssertionError("terminal response must be used directly")

    class Client:
        def __init__(self, status: str | None, final_error: str | None = None) -> None:
            self.stream_instance = Stream(status, final_error)
            self.responses = self

        def with_options(self, **kwargs: object) -> "Client":
            assert kwargs["max_retries"] == 0
            return self

        def stream(self, **kwargs: object) -> Stream:
            return self.stream_instance

    for status, expected in (("completed", "completed"), ("incomplete", "incomplete"),
                             ("failed", "api_error")):
        client = Client(status)
        writer = OpenAIInteractiveResultsWriter(client)  # type: ignore[arg-type]
        if status == "completed":
            assert writer.author({}, _config(), InteractiveSettings(
                reasoning_effort="none")) == wire
        else:
            with pytest.raises(ResultsWriterError) as exc:
                writer.author({}, _config(), InteractiveSettings(reasoning_effort="none"))
            assert exc.value.outcome == expected
        receipt = writer.take_receipt()
        assert receipt is not None
        assert receipt.status == status
        assert receipt.usage["input_tokens"] == 11
        assert client.stream_instance.final_response_calls == 0

    eof_message = "Didn't receive a " + chr(96) + "response.completed" + chr(96) + " event."
    client = Client(None, eof_message)
    writer = OpenAIInteractiveResultsWriter(client)  # type: ignore[arg-type]
    with pytest.raises(ResultsWriterError) as exc:
        writer.author({}, _config(), InteractiveSettings(reasoning_effort="none"))
    assert exc.value.outcome == "api_error"
    assert str(exc.value) == (
        "Interactive Results writer request failed. exception=RuntimeError")
    receipt = writer.take_receipt()
    assert receipt is not None
    assert receipt.status is None
    assert receipt.latency_seconds is not None
    assert "first_text_ms" in receipt.usage

    client = Client(None, "different runtime failure")
    writer = OpenAIInteractiveResultsWriter(client)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="different runtime failure"):
        writer.author({}, _config(), InteractiveSettings(reasoning_effort="none"))

    # Exercise the real Results runner: a clean SDK EOF becomes a saved,
    # unavailable attempt instead of escaping before an artifact is returned.
    artifact = run_interactive_results(
        _projection(), _config(), InteractiveSettings(reasoning_effort="low"),
        OpenAIInteractiveResultsWriter(Client(None, eof_message)),  # type: ignore[arg-type]
        packet_profile="joined-v3")
    assert artifact.generation_outcome == "api_error"
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.attempts[0].writer_receipt is not None
    assert artifact.attempts[0].writer_receipt.status is None


def test_api_error_message_keeps_only_safe_diagnostics() -> None:
    class FailedRequest(Exception):
        status_code = 429

        def __init__(self, message: str) -> None:
            super().__init__(message)
            self.body = {"error": {"code": "rate_limit_exceeded",
                                   "message": "private secret"}}

    assert _safe_api_error_message(FailedRequest("private secret")) == (
        "Interactive Results writer request failed. exception=FailedRequest "
        "status=429 code=rate_limit_exceeded")

    class UnsafeRequest(Exception):
        status_code = "429 private"
        code = "private secret"

    assert _safe_api_error_message(UnsafeRequest("private secret")) == (
        "Interactive Results writer request failed. exception=UnsafeRequest")
