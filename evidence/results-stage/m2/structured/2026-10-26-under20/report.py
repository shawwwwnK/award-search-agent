"""Integrity and evidence report for the under20 Results campaign."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
RUNS = HERE / "runs"
CALLS = HERE / "calls"
INDEX = HERE / "review-index.json"
BUNDLES = HERE / "review-bundles"
CAMPAIGN_PATH = HERE / "campaign.json"
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
METRICS = HERE / "metrics.json"
RATES = {
    "ordinary_input": Decimal("0.10"),
    "cached_input": Decimal("0.01"),
    "cache_write_input": Decimal("0.125"),
    "output": Decimal("0.50"),
}
MILLION = Decimal(1_000_000)
EXECUTION_FIELDS = {"max_output_tokens", "store", "truncation", "stream", "service_tier"}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _optional_json(path: Path) -> Any:
    try:
        return _json(path) if path.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _content_digest(value: object) -> str:
    if str(REPO / "src") not in sys.path:
        sys.path.insert(0, str(REPO / "src"))
    from award_agent.providers.contracts import content_digest
    return content_digest(value)


def _response_from_call(run: Path, kind: str, label: str) -> tuple[dict[str, Any] | None, str | None]:
    folder = run / label
    names = (("raw-response.json", "response.json") if kind == "generation"
             else ("count-receipt.json",))
    for name in names:
        path = folder / name
        if not path.is_file():
            continue
        try:
            value = _json(path)
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"{name} parse failed: {type(exc).__name__}"
        if name == "count-receipt.json":
            raw = value.get("raw_response")
            if isinstance(raw, dict):
                return raw, None
            return None, "count receipt has no raw response"
        if not isinstance(value, dict):
            return None, f"{name} is not a JSON object"
        return value, None
    # Some completed/failure attempts only retained the model receipt in artifact.json.
    artifact_path = run / "artifact.json"
    if artifact_path.exists():
        try:
            artifact = _json(artifact_path)
            ordinal = int(label.rsplit("-", 1)[-1]) - 1
            records = artifact.get("passes", artifact.get("attempts", []))
            attempt = records[ordinal]
            if kind == "count":
                receipt = attempt.get("input_token_receipt")
                raw = receipt.get("raw_response") if isinstance(receipt, dict) else None
                return (raw, None) if isinstance(raw, dict) else (None, None)
            receipt = attempt.get("writer_receipt")
            raw_text = receipt.get("raw_response") if isinstance(receipt, dict) else None
            if isinstance(raw_text, str):
                value = json.loads(raw_text)
                return (value, None) if isinstance(value, dict) else (None, "writer raw response is not an object")
        except (IndexError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass
    return None, None


def _attempt_for_label(label: str, summary: dict[str, Any],
                       artifact: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        index = int(label.rsplit("-", 1)[-1]) - 1
    except ValueError:
        return None
    rows = (artifact.get("passes", artifact.get("attempts", [])) if artifact
            else summary.get("attempts", []))
    return rows[index] if isinstance(rows, list) and 0 <= index < len(rows) else None


def _generation_timing(run: Path, label: str) -> dict[str, Any] | None:
    path = run / label / "generation-timing.json"
    if not path.exists():
        return None
    try:
        value = _json(path)
        keys = ("first_event_ms", "first_text_ms", "first_event_seconds",
                "first_text_seconds", "full_response_seconds", "requested_service_tier",
                "returned_service_tier", "events_seen", "text_delta_events")
        return {key: value[key] for key in keys if key in value}
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return {"parse_error": type(exc).__name__}


def _call_requests(run: Path, kind: str, label: str) -> tuple[dict[str, Any] | None, str | None]:
    path = run / label / ("count-request.json" if kind == "count" else "generation-request.json")
    if not path.is_file():
        return None, "request file missing"
    try:
        value = _json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"request parse failed: {type(exc).__name__}"
    return (value, None) if isinstance(value, dict) else (None, "request is not an object")


def _token_request(generation_request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in generation_request.items()
            if key not in EXECUTION_FIELDS}


def _tier_factor(tier: object) -> Decimal:
    # The Responses API reports Fast processing as priority service when granted.
    return Decimal(2) if tier in {"priority", "fast"} else Decimal(1)


def _usage_metrics(response: dict[str, Any] | None) -> dict[str, Any] | None:
    if response is None:
        return None
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return {"status": response.get("status"), "service_tier": response.get("service_tier"),
                "usage_available": False}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "status": response.get("status"),
        "service_tier": response.get("service_tier"),
        "input_tokens": usage.get("input_tokens"),
        "cached_input_tokens": input_details.get("cached_tokens")
            if isinstance(input_details, dict) else None,
        "cache_write_input_tokens": input_details.get("cache_write_tokens")
            if isinstance(input_details, dict) else None,
        "ordinary_input_tokens": (
            usage.get("input_tokens") - (input_details.get("cached_tokens") or 0)
            - (input_details.get("cache_write_tokens") or 0)
            if isinstance(usage.get("input_tokens"), int) and isinstance(input_details, dict)
            else None),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": output_details.get("reasoning_tokens")
            if isinstance(output_details, dict) else None,
        "total_tokens": usage.get("total_tokens"),
        "raw_usage": usage,
    }


def _cost(metrics: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if metrics is None:
        return None, "raw usage unavailable"
    needed = ("ordinary_input_tokens", "cached_input_tokens",
              "cache_write_input_tokens", "output_tokens")
    if any(not isinstance(metrics.get(key), int) or isinstance(metrics.get(key), bool)
           for key in needed):
        return None, "one or more billable usage fields unavailable"
    factor = _tier_factor(metrics.get("service_tier"))
    value = factor * (
        Decimal(metrics["ordinary_input_tokens"]) * RATES["ordinary_input"]
        + Decimal(metrics["cached_input_tokens"]) * RATES["cached_input"]
        + Decimal(metrics["cache_write_input_tokens"]) * RATES["cache_write_input"]
        + Decimal(metrics["output_tokens"]) * RATES["output"]
    ) / MILLION
    return format(value, "f"), None


def _review_for_run(run_name: str, index: dict[str, str]) -> dict[str, Any] | None:
    for bundle, run_path in index.items():
        if run_path.rstrip("/") != f"runs/{run_name}":
            continue
        path = BUNDLES / bundle / "review.json"
        if path.exists():
            try:
                review = _json(path)
                return {"bundle": bundle, "H": review.get("H"), "U": review.get("U"),
                        "C": review.get("C"), "protocol": review.get("protocol"),
                        "findings_count": len(review.get("findings", []))}
            except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
                return {"bundle": bundle, "review_error": type(exc).__name__}
    return None


def _manifest_run_match(manifest: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """Compare frozen confirmation claims with each run's archived evidence."""
    expected_settings = manifest.get("settings")
    recorded = row.get("recorded_settings") or {}
    if not isinstance(recorded, dict):
        recorded = {}
    checks: list[dict[str, Any]] = []

    def compare(label: str, expected: Any, actual: Any, *, available: bool = True) -> None:
        checks.append({"field": label, "expected": expected, "actual": actual,
                       "available": available,
                       "passed": available and expected == actual})

    if not isinstance(expected_settings, dict):
        compare("settings", "declared frozen settings", expected_settings)
    else:
        compare("model", expected_settings.get("model"), row.get("model"))
        if "selector_reasoning_effort" in expected_settings:
            compare("selector_reasoning_effort",
                    expected_settings["selector_reasoning_effort"],
                    recorded.get("selector_reasoning_effort"))
            compare("composer_reasoning_effort",
                    expected_settings.get("composer_reasoning_effort"),
                    recorded.get("composer_reasoning_effort"))
        else:
            compare("reasoning_effort", expected_settings.get("reasoning_effort"),
                    recorded.get("effort"))
        compare("service_tier", expected_settings.get("service_tier"),
                recorded.get("service_tier"))
        compare("max_output_tokens", expected_settings.get("max_output_tokens"),
                recorded.get("max_output_tokens"))
        compare("timeout_seconds", expected_settings.get("timeout_seconds"),
                recorded.get("timeout_seconds"))
        compare("max_retries", expected_settings.get("max_retries"),
                recorded.get("max_retries"))
        # Historical manifests predate packet_profile. Their original packet
        # identity remains verifiable through the saved artifact and code hashes.
        if "packet_profile" in expected_settings:
            compare("packet_profile", expected_settings["packet_profile"],
                    row.get("packet_profile"))

    expected_code = manifest.get("code_sha256")
    snapshot = row.get("source_snapshot_hashes") or {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    if not isinstance(expected_code, dict) or not expected_code:
        compare("code_sha256", "nonempty frozen code hash mapping", expected_code)
    else:
        for path, digest in sorted(expected_code.items()):
            actual = snapshot.get(path)
            compare(f"code_sha256:{path}", digest, actual, available=actual is not None)

    failures = [check["field"] for check in checks if not check["passed"]]
    unavailable = [check["field"] for check in checks if not check["available"]]
    mismatches = [check["field"] for check in checks
                  if check["available"] and not check["passed"]]
    return {"passed": not failures, "checks": checks, "failed_fields": failures,
            "unavailable_fields": unavailable, "mismatch_fields": mismatches}


def _run_labels(run: Path, ledger: dict[str, list[dict[str, Any]]]) -> list[str]:
    labels = {entry.get("label") for entries in ledger.values() for entry in entries
              if entry.get("run_name") == run.name and isinstance(entry.get("label"), str)}
    labels.update(path.name for path in run.glob("final-*") if path.is_dir())
    interruption_path = run / "interruption-receipt.json"
    if interruption_path.is_file():
        try:
            interruption = _json(interruption_path)
            label = interruption.get("label") if isinstance(interruption, dict) else None
            labels.add(label if isinstance(label, str) and label else "external-interruption-receipt")
        except (OSError, json.JSONDecodeError):
            labels.add("external-interruption-receipt")
    return sorted(labels)


def _confirmation_summary(filename: str, manifest: dict[str, Any],
                          runs_report: list[dict[str, Any]],
                          expected_cases: set[str]) -> dict[str, Any]:
    names = manifest.get("runs", [])
    by_name = {row["run_name"]: row for row in runs_report}
    checks: list[dict[str, Any]] = []
    latency_misses: list[dict[str, Any]] = []
    quality_unavailable: list[str] = []
    quality_failures: list[str] = []
    manifest_failures: list[dict[str, Any]] = []
    manifest_unavailable: list[dict[str, Any]] = []
    covered_cases: set[str] = set()
    for name in names:
        row = by_name.get(name)
        if row is None:
            checks.append({"run_name": name, "status": "not_run",
                           "passes_joint_confirmation": False})
            continue
        if row.get("case"):
            covered_cases.add(row["case"])
        review = row["review"] or {}
        manifest_match = _manifest_run_match(manifest, row)
        if not manifest_match["passed"]:
            issue = {"run_name": name, "failed_fields": manifest_match["failed_fields"],
                     "unavailable_fields": manifest_match["unavailable_fields"],
                     "mismatch_fields": manifest_match["mismatch_fields"]}
            manifest_failures.append(issue)
            if manifest_match["unavailable_fields"]:
                manifest_unavailable.append(issue)
        elapsed = row.get("outer_results_completion_seconds")
        latency_pass = isinstance(elapsed, (int, float)) and elapsed < 20
        quality_available = all(review.get(axis) in {"pass", "fail"}
                                for axis in ("H", "U"))
        quality_pass = quality_available and review.get("H") == "pass" and review.get("U") == "pass"
        checks.append({"run_name": name, "case": row.get("case"), "kind": row["kind"],
            "H": review.get("H"), "U": review.get("U"), "C": review.get("C"),
            "protocol": review.get("protocol"),
            "manifest_match": manifest_match,
            "delivery_outcome": row.get("delivery_outcome"),
            "validation_outcome": row.get("validation_outcome"),
            "outer_results_completion_seconds": elapsed,
            "latency_pass": latency_pass, "quality_review_available": quality_available,
            "passes_joint_confirmation": (row["kind"] in {"actual_v7", "actual_v8"} and quality_pass
                and manifest_match["passed"]
                and review.get("protocol") == "clean"
                and row.get("delivery_outcome") == "delivered"
                and row.get("validation_outcome") == "clean" and latency_pass)})
        if not latency_pass:
            latency_misses.append({"run_name": name, "seconds": elapsed,
                "reason": "missing actual v7 outer time" if elapsed is None else "at or above 20 seconds"})
        if not quality_available:
            quality_unavailable.append(name)
        elif not quality_pass or review.get("protocol") != "clean":
            quality_failures.append(name)
    complete = bool(names) and all(name in by_name for name in names)
    covered = expected_cases <= covered_cases
    joint = (None if not complete else bool(covered and checks and
              all(item.get("passes_joint_confirmation", False) for item in checks)))
    return {"filename": filename, "status": manifest.get("status"),
        "settings": manifest.get("settings"), "run_names": names,
        "planned_run_names_complete": complete,
        "runs": checks,
        "coverage": {"expected_cases": sorted(expected_cases),
                     "covered_cases": sorted(covered_cases),
                     "missing_cases": sorted(expected_cases - covered_cases),
                     "complete": bool(names) and covered},
        "latency_misses": latency_misses,
        "quality_unavailable_runs": quality_unavailable,
        "quality_failure_runs": quality_failures,
        "manifest_mismatch_runs": manifest_failures,
        "manifest_unavailable_runs": manifest_unavailable,
        "joint_success": joint}


def _archive_integrity(run: Path) -> dict[str, Any]:
    manifest_path, archive_path = run / "source-snapshot.json", run / "source-snapshot.zip"
    if not manifest_path.exists() or not archive_path.exists():
        return {"status": "unavailable", "issues": ["snapshot manifest or archive missing"]}
    try:
        manifest = _json(manifest_path)
        issues: list[str] = []
        with zipfile.ZipFile(archive_path) as archive:
            members = {name: _sha_bytes(archive.read(name)) for name in archive.namelist()}
        if set(members) != set(manifest):
            issues.append("archive member set differs from snapshot manifest")
        for name, digest in manifest.items():
            if members.get(name) != digest:
                issues.append(f"archive hash differs: {name}")
        return {"status": "failed" if issues else "verified",
                "members": len(members), "issues": issues}
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, TypeError) as exc:
        return {"status": "failed", "issues": [f"archive verification: {type(exc).__name__}"]}


def _verified_external_interruption(run: Path, label: str,
        count_entry: dict[str, Any] | None, count_request: dict[str, Any] | None,
        generation_entries_for_run: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """Validate an exec-tool interruption without treating it as an API result."""
    receipt_path = run / "interruption-receipt.json"
    if not receipt_path.is_file():
        return None, None
    try:
        receipt = _json(receipt_path)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"interruption receipt parse failed: {type(exc).__name__}"
    if not isinstance(receipt, dict):
        return None, "interruption receipt is not an object"
    if receipt.get("kind") != "external_interruption":
        return None, "interruption receipt kind is invalid"
    if receipt.get("run_name") != run.name or receipt.get("label") != label:
        return None, "interruption receipt run or label does not match reservation"
    if receipt.get("call_kind") != "count":
        return None, "interruption receipt call kind is not count"
    if count_entry is None or count_request is None:
        return None, "interrupted count reservation or request is missing"
    reservation = receipt.get("reservation")
    if not isinstance(reservation, dict):
        return None, "interruption receipt reservation is missing"
    for key in ("run_name", "label", "request_digest", "reserved_at_utc", "status"):
        if reservation.get(key) != count_entry.get(key):
            return None, f"interruption receipt reservation differs from count ledger: {key}"
    if reservation.get("status") != "reserved_before_invocation":
        return None, "interruption reservation status is not reserved_before_invocation"
    if _content_digest(count_request) != count_entry.get("request_digest"):
        return None, "count ledger digest differs from exact count request"
    if receipt.get("observed_failure_source") != \
            "Codex exec/write_stdin sandbox tool result, not an OpenAI API response":
        return None, "interruption receipt source is not the external exec tool"
    if receipt.get("observed_error") != \
            'Network access to "api.openai.com" was blocked: local/private network addresses are blocked by the sandbox policy.':
        return None, "interruption receipt error does not match the recorded sandbox failure"
    if receipt.get("response_available") is not False:
        return None, "interruption receipt must state that no response is available"
    if receipt.get("generation_reservation_present") is not False:
        return None, "interruption receipt must state that no generation reservation exists"
    if receipt.get("latency_claim") is not None or receipt.get("billing_claim") is not None:
        return None, "interruption receipt must not claim latency or billing"
    if not isinstance(receipt.get("disposition"), str) or not receipt["disposition"].strip():
        return None, "interruption receipt disposition is missing"
    folder = run / label
    if generation_entries_for_run:
        return None, "interrupted run has a generation ledger reservation"
    if any((folder / name).exists() for name in (
            "count-receipt.json", "count-error.json", "generation-request.json",
            "raw-response.json", "response.json", "generation-error.json",
            "generation-timing.json")):
        return None, "interrupted call has count or generation response evidence"
    return receipt, None


def _v7_integrity(run: Path, source_path: Path, source_hash: str) -> dict[str, Any]:
    issues: list[str] = []
    result: dict[str, Any] = {"source_sha256": {"recorded": None, "current": source_hash,
                                                 "matches": None},
                              "canonical_source_matches": None,
                              "replay": "not_run", "raw_wire_identity": []}
    settings_path = run / "settings.json"
    artifact_path = run / "artifact.json"
    try:
        settings = _json(settings_path)
        recorded = settings.get("source_sha256")
        result["source_sha256"] = {"recorded": recorded, "current": source_hash,
                                   "matches": recorded == source_hash}
        if recorded != source_hash:
            issues.append("run source hash differs from current source artifact")
        from award_agent.results.interactive import replay_interactive_results
        from award_agent.results.interactive_contracts import InteractiveResultsArtifact
        from award_agent.results.structured_contracts import StructuredResultsArtifact

        artifact = InteractiveResultsArtifact.model_validate_json(
            artifact_path.read_text(encoding="utf-8"))
        source_artifact = StructuredResultsArtifact.model_validate_json(
            source_path.read_text(encoding="utf-8"))
        canonical_match = artifact.evidence.source == source_artifact.evidence.source
        result["canonical_source_matches"] = canonical_match
        if not canonical_match:
            issues.append("artifact canonical source differs from original source")
        for index, attempt in enumerate(artifact.attempts):
            response, parse_error = _response_from_call(run, "generation", f"final-{index + 1:02d}")
            if parse_error:
                issues.append(parse_error)
            if attempt.raw_wire is not None:
                text_parts = []
                if response:
                    for item in response.get("output", []):
                        if item.get("type") == "message":
                            text_parts.extend(part.get("text", "") for part in item.get("content", [])
                                              if part.get("type") == "output_text")
                matches = "".join(text_parts) == attempt.raw_wire
                result["raw_wire_identity"].append({"attempt": index + 1, "matches": matches})
                if not matches:
                    issues.append(f"attempt {index + 1} raw wire differs from response text")
        replayed = replay_interactive_results(artifact)
        replay_matches = replayed == artifact.resolved
        result["replay"] = "passed" if replay_matches else "resolved_mismatch"
        if not replay_matches:
            issues.append("offline replay resolved answer differs")
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        result["replay"] = f"failed:{type(exc).__name__}"
        issues.append(f"v7 source/replay verification: {type(exc).__name__}: {exc}")
    result["issues"] = issues
    return result


def _v8_integrity(run: Path, source_path: Path, source_hash: str) -> dict[str, Any]:
    """Rebuild both focused passes and bind their saved raw outputs to receipts."""
    issues: list[str] = []
    result: dict[str, Any] = {"source_sha256": {"recorded": None, "current": source_hash,
                                                 "matches": None},
                              "canonical_source_matches": None,
                              "replay": "not_run", "raw_wire_identity": []}
    try:
        settings = _json(run / "settings.json")
        recorded = settings.get("source_sha256")
        result["source_sha256"] = {"recorded": recorded, "current": source_hash,
                                   "matches": recorded == source_hash}
        if recorded != source_hash:
            issues.append("run source hash differs from current source artifact")
        from award_agent.results.focused import replay_focused_results
        from award_agent.results.focused_contracts import FocusedResultsArtifact
        from award_agent.results.structured_contracts import StructuredResultsArtifact

        artifact = FocusedResultsArtifact.model_validate_json(
            (run / "artifact.json").read_text(encoding="utf-8"))
        source_artifact = StructuredResultsArtifact.model_validate_json(
            source_path.read_text(encoding="utf-8"))
        canonical_match = artifact.evidence.source == source_artifact.evidence.source
        result["canonical_source_matches"] = canonical_match
        if not canonical_match:
            issues.append("artifact canonical source differs from original source")
        for index, phase in enumerate(artifact.passes, 1):
            response, parse_error = _response_from_call(run, "generation", f"final-{index:02d}")
            if parse_error:
                issues.append(parse_error)
            if phase.raw_wire is not None:
                text_parts = []
                if response:
                    for item in response.get("output", []):
                        if item.get("type") == "message":
                            text_parts.extend(part.get("text", "") for part in item.get("content", [])
                                              if part.get("type") == "output_text")
                matches = "".join(text_parts) == phase.raw_wire
                result["raw_wire_identity"].append({"phase": phase.phase, "matches": matches})
                if not matches:
                    issues.append(f"{phase.phase} raw wire differs from response text")
        replayed = replay_focused_results(artifact)
        replay_matches = replayed == artifact.resolved
        result["replay"] = "passed" if replay_matches else "resolved_mismatch"
        if not replay_matches:
            issues.append("focused offline replay resolved answer differs")
    except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        result["replay"] = f"failed:{type(exc).__name__}"
        issues.append(f"v8 source/replay verification: {type(exc).__name__}: {exc}")
    result["issues"] = issues
    return result


def build_report(strict: bool = False) -> dict[str, Any]:
    campaign = _json(CAMPAIGN_PATH)
    call_ledger: dict[str, list[dict[str, Any]]] = {
        "count": [], "generation": []}
    for kind, entries in call_ledger.items():
        for path in sorted(CALLS.glob(f"{kind}-*.json")):
            value = _json(path)
            value["ledger_file"] = path.name
            entries.append(value)
    limits = {"count": campaign["maximum_input_count_calls"],
              "generation": campaign["maximum_generation_calls"]}
    ledger_issues: list[str] = []
    for kind, limit in limits.items():
        if len(call_ledger[kind]) > limit:
            ledger_issues.append(f"{kind} ledger exceeds {limit} calls")

    review_index = _json(INDEX) if INDEX.exists() else {}
    runs_report: list[dict[str, Any]] = []
    all_issues: list[str] = list(ledger_issues)
    cost_total = Decimal(0)
    known_cost_total = Decimal(0)
    unknown_cost_calls: list[str] = []
    response_count = 0
    interrupted_reservations: list[dict[str, Any]] = []

    run_dirs = sorted(path for path in RUNS.iterdir() if path.is_dir()) if RUNS.exists() else []
    for run in run_dirs:
        run_issues: list[str] = []
        summary_path = run / "summary.json"
        summary = _json(summary_path) if summary_path.exists() else {}
        artifact_path = run / "artifact.json"
        artifact = _json(artifact_path) if artifact_path.exists() else None
        diagnostic_path = run / "diagnostic-artifact.json"
        diagnostic = _json(diagnostic_path) if diagnostic_path.exists() else None
        if artifact is None and isinstance(diagnostic, dict):
            artifact = diagnostic
        is_v7 = isinstance(artifact, dict) and artifact.get("contract_version") == "results-artifact-v7"
        is_v8 = isinstance(artifact, dict) and artifact.get("contract_version") == "results-artifact-v8"
        is_composition_diagnostic = (isinstance(diagnostic, dict) and
            diagnostic.get("contract") == "comparison-composition-diagnostic-v1")
        is_actual = is_v7 or is_v8
        if is_composition_diagnostic:
            source_ref = diagnostic.get("source_artifact")
            source_path = REPO / source_ref if isinstance(source_ref, str) else Path("__missing__")
        else:
            source_path = SOURCE / str(summary.get("case", "admitted")) / "artifact.json"
        source_hash = _sha_file(source_path) if source_path.exists() else None
        archive = _archive_integrity(run)
        if archive["status"] == "failed":
            run_issues.extend(archive["issues"])
        if is_v7 and source_hash:
            source_result = _v7_integrity(run, source_path, source_hash)
        elif is_v8 and source_hash:
            source_result = _v8_integrity(run, source_path, source_hash)
        elif source_hash and not is_composition_diagnostic:
            try:
                settings = _json(run / "settings.json")
                recorded = settings.get("source_sha256")
                source_result = {"source_sha256": {"recorded": recorded,
                    "current": source_hash, "matches": recorded == source_hash},
                    "canonical_source_matches": None, "replay": "prototype_replay_not_applicable",
                    "issues": [] if recorded == source_hash else
                        ["prototype run source hash differs from current source artifact"]}
            except (OSError, json.JSONDecodeError, TypeError, KeyError) as exc:
                source_result = {"issues": [f"prototype source verification: {type(exc).__name__}"]}
        elif is_composition_diagnostic:
            source_result = {"source_sha256": {"recorded": diagnostic.get("source_sha256"),
                "current": source_hash, "matches": diagnostic.get("source_sha256") == source_hash},
                "canonical_source_matches": None, "replay": "composition_only_not_applicable",
                "reused_selector": {"source_artifact": diagnostic.get("source_artifact"),
                    "new_selector_calls": diagnostic.get("new_selector_calls"),
                    "old_selector_request_digest": (diagnostic.get("old_selector_pass") or {}).get("request_digest")},
                "issues": [] if diagnostic.get("source_sha256") == source_hash else
                    ["composition diagnostic source hash differs from saved selector artifact"]}
        else:
            source_result = {"issues": ["original source artifact unavailable"]}
        if source_result:
            run_issues.extend(source_result["issues"])

        call_rows: list[dict[str, Any]] = []
        for label in _run_labels(run, call_ledger):
            count_request, count_req_error = _call_requests(run, "count", label)
            gen_request, gen_req_error = _call_requests(run, "generation", label)
            count_entry = next((x for x in call_ledger["count"]
                                if x.get("run_name") == run.name and x.get("label") == label), None)
            gen_entry = next((x for x in call_ledger["generation"]
                              if x.get("run_name") == run.name and x.get("label") == label), None)
            response, response_error = _response_from_call(run, "generation", label)
            if response is not None:
                response_count += 1
            usage = _usage_metrics(response)
            cost, cost_error = _cost(usage)
            if cost is not None:
                known_cost_total += Decimal(cost)
                cost_total += Decimal(cost)
            elif gen_entry is not None:
                unknown_cost_calls.append(f"{run.name}/{label}")
            checks: list[str] = []
            if count_entry is not None and count_request is not None:
                if _content_digest(count_request) != count_entry.get("request_digest"):
                    checks.append("count ledger digest differs from exact count request")
            elif count_entry is not None:
                checks.append(count_req_error or "count request missing")
            if gen_entry is not None and gen_request is not None:
                if _content_digest(gen_request) != gen_entry.get("request_digest"):
                    checks.append("generation ledger digest differs from exact SDK request")
            elif gen_entry is not None:
                checks.append(gen_req_error or "generation request missing")
            if gen_entry is not None and count_entry is None:
                checks.append("generation reservation has no preceding count reservation")
            if count_request is not None and gen_request is not None and \
                    count_request != _token_request(gen_request):
                checks.append("count request differs from token-bearing generation request")
            folder = run / label
            explicit_gen_failure = (folder / "generation-error.json").exists()
            explicit_count_failure = (folder / "count-error.json").exists()
            generation_entries_for_run = [entry for entry in call_ledger["generation"]
                                          if entry.get("run_name") == run.name]
            interruption, interruption_error = _verified_external_interruption(
                run, label, count_entry, count_request, generation_entries_for_run)
            if interruption_error:
                checks.append(interruption_error)
            if interruption is not None:
                interrupted_reservations.append({
                    "run_name": run.name, "label": label, "kind": "count",
                    "status": "accounted_interrupted", "reservation": interruption["reservation"],
                    "observed_failure_source": interruption["observed_failure_source"],
                    "observed_error": interruption["observed_error"],
                    "response_available": False, "generation_reservation_present": False,
                    "latency_claim": None, "billing_claim": None,
                    "disposition": interruption["disposition"],
                })
            attempt_for_call = _attempt_for_label(label, summary, artifact)
            if response_error:
                checks.append(response_error)
            gen_accounted = (response is not None or explicit_gen_failure or
                (attempt_for_call is not None and (attempt_for_call.get("writer_called") is True or
                 attempt_for_call.get("outcome") in {"api_error", "generation_error"})))
            count_accounted = (interruption is not None or
                (folder / "count-receipt.json").exists() or explicit_count_failure
                or (attempt_for_call is not None and
                    (attempt_for_call.get("input_token_receipt") is not None or
                     attempt_for_call.get("outcome") == "measurement_error")))
            count_status = ("interrupted_external" if interruption is not None else
                "failed_explicitly" if explicit_count_failure else
                "receipt_saved" if (folder / "count-receipt.json").exists() else
                "receipt_in_artifact" if attempt_for_call is not None and
                    attempt_for_call.get("input_token_receipt") is not None else
                "not_reserved" if count_entry is None else "dangling")
            generation_status = ("response_saved" if response is not None else
                "failed_explicitly" if explicit_gen_failure else
                "not_reserved" if gen_entry is None else "dangling")
            count_accounting = ("not_reserved" if count_entry is None else
                "interrupted_external" if interruption is not None else
                "accounted" if count_accounted else "dangling_reservation")
            generation_accounting = ("not_reserved" if gen_entry is None else
                "accounted" if gen_accounted else "dangling_reservation")
            status = ("accounted_interrupted" if count_accounting == "interrupted_external" and
                generation_accounting == "not_reserved" else
                "accounted" if count_accounting in {"accounted", "not_reserved"} and
                generation_accounting in {"accounted", "not_reserved"} else "dangling_reservation")
            if checks:
                run_issues.extend(f"{label}: {item}" for item in checks)
            call_rows.append({
                "label": label, "count_reserved": count_entry is not None,
                "generation_reserved": gen_entry is not None,
                "count_status": count_status,
                "generation_status": generation_status,
                "count_accounting": count_accounting,
                "generation_accounting": generation_accounting,
                "response_status": response.get("status") if response else None,
                "generation_timing": _generation_timing(run, label),
                "usage": usage, "estimated_generation_cost_usd": cost,
                "cost_unknown_reason": cost_error, "integrity_checks": checks,
                "accounting": status,
            })

        attempts = []
        if is_v7:
            for i, attempt in enumerate(artifact.get("attempts", []), 1):
                attempts.append({
                    "number": i, "phase": attempt.get("phase"), "outcome": attempt.get("outcome"),
                    "writer_called": attempt.get("writer_called"),
                    "count_receipt": attempt.get("input_token_receipt") is not None,
                    "writer_receipt": attempt.get("writer_receipt") is not None,
                    "returned_service_tier": attempt.get("returned_service_tier"),
                    "error": attempt.get("error"), "failure_subtype": attempt.get("failure_subtype"),
                })
        elif is_v8:
            for i, phase in enumerate(artifact.get("passes", []), 1):
                attempts.append({
                    "number": i, "phase": phase.get("phase"), "outcome": phase.get("outcome"),
                    "writer_called": phase.get("writer_called"),
                    "count_receipt": phase.get("input_token_receipt") is not None,
                    "writer_receipt": phase.get("writer_receipt") is not None,
                    "returned_service_tier": phase.get("returned_service_tier"),
                    "error": phase.get("error"), "failure_subtype": phase.get("failure_subtype"),
                })
        elif is_composition_diagnostic:
            phase = artifact.get("composer_pass") or {}
            attempts.append({
                "number": 1, "phase": "composition", "outcome": phase.get("outcome"),
                "writer_called": phase.get("writer_called"),
                "count_receipt": phase.get("input_token_receipt") is not None,
                "writer_receipt": phase.get("writer_receipt") is not None,
                "returned_service_tier": phase.get("returned_service_tier"),
                "error": phase.get("error"), "failure_subtype": phase.get("failure_subtype"),
            })
        else:
            prototype_attempts = summary.get("attempts", [])
            if not isinstance(prototype_attempts, list):
                prototype_attempts = []
            for i, attempt in enumerate(prototype_attempts, 1):
                attempts.append({
                    "number": i, "phase": attempt.get("phase"), "outcome": attempt.get("outcome"),
                    "writer_called": attempt.get("writer_called"),
                    "count_receipt": attempt.get("input_token_receipt") is not None,
                    "writer_receipt": attempt.get("writer_receipt") is not None,
                    "error": attempt.get("error"), "failure_subtype": attempt.get("failure_subtype"),
                })
        source_attempts = ([artifact.get("composer_pass", {})] if is_composition_diagnostic else
                           artifact.get("attempts", []) if is_v7 else
                           artifact.get("passes", []) if is_v8 else
                           summary.get("attempts", []) if isinstance(
                               summary.get("attempts", []), list) else [])
        for i, attempt in enumerate(source_attempts, 1):
            label = f"final-{i:02d}"
            if attempt.get("input_token_receipt") is not None and not any(
                    row.get("run_name") == run.name and row.get("label") == label
                    for row in call_ledger["count"]):
                run_issues.append(f"{label}: input count receipt has no campaign reservation")
            if attempt.get("writer_called") is True and not any(
                    row.get("run_name") == run.name and row.get("label") == label
                    for row in call_ledger["generation"]):
                run_issues.append(f"{label}: writer call has no campaign reservation")
        review = _review_for_run(run.name, review_index)
        if run_issues:
            all_issues.extend(f"{run.name}: {issue}" for issue in run_issues)
        prototype_seconds = (summary.get("results_completion_seconds") if not is_actual else None)
        actual_seconds = (summary.get("outer_results_completion_seconds") if is_actual else None)
        if not is_actual and prototype_seconds is not None:
            latency_scope = "prototype_results_completion_seconds; experimental harness scope, not actual V7/V8 runtime confirmation"
        else:
            latency_scope = summary.get("timing_scope")
        if is_v8:
            latency_scope = summary.get("timing_scope")
        if is_composition_diagnostic:
            profile = "focused-v3"
        elif is_v8:
            profile = summary.get("packet_profile") or "focused-v1"
        else:
            profile = (summary.get("packet_profile") or
                ("joined-v2" if is_v7 and
                 artifact.get("prepared", {}).get("packet", {}).get("format") ==
                 "decision-joined-v2" else "indexed-v1" if is_v7 else "lean-wire-prototype"))
        runs_report.append({
            "run_name": run.name, "case": summary.get("case"),
            "kind": ("actual_v8" if is_v8 else "actual_v7" if is_v7 else
                     "composition_diagnostic" if is_composition_diagnostic else "prototype"),
            "consumer_kind": "composition_diagnostic" if is_composition_diagnostic else None,
            "reused_selector_provenance": ({
                "source_artifact": diagnostic.get("source_artifact"),
                "source_sha256": diagnostic.get("source_sha256"),
                "request_digest": (diagnostic.get("old_selector_pass") or {}).get("request_digest"),
                "new_selector_calls": diagnostic.get("new_selector_calls"),
            } if is_composition_diagnostic else None),
            "packet_profile": profile,
            "packet_profile_provenance": summary.get("packet_profile_provenance"),
            "recorded_settings": _optional_json(run / "settings.json"),
            "source_snapshot_hashes": _optional_json(run / "source-snapshot.json"),
            "model": ((artifact or {}).get("config") or {}).get("model"),
            "attempts": attempts, "calls": call_rows,
            "generation_outcome": (artifact or {}).get("generation_outcome",
                                    summary.get("generation_outcome")),
            "validation_outcome": (artifact or {}).get("validation_outcome",
                                   summary.get("validation_outcome")),
            "delivery_outcome": (artifact or {}).get("delivery_outcome",
                                 summary.get("delivery_outcome")),
            "prototype_results_completion_seconds": prototype_seconds,
            "outer_results_completion_seconds": actual_seconds,
            "artifact_runtime_seconds": summary.get("artifact_runtime_seconds") if is_actual else None,
            "composition_diagnostic_seconds": diagnostic.get("composition_seconds")
                if is_composition_diagnostic else None,
            "timing_scope": latency_scope,
            "returned_service_tiers": (summary.get("returned_service_tiers") or
                [row.get("returned_service_tier") for row in attempts
                 if row.get("returned_service_tier")]),
            "review": review,
            "source": source_result,
            "archive": archive,
            "integrity_issues": run_issues,
            "run_error": _json(run / "run-error.json") if (run / "run-error.json").exists() else None,
        })

    for kind, entries in call_ledger.items():
        for entry in entries:
            key = f"{entry.get('run_name')}/{entry.get('label')}"
            if entry.get("run_name") not in {r["run_name"] for r in runs_report}:
                all_issues.append(f"{kind} reservation references missing run {key}")

    expected_cases = set(campaign.get("source_cases", []))
    manifest_paths = sorted(HERE.glob("confirmation*.json"))
    manifests: dict[str, dict[str, Any]] = {}
    for path in manifest_paths:
        try:
            value = _json(path)
            if isinstance(value, dict) and isinstance(value.get("runs"), list):
                manifests[path.name] = value
        except (OSError, json.JSONDecodeError):
            all_issues.append(f"confirmation manifest failed to parse: {path.name}")
    selected_manifest = campaign.get("final_confirmation")
    if not isinstance(selected_manifest, str) or not selected_manifest:
        selected_manifest = "confirmation.json"
    elif not selected_manifest.endswith(".json"):
        selected_manifest += ".json"
    selected_report = (_confirmation_summary(selected_manifest, manifests[selected_manifest],
                                             runs_report, expected_cases)
                       if selected_manifest in manifests else None)
    confirmation_summaries = [
        _confirmation_summary(filename, manifest, runs_report, expected_cases)
        for filename, manifest in manifests.items()]
    selected_is_final = selected_manifest in manifests
    for item in confirmation_summaries:
        item["selected_for_final_joint_count"] = item["filename"] == selected_manifest
    if selected_report is not None:
        selected_report["selected_for_final_joint_count"] = True

    total_calls = {kind: len(entries) for kind, entries in call_ledger.items()}
    dangling = [{"kind": kind, "run_name": entry.get("run_name"), "label": entry.get("label")}
                for kind, entries in call_ledger.items() for entry in entries
                if not any(call.get(f"{kind}_reserved") and
                           call.get(f"{kind}_accounting") in {"accounted", "interrupted_external"}
                           for row in runs_report if row["run_name"] == entry.get("run_name")
                           for call in row["calls"] if call.get("label") == entry.get("label"))]
    if strict and dangling:
        all_issues.append("strict verification found dangling call reservations")
    estimated_total = None if unknown_cost_calls else format(cost_total, "f")
    return {
        "report_version": "under20-report-v1",
        "campaign": {"model": campaign.get("model"), "call_limits": limits,
                     "reserved_calls": total_calls,
                     "remaining_calls": {kind: limits[kind] - total_calls[kind]
                                         for kind in limits},
                     "dangling_reservations": dangling,
                     "strict_verification": strict},
        "interrupted_reservations": interrupted_reservations,
        "pricing": {"rates_usd_per_million": {key: format(value, "f")
                    for key, value in RATES.items()},
                    "fast_priority_multiplier": "2",
                    "cost_method": "Generation Responses raw usage only; count endpoint and Codex billing excluded; unknown calls are never assigned zero."},
        "generation_cost": {"known_generation_cost_usd": format(known_cost_total, "f"),
                            "estimated_generation_cost_usd": estimated_total,
                            "unknown_cost_calls": unknown_cost_calls},
        "raw_response_count": response_count,
        "runs": runs_report,
        "confirmation": {"selected_final_manifest": selected_manifest,
                         "selected_manifest_present": selected_is_final,
                         "selected": selected_report,
                         "all_manifests": confirmation_summaries,
                         "joint_success": (selected_report["joint_success"]
                                           if selected_report else None),
                         "prototype_runs_excluded_from_joint_gate": True,
                         "joint_counts_scope": "Only the campaign-selected final_confirmation contributes to joint confirmation; earlier manifests remain individually visible."},
        "integrity_issues": all_issues,
        "verification_status": "failed" if all_issues or (strict and dangling) else
            "passed" if not dangling else "active_or_unresolved_reservations",
        "claim_limits": {
            "latency": "Prototype completion timings are separate from V7/V8 outer Results completion. Small saved-case evidence does not establish an SLA or population reliability.",
            "quality": "H/U/C come only from indexed independent review.json files. Mechanical checks and replay do not establish semantic quality.",
            "confirmation": "Joint success requires each manifest run to be actual V7 or V8, independently H/U passing, protocol clean, mechanically clean, delivered, and under 20 seconds; coverage is reported separately.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="require every reservation to have explicit evidence; fail on dangling reservations")
    args = parser.parse_args()
    report = build_report(strict=args.verify)
    METRICS.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"verification_status": report["verification_status"],
                      "reserved_calls": report["campaign"]["reserved_calls"],
                      "dangling_reservations": report["campaign"]["dangling_reservations"],
                      "integrity_issues": report["integrity_issues"],
                      "metrics": str(METRICS)}, indent=2))
    return 1 if args.verify and report["verification_status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
