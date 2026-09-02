"""Deterministic conflict detection for parsed requests."""

from datetime import timedelta

from award_agent.domain import (
    Conflict,
    DateWindow,
    GroundedTemporalEvidence,
    InterpretedDuration,
    TemporalEvidenceClaim,
)

_EVIDENCE_CLAIMS_BY_FIELD = {
    "departure": {
        TemporalEvidenceClaim.DEPARTURE_ANCHOR,
        TemporalEvidenceClaim.DEPARTURE_PERIOD,
        TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY,
    },
    "return_date": {
        TemporalEvidenceClaim.RETURN_ANCHOR,
        TemporalEvidenceClaim.RETURN_PERIOD,
        TemporalEvidenceClaim.ALTERNATE_RETURN_DAY,
    },
    "duration": {
        TemporalEvidenceClaim.DURATION,
        TemporalEvidenceClaim.APPROXIMATE_DURATION,
    },
}


def _evidence_by_alternative(
    fields: list[str],
    evidence: list[GroundedTemporalEvidence],
) -> dict[str, list[GroundedTemporalEvidence]]:
    return {
        field: [
            item
            for item in evidence
            if set(item.claim_ids) & _EVIDENCE_CLAIMS_BY_FIELD.get(field, set())
        ]
        for field in fields
    }


def detect_conflicts(
    departure: DateWindow | None,
    return_window: DateWindow | None,
    duration: InterpretedDuration | None,
    evidence: list[GroundedTemporalEvidence] | None = None,
) -> list[Conflict]:
    grounded_evidence = evidence or []
    conflicts: list[Conflict] = []
    if departure is not None and return_window is not None:
        if return_window.end < departure.start:
            conflicts.append(
                Conflict(
                    code="return_before_departure",
                    fields=["departure", "return_date"],
                    detail="The return-date constraint ends before the departure window begins.",
                    evidence_by_alternative=_evidence_by_alternative(
                        ["departure", "return_date"], grounded_evidence
                    ),
                )
            )
        if duration is not None:
            derived_start = departure.start + timedelta(days=duration.minimum_days)
            derived_end = departure.end + timedelta(days=duration.maximum_days)
            if return_window.end < derived_start or return_window.start > derived_end:
                conflicts.append(
                    Conflict(
                        code="duration_date_mismatch",
                        fields=["departure", "return_date", "duration"],
                        detail=(
                            "The explicit return window does not overlap the return window "
                            "implied by the stated duration."
                        ),
                        evidence_by_alternative=_evidence_by_alternative(
                            ["departure", "return_date", "duration"], grounded_evidence
                        ),
                    )
                )
    return conflicts
