"""Structurally narrow inputs for the two model passes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, PrivateAttr, model_validator

from award_agent.domain import (
    Ambiguity,
    CabinClass,
    CoarseIntentExtraction,
    ContractModel,
    GroundedTemporalEvidence,
    LocationRef,
    ModelPassRepairTrace,
    SearchMode,
    TemporalAnchor,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalRelationGraph,
    TemporalTarget,
)
from award_agent.intent.evidence import TemporalValidationDetails

ReferenceRelationKind = Literal[
    "relative_calendar_period",
    "relative_weekend",
    "relative_weekday",
    "relative_offset",
    "unbounded_boundary",
    "duration",
]
EvidenceRelationKind = Literal[
    "anchor_window",
    "month_portion",
    "relative_calendar_period",
    "relative_weekend",
    "relative_weekday",
    "relative_offset",
    "duration",
    "unbounded_boundary",
    "unresolved",
]
EvidenceTarget = TemporalTarget | Literal["unspecified"]

_ANCHOR_REFERENCE_RELATIONS: list[ReferenceRelationKind] = [
    "relative_weekend",
    "relative_weekday",
    "relative_offset",
    "unbounded_boundary",
]
_TARGET_PERIOD_RELATIONS: list[EvidenceRelationKind] = [
    "anchor_window",
    "month_portion",
    "relative_calendar_period",
    "relative_weekend",
    "relative_weekday",
    "relative_offset",
    "unbounded_boundary",
    "unresolved",
]


def _evidence_relation_kinds(
    claims: list[TemporalEvidenceClaim],
) -> list[EvidenceRelationKind]:
    allowed: set[EvidenceRelationKind] = set()
    for claim in claims:
        if claim in {
            TemporalEvidenceClaim.DURATION,
            TemporalEvidenceClaim.APPROXIMATE_DURATION,
        }:
            allowed.update(("duration", "unresolved"))
        elif claim is TemporalEvidenceClaim.UNSPECIFIED:
            allowed.add("unresolved")
        else:
            allowed.update(_TARGET_PERIOD_RELATIONS)
    canonical_order: list[EvidenceRelationKind] = [
        "anchor_window",
        "month_portion",
        "relative_calendar_period",
        "relative_weekend",
        "relative_weekday",
        "relative_offset",
        "duration",
        "unbounded_boundary",
        "unresolved",
    ]
    return [kind for kind in canonical_order if kind in allowed]


def _evidence_targets(claims: list[TemporalEvidenceClaim]) -> list[EvidenceTarget]:
    """Expose endpoint bindings without exposing pass-one claim labels.

    Pass two needs the endpoint relation carried by evidence such as "flexible to leave
    Thursday as well".  The permitted targets retain that bounded semantic fact while avoiding
    the model-facing claim-label vocabulary and all calendar state.
    """

    targets: list[EvidenceTarget] = []
    if any(
        claim
        in {
            TemporalEvidenceClaim.DEPARTURE_ANCHOR,
            TemporalEvidenceClaim.DEPARTURE_PERIOD,
            TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
        }
        for claim in claims
    ):
        targets.append(TemporalTarget.DEPARTURE)
    if any(
        claim
        in {
            TemporalEvidenceClaim.RETURN_ANCHOR,
            TemporalEvidenceClaim.RETURN_PERIOD,
            TemporalEvidenceClaim.ALTERNATE_RETURN_DAY,
            TemporalEvidenceClaim.DURATION,
            TemporalEvidenceClaim.APPROXIMATE_DURATION,
        }
        for claim in claims
    ):
        targets.append(TemporalTarget.RETURN)
    if TemporalEvidenceClaim.UNSPECIFIED in claims:
        targets.append("unspecified")
    return targets


class CoarseExtractionInput(ContractModel):
    """The complete information available to the first model pass."""

    request_text: str = Field(
        min_length=1,
        description="The complete and only source for pass-one extraction; copy evidence from it.",
    )


class NonTemporalExtractionInput(ContractModel):
    """The complete information available to compiler-route non-temporal extraction.

    This is intentionally a separate boundary from ``CoarseExtractionInput``.  Its paired
    output contract has no temporal fields, so the deterministic scanner remains the only
    producer of compiler-route temporal facts.
    """

    request_text: str = Field(
        min_length=1,
        description=(
            "The complete and only source for non-temporal extraction. "
            "Timing is interpreted by deterministic code outside this model boundary."
        ),
    )


class NonTemporalIntentExtraction(ContractModel):
    """Strict compiler-route Pass-1 result with no temporal semantics."""

    travelers: int | None = Field(default=None, ge=1)
    origins: list[LocationRef] = Field(default_factory=list)
    destinations: list[LocationRef] = Field(default_factory=list)
    cabins: list[CabinClass] = Field(default_factory=list)
    search_modes: list[SearchMode] = Field(default_factory=list)
    repositioning_allowed: bool | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)


class StructuredValidationErrorView(ContractModel):
    """Date-free validation detail safe to return to either model pass."""

    stage: str = Field(min_length=1)
    error_code: str = Field(
        min_length=1,
        description="Machine-readable violation to correct without guessing an expected answer.",
    )
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
    """One grounded source entry exposed to the model with a request-local handle only."""

    handle: str = Field(
        min_length=1,
        description=(
            "Short opaque request-local evidence handle such as e0. Copy it only into an output "
            "decision.evidence field."
        ),
    )
    text: str = Field(min_length=1, description="Exact grounded wording selected by evidence_id.")
    allowed_targets: list[EvidenceTarget] = Field(
        min_length=1,
        description=(
            "Endpoint targets this evidence may constrain. Select decision.target only from this "
            "list; this preserves an endpoint cue without exposing a claim label."
        ),
    )
    allowed_relation_kinds: list[EvidenceRelationKind] = Field(
        min_length=1,
        description=(
            "Non-authoritative relation templates permitted for this evidence. Select one or mark "
            "the evidence unresolved; this is not a semantic claim label."
        ),
    )
    _canonical_id: str | None = PrivateAttr(default=None)
    _legacy_claim_labels: list[TemporalEvidenceClaim] = PrivateAttr(default_factory=list)
    _legacy_source_start: int = PrivateAttr(default=0)
    _legacy_source_end: int = PrivateAttr(default=0)

    def __init__(self, **data: object) -> None:
        """Accept pre-v2 test fixtures without serializing their old wire fields."""

        legacy_claims = data.pop("claim_labels", [])
        legacy_id = data.pop("evidence_id", None)
        data.pop("source_order", None)
        source_start = data.pop("source_start", 0)
        source_end = data.pop("source_end", 0)
        if "handle" not in data and isinstance(legacy_id, str):
            data["handle"] = legacy_id
        if "allowed_relation_kinds" not in data and isinstance(legacy_claims, list):
            data["allowed_relation_kinds"] = _evidence_relation_kinds(legacy_claims)
        if "allowed_targets" not in data and isinstance(legacy_claims, list):
            data["allowed_targets"] = _evidence_targets(legacy_claims)
        super().__init__(**data)
        self._legacy_claim_labels = list(legacy_claims) if isinstance(legacy_claims, list) else []
        self._legacy_source_start = source_start if isinstance(source_start, int) else 0
        self._legacy_source_end = source_end if isinstance(source_end, int) else 0

    @property
    def evidence_id(self) -> str:
        """Compatibility accessor; the model-facing value is still only ``handle``."""
        return self._canonical_id or self.handle

    @property
    def source_start(self) -> int:
        return self._legacy_source_start

    @property
    def source_end(self) -> int:
        return self._legacy_source_end


class ExplicitAnchorCatalogEntry(ContractModel):
    """An explicit anchor identity without resolved calendar state."""

    handle: str = Field(
        min_length=1,
        description=(
            "Short opaque request-local anchor handle such as a0. Copy only into output anchor "
            "or reference fields; never use it as evidence."
        ),
    )
    kind: Literal["exact_date", "month", "holiday"] = Field(
        description="Literal anchor type; it does not imply a window policy."
    )
    applies_to: TemporalTarget = Field(
        description="Only compatible target for a direct anchor relation."
    )
    _canonical_id: str | None = PrivateAttr(default=None)

    def __init__(self, **data: object) -> None:
        legacy_id = data.pop("anchor_id", None)
        data.pop("direct_relation_kind", None)
        if "handle" not in data and isinstance(legacy_id, str):
            data["handle"] = legacy_id
        super().__init__(**data)

    @property
    def anchor_id(self) -> str:
        return self._canonical_id or self.handle

    @property
    def direct_relation_kind(self) -> Literal["anchor_window", "month_portion"]:
        return "month_portion" if self.kind == "month" else "anchor_window"


class SymbolicReferenceCatalogEntry(ContractModel):
    """An opaque relation reference whose concrete value stays deterministic."""

    handle: str = Field(
        min_length=1,
        description=(
            "Short opaque request-local reference handle such as r0. Copy it only into a relation "
            "reference field; never use it as evidence or anchor."
        ),
    )
    allowed_targets: list[TemporalTarget] = Field(
        min_length=1,
        description="Targets permitted to select this key; the output target must be listed.",
    )
    allowed_relation_kinds: list[ReferenceRelationKind] = Field(
        min_length=1,
        description=(
            "Reference-relation collections permitted to select this key; the output relation "
            "kind must be listed."
        ),
    )
    _canonical_key: str | None = PrivateAttr(default=None)

    @property
    def key(self) -> str:
        return self._canonical_key or self.handle

    @classmethod
    def from_key(cls, key: str, handle: str | None = None) -> SymbolicReferenceCatalogEntry:
        """Construct the deterministic permissions for one date-free reference key."""

        handle = handle or key
        if key == "context:request_date":
            return cls(
                handle=handle,
                allowed_targets=list(TemporalTarget),
                allowed_relation_kinds=["relative_calendar_period"],
            )
        if key.startswith("anchor_ref:"):
            return cls(
                handle=handle,
                allowed_targets=list(TemporalTarget),
                allowed_relation_kinds=_ANCHOR_REFERENCE_RELATIONS,
            )
        if key.startswith("request_field:departure:"):
            return cls(
                handle=handle,
                allowed_targets=[TemporalTarget.RETURN],
                allowed_relation_kinds=[*_ANCHOR_REFERENCE_RELATIONS, "duration"],
            )
        if key.startswith("request_field:return:"):
            return cls(
                handle=handle,
                allowed_targets=[TemporalTarget.DEPARTURE],
                allowed_relation_kinds=_ANCHOR_REFERENCE_RELATIONS,
            )
        raise ValueError(f"unsupported symbolic reference key: {key}")


class TemporalInterpretationInput(ContractModel):
    """Date-free pass-two view; private maps restore canonical identities after the call."""

    _evidence_ids: dict[str, str] = PrivateAttr(default_factory=dict)
    _anchor_ids: dict[str, str] = PrivateAttr(default_factory=dict)
    _reference_keys: dict[str, str] = PrivateAttr(default_factory=dict)
    _anchors: dict[str, TemporalAnchor] = PrivateAttr(default_factory=dict)
    _claim_labels: dict[str, list[TemporalEvidenceClaim]] = PrivateAttr(default_factory=dict)
    _anchor_evidence: dict[str, str] = PrivateAttr(default_factory=dict)
    _evidence_spans: dict[str, tuple[int, int]] = PrivateAttr(default_factory=dict)
    _transcript_evidence_spans: dict[str, tuple[int, int]] = PrivateAttr(default_factory=dict)

    temporal_transcript: str = Field(
        min_length=1,
        description=(
            "Ordered handle-labelled temporal clauses for coreference. Each [eN] prefix names the "
            "matching evidence_catalog entry; output selects handles, not quotes."
        ),
    )
    evidence_catalog: list[TemporalEvidenceCatalogEntry] = Field(
        default_factory=list,
        description="Allowed evidence handles. Empty means emit no decisions.",
    )
    explicit_anchor_catalog: list[ExplicitAnchorCatalogEntry] = Field(
        default_factory=list,
        description="Allowed anchor handles. Direct anchor facts are inserted deterministically.",
    )
    allowed_symbolic_references: list[SymbolicReferenceCatalogEntry] = Field(
        default_factory=list,
        description="Allowed reference handles; concrete values remain deterministic.",
    )

    @model_validator(mode="after")
    def validate_catalogs(self) -> TemporalInterpretationInput:
        evidence_ids = [entry.handle for entry in self.evidence_catalog]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence catalog IDs must be unique")
        anchor_ids = [entry.handle for entry in self.explicit_anchor_catalog]
        if len(anchor_ids) != len(set(anchor_ids)):
            raise ValueError("explicit anchor catalog IDs must be unique")
        reference_keys = [entry.handle for entry in self.allowed_symbolic_references]
        if len(reference_keys) != len(set(reference_keys)):
            raise ValueError("symbolic reference catalog keys must be unique")
        if not self._evidence_ids:
            self._evidence_ids = {
                entry.handle: entry.evidence_id for entry in self.evidence_catalog
            }
        if not self._anchor_ids:
            self._anchor_ids = {
                entry.handle: entry.anchor_id for entry in self.explicit_anchor_catalog
            }
        if not self._reference_keys:
            self._reference_keys = {
                entry.handle: entry.key for entry in self.allowed_symbolic_references
            }
        if not self._claim_labels:
            self._claim_labels = {
                entry.evidence_id: entry._legacy_claim_labels for entry in self.evidence_catalog
            }
        if not self._anchor_evidence:
            for anchor_handle, anchor_id in self._anchor_ids.items():
                anchor = next(
                    item for item in self.explicit_anchor_catalog if item.handle == anchor_handle
                )
                claim = (
                    TemporalEvidenceClaim.DEPARTURE_ANCHOR
                    if anchor.applies_to is TemporalTarget.DEPARTURE
                    else TemporalEvidenceClaim.RETURN_ANCHOR
                )
                matching = next(
                    (
                        evidence_id
                        for evidence_id, claims in self._claim_labels.items()
                        if claim in claims
                    ),
                    "",
                )
                self._anchor_evidence[anchor_id] = matching
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


# The selector contract is intentionally separate from the v2 relation-authoring contract
# above.  It exposes an already-built, finite choice set and accepts only opaque candidate
# handles back.  These models must never acquire resolved calendar state or canonical IDs.
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
    """How one candidate may use a local literal anchor."""

    anchor: str = Field(min_length=1, description="An aN handle from local_anchors.")
    mode: Literal["direct_window", "reference_only", "unresolved_support"]


class TemporalSelectorCandidate(ContractModel):
    """A single pre-authored local choice; the selector cannot modify its fields."""

    handle: str = Field(min_length=1, description="Opaque candidate handle such as c0.")
    summary: str = Field(
        min_length=1,
        description="Deterministic, date-free description of the supplied interpretation.",
    )
    interpretation_kind: str | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description=(
            "Pre-authored safe interpretation label. It describes the supplied choice and is "
            "not an instruction to invent a new relation."
        ),
    )
    relation_ordinal: int | None = Field(
        default=None,
        ge=1,
        exclude_if=lambda value: value is None,
        description=(
            "Literal ordinal for an interpretation where count changes the relation, such as "
            "the second weekend after an anchor."
        ),
    )
    target: Literal["departure", "return", "unspecified"] | None = None
    covers: tuple[str, ...] = Field(description="eN clauses covered by this candidate.")
    requires: tuple[str, ...] = Field(
        description="Opaque pN production slots this choice depends on, if any."
    )
    produces: tuple[str, ...] = Field(
        description="Opaque pN production slots this choice contributes, if any."
    )
    anchor_uses: tuple[TemporalSelectorAnchorUse, ...] = ()
    composition: Literal["extend_start"] | None = None
    composition_operand: str | None = Field(
        default=None,
        description="The required pN slot used by composition, when composition is present.",
    )


class TemporalSelectorGroup(ContractModel):
    """Mutually exclusive selector choices for one local semantic group."""

    handle: str = Field(min_length=1, description="Opaque exclusive-group handle such as g0.")
    candidates: tuple[TemporalSelectorCandidate, ...] = Field(min_length=1)


class TemporalSelectorInput(ContractModel):
    """Complete date-free view for the optional temporal candidate selector.

    Private maps restore opaque handles after the call.  Private attributes are deliberately not
    serialized by Pydantic, so the selector cannot receive internal semantic candidate handles.
    """

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
        candidates = [
            candidate for group in self.candidate_groups for candidate in group.candidates
        ]
        unique([candidate.handle for candidate in candidates], "candidate")
        if any(
            not slot.startswith("p") or not slot[1:].isdigit()
            for slot in self.available_productions
        ):
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
            if any(
                not slot.startswith("p") or not slot[1:].isdigit()
                for slot in (*candidate.requires, *candidate.produces)
            ):
                raise ValueError("selector production slots must use pN handles")
            if candidate.composition is None and candidate.composition_operand is not None:
                raise ValueError("selector candidate has an operand without composition")
            if (
                candidate.composition is not None
                and candidate.composition_operand not in candidate.requires
            ):
                raise ValueError("selector composition operand must be required")
        return self


class TemporalSelectorOutput(ContractModel):
    """The selector's complete output contract: choose supplied opaque candidates only."""

    selected_candidates: list[str] = Field(
        description="Complete list of opaque cN candidate handles selected from the supplied groups."
    )


def build_temporal_interpretation_input(
    request_text: str,
    extraction: CoarseIntentExtraction,
    evidence: list[GroundedTemporalEvidence],
) -> TemporalInterpretationInput:
    """Build the complete, date-free pass-two catalog view deterministically."""

    # Do not pass source offsets, canonical IDs, claim labels, direct-relation hints, or the full
    # travel request into Pass 2.  Date-free target permissions retain only the endpoint binding
    # required to interpret a bounded temporal clause.  The private maps never serialize.
    model_input = TemporalInterpretationInput(
        temporal_transcript="\n".join(
            f"[e{source_order}] {item.span.text}" for source_order, item in enumerate(evidence)
        )
        or "No temporal wording.",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                handle=f"e{source_order}",
                text=item.span.text,
                allowed_targets=_evidence_targets(item.claim_ids),
                allowed_relation_kinds=_evidence_relation_kinds(item.claim_ids),
            )
            for source_order, item in enumerate(evidence)
        ],
        explicit_anchor_catalog=[
            ExplicitAnchorCatalogEntry(
                handle=f"a{index}",
                kind=anchor.kind,
                applies_to=anchor.applies_to,
            )
            for index, anchor in enumerate(extraction.date_anchors)
        ],
        allowed_symbolic_references=[
            SymbolicReferenceCatalogEntry.from_key("context:request_date", "r0"),
            *[
                SymbolicReferenceCatalogEntry.from_key(
                    f"anchor_ref:{anchor.anchor_id}:{edge}", f"r{index + 1}"
                )
                for index, (anchor, edge) in enumerate(
                    (anchor, edge)
                    for anchor in extraction.date_anchors
                    for edge in ("start", "end")
                )
            ],
            *[
                SymbolicReferenceCatalogEntry.from_key(
                    f"request_field:{target}:{edge}",
                    f"r{index + 1 + 2 * len(extraction.date_anchors)}",
                )
                for index, (target, edge) in enumerate(
                    (target, edge)
                    for target in ("departure", "return")
                    for edge in ("start", "end", "whole_interval")
                )
            ],
        ],
    )
    model_input._evidence_ids = {
        f"e{index}": item.evidence_id for index, item in enumerate(evidence)
    }
    for evidence_entry in model_input.evidence_catalog:
        evidence_entry._canonical_id = model_input._evidence_ids[evidence_entry.handle]
    model_input._claim_labels = {item.evidence_id: item.claim_ids for item in evidence}
    model_input._evidence_spans = {
        item.evidence_id: (item.span.start, item.span.end) for item in evidence
    }
    transcript_offset = 0
    for index, item in enumerate(evidence):
        if index:
            transcript_offset += 1  # the newline inserted by the condensed transcript join
        transcript_offset += len(f"[e{index}] ")
        start = transcript_offset
        transcript_offset += len(item.span.text)
        model_input._transcript_evidence_spans[item.evidence_id] = (start, transcript_offset)
    model_input._anchor_ids = {
        f"a{index}": anchor.anchor_id for index, anchor in enumerate(extraction.date_anchors)
    }
    for anchor_entry in model_input.explicit_anchor_catalog:
        anchor_entry._canonical_id = model_input._anchor_ids[anchor_entry.handle]
    model_input._anchors = {
        f"a{index}": anchor for index, anchor in enumerate(extraction.date_anchors)
    }
    model_input._anchor_evidence = {
        anchor.anchor_id: next(
            (item.evidence_id for item in evidence if item.span.text == anchor.raw_text),
            "",
        )
        for anchor in extraction.date_anchors
    }
    reference_keys = (
        ["context:request_date"]
        + [
            f"anchor_ref:{anchor.anchor_id}:{edge}"
            for anchor in extraction.date_anchors
            for edge in ("start", "end")
        ]
        + [
            f"request_field:{target}:{edge}"
            for target in ("departure", "return")
            for edge in ("start", "end", "whole_interval")
        ]
    )
    model_input._reference_keys = {f"r{index}": key for index, key in enumerate(reference_keys)}
    for reference_entry in model_input.allowed_symbolic_references:
        reference_entry._canonical_key = model_input._reference_keys[reference_entry.handle]
    return model_input
