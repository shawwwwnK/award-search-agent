"""Shared catalog-backed conformance checks for every temporal resolver."""

from __future__ import annotations

import re

from award_agent.domain import (
    AnchorReference,
    AnchorWindowConstraint,
    MonthPortionConstraint,
    RelativeCalendarPeriodConstraint,
    RelativeOffsetConstraint,
    RelativeWeekdayConstraint,
    RelativeWeekendConstraint,
    RequestFieldReference,
    SemanticDurationConstraint,
    SymbolicContextReference,
    TemporalConstraint,
    TemporalEvidenceClaim,
    TemporalRelationGraph,
    TemporalTarget,
    UnresolvedRelationConstraint,
)
from award_agent.intent.evidence import TemporalResolutionValidationError
from award_agent.intent.model_views import (
    TemporalEvidenceCatalogEntry,
    TemporalInterpretationInput,
)

_TARGET_CLAIMS = {
    TemporalTarget.DEPARTURE: {
        TemporalEvidenceClaim.DEPARTURE_ANCHOR,
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
        TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
    },
    TemporalTarget.RETURN: {
        TemporalEvidenceClaim.RETURN_ANCHOR,
        TemporalEvidenceClaim.RETURN_PERIOD,
        TemporalEvidenceClaim.ALTERNATE_RETURN_DAY,
    },
}
_DURATION_CLAIMS = {
    TemporalEvidenceClaim.DURATION,
    TemporalEvidenceClaim.APPROXIMATE_DURATION,
}
_SEASON = re.compile(r"\b(?:spring|summer|autumn|fall|winter)\b", re.IGNORECASE)
_FIRST_WEEK_OF_MONTH = re.compile(
    r"\b(?:first|1st)\s+week\s+of\s+"
    r"(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\b",
    re.IGNORECASE,
)
_BOUNDED_CONSTRAINTS = (
    AnchorWindowConstraint,
    MonthPortionConstraint,
    RelativeCalendarPeriodConstraint,
    RelativeWeekendConstraint,
    RelativeWeekdayConstraint,
    RelativeOffsetConstraint,
)


def _reference_key(constraint: TemporalConstraint) -> str | None:
    reference = getattr(constraint, "reference", None)
    if isinstance(reference, AnchorReference):
        return f"anchor_ref:{reference.anchor_id}:{reference.edge.value}"
    if isinstance(reference, RequestFieldReference):
        return f"request_field:{reference.field.value}:{reference.edge.value}"
    if isinstance(reference, SymbolicContextReference):
        return reference.key
    return None


def _catalog_evidence(
    constraint: TemporalConstraint,
    model_input: TemporalInterpretationInput,
    constraint_index: int,
) -> TemporalEvidenceCatalogEntry:
    raw_text = constraint.raw_text
    matches = sorted(
        (item for item in model_input.evidence_catalog if item.text == raw_text),
        key=lambda item: (item.source_start, item.source_end),
    )
    occurrence = getattr(constraint, "occurrence_index", None)
    if not matches or (occurrence is not None and occurrence >= len(matches)):
        raise TemporalResolutionValidationError(
            "temporal relation evidence is not in the supplied catalog",
            stage="pass_two_conformance",
            error_code="unknown_evidence_id",
            constraint_index=constraint_index,
            relation_kind=constraint.kind,
            evidence_id=None,
            validation_cause=f"no catalog entry matches {raw_text!r} occurrence {occurrence!r}",
        )
    if len(matches) > 1 and occurrence is None:
        raise TemporalResolutionValidationError(
            "repeated relation evidence requires its catalog occurrence",
            stage="pass_two_conformance",
            error_code="ambiguous_evidence_id",
            constraint_index=constraint_index,
            relation_kind=constraint.kind,
            validation_cause=f"{raw_text!r} matches {len(matches)} catalog entries",
        )
    return matches[occurrence or 0]


def _compatible_claims(constraint: TemporalConstraint) -> set[TemporalEvidenceClaim]:
    target = getattr(constraint, "target", None)
    if isinstance(constraint, SemanticDurationConstraint):
        return _DURATION_CLAIMS
    if isinstance(constraint, UnresolvedRelationConstraint):
        return (
            set(TemporalEvidenceClaim)
            if target is None
            else _TARGET_CLAIMS[target] | _DURATION_CLAIMS
        )
    assert isinstance(target, TemporalTarget)
    return _TARGET_CLAIMS[target]


def _overlaps(entry: TemporalEvidenceCatalogEntry, start: int, end: int) -> bool:
    return entry.source_start < end and start < entry.source_end


def _validate_supported_bounded_language(
    constraint: TemporalConstraint,
    evidence: TemporalEvidenceCatalogEntry,
    model_input: TemporalInterpretationInput,
    constraint_index: int,
) -> None:
    if not isinstance(constraint, _BOUNDED_CONSTRAINTS):
        return
    unsupported: str | None = None
    for match in _FIRST_WEEK_OF_MONTH.finditer(model_input.temporal_transcript):
        if _overlaps(evidence, match.start(), match.end()):
            unsupported = "first-week month portions are not represented by the approved vocabulary"
            break
    if unsupported is None:
        return
    raise TemporalResolutionValidationError(
        unsupported,
        stage="pass_two_conformance",
        error_code="unsupported_bounded_temporal_language",
        constraint_index=constraint_index,
        relation_kind=constraint.kind,
        contradictory_fields=("relation_kind", "evidence_id"),
        evidence_id=evidence.evidence_id,
        validation_cause=unsupported,
    )


def _anchor_claims_consumed(
    constraint: TemporalConstraint,
    model_input: TemporalInterpretationInput,
) -> set[tuple[str, TemporalEvidenceClaim]]:
    anchor_ids: set[str] = set()
    direct_anchor_id = getattr(constraint, "anchor_id", None)
    if isinstance(direct_anchor_id, str):
        anchor_ids.add(direct_anchor_id)
    reference = getattr(constraint, "reference", None)
    if isinstance(reference, AnchorReference):
        anchor_ids.add(reference.anchor_id)
    consumed: set[tuple[str, TemporalEvidenceClaim]] = set()
    anchors = {item.anchor_id: item for item in model_input.explicit_anchor_catalog}
    for anchor_id in anchor_ids:
        anchor = anchors.get(anchor_id)
        if anchor is None:
            continue
        suffix = anchor.anchor_id.rsplit(":", 2)
        if len(suffix) != 3 or not suffix[-2].isdigit() or not suffix[-1].isdigit():
            continue
        claim = (
            TemporalEvidenceClaim.DEPARTURE_ANCHOR
            if anchor.applies_to is TemporalTarget.DEPARTURE
            else TemporalEvidenceClaim.RETURN_ANCHOR
        )
        consumed.add((f"request:{suffix[-2]}:{suffix[-1]}", claim))
    return consumed


def validate_temporal_conformance(
    model_input: TemporalInterpretationInput,
    graph: TemporalRelationGraph,
) -> None:
    """Validate catalogs, evidence semantics, and claim coverage for any resolver result."""

    allowed_anchors = {item.anchor_id for item in model_input.explicit_anchor_catalog}
    anchors_by_id = {item.anchor_id: item for item in model_input.explicit_anchor_catalog}
    allowed_references = {item.key for item in model_input.allowed_symbolic_references}
    consumed: set[tuple[str, TemporalEvidenceClaim]] = set()
    unresolved_evidence: list[TemporalEvidenceCatalogEntry] = []
    bounded_evidence: list[tuple[int, TemporalConstraint, TemporalEvidenceCatalogEntry]] = []
    for index, constraint in enumerate(graph.constraints):
        evidence = _catalog_evidence(constraint, model_input, index)
        anchor_id = getattr(constraint, "anchor_id", None)
        if isinstance(anchor_id, str) and anchor_id not in allowed_anchors:
            raise TemporalResolutionValidationError(
                f"temporal relation references missing anchor: {anchor_id}",
                stage="pass_two_conformance",
                error_code="unknown_anchor_id",
                constraint_index=index,
                relation_kind=constraint.kind,
                evidence_id=evidence.evidence_id,
                reference_id=anchor_id,
            )
        if isinstance(anchor_id, str):
            anchor = anchors_by_id[anchor_id]
            target = getattr(constraint, "target", None)
            if target is not anchor.applies_to:
                raise TemporalResolutionValidationError(
                    "anchor target is incompatible with relation target",
                    stage="pass_two_conformance",
                    error_code="incompatible_relation_fields",
                    constraint_index=index,
                    relation_kind=constraint.kind,
                    contradictory_fields=("anchor_id", "target"),
                    evidence_id=evidence.evidence_id,
                    reference_id=anchor_id,
                )
            if isinstance(constraint, MonthPortionConstraint) and anchor.kind != "month":
                raise TemporalResolutionValidationError(
                    "month_portion requires a month anchor",
                    stage="pass_two_conformance",
                    error_code="incompatible_relation_fields",
                    constraint_index=index,
                    relation_kind=constraint.kind,
                    contradictory_fields=("anchor_id", "relation_kind"),
                    evidence_id=evidence.evidence_id,
                    reference_id=anchor_id,
                )
        reference_key = _reference_key(constraint)
        if reference_key is not None and reference_key not in allowed_references:
            raise TemporalResolutionValidationError(
                f"reference is not in supplied catalog: {reference_key}",
                stage="pass_two_conformance",
                error_code="unknown_reference_key",
                constraint_index=index,
                relation_kind=constraint.kind,
                evidence_id=evidence.evidence_id,
                reference_id=reference_key,
            )
        compatible = set(evidence.claim_labels) & _compatible_claims(constraint)
        if not compatible:
            raise TemporalResolutionValidationError(
                "relation evidence claims are incompatible with its kind and target",
                stage="pass_two_conformance",
                error_code="incompatible_evidence_claim",
                constraint_index=index,
                relation_kind=constraint.kind,
                contradictory_fields=("evidence_id", "target"),
                evidence_id=evidence.evidence_id,
            )
        consumed.update((evidence.evidence_id, claim) for claim in compatible)
        consumed.update(_anchor_claims_consumed(constraint, model_input))
        if isinstance(constraint, UnresolvedRelationConstraint):
            unresolved_evidence.append(evidence)
        elif isinstance(constraint, _BOUNDED_CONSTRAINTS):
            bounded_evidence.append((index, constraint, evidence))
        _validate_supported_bounded_language(constraint, evidence, model_input, index)

    for match in _SEASON.finditer(model_input.temporal_transcript):
        covering_unresolved = [
            evidence
            for evidence in unresolved_evidence
            if _overlaps(evidence, match.start(), match.end())
        ]
        if covering_unresolved:
            for index, constraint, evidence in bounded_evidence:
                if any(
                    _overlaps(
                        evidence,
                        unresolved.source_start,
                        unresolved.source_end,
                    )
                    for unresolved in covering_unresolved
                ):
                    cause = "bounded relation evidence overlaps unresolved season evidence"
                    raise TemporalResolutionValidationError(
                        cause,
                        stage="pass_two_conformance",
                        error_code="unsupported_bounded_temporal_language",
                        constraint_index=index,
                        relation_kind=constraint.kind,
                        contradictory_fields=("relation_kind", "evidence_id"),
                        evidence_id=evidence.evidence_id,
                        validation_cause=cause,
                    )
            continue
        overlapping = next(
            (
                evidence
                for evidence in model_input.evidence_catalog
                if _overlaps(evidence, match.start(), match.end())
            ),
            None,
        )
        cause = "season language has no approved deterministic calendar policy"
        raise TemporalResolutionValidationError(
            cause,
            stage="pass_two_conformance",
            error_code="unsupported_bounded_temporal_language",
            evidence_id=overlapping.evidence_id if overlapping is not None else None,
            validation_cause=(
                f"season token {match.group(0)!r} is not covered by unresolved relation evidence"
            ),
        )

    for evidence in model_input.evidence_catalog:
        for claim in evidence.claim_labels:
            if (evidence.evidence_id, claim) in consumed:
                continue
            raise TemporalResolutionValidationError(
                f"first-pass claim {claim.value!r} was not consumed by a compatible relation "
                "or preserved as unresolved",
                stage="pass_two_conformance",
                error_code="unconsumed_temporal_claim",
                evidence_id=evidence.evidence_id,
            )
