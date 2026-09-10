"""Run ADR 0014's typed semantic offline guardrail evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.evaluation.clarification_semantic_guardrails import (
    DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES,
    run_offline_clarification_semantic_guardrails,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline ADR 0014 typed semantic guardrails.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES)
    parser.add_argument("--output", type=Path, help="Optional redacted JSON artifact path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    artifact = run_offline_clarification_semantic_guardrails(fixture_path=args.fixtures)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["checks"], indent=2))
    return 0 if artifact["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
