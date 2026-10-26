"""Audit saved live campaign receipts and source-version replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, cast

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
CASES = ("admitted", "conditional", "incomplete")
SAVED_INPUTS = REPO / "evidence/results-stage/m2/compact-input/2026-10-20-luna"
ORIGINAL = ("evidence/results-stage/m2/structured/2026-10-24-luna",
            "evidence/results-stage/m2/compact-input/2026-10-20-luna")


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replay_worker(artifact_path: Path, seed: int, source_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(source_root))
    from award_agent.providers.contracts import content_digest
    from award_agent.ranking.projection_contracts import (
        SolutionProjection,
    )
    from award_agent.results.structured import (
        _bound_document,
        replay_structured_results,
    )
    from award_agent.results.structured_contracts import (
        StructuredDocument,
        StructuredResultsArtifact,
    )

    artifact = StructuredResultsArtifact.model_validate_json(artifact_path.read_bytes())
    replayed = replay_structured_results(artifact)
    if replayed != artifact.resolved or replayed is None or artifact.resolved_digest is None:
        raise AssertionError("saved result differs from source-version replay")
    if content_digest(replayed.model_dump(mode="json")) != artifact.resolved_digest:
        raise AssertionError("resolved digest mismatch")

    raw_tokens: Counter[str] = Counter()
    writer_receipts = 0
    for attempt in artifact.attempts:
        receipt = attempt.writer_receipt
        if receipt is None:
            continue
        writer_receipts += 1
        if receipt.raw_response is None:
            raise AssertionError("writer receipt lacks raw response")
        response = json.loads(receipt.raw_response)
        usage = response.get("usage")
        if response.get("status") != "completed" or not isinstance(usage, dict):
            raise AssertionError("writer receipt lacks completed response and usage")
        for key, value in receipt.usage.items():
            if usage.get(key) != value:
                raise AssertionError(f"raw response/receipt usage differs at {key}")
        text = "".join(node.get("text", "") for output in response.get("output", [])
                       for node in output.get("content", []) if node.get("type") == "output_text")
        if not text or attempt.document is None:
            raise AssertionError("writer receipt lacks document")
        if _bound_document(artifact.prepared, StructuredDocument.model_validate_json(text)) != attempt.document:
            raise AssertionError("raw writer document differs after alias binding")
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            raw_tokens[key] += usage.get(key, 0)

    eligible = [item.candidate_id for item in artifact.evidence.source.view.alternatives
                if item.status in {"admitted", "conditional"}]
    workspace = [item.candidate_id for item in artifact.evidence.journeys]
    grouped = [member for group in artifact.evidence.groups for member in group.member_ids]
    if Counter(eligible) != Counter(workspace) or Counter(workspace) != Counter(grouped):
        raise AssertionError("source, workspace and group IDs differ")
    if any(count != 1 for rows in (eligible, workspace, grouped) for count in Counter(rows).values()):
        raise AssertionError("journey identity is missing or duplicated")

    count_index = 0
    for attempt in artifact.attempts:
        count_receipt = attempt.input_token_receipt
        if count_receipt is None:
            continue
        count_index += 1
        directory = artifact_path.parent
        if read(directory / f"{count_index:02d}-count.json") != count_receipt.model_dump(mode="json"):
            raise AssertionError("saved input count receipt mismatch")
        request = read(directory / f"{count_index:02d}-request.json")
        if content_digest(request) != count_receipt.request_digest:
            raise AssertionError("saved input count request digest mismatch")

    source_path = SAVED_INPUTS / artifact_path.parent.name / "artifact.json"
    source_bytes = source_path.read_bytes()
    source_projection = SolutionProjection.model_validate_json(
        json.dumps(json.loads(source_bytes)["projection"]))
    source_receipt = read(artifact_path.parent / "source-receipt.json")
    if sha(source_bytes) != source_receipt["source_sha256"]:
        raise AssertionError("saved source receipt does not match input bytes")
    if source_projection.receipt.view_digest != source_receipt["source_digest"]:
        raise AssertionError("saved source receipt digest differs from projection")
    if artifact.evidence.source.receipt.view_digest != source_receipt["source_digest"]:
        raise AssertionError("artifact projection digest differs from source receipt")

    return {"artifact": str(artifact_path), "seed": seed, "replay_equal": True,
            "resolved_digest": artifact.resolved_digest, "eligible": len(eligible),
            "workspace": len(workspace), "group_members": len(grouped),
            "writer_responses": writer_receipts, "count_responses": count_index,
            "writer_tokens": dict(raw_tokens),
            "failed_mechanical_findings": sum(f.outcome == "failed" for f in replayed.findings)}


def replay_archived(artifact: Path, seed: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="results-source-replay-") as temp_name:
        root = Path(temp_name)
        source_root = root / "src"
        shutil.copytree(REPO / "src/award_agent", source_root / "award_agent")
        with zipfile.ZipFile(artifact.parent / "source-snapshot.zip") as archive:
            for name in archive.namelist():
                if name.startswith("src/award_agent/results/") and name.endswith(".py"):
                    target = source_root / name.removeprefix("src/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(seed)
        env["PYTHONPATH"] = str(source_root)
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker",
                                 str(artifact), str(seed), str(source_root)], cwd=REPO,
                                env=env, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return cast(dict[str, Any], json.loads(result.stdout))


def audit(root: Path, final_round: int | None) -> dict[str, Any]:
    paths = sorted(path for round_dir in root.glob("round-*") for case in CASES
                   if (path := round_dir / case / "artifact.json").is_file())
    if not paths:
        raise ValueError("campaign contains no artifacts")
    expected_calls: Counter[tuple[str, str, int]] = Counter()
    output = []
    artifact_accounting = []
    for artifact_path in paths:
        directory = artifact_path.parent
        artifact_bytes_before = artifact_path.read_bytes()
        source_bytes_before = (SAVED_INPUTS / directory.name / "artifact.json").read_bytes()
        snapshot = read(directory / "source-snapshot.json")
        with zipfile.ZipFile(directory / "source-snapshot.zip") as archive:
            if set(archive.namelist()) != set(snapshot):
                raise AssertionError(f"archive paths differ from snapshot: {directory}")
            for name, expected_hash in snapshot.items():
                if sha(archive.read(name)) != expected_hash:
                    raise AssertionError(f"archived source hash mismatch: {name}")

        artifact = read(artifact_path)
        if artifact["resolved"] != read(directory / "resolved.json"):
            raise AssertionError(f"artifact and resolved.json differ: {directory}")
        attempts = artifact["attempts"]
        summary = read(directory / "summary.json")
        generation_calls = sum(bool(attempt.get("writer_called")) for attempt in attempts)
        count_calls = sum(attempt.get("input_token_receipt") is not None for attempt in attempts)
        if summary["generation_calls"] != generation_calls or summary["input_count_calls"] != count_calls:
            raise AssertionError(f"summary call totals differ: {directory}")
        rd = int(directory.parent.name.removeprefix("round-"))
        expected_calls[("generation", directory.name, rd)] += generation_calls
        expected_calls[("count", directory.name, rd)] += count_calls
        for kind, suffix, key in (("writer", "writer", "writer_receipt"),
                                  ("count", "count", "input_token_receipt")):
            selected = [attempt[key] for attempt in attempts if attempt.get(key) is not None]
            for index, saved in enumerate(selected, start=1):
                if read(directory / f"{index:02d}-{suffix}.json") != saved:
                    raise AssertionError(f"{kind} receipt differs from artifact: {directory}")
        writer_input = sum(attempt["writer_receipt"].get("usage", {}).get("input_tokens", 0)
                           for attempt in attempts if attempt.get("writer_receipt") is not None)
        writer_output = sum(attempt["writer_receipt"].get("usage", {}).get("output_tokens", 0)
                            for attempt in attempts if attempt.get("writer_receipt") is not None)
        if writer_input != summary["writer_input_tokens"] or writer_output != summary["writer_output_tokens"]:
            raise AssertionError(f"writer token totals differ from run summary: {directory}")
        artifact_accounting.append({"artifact": str(artifact_path),
                                    "generations": generation_calls,
                                    "input_counts": count_calls,
                                    "writer_input_tokens": writer_input,
                                    "writer_output_tokens": writer_output})
        for seed in (11, 23, 37):
            output.append(replay_archived(artifact_path, seed))
        if artifact_bytes_before != artifact_path.read_bytes():
            raise AssertionError(f"campaign artifact changed during replay: {directory}")
        if source_bytes_before != (SAVED_INPUTS / directory.name / "artifact.json").read_bytes():
            raise AssertionError(f"saved source changed during replay: {directory}")

    actual_calls: Counter[tuple[str, str, int]] = Counter()
    for path in (root / "calls").glob("*.json"):
        reservation = read(path)
        if reservation.get("status") != "reserved_before_invocation":
            raise AssertionError(f"invalid reservation {path.name}")
        actual_calls[(reservation["kind"], reservation["case"], reservation["round"])] += 1
    if expected_calls != actual_calls:
        raise AssertionError(f"reservation ledger differs: expected={expected_calls}; actual={actual_calls}")

    final: dict[str, Any] = {"checked": False}
    if final_round is not None:
        folders = [root / f"round-{final_round}" / case for case in CASES]
        if not all((folder / "artifact.json").is_file() for folder in folders):
            raise ValueError(f"final round {final_round} does not have all cases")
        configs = [read(folder / "config.json") for folder in folders]
        snapshots = [read(folder / "source-snapshot.json") for folder in folders]
        if configs[0] != configs[1] or configs[0] != configs[2]:
            raise AssertionError("final round configs differ")
        if snapshots[0] != snapshots[1] or snapshots[0] != snapshots[2]:
            raise AssertionError("final round source snapshots differ")
        for relative, expected_hash in snapshots[0].items():
            if sha((REPO / relative).read_bytes()) != expected_hash:
                raise AssertionError(f"final source differs from run snapshot: {relative}")
        final = {"checked": True, "round": final_round,
                 "same_config": True, "same_snapshot": True, "matches_current_source": True}

    original_diff = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *ORIGINAL],
                                   cwd=REPO, check=False)
    if original_diff.returncode != 0:
        raise RuntimeError("git diff could not verify original evidence")
    rounds = sorted({int(path.parent.parent.name.removeprefix("round-")) for path in paths})
    return {"status": "passed", "rounds": rounds, "artifacts": len(paths),
            "fresh_process_replays": len(output), "results": output,
            "artifact_accounting": artifact_accounting,
            "reservations": {f"{kind}/{case}/round-{rnd}": count
                             for (kind, case, rnd), count in sorted(actual_calls.items())},
            "final_round": final,
            "original_2026_10_24_and_compact_inputs_unchanged_vs_HEAD": original_diff.returncode == 0,
            "limits": ["Replay and receipt integrity do not establish prose truth or composition.",
                       "Each artifact replay used its captured Results source archive.",
                       "Original V6 current-code preparation mismatch is intentional and is not a replay failure."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, default=HERE)
    parser.add_argument("--final-round", type=int)
    args = parser.parse_args()
    result = audit(args.campaign_root, args.final_round)
    (args.campaign_root / "audit-summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        print(json.dumps(replay_worker(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])),
                         sort_keys=True))
    else:
        main()
