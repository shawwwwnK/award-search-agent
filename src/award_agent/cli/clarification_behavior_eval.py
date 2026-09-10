"""Run the property-based ADR 0012 clarification behavioral evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.evaluation.clarification_behavior import (
    DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES,
    run_clarification_behavior_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline ADR 0012 behavioral clarification fixtures.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES)
    parser.add_argument("--output", type=Path, help="Optional redacted JSON artifact path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = run_clarification_behavior_eval(args.fixtures)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["exact_safety_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
