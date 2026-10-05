"""Assemble Ranking M1 journeys from a frozen plan and offline provider result."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from award_agent.cli._atomic_output import write_new_atomic as _write_new_atomic
from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.providers.contracts import ProviderResultSet


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True,
                        help="Frozen ProviderInputBundle with current request authority.")
    parser.add_argument("--result", type=Path, required=True,
                        help="ProviderResultSet from the same plan and request.")
    parser.add_argument("--output", type=Path, required=True,
                        help="New path for the deterministic MatchedJourneySet JSON.")
    parser.add_argument("--max-combinations", type=int, default=100_000,
                        help="Positive safety bound on combinations to enumerate.")
    args = parser.parse_args(argv)
    if args.max_combinations < 1:
        parser.error("--max-combinations must be positive")
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must be new; existing evidence is immutable")

    from award_agent.ranking import assemble_matched_journeys

    bundle = ProviderInputBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    provider_result = ProviderResultSet.model_validate_json(
        args.result.read_text(encoding="utf-8")
    )
    matched = assemble_matched_journeys(
        bundle.plan,
        provider_result,
        current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy,
        award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability,
        max_combinations=args.max_combinations,
    )
    # The bundle is the CLI's authority source. Reject a revision that changed
    # while assembly was running, before any result is published.
    current = ProviderInputBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    if current != bundle:
        raise ValueError("provider input bundle changed during Ranking M1 assembly")
    _write_new_atomic(args.output, matched.model_dump_json(indent=2))
    print(json.dumps({
        "output": str(args.output),
        "journeys": len(matched.journeys),
        "admitted": matched.accounting.admitted,
        "conditional": matched.accounting.conditional,
        "rejected": matched.accounting.rejected,
        "research_leads": matched.accounting.research_leads,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
