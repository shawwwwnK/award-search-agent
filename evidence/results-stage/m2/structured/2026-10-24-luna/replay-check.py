"""Reproduce deterministic replay and receipt integrity checks for the M2 campaign."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from award_agent.results.structured import _bound_document, replay_structured_results
from award_agent.results.structured_contracts import StructuredDocument, StructuredResultsArtifact
from award_agent.providers.contracts import content_digest


REPO = Path(__file__).resolve().parents[5]
ROOT = Path(__file__).resolve().parent
CASES = ("admitted", "conditional", "incomplete")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def worker(case: str, round_number: int, seed: int) -> dict[str, Any]:
    directory = ROOT / f"round-{round_number}" / case
    artifact_path = directory / "artifact.json"
    artifact_bytes_before = artifact_path.read_bytes()
    artifact = StructuredResultsArtifact.model_validate_json(artifact_bytes_before)
    source_path = (REPO / "evidence/results-stage/m2/compact-input/2026-10-20-luna"
                   / case / "artifact.json")
    source_bytes_before = source_path.read_bytes()

    replayed = replay_structured_results(artifact)
    recorded = artifact.resolved
    if replayed != recorded:
        raise AssertionError("resolved object differs from deterministic replay")
    if replayed is None or artifact.resolved_digest is None:
        raise AssertionError("delivered campaign artifact lacks resolved answer/digest")
    if content_digest(replayed.model_dump(mode="json")) != artifact.resolved_digest:
        raise AssertionError("resolved digest differs from replayed answer")

    source_projection = artifact.evidence.source
    eligible_ids = [item.candidate_id for item in source_projection.view.alternatives
                    if item.status in {"admitted", "conditional"}]
    workspace_ids = [journey.candidate_id for journey in artifact.evidence.journeys]
    group_member_ids = [member for group in artifact.evidence.groups for member in group.member_ids]
    if Counter(eligible_ids) != Counter(workspace_ids) or Counter(workspace_ids) != Counter(group_member_ids):
        raise AssertionError("eligible source/workspace/group journey IDs differ")
    if any(count != 1 for ids in (eligible_ids, workspace_ids, group_member_ids)
           for count in Counter(ids).values()):
        raise AssertionError("eligible journey IDs are not unique exactly once")

    source_dates = {item.observation_id: item.departure_date
                    for item in source_projection.view.components}
    v2_dates_checked = 0
    for component in artifact.evidence.components:
        if hasattr(component, "departure_date"):
            if component.departure_date != source_dates.get(component.observation_id):
                raise AssertionError(f"workspace v2 date mismatch: {component.observation_id}")
            v2_dates_checked += 1
    for block in recorded.blocks:
        component = block.component
        if component is not None and hasattr(component, "departure_date") and \
                component.departure_date != source_dates.get(component.observation_id):
            raise AssertionError(f"resolved v2 date mismatch: {component.observation_id}")

    if source_bytes_before != source_path.read_bytes():
        raise AssertionError("source fixture bytes changed during replay")
    if artifact_bytes_before != artifact_path.read_bytes():
        raise AssertionError("saved artifact bytes changed during replay")

    return {
        "case": case,
        "round": round_number,
        "seed": seed,
        "replay_equal": True,
        "resolved_digest": artifact.resolved_digest,
        "replayed_digest": content_digest(replayed.model_dump(mode="json")),
        "eligible_journeys": len(eligible_ids),
        "workspace_journeys": len(workspace_ids),
        "group_members": len(group_member_ids),
        "source_sha256_unchanged": sha256(source_bytes_before),
        "artifact_sha256_unchanged": sha256(artifact_bytes_before),
        "v2_component_dates_checked": v2_dates_checked,
        "resolved_component_dates_checked": sum(block.component is not None
                                                   for block in recorded.blocks),
    }


def check_campaign() -> dict[str, Any]:
    artifact_records: list[dict[str, Any]] = []
    expected_calls: Counter[tuple[str, str, int]] = Counter()
    expected_token_totals = Counter()
    model_responses = 0
    for round_number in (1, 2, 3):
        for case in CASES:
            directory = ROOT / f"round-{round_number}" / case
            artifact = StructuredResultsArtifact.model_validate_json(
                (directory / "artifact.json").read_bytes())
            summary = read_json(directory / "summary.json")
            if summary["generation_calls"] != sum(a.writer_called for a in artifact.attempts):
                raise AssertionError(f"generation call summary mismatch: {round_number}/{case}")
            count_receipts = [a for a in artifact.attempts if a.input_token_receipt is not None]
            writer_receipts = [a for a in artifact.attempts if a.writer_receipt is not None]
            if summary["input_count_calls"] != len(count_receipts):
                raise AssertionError(f"count call summary mismatch: {round_number}/{case}")
            for attempt in artifact.attempts:
                if attempt.writer_called:
                    expected_calls[("generation", case, round_number)] += 1
                if attempt.input_token_receipt is not None:
                    expected_calls[("count", case, round_number)] += 1
            for number, attempt in enumerate(count_receipts, start=1):
                receipt_path = directory / f"{number:02d}-count.json"
                if read_json(receipt_path) != attempt.input_token_receipt.model_dump(mode="json"):
                    raise AssertionError(f"count receipt mismatch: {round_number}/{case}/{number}")
                request = read_json(directory / f"{number:02d}-request.json")
                if content_digest(request) != attempt.input_token_receipt.request_digest:
                    raise AssertionError(f"count request digest mismatch: {round_number}/{case}/{number}")
            for number, attempt in enumerate(writer_receipts, start=1):
                receipt = attempt.writer_receipt
                assert receipt is not None
                recorded_receipt = read_json(directory / f"{number:02d}-writer.json")
                if recorded_receipt != receipt.model_dump(mode="json"):
                    raise AssertionError(f"writer receipt mismatch: {round_number}/{case}/{number}")
                response = json.loads(receipt.raw_response)
                usage = response.get("usage")
                if response.get("status") != "completed" or not isinstance(usage, dict):
                    raise AssertionError("model response lacks completed status/usage")
                recorded_usage = {key: receipt.usage.get(key) for key in
                                  ("input_tokens", "output_tokens", "total_tokens")}
                returned_usage = {key: usage.get(key) for key in
                                  ("input_tokens", "output_tokens", "total_tokens")}
                if returned_usage != recorded_usage:
                    raise AssertionError("raw model usage differs from persisted usage receipt")
                returned_text = "".join(
                    node.get("text", "")
                    for output in response.get("output", [])
                    for node in output.get("content", [])
                    if node.get("type") == "output_text"
                )
                if not returned_text:
                    raise AssertionError("model response has no returned output text")
                if attempt.document is None or _bound_document(
                        artifact.prepared,
                        StructuredDocument.model_validate_json(returned_text)) != attempt.document:
                    raise AssertionError("raw model returned document differs after alias binding")
                expected_token_totals["writer_input"] += usage.get("input_tokens", 0)
                expected_token_totals["writer_output"] += usage.get("output_tokens", 0)
                expected_token_totals["writer_total"] += usage.get("total_tokens", 0)
                details = usage.get("input_tokens_details", {})
                expected_token_totals["writer_cached_input"] += details.get("cached_tokens", 0)
                expected_token_totals["writer_cache_write_input"] += details.get(
                    "cache_write_tokens", 0)
                expected_token_totals["writer_reasoning_output"] += usage.get(
                    "output_tokens_details", {}).get("reasoning_tokens", 0)
                model_responses += 1
            for attempt in count_receipts:
                expected_token_totals["measured_input"] += attempt.input_token_receipt.input_tokens
            artifact_records.append({"case": case, "round": round_number,
                                     "generation_calls": len(writer_receipts),
                                     "count_calls": len(count_receipts),
                                     "generation_receipts": len(writer_receipts),
                                     "count_receipts": len(count_receipts)})

    reservations = Counter()
    for kind in ("generation", "count"):
        for path in sorted((ROOT / "calls").glob(f"{kind}-*.json")):
            item = read_json(path)
            if item.get("kind") != kind or item.get("status") != "reserved_before_invocation":
                raise AssertionError(f"invalid immutable reservation: {path.name}")
            reservations[(kind, item["case"], item["round"])] += 1
    if reservations != expected_calls:
        raise AssertionError(f"reservation counts differ: expected={expected_calls}, got={reservations}")

    round3 = [ROOT / "round-3" / case for case in CASES]
    configs = [read_json(path / "config.json") for path in round3]
    if not (configs[0] == configs[1] == configs[2]):
        raise AssertionError("round 3 configs differ")
    snapshots = [read_json(path / "source-snapshot.json") for path in round3]
    snapshot_hashes = [sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False).encode()) for snapshot in snapshots]
    if len(set(snapshot_hashes)) != 1:
        raise AssertionError("round 3 source-snapshot.json contents differ")

    return {
        "artifacts": artifact_records,
        "campaign_reservations": {f"{kind}/{case}/round-{round_number}": count
                                   for (kind, case, round_number), count in sorted(reservations.items())},
        "model_responses_with_usage": model_responses,
        "actual_model_usage_tokens": dict(expected_token_totals),
        "round3_configs_equal": True,
        "round3_source_snapshot_hashes_equal": True,
        "round3_source_snapshot_sha256": snapshot_hashes[0],
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        print(json.dumps(worker(sys.argv[2], int(sys.argv[3]), int(sys.argv[4])), sort_keys=True))
        return 0
    sys.path.insert(0, str(REPO / "src"))
    # Imports above need the project source tree for direct invocation.
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for seed in (11, 23, 37):
        for round_number in (1, 2, 3):
            for case in CASES:
                environment = dict(os.environ)
                environment["PYTHONHASHSEED"] = str(seed)
                environment["PYTHONPATH"] = str(REPO / "src")
                process = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve()), "--worker", case,
                     str(round_number), str(seed)], cwd=REPO, env=environment,
                    capture_output=True, text=True, check=False)
                if process.returncode:
                    errors.append({"case": case, "round": round_number, "seed": seed,
                                   "returncode": process.returncode,
                                   "stderr": process.stderr.strip()})
                else:
                    results.append(json.loads(process.stdout))
    summary: dict[str, Any] = {
        "command": "PYTHONPATH=src .venv/bin/python "
                   "evidence/results-stage/m2/structured/2026-10-24-luna/replay-check.py",
        "fresh_processes_requested": 27,
        "fresh_processes_passed": len(results),
        "fresh_processes_failed": errors,
        "replay_checks_passed": len(results),
        "replay_checks_failed": len(errors),
        "checks_per_process": ["artifact parse", "exact replay equality and digest",
                               "eligible/workspace/group identity and uniqueness",
                               "v2 component departure-date source equality",
                               "source and artifact byte immutability"],
        "process_results": results,
    }
    if errors:
        (ROOT / "structured-replay.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return 1
    campaign = check_campaign()
    summary["campaign_receipt_audit"] = campaign
    summary["campaign_reconciliation_groups_passed"] = 4
    summary["assertion_groups_passed"] = 27 + 4
    summary["assertion_groups_failed"] = 0
    (ROOT / "structured-replay.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (ROOT / "verification-summary.json").write_text(json.dumps({
        "status": "passed",
        "command": summary["command"],
        "fresh_processes": 27,
        "replay_checks_passed": 27,
        "replay_checks_failed": 0,
        "hash_seeds": [11, 23, 37],
        "artifacts": 9,
        "assertion_groups_passed": 31,
        "assertion_groups_failed": 0,
        "campaign_reconciliation_groups_passed": 4,
        "campaign_audit": campaign,
        "limits": ["Saved local artifacts only; no live model/provider calls.",
                   "Audit checks artifact/source replay and recorded receipts, not semantic truth of model-authored prose."],
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"fresh_processes_passed": len(results), "errors": errors,
                      "campaign_audit": campaign}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
