"""Freeze a prospective six-source category confirmation before live calls."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import ledger
import run


def freeze(path: Path, *, candidate: str, prefix: str, cases: tuple[str, ...],
           gate: str, phase: str = "confirmation") -> Path:
    run._candidate(candidate)
    if len(cases) != len(set(cases)) or not cases:
        raise ValueError("confirmation cases must be unique and nonempty")
    if not prefix or not prefix.replace("-", "").replace("_", "").isalnum():
        raise ValueError("invalid confirmation prefix")
    if phase == "confirmation":
        required = set(run.source_registry())
    elif phase == "scout":
        required = {"prior-admitted", "prior-conditional", "prior-incomplete"}
    else:
        raise ValueError("unknown freeze phase")
    if set(cases) != required:
        raise ValueError(f"{phase} must include its exact declared source cases")
    needed = len(cases) * ledger.campaign()["per_run_maximum_generations"]
    for kind in ("count", "generation"):
        if ledger.remaining(kind, ledger.campaign()) < needed:
            raise ValueError(f"campaign lacks {needed} {kind} slots")
    rows = []
    for case in cases:
        name = f"{prefix}-{case}"
        if (run.RUNS / name).exists():
            raise FileExistsError(f"confirmation run exists: {name}")
        projection = run.projection_for(case)
        rows.append({"name": name, "case": case, "candidate": candidate,
                     "source_sha256": ledger.sha256(run.source_path(case)),
                     "source_digest": projection.receipt.source_digest,
                     "view_digest": projection.receipt.view_digest,
                     "snapshot_hashes": run.snapshot_hashes(case)})
    ledger.write_new(path, {
        "contract": f"results-category-{phase}-v1",
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "campaign_sha256": ledger.sha256(ledger.CAMPAIGN),
        "candidate": candidate,
        "source_scope": ("3 historical repeated sources, regression only" if phase == "scout"
                         else "3 historical repeated sources and 3 distinct saved Ranking projections; no new provider searches, no distinct incomplete source, no observed complete cost-reference case."),
        "runs": rows,
        "gate": gate})
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--scouts", action="store_true")
    args = parser.parse_args()
    cases = (("prior-admitted", "prior-conditional", "prior-incomplete")
             if args.scouts else tuple(run.source_registry()))
    print(freeze(args.path, candidate=args.candidate, prefix=args.prefix,
                 cases=cases, gate=args.gate,
                 phase="scout" if args.scouts else "confirmation"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
