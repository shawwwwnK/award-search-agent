"""Pure initial-snapshot projection for ADR 0011 continuation sessions."""

from __future__ import annotations

from award_agent.domain import ParsedRequest
from award_agent.domain.clarification_session import (
    EffectiveField,
    EffectiveRequest,
    EffectiveValueSource,
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
    # The frozen projection exposes a duration-derived return window in the
    # same field as an explicit return.  Keep only explicit windows as active
    # return contributions: a derived window must be rebuilt when departure or
    # duration changes in a later answer.
    return_is_duration_derived = bool(
        copied.date_resolution
        and copied.date_resolution.return_date
        and "derived" in copied.date_resolution.return_date.interpretation.casefold()
    )
    if copied.return_window is not None and not return_is_duration_derived:
        return_source = record(EffectiveField.RETURN_OR_DURATION)
        temporal_contributions.append(
            TemporalContribution(
                contribution_id="initial:return_window",
                kind=TemporalContributionKind.RETURN_WINDOW,
                source=return_source,
                raw_text=copied.return_window.raw_text,
                date_window=copied.return_window,
            )
        )
    interpreted_duration = (
        copied.date_resolution.interpreted_duration if copied.date_resolution is not None else None
    )
    if interpreted_duration is not None:
        # A resolved return and a duration can coexist in the frozen snapshot;
        # one effective field still has one provenance record.
        duration_source: EffectiveValueSource | None = next(
            (
                item.source
                for item in provenance
                if item.field is EffectiveField.RETURN_OR_DURATION
            ),
            None,
        )
        if duration_source is None:
            duration_source = record(EffectiveField.RETURN_OR_DURATION)
        temporal_contributions.append(
            TemporalContribution(
                contribution_id="initial:duration",
                kind=TemporalContributionKind.DURATION,
                source=duration_source,
                raw_text=interpreted_duration.raw_text,
                interpreted_duration=interpreted_duration,
            )
        )

    return EffectiveRequest(
        raw_text=copied.raw_text,
        context=copied.context,
        travelers=copied.travelers,
        origins=tuple(copied.origins),
        destinations=tuple(copied.destinations),
        departure_window=copied.departure_window,
        return_window=copied.return_window,
        interpreted_duration=interpreted_duration,
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
