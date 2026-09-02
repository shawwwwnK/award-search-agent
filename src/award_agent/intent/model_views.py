"""Structurally narrow inputs for the two model passes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from award_agent.domain import (
    Ambiguity,
    CabinClass,
    CoarseIntentExtraction,
    ContractModel,
    GroundedTemporalEvidence,
    LocationRef,
    ModelPassRepairTrace,
    SearchMode,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalRelationGraph,
    TemporalTarget,
)
from award_agent.intent.evidence import TemporalValidationDetails


class CoarseExtractionInput(ContractModel):
    """The complete information available to the first model pass."""

    request_text: str = Field(min_length=1)


class StructuredValidationErrorView(ContractModel):
    """Date-free validation detail safe to return to either model pass."""

    stage: str = Field(min_length=1)
    error_code: str = Field(min_length=1)
    relation_index: int | None = None
    constraint_index: int | None = None
    selected_relation_kind: str | None = None
    collection: str | None = None
    missing_fields: tuple[str, ...] = ()
    contradictory_fields: tuple[str, ...] = ()
    evidence_id: str | None = None
    reference_id: str | None = None
    validation_cause: str = ""

    @classmethod
    def from_details(cls, details: TemporalValidationDetails) -> StructuredValidationErrorView:
        return cls.model_validate(details.as_dict())


class RejectedExplicitAnchorView(ContractModel):
    """A rejected anchor with all model-authored calendar values removed."""

    anchor_id: str = Field(min_length=1)
    kind: Literal["exact_date", "month", "holiday"]
    applies_to: TemporalTarget
    raw_text: str
    occurrence_index: int | None = Field(default=None, ge=0)


class RejectedCoarseExtractionView(ContractModel):
    """Rejected pass-one output safe to disclose without inferred calendar values."""

    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    repositioning_allowed: bool | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    date_anchors: list[RejectedExplicitAnchorView] = Field(default_factory=list)
    temporal_phrases: list[TemporalPhrase] = Field(default_factory=list)

    @classmethod
    def from_output(cls, output: CoarseIntentExtraction) -> RejectedCoarseExtractionView:
        data = output.model_dump(mode="python", exclude={"date_anchors"})
        data["date_anchors"] = [
            RejectedExplicitAnchorView(
                anchor_id=anchor.anchor_id,
                kind=anchor.kind,
                applies_to=anchor.applies_to,
                raw_text=anchor.raw_text,
                occurrence_index=anchor.occurrence_index,
            )
            for anchor in output.date_anchors
        ]
        return cls.model_validate(data)


class CoarseExtractionRepairInput(ContractModel):
    """The complete information allowed in a pass-one repair call."""

    original_input: CoarseExtractionInput
    rejected_output: RejectedCoarseExtractionView
    validation_errors: list[StructuredValidationErrorView] = Field(min_length=1)


class TemporalEvidenceCatalogEntry(ContractModel):
    """One grounded, date-free source entry exposed to the second pass."""

    evidence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claim_labels: list[TemporalEvidenceClaim] = Field(min_length=1)
    source_order: int = Field(ge=0)
    source_start: int = Field(ge=0)
    source_end: int = Field(gt=0)


class ExplicitAnchorCatalogEntry(ContractModel):
    """An explicit anchor identity without resolved calendar state."""

    anchor_id: str = Field(min_length=1)
    kind: Literal["exact_date", "month", "holiday"]
    applies_to: TemporalTarget


class SymbolicReferenceCatalogEntry(ContractModel):
    """An opaque relation reference whose concrete value stays deterministic."""

    key: str = Field(min_length=1)


class TemporalInterpretationInput(ContractModel):
    """The complete date-free information available to the second model pass."""

    temporal_transcript: str = Field(min_length=1)
    evidence_catalog: list[TemporalEvidenceCatalogEntry] = Field(default_factory=list)
    explicit_anchor_catalog: list[ExplicitAnchorCatalogEntry] = Field(default_factory=list)
    allowed_symbolic_references: list[SymbolicReferenceCatalogEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_catalogs(self) -> TemporalInterpretationInput:
        evidence_ids = [entry.evidence_id for entry in self.evidence_catalog]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence catalog IDs must be unique")
        anchor_ids = [entry.anchor_id for entry in self.explicit_anchor_catalog]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError("explicit anchor catalog IDs must be unique")
        reference_keys = [entry.key for entry in self.allowed_symbolic_references]
        if len(reference_keys) != len(set(reference_keys)):
            raise ValueError("symbolic reference catalog keys must be unique")
        expected_orders = list(range(len(self.evidence_catalog)))
        if [entry.source_order for entry in self.evidence_catalog] != expected_orders:
            raise ValueError("evidence catalog source_order must be contiguous and canonical")
        for entry in self.evidence_catalog:
            if (
                entry.source_end > len(self.temporal_transcript)
                or self.temporal_transcript[entry.source_start : entry.source_end] != entry.text
            ):
                raise ValueError(
                    f"evidence catalog offsets do not match transcript: {entry.evidence_id}"
                )
        return self


class TemporalInterpretationRepairInput(ContractModel):
    """Date-free repair view for a graph that failed post-conversion validation."""

    original_input: TemporalInterpretationInput
    rejected_output: TemporalRelationGraph
    validation_errors: list[StructuredValidationErrorView] = Field(min_length=1)


class TemporalResolutionResult(ContractModel):
    """A typed graph plus the adapter-owned wire-validation attempt trace."""

    relations: TemporalRelationGraph
    repair_trace: ModelPassRepairTrace


def build_temporal_interpretation_input(
    request_text: str,
    extraction: CoarseIntentExtraction,
    evidence: list[GroundedTemporalEvidence],
) -> TemporalInterpretationInput:
    """Build the complete, date-free pass-two catalog view deterministically."""

    return TemporalInterpretationInput(
        temporal_transcript=request_text,
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                evidence_id=item.evidence_id,
                text=item.span.text,
                claim_labels=item.claim_ids,
                source_order=source_order,
                source_start=item.span.start,
                source_end=item.span.end,
            )
            for source_order, item in enumerate(evidence)
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                anchor_id=anchor.anchor_id,
                kind=anchor.kind,
                applies_to=anchor.applies_to,
            )
            for anchor in extraction.date_anchors
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry(key="context:request_date"),
            *[
                SymbolicReferenceCatalogEntry(key=f"anchor_ref:{anchor.anchor_id}:{edge}")
                for anchor in extraction.date_anchors
                for edge in ("start", "end")
            ],
            *[
                SymbolicReferenceCatalogEntry(key=f"request_field:{target}:{edge}")
                for target in ("departure", "return")
                for edge in ("start", "end")
            ],
        ],
    )
