"""Compatibility alias for active one-way offline clarification checks."""

from award_agent.cli.one_way_award_clarification_eval import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
