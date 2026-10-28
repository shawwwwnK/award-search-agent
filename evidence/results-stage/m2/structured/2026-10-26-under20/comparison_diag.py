"""One paid composition-only diagnostic using a previously validated selector choice.

This is not an end-to-end Results run or a latency measurement of one.
Offline is the default; --live is required to construct an API client.
"""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import runtime_runner as base
from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
CAMPAIGN = HERE / "campaign.json"
SOURCE = HERE / "runs/focused2-a-recovery/artifact.json"


def run(name: str, *, live: bool = False) -> dict[str, object]:
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("run name must contain only letters, digits, - or _")
    if not live:
        return {"contract": "comparison-composition-diagnostic-v1", "mode": "offline",
                "source": str(SOURCE.relative_to(REPO)), "live_calls": 0}

    campaign = json.loads(CAMPAIGN.read_text(encoding="utf-8"))
    if campaign.get("maximum_generation_calls") != 48 or \
            campaign.get("maximum_input_count_calls") != 48:
        raise ValueError("campaign must declare exact 48/48 ceilings")
    base.campaign_utils.require_two_attempt_headroom(campaign)
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), HERE / "verify_comparisons.py", SOURCE, CAMPAIGN,
             HERE / "runtime_runner.py", HERE / "harness.py",
             *sorted((REPO / "src/award_agent/results").glob("*.py"))]
    base.campaign_utils.write_json(directory / "source-snapshot.json", {
        str(path.relative_to(REPO)): base.campaign_utils.sha256(path) for path in paths})
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, str(path.relative_to(REPO)))

    from award_agent.results.adapter import OpenAIResultsInputMeasurer
    from award_agent.results.focused import (
        COMPOSER_SETTINGS,
        _pass,
        _request,
        prepare_focused_composer,
        replay_focused_results,
    )
    from award_agent.results.focused_contracts import FocusedResultsArtifact
    from award_agent.results.focused_wire import decode as decode_focused_wire
    from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter
    from award_agent.results.structured import resolve_structured_document

    stage = "validate_previous_selection"
    started: float | None = None
    try:
        prior = FocusedResultsArtifact.model_validate_json(SOURCE.read_bytes())
        replay_focused_results(prior)
        if (len(prior.passes) != 2 or prior.passes[0].outcome != "recoverable" or
                prior.passes[0].selection is None or
                prior.selector_prepared.packet.get("selection_format") != "roles-v2"):
            raise ValueError("source artifact lacks a validated roles-v2 selected pool")
        projection = prior.evidence.source
        focus = prepare_focused_composer(prior.passes[0].selection,
            prior.selector_prepared, projection, prior.evidence,
            composition_format="comparisons-v1")
        envelope = _request(focus, prior.config, COMPOSER_SETTINGS, "composition", projection)
        base.campaign_utils.write_json(directory / "settings.json", {
            "contract": "comparison-composition-diagnostic-v1", "case": "admitted",
            "mode": "composition-only", "model": "gpt-6-luna",
            "source_artifact": str(SOURCE.relative_to(REPO)),
            "source_sha256": base.campaign_utils.sha256(SOURCE),
            "old_selector_request_digest": prior.passes[0].request_digest,
            "old_selector_response_receipt": str(SOURCE.relative_to(REPO)),
            "source_selector_count_is_reused": True, "new_selector_calls": 0,
            "new_composer_calls_max": 1, "new_count_calls_max": 1,
            "reasoning_effort": COMPOSER_SETTINGS.reasoning_effort,
            "service_tier": COMPOSER_SETTINGS.service_tier,
            "started_at_utc": datetime.now(UTC).isoformat()})
        load_dotenv(REPO / ".env")
        client = OpenAI(max_retries=0, timeout=240)
        writer = base.RecordingInteractiveWriter(OpenAIInteractiveResultsWriter(client),
                                                 directory, campaign, "fast")
        measurer = base.RecordingInputMeasurer(OpenAIResultsInputMeasurer(client),
                                               directory, campaign)
        stage = "single_composition_pass"
        started = time.perf_counter()
        answer_pass = _pass("composition", envelope, prior.config, COMPOSER_SETTINGS,
            writer, measurer, lambda raw: decode_focused_wire(raw, focus, projection),
            projection=projection, prepared=focus)
        elapsed = time.perf_counter() - started
        resolved = (resolve_structured_document(answer_pass.document, focus.structured,
                                                prior.evidence, answer_pass.findings)
                    if answer_pass.document is not None else None)
        artifact = {
            "contract": "comparison-composition-diagnostic-v1",
            "timing_scope": "Composition count and generation only; no selector or full Results run",
            "source_artifact": str(SOURCE.relative_to(REPO)),
            "source_sha256": base.campaign_utils.sha256(SOURCE),
            "old_selector_pass": prior.passes[0].model_dump(mode="json"),
            "evidence": prior.evidence.model_dump(mode="json"),
            "config": prior.config.model_dump(mode="json"),
            "selector_prepared": prior.selector_prepared.model_dump(mode="json"),
            "focus_prepared": focus.model_dump(mode="json"),
            "composer_pass": answer_pass.model_dump(mode="json"),
            "document": answer_pass.document.model_dump(mode="json")
                if answer_pass.document else None,
            "resolved": resolved.model_dump(mode="json") if resolved else None,
            "composition_seconds": elapsed,
            "new_selector_calls": 0, "new_count_calls": measurer.index,
            "new_generation_calls": writer.index,
        }
        stage = "persist"
        base.campaign_utils.write_json(directory / "diagnostic-artifact.json", artifact)
        if resolved is not None:
            base.campaign_utils.write_json(directory / "resolved.json", resolved.model_dump(mode="json"))
            (directory / "answer-preview.md").write_text(base._preview(resolved),
                                                          encoding="utf-8")
        summary: dict[str, object] = {
            "contract": "comparison-composition-diagnostic-v1", "mode": "live",
            "timing_scope": artifact["timing_scope"], "composition_seconds": elapsed,
            "outcome": answer_pass.outcome, "delivered": resolved is not None,
            "failed_findings": [item.model_dump(mode="json") for item in answer_pass.findings
                                if item.outcome == "failed"],
            "new_selector_calls": 0, "new_count_calls": measurer.index,
            "new_generation_calls": writer.index,
            "source_artifact": artifact["source_artifact"],
            "old_selector_request_digest": prior.passes[0].request_digest,
            "new_composer_request_digest": answer_pass.request_digest,
        }
        base.campaign_utils.write_json(directory / "summary.json", summary)
        stage = "offline_verify"
        from verify_comparisons import verify
        verify(directory)
        return summary
    except Exception as exc:
        base.campaign_utils.write_json(directory / "run-error.json", {
            "type": type(exc).__name__, "stage": stage,
            "elapsed_seconds": time.perf_counter() - started if started else None,
            "source_sha256": base.campaign_utils.sha256(SOURCE),
            "cost_claim": None})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.name, live=args.live), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
