"""Retired selector-to-workflow integration study.

The manifests and prior artifacts remain historical evaluation evidence. The
active initial-intent workflow has no selector or injected-catalog route, so
this module deliberately fails closed rather than importing legacy workflow
helpers that could accidentally reintroduce that path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_SELECTOR_WORKFLOW_MANIFEST = Path("evals/selector/workflow_integration_cases_v1.yaml")


class SelectorWorkflowIntegrationRetiredError(RuntimeError):
    """The selector integration study cannot execute against the active workflow."""


def _retired() -> None:
    raise SelectorWorkflowIntegrationRetiredError(
        "selector workflow integration is historical; use the active one-receiver intent evaluation"
    )


def preflight_selector_workflow_cases(*_args: object, **_kwargs: object) -> tuple[object, ...]:
    """Fail closed instead of validating a manifest for a removed live route."""

    _retired()


def run_selector_workflow_integration_eval(*_args: object, **_kwargs: object) -> dict[str, Any]:
    """Fail closed instead of constructing selector or legacy workflow dependencies."""

    _retired()
