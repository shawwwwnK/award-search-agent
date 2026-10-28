"""Offline metrics and integrity checks for the bounded Luna diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
CALLS = HERE / "calls"
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
TRANSPORT_KEYS = {"max_output_tokens", "store", "truncation", "stream"}
RATES = {"ordinary_input": Decimal("0.10"), "cached_input": Decimal("0.01"),
         "cache_write_input": Decimal("0.125"), "output": Decimal("0.50")}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value: Any) -> str:
    from award_agent.providers.contracts import content_digest

    return content_digest(value)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def base_request(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if key not in TRANSPORT_KEYS}


def response_usage(path: Path) -> dict[str, int]:
    raw = read(path)
    usage = raw.get("usage") or {}
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    idetails = usage.get("input_tokens_details") or {}
    odetails = usage.get("output_tokens_details") or {}
    return {"input_tokens": int(inp), "output_tokens": int(out),
            "cached_tokens": int(idetails.get("cached_tokens", 0)),
            "cache_write_tokens": int(idetails.get("cache_write_tokens", 0)),
            "reasoning_tokens": int(odetails.get("reasoning_tokens", 0))}


def usage_cost(usage: dict[str, int]) -> Decimal:
    ordinary = (usage["input_tokens"] - usage["cached_tokens"] -
                usage["cache_write_tokens"])
    if ordinary < 0:
        raise ValueError("cached and cache-write tokens exceed input tokens")
    return (Decimal(ordinary) * RATES["ordinary_input"] +
            Decimal(usage["cached_tokens"]) * RATES["cached_input"] +
            Decimal(usage["cache_write_tokens"]) * RATES["cache_write_input"] +
            Decimal(usage["output_tokens"]) * RATES["output"]) / Decimal(1_000_000)


def time_summary(values: list[float]) -> dict[str, float | int] | None:
    if not values:
        return None
    return {"n": len(values), "median_seconds": statistics.median(values),
            "minimum_seconds": min(values), "maximum_seconds": max(values)}


def public_call(call: dict[str, Any]) -> dict[str, Any]:
    """Keep an unfinished run visible without copying its potentially huge request."""
    fields = ("kind", "run_name", "label", "request_digest", "reserved_at_utc",
              "status", "input_tokens", "seconds", "timing", "usage",
              "estimated_cost_usd")
    result = {key: call[key] for key in fields if key in call}
    if "error" in call:
        error = call["error"]
        result["error"] = {key: error[key] for key in ("type", "elapsed_seconds")
                           if key in error} if isinstance(error, dict) else str(error)
    return result


def verify_source_snapshot(directory: Path, issues: list[str]) -> None:
    manifest = read(directory / "source-snapshot.json")
    archive_path = directory / "source-snapshot.zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for name, expected in manifest.items():
            if name not in names:
                issues.append(f"{directory.name}: snapshot file absent {name}")
                continue
            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if actual != expected:
                issues.append(f"{directory.name}: snapshot digest mismatch {name}")


def failure_note_is_accounted(directory: Path,
                             calls: list[dict[str, Any]]) -> bool:
    """A failure note is terminal only when its source and every paid call are retained."""
    note_path = directory / "failure-note.json"
    settings_path = directory / "settings.json"
    manifest_path = directory / "source-snapshot.json"
    archive_path = directory / "source-snapshot.zip"
    if not all(path.exists() for path in (note_path, settings_path,
                                          manifest_path, archive_path)):
        return False
    note = read(note_path)
    settings = read(settings_path)
    source_path = SOURCE / settings.get("case", "") / "artifact.json"
    if not source_path.exists() or sha256(source_path) != settings.get("source_sha256"):
        return False
    if not calls or any(call.get("status") not in {
            "complete", "error", "noncompleted_response", "failed_no_response"}
            for call in calls):
        return False
    if not any(call.get("kind") == "generation" and
               call.get("status") == "failed_no_response" for call in calls):
        return False
    # A transport timeout has no usable response receipt, so its elapsed Results
    # time and cost must remain unknown rather than being filled with the SDK limit.
    if note.get("results_completion_seconds") is not None:
        return False
    timeout_generations = [call for call in calls
                           if call.get("kind") == "generation" and
                           call.get("status") == "failed_no_response"]
    return not any("usage" in call or "estimated_cost_usd" in call
                   for call in timeout_generations)


def verify_failure_accounting_control() -> None:
    """Focused pure control: terminal timeout counts; a reserved call does not."""
    terminal = [
        {"kind": "count", "status": "complete"},
        {"kind": "generation", "status": "failed_no_response"},
    ]
    unfinished = [dict(terminal[0]),
                  {"kind": "generation", "status": "request_saved"}]
    assert all(call["status"] in {
        "complete", "error", "noncompleted_response", "failed_no_response"}
        for call in terminal)
    assert not all(call["status"] in {
        "complete", "error", "noncompleted_response", "failed_no_response"}
        for call in unfinished)


def check_artifact(directory: Path, issues: list[str]) -> str:
    """Recompute mechanical checks and resolution without any model/provider call."""
    sys.path.insert(0, str(REPO / "src"))
    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.presentation import resolve_workspace
    from award_agent.results.structured import (
        check_structured_document,
        prepare_structured_results,
        resolve_structured_document,
    )
    from award_agent.results.structured_contracts import (
        StructuredDocument,
        StructuredResultsArtifact,
    )

    settings = read(directory / "settings.json")
    source_dir = SOURCE / settings["case"]
    source_path = source_dir / "artifact.json"
    if sha256(source_path) != settings["source_sha256"]:
        issues.append(f"{directory.name}: saved source hash changed")
    source_artifact = StructuredResultsArtifact.model_validate_json(source_path.read_text())
    projection = source_artifact.evidence.source
    config = ResultsConfig.model_validate_json((source_dir / "config.json").read_text()).model_copy(
        update={"model": "gpt-6-luna", "timeout_seconds": 240.0,
                "max_output_tokens": 32768})
    prepared = prepare_structured_results(projection, config)
    evidence = resolve_workspace(projection)

    attempts = sorted(directory.glob("attempt-*.json"))
    selected_index = settings.get("selected_attempt")
    # settings are immutable invocation controls; selection is in summary.json.
    summary_path = directory / "summary.json"
    summary = read(summary_path) if summary_path.exists() else {}
    selected_index = summary.get("selected_attempt")
    for number, path in enumerate(attempts, 0):
        attempt = read(path)
        if attempt.get("document") is None:
            continue
        try:
            document = StructuredDocument.model_validate(attempt["document"])
            findings = check_structured_document(document, projection, prepared)
            expected = [finding.model_dump(mode="json") for finding in findings]
            if expected != attempt.get("findings"):
                issues.append(f"{directory.name}: attempt {number} findings differ on replay")
        except (ValueError, TypeError) as exc:
            issues.append(f"{directory.name}: attempt {number} cannot be rechecked ({type(exc).__name__})")

    resolved_path = directory / "resolved.json"
    if selected_index is None:
        if resolved_path.exists():
            issues.append(f"{directory.name}: has resolved output without selected attempt")
        return "unavailable"
    selected_path = directory / f"attempt-{selected_index + 1:02d}.json"
    if not selected_path.exists():
        issues.append(f"{directory.name}: selected attempt file missing")
        return "unavailable"
    selected = read(selected_path)
    if selected.get("document") is None:
        issues.append(f"{directory.name}: selected attempt has no document")
        return "unavailable"
    document = StructuredDocument.model_validate(selected["document"])
    findings = check_structured_document(document, projection, prepared)
    resolved = resolve_structured_document(document, prepared, evidence, findings)
    if not resolved_path.exists():
        issues.append(f"{directory.name}: resolved output missing")
        return "unavailable"
    saved_resolved = read(resolved_path)
    if resolved.model_dump(mode="json") != saved_resolved:
        issues.append(f"{directory.name}: resolved output differs on replay")
    return "annotated" if any(f.outcome == "failed" for f in findings) else "clean"


def inventory_calls(issues: list[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    counts = {"generation": 0, "count": 0}
    seen: set[tuple[str, str, str]] = set()
    for kind in ("count", "generation"):
        for ledger_path in sorted(CALLS.glob(f"{kind}-*.json")):
            row = read(ledger_path)
            counts[kind] += 1
            key = (kind, row.get("run_name", ""), row.get("label", ""))
            if key in seen:
                issues.append(f"duplicate reserved call {kind}:{key}")
            seen.add(key)
            _, run_name, label = key
            directory = RUNS / run_name / label
            call = {"kind": kind, "run_name": run_name, "label": label,
                    "request_digest": row.get("request_digest"),
                    "reserved_at_utc": row.get("reserved_at_utc"),
                    "status": "reserved_only"}
            req_name = "count-request.json" if kind == "count" else "generation-request.json"
            req_path = directory / req_name
            if not req_path.exists():
                issues.append(f"reserved call has no request {kind}:{key}")
            else:
                request = read(req_path)
                actual_digest = digest(request)
                if actual_digest != row.get("request_digest"):
                    issues.append(f"reservation/request digest mismatch {kind}:{key}")
                call["request"] = request
                call["status"] = "request_saved"
            if kind == "count":
                receipt_path = directory / "count-receipt.json"
                error_path = directory / "count-error.json"
                if receipt_path.exists():
                    receipt = read(receipt_path)
                    if receipt.get("request_digest") != call.get("request_digest"):
                        issues.append(f"count receipt/request digest mismatch {key}")
                    raw = receipt.get("raw_response") or {}
                    if raw.get("object") != "response.input_tokens":
                        issues.append(f"count response object invalid {key}")
                    if raw.get("input_tokens") != receipt.get("input_tokens"):
                        issues.append(f"count token value differs from receipt {key}")
                    timing = directory / "count-timing.json"
                    if timing.exists():
                        call["seconds"] = read(timing).get("full_response_seconds")
                    call.update(status="complete", input_tokens=receipt.get("input_tokens"))
                elif error_path.exists():
                    call.update(status="error", error=read(error_path))
                if req_path.exists():
                    call["request"] = read(req_path)
            else:
                response_path = directory / "response.json"
                error_path = directory / "generation-error.json"
                run_failure_path = RUNS / run_name / "failure-note.json"
                timing_path = directory / "generation-timing.json"
                if response_path.exists():
                    response = read(response_path)
                    timing = read(timing_path) if timing_path.exists() else {}
                    usage = response_usage(response_path)
                    if response.get("usage") != timing.get("usage"):
                        issues.append(f"generation response/timing usage mismatch {key}")
                    call.update(status="response_saved", response=response,
                        timing=timing, usage=usage, estimated_cost_usd=str(usage_cost(usage)))
                    if response.get("status") == "completed":
                        call["status"] = "complete"
                    else:
                        call["status"] = "noncompleted_response"
                elif error_path.exists():
                    call.update(status="error", error=read(error_path))
                elif run_failure_path.exists():
                    # Invocation was reserved and attempted, but transport ended
                    # before a response receipt was retained. Cost and elapsed
                    # response time remain unknown; never treat them as zero.
                    failure = read(run_failure_path)
                    call.update(status="failed_no_response",
                                error={"type": failure.get("exception"),
                                       "outcome": failure.get("outcome"),
                                       "results_completion_seconds": failure.get(
                                           "results_completion_seconds")})
            grouped.setdefault(run_name, []).append(call)

    for run_name, rows in grouped.items():
        by_label: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.get("kind") == "count":
                by_label[row["label"]] = row
        for row in rows:
            if row.get("kind") != "generation" or row.get("status") not in {
                    "response_saved", "complete", "noncompleted_response"}:
                continue
            count_row = by_label.get(row["label"])
            if count_row is None:
                issues.append(f"generation has no associated count {run_name}/{row['label']}")
                continue
            if base_request(row["request"]) != count_row.get("request"):
                issues.append(f"count/generation request mismatch {run_name}/{row['label']}")
    return grouped, counts


def summarize(*, strict: bool) -> dict[str, Any]:
    campaign = read(HERE / "campaign.json")
    issues: list[str] = []
    calls_by_run, call_counts = inventory_calls(issues)
    for kind, ceiling_key in (("generation", "maximum_generation_calls"),
                              ("count", "maximum_input_count_calls")):
        if call_counts[kind] > campaign[ceiling_key]:
            issues.append(f"{kind} call envelope exceeded")

    reviews_path = HERE / "reviews.json"
    reviews = read(reviews_path) if reviews_path.exists() else {}
    run_rows: list[dict[str, Any]] = []
    complete_run_paths = sorted(path for path in RUNS.iterdir()
                                if path.is_dir() and (path / "summary.json").exists())
    all_run_names = sorted(path.name for path in RUNS.iterdir() if path.is_dir())
    unknown_reviews = sorted(set(reviews) - set(all_run_names))
    if unknown_reviews:
        issues.append(f"quality reviews reference unknown runs: {unknown_reviews}")

    for directory in complete_run_paths:
        settings = read(directory / "settings.json")
        summary = read(directory / "summary.json")
        run_calls = calls_by_run.get(directory.name, [])
        for call in run_calls:
            if call["status"] in {"reserved_only", "request_saved", "response_saved"} and strict:
                issues.append(f"incomplete call at final verification {directory.name}/{call['label']}")
        source_path = SOURCE / settings["case"] / "artifact.json"
        if sha256(source_path) != settings.get("source_sha256"):
            issues.append(f"{directory.name}: source hash changed")
        before_snapshot_issues = len(issues)
        verify_source_snapshot(directory, issues)
        snapshot_verified = len(issues) == before_snapshot_issues
        mechanical = check_artifact(directory, issues)

        count_calls = [c for c in run_calls if c["kind"] == "count"]
        gen_calls = [c for c in run_calls if c["kind"] == "generation"]
        worker_gen = [c for c in gen_calls if c["label"].startswith("worker-")]
        final_gen = [c for c in gen_calls if c["label"].startswith("final-")]
        worker_counts = [c for c in count_calls if c["label"].startswith("worker-")]
        final_counts = [c for c in count_calls if c["label"].startswith("final-")]
        all_usage = [c["usage"] for c in gen_calls if "usage" in c]
        total_usage = {key: sum(row.get(key, 0) for row in all_usage)
                       for key in ("input_tokens", "output_tokens", "cached_tokens",
                                   "cache_write_tokens", "reasoning_tokens")}
        worker_usage = [c["usage"] for c in worker_gen if "usage" in c]
        worker_token_totals = {key: sum(row.get(key, 0) for row in worker_usage)
                               for key in ("input_tokens", "output_tokens", "reasoning_tokens")}
        costs = [Decimal(c["estimated_cost_usd"]) for c in gen_calls
                 if "estimated_cost_usd" in c]
        unknown_cost_calls = [c for c in gen_calls if c["status"] == "failed_no_response"]
        seconds = [c.get("timing", {}).get("full_response_seconds") for c in gen_calls
                   if c.get("timing", {}).get("full_response_seconds") is not None]
        first_texts = [c.get("timing", {}).get("first_text_seconds") for c in gen_calls
                       if c.get("timing", {}).get("first_text_seconds") is not None]
        selected_answer = (summary.get("selected_attempt") is not None and
                           (directory / "resolved.json").exists())
        run_failure_path = directory / "worker-failure.json"
        worker_failure = (summary.get("generation_outcome") == "worker_failure" or
                          run_failure_path.exists())
        candidate_version = settings.get("candidate_version")
        candidate_version = ("none" if settings["variant"] == "original" else
                             candidate_version or "v1")
        row = {"run_name": directory.name, "case": settings["case"],
            "variant": settings["variant"], "effort": settings["effort"],
            "candidate_version": candidate_version,
            "worker_effort": settings.get("worker_effort"),
            "mechanical_replay": mechanical,
            "answer_available": selected_answer,
            "worker_failure_recorded": worker_failure,
            "worker_failure": (read(run_failure_path) if run_failure_path.exists() else None),
            "quality_review": reviews.get(directory.name, "not reviewed"),
            "results_completion_seconds": summary.get("results_completion_seconds"),
            "preparation_seconds": summary.get("preparation_seconds"),
            "worker_critical_path_seconds": summary.get("worker_wall_seconds"),
            "final_count_phase_seconds": summary.get("final_count_seconds"),
            "worker_count_endpoint_seconds_sum": sum((c.get("seconds") or 0)
                                                      for c in worker_counts),
            "final_count_endpoint_seconds_sum": sum((c.get("seconds") or 0)
                                                    for c in final_counts),
            "check_seconds": summary.get("check_seconds"),
            "resolution_seconds": summary.get("resolution_seconds"),
            "final_generation_seconds_sum": sum((c.get("timing", {}).get(
                "full_response_seconds") or 0) for c in final_gen),
            "worker_generation_seconds_sum": sum((c.get("timing", {}).get(
                "full_response_seconds") or 0) for c in worker_gen),
            "generation_call_details": [{"label": c["label"],
                "first_text_seconds": c.get("timing", {}).get("first_text_seconds"),
                "full_response_seconds": c.get("timing", {}).get("full_response_seconds"),
                "status": c.get("status"), "usage": c.get("usage")}
                for c in gen_calls],
            "worker_duration_interpretation": "Concurrent worker durations are reported separately and are not summed into Results wall time.",
            "count_calls": len(count_calls), "generation_calls": len(gen_calls),
            "corrections": sum(1 for a in directory.glob("attempt-*.json")
                               if read(a).get("phase") == "correction"),
            "input_count_receipts": summary.get("input_counts", []),
            "count_call_details": [{"label": c["label"], "status": c["status"],
                "input_tokens": c.get("input_tokens"), "endpoint_seconds": c.get("seconds")}
                for c in count_calls],
            "generation_usage": total_usage,
            "worker_generation_usage": worker_token_totals,
            "estimated_generation_cost_usd": (None if unknown_cost_calls else
                                               str(sum(costs, Decimal(0)))),
            "known_generation_cost_usd": str(sum(costs, Decimal(0))),
            "unknown_cost_generation_calls": [c["label"] for c in unknown_cost_calls],
            "pricing_rates_usd_per_million": {k: str(v) for k, v in RATES.items()},
            "generation_response_count": len(seconds),
            "generation_first_text_count": len(first_texts),
            "generation_outcome": summary.get("generation_outcome"),
            "validation_outcome": summary.get("validation_outcome"),
            "selected_attempt": summary.get("selected_attempt"),
            "failed_findings": summary.get("failed_findings", []),
            "archive_source_snapshot_verified": snapshot_verified}
        run_rows.append(row)

    # Groups with only partial calls remain visible so failed reservations do not vanish.
    summarized_names = {row["run_name"] for row in run_rows}
    for name in all_run_names:
        if name not in summarized_names:
            run_dir = RUNS / name
            failure_path = run_dir / "failure-note.json"
            if failure_path.exists():
                failure = read(failure_path)
                failure_settings = read(run_dir / "settings.json")
                failure_version = failure_settings.get("candidate_version")
                failure_version = ("none" if failure_settings.get("variant") == "original"
                                   else failure_version or "v1")
                source_path = SOURCE / failure_settings["case"] / "artifact.json"
                before_snapshot_issues = len(issues)
                verify_source_snapshot(run_dir, issues)
                source_integrity = sha256(source_path) == failure_settings.get("source_sha256")
                if not source_integrity:
                    issues.append(f"{name}: saved source hash changed")
                run_rows.append({"run_name": name,
                    "case": failure_settings.get("case"),
                    "variant": failure_settings.get("variant"),
                    "candidate_version": failure_version,
                    "effort": failure_settings.get("effort"),
                    "status": failure.get("outcome", "failed_attempt"),
                    "exception": failure.get("exception"),
                    "results_completion_seconds": failure.get("results_completion_seconds"),
                    "estimated_generation_cost_usd": None,
                    "cost_status": "unknown_no_response_usage",
                    "first_text_seconds": None,
                    "mechanical_replay": "unavailable_no_document",
                    "quality_review": reviews.get(name, "not reviewed"),
                    "archive_source_snapshot_verified": len(issues) == before_snapshot_issues,
                    "source_sha256_verified": source_integrity,
                    "failure_note": failure,
                    "calls": [public_call(c) for c in calls_by_run.get(name, [])]})
            else:
                run_rows.append({"run_name": name, "status": "incomplete_run_no_summary",
                                 "calls": [public_call(c) for c in calls_by_run.get(name, [])]})

    for run_name in all_run_names:
        if not any(c.get("run_name") == run_name for c in run_rows):
            issues.append(f"run directory has no call ledger entries {run_name}")
    if strict:
        verify_failure_accounting_control()
        for directory in RUNS.iterdir():
            if (directory.is_dir() and not (directory / "summary.json").exists()
                    and not (directory / "failure-note.json").exists()):
                issues.append(f"unfinished run directory {directory.name}")
        accounted_names = {path.name for path in complete_run_paths}
        for directory in RUNS.iterdir():
            if not directory.is_dir() or not (directory / "failure-note.json").exists():
                continue
            run_calls = calls_by_run.get(directory.name, [])
            if failure_note_is_accounted(directory, run_calls):
                before_snapshot_issues = len(issues)
                verify_source_snapshot(directory, issues)
                if len(issues) == before_snapshot_issues:
                    accounted_names.add(directory.name)
            else:
                issues.append(f"failure note is not fully accounted {directory.name}")
        if accounted_names != set(all_run_names):
            issues.append("some run directories are not complete or terminally accounted")

    arms: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in run_rows:
        version = row.get("candidate_version", "none")
        arm = (str(row.get("variant", "unknown")), str(row.get("effort", "unknown")),
               str(version))
        arms.setdefault(arm, []).append(row)
    arm_rows: list[dict[str, Any]] = []
    for (variant, effort, version), rows in sorted(arms.items()):
        answered = [row for row in rows if row.get("answer_available") is True]
        wall = [float(row["results_completion_seconds"]) for row in answered
                if row.get("results_completion_seconds") is not None]
        quality_wall = [float(row["results_completion_seconds"]) for row in answered
                        if row.get("results_completion_seconds") is not None and
                        row.get("quality_review") in ("pass", "pass_minor")]
        failures = [{"run_name": row["run_name"],
                     "status": row.get("status") or row.get("generation_outcome"),
                     "worker_failure": row.get("worker_failure")}
                    for row in rows if row.get("answer_available") is not True]
        arm_rows.append({"variant": variant, "effort": effort,
            "candidate_version": version, "runs": len(rows),
            "answers_available": len(answered),
            "completed_answer_wall_seconds": time_summary(wall),
            "quality_passing_answer_wall_seconds": time_summary(quality_wall),
            "worker_failures": sum(1 for row in rows if row.get("worker_failure")),
            "failed_or_unavailable_runs": failures,
            "cost_limit": "Included in per-run totals; not inferred for no-response timeouts."})

    complete_wall = [row["results_completion_seconds"] for row in run_rows
                     if row.get("results_completion_seconds") is not None and
                     row.get("answer_available") is True and
                     row.get("quality_review") in ("pass", "pass_minor")]
    report = {"campaign": campaign, "campaign_call_counts": call_counts,
        "arms": arm_rows,
        "runs": run_rows,
        "quality_passing_wall_seconds": complete_wall,
        "quality_passing_wall_summary": ({"median_seconds": statistics.median(complete_wall),
            "minimum_seconds": min(complete_wall), "maximum_seconds": max(complete_wall)}
            if complete_wall else None),
        "all_runs_have_quality_review": all(row.get("quality_review") != "not reviewed"
                                             for row in run_rows),
        "integrity_issues": issues,
        "verification_status": "passed" if not issues else "issues_found",
        "cost_estimate_limit": "Estimated from saved generation receipts only; count endpoint pricing and Codex work excluded; not an invoice.",
        "quality_limit": "Mechanical replay/check outcomes are distinct from independent source/composition review. No verdict is inferred when reviews.json is absent.",
        "latency_limit": "Results-only request path from saved projection; not intent/planning/provider workflow or a numerical SLA. First response text is not a rendered usable answer."}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true",
                        help="fail unless all current runs and reserved calls are complete and replay cleanly")
    args = parser.parse_args()
    report = summarize(strict=args.verify)
    (HERE / "metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(args.verify and bool(report["integrity_issues"]))


if __name__ == "__main__":
    raise SystemExit(main())
