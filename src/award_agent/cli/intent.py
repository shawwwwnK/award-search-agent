"""Command-line entry point for the request-understanding workflow."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from datetime import date

from dotenv import load_dotenv

from award_agent.domain import RawRequest, RequestContext
from award_agent.intent.openai_extractor import OpenAIIntentExtractor
from award_agent.intent.workflow import understand_request


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse an award-travel request.")
    parser.add_argument("request", help="Natural-language travel request")
    parser.add_argument(
        "--reference-date",
        required=True,
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Date used for relative-date resolution",
    )
    parser.add_argument(
        "--timezone",
        required=True,
        help="IANA timezone used to interpret the request context",
    )
    parser.add_argument("--model", help="OpenAI model ID; defaults to MODEL_NAME")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = _parser()
    args = parser.parse_args(argv)
    model = args.model or os.environ.get("MODEL_NAME")
    if not model:
        parser.error("set MODEL_NAME or pass --model")

    raw_request = RawRequest(
        text=args.request,
        context=RequestContext(
            reference_date=args.reference_date,
            timezone=args.timezone,
        ),
    )
    result = understand_request(
        raw_request,
        OpenAIIntentExtractor(model=model),
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
