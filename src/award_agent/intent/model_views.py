"""Strict date-free views at the selector-only model boundaries."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, PrivateAttr, model_validator

from award_agent.domain import CabinClass, ContractModel, LocationRef, SearchMode

NonTemporalAmbiguityField = Literal[
    "origin",
    "destination",
    "destination_preference",
    "travelers",
    "cabin",
    "search_modes",
    "repositioning_allowed",
    "hard_constraints",
]


class NonTemporalExtractionInput(ContractModel):
    """The complete information available to non-temporal Pass 1."""

    request_text: str = Field(
        min_length=1,
        description=(
            "The complete and only source for non-temporal extraction. Timing is interpreted "
            "by deterministic code outside this model boundary."
        ),
    )


class NonTemporalAmbiguity(ContractModel):
    """A bounded clarification-field vocabulary for non-temporal extraction."""

    field: NonTemporalAmbiguityField
    detail: str = Field(min_length=1)
    raw_text: str | None = None


class NonTemporalIntentExtraction(ContractModel):
    """Pass-1 result with no temporal semantics or repair surface."""

    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    repositioning_allowed: bool | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    ambiguities: list[NonTemporalAmbiguity] = Field(default_factory=list)


class TemporalSelectorEvidence(ContractModel):
    """One ordered local temporal clause available to the candidate selector."""

    handle: str = Field(min_length=1, description="Opaque local evidence handle such as e0.")
    text: str = Field(min_length=1, description="Exact local temporal wording from the request.")
    endpoint_cue: Literal["departure", "return", "unspecified"] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Explicit endpoint cue from local leave/depart/return/back wording only. "
            "It is unspecified when the clause has no unambiguous local cue."
        ),
    )


class TemporalSelectorAnchor(ContractModel):
    """A literal anchor identity, without a resolved date or canonical anchor ID."""

    handle: str = Field(min_length=1, description="Opaque local anchor handle such as a0.")
    evidence: str = Field(min_length=1, description="The eN clause containing this anchor.")
    kind: Literal["exact_date", "month", "holiday"]


class TemporalSelectorAnchorUse(ContractModel):
    anchor: str = Field(min_length=1, description="An aN handle from local_anchors.")
    mode: Literal["direct_window", "reference_only", "unresolved_support"]


class TemporalSelectorCandidate(ContractModel):
    """A pre-authored local choice; the selector cannot modify its fields."""

    handle: str = Field(min_length=1, description="Opaque candidate handle such as c0.")
    summary: str = Field(min_length=1, description="Date-free supplied interpretation.")
    interpretation_kind: str | None = Field(default=None, exclude_if=lambda value: value is None)
    relation_ordinal: int | None = Field(default=None, ge=1, exclude_if=lambda value: value is None)
    target: Literal["departure", "return", "unspecified"] | None = None
    covers: tuple[str, ...] = Field(description="eN clauses covered by this candidate.")
    requires: tuple[str, ...] = Field(description="Opaque pN dependency slots.")
    produces: tuple[str, ...] = Field(description="Opaque pN output slots.")
    anchor_uses: tuple[TemporalSelectorAnchorUse, ...] = ()
    composition: Literal["extend_start"] | None = None
    composition_operand: str | None = None


class TemporalSelectorGroup(ContractModel):
    handle: str = Field(min_length=1, description="Opaque exclusive-group handle such as g0.")
    candidates: tuple[TemporalSelectorCandidate, ...] = Field(min_length=1)


class TemporalSelectorInput(ContractModel):
    """Complete date-free selector input with private restoration maps."""

    ordered_evidence: tuple[TemporalSelectorEvidence, ...] = ()
    local_anchors: tuple[TemporalSelectorAnchor, ...] = ()
    available_productions: tuple[str, ...] = ()
    candidate_groups: tuple[TemporalSelectorGroup, ...] = ()
    _candidate_handles: dict[str, str] = PrivateAttr(default_factory=dict)
    _group_handles: dict[str, str] = PrivateAttr(default_factory=dict)
    _evidence_handles: dict[str, str] = PrivateAttr(default_factory=dict)
    _anchor_handles: dict[str, str] = PrivateAttr(default_factory=dict)
    _production_slots: dict[str, str] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def validate_selector_catalog(self) -> TemporalSelectorInput:
        def unique(values: list[str], label: str) -> None:
            if len(values) != len(set(values)):
                raise ValueError(f"selector {label} handles must be unique")

        unique([entry.handle for entry in self.ordered_evidence], "evidence")
        unique([entry.handle for entry in self.local_anchors], "anchor")
        unique([group.handle for group in self.candidate_groups], "group")
        candidates = [candidate for group in self.candidate_groups for candidate in group.candidates]
        unique([candidate.handle for candidate in candidates], "candidate")
        if any(not slot.startswith("p") or not slot[1:].isdigit() for slot in self.available_productions):
            raise ValueError("selector production slots must use pN handles")
        evidence_handles = {entry.handle for entry in self.ordered_evidence}
        anchor_handles = {entry.handle for entry in self.local_anchors}
        all_slots = set(self.available_productions) | {
            slot for item in candidates for slot in item.produces
        }
        for anchor in self.local_anchors:
            if anchor.evidence not in evidence_handles:
                raise ValueError("selector anchor references unknown evidence")
        for candidate in candidates:
            if not set(candidate.covers) <= evidence_handles:
                raise ValueError("selector candidate covers unknown evidence")
            if any(use.anchor not in anchor_handles for use in candidate.anchor_uses):
                raise ValueError("selector candidate uses unknown anchor")
            if not set(candidate.requires) <= all_slots:
                raise ValueError("selector candidate requires unknown production slot")
            if any(not slot.startswith("p") or not slot[1:].isdigit() for slot in (*candidate.requires, *candidate.produces)):
                raise ValueError("selector production slots must use pN handles")
            if candidate.composition is None and candidate.composition_operand is not None:
                raise ValueError("selector candidate has an operand without composition")
            if candidate.composition is not None and candidate.composition_operand not in candidate.requires:
                raise ValueError("selector composition operand must be required")
        return self


class TemporalSelectorOutput(ContractModel):
    """The selector's complete output: choose supplied opaque candidates only."""

    selected_candidates: list[str] = Field(
        description="Complete list of opaque cN candidate handles selected from supplied groups."
    )
