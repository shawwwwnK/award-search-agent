"""Run the fixture-only deterministic search-planning golden evaluation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.evaluation.search_planning import (
    DEFAULT_SEARCH_PLANNING_CASES,
    run_search_planning_golden_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run offline fixture-grade search-planning golden cases (no provider calls)."
    )
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_SEARCH_PLANNING_CASES)
    parser.add_argument("--output", type=Path, help="Optional JSON artifact destination.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = run_search_planning_golden_eval(args.fixtures)
    rendered = json.dumps(artifact, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"saved={args.output}")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["exact_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
