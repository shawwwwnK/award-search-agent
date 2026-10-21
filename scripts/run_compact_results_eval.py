"""Offline-default Results V5 evaluator; live calls require an explicit --live gate.

The live mode processes saved iteration 006 projections only. It never invokes
providers, retries, or selects another model, and saves each exact token-bearing
request before the next attempt. Run one case per invocation to keep the call
budget visible and easy to audit.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import cast

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, prepare_results, replay_results, run_results
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIResultsWriter
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsDocument,
    ResultsWriterError,
    WriterReceipt,
)

REPO = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO / "evidence/end-to-end/presentation/iterations/006"
OUTPUT_ROOT = REPO / "evidence/results-stage/m2/compact-input"
CASES = ("admitted", "conditional", "incomplete")
FIXED_SETTINGS = {
    "model": "gpt-6-luna",
    "max_output_tokens": 32768,
    "timeout_seconds": 600.0,
    "context_limit_tokens": 1050000,
    "max_input_tokens": 922000,
    "prompt_overhead_tokens": 2048,
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_digest(path: Path) -> str:
    return _digest(path.read_bytes())


def _write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        output.write(content)


def _write_json_new(path: Path, value: object) -> None:
    _write_new(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _source_snapshot(run_dir: Path) -> dict[str, object]:
    files = sorted((REPO / "src/award_agent/results").glob("*.py"))
    files += [REPO / "scripts/measure_results_authoring.py",
              REPO / "scripts/run_compact_results_eval.py"]
    hashes = {str(path.relative_to(REPO)): _file_digest(path) for path in files}
    archive_path = run_dir / "results-source-snapshot.zip"
    receipt_path = run_dir / "source-snapshot.json"
    if archive_path.exists() or receipt_path.exists():
        if not (archive_path.exists() and receipt_path.exists()):
            raise ValueError("partial Results source snapshot exists")
        saved = cast(dict[str, object], json.loads(receipt_path.read_text()))
        if saved.get("files") != hashes or saved.get("sha256") != _file_digest(archive_path):
            raise ValueError("Results source differs from this run's immutable snapshot")
        return saved
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(REPO)))
    receipt: dict[str, object] = {
        "sha256": _file_digest(archive_path),
        "files": hashes,
        "dependencies": {name: importlib.metadata.version(name)
                          for name in ("pydantic", "openai", "python-dotenv")},
    }
    _write_json_new(receipt_path, receipt)
    return receipt


def _git_state() -> tuple[str, list[str]]:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--short"], cwd=REPO,
                                    text=True).splitlines()
    return head, dirty


class RecordingMeasurer:
    """Capture exact requests and preserve the OpenAI measurer's real receipts."""

    def __init__(self, delegate: OpenAIResultsInputMeasurer, case_dir: Path) -> None:
        self.delegate = delegate
        self.case_dir = case_dir
        self.count = 0
        self.records: list[dict[str, object]] = []

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        if self.count >= 2:
            raise ResultsWriterError("api_error", "per-case input measurement limit reached")
        self.count += 1
        phase = "initial" if self.count == 1 else "correction"
        request_bytes = json.dumps(request, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode("utf-8")
        path = self.case_dir / f"{self.count:02d}-{phase}-request.json"
        _write_new(path, request_bytes.decode("utf-8") + "\n")
        record: dict[str, object] = {
            "phase": phase, "request_path": _display_path(path),
            "request_sha256": _digest(request_bytes),
            "request_json_bytes": len(request_bytes), "measurement_outcome": "pending",
        }
        self.records.append(record)
        try:
            receipt = self.delegate.measure(request, config)
        except Exception as error:
            record.update({"measurement_outcome": "error", "error_type": type(error).__name__,
                           "error": str(error)})
            raise
        record.update({"measurement_outcome": "counted", "input_tokens": receipt.input_tokens,
                       "receipt": receipt.model_dump(mode="json")})
        return receipt


class RecordingWriter:
    """Forward the core's receipt handoff while durably saving each raw receipt."""

    def __init__(self, delegate: OpenAIResultsWriter, case_dir: Path) -> None:
        self.delegate = delegate
        self.case_dir = case_dir
        self.author_count = 0
        self.records: list[dict[str, object]] = []

    def author(
        self,
        prepared: PreparedResultsInput,
        config: ResultsConfig,
        feedback: tuple[CheckFinding, ...] = (),
        previous_document: ResultsDocument | None = None,
    ) -> ResultsDocument:
        self.author_count += 1
        return self.delegate.author(prepared, config, feedback, previous_document)

    def take_receipt(self) -> WriterReceipt | None:
        raw = self.delegate.take_receipt()
        if raw is None:
            return None
        receipt = WriterReceipt.model_validate(raw)
        phase = "initial" if self.author_count == 1 else "correction"
        path = self.case_dir / f"{self.author_count:02d}-{phase}-writer-receipt.json"
        _write_new(path, receipt.model_dump_json(indent=2) + "\n")
        self.records.append({"phase": phase, "receipt_path": _display_path(path),
                             "receipt": receipt.model_dump(mode="json")})
        return receipt


def _validate_live_config(config: ResultsConfig) -> ResultsConfig:
    if config.model != FIXED_SETTINGS["model"]:
        raise ValueError("live compact evaluation is restricted to gpt-6-luna")
    for key, expected in FIXED_SETTINGS.items():
        actual = getattr(config, key)
        if actual != expected:
            raise ValueError(f"live config {key} must equal the approved value {expected!r}")
    return config


def _case_source(case: str) -> tuple[Path, Path]:
    case_dir = SOURCE_ROOT / case
    return case_dir / "artifact.json", case_dir / "answer.md"


def _case_has_attempt_evidence(case_dir: Path) -> bool:
    return case_dir.exists() and any(case_dir.iterdir())


def run_case(case: str, config: ResultsConfig, run_dir: Path) -> dict[str, object]:
    source_artifact_path, baseline_answer_path = _case_source(case)
    source_artifact = json.loads(source_artifact_path.read_text())
    projection_data = source_artifact.get("projection")
    if not isinstance(projection_data, dict):
        raise TypeError(f"saved source {case} has no embedded canonical projection")
    projection = SolutionProjection.model_validate(projection_data)
    case_dir = run_dir / case
    if _case_has_attempt_evidence(case_dir):
        raise ValueError(f"{case} already has attempt evidence; partial attempts cannot be rerun")
    case_dir.mkdir(parents=True, exist_ok=True)
    sources_before = {
        "source_artifact": _file_digest(source_artifact_path),
        "baseline_answer": _file_digest(baseline_answer_path),
    }
    head, dirty = _git_state()
    recorder = RecordingMeasurer(OpenAIResultsInputMeasurer(), case_dir)
    writer_recorder = RecordingWriter(OpenAIResultsWriter(), case_dir)
    artifact: ResultsArtifact | None = None
    try:
        artifact = run_results(projection, config, writer_recorder,
                               input_measurer=recorder, render_version="results-artifact-v5")
        _write_new(case_dir / "artifact.json", artifact.model_dump_json(indent=2) + "\n")
        rendered: str | None = None
        if artifact.delivery_outcome == "delivered":
            rendered = replay_results(artifact)
            _write_new(case_dir / "answer.md", rendered)
    except Exception as error:
        writer_records = writer_recorder.records
        # run_results stores a recoverable API/generation failure as an artifact.
        if artifact is not None:
            writer_records = writer_recorder.records or [
                {"phase": attempt.phase, "receipt": attempt.writer_receipt.model_dump(mode="json")}
                for attempt in artifact.attempts if attempt.writer_receipt]
        _write_json_new(case_dir / "failure.json", {
            "case": case, "error_type": type(error).__name__, "error": str(error),
            "source_hashes_before": sources_before, "git_head": head,
            "git_dirty_paths": dirty, "captured_requests": recorder.records,
            "writer_receipts": writer_records,
        })
        raise
    sources_after = {
        "source_artifact": _file_digest(source_artifact_path),
        "baseline_answer": _file_digest(baseline_answer_path),
    }
    artifact_digest = _file_digest(case_dir / "artifact.json")
    receipt = {
        "method": "bounded live Results V5 authoring on saved iteration 006 projection; no providers",
        "case": case,
        "source_artifact": str(source_artifact_path.relative_to(REPO)),
        "source_artifact_sha256": sources_before["source_artifact"],
        "baseline_answer_sha256": sources_before["baseline_answer"],
        "source_unchanged_during_call": sources_before == sources_after,
        "config_sha256": _file_digest(run_dir / "config.json"),
        "results_source_snapshot_sha256": json.loads(
            (run_dir / "source-snapshot.json").read_text())["sha256"],
        "git_head_before_call": head,
        "git_dirty_paths_before_call": dirty,
        "settings": {key: getattr(config, key) for key in FIXED_SETTINGS},
        "generation_outcome": artifact.generation_outcome,
        "validation_outcome": artifact.validation_outcome,
        "delivery_outcome": artifact.delivery_outcome,
        "attempts": [{
            "phase": attempt.phase, "outcome": attempt.outcome,
            "input_tokens": (attempt.input_token_receipt.input_tokens
                             if attempt.input_token_receipt else None),
            "writer_usage": (attempt.writer_receipt.usage if attempt.writer_receipt else None),
            "writer_status": (attempt.writer_receipt.status if attempt.writer_receipt else None),
            "writer_latency_seconds": (attempt.writer_receipt.latency_seconds
                                       if attempt.writer_receipt else None),
            "findings": {name: sum(finding.outcome == name for finding in attempt.findings)
                         for name in ("supported", "failed", "unchecked", "insufficient_evidence")},
        } for attempt in artifact.attempts],
        "captured_requests": recorder.records,
        "captured_writer_receipts": writer_recorder.records,
        "request_count": len(recorder.records),
        "artifact_sha256": artifact_digest,
        "rendered_digest": artifact.rendered_digest,
        "replay_equal": (rendered == artifact.rendered_markdown if rendered is not None else None),
    }
    _write_json_new(case_dir / "receipt.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="Explicitly enable the bounded Luna generation and token-count calls")
    parser.add_argument("--case", choices=CASES, action="append",
                        help="Saved case; live mode requires exactly one case per invocation")
    parser.add_argument("--config", type=Path, default=SOURCE_ROOT / "config.json",
                        help="Saved ResultsConfig with the iteration 006 guidance")
    args = parser.parse_args()
    selected = args.case or list(CASES)
    if args.live and len(selected) != 1:
        parser.error("live mode accepts exactly one --case per invocation")
    config = ResultsConfig.model_validate_json(args.config.read_text()).model_copy(
        update={"model": FIXED_SETTINGS["model"]})
    if args.live:
        _validate_live_config(config)
    run_dir = OUTPUT_ROOT / "2026-10-20-luna"
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "config.json"
    config_text = config.model_dump_json(indent=2) + "\n"
    if config_path.exists():
        if config_path.read_text() != config_text:
            parser.error("saved config differs from requested Luna settings/guidance; refusing to reuse evidence path")
    else:
        _write_new(config_path, config_text)
    _source_snapshot(run_dir)

    if not args.live:
        # Offline mode intentionally performs deterministic preparation/replay only.
        from award_agent.results.core import authoring_payload
        from award_agent.results.request import token_request

        reports = []
        for case in selected:
            source_path, _ = _case_source(case)
            source = json.loads(source_path.read_text())
            projection = SolutionProjection.model_validate(source["projection"])
            prepared = prepare_results(projection, config, version="results-artifact-v5")
            request = token_request(prepared, config, authoring_payload(prepared))
            body = json.dumps(request, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode("utf-8")
            reports.append({"case": case, "source_sha256": _file_digest(source_path),
                            "compact_initial_request_bytes": len(body),
                            "compact_initial_request_sha256": _digest(body),
                            "eligible_candidates": sum(item.status in {"admitted", "conditional"}
                                                        for item in projection.view.alternatives),
                            "token_count_requested": False})
        print(json.dumps({"mode": "offline", "reports": reports}, indent=2))
        return

    # Only live mode reads .env; its contents are never copied to evidence.
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO / ".env")
    except ImportError:
        pass
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is required for --live")
    receipt = run_case(selected[0], config, run_dir)
    print(json.dumps(receipt, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
