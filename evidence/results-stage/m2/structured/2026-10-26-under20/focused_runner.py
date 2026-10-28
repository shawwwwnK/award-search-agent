"""Bounded source-snapshot runner for the two-pass V8 focused Results experiment."""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import runtime_runner as base
from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CAMPAIGN = HERE / "campaign.json"
CASES = ("admitted", "conditional", "incomplete")


def run(case: str, name: str, *, live: bool = False,
        profile: Literal["focused-v1", "focused-v2", "focused-v3"] = "focused-v1") -> dict[str, object]:
    if case not in CASES:
        raise ValueError("unknown focused source case")
    if profile not in {"focused-v1", "focused-v2", "focused-v3"}:
        raise ValueError("unknown focused profile")
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("run name must contain only letters, digits, - or _")
    if not live:
        return {"case": case, "packet_profile": profile, "mode": "offline",
                "live_calls": 0}

    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    if campaign.get("maximum_generation_calls") != 48 or \
            campaign.get("maximum_input_count_calls") != 48:
        raise ValueError("campaign must declare exact 48/48 ceilings")
    base.campaign_utils.require_two_attempt_headroom(campaign)
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)
    source_path = SOURCE / case / "artifact.json"
    config_path = SOURCE / case / "config.json"
    runtime_files = sorted((REPO / "src/award_agent/results").glob("*.py"))
    snapshot_paths = [Path(__file__), HERE / "runtime_runner.py", HERE / "harness.py",
                      CAMPAIGN, source_path, config_path,
                      REPO / "src/award_agent/cli/results.py", *runtime_files]
    source_hash = base.campaign_utils.sha256(source_path)
    config_hash = base.campaign_utils.sha256(config_path)
    base.campaign_utils.write_json(directory / "settings.json", {
        "case": case, "packet_profile": profile, "model": "gpt-6-luna",
        "selector_reasoning_effort": "none", "composer_reasoning_effort": "low",
        "service_tier": "fast", "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": source_hash, "config_sha256": config_hash,
        "runner_sha256": base.campaign_utils.sha256(Path(__file__)),
        "campaign_sha256": base.campaign_utils.sha256(CAMPAIGN),
        "max_output_tokens": 8192, "timeout_seconds": 240, "max_retries": 0})
    base.campaign_utils.write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): base.campaign_utils.sha256(path) for path in snapshot_paths})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshot_paths:
            archive.write(path, str(path.relative_to(REPO)))

    from award_agent.results.adapter import OpenAIResultsInputMeasurer
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.focused import replay_focused_results, run_focused_results
    from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    stage = "load_dotenv"
    outer_started: float | None = None
    try:
        load_dotenv(REPO / ".env")
        outer_started = time.perf_counter()
        stage = "parse_saved_artifact_and_config"
        source = StructuredResultsArtifact.model_validate_json(source_path.read_bytes())
        base_config = ResultsConfig.model_validate_json(config_path.read_bytes())
        config = base_config.model_copy(update={"model": "gpt-6-luna",
            "max_output_tokens": 8192, "timeout_seconds": 240.0})
        stage = "focused_results"
        client = OpenAI(max_retries=0, timeout=240)
        writer = base.RecordingInteractiveWriter(OpenAIInteractiveResultsWriter(client),
                                                 directory, campaign, "fast")
        measurer = base.RecordingInputMeasurer(OpenAIResultsInputMeasurer(client),
                                               directory, campaign)
        artifact = run_focused_results(source.evidence.source, config, writer, measurer,
            selection_format="roles-v2" if profile in {"focused-v2", "focused-v3"} else "roles-v1",
            composition_format="comparisons-v1" if profile == "focused-v3" else "source-v1")
        outer_elapsed = time.perf_counter() - outer_started
        stage = "persist"
        base.campaign_utils.write_json(directory / "artifact.json", artifact.model_dump(mode="json"))
        if artifact.resolved is not None:
            base.campaign_utils.write_json(directory / "resolved.json",
                                           artifact.resolved.model_dump(mode="json"))
            (directory / "answer-preview.md").write_text(base._preview(artifact.resolved),
                                                          encoding="utf-8")
        pass_rows = []
        for number, item in enumerate(artifact.passes, 1):
            receipt = item.writer_receipt
            response = base._raw(receipt.raw_response if receipt else None)
            pass_rows.append({
                "pass": number, "phase": item.phase, "label": f"final-{number:02d}",
                "outcome": item.outcome, "writer_called": item.writer_called,
                "input_token_receipt": item.input_token_receipt.model_dump(mode="json")
                    if item.input_token_receipt else None,
                "writer_receipt": receipt.model_dump(mode="json") if receipt else None,
                "actual_response_usage": response.get("usage") if response else None,
                "returned_service_tier": item.returned_service_tier,
                "error": item.error, "failure_subtype": item.failure_subtype,
            })
        summary: dict[str, object] = {
            "case": case, "packet_profile": profile, "mode": "live",
            "selector_reasoning_effort": "none", "composer_reasoning_effort": "low",
            "service_tier_requested": "fast",
            "selector_packet_digest": artifact.selector_prepared.packet_digest,
            "focus_packet_digest": artifact.focus_prepared.packet_digest
                if artifact.focus_prepared else None,
            "outer_results_completion_seconds": outer_elapsed,
            "artifact_runtime_seconds": artifact.runtime_seconds,
            "parse_and_runner_overhead_seconds": max(0.0, outer_elapsed - artifact.runtime_seconds),
            "timing_scope": "Saved artifact/config parse through constructed V8 artifact; before persistence and offline replay.",
            "pass_count": len(artifact.passes),
            "count_calls": measurer.index,
            "generation_calls": writer.index,
            "passes": pass_rows,
            "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "failed_findings": [f.model_dump(mode="json") for f in artifact.passes[-1].findings
                                if f.outcome == "failed"],
            "returned_service_tiers": [row["returned_service_tier"] for row in pass_rows
                                       if row["returned_service_tier"] is not None],
            "source_sha256": source_hash,
            "live_calls": measurer.index + writer.index,
        }
        base.campaign_utils.write_json(directory / "summary.json", summary)
        stage = "offline_replay"
        replayed = replay_focused_results(artifact)
        replay_ok = replayed == artifact.resolved
        base.campaign_utils.write_json(directory / "verification-receipt.json", {
            "verification": "replay_focused_results", "passed": replay_ok,
            "resolved_matches": replay_ok, "expected_resolved_digest": artifact.resolved_digest,
            "replayed_resolved_digest": base._digest(replayed.model_dump(mode="json"))
                if replayed is not None else None,
            "replay_made_live_calls": False})
        if not replay_ok:
            raise ValueError("offline focused replay resolved answer differs")
        return summary
    except Exception as exc:
        elapsed = time.perf_counter() - outer_started if outer_started is not None else None
        base.campaign_utils.write_json(directory / "run-error.json", {
            "type": type(exc).__name__, "stage": stage, "elapsed_seconds": elapsed,
            "source_sha256": source_hash, "config_sha256": config_hash,
            "provenance": {"case": case, "packet_profile": profile, "run_name": name},
            "cost_claim": None})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--profile", choices=("focused-v1", "focused-v2", "focused-v3"),
                        default="focused-v1")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    summary = run(args.case, args.name, live=args.live, profile=args.profile)
    print(json.dumps({key: value for key, value in summary.items() if key != "passes"}, indent=2))
    return 0 if not args.live or summary.get("delivery_outcome") == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
