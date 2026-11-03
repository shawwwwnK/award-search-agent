"""Run one isolated, bounded category-led Luna evaluation on a saved projection.

Without --live, inspect the source and request identity only. A live run reserves
before each exact API request, retains all responses and failures, and replays the
saved artifact without new calls. Old campaign files are never read or changed.
"""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import ledger

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCES = HERE / "sources.json"
CONFIG = REPO / "data/results/fast-default.json"
RECOVERY_GUIDANCE = HERE / "recovery-guidance.txt"
RUNS = HERE / "runs"


def _digest(value: object) -> str:
    from award_agent.providers.contracts import content_digest

    return content_digest(value)


def source_registry() -> dict[str, dict[str, str]]:
    value = ledger.read_json(SOURCES)
    if value.get("contract") != "results-category-sources-v1":
        raise ValueError("unknown category source registry")
    return value["cases"]


def source_path(case: str) -> Path:
    row = source_registry().get(case)
    if row is None:
        raise ValueError(f"unknown case: {case}")
    path = (REPO / row["path"]).resolve()
    if not path.is_relative_to(REPO) or not path.is_file():
        raise ValueError("source path escapes repository or is unavailable")
    return path


def projection_for(case: str) -> Any:
    return projection_from_bytes(case, source_path(case).read_bytes())


def projection_from_bytes(case: str, data: bytes) -> Any:
    from award_agent.ranking.projection_contracts import SolutionProjection
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    row = source_registry()[case]
    if row["kind"] == "ranking_projection":
        return SolutionProjection.model_validate_json(data)
    if row["kind"] == "structured_artifact":
        return StructuredResultsArtifact.model_validate_json(data).evidence.source
    raise ValueError("unknown source kind")


def snapshot_paths(case: str) -> list[Path]:
    paths = [Path(__file__), HERE / "ledger.py", HERE / "freeze.py",
             HERE / "verify.py", HERE / "review_bundle.py",
             HERE / "preview_loader.py",
             HERE / "test_verify.py", HERE / "sources.json", HERE / "campaign.json",
             HERE / "reviewer-instructions.md", HERE / "preview.py",
             RECOVERY_GUIDANCE,
             source_path(case), CONFIG,
             REPO / "src/award_agent/cli/results.py",
             *sorted((REPO / "tests/unit").glob("test_results_category*.py")),
             *sorted((REPO / "src/award_agent/results").glob("*.py"))]
    return paths


def snapshot_hashes(case: str) -> dict[str, str]:
    return {str(path.relative_to(REPO)): ledger.sha256(path)
            for path in snapshot_paths(case)}


class RecordingMeasurer:
    def __init__(self, delegate: Any, directory: Path, campaign: dict[str, Any]) -> None:
        self.delegate, self.directory, self.campaign = delegate, directory, campaign
        self.index = 0

    def measure(self, request: dict[str, object], config: Any) -> Any:
        self.index += 1
        folder = self.directory / f"pass-{self.index:02d}"
        digest = _digest(request)
        ledger.write_new(folder / "count-request.json", request)
        ledger.reserve("count", self.campaign, run=self.directory.name,
                       label=folder.name, digest=digest)
        started = time.perf_counter()
        try:
            receipt = self.delegate.measure(request, config)
            ledger.write_new(folder / "count-receipt.json", receipt.model_dump(mode="json"))
            return receipt
        except Exception as exc:
            ledger.write_new(folder / "count-error.json", {
                "type": type(exc).__name__, "request_digest": digest})
            raise
        finally:
            ledger.write_new(folder / "count-timing.json", {
                "full_response_seconds": time.perf_counter() - started})


class RecordingWriter:
    def __init__(self, delegate: Any, directory: Path, campaign: dict[str, Any]) -> None:
        self.delegate, self.directory, self.campaign = delegate, directory, campaign
        self.index = 0
        self._receipt: Any = None

    def author(self, request: dict[str, object], config: Any, settings: Any) -> str:
        self.index += 1
        folder = self.directory / f"pass-{self.index:02d}"
        body = dict(request, max_output_tokens=config.max_output_tokens,
                    store=False, truncation="disabled", stream=True)
        if settings.service_tier == "fast":
            body["service_tier"] = "fast"
        digest = _digest(body)
        ledger.write_new(folder / "generation-request.json", body)
        ledger.reserve("generation", self.campaign, run=self.directory.name,
                       label=folder.name, digest=digest)
        started = time.perf_counter()
        error: Exception | None = None
        try:
            output = self.delegate.author(request, config, settings)
            ledger.write_new(folder / "output-text.json", output)
            return output
        except Exception as exc:
            error = exc
            raise
        finally:
            self._receipt = self.delegate.take_receipt()
            receipt = self._receipt
            raw = None
            if receipt is not None:
                ledger.write_new(folder / "writer-receipt.json", receipt.model_dump(mode="json"))
                try:
                    raw = json.loads(receipt.raw_response) if receipt.raw_response else None
                except ValueError:
                    pass
            if isinstance(raw, dict):
                ledger.write_new(folder / "raw-response.json", raw)
            ledger.write_new(folder / "generation-timing.json", {
                "full_response_seconds": time.perf_counter() - started,
                "returned_service_tier": raw.get("service_tier") if isinstance(raw, dict) else None,
                "usage": raw.get("usage") if isinstance(raw, dict) else None,
                "first_event_ms": receipt.usage.get("first_event_ms") if receipt else None,
                "first_text_ms": receipt.usage.get("first_text_ms") if receipt else None,
                "status": receipt.status if receipt else None})
            if error is not None:
                ledger.write_new(folder / "generation-error.json", {
                    "type": type(error).__name__, "request_digest": digest,
                    "receipt_available": receipt is not None})

    def take_receipt(self) -> Any:
        result, self._receipt = self._receipt, None
        return result


def _candidate(value: str) -> str:
    if (not value.startswith("category-c") or len(value) != 12 or
            not value[-2:].isdigit() or not 1 <= int(value[-2:]) <= 20):
        raise ValueError("candidate must be category-c01 through category-c20")
    return value


def run(case: str, name: str, candidate: str, *, live: bool = False,
        manifest: Path | None = None,
        recovery_diagnostic: bool = False) -> dict[str, object]:
    _candidate(candidate)
    path = source_path(case)
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("invalid run name")
    if recovery_diagnostic and manifest is not None:
        raise ValueError("controlled recovery is separate from frozen confirmation")
    if not live:
        projection = projection_for(case)
        return {"case": case, "candidate": candidate, "mode": "offline",
                "source_sha256": ledger.sha256(path),
                "source_digest": projection.receipt.source_digest,
                "view_digest": projection.receipt.view_digest, "live_calls": 0}
    with ledger.locked_campaign():
        return _run_live(case, name, candidate, manifest, recovery_diagnostic)


def _run_live(case: str, name: str, candidate: str,
              manifest: Path | None, recovery_diagnostic: bool) -> dict[str, object]:
    from dotenv import load_dotenv
    from openai import OpenAI

    from award_agent.results.adapter import OpenAIResultsInputMeasurer
    from award_agent.results.category import replay_category_results, run_category_results
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter

    settings = ledger.campaign()
    if settings["status"] not in {"preparing", "active"}:
        raise ValueError("campaign is stopped")
    ledger.require_headroom(settings)
    config = ResultsConfig.model_validate_json(CONFIG.read_bytes())
    if (config.model != settings["model"] or
            config.max_output_tokens != settings["max_output_tokens"] or
            config.timeout_seconds != settings["timeout_seconds"]):
        raise ValueError("live configuration differs from campaign controls")
    if recovery_diagnostic:
        original = config.authoring_guidance or ""
        config = config.model_copy(update={"authoring_guidance":
            original + "\n" + RECOVERY_GUIDANCE.read_text(encoding="utf-8")})
    frozen = snapshot_hashes(case)
    if manifest is not None:
        declared = ledger.read_json(manifest)
        matches = [row for row in declared.get("runs", []) if row.get("name") == name]
        if (len(matches) != 1 or matches[0].get("case") != case or
                matches[0].get("candidate") != candidate or
                matches[0].get("snapshot_hashes") != frozen):
            raise ValueError("run differs from frozen manifest")
    directory = RUNS / name
    directory.mkdir(parents=True, exist_ok=False)
    ledger.write_new(directory / "source-snapshot.json", frozen)
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshot_paths(case):
            archive.write(path, str(path.relative_to(REPO)))
    if manifest is not None:
        (directory / "manifest.json").write_bytes(manifest.read_bytes())
    ledger.write_new(directory / "settings.json", {
        "case": case, "candidate": candidate,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": ledger.sha256(source_path(case)),
        "source_digest": projection_for(case).receipt.source_digest,
        "view_digest": projection_for(case).receipt.view_digest,
        "config_sha256": ledger.sha256(CONFIG),
        "campaign_sha256": ledger.sha256(ledger.CAMPAIGN),
        "manifest_sha256": ledger.sha256(manifest) if manifest else None,
        "recovery_diagnostic": recovery_diagnostic,
        "expected_fault_code": "visible_internal_alias" if recovery_diagnostic else None,
        "model": settings["model"], "max_output_tokens": settings["max_output_tokens"],
        "timeout_seconds": settings["timeout_seconds"], "max_retries": 0})
    stage = "parse_source"
    started = time.perf_counter()
    try:
        projection = projection_for(case)
        load_dotenv(REPO / ".env")
        stage = "run_category_results"
        with OpenAI(max_retries=0, timeout=settings["timeout_seconds"]) as client:
            writer = RecordingWriter(OpenAIInteractiveResultsWriter(client), directory, settings)
            measurer = RecordingMeasurer(OpenAIResultsInputMeasurer(client), directory, settings)
            artifact = run_category_results(projection, config, writer, measurer,
                                            profile=candidate)
        elapsed = time.perf_counter() - started
        stage = "persist"
        ledger.write_new(directory / "artifact.json", artifact.model_dump(mode="json"))
        post_hashes = snapshot_hashes(case)
        drifted = sorted(name for name in set(frozen) | set(post_hashes)
                         if frozen.get(name) != post_hashes.get(name))
        ledger.write_new(directory / "post-run-source-check.json", {
            "snapshot_drift": bool(drifted), "changed_paths": drifted,
            "checked_at_utc": datetime.now(UTC).isoformat()})
        if artifact.resolved is not None:
            ledger.write_new(directory / "resolved.json", artifact.resolved.model_dump(mode="json"))
            from preview import render_html, render_markdown

            (directory / "answer-preview.md").write_text(render_markdown(artifact),
                                                            encoding="utf-8")
            (directory / "answer-preview.html").write_text(render_html(artifact),
                                                              encoding="utf-8")
        selected_index = getattr(artifact, "selected_pass_index", None)
        selected_findings = (artifact.passes[selected_index].findings
                             if selected_index is not None else ())
        summary = {
            "case": case, "candidate": candidate, "mode": "live",
            "recovery_diagnostic": recovery_diagnostic,
            "outer_results_completion_seconds": elapsed,
            "timing_scope": "Saved source parse through checked/resolved Results artifact before disk persistence and offline replay.",
            "artifact_runtime_seconds": artifact.runtime_seconds,
            "count_calls": measurer.index, "generation_calls": writer.index,
            "passes": [{"phase": item.phase, "outcome": item.outcome,
                        "writer_called": item.writer_called,
                        "returned_service_tier": item.returned_service_tier,
                        "input_tokens": item.input_token_receipt.input_tokens
                            if item.input_token_receipt else None,
                        "usage": json.loads(item.writer_receipt.raw_response).get("usage")
                            if item.writer_receipt and item.writer_receipt.raw_response else None}
                       for item in artifact.passes],
            "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "selection_failed_findings": [f.model_dump(mode="json")
                for f in artifact.selection_findings if f.outcome == "failed"],
            "selected_pass_index": selected_index,
            "failed_findings": [f.model_dump(mode="json") for f in selected_findings
                                if f.outcome == "failed"],
            "diagnostic_fault_observed": recovery_diagnostic and len(artifact.passes) > 1
                and any(f.code == "visible_internal_alias" and f.outcome == "failed"
                        for f in artifact.passes[1].findings),
            "source_sha256": ledger.sha256(source_path(case)),
            "snapshot_drift": bool(drifted),
            "live_calls": measurer.index + writer.index}
        ledger.write_new(directory / "summary.json", summary)
        stage = "offline_replay"
        replayed = replay_category_results(artifact)
        same = replayed == artifact.resolved
        ledger.write_new(directory / "verification-receipt.json", {
            "verification": "replay_category_results", "passed": same,
            "resolved_matches": same, "live_calls": 0})
        if not same:
            raise ValueError("offline replay differs")
        return summary
    except Exception as exc:
        ledger.write_new(directory / "run-error.json", {
            "type": type(exc).__name__, "stage": stage,
            "elapsed_seconds": time.perf_counter() - started,
            "source_sha256": ledger.sha256(source_path(case))})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(source_registry()), required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--recovery-diagnostic", action="store_true")
    args = parser.parse_args()
    result = run(args.case, args.name, args.candidate, live=args.live,
                 manifest=args.manifest,
                 recovery_diagnostic=args.recovery_diagnostic)
    print(json.dumps(result, indent=2))
    return 0 if not args.live or result["delivery_outcome"] == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
