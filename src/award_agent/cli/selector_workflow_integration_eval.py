"""Fail-closed historical selector-workflow study entry point."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from award_agent.evaluation.selector_workflow_integration import (
    SelectorWorkflowIntegrationRetiredError,
)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="Retired: selector workflow integration cannot run against the active route."
    )


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    raise SelectorWorkflowIntegrationRetiredError(
        "selector workflow integration is historical; run award_agent.cli.intent_eval instead"
    )


if __name__ == "__main__":
    raise SystemExit(main())
