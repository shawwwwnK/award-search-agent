"""Caller-owned execution handoff checks for immutable search plans.

Planning has no authority over session revisions.  A caller must therefore
compare the materialized plan identity with its current authoritative request
immediately before handing items to a future provider-execution stage.  This
module is deliberately a pure, non-mutating contract; it is not an executor.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from award_agent.domain import EffectiveRequest
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.contracts import PlanningContractModel
from award_agent.search_planning.planner import effective_request_digest


class PlanHandoffStatus(str, Enum):
    CURRENT = "current"
    STALE_SESSION_OR_REVISION = "stale_session_or_revision"
    STALE_EFFECTIVE_REQUEST = "stale_effective_request"
    STALE_PLANNING_BINDINGS = "stale_planning_bindings"


class PlanHandoffCheck(PlanningContractModel):
    """Typed proof that a caller checked a plan against its current authority."""

    status: PlanHandoffStatus
    plan_session_id: str = Field(min_length=1)
    plan_revision: int = Field(ge=0)
    current_session_id: str = Field(min_length=1)
    current_revision: int = Field(ge=0)
    plan_effective_request_digest: str = Field(min_length=1)
    current_effective_request_digest: str = Field(min_length=1)
    plan_compilation_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_compilation_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    executable: bool | None = None

    @model_validator(mode="after")
    def derive_and_validate_freshness(self) -> PlanHandoffCheck:
        """Reject a forged receipt whose status disagrees with its evidence.

        Session/revision drift deliberately wins over an effective-request
        digest mismatch, matching :func:`check_plan_handoff`.  The serialized
        executable bit is derived from that same status so a caller cannot
        turn a stale receipt into an executable one by altering one field.
        """

        if (
            self.plan_session_id != self.current_session_id
            or self.plan_revision != self.current_revision
        ):
            expected_status = PlanHandoffStatus.STALE_SESSION_OR_REVISION
        elif self.plan_effective_request_digest != self.current_effective_request_digest:
            expected_status = PlanHandoffStatus.STALE_EFFECTIVE_REQUEST
        elif self.plan_compilation_binding_digest != self.expected_compilation_binding_digest:
            expected_status = PlanHandoffStatus.STALE_PLANNING_BINDINGS
        else:
            expected_status = PlanHandoffStatus.CURRENT
        if self.status is not expected_status:
            raise ValueError(
                "handoff status must be derived from session/revision before request digest"
            )
        expected_executable = expected_status is PlanHandoffStatus.CURRENT
        if self.executable is None:
            object.__setattr__(self, "executable", expected_executable)
        elif self.executable is not expected_executable:
            raise ValueError("handoff executable must match the derived handoff status")
        return self


def check_plan_handoff(
    plan: CompiledSearchPlan,
    *,
    current_session_id: str,
    current_revision: int,
    current_effective_request: EffectiveRequest,
    expected_compilation_binding_digest: str,
) -> PlanHandoffCheck:
    """Classify plan freshness without mutating the plan or session value.

    Revision authority remains outside the planner.  A revision/session change
    always wins over a matching payload digest because the caller's ledger is
    the authoritative lifecycle owner.
    """

    identity = plan.identity
    current_digest = effective_request_digest(current_effective_request)
    if (
        identity.session_id != current_session_id
        or identity.revision != current_revision
    ):
        status = PlanHandoffStatus.STALE_SESSION_OR_REVISION
    elif identity.effective_request_digest != current_digest:
        status = PlanHandoffStatus.STALE_EFFECTIVE_REQUEST
    elif identity.compilation_binding_digest != expected_compilation_binding_digest:
        status = PlanHandoffStatus.STALE_PLANNING_BINDINGS
    else:
        status = PlanHandoffStatus.CURRENT
    return PlanHandoffCheck(
        status=status,
        plan_session_id=identity.session_id,
        plan_revision=identity.revision,
        current_session_id=current_session_id,
        current_revision=current_revision,
        plan_effective_request_digest=identity.effective_request_digest,
        current_effective_request_digest=current_digest,
        plan_compilation_binding_digest=identity.compilation_binding_digest,
        expected_compilation_binding_digest=expected_compilation_binding_digest,
    )


__all__ = ["PlanHandoffCheck", "PlanHandoffStatus", "check_plan_handoff"]
