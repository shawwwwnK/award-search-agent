"""Historical selector workflow study must not reconnect to the active route."""

from __future__ import annotations

import pytest

from award_agent.cli import selector_workflow_integration_eval as retired_cli
from award_agent.evaluation.selector_workflow_integration import (
    DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
    SelectorWorkflowIntegrationRetiredError,
    preflight_selector_workflow_cases,
    run_selector_workflow_integration_eval,
)


def test_historical_manifest_remains_available_without_a_live_workflow_import() -> None:
    assert DEFAULT_SELECTOR_WORKFLOW_MANIFEST.exists()


def test_historical_selector_workflow_evaluator_fails_closed() -> None:
    with pytest.raises(SelectorWorkflowIntegrationRetiredError, match="historical"):
        preflight_selector_workflow_cases()
    with pytest.raises(SelectorWorkflowIntegrationRetiredError, match="historical"):
        run_selector_workflow_integration_eval()


def test_historical_selector_workflow_cli_has_no_selector_model_option() -> None:
    with pytest.raises(SystemExit):
        retired_cli._parser().parse_args(["--selector-model", "retired"])
    with pytest.raises(SelectorWorkflowIntegrationRetiredError, match="historical"):
        retired_cli.main([])
