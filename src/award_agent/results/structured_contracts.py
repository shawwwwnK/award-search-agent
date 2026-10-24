"""Versioned authored and resolved Results contracts for the local workspace."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field, model_validator

from award_agent.search_planning.contracts import PlanningContractModel

from .contracts import (
    AuthoringReferenceMap,
    CheckFinding,
    CompactAuthoringInput,
    DeclaredClaim,
    InputTokenReceipt,
    ResultsConfig,
    WriterReceipt,
)
from .workspace_contracts import (
    ComponentView,
    ComponentViewV1,
    JourneyView,
    LeadView,
    WorkspaceEvidence,
)


class StructuredSelection(PlanningContractModel):
    journey_ids: tuple[str, ...] = ()
    benchmark_observation_id: str | None = None
    incomplete_observation_ids: tuple[str, ...] = ()


class StructuredBlock(PlanningContractModel):
    kind: Literal["narrative", "reference"]
    text: str
    reference_kind: Literal["journey", "benchmark", "lead"] | None = None
    reference_id: str | None = None
    label: str | None = None
    claims: tuple[DeclaredClaim, ...] = ()

    @model_validator(mode="after")
    def valid_kind(self) -> StructuredBlock:
        if self.kind == "reference" and (self.reference_kind is None or self.reference_id is None):
            raise ValueError("reference blocks require a kind and exact reference")
        if self.kind == "narrative" and (self.reference_kind is not None or
                                          self.reference_id is not None):
            raise ValueError("narrative blocks cannot contain a reference")
        return self


class StructuredDocument(PlanningContractModel):
    contract_version: Literal["results-document-v2"] = "results-document-v2"
    selection: StructuredSelection
    blocks: tuple[StructuredBlock, ...] = Field(min_length=1)


class StructuredPreparedInput(PlanningContractModel):
    contract_version: Literal["results-prepared-v5"] = "results-prepared-v5"
    source_digest: str
    authoring_view: CompactAuthoringInput
    instructions: str
    input_bytes: int = Field(ge=0)
    estimated_input_tokens: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)

    @property
    def references(self) -> AuthoringReferenceMap:
        return self.authoring_view.references


class ResolvedStructuredBlock(PlanningContractModel):
    kind: Literal["narrative", "reference"]
    text: str
    label: str | None = None
    reference_kind: Literal["journey", "benchmark", "lead"] | None = None
    canonical_id: str | None = None
    journey: JourneyView | None = None
    component: ComponentViewV1 | ComponentView | None = None
    lead: LeadView | None = None
    unavailable: bool = False


class ResolvedStructuredAnswer(PlanningContractModel):
    contract_version: Literal["results-resolved-v1", "results-resolved-v2"] = "results-resolved-v2"
    selected_journey_ids: tuple[str, ...]
    blocks: tuple[ResolvedStructuredBlock, ...]
    availability_guidance: str
    findings: tuple[CheckFinding, ...] = ()

    @model_validator(mode="after")
    def versioned_components(self) -> ResolvedStructuredAnswer:
        expected = (ComponentViewV1 if self.contract_version == "results-resolved-v1"
                    else ComponentView)
        if any(block.component is not None and type(block.component) is not expected
               for block in self.blocks):
            raise ValueError("resolved component shape differs from answer version")
        return self


class StructuredAttempt(PlanningContractModel):
    phase: Literal["initial", "correction"]
    outcome: Literal["recoverable", "api_error", "generation_error", "measurement_error"]
    document: StructuredDocument | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None
    writer_receipt: WriterReceipt | None = None
    input_bytes: int = Field(ge=0)
    estimated_total_tokens: int = Field(ge=0)
    prompt_digest: str | None = None
    schema_digest: str | None = None
    writer_called: bool = True
    input_token_receipt: InputTokenReceipt | None = None


class StructuredResultsArtifact(PlanningContractModel):
    contract_version: Literal["results-artifact-v6"] = "results-artifact-v6"
    evidence: WorkspaceEvidence
    config: ResultsConfig
    prepared: StructuredPreparedInput
    attempts: tuple[StructuredAttempt, ...]
    selected_attempt: int | None
    selection_reason: str
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]
    validation_outcome: Literal["clean", "annotated", "unavailable"]
    delivery_outcome: Literal["delivered", "not_delivered"]
    resolved: ResolvedStructuredAnswer | None = None
    resolved_digest: str | None = None


class StructuredResultsWriter(Protocol):
    def author(self, prepared: StructuredPreparedInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: StructuredDocument | None = None) -> StructuredDocument: ...
