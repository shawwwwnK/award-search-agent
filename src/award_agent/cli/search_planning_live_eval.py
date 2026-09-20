"""Run the bounded integrated M2A -> M2B -> M2C development evaluator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.search_planning_live import (
    DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK,
    DEFAULT_SEARCH_PLANNING_LIVE_CATALOG,
    DEFAULT_SEARCH_PLANNING_LIVE_TRACE_DIR,
    run_search_planning_live_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the diagnostic integrated M2A/M2B/M2C evaluator."
    )
    parser.add_argument("--casebook", type=Path, default=DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK)
    parser.add_argument(
        "--catalog-release", type=Path, default=DEFAULT_SEARCH_PLANNING_LIVE_CATALOG
    )
    parser.add_argument("--trace-dir", type=Path, default=DEFAULT_SEARCH_PLANNING_LIVE_TRACE_DIR)
    parser.add_argument("--intent-model", default="gpt-5.6-luna")
    parser.add_argument("--clarification-model", default="gpt-5.6-luna")
    parser.add_argument("--selector-model", default="gpt-5.6-luna")
    parser.add_argument("--gateway-model", default="gpt-5.6-luna")
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.preflight_only and args.output is None:
        _parser().error("--output is required unless --preflight-only is used")
    load_dotenv()
    artifact = run_search_planning_live_eval(
        intent_model=args.intent_model,
        clarification_model=args.clarification_model,
        selector_model=args.selector_model,
        gateway_model=args.gateway_model,
        trials=args.trials,
        casebook_path=args.casebook,
        catalog_release=args.catalog_release,
        trace_dir=args.trace_dir,
        case_ids=args.case_ids,
        preflight_only=args.preflight_only,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    if args.preflight_only:
        return 0 if artifact["summary"]["preflight_passed"] else 1
    return 0 if artifact["summary"]["mechanically_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
