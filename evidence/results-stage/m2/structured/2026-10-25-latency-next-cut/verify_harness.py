"""Offline controls for the isolated experiment runner. No API credentials needed."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Self

import harness
import httpx

from award_agent.providers.contracts import content_digest
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsWriterError,
)
from award_agent.results.runner import RequestEnvelope, run_attempts


def config() -> ResultsConfig:
    return ResultsConfig(model="gpt-6-luna", max_output_tokens=1024,
        timeout_seconds=7.0, context_limit_tokens=100000,
        prompt_overhead_tokens=0)


class FakeResponse:
    output_text = '{"findings":[]}'

    def __init__(self, status: str = "completed", refusal: bool = False) -> None:
        self.status, self.refusal = status, refusal

    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return {"status": self.status,
            "output": ([{"type": "message", "content": [{"type": "refusal"}]}]
                       if self.refusal else []),
            "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
                      "input_tokens_details": {"cached_tokens": 0}},
            "reasoning": {"effort": "low"}}


class FakeStream:
    def __init__(self, response: FakeResponse, *, timeout_during_events: bool = False) -> None:
        self.response = response
        self.timeout_during_events = timeout_during_events

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def __iter__(self):
        yield SimpleNamespace(type="response.created", response=None)
        yield SimpleNamespace(type="response.output_text.delta", response=None)
        if self.timeout_during_events:
            raise httpx.ReadTimeout("simulated stalled SSE stream")
        yield SimpleNamespace(type="response.completed", response=self.response)


class FakeClient:
    def __init__(self) -> None:
        self.options: list[dict[str, object]] = []
        self.posts: list[dict[str, object]] = []
        self.generations: list[dict[str, object]] = []
        self.responses = self
        self.raw_count: dict[str, object] = {
            "object": "response.input_tokens", "input_tokens": 10}
        self.response = FakeResponse()
        self.timeout_during_events = False

    def with_options(self, **kwargs: object) -> FakeClient:
        self.options.append(kwargs)
        return self

    def post(self, _path: str, *, body: dict[str, object], cast_to: object):
        self.posts.append(body)
        return self.raw_count

    def create(self, **kwargs: object) -> FakeStream:
        self.generations.append(kwargs)
        return FakeStream(self.response,
                          timeout_during_events=self.timeout_during_events)


def endpoint_controls() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        original = harness.HERE
        harness.HERE = root
        try:
            fake = FakeClient()
            endpoint = harness.Endpoint(root / "run", {
                "maximum_input_count_calls": 1,
                "maximum_generation_calls": 1,
            }, config(), fake)  # type: ignore[arg-type]
            request = {"model": "gpt-6-luna", "input": "{}",
                "instructions": "Test", "reasoning": {"effort": "low"},
                "text": {"format": {"type": "json_object"}}}
            receipt = endpoint.count(request, "first")
            text, writer_receipt = endpoint.generate(request, "first", max_output_tokens=1024)
            assert receipt.request_digest == content_digest(request)
            assert writer_receipt.usage["input_tokens"] == 10
            assert json.loads(text) == {"findings": []}
            assert fake.posts == [request]
            assert fake.generations[0]["reasoning"] == request["reasoning"]
            assert all(option == {"max_retries": 0, "timeout": 7.0}
                       for option in fake.options)
            assert (root / "calls/count-001.json").exists()
            assert (root / "calls/generation-001.json").exists()
            reservation = json.loads((root / "calls/count-001.json").read_text())
            assert reservation["run_name"] == "run"
            assert reservation["request_digest"] == content_digest(request)
            assert (root / "run/first/generation-timing.json").exists()
            assert (root / "run/first/count-timing.json").exists()
            try:
                endpoint.count(request, "second")
            except ValueError as exc:
                assert "bound exhausted" in str(exc)
            else:
                raise AssertionError("second count bypassed campaign bound")
            assert not fake.posts[1:]
        finally:
            harness.HERE = original


def invalid_endpoint_controls() -> None:
    request = {"model": "gpt-6-luna", "input": "{}",
        "instructions": "Test", "reasoning": {"effort": "low"},
        "text": {"format": {"type": "json_object"}}}
    for invalid in (True, -1, "10", None):
        with tempfile.TemporaryDirectory() as temp:
            original = harness.HERE
            harness.HERE = Path(temp)
            try:
                fake = FakeClient()
                fake.raw_count["input_tokens"] = invalid
                endpoint = harness.Endpoint(Path(temp) / "run", {
                    "maximum_input_count_calls": 1,
                    "maximum_generation_calls": 1}, config(), fake)  # type: ignore[arg-type]
                try:
                    endpoint.count(request, "invalid")
                except ResultsWriterError:
                    pass
                else:
                    raise AssertionError(f"invalid count accepted: {invalid!r}")
                assert (Path(temp) / "run/invalid/count-error.json").exists()
            finally:
                harness.HERE = original
    for response, outcome in ((FakeResponse("incomplete"), "incomplete"),
                              (FakeResponse(refusal=True), "refusal")):
        with tempfile.TemporaryDirectory() as temp:
            original = harness.HERE
            harness.HERE = Path(temp)
            try:
                fake = FakeClient()
                fake.response = response
                endpoint = harness.Endpoint(Path(temp) / "run", {
                    "maximum_input_count_calls": 1,
                    "maximum_generation_calls": 1}, config(), fake)  # type: ignore[arg-type]
                try:
                    endpoint.generate(request, "invalid", max_output_tokens=1024)
                except ResultsWriterError as exc:
                    assert exc.outcome == outcome
                else:
                    raise AssertionError(f"{outcome} response accepted")
                assert (Path(temp) / "run/invalid/response.json").exists()
            finally:
                harness.HERE = original


def stalled_stream_control() -> None:
    request = {"model": "gpt-6-luna", "input": "{}",
        "instructions": "Test", "reasoning": {"effort": "low"},
        "text": {"format": {"type": "json_object"}}}
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        original = harness.HERE
        harness.HERE = root
        try:
            fake = FakeClient()
            fake.timeout_during_events = True
            endpoint = harness.Endpoint(root / "run", {
                "maximum_input_count_calls": 1,
                "maximum_generation_calls": 1}, config(), fake)  # type: ignore[arg-type]
            try:
                endpoint.generate(request, "stalled", max_output_tokens=1024)
            except ResultsWriterError as exc:
                assert exc.outcome == "api_error"
            else:
                raise AssertionError("stalled SSE stream was accepted")
            error = json.loads((root / "run/stalled/generation-error.json").read_text())
            assert error["type"] == "ReadTimeout"
            assert error["first_event_seconds"] is not None
            assert error["first_text_seconds"] is not None
            assert error["events_seen"] == 2
            assert error["text_delta_events"] == 1
            assert not (root / "run/stalled/response.json").exists()
            assert (root / "calls/generation-001.json").exists()
        finally:
            harness.HERE = original


def recovery_control() -> None:
    request = {"model": "gpt-6-luna", "input": "{}",
               "instructions": "Test", "text": {"format": {"type": "json_object"}}}
    finding = CheckFinding(scope="journey", code="bad_ref", outcome="failed",
                           message="missing")
    calls = 0

    class FakeMeasurer:
        def measure(self, received: dict[str, object], _config: ResultsConfig):
            return InputTokenReceipt(request_digest=content_digest(received),
                input_tokens=10, raw_response={"object": "response.input_tokens",
                                               "input_tokens": 10})

    def invoke(_feedback: object, _previous: object) -> str:
        nonlocal calls
        calls += 1
        return f"draft-{calls}"

    outcome = run_attempts(config(), FakeMeasurer(),
        request_for=lambda _feedback, _previous: RequestEnvelope(
            request=request, input_bytes=100, estimated_total_tokens=2000,
            prompt_digest="p", schema_digest="s"),
        invoke=invoke,
        check=lambda document: (finding,) if document == "draft-1" else (),
        take_receipt=lambda: None)
    assert calls == 2
    assert outcome.selected_attempt == 1
    assert outcome.selection_reason == "correction_fewer_failures"


def worker_controls() -> None:
    class FakePrepared:
        references = SimpleNamespace(
            journeys={"J1": "one", "J2": "two"}, cash={"C1": "cash"},
            awards={"A1": "award"},
            comparison_pools={"P1": ("one", "two"), "P2": ("one",)})
    prepared = FakePrepared()
    good = {"findings": [{"refs": ["J1", "C1"], "finding": "same schedule"}]}
    assert harness.parse_worker(json.dumps(good), prepared) == good  # type: ignore[arg-type]
    bad = {"findings": [{"refs": ["J999"], "finding": "unsupported"}]}
    try:
        harness.parse_worker(json.dumps(bad), prepared)  # type: ignore[arg-type]
    except ValueError as exc:
        assert "exact references" in str(exc)
    else:
        raise AssertionError("invalid worker reference was accepted")
    pool = {"findings": [{"refs": ["P1"], "finding": "whole eligible pool"}]}
    try:
        harness.parse_worker(json.dumps(pool), prepared)  # type: ignore[arg-type]
    except ValueError:
        pass
    else:
        raise AssertionError("v1 accepted comparison-pool alias")
    assert harness.parse_worker(json.dumps(pool), prepared,
        candidate_version="v2") == pool  # type: ignore[arg-type]
    for ref in ("P2", "P999", "J1–J2", "J1,J2", "J1 J2"):
        invalid = {"findings": [{"refs": [ref], "finding": "unsupported scope"}]}
        try:
            harness.parse_worker(json.dumps(invalid), prepared,
                                 candidate_version="v2")  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"v2 accepted invalid worker reference {ref}")
    base = {"model": "gpt-6-luna", "input": "{}"}
    v1 = harness.worker_request(base, "choices", "low")
    v2 = harness.worker_request(base, "choices", "low", candidate_version="v2")
    from candidate import GUIDE
    assert v1["instructions"] == (harness.WORKER_INSTRUCTIONS["choices"] +
                                  GUIDE.split("Reference contract:", 1)[0])
    assert "Each refs array item" not in v1["instructions"]
    assert "Each refs array item" in v2["instructions"]


def versioned_request_controls() -> None:
    import candidate
    import candidate_v2

    from award_agent.results.structured import (
        prepare_structured_results,
        structured_payload,
        structured_token_request,
    )
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    source = harness.SOURCE / "admitted" / "artifact.json"
    artifact = StructuredResultsArtifact.model_validate_json(source.read_text())
    prepared = prepare_structured_results(artifact.evidence.source, config())
    original = structured_token_request(prepared, config(), structured_payload(prepared))
    expected_v1 = candidate.transform(original, prepared)
    expected_v1["reasoning"] = {"effort": "medium"}
    actual_v1 = harness.build_final_request(prepared, config(), "candidate", "medium")
    assert actual_v1 == expected_v1
    expected_v2 = candidate_v2.transform(original, prepared)
    expected_v2["reasoning"] = {"effort": "medium"}
    actual_v2 = harness.build_final_request(prepared, config(), "candidate", "medium",
                                            candidate_version="v2")
    assert actual_v2 == expected_v2
    assert actual_v2 != actual_v1


if __name__ == "__main__":
    endpoint_controls()
    invalid_endpoint_controls()
    stalled_stream_control()
    recovery_control()
    worker_controls()
    versioned_request_controls()
    print("harness offline controls passed")
