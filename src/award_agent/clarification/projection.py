"""Pure initial-snapshot projection for ADR 0011 continuation sessions."""

from __future__ import annotations

from award_agent.domain import ParsedRequest
from award_agent.domain.clarification_session import (
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    InitialSnapshotSource,
    TemporalContribution,
    TemporalContributionKind,
)


def project_initial_request(parsed: ParsedRequest) -> EffectiveRequest:
    """Materialize an additive ``EffectiveRequest`` without changing ``parsed``.

    The projection deep-copies nested frozen-boundary data before validating the
    continuation value object.  Later reducer steps replace only explicitly
    amended effective fields and rebuild temporal contributions.
    """

    copied = parsed.model_copy(deep=True)
    provenance: list[FieldProvenance] = []

    def record(field: EffectiveField) -> InitialSnapshotSource:
        provenance.append(
            FieldProvenance(
                field=field,
                source=InitialSnapshotSource(field=field),
            )
        )
        return InitialSnapshotSource(field=field)

    temporal_contributions: list[TemporalContribution] = []
    if copied.travelers is not None:
        record(EffectiveField.TRAVELERS)
    if copied.origins:
        record(EffectiveField.ORIGIN)
    if copied.destinations:
        record(EffectiveField.DESTINATION)
    if copied.cabins:
        record(EffectiveField.CABIN)
    if copied.search_modes:
        record(EffectiveField.SEARCH_MODE)
    if copied.repositioning_allowed is not None:
        record(EffectiveField.REPOSITIONING)
    if copied.hard_constraints:
        record(EffectiveField.HARD_CONSTRAINTS)
    if copied.departure_window is not None:
        departure_source = record(EffectiveField.DEPARTURE)
        temporal_contributions.append(
            TemporalContribution(
                contribution_id="initial:departure_window",
                kind=TemporalContributionKind.DEPARTURE_WINDOW,
                source=departure_source,
                raw_text=copied.departure_window.raw_text,
                date_window=copied.departure_window,
            )
        )
    return EffectiveRequest(
        raw_text=copied.raw_text,
        context=copied.context,
        travelers=copied.travelers,
        origins=tuple(copied.origins),
        destinations=tuple(copied.destinations),
        departure_window=copied.departure_window,
        cabins=tuple(copied.cabins),
        search_modes=tuple(copied.search_modes),
        repositioning_allowed=copied.repositioning_allowed,
        hard_constraints=tuple(copied.hard_constraints),
        unknowns=tuple(copied.unknowns),
        conflicts=tuple(copied.conflicts),
        field_provenance=tuple(provenance),
        temporal_contributions=tuple(temporal_contributions),
    )


__all__ = ["project_initial_request"]
