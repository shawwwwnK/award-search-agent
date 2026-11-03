"""Freeze a named prospective confirmation before any live run."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import ledger
import run


def freeze(path: Path, *, profile: str, repeat: int = 2,
           prefix: str | None = None,
           scout_source_evidence: Path | None = None) -> Path:
    if profile not in run.PROFILES or repeat < 1:
        raise ValueError("invalid profile or repetition count")
    prefix = prefix or path.stem
    if not prefix or not prefix.replace("-", "").replace("_", "").isalnum():
        raise ValueError("prefix must contain only letters, digits, - or _")
    needed = repeat * len(run.CASES) * ledger.campaign()["per_run_maximum_generations"]
    for kind in ("count", "generation"):
        if ledger.remaining(kind, ledger.campaign()) < needed:
            raise ValueError(f"campaign lacks {needed} {kind} slots for frozen cohort")
    rows = []
    for cohort in range(1, repeat + 1):
        for case in run.CASES:
            name = f"{prefix}-{cohort}-{case}"
            if (run.HERE / "runs" / name).exists():
                raise FileExistsError(f"confirmation run exists: {name}")
            rows.append({"name": name, "case": case, "profile": profile,
                         "source_sha256": ledger.sha256(run.SOURCE / case / "artifact.json"),
                         "snapshot_hashes": run.snapshot_hashes(case)})
    manifest = {"contract": "fast-default-confirmation-v1",
                "frozen_at_utc": datetime.now(UTC).isoformat(),
                "campaign_sha256": ledger.sha256(ledger.CAMPAIGN),
                "runs": rows,
                "gate": "Every declared run must pass H, U and M2 with decision-rich C (or a source-grounded sparse exception) and close to or below 20-second complete Results timing. A basic or unresolved factual confirmation fails this gate. Record every failure, original judgment and explicit adjudication; replace no draws. Scouts retain their separate outcomes and denominator."}
    if scout_source_evidence is not None:
        evidence_bytes = scout_source_evidence.read_bytes()
        try:
            evidence_value = json.loads(evidence_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("scout source evidence must be a JSON document") from exc
        if not isinstance(evidence_value, dict):
            raise ValueError("scout source evidence must be a JSON object")
        canonical_evidence = json.dumps(
            evidence_value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")
        manifest["scout_source_evidence"] = {
            "path_name": scout_source_evidence.name,
            "sha256": hashlib.sha256(evidence_bytes).hexdigest(),
            "canonical_sha256": hashlib.sha256(canonical_evidence).hexdigest(),
            "document": evidence_value,
            "use": "prospective source evidence only; not part of the V23 confirmation cohort or latency evidence",
        }
    ledger.write_new(path, manifest)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--profile", choices=run.PROFILES, default="focused-v6")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--prefix")
    parser.add_argument("--scout-source-evidence", type=Path,
                        help="embed a reviewed scout identity/provenance JSON object before freezing")
    args = parser.parse_args()
    print(freeze(args.path, profile=args.profile, repeat=args.repeat,
                 prefix=args.prefix, scout_source_evidence=args.scout_source_evidence))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
