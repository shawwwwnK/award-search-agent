"""CLI for the single-model structural selector challenge study."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.selector_challenge_fixture import DEFAULT_SELECTOR_CHALLENGE_FIXTURE
from award_agent.evaluation.selector_structural_challenge_eval import (
    SelectorChallengePricing,
    run_selector_structural_challenge_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one explicit model against 28 redacted structural selector challenges."
    )
    parser.add_argument("--selector-model", required=True, help="Explicit selector model ID.")
    parser.add_argument("--trials", type=int, default=1, help="Repeat every payload this many times.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_SELECTOR_CHALLENGE_FIXTURE)
    parser.add_argument("--output", type=Path, required=True, help="Redacted JSON artifact destination.")
    parser.add_argument("--pricing-snapshot", required=True, help="Dated/source pricing snapshot identifier.")
    parser.add_argument("--input-usd-per-million", type=float, required=True)
    parser.add_argument("--cached-input-usd-per-million", type=float, default=0.0)
    parser.add_argument("--output-usd-per-million", type=float, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    pricing = SelectorChallengePricing(
        input_usd_per_million=args.input_usd_per_million,
        cached_input_usd_per_million=args.cached_input_usd_per_million,
        output_usd_per_million=args.output_usd_per_million,
        snapshot=args.pricing_snapshot,
    )
    artifact = run_selector_structural_challenge_eval(
        selector_model=args.selector_model,
        trials=args.trials,
        fixture_path=args.fixtures,
        pricing=pricing,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"saved={args.output}")
    if not artifact["summary"]["exact_gate"]["passed"]:
        print("exact_gate=failed")
        return 1
    print("exact_gate=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
