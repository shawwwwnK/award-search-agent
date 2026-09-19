"""Run the bounded diagnostic Milestone 2B gateway-discovery evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.gateway_discovery_live import (
    DEFAULT_GATEWAY_DISCOVERY_CATALOG_RELEASE,
    DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES,
    DEFAULT_GATEWAY_DISCOVERY_LIVE_TRACE_DIR,
    run_gateway_discovery_live_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run diagnostic (not qualifying) M2B gateway evaluation."
    )
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES)
    parser.add_argument(
        "--catalog-release", type=Path, default=DEFAULT_GATEWAY_DISCOVERY_CATALOG_RELEASE
    )
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_GATEWAY_DISCOVERY_LIVE_TRACE_DIR)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv()
    artifact = run_gateway_discovery_live_eval(
        model=args.model,
        trials=args.trials,
        fixture_path=args.fixtures,
        catalog_release=args.catalog_release,
        policy_path=args.policy,
        trace_dir=args.trace_dir,
        max_cases=args.max_cases,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return 0 if artifact["summary"]["mechanically_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
