"""Run the fixed live one-way award clarification corpus."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.one_way_award_live import (
    DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES,
    DEFAULT_ONE_WAY_AWARD_LIVE_TRACE_DIR,
    run_one_way_award_live_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fixed active one-way award live evaluation."
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--composer-model")
    parser.add_argument("--interpreter-model")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_ONE_WAY_AWARD_LIVE_TRACE_DIR)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_one_way_award_live_eval(
        model=args.model,
        composer_model=args.composer_model,
        interpreter_model=args.interpreter_model,
        trials=args.trials,
        fixture_path=args.fixtures,
        trace_dir=args.trace_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["mechanically_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
