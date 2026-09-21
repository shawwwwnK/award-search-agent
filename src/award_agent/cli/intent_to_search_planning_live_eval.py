"""CLI for the active Intent-corpus end-to-end planning diagnostic."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from award_agent.evaluation.intent_to_search_planning_live import (
    DEFAULT_CATALOG,
    DEFAULT_CORPUS,
    DEFAULT_PRIVATE_ROOT,
    PINNED_MODEL,
    run_intent_to_search_planning_live_eval,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Intent -> clarification -> M2A/M2B/M2C diagnostic."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--catalog-release", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--private-root", type=Path, default=DEFAULT_PRIVATE_ROOT)
    parser.add_argument("--model", default=PINNED_MODEL)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--case-id", action="append", dest="case_ids")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.preflight_only and args.output is None:
        parser.error("--output is required unless --preflight-only is used")
    load_dotenv()
    artifact = run_intent_to_search_planning_live_eval(
        model=args.model,
        trials=args.trials,
        corpus_path=args.cases,
        catalog_release=args.catalog_release,
        private_root=args.private_root,
        case_ids=args.case_ids,
        preflight_only=args.preflight_only,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps(artifact["summary"], indent=2))
    return (
        0
        if artifact["summary"]["preflight_passed"]
        and (args.preflight_only or artifact["summary"]["mechanically_completed"])
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
