"""Offline invariants for the current compiled-plan handoff receipt."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from award_agent.search_planning import PlanHandoffCheck, PlanHandoffStatus


def test_handoff_receipt_derives_current_and_stale_executability() -> None:
    current = PlanHandoffCheck(
        status=PlanHandoffStatus.CURRENT,
        plan_session_id="session",
        plan_revision=2,
        current_session_id="session",
        current_revision=2,
        plan_effective_request_digest="a" * 64,
        current_effective_request_digest="a" * 64,
        plan_compilation_binding_digest="b" * 64,
        expected_compilation_binding_digest="b" * 64,
    )
    stale = PlanHandoffCheck(
        status=PlanHandoffStatus.STALE_SESSION_OR_REVISION,
        plan_session_id="session",
        plan_revision=2,
        current_session_id="session",
        current_revision=3,
        plan_effective_request_digest="a" * 64,
        current_effective_request_digest="a" * 64,
        plan_compilation_binding_digest="b" * 64,
        expected_compilation_binding_digest="b" * 64,
    )

    assert current.executable is True
    assert stale.executable is False


def test_handoff_receipt_rejects_forged_current_status() -> None:
    with pytest.raises(ValidationError, match="status must be derived"):
        PlanHandoffCheck(
            status=PlanHandoffStatus.CURRENT,
            plan_session_id="session",
            plan_revision=2,
            current_session_id="session",
            current_revision=3,
            plan_effective_request_digest="a" * 64,
            current_effective_request_digest="a" * 64,
            plan_compilation_binding_digest="b" * 64,
            expected_compilation_binding_digest="b" * 64,
        )


def test_handoff_receipt_detects_changed_planning_bindings_after_request_checks() -> None:
    check = PlanHandoffCheck(
        status=PlanHandoffStatus.STALE_PLANNING_BINDINGS,
        plan_session_id="session",
        plan_revision=2,
        current_session_id="session",
        current_revision=2,
        plan_effective_request_digest="a" * 64,
        current_effective_request_digest="a" * 64,
        plan_compilation_binding_digest="b" * 64,
        expected_compilation_binding_digest="c" * 64,
    )

    assert check.executable is False
