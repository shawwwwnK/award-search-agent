"""Run the active offline one-way clarification conformance evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.evaluation.one_way_award_clarification import (
    DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES,
    run_offline_one_way_award_clarification_eval,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run active one-way award clarification checks.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    artifact = run_offline_one_way_award_clarification_eval(args.fixtures)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"passed": artifact["passed"], "cases": len(artifact["records"])}, indent=2))
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
