"""Offline controls for the explicitly invoked structured Results campaign."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsWriterError,
    WriterReceipt,
)
from award_agent.results.structured import prepare_structured_results
from award_agent.results.structured_contracts import StructuredDocument, StructuredPreparedInput

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_structured_results_eval.py"
_SPEC = importlib.util.spec_from_file_location("structured_results_eval", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class FakeMeasurer:
    def __init__(self) -> None:
        self.calls = 0

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        self.calls += 1
        return InputTokenReceipt(request_digest="digest", input_tokens=17,
            raw_response={"object": "response.input_tokens", "input_tokens": 17})


class FailingWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.receipt: WriterReceipt | None = None

    def author(self, prepared: StructuredPreparedInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: StructuredDocument | None = None) -> StructuredDocument:
        self.calls += 1
        self.receipt = WriterReceipt(raw_response='{"raw":"structured response"}',
            status="failed", usage={"input_tokens": 17}, latency_seconds=0.5)
        raise ResultsWriterError("api_error", "writer failed")

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.receipt = self.receipt, None
        return receipt


def _sandbox_campaign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "campaign"
    root.mkdir()
    source = Path(__file__).resolve().parents[2] / (
        "evidence/results-stage/m2/structured/2026-10-24-luna/campaign.json")
    (root / "campaign.json").write_bytes(source.read_bytes())
    monkeypatch.setattr(_MODULE, "ROOT", root)
    return root


def test_offline_case_prepares_saved_evidence_without_calling_or_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _sandbox_campaign(tmp_path, monkeypatch)
    monkeypatch.setattr(_MODULE, "OpenAIResultsInputMeasurer",
                        lambda: pytest.fail("offline case created a token measurer"))
    monkeypatch.setattr(_MODULE, "OpenAIStructuredResultsWriter",
                        lambda: pytest.fail("offline case created a model writer"))

    summary = _MODULE.run_case("admitted", 1, live=False)

    assert summary["mode"] == "offline"
    assert summary["eligible_candidates"] == 258
    assert summary["input_bytes"] > 0
    assert sorted(path.name for path in root.iterdir()) == ["campaign.json"]


def test_call_reservation_is_immutable_and_stops_at_budget(tmp_path: Path) -> None:
    _MODULE.reserve_call(tmp_path, "generation", 1, "admitted", 1)
    receipt = tmp_path / "calls/generation-001.json"
    before = receipt.read_bytes()

    with pytest.raises(ValueError, match="limit reached"):
        _MODULE.reserve_call(tmp_path, "generation", 1, "conditional", 2)

    assert receipt.read_bytes() == before
    assert json.loads(before) == {"kind": "generation", "case": "admitted",
        "round": 1, "status": "reserved_before_invocation"}


def test_recording_measurer_saves_request_and_receipt_and_budget_blocks_delegate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _sandbox_campaign(tmp_path, monkeypatch)
    call_dir = tmp_path / "case"
    call_dir.mkdir()
    delegate = FakeMeasurer()
    recorder = _MODULE.RecordingMeasurer(delegate, call_dir, "admitted", 1, 1)
    config = ResultsConfig(model="offline-test", max_output_tokens=100,
        timeout_seconds=10, context_limit_tokens=1000, prompt_overhead_tokens=0)
    request: dict[str, object] = {"model": "offline-test", "instructions": "write", "input": "{}"}

    receipt = recorder.measure(request, config)

    assert receipt.input_tokens == 17
    assert json.loads((call_dir / "01-request.json").read_text()) == request
    assert json.loads((call_dir / "01-count.json").read_text()) == receipt.model_dump(mode="json")
    assert delegate.calls == 1

    blocked_delegate = FakeMeasurer()
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    blocked = _MODULE.RecordingMeasurer(blocked_delegate, blocked_dir, "conditional", 2, 1)
    with pytest.raises(ValueError, match="limit reached"):
        blocked.measure(request, config)
    assert blocked_delegate.calls == 0
    assert len(list((root / "calls").glob("count-*.json"))) == 1


def test_recording_writer_saves_raw_receipt_even_when_writer_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _sandbox_campaign(tmp_path, monkeypatch)
    call_dir = tmp_path / "case"
    call_dir.mkdir()
    delegate = FailingWriter()
    writer = _MODULE.RecordingWriter(delegate, call_dir, "incomplete", 1, 1)
    config = ResultsConfig(model="offline-test", max_output_tokens=100,
        timeout_seconds=10, context_limit_tokens=1000, prompt_overhead_tokens=0)
    projection = SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())
    prepared = prepare_structured_results(projection, config)

    with pytest.raises(ResultsWriterError, match="writer failed"):
        writer.author(prepared, config)
    receipt = writer.take_receipt()

    assert delegate.calls == 1
    assert receipt is not None
    assert receipt.raw_response == '{"raw":"structured response"}'
    assert json.loads((call_dir / "01-writer.json").read_text()) == receipt.model_dump(mode="json")
    assert len(list((tmp_path / "campaign/calls").glob("generation-*.json"))) == 1
