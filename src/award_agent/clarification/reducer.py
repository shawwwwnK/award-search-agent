"""Deterministic reduction of accepted clarification amendments."""

from __future__ import annotations

from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    BlockingRequirement,
    DateWindow,
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    LocationAmendment,
    TemporalAmendment,
    TemporalContribution,
    TemporalContributionKind,
    TravelersAmendment,
    TypedAmendment,
    UnknownField,
)


def _replace_provenance(
    entries: tuple[FieldProvenance, ...],
    field: EffectiveField,
    amendment: TypedAmendment,
) -> tuple[FieldProvenance, ...]:
    replacement = FieldProvenance(
        field=field,
        source=AnswerMessageSource(span=amendment.span),
        amendment_id=amendment.amendment_id,
    )
    return tuple(entry for entry in entries if entry.field is not field) + (replacement,)


def _latest_window(
    contributions: tuple[TemporalContribution, ...],
    kind: TemporalContributionKind,
) -> DateWindow | None:
    for contribution in reversed(contributions):
        if contribution.kind is kind:
            return contribution.date_window
    return None


def _remove_unknowns(
    unknowns: tuple[UnknownField, ...],
    fields: set[str],
) -> tuple[UnknownField, ...]:
    return tuple(unknown for unknown in unknowns if unknown.field not in fields)


def apply_amendments(
    effective: EffectiveRequest,
    amendments: tuple[TypedAmendment, ...],
    *,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    compiled_temporal_contributions: dict[str, tuple[TemporalContribution, ...]] | None = None,
) -> EffectiveRequest:
    """Apply an independently validated amendment set as one new projection.

    This function is pure: caller-held effective state is never altered.  The
    controller decides which user-level failures become rejected fragments;
    exceptions here are reducer failures and leave a session revision
    uncommitted.  ``answer_text`` and ``requirements`` remain temporarily in
    the signature for caller compatibility.  They are deliberately not read:
    raw-answer semantics belong only to the receiver under ADR 0014.
    """

    travelers = effective.travelers
    origins = effective.origins
    destinations = effective.destinations
    contributions = effective.temporal_contributions
    provenance = effective.field_provenance
    resolved_fields: set[str] = set()

    for amendment in amendments:
        if isinstance(amendment, LocationAmendment):
            field = (
                EffectiveField.ORIGIN
                if amendment.target is AmendmentTarget.ORIGIN
                else EffectiveField.DESTINATION
            )
            if field is EffectiveField.ORIGIN:
                origins = amendment.locations
                resolved_fields.add("origin")
            else:
                destinations = amendment.locations
                resolved_fields.add("destination")
            provenance = _replace_provenance(provenance, field, amendment)
            continue
        if isinstance(amendment, TravelersAmendment):
            travelers = amendment.travelers
            resolved_fields.add("travelers")
            provenance = _replace_provenance(provenance, EffectiveField.TRAVELERS, amendment)
            continue

        assert isinstance(amendment, TemporalAmendment)
        contributions_to_apply = (compiled_temporal_contributions or {}).get(
            amendment.amendment_id
        )
        if contributions_to_apply is None:
            raise ValueError(
                "temporal amendments require receiver-approved compiled semantic contributions"
            )
        for contribution in contributions_to_apply:
            contributions = tuple(
                existing for existing in contributions if existing.kind is not contribution.kind
            ) + (contribution,)
            if contribution.kind is TemporalContributionKind.DEPARTURE_WINDOW:
                provenance = _replace_provenance(provenance, EffectiveField.DEPARTURE, amendment)
                resolved_fields.add("departure")
            else:
                raise ValueError("one-way clarification accepts only departure contributions")

    departure = _latest_window(contributions, TemporalContributionKind.DEPARTURE_WINDOW)

    return EffectiveRequest(
        raw_text=effective.raw_text,
        context=effective.context,
        travelers=travelers,
        origins=origins,
        destinations=destinations,
        departure_window=departure,
        cabins=effective.cabins,
        search_modes=effective.search_modes,
        repositioning_allowed=effective.repositioning_allowed,
        hard_constraints=effective.hard_constraints,
        unknowns=_remove_unknowns(effective.unknowns, resolved_fields),
        conflicts=effective.conflicts,
        field_provenance=provenance,
        temporal_contributions=contributions,
    )


__all__ = ["apply_amendments"]
