"""Generate or verify the offline Ranking M2 compact-export corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from award_agent.cli._atomic_output import write_new_atomic
from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankedJourneySet

CASES = ("mixed_access", "exact_business", "sfo_to_bkk_positioning")


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path,
                        default=Path("evidence/ranking-stage/m2/styled"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        index = json.loads((args.output_dir / "index.json").read_text())
    else:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        index = {"version": "ranking-solution-corpus-v1", "cases": {}}

    for case in CASES:
        source = args.source_dir / f"{case}.json"
        source_bytes = source.read_bytes()
        ranked = RankedJourneySet.model_validate_json(source_bytes)
        projection = project_solutions(ranked)
        content = (projection.model_dump_json(indent=2) + "\n").encode()
        view_bytes = projection.view.model_dump_json().encode()
        entry = {
            "source": source.as_posix(),
            "source_sha256": _sha(source_bytes),
            "output_sha256": _sha(content),
            "source_bytes": len(source_bytes),
            "artifact_bytes": len(content),
            "compact_view_bytes": len(view_bytes),
            "source_digest": projection.receipt.source_digest,
            "view_digest": projection.receipt.view_digest,
            "candidates": len(projection.view.alternatives),
            "eligible": len(projection.view.comparison_pool_ids),
            "components": len(projection.view.components),
            "statuses": dict(sorted(Counter(
                item.status for item in projection.view.alternatives
            ).items())),
            "cost_reference_usd": (
                str(projection.view.cost_reference_usd)
                if projection.view.cost_reference_usd is not None else None
            ),
        }
        output = args.output_dir / f"{case}.json"
        if source.read_bytes() != source_bytes:
            raise ValueError(f"{case}: source changed during projection")
        if args.verify:
            saved = output.read_bytes()
            if saved != content or index["cases"].get(case) != entry:
                raise ValueError(f"{case}: saved export or index differs from replay")
            if SolutionProjection.model_validate_json(saved) != projection:
                raise ValueError(f"{case}: projection JSON round-trip differs")
        else:
            write_new_atomic(output, content.decode().removesuffix("\n"))
            index["cases"][case] = entry
        print(json.dumps({"case": case, "verified": args.verify, **entry}))

    if not args.verify:
        write_new_atomic(args.output_dir / "index.json", json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
