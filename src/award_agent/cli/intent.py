"""Command-line entry point for the request-understanding workflow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date

from dotenv import load_dotenv

from award_agent.domain import RawRequest, RequestContext
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.intent.openai_extractor import OpenAIExtractorConfig, OpenAIIntentExtractor
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
    parser.add_argument(
        "--model",
        required=True,
        help="OpenAI model ID selected explicitly for this workflow run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    parser = _parser()
    args = parser.parse_args(argv)
    raw_request = RawRequest(
        text=args.request,
        context=RequestContext(
            reference_date=args.reference_date,
            timezone=args.timezone,
        ),
    )
    model_adapter = OpenAIIntentExtractor(config=OpenAIExtractorConfig(model=args.model))
    result = understand_request(
        raw_request,
        model_adapter,
        model_adapter,
        NagerHolidayProvider(),
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
