"""Project a frozen ranked journey set to its factual solution export."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.cli._atomic_output import write_new_atomic as _write_new_atomic
from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankedJourneySet


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ranked", type=Path, required=True,
        help="Frozen Ranking M2 RankedJourneySet JSON.",
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="New path for the compact factual solution export JSON.",
    )
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must be new; existing evidence is immutable")

    ranked_content = args.ranked.read_bytes()
    ranked = RankedJourneySet.model_validate_json(ranked_content)
    projection: SolutionProjection = project_solutions(ranked)

    if args.ranked.read_bytes() != ranked_content:
        raise ValueError("ranked journey input changed during solution projection")

    rendered = projection.model_dump_json(indent=2)
    _write_new_atomic(args.output, rendered)
    print(json.dumps({
        "output": str(args.output),
        "total_candidates": projection.receipt.total_candidates,
        "eligible_alternatives": projection.receipt.eligible_alternatives,
        "bytes": len(rendered.encode("utf-8")) + 1,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
