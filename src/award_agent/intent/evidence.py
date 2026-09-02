"""Strict temporal-evidence grounding against the immutable request text."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Literal

from award_agent.domain import (
    CoarseIntentExtraction,
    DateResolutionProposal,
    GroundedTemporalEvidence,
    RawRequest,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    ValidatedSourceSpan,
)


class EvidenceErrorCode(str, Enum):
    UNGROUNDED_QUOTE = "ungrounded_quote"
    AMBIGUOUS_QUOTE = "ambiguous_quote"
    INVALID_OCCURRENCE = "invalid_occurrence"


ValidationStage = Literal[
    "pass_one_grounding",
    "pass_one_anchor_validation",
    "pass_two_wire_conversion",
    "pass_two_conformance",
    "pass_two_dependency_validation",
    "deterministic_evaluation",
]


@dataclass(frozen=True, slots=True)
class TemporalValidationDetails:
    """Stable machine-readable context for one deterministic temporal failure."""

    stage: ValidationStage
    error_code: str
    relation_index: int | None = None
    constraint_index: int | None = None
    selected_relation_kind: str | None = None
    collection: str | None = None
    missing_fields: tuple[str, ...] = ()
    contradictory_fields: tuple[str, ...] = ()
    evidence_id: str | None = None
    reference_id: str | None = None
    validation_cause: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class TemporalResolutionValidationError(ValueError):
    """Deterministic temporal failure with a serializable owning-layer envelope."""

    def __init__(
        self,
        message: str,
        *,
        stage: ValidationStage = "deterministic_evaluation",
        error_code: str = "temporal_validation_failed",
        relation_index: int | None = None,
        constraint_index: int | None = None,
        relation_kind: str | None = None,
        collection: str | None = None,
        missing_fields: tuple[str, ...] = (),
        contradictory_fields: tuple[str, ...] = (),
        evidence_id: str | None = None,
        reference_id: str | None = None,
        validation_cause: str | None = None,
    ) -> None:
        self.details = TemporalValidationDetails(
            stage=stage,
            error_code=error_code,
            relation_index=relation_index,
            constraint_index=constraint_index,
            selected_relation_kind=relation_kind,
            collection=collection,
            missing_fields=missing_fields,
            contradictory_fields=contradictory_fields,
            evidence_id=evidence_id,
            reference_id=reference_id,
            validation_cause=validation_cause or message,
        )
        super().__init__(message)

    def as_dict(self) -> dict[str, Any]:
        return self.details.as_dict()

    def attach_repair_trace(self, trace: dict[str, Any]) -> TemporalResolutionValidationError:
        """Attach date-free attempt metadata without changing the structured root cause."""

        self.repair_trace = trace
        return self


class TemporalEvidenceValidationError(TemporalResolutionValidationError):
    """Structured failure to resolve an exact model-facing quote to one source span."""

    def __init__(
        self,
        *,
        code: EvidenceErrorCode,
        quote: str,
        claim_id: str,
        reason: str,
        stage: ValidationStage = "pass_one_grounding",
        constraint_index: int | None = None,
        relation_kind: str | None = None,
    ) -> None:
        self.code = code
        self.quote = quote
        self.claim_id = claim_id
        self.reason = reason
        self.ambiguous = code is EvidenceErrorCode.AMBIGUOUS_QUOTE
        super().__init__(
            f"{code.value}: claim={claim_id!r} quote={quote!r}: {reason}",
            stage=stage,
            error_code=code.value,
            constraint_index=constraint_index,
            relation_kind=relation_kind,
            validation_cause=reason,
        )


def _occurrences(source: str, quote: str) -> list[int]:
    starts: list[int] = []
    cursor = 0
    while True:
        start = source.find(quote, cursor)
        if start < 0:
            return starts
        starts.append(start)
        cursor = start + 1


def resolve_source_quote(
    source: str,
    quote: str,
    *,
    claim_id: str,
    occurrence_index: int | None = None,
) -> ValidatedSourceSpan:
    """Resolve an exact quote using Python string offsets and no normalization."""

    if not quote:
        raise TemporalEvidenceValidationError(
            code=EvidenceErrorCode.UNGROUNDED_QUOTE,
            quote=quote,
            claim_id=claim_id,
            reason="the evidence quote is empty",
        )
    starts = _occurrences(source, quote)
    if not starts:
        raise TemporalEvidenceValidationError(
            code=EvidenceErrorCode.UNGROUNDED_QUOTE,
            quote=quote,
            claim_id=claim_id,
            reason="the exact quote is absent from the original request",
        )
    if occurrence_index is None:
        if len(starts) != 1:
            raise TemporalEvidenceValidationError(
                code=EvidenceErrorCode.AMBIGUOUS_QUOTE,
                quote=quote,
                claim_id=claim_id,
                reason=(
                    f"the quote occurs {len(starts)} times; provide a zero-based occurrence_index"
                ),
            )
        start = starts[0]
    else:
        if occurrence_index < 0 or occurrence_index >= len(starts):
            raise TemporalEvidenceValidationError(
                code=EvidenceErrorCode.INVALID_OCCURRENCE,
                quote=quote,
                claim_id=claim_id,
                reason=(
                    f"occurrence_index {occurrence_index} is outside the {len(starts)} matches"
                ),
            )
        start = starts[occurrence_index]
    end = start + len(quote)
    return ValidatedSourceSpan(start=start, end=end, text=source[start:end])


def validate_source_span(source: str, span: ValidatedSourceSpan, *, claim_id: str) -> None:
    """Reject externally supplied offset/text combinations that are not source-derived."""

    if span.end > len(source) or source[span.start : span.end] != span.text:
        raise TemporalEvidenceValidationError(
            code=EvidenceErrorCode.UNGROUNDED_QUOTE,
            quote=span.text,
            claim_id=claim_id,
            reason="span text does not equal original_request[start:end]",
        )


def _legacy_claims(phrase: TemporalPhrase) -> list[TemporalEvidenceClaim]:
    """Temporary adapter for first-party objects created before claim links existed."""

    claims_by_target = {
        TemporalPhraseTarget.DEPARTURE: [TemporalEvidenceClaim.DEPARTURE_PERIOD],
        TemporalPhraseTarget.RETURN: [TemporalEvidenceClaim.RETURN_PERIOD],
        TemporalPhraseTarget.DURATION: [TemporalEvidenceClaim.DURATION],
        TemporalPhraseTarget.UNSPECIFIED: [TemporalEvidenceClaim.UNSPECIFIED],
    }
    return claims_by_target[phrase.applies_to]


def _anchor_claim(applies_to: TemporalTarget) -> TemporalEvidenceClaim:
    if applies_to is TemporalTarget.DEPARTURE:
        return TemporalEvidenceClaim.DEPARTURE_ANCHOR
    return TemporalEvidenceClaim.RETURN_ANCHOR


def _merge_claims(
    existing: Iterable[TemporalEvidenceClaim],
    additions: Iterable[TemporalEvidenceClaim],
) -> list[TemporalEvidenceClaim]:
    return list(dict.fromkeys([*existing, *additions]))


def ground_temporal_evidence(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
) -> list[GroundedTemporalEvidence]:
    """Canonicalize all first-pass temporal quotes and merge identical source spans."""

    by_offsets: dict[tuple[int, int], GroundedTemporalEvidence] = {}

    def add(
        quote: str,
        claims: list[TemporalEvidenceClaim],
        occurrence_index: int | None,
    ) -> None:
        claim_label = ",".join(claim.value for claim in claims)
        span = resolve_source_quote(
            request.text,
            quote,
            claim_id=claim_label,
            occurrence_index=occurrence_index,
        )
        key = (span.start, span.end)
        existing = by_offsets.get(key)
        if existing is None:
            by_offsets[key] = GroundedTemporalEvidence(
                evidence_id=f"request:{span.start}:{span.end}",
                claim_ids=claims,
                span=span,
            )
            return
        by_offsets[key] = existing.model_copy(
            update={"claim_ids": _merge_claims(existing.claim_ids, claims)}
        )

    for anchor in extraction.date_anchors:
        add(
            anchor.raw_text,
            [_anchor_claim(anchor.applies_to)],
            anchor.occurrence_index,
        )
    for phrase in extraction.temporal_phrases:
        claims = phrase.claim_ids or _legacy_claims(phrase)
        add(phrase.raw_text, claims, phrase.occurrence_index)

    grounded = sorted(
        by_offsets.values(),
        key=lambda evidence: (evidence.span.start, evidence.span.end),
    )
    claim_order = {claim: index for index, claim in enumerate(TemporalEvidenceClaim)}
    return [
        evidence.model_copy(
            update={"claim_ids": sorted(evidence.claim_ids, key=claim_order.__getitem__)}
        )
        for evidence in grounded
    ]


def assign_stable_anchor_ids(
    request: RawRequest,
    extraction: CoarseIntentExtraction,
) -> CoarseIntentExtraction:
    """Replace model-authored anchor IDs with source-derived checkpoint identities."""

    stable_anchors_with_spans = []
    seen_ids: set[str] = set()
    for anchor in extraction.date_anchors:
        span = resolve_source_quote(
            request.text,
            anchor.raw_text,
            claim_id=f"{anchor.applies_to.value}_anchor",
            occurrence_index=anchor.occurrence_index,
        )
        anchor_id = f"anchor:{anchor.kind}:{anchor.applies_to.value}:{span.start}:{span.end}"
        if anchor_id in seen_ids:
            raise TemporalResolutionValidationError(
                f"duplicate explicit anchor at the same source span: {anchor_id}",
                stage="pass_one_anchor_validation",
                error_code="duplicate_explicit_anchor",
                relation_kind=anchor.kind,
                contradictory_fields=("source_span", "anchor_kind", "target"),
                reference_id=anchor_id,
            )
        seen_ids.add(anchor_id)
        stable_anchors_with_spans.append(
            (
                (span.start, span.end, anchor.kind, anchor.applies_to.value),
                anchor.model_copy(update={"anchor_id": anchor_id}),
            )
        )
    stable_anchors = [
        anchor for _, anchor in sorted(stable_anchors_with_spans, key=lambda item: item[0])
    ]
    return extraction.model_copy(update={"date_anchors": stable_anchors})


def ground_date_resolution_evidence(
    request: RawRequest,
    proposal: DateResolutionProposal,
    existing: list[GroundedTemporalEvidence],
) -> list[GroundedTemporalEvidence]:
    """Canonicalize second-pass evidence not already represented by first-pass spans."""

    grounded = list(existing)

    def add_if_new(quote: str, claim: TemporalEvidenceClaim) -> None:
        matches = [item for item in grounded if item.span.text == quote]
        if len(matches) == 1:
            return
        if len(matches) > 1:
            raise TemporalEvidenceValidationError(
                code=EvidenceErrorCode.AMBIGUOUS_QUOTE,
                quote=quote,
                claim_id=claim.value,
                reason="the quote maps to multiple already-grounded request spans",
            )
        span = resolve_source_quote(request.text, quote, claim_id=claim.value)
        grounded.append(
            GroundedTemporalEvidence(
                evidence_id=f"request:{span.start}:{span.end}",
                claim_ids=[claim],
                span=span,
            )
        )

    if proposal.departure is not None:
        for quote in proposal.departure.supporting_text:
            add_if_new(quote, TemporalEvidenceClaim.DEPARTURE_PERIOD)
    if proposal.return_date is not None:
        for quote in proposal.return_date.supporting_text:
            add_if_new(quote, TemporalEvidenceClaim.RETURN_PERIOD)
    if proposal.interpreted_duration is not None:
        add_if_new(proposal.interpreted_duration.raw_text, TemporalEvidenceClaim.DURATION)
    for unresolved in proposal.unresolved:
        claim = {
            "departure": TemporalEvidenceClaim.DEPARTURE_PERIOD,
            "return_or_duration": TemporalEvidenceClaim.RETURN_PERIOD,
            "dates": TemporalEvidenceClaim.UNSPECIFIED,
        }[unresolved.field]
        add_if_new(unresolved.raw_text, claim)

    return sorted(grounded, key=lambda evidence: evidence.span.start)


def ground_temporal_relation_evidence(
    request: RawRequest,
    graph: TemporalRelationGraph,
    existing: list[GroundedTemporalEvidence],
) -> list[GroundedTemporalEvidence]:
    """Canonicalize second-pass relation evidence with explicit occurrence handling."""

    grounded = list(existing)
    for constraint in graph.constraints:
        target = getattr(constraint, "target", None)
        claim = TemporalEvidenceClaim.UNSPECIFIED
        if getattr(constraint, "kind", None) == "duration":
            claim = TemporalEvidenceClaim.DURATION
        elif target is TemporalTarget.DEPARTURE:
            claim = TemporalEvidenceClaim.DEPARTURE_PERIOD
        elif target is TemporalTarget.RETURN:
            claim = TemporalEvidenceClaim.RETURN_PERIOD
        span = resolve_source_quote(
            request.text,
            constraint.raw_text,
            claim_id=claim.value,
            occurrence_index=constraint.occurrence_index,
        )
        matching = [
            (index, item)
            for index, item in enumerate(grounded)
            if item.span.start == span.start and item.span.end == span.end
        ]
        if matching:
            # First-pass claim links remain authoritative when the exact span already exists.
            # The second pass adds semantic structure, not additional evidence claims.
            continue
        else:
            grounded.append(
                GroundedTemporalEvidence(
                    evidence_id=f"request:{span.start}:{span.end}",
                    claim_ids=[claim],
                    span=span,
                )
            )
    return sorted(grounded, key=lambda evidence: evidence.span.start)
