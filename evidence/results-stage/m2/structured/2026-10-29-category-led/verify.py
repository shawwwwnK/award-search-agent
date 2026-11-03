"""Verify immutable call evidence, source snapshots, preview and exact replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import ledger
import run

HERE = Path(__file__).resolve().parent


def comparison_pairs_issues(pairs: object, same_role_selected: int) -> list[str]:
    """An empty pair list is valid when no option-to-option pair exists."""
    if not isinstance(pairs, list):
        return ["comparison_pairs is missing or malformed"]
    if same_role_selected >= 2 and not pairs:
        return ["comparison_pairs omits selected option pair"]
    return []


def branch_guidance_issues(request: object, *, incomplete: bool,
                           marker: str) -> list[str]:
    """Only the incomplete branch can be required to include its own marker."""
    if not isinstance(request, dict):
        return ["request is malformed"]
    if not incomplete:
        return []
    serialized = json.dumps(request, ensure_ascii=False)
    return [] if marker in serialized else ["incomplete branch guidance is absent"]


def failure_shape_issues(artifact: Any) -> list[str]:
    """A valid first-pass API failure has no composition document or answer."""
    if artifact.delivery_outcome == "delivered":
        return [] if artifact.resolved is not None else ["delivered artifact lacks answer"]
    if artifact.resolved is not None:
        return ["failed artifact unexpectedly has answer"]
    if not artifact.passes:
        return ["failed artifact has no pass receipt"]
    return []


def observed_fault_issues(*, expected_code: str | None,
                          first_findings: list[dict[str, Any]],
                          correction_count: int) -> list[str]:
    """Compare the recorded injected fault identity with actual findings."""
    if expected_code is None:
        return []
    observed = {row.get("code") for row in first_findings if row.get("outcome") == "failed"}
    issues = []
    if expected_code not in observed:
        issues.append(f"injected fault {expected_code} was not observed")
    if correction_count != 1:
        issues.append("controlled fault did not trigger exactly one correction")
    return issues


def _archive_issues(directory: Path, issues: list[str]) -> None:
    snapshot = ledger.read_json(directory / "source-snapshot.json")
    with zipfile.ZipFile(directory / "source-snapshot.zip") as archive:
        if set(archive.namelist()) != set(snapshot):
            issues.append(f"{directory.name}: archive members differ from snapshot")
        for name, digest in snapshot.items():
            try:
                data = archive.read(name)
            except KeyError:
                issues.append(f"{directory.name}: archive member missing: {name}")
                continue
            if hashlib.sha256(data).hexdigest() != digest:
                issues.append(f"{directory.name}: archive hash differs: {name}")


def _artifact_bindings_issues(artifact: Any, summary: dict[str, Any],
                             recorded: dict[str, Any], archived_source: bytes,
                             archived_config: bytes, directory: Path,
                             archived_guidance: bytes | None = None) -> list[str]:
    from award_agent.results.contracts import ResultsConfig

    issues = []
    case = recorded["case"]
    source = run.projection_from_bytes(case, archived_source)
    config = ResultsConfig.model_validate_json(archived_config)
    if recorded.get("recovery_diagnostic"):
        if archived_guidance is None:
            return ["controlled recovery guidance is missing from archive"]
        original = config.authoring_guidance or ""
        config = config.model_copy(update={"authoring_guidance":
            original + "\n" + archived_guidance.decode("utf-8")})
    if artifact.evidence.source != source:
        issues.append("artifact source differs from archived source")
    if artifact.config != config:
        issues.append("artifact config differs from archived config")
    if artifact.profile != recorded["candidate"]:
        issues.append("artifact profile differs from run settings")
    if artifact.resolved is not None:
        resolved_path = directory / "resolved.json"
        if not resolved_path.is_file() or ledger.read_json(resolved_path) != artifact.resolved.model_dump(mode="json"):
            issues.append("saved resolved answer differs from artifact")
    elif (directory / "resolved.json").exists():
        issues.append("failed artifact has stray resolved answer")
    expected_summary = {
        "generation_outcome": artifact.generation_outcome,
        "validation_outcome": artifact.validation_outcome,
        "delivery_outcome": artifact.delivery_outcome,
        "selected_pass_index": artifact.selected_pass_index,
        "selection_failed_findings": [f.model_dump(mode="json")
            for f in artifact.selection_findings if f.outcome == "failed"],
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            issues.append(f"summary {key} differs from artifact")
    if (summary.get("source_sha256") != recorded["source_sha256"] or
            summary.get("candidate") != recorded["candidate"] or
            summary.get("case") != case):
        issues.append("summary source, candidate or case differs from settings")
    return issues


def _pass_bindings_issues(artifact: Any, directory: Path,
                          reservation_counts: dict[str, int]) -> list[str]:
    issues = []
    if (reservation_counts["count"] != len(artifact.passes) or
            reservation_counts["generation"] != sum(item.writer_called for item in artifact.passes)):
        issues.append("actual call reservations differ from artifact passes")
    generation_index = 0
    for index, item in enumerate(artifact.passes, 1):
        folder = directory / f"pass-{index:02d}"
        count_request = folder / "count-request.json"
        if not count_request.is_file() or ledger.read_json(count_request) != item.request:
            issues.append(f"pass {index} count request differs from artifact")
        count_receipt = folder / "count-receipt.json"
        if item.input_token_receipt is not None:
            if (not count_receipt.is_file() or
                    ledger.read_json(count_receipt) != item.input_token_receipt.model_dump(mode="json")):
                issues.append(f"pass {index} count receipt differs from artifact")
        elif count_receipt.is_file():
            issues.append(f"pass {index} has stray count receipt")
        if not item.writer_called:
            continue
        generation_index += 1
        generation_folder = directory / f"pass-{generation_index:02d}"
        expected_body = dict(item.request, max_output_tokens=artifact.config.max_output_tokens,
                             store=False, truncation="disabled", stream=True)
        settings = (artifact.selector_settings if item.phase == "selection" else
                    artifact.correction_settings if item.phase == "correction" else
                    artifact.composer_settings)
        if settings.service_tier == "fast":
            expected_body["service_tier"] = "fast"
        request_path = generation_folder / "generation-request.json"
        if not request_path.is_file() or ledger.read_json(request_path) != expected_body:
            issues.append(f"generation {generation_index} request differs from artifact")
        writer_receipt = generation_folder / "writer-receipt.json"
        if item.writer_receipt is not None:
            if (not writer_receipt.is_file() or
                    ledger.read_json(writer_receipt) != item.writer_receipt.model_dump(mode="json")):
                issues.append(f"generation {generation_index} receipt differs from artifact")
        elif writer_receipt.is_file():
            issues.append(f"generation {generation_index} has stray writer receipt")
    return issues


def _reservation_issues(directory: Path, kind: str,
                        reservations: list[dict[str, Any]], issues: list[str]) -> None:
    from award_agent.providers.contracts import content_digest

    for row in (item for item in reservations if item["run_name"] == directory.name):
        folder = directory / row["label"]
        prefix = "count" if kind == "count" else "generation"
        request = folder / f"{prefix}-request.json"
        if not request.is_file() or content_digest(ledger.read_json(request)) != row["request_digest"]:
            issues.append(f"{directory.name}: {kind} request missing or digest differs")
        receipts = (("count-receipt.json", "count-error.json") if kind == "count"
                    else ("writer-receipt.json", "generation-error.json"))
        if not any((folder / item).is_file() for item in receipts):
            issues.append(f"{directory.name}: {kind} has no response or error receipt")


def report() -> dict[str, Any]:
    from award_agent.results.category import parse_category_artifact, replay_category_results

    settings = ledger.campaign()
    issues: list[str] = []
    reservations = {}
    for kind in ("count", "generation"):
        files = sorted(ledger.CALLS.glob(f"{kind}-*.json"))
        if len(files) > settings["maximum_input_count_calls" if kind == "count"
                                 else "maximum_generation_calls"]:
            issues.append(f"{kind}: campaign bound exceeded")
        ordinals = [int(file.stem.rsplit("-", 1)[-1]) for file in files]
        if ordinals != list(range(1, len(files) + 1)):
            issues.append(f"{kind}: reservation sequence has a gap")
        reservations[kind] = [ledger.read_json(path) for path in files]
    rows = []
    for directory in sorted(run.RUNS.iterdir()) if run.RUNS.exists() else []:
        if not directory.is_dir():
            continue
        try:
            recorded = ledger.read_json(directory / "settings.json")
            _archive_issues(directory, issues)
            snapshot = ledger.read_json(directory / "source-snapshot.json")
            case = recorded["case"]
            relative_source = str(run.source_path(case).relative_to(run.REPO))
            if recorded["source_sha256"] != snapshot[relative_source]:
                issues.append(f"{directory.name}: source hash differs")
            campaign_key = str(ledger.CAMPAIGN.relative_to(run.REPO))
            if recorded["campaign_sha256"] != snapshot[campaign_key]:
                issues.append(f"{directory.name}: campaign hash differs")
            drift_check = directory / "post-run-source-check.json"
            if drift_check.is_file():
                drift = ledger.read_json(drift_check)
                if drift.get("snapshot_drift") or drift.get("changed_paths"):
                    issues.append(f"{directory.name}: source or code changed during run")
            if (directory / "manifest.json").is_file():
                manifest = ledger.read_json(directory / "manifest.json")
                matching = [row for row in manifest.get("runs", [])
                            if row.get("name") == directory.name]
                if (len(matching) != 1 or matching[0].get("snapshot_hashes") != snapshot or
                        matching[0].get("case") != case or
                        matching[0].get("candidate") != recorded["candidate"] or
                        ledger.sha256(directory / "manifest.json") != recorded["manifest_sha256"]):
                    issues.append(f"{directory.name}: frozen manifest differs")
            artifact_path = directory / "artifact.json"
            summary_path = directory / "summary.json"
            if artifact_path.is_file() and summary_path.is_file():
                artifact = parse_category_artifact(artifact_path.read_bytes())
                summary = ledger.read_json(summary_path)
                if drift_check.is_file() and summary.get("snapshot_drift") != ledger.read_json(
                        drift_check).get("snapshot_drift"):
                    issues.append(f"{directory.name}: drift summary differs")
                with zipfile.ZipFile(directory / "source-snapshot.zip") as archive:
                    archived_source = archive.read(relative_source)
                    archived_config = archive.read(str(run.CONFIG.relative_to(run.REPO)))
                    archived_guidance = archive.read(str(run.RECOVERY_GUIDANCE.relative_to(run.REPO)))
                issues.extend(f"{directory.name}: {item}" for item in
                              _artifact_bindings_issues(artifact, summary, recorded,
                                                       archived_source, archived_config,
                                                       directory, archived_guidance))
                if replay_category_results(artifact) != artifact.resolved:
                    issues.append(f"{directory.name}: replay differs")
                issues.extend(f"{directory.name}: {item}" for item in failure_shape_issues(artifact))
                if (summary["count_calls"], summary["generation_calls"]) != (
                        len([x for x in reservations["count"] if x["run_name"] == directory.name]),
                        len([x for x in reservations["generation"] if x["run_name"] == directory.name])):
                    issues.append(f"{directory.name}: call totals differ")
                issues.extend(f"{directory.name}: {item}" for item in
                              _pass_bindings_issues(artifact, directory, {
                                  kind: len([x for x in reservations[kind]
                                             if x["run_name"] == directory.name])
                                  for kind in ("count", "generation")}))
                if recorded.get("recovery_diagnostic"):
                    first_findings = ([f.model_dump(mode="json") for f in
                                       artifact.passes[1].findings]
                                      if len(artifact.passes) > 1 else [])
                    correction_count = sum(item.phase == "correction" for item in artifact.passes)
                    issues.extend(f"{directory.name}: {item}" for item in
                                  observed_fault_issues(
                                      expected_code=recorded.get("expected_fault_code"),
                                      first_findings=first_findings,
                                      correction_count=correction_count))
                if artifact.resolved is not None:
                    from preview_loader import render_saved

                    markdown, html = render_saved(directory, artifact)
                    if (directory / "answer-preview.md").read_text() != markdown:
                        issues.append(f"{directory.name}: markdown preview differs")
                    if (directory / "answer-preview.html").read_text() != html:
                        issues.append(f"{directory.name}: HTML preview differs")
                rows.append({"run": directory.name, "case": case,
                             "candidate": recorded["candidate"],
                             "seconds": summary["outer_results_completion_seconds"],
                             "delivery": summary["delivery_outcome"]})
            elif not (directory / "run-error.json").is_file():
                issues.append(f"{directory.name}: artifact or summary missing without error receipt")
            for kind in ("count", "generation"):
                _reservation_issues(directory, kind, reservations[kind], issues)
        except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
            issues.append(f"{directory.name}: verification error {type(exc).__name__}: {exc}")
    for kind in ("count", "generation"):
        for row in reservations[kind]:
            if not (run.RUNS / row["run_name"]).is_dir():
                issues.append(f"{kind}: reservation without run directory: {row['run_name']}")
    return {"campaign": str(ledger.CAMPAIGN),
            "generation_reservations": len(reservations["generation"]),
            "count_reservations": len(reservations["count"]),
            "runs": rows, "integrity_issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = report()
    print(json.dumps(result, indent=2))
    return 1 if args.verify and result["integrity_issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
