"""CLI for the isolated frozen temporal-candidate selector study."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.frozen_selector_eval import (
    DEFAULT_FROZEN_SELECTOR_FIXTURES,
    run_frozen_selector_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate None/Mini/Luna selector arms against frozen date-free inputs."
    )
    parser.add_argument(
        "--mini-model",
        required=True,
        help="Explicit model ID for the arm labelled mini; no model ID is inferred.",
    )
    parser.add_argument(
        "--luna-model",
        required=True,
        help="Explicit model ID for the arm labelled luna; no model ID is inferred.",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FROZEN_SELECTOR_FIXTURES,
        help="Checked-in public frozen selector projections.",
    )
    parser.add_argument("--trials", type=int, default=1, help="Runs per arm and frozen scenario.")
    parser.add_argument("--output", type=Path, required=True, help="JSON artifact destination.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    artifact = run_frozen_selector_eval(
        mini_model=args.mini_model,
        luna_model=args.luna_model,
        fixtures_path=args.fixtures,
        trials=args.trials,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"saved={args.output}")
    gate_arms = artifact["summary"]["quality_gate"]["arms"]
    failed_model_arms = [
        arm for arm, result in gate_arms.items() if result["eligible"] and not result["passed"]
    ]
    if failed_model_arms:
        print(f"quality_gate=failed arms={','.join(failed_model_arms)}")
        return 1
    print("quality_gate=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
