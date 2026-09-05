"""CLI for the test-only selector-to-workflow integration evaluation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.selector_workflow_integration import (
    DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
    run_selector_workflow_integration_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run test-only manual selector ambiguities through the compiler workflow."
    )
    parser.add_argument("--selector-model", required=True, help="Explicit selector model ID.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
        help="Checked-in public integration scenario manifest.",
    )
    parser.add_argument("--trials", type=int, default=1, help="Runs per manual scenario.")
    parser.add_argument("--output", required=True, type=Path, help="Redacted JSON artifact destination.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _parser().parse_args(argv)
    artifact = run_selector_workflow_integration_eval(
        selector_model=args.selector_model,
        manifest_path=args.manifest,
        trials=args.trials,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    print(f"saved={args.output}")
    passed = (
        artifact["summary"]["errors"] == 0
        and artifact["summary"]["selector_oracle_matches"] == artifact["summary"]["runs"]
        and artifact["summary"]["workflow_oracle_matches"] == artifact["summary"]["runs"]
        and artifact["summary"]["zero_repairs"]
        and all(item["workflow"].get("paired_output_match") for item in artifact["results"])
    )
    print(f"integration_gate={'passed' if passed else 'failed'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
