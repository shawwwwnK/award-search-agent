"""Actual interactive Results runtime confirmation runner.

Offline is the default and never constructs an OpenAI client. Live execution
uses the repository's interactive API and real OpenAI adapters.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CAMPAIGN = HERE / "campaign.json"
CASES = ("admitted", "conditional", "incomplete")

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import harness as campaign_utils


def _digest(value: object) -> str:
    from award_agent.providers.contracts import content_digest
    return content_digest(value)


def _raw(raw_response: str | None) -> dict[str, Any] | None:
    if raw_response is None:
        return None
    try:
        value = json.loads(raw_response)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_raw(folder: Path, raw_response: str) -> None:
    value = _raw(raw_response)
    campaign_utils.write_json(folder / "raw-response.json",
                              value if value is not None else {"raw_response": raw_response})


class RecordingInputMeasurer:
    """Reserve and persist the exact count request around the real measurer."""

    def __init__(self, delegate: Any, directory: Path, campaign: dict[str, Any]) -> None:
        self.delegate, self.directory, self.campaign = delegate, directory, campaign
        self.index = 0

    def measure(self, request: dict[str, object], config: Any) -> Any:
        self.index += 1
        label = f"final-{self.index:02d}"
        folder = self.directory / label
        folder.mkdir(parents=True, exist_ok=True)
        campaign_utils.write_json(folder / "count-request.json", request)
        digest = _digest(request)
        campaign_utils.reserve("count", label, self.campaign, run_name=self.directory.name,
                               request_digest=digest)
        started = time.perf_counter()
        try:
            receipt = self.delegate.measure(request, config)
        except Exception as exc:
            campaign_utils.write_json(folder / "count-error.json", {
                "type": type(exc).__name__, "elapsed_seconds": time.perf_counter() - started,
                "request_digest": digest, "receipt_available": False})
            raise
        campaign_utils.write_json(folder / "count-receipt.json", receipt.model_dump(mode="json"))
        campaign_utils.write_json(folder / "count-timing.json", {
            "full_response_seconds": time.perf_counter() - started, "request_digest": digest})
        return receipt


class RecordingInteractiveWriter:
    """Record the actual SDK body and preserve the delegate receipt exactly once."""

    def __init__(self, delegate: Any, directory: Path, campaign: dict[str, Any],
                 service_tier: str) -> None:
        self.delegate, self.directory, self.campaign = delegate, directory, campaign
        self.service_tier = service_tier
        self.index = 0
        self._receipt: Any = None

    def author(self, request: dict[str, object], config: Any, settings: Any) -> str:
        self.index += 1
        label = f"final-{self.index:02d}"
        folder = self.directory / label
        folder.mkdir(parents=True, exist_ok=True)
        sdk_body = dict(request, max_output_tokens=config.max_output_tokens,
                        store=False, truncation="disabled", stream=True)
        if self.service_tier == "fast":
            sdk_body["service_tier"] = "fast"
        campaign_utils.write_json(folder / "generation-request.json", sdk_body)
        digest = _digest(sdk_body)
        campaign_utils.reserve("generation", label, self.campaign,
                               run_name=self.directory.name, request_digest=digest)
        started = time.perf_counter()
        error: Exception | None = None
        try:
            return self.delegate.author(request, config, settings)
        except Exception as exc:
            error = exc
            raise
        finally:
            self._receipt = self.delegate.take_receipt()
            receipt = self._receipt
            if receipt is not None:
                campaign_utils.write_json(folder / "writer-receipt.json",
                                          receipt.model_dump(mode="json"))
                if receipt.raw_response is not None:
                    _write_raw(folder, receipt.raw_response)
                response = _raw(receipt.raw_response)
                usage = receipt.usage
                campaign_utils.write_json(folder / "generation-timing.json", {
                    "full_response_seconds": time.perf_counter() - started,
                    "usage": usage,
                    "first_event_ms": usage.get("first_event_ms"),
                    "first_text_ms": usage.get("first_text_ms"),
                    "requested_service_tier": self.service_tier,
                    "returned_service_tier": response.get("service_tier") if response else None,
                    "status": receipt.status})
            else:
                campaign_utils.write_json(folder / "generation-timing.json", {
                    "full_response_seconds": time.perf_counter() - started,
                    "receipt_available": False})
            if error is not None:
                campaign_utils.write_json(folder / "generation-error.json", {
                    "type": type(error).__name__, "elapsed_seconds": time.perf_counter() - started,
                    "request_digest": digest, "receipt_available": receipt is not None})

    def take_receipt(self) -> Any:
        receipt, self._receipt = self._receipt, None
        return receipt


def _preview(resolved: Any) -> str:
    rows = []
    for block in resolved.blocks:
        rows.append(block.text)
        if block.kind == "reference":
            rows.append(f"[Display: {block.label}; {block.reference_kind}; {block.canonical_id}]")
    return "\n\n".join(rows) + "\n"


def _usage_summary(artifact: Any) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows: list[dict[str, object]] = []
    fields = ("input_tokens", "cached_input_tokens", "output_tokens",
              "reasoning_tokens", "total_tokens")
    totals: dict[str, int | None] = {key: 0 for key in fields}
    observed = {key: False for key in fields}
    for number, attempt in enumerate(artifact.attempts, 1):
        receipt = attempt.writer_receipt
        response = _raw(receipt.raw_response if receipt else None)
        usage = response.get("usage") if response else None
        input_details = (usage.get("input_tokens_details") or {}) if isinstance(usage, dict) else {}
        output_details = (usage.get("output_tokens_details") or {}) if isinstance(usage, dict) else {}
        metrics = {
            "service_tier": response.get("service_tier") if response else None,
            "input_tokens": usage.get("input_tokens") if isinstance(usage, dict) else None,
            "cached_input_tokens": input_details.get("cached_tokens")
                if isinstance(input_details, dict) else None,
            "output_tokens": usage.get("output_tokens") if isinstance(usage, dict) else None,
            "reasoning_tokens": output_details.get("reasoning_tokens")
                if isinstance(output_details, dict) else None,
            "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
            "raw_usage": usage,
        }
        rows.append({
            "attempt": number, "phase": attempt.phase, "outcome": attempt.outcome,
            "writer_called": attempt.writer_called,
            "input_token_receipt": attempt.input_token_receipt.model_dump(mode="json")
                if attempt.input_token_receipt else None,
            "writer_receipt": receipt.model_dump(mode="json") if receipt else None,
            "actual_response_usage": metrics if response else None,
            "returned_service_tier": attempt.returned_service_tier,
            "error": attempt.error, "failure_subtype": attempt.failure_subtype,
        })
        for key in fields:
            value = metrics[key]
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] = (totals[key] or 0) + value
                observed[key] = True
    for key in fields:
        if not observed[key]:
            totals[key] = None
    return rows, {"generation_usage_totals": totals,
                  "usage_attempt_count": sum(row["actual_response_usage"] is not None
                                             for row in rows)}


def run(case: str, effort: str, name: str, *, live: bool,
        service_tier: str = "standard",
        packet_profile: str = "indexed-v1") -> dict[str, object]:
    if case not in CASES or effort not in {"none", "low", "medium"}:
        raise ValueError("unknown case or effort")
    if service_tier not in {"standard", "fast"}:
        raise ValueError("unknown service tier")
    if packet_profile not in {"indexed-v1", "joined-v2", "joined-v3", "joined-v4"}:
        raise ValueError("unknown packet profile")
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("name must contain only letters, digits, - or _")
    source_path, config_path = SOURCE / case / "artifact.json", SOURCE / case / "config.json"
    if not live:
        return {"case": case, "effort": effort, "service_tier": service_tier,
                "packet_profile": packet_profile,
                "mode": "offline", "live_calls": 0}

    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    if campaign.get("maximum_generation_calls") != 48 or \
            campaign.get("maximum_input_count_calls") != 48:
        raise ValueError("campaign must declare exact 48/48 ceilings")
    campaign_utils.require_two_attempt_headroom(campaign)
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)

    from award_agent.results.adapter import OpenAIResultsInputMeasurer
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.interactive import replay_interactive_results, run_interactive_results
    from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter
    from award_agent.results.interactive_contracts import InteractiveSettings
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    runtime_files = sorted((REPO / "src/award_agent/results").glob("*.py"))
    snapshot_paths = [Path(__file__), HERE / "harness.py", CAMPAIGN, source_path,
                      config_path, REPO / "src/award_agent/cli/results.py", *runtime_files]
    source_hash, config_hash = campaign_utils.sha256(source_path), campaign_utils.sha256(config_path)
    campaign_utils.write_json(directory / "settings.json", {
        "case": case, "effort": effort, "service_tier": service_tier,
        "packet_profile": packet_profile,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": source_hash, "config_sha256": config_hash,
        "runner_sha256": campaign_utils.sha256(Path(__file__)),
        "campaign_sha256": campaign_utils.sha256(CAMPAIGN),
        "max_output_tokens": 8192, "timeout_seconds": 240, "max_retries": 0})
    campaign_utils.write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): campaign_utils.sha256(path) for path in snapshot_paths})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshot_paths:
            archive.write(path, str(path.relative_to(REPO)))

    stage = "load_dotenv"
    outer_started: float | None = None
    try:
        load_dotenv(REPO / ".env")
        outer_started = time.perf_counter()
        stage = "parse_saved_artifact_and_config"
        source_artifact = StructuredResultsArtifact.model_validate_json(
            source_path.read_text(encoding="utf-8"))
        base_config = ResultsConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
        config = base_config.model_copy(update={"model": "gpt-6-luna",
            "max_output_tokens": 8192, "timeout_seconds": 240.0})
        settings = InteractiveSettings(reasoning_effort=effort, service_tier=service_tier)
        projection = source_artifact.evidence.source
        stage = "interactive_results"
        client = OpenAI(max_retries=0, timeout=240)
        writer = RecordingInteractiveWriter(OpenAIInteractiveResultsWriter(client),
                                            directory, campaign, service_tier)
        measurer = RecordingInputMeasurer(OpenAIResultsInputMeasurer(client), directory, campaign)
        artifact = run_interactive_results(projection, config, settings, writer, measurer,
                                           packet_profile=packet_profile)
        outer_elapsed = time.perf_counter() - outer_started

        stage = "persist"
        campaign_utils.write_json(directory / "artifact.json", artifact.model_dump(mode="json"))
        if artifact.resolved is not None:
            campaign_utils.write_json(directory / "resolved.json",
                                      artifact.resolved.model_dump(mode="json"))
            (directory / "answer-preview.md").write_text(_preview(artifact.resolved),
                                                          encoding="utf-8")
        attempts, usage = _usage_summary(artifact)
        packet_marker = artifact.prepared.packet.get("format")
        packet_provenance = {"requested_profile": packet_profile,
            "packet_marker": packet_marker,
            "packet_digest": artifact.prepared.packet_digest}
        summary: dict[str, object] = {
            "case": case, "effort": effort, "service_tier_requested": service_tier,
            "packet_profile": packet_profile,
            "packet_profile_provenance": packet_provenance,
            "returned_service_tiers": [row["returned_service_tier"] for row in attempts
                                       if row.get("returned_service_tier") is not None],
            "outer_results_completion_seconds": outer_elapsed,
            "artifact_runtime_seconds": artifact.runtime_seconds,
            "parse_and_runner_overhead_seconds": max(0.0, outer_elapsed - artifact.runtime_seconds),
            "timing_scope": "Saved artifact/config parse through fully constructed interactive Results artifact; stops before persistence and offline replay.",
            "attempt_count": len(artifact.attempts),
            "count_calls": sum(a.input_token_receipt is not None for a in artifact.attempts),
            "generation_calls": sum(a.writer_called for a in artifact.attempts),
            "attempts": attempts, "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "selected_attempt": artifact.selected_attempt,
            "selection_reason": artifact.selection_reason,
            "failed_findings": ([] if artifact.selected_attempt is None else
                [f.model_dump(mode="json") for f in artifact.attempts[artifact.selected_attempt].findings
                 if f.outcome == "failed"]),
            "source_sha256": source_hash, "packet_digest": artifact.prepared.packet_digest,
            "live_calls": sum(a.input_token_receipt is not None or a.writer_called
                              for a in artifact.attempts),
            **usage}
        campaign_utils.write_json(directory / "summary.json", summary)

        stage = "offline_replay"
        replayed = replay_interactive_results(artifact)
        replay_ok = replayed == artifact.resolved
        campaign_utils.write_json(directory / "verification-receipt.json", {
            "verification": "replay_interactive_results", "passed": replay_ok,
            "resolved_matches": replay_ok, "expected_resolved_digest": artifact.resolved_digest,
            "replayed_resolved_digest": (_digest(replayed.model_dump(mode="json"))
                                         if replayed is not None else None),
            "replay_made_live_calls": False})
        if not replay_ok:
            raise ValueError("offline replay resolved answer differs")
        return summary
    except Exception as exc:
        elapsed = time.perf_counter() - outer_started if outer_started is not None else None
        campaign_utils.write_json(directory / "run-error.json", {
            "type": type(exc).__name__, "stage": stage, "elapsed_seconds": elapsed,
            "elapsed_scope": "from immediately before saved artifact/config parse"
                if outer_started is not None else None,
            "source_sha256": source_hash, "config_sha256": config_hash,
            "provenance": {"case": case, "effort": effort, "service_tier": service_tier,
                           "run_name": name},
            "cost_claim": None})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--effort", choices=("none", "low", "medium"), required=True)
    parser.add_argument("--service-tier", choices=("standard", "fast"), default="standard")
    parser.add_argument("--packet-profile", choices=("indexed-v1", "joined-v2", "joined-v3",
                                                     "joined-v4"),
                        default="indexed-v1")
    parser.add_argument("--name", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    summary = run(args.case, args.effort, args.name, live=args.live,
                  service_tier=args.service_tier, packet_profile=args.packet_profile)
    print(json.dumps({key: value for key, value in summary.items()
                      if key != "attempts"}, indent=2))
    return 0 if not args.live or summary.get("delivery_outcome") == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
