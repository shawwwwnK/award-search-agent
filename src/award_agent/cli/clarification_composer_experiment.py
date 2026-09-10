"""Run the preregistered Luna versus GPT-4o-mini composer experiment."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.clarification_composer_experiment import (
    DEFAULT_COMPOSER_EXPERIMENT_FIXTURES,
    DEFAULT_COMPOSER_EXPERIMENT_TRACE_DIR,
    run_clarification_composer_experiment,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run paired, randomized Luna versus GPT-4o-mini clarification composer experiment."
    )
    parser.add_argument("--luna-model", default="gpt-5.6-luna")
    parser.add_argument("--gpt-4o-mini-model", default="gpt-4o-mini")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_COMPOSER_EXPERIMENT_FIXTURES)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_COMPOSER_EXPERIMENT_TRACE_DIR)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--output", type=Path, required=True, help="Redacted public JSON artifact.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_clarification_composer_experiment(
        luna_model=args.luna_model,
        gpt_4o_mini_model=args.gpt_4o_mini_model,
        trials=args.trials,
        fixture_path=args.fixtures,
        trace_dir=args.trace_dir,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    # The protocol leaves model selection to preregistered analysis and human
    # review, so a completed experiment is successful regardless of its arm.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
