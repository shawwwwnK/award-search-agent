"""Run bounded Luna fast-profile experiments against frozen Results sources.

Offline mode is the default. A live run reserves up to three count/generation
slots, saves exact requests and raw responses, and verifies the saved artifact.
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
from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CASES = ("admitted", "conditional", "incomplete")
PROFILES = ("focused-v3", "focused-v4", "focused-v5", "focused-v6",
            "focused-v7", "focused-v8", "focused-v9", "focused-v10",
            "focused-v11", "focused-v12", "focused-v13", "focused-v14",
            "focused-v15", "focused-v16", "focused-v17", "focused-v18",
            "focused-v19", "focused-v20", "focused-v21", "focused-v22",
            "focused-v23", "focused-v24", "focused-v25", "focused-v26",
            "focused-v27", "focused-v28", "focused-v29", "focused-v30")
RECOVERY_DIAGNOSTIC_PROFILES = frozenset({"focused-v4", "focused-v5",
                                         "focused-v6", "focused-v7",
                                         "focused-v11", "focused-v12", "focused-v13",
                                         "focused-v14", "focused-v15", "focused-v16",
                                         "focused-v17", "focused-v18", "focused-v19",
                                         "focused-v20", "focused-v21", "focused-v22",
                                         "focused-v23", "focused-v24", "focused-v25",
                                         "focused-v26", "focused-v27", "focused-v28",
                                         "focused-v29", "focused-v30"})
RECOVERY_GUIDANCE = HERE / "recovery-guidance.txt"
DEFAULT_CONFIG = REPO / "data/results/fast-default.json"


def append_recovery_guidance(existing: str | None, diagnostic: str) -> str:
    return (existing + "\n" if existing else "") + diagnostic


def snapshot_paths(case: str) -> list[Path]:
    return [Path(__file__), HERE / "ledger.py", HERE / "freeze.py",
            HERE / "review_bundle.py", HERE / "verify.py",
            HERE / "reviewer-instructions.md", RECOVERY_GUIDANCE, ledger.CAMPAIGN,
            SOURCE / case / "artifact.json", SOURCE / case / "config.json",
            DEFAULT_CONFIG,
            REPO / "src/award_agent/cli/results.py",
            *sorted((REPO / "src/award_agent/results").glob("*.py"))]


def snapshot_hashes(case: str) -> dict[str, str]:
    return {str(path.relative_to(REPO)): ledger.sha256(path)
            for path in snapshot_paths(case)}


def _digest(value: object) -> str:
    from award_agent.providers.contracts import content_digest
    return content_digest(value)


def _raw(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


class RecordingMeasurer:
    def __init__(self, delegate: Any, directory: Path, campaign: dict[str, Any]) -> None:
        self.delegate, self.directory, self.campaign = delegate, directory, campaign
        self.index = 0

    def measure(self, request: dict[str, object], config: Any) -> Any:
        self.index += 1
        label = f"pass-{self.index:02d}"
        folder = self.directory / label
        digest = _digest(request)
        ledger.write_new(folder / "count-request.json", request)
        ledger.reserve("count", self.campaign, run=self.directory.name,
                       label=label, digest=digest)
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
        label = f"pass-{self.index:02d}"
        folder = self.directory / label
        body = dict(request, max_output_tokens=config.max_output_tokens,
                    store=False, truncation="disabled", stream=True)
        if settings.service_tier == "fast":
            body["service_tier"] = "fast"
        digest = _digest(body)
        ledger.write_new(folder / "generation-request.json", body)
        ledger.reserve("generation", self.campaign, run=self.directory.name,
                       label=label, digest=digest)
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
            raw = _raw(receipt.raw_response if receipt else None)
            if receipt is not None:
                ledger.write_new(folder / "writer-receipt.json", receipt.model_dump(mode="json"))
            if raw is not None:
                ledger.write_new(folder / "raw-response.json", raw)
            ledger.write_new(folder / "generation-timing.json", {
                "full_response_seconds": time.perf_counter() - started,
                "returned_service_tier": raw.get("service_tier") if raw else None,
                "usage": raw.get("usage") if raw else None,
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


def _preview(resolved: Any) -> str:
    from award_agent.results.focused_comparison_wire import format_focused_comparison_block

    rows: list[str] = []
    labels = {block.canonical_id: block.label for block in resolved.blocks
              if block.kind == "reference" and block.reference_kind == "journey"
              and block.canonical_id and block.label}
    for block in resolved.blocks:
        if block.kind == "comparison":
            rows.append(format_focused_comparison_block(block, labels))
            continue
        rows.append(block.text)
        if block.kind == "reference":
            rows.append(f"[Display: {block.label}; {block.reference_kind}; {block.canonical_id}]")
    return "\n\n".join(rows) + "\n"


def _profile_kwargs(profile: str) -> dict[str, object]:
    if profile == "focused-v3":
        return {"selection_format": "roles-v2", "composition_format": "comparisons-v1"}
    if profile in {"focused-v4", "focused-v5", "focused-v6", "focused-v7",
                   "focused-v8", "focused-v9", "focused-v10", "focused-v11",
                   "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16",
                   "focused-v17", "focused-v18", "focused-v19", "focused-v20",
                   "focused-v21", "focused-v22", "focused-v23", "focused-v24",
                   "focused-v25", "focused-v26", "focused-v27", "focused-v28",
                   "focused-v29", "focused-v30"}:
        return {"profile": profile}
    raise ValueError("unknown profile")


def _invoke_results_profile(projection: Any, config: Any, writer: Any, measurer: Any,
                            profile: str, *, default_runner: Any = None,
                            focused_runner: Any = None) -> Any:
    """Route only the current default through its public Results entry point."""
    from award_agent.results.default import DEFAULT_RESULTS_PROFILE, run_default_results
    from award_agent.results.focused import run_focused_results

    if profile == DEFAULT_RESULTS_PROFILE:
        runner = default_runner or run_default_results
        return runner(projection, config, writer, measurer)
    runner = focused_runner or run_focused_results
    return runner(projection, config, writer, measurer, **_profile_kwargs(profile))


def _with_openai_client(timeout: float, operation: Any) -> Any:
    """Run one operation with a campaign-owned client that is always closed."""
    with OpenAI(max_retries=0, timeout=timeout) as client:
        return operation(client)


def run(case: str, name: str, *, profile: str = "focused-v6",
        live: bool = False, manifest: Path | None = None,
        recovery_diagnostic: bool = False) -> dict[str, object]:
    if case not in CASES or profile not in PROFILES:
        raise ValueError("unknown case or profile")
    if recovery_diagnostic and (profile not in RECOVERY_DIAGNOSTIC_PROFILES or
                                manifest is not None):
        raise ValueError("recovery diagnostic requires a conditional-correction profile and no confirmation manifest")
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError("invalid run name")
    source_path = SOURCE / case / "artifact.json"
    config_path = SOURCE / case / "config.json"
    if not live:
        return {"case": case, "profile": profile, "mode": "offline", "live_calls": 0,
                "recovery_diagnostic": recovery_diagnostic,
                "source_sha256": ledger.sha256(source_path)}

    with ledger.locked_campaign():
        return _run_live(case, name, profile, source_path, config_path, manifest,
                         recovery_diagnostic)


def _run_live(case: str, name: str, profile: str,
              source_path: Path, config_path: Path,
              manifest: Path | None,
              recovery_diagnostic: bool) -> dict[str, object]:

    campaign = ledger.campaign()
    ledger.require_headroom(campaign)
    from award_agent.results.contracts import ResultsConfig

    candidate = ResultsConfig.model_validate_json(DEFAULT_CONFIG.read_bytes())
    if (candidate.model != campaign["model"] or
            candidate.max_output_tokens != campaign["max_output_tokens"] or
            candidate.timeout_seconds != campaign["timeout_seconds"]):
        raise ValueError("proposed default config differs from campaign execution settings")
    if manifest is not None:
        declared = ledger.read_json(manifest)
        rows = declared.get("runs", [])
        matching = [row for row in rows if row.get("name") == name]
        if len(matching) != 1 or matching[0].get("case") != case or \
                matching[0].get("profile") != profile:
            raise ValueError("run differs from frozen confirmation manifest")
        if matching[0].get("source_sha256") != ledger.sha256(source_path):
            raise ValueError("source differs from frozen confirmation manifest")
        if matching[0].get("snapshot_hashes") != snapshot_hashes(case):
            raise ValueError("code or inputs differ from frozen confirmation manifest")
    directory = HERE / "runs" / name
    directory.mkdir(parents=True, exist_ok=False)
    snapshots = snapshot_paths(case)
    hashes = snapshot_hashes(case)
    ledger.write_new(directory / "source-snapshot.json", hashes)
    with zipfile.ZipFile(directory / "source-snapshot.zip", "x",
                         compression=zipfile.ZIP_DEFLATED) as archive:
        for path in snapshots:
            archive.write(path, str(path.relative_to(REPO)))
    ledger.write_new(directory / "settings.json", {
        "case": case, "profile": profile, "model": "gpt-6-luna",
        "recovery_diagnostic": recovery_diagnostic,
        "recovery_guidance_sha256": ledger.sha256(RECOVERY_GUIDANCE)
            if recovery_diagnostic else None,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": ledger.sha256(source_path),
        "config_sha256": ledger.sha256(config_path),
        "effective_config_source": "data/results/fast-default.json",
        "default_config_sha256": ledger.sha256(DEFAULT_CONFIG),
        "campaign_sha256": ledger.sha256(ledger.CAMPAIGN),
        "manifest_sha256": ledger.sha256(manifest) if manifest else None,
        "max_output_tokens": campaign["max_output_tokens"],
        "timeout_seconds": campaign["timeout_seconds"], "max_retries": 0})
    if manifest is not None:
        (directory / "manifest.json").write_bytes(manifest.read_bytes())
    stage = "start"
    started = time.perf_counter()
    try:
        from award_agent.results.adapter import OpenAIResultsInputMeasurer
        from award_agent.results.focused import replay_focused_results
        from award_agent.results.interactive_adapter import OpenAIInteractiveResultsWriter
        from award_agent.results.structured_contracts import StructuredResultsArtifact

        stage = "parse_source"
        source = StructuredResultsArtifact.model_validate_json(source_path.read_bytes())
        ResultsConfig.model_validate_json(config_path.read_bytes())
        config = candidate.model_copy(update={"authoring_guidance":
            append_recovery_guidance(candidate.authoring_guidance,
                RECOVERY_GUIDANCE.read_text(encoding="utf-8"))}) if recovery_diagnostic else candidate
        stage = "run_focused_results"
        load_dotenv(REPO / ".env")
        def execute(client: Any) -> Any:
            writer = RecordingWriter(OpenAIInteractiveResultsWriter(client), directory, campaign)
            measurer = RecordingMeasurer(OpenAIResultsInputMeasurer(client), directory, campaign)
            artifact = _invoke_results_profile(source.evidence.source, config, writer, measurer,
                                               profile)
            return artifact, writer, measurer

        artifact, writer, measurer = _with_openai_client(campaign["timeout_seconds"], execute)
        elapsed = time.perf_counter() - started
        stage = "persist"
        ledger.write_new(directory / "artifact.json", artifact.model_dump(mode="json"))
        if artifact.resolved is not None:
            ledger.write_new(directory / "resolved.json", artifact.resolved.model_dump(mode="json"))
            (directory / "answer-preview.md").write_text(_preview(artifact.resolved), encoding="utf-8")
        selected_pass_index = getattr(artifact, "selected_pass_index", None)
        if selected_pass_index is None and artifact.resolved is not None:
            selected_pass_index = next((index for index in range(len(artifact.passes) - 1, -1, -1)
                if artifact.passes[index].document is not None), None)
        selected_findings = (artifact.passes[selected_pass_index].findings
                             if selected_pass_index is not None else ())
        summary = {
            "case": case, "profile": profile, "mode": "live",
            "comparison_registry_digest": _digest(artifact.comparison_registry.model_dump(mode="json"))
                if artifact.contract_version in {"results-artifact-v11", "results-artifact-v12"} and
                   artifact.comparison_registry is not None else None,
            "comparison_cards": [block.comparison.comparison_id
                for block in artifact.resolved.blocks if block.kind == "comparison"]
                if artifact.resolved is not None and
                   artifact.contract_version in {"results-artifact-v11", "results-artifact-v12"} else [],
            "recovery_diagnostic": recovery_diagnostic,
            "editorial_revision": artifact.contract_version in {"results-artifact-v10", "results-artifact-v12"},
            "revision_trigger": getattr(artifact, "revision_trigger", None),
            "recovery_triggered": recovery_diagnostic and len(artifact.passes) == 3 and
                artifact.contract_version != "results-artifact-v12",
            "diagnostic_fault_observed": recovery_diagnostic and len(artifact.passes) > 1
                and any(f.code == "visible_internal_alias" and f.outcome == "failed"
                        for f in artifact.passes[1].findings),
            "initial_composition_failed_findings": (
                [f.model_dump(mode="json") for f in artifact.passes[1].findings
                 if f.outcome == "failed"] if recovery_diagnostic and
                    len(artifact.passes) > 1 else []),
            "outer_results_completion_seconds": elapsed,
            "timing_scope": "Saved source parse through checked/resolved Results artifact, before disk persistence and offline replay.",
            "artifact_runtime_seconds": artifact.runtime_seconds,
            "count_calls": measurer.index, "generation_calls": writer.index,
            "passes": [{"phase": item.phase, "outcome": item.outcome,
                        "writer_called": item.writer_called,
                        "returned_service_tier": item.returned_service_tier,
                        "input_tokens": item.input_token_receipt.input_tokens
                            if item.input_token_receipt else None,
                        "usage": _raw(item.writer_receipt.raw_response).get("usage")
                            if item.writer_receipt and _raw(item.writer_receipt.raw_response)
                            else None} for item in artifact.passes],
            "generation_outcome": artifact.generation_outcome,
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "selected_pass_index": selected_pass_index,
            "failed_findings": [f.model_dump(mode="json") for f in selected_findings
                                if f.outcome == "failed"],
            "source_sha256": ledger.sha256(source_path),
            "live_calls": measurer.index + writer.index,
        }
        ledger.write_new(directory / "summary.json", summary)
        stage = "offline_replay"
        from award_agent.results.focused import parse_focused_artifact
        checked = parse_focused_artifact((directory / "artifact.json").read_bytes())
        replayed = replay_focused_results(checked)
        ok = replayed == artifact.resolved
        ledger.write_new(directory / "verification-receipt.json", {
            "verification": "replay_focused_results", "passed": ok,
            "resolved_matches": ok, "live_calls": 0})
        if not ok:
            raise ValueError("offline replay differs")
        return summary
    except Exception as exc:
        ledger.write_new(directory / "run-error.json", {
            "type": type(exc).__name__, "stage": stage,
            "elapsed_seconds": time.perf_counter() - started,
            "source_sha256": ledger.sha256(source_path), "cost_claim": None})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--profile", choices=PROFILES, default="focused-v6")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--recovery-diagnostic", action="store_true")
    args = parser.parse_args()
    result = run(args.case, args.name, profile=args.profile,
                 live=args.live, manifest=args.manifest,
                 recovery_diagnostic=args.recovery_diagnostic)
    print(json.dumps(result, indent=2))
    return 0 if not args.live or result["delivery_outcome"] == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
