"""Run the bounded, diagnostic M2A airport-selector live evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.airport_selector_live import (
    DEFAULT_AIRPORT_SELECTOR_CATALOG_RELEASE,
    DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES,
    DEFAULT_AIRPORT_SELECTOR_LIVE_TRACE_DIR,
    run_airport_selector_live_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run diagnostic (not qualifying) live airport-selector evaluation."
    )
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument(
        "--prompt-arm",
        choices=("original_simple", "refined"),
        action="append",
        dest="prompt_arms",
        help="Repeat to select arms; defaults to both arms.",
    )
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_AIRPORT_SELECTOR_LIVE_FIXTURES)
    parser.add_argument(
        "--catalog-release", type=Path, default=DEFAULT_AIRPORT_SELECTOR_CATALOG_RELEASE
    )
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_AIRPORT_SELECTOR_LIVE_TRACE_DIR)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_airport_selector_live_eval(
        model=args.model,
        trials=args.trials,
        prompt_arms=("original_simple", "refined")
        if args.prompt_arms is None
        else tuple(args.prompt_arms),
        fixture_path=args.fixtures,
        catalog_release=args.catalog_release,
        trace_dir=args.trace_dir,
        max_cases=args.max_cases,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["mechanically_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
