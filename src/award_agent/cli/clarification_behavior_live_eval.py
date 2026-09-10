"""Run ADR 0012's redacted live behavioral qualification."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.clarification_behavior_live import (
    DEFAULT_LIVE_BEHAVIOR_FIXTURES,
    DEFAULT_LIVE_BEHAVIOR_TRACE_DIR,
    run_live_clarification_behavior_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run live ADR 0012 behavioral clarification qualification.",
        epilog=(
            "One-trial pilot: award-clarification-behavior-live-eval --trials 1 "
            "--output evals/clarification/baseline/behavior-v2-pilot.json"
        ),
    )
    parser.add_argument("--interpreter-model", default="gpt-5.6-luna")
    parser.add_argument("--composer-model", default="gpt-5.6-luna")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_LIVE_BEHAVIOR_FIXTURES)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_LIVE_BEHAVIOR_TRACE_DIR)
    parser.add_argument("--output", type=Path, required=True, help="Redacted public JSON artifact.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_live_clarification_behavior_eval(
        interpreter_model=args.interpreter_model,
        composer_model=args.composer_model,
        trials=args.trials,
        fixture_path=args.fixtures,
        trace_dir=args.trace_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["exact_safety_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
