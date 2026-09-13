"""Compatibility alias for active one-way live smoke evaluation."""

from award_agent.cli.one_way_award_live_eval import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
