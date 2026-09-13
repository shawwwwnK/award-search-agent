import pytest

from award_agent.evaluation import clarification_behavior_live, clarification_live


def test_retired_live_entrypoints_fail_closed_with_active_command() -> None:
    with pytest.raises(RuntimeError, match="one_way_award_live_eval"):
        clarification_live.run_live_clarification_eval()
    with pytest.raises(RuntimeError, match="one_way_award_live_eval"):
        clarification_behavior_live.run_live_clarification_behavior_eval()
