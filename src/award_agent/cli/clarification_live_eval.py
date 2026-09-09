"""Run redacted live clarification qualification against an explicit model."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.clarification_live import (
    DEFAULT_LIVE_CLARIFICATION_FIXTURES,
    DEFAULT_LIVE_CLARIFICATION_TRACE_DIR,
    run_live_clarification_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live ADR 0011 continuation qualification.")
    parser.add_argument("--model", required=True, help="OpenAI model ID for answer interpretation")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_LIVE_CLARIFICATION_FIXTURES)
    parser.add_argument(
        "--trace-dir",
        type=Path,
        default=DEFAULT_LIVE_CLARIFICATION_TRACE_DIR,
        help="Private gitignored destination for all raw model-call trace sidecars.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Redacted JSON artifact destination")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_live_clarification_eval(
        model=args.model, trials=args.trials, fixture_path=args.fixtures, trace_dir=args.trace_dir
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["live_gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
