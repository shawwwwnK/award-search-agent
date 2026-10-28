"""Versioned receipts for the explicit interactive Results channel."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import CheckFinding, InputTokenReceipt, ResultsConfig, WriterReceipt
from .structured_contracts import (
    ResolvedStructuredAnswer,
    StructuredDocument,
    StructuredPreparedInput,
)
from .workspace_contracts import WorkspaceEvidence


class InteractiveSettings(PlanningContractModel):
    reasoning_effort: Literal["none", "low", "medium"]
    service_tier: Literal["standard", "fast"] = "standard"


class InteractivePreparedInput(PlanningContractModel):
    contract_version: Literal["results-prepared-v6"] = "results-prepared-v6"
    structured: StructuredPreparedInput
    packet: dict[str, object]
    packet_digest: str
    source_digest: str


class InteractiveAttempt(PlanningContractModel):
    phase: Literal["initial", "correction"]
    outcome: Literal["recoverable", "api_error", "generation_error", "measurement_error"]
    request: dict[str, object]
    request_digest: str
    raw_wire: str | None = None
    document: StructuredDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None
    writer_receipt: WriterReceipt | None = None
    returned_service_tier: str | None = None
    input_bytes: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)
    prompt_digest: str
    schema_digest: str
    writer_called: bool
    input_token_receipt: InputTokenReceipt | None = None


class InteractiveResultsArtifact(PlanningContractModel):
    contract_version: Literal["results-artifact-v7"] = "results-artifact-v7"
    evidence: WorkspaceEvidence
    config: ResultsConfig
    settings: InteractiveSettings
    prepared: InteractivePreparedInput
    attempts: tuple[InteractiveAttempt, ...]
    selected_attempt: int | None
    selection_reason: str
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: ResolvedStructuredAnswer | None = None
    resolved_digest: str | None = None
    runtime_seconds: float = Field(ge=0)


class InteractiveWriter(Protocol):
    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: InteractiveSettings) -> str: ...
    def take_receipt(self) -> WriterReceipt | None: ...
