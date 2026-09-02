"""Deterministic compilation and scoring of claim-level temporal evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import Field

from award_agent.domain import (
    ContractModel,
    GroundedTemporalEvidence,
    TemporalEvidenceClaim,
    ValidatedSourceSpan,
)
from award_agent.intent.evidence import (
    TemporalEvidenceValidationError,
    resolve_source_quote,
    validate_source_span,
)


class EvalFixtureValidationError(ValueError):
    """Raised when human-authored evidence expectations cannot be grounded."""

    code = "malformed_eval_fixture"

    def __init__(self, *, claim_id: str, reason: str, quote: str | None = None) -> None:
        self.claim_id = claim_id
        self.reason = reason
        self.quote = quote
        super().__init__(f"{self.code}: claim={claim_id!r} quote={quote!r}: {reason}")


class CompiledEvidenceExpectation(ContractModel):
    claim_id: TemporalEvidenceClaim
    allowed_envelopes: list[ValidatedSourceSpan] = Field(min_length=1)
    required_all: list[ValidatedSourceSpan] = Field(default_factory=list)
    required_any_groups: list[list[ValidatedSourceSpan]] = Field(default_factory=list)
    preferred_spans: list[ValidatedSourceSpan] = Field(default_factory=list)


class EvidenceSupportFailure(ContractModel):
    code: str
    claim_id: str
    quote: str | None = None
    detail: str


class EvidenceEvaluationResult(ContractModel):
    grounding_valid: bool
    evidence_support_valid: bool
    preferred_boundary_exact_match: bool
    missing_expected_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    overbroad_spans: list[str] = Field(default_factory=list)
    insufficient_spans: list[str] = Field(default_factory=list)
    failures: list[EvidenceSupportFailure] = Field(default_factory=list)


def _quote_spec(value: Any, *, claim_id: str) -> tuple[str, int | None]:
    if isinstance(value, str):
        return value, None
    if isinstance(value, Mapping):
        quote = value.get("quote")
        occurrence = value.get("occurrence_index")
        if not isinstance(quote, str) or (
            occurrence is not None and not isinstance(occurrence, int)
        ):
            raise EvalFixtureValidationError(
                claim_id=claim_id,
                quote=quote if isinstance(quote, str) else None,
                reason="quote specs require a string quote and optional integer occurrence_index",
            )
        return quote, occurrence
    raise EvalFixtureValidationError(
        claim_id=claim_id,
        reason="fixture evidence must be a string or quote mapping",
    )


def _compile_span(source: str, value: Any, *, claim_id: str) -> ValidatedSourceSpan:
    quote, occurrence = _quote_spec(value, claim_id=claim_id)
    try:
        return resolve_source_quote(
            source,
            quote,
            claim_id=claim_id,
            occurrence_index=occurrence,
        )
    except TemporalEvidenceValidationError as exc:
        raise EvalFixtureValidationError(
            claim_id=claim_id,
            quote=quote,
            reason=f"{exc.code.value}: {exc.reason}",
        ) from exc


def _inside(inner: ValidatedSourceSpan, outer: ValidatedSourceSpan) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


def compile_evidence_expectations(
    source: str,
    raw_expectations: Mapping[str, Any],
) -> list[CompiledEvidenceExpectation]:
    """Compile exact fixture strings to validated Python source offsets."""

    compiled: list[CompiledEvidenceExpectation] = []
    for raw_claim_id, raw_rule in raw_expectations.items():
        try:
            claim_id = TemporalEvidenceClaim(raw_claim_id)
        except ValueError as exc:
            raise EvalFixtureValidationError(
                claim_id=raw_claim_id,
                reason="unsupported_semantic_claim",
            ) from exc
        if not isinstance(raw_rule, Mapping):
            raise EvalFixtureValidationError(
                claim_id=raw_claim_id,
                reason="claim expectation must be a mapping",
            )
        envelopes = [
            _compile_span(source, item, claim_id=raw_claim_id)
            for item in raw_rule.get("allowed_envelopes", [])
        ]
        if not envelopes:
            raise EvalFixtureValidationError(
                claim_id=raw_claim_id,
                reason="at least one allowed_envelope is required",
            )
        required_all = [
            _compile_span(source, item, claim_id=raw_claim_id)
            for item in raw_rule.get("required_all", [])
        ]
        raw_groups = raw_rule.get("required_any_groups", [])
        if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
            raise EvalFixtureValidationError(
                claim_id=raw_claim_id,
                reason="required_any_groups must be a list of non-empty lists",
            )
        required_any_groups: list[list[ValidatedSourceSpan]] = []
        for raw_group in raw_groups:
            if (
                not isinstance(raw_group, Sequence)
                or isinstance(raw_group, (str, bytes))
                or not raw_group
            ):
                raise EvalFixtureValidationError(
                    claim_id=raw_claim_id,
                    reason="required_any_groups must contain non-empty lists",
                )
            required_any_groups.append(
                [_compile_span(source, item, claim_id=raw_claim_id) for item in raw_group]
            )
        preferred = [
            _compile_span(source, item, claim_id=raw_claim_id)
            for item in raw_rule.get("preferred_spans", [])
        ]
        grouped_fragments = [fragment for group in required_any_groups for fragment in group]
        for fragment in [*required_all, *preferred, *grouped_fragments]:
            if not any(_inside(fragment, envelope) for envelope in envelopes):
                raise EvalFixtureValidationError(
                    claim_id=raw_claim_id,
                    quote=fragment.text,
                    reason="fixture fragment is outside every allowed envelope",
                )
        compiled.append(
            CompiledEvidenceExpectation(
                claim_id=claim_id,
                allowed_envelopes=envelopes,
                required_all=required_all,
                required_any_groups=required_any_groups,
                preferred_spans=preferred,
            )
        )
    return compiled


def _covered(fragment: ValidatedSourceSpan, spans: Sequence[ValidatedSourceSpan]) -> bool:
    """Return whether the union of exact candidate intervals covers a fragment."""

    cursor = fragment.start
    for span in sorted(spans, key=lambda item: item.start):
        if span.end <= cursor or span.start > cursor:
            continue
        cursor = max(cursor, span.end)
        if cursor >= fragment.end:
            return True
    return False


def evaluate_evidence_support(
    source: str,
    evidence: Sequence[GroundedTemporalEvidence],
    expectations: Sequence[CompiledEvidenceExpectation],
) -> EvidenceEvaluationResult:
    """Score grounded candidate spans against claim-specific deterministic rules."""

    failures: list[EvidenceSupportFailure] = []
    grounding_valid = True
    for item in evidence:
        try:
            validate_source_span(source, item.span, claim_id=",".join(item.claim_ids))
        except TemporalEvidenceValidationError as exc:
            grounding_valid = False
            failures.append(
                EvidenceSupportFailure(
                    code=exc.code.value,
                    claim_id=exc.claim_id,
                    quote=exc.quote,
                    detail=exc.reason,
                )
            )

    expected_claims = {expectation.claim_id for expectation in expectations}
    actual_claims = {claim for item in evidence for claim in item.claim_ids}
    unsupported = sorted(claim.value for claim in actual_claims - expected_claims)
    for claim_id in unsupported:
        failures.append(
            EvidenceSupportFailure(
                code="unsupported_semantic_claim",
                claim_id=claim_id,
                detail="the output linked evidence to a claim absent from this fixture",
            )
        )

    missing: list[str] = []
    overbroad: list[str] = []
    insufficient: list[str] = []
    preferred_match = True

    for expectation in expectations:
        candidates = [item for item in evidence if expectation.claim_id in item.claim_ids]
        if not candidates:
            missing.append(expectation.claim_id.value)
            failures.append(
                EvidenceSupportFailure(
                    code="evidence_not_linked_to_claim",
                    claim_id=expectation.claim_id.value,
                    detail="no grounded evidence span is linked to the expected claim",
                )
            )
            preferred_match = False
            continue
        spans = [item.span for item in candidates]
        common_envelopes = [
            envelope
            for envelope in expectation.allowed_envelopes
            if all(_inside(span, envelope) for span in spans)
        ]
        if not common_envelopes:
            quotes = [span.text for span in spans]
            overbroad.extend(quotes)
            failures.append(
                EvidenceSupportFailure(
                    code="outside_allowed_envelope",
                    claim_id=expectation.claim_id.value,
                    quote=" | ".join(quotes),
                    detail="claim spans do not share one allowed source envelope",
                )
            )
        for fragment in expectation.required_all:
            if not _covered(fragment, spans):
                insufficient.append(fragment.text)
                failures.append(
                    EvidenceSupportFailure(
                        code="missing_required_fragment",
                        claim_id=expectation.claim_id.value,
                        quote=fragment.text,
                        detail="candidate span union does not cover the required fragment",
                    )
                )
        for group in expectation.required_any_groups:
            if not any(_covered(fragment, spans) for fragment in group):
                group_text = " | ".join(fragment.text for fragment in group)
                insufficient.append(group_text)
                failures.append(
                    EvidenceSupportFailure(
                        code="missing_required_any_group",
                        claim_id=expectation.claim_id.value,
                        quote=group_text,
                        detail="candidate span union covers no member of the required-any group",
                    )
                )
        if expectation.preferred_spans and not any(
            candidate.start == preferred.start and candidate.end == preferred.end
            for candidate in spans
            for preferred in expectation.preferred_spans
        ):
            preferred_match = False

    support_valid = grounding_valid and not failures
    return EvidenceEvaluationResult(
        grounding_valid=grounding_valid,
        evidence_support_valid=support_valid,
        preferred_boundary_exact_match=preferred_match,
        missing_expected_claims=missing,
        unsupported_claims=unsupported,
        overbroad_spans=overbroad,
        insufficient_spans=insufficient,
        failures=failures,
    )
