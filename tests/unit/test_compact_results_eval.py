"""Offline checks for the bounded compact Results evaluation harness."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from award_agent.results import ResultsConfig
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    PreparedResultsInput,
    ResultsDocument,
    ResultsWriterError,
    WriterReceipt,
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/run_compact_results_eval.py"
_SPEC = importlib.util.spec_from_file_location("compact_results_eval", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_MEASURE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/measure_results_authoring.py"
_MEASURE_SPEC = importlib.util.spec_from_file_location("measure_results_authoring", _MEASURE_SCRIPT)
assert _MEASURE_SPEC is not None and _MEASURE_SPEC.loader is not None
_MEASURE_MODULE = importlib.util.module_from_spec(_MEASURE_SPEC)
_MEASURE_SPEC.loader.exec_module(_MEASURE_MODULE)
_shorten_hash_ids = _MEASURE_MODULE._shorten_hash_ids
_filter_rejected_alternatives = _MEASURE_MODULE._filter_rejected_alternatives
_expand_compact_groups = _MEASURE_MODULE._expand_compact_groups
FIXED_SETTINGS = _MODULE.FIXED_SETTINGS
RecordingMeasurer = _MODULE.RecordingMeasurer
RecordingWriter = _MODULE.RecordingWriter
_validate_live_config = _MODULE._validate_live_config
_case_has_attempt_evidence = _MODULE._case_has_attempt_evidence


class FakeMeasurer:
    def __init__(self) -> None:
        self.calls = 0

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        self.calls += 1
        return InputTokenReceipt(request_digest=f"request-{self.calls}", input_tokens=17,
                                 raw_response={"object": "response.input_tokens",
                                               "input_tokens": 17})


class FakeWriter:
    def __init__(self) -> None:
        self.receipt: WriterReceipt | None = None

    def author(
        self,
        prepared: PreparedResultsInput,
        config: ResultsConfig,
        feedback: tuple[CheckFinding, ...] = (),
        previous_document: ResultsDocument | None = None,
    ) -> ResultsDocument:
        self.receipt = WriterReceipt(raw_response='{"raw":"writer response"}', status="failed",
                                     usage={"input_tokens": 17}, latency_seconds=0.5)
        raise ResultsWriterError("api_error", "writer failed")

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.receipt = self.receipt, None
        return receipt


def test_recording_measurer_saves_exact_request_and_receipt(tmp_path: Path) -> None:
    delegate = FakeMeasurer()
    recorder = RecordingMeasurer(delegate, tmp_path)
    config = ResultsConfig.model_validate_json(
        (Path(__file__).resolve().parents[2] /
         "evidence/end-to-end/presentation/iterations/006/config.json").read_text())
    request = {"model": "gpt-6-luna", "instructions": "write", "input": "{}",
               "text": {"format": {"strict": True}}}

    receipt = recorder.measure(request, config)

    saved_path = Path(str(recorder.records[0]["request_path"]))
    assert json.loads(saved_path.read_text()) == request
    assert recorder.records[0]["phase"] == "initial"
    assert recorder.records[0]["input_tokens"] == 17
    assert receipt.input_tokens == 17
    assert delegate.calls == 1


def test_recording_writer_persists_raw_receipt_when_authoring_fails(tmp_path: Path) -> None:
    delegate = FakeWriter()
    writer = RecordingWriter(delegate, tmp_path)
    config_path = Path(__file__).resolve().parents[2] / (
        "evidence/end-to-end/presentation/iterations/006/config.json")
    config = ResultsConfig.model_validate_json(config_path.read_text())
    prepared = PreparedResultsInput(source_digest="digest", source={}, slots={}, instructions="",
                                    input_bytes=0, estimated_input_tokens=0,
                                    estimated_total_tokens=0)

    with pytest.raises(ResultsWriterError):
        writer.author(prepared, config)
    receipt = writer.take_receipt()

    assert receipt is not None
    saved = tmp_path / "01-initial-writer-receipt.json"
    assert json.loads(saved.read_text())["raw_response"] == '{"raw":"writer response"}'
    assert writer.records[0]["receipt"]["usage"] == {"input_tokens": 17}


def test_partial_request_artifact_prevents_case_rerun(tmp_path: Path) -> None:
    case_dir = tmp_path / "admitted"
    case_dir.mkdir()
    (case_dir / "01-initial-request.json").write_text("{}")

    assert _case_has_attempt_evidence(case_dir)


def test_live_settings_are_fixed_to_requested_luna_configuration() -> None:
    source_config = Path(__file__).resolve().parents[2] / (
        "evidence/end-to-end/presentation/iterations/006/config.json")
    config = ResultsConfig.model_validate_json(source_config.read_text()).model_copy(
        update={"model": FIXED_SETTINGS["model"]})

    assert _validate_live_config(config) == config
    with pytest.raises(ValueError, match="max_output_tokens"):
        _validate_live_config(config.model_copy(update={"max_output_tokens": 1024}))


def test_counterfactual_measurements_are_structural_and_isolated() -> None:
    opaque_id = "a" * 64
    baseline_request: dict[str, object] = {
        "model": "gpt-6-luna",
        "instructions": "Use " + opaque_id,
        "input": json.dumps({"prepared": {"source": {"alternatives": [
            {"status": "admitted", "candidate": opaque_id},
            {"status": "rejected", "candidate": "b" * 64},
        ]}}}),
    }

    short_ids, identifier_count = _shorten_hash_ids(baseline_request)
    filtered, removed = _filter_rejected_alternatives(baseline_request)
    compact_request: dict[str, object] = {"input": json.dumps({"prepared": {"view": {
        "journeys": [{"facts": {"route": "SFO-BKK"}, "members": [
            {"ref": "J1"}, {"ref": "J2"}]}],
        "components": [{"facts": {"program": "Example"}, "members": [{"ref": "A1"}]}],
    }}})}
    ungrouped, grouping = _expand_compact_groups(compact_request)

    assert identifier_count == 2
    assert len(_MEASURE_MODULE._json_bytes(short_ids)) < len(
        _MEASURE_MODULE._json_bytes(baseline_request))
    assert removed == 1
    assert len(json.loads(filtered["input"])['prepared']['source']['alternatives']) == 1
    assert grouping["journeys_groups_expanded"] == 1
    assert grouping["journeys_after"] == 2
    assert len(_MEASURE_MODULE._json_bytes(ungrouped)) > len(
        _MEASURE_MODULE._json_bytes(compact_request))
