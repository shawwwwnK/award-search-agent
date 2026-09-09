"""Deterministic reduction of accepted clarification amendments."""

from __future__ import annotations

from datetime import timedelta

from award_agent.clarification.temporal import normalize_temporal_amendment
from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    BlockingRequirement,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    InterpretedDuration,
    LocationAmendment,
    TemporalAmendment,
    TemporalContribution,
    TemporalContributionKind,
    TravelersAmendment,
    TypedAmendment,
    UnknownField,
)
from award_agent.intent.conflicts import detect_conflicts


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


def _derived_return(
    departure: DateWindow | None,
    duration: InterpretedDuration | None,
) -> DateWindow | None:
    if departure is None or duration is None:
        return None
    return DateWindow(
        start=departure.start + timedelta(days=duration.minimum_days),
        end=departure.end + timedelta(days=duration.maximum_days),
        precision=DateWindowPrecision.DERIVED,
        raw_text=duration.raw_text,
    )


def _latest_window(
    contributions: tuple[TemporalContribution, ...],
    kind: TemporalContributionKind,
) -> DateWindow | None:
    for contribution in reversed(contributions):
        if contribution.kind is kind:
            return contribution.date_window
    return None


def _latest_duration(
    contributions: tuple[TemporalContribution, ...],
) -> InterpretedDuration | None:
    for contribution in reversed(contributions):
        if contribution.kind is TemporalContributionKind.DURATION:
            return contribution.interpreted_duration
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
) -> EffectiveRequest:
    """Apply an independently validated amendment set as one new projection.

    This function is pure: caller-held effective state is never altered.  The
    controller decides which user-level failures become rejected fragments;
    exceptions here are reducer/normalization failures and leave a session
    revision uncommitted.
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
        normalization = normalize_temporal_amendment(
            amendment,
            answer_text=answer_text,
            requirements=requirements,
            context=effective.context,
        )
        for contribution in normalization.contributions:
            contributions = tuple(
                existing for existing in contributions if existing.kind is not contribution.kind
            ) + (contribution,)
            if contribution.kind is TemporalContributionKind.DEPARTURE_WINDOW:
                provenance = _replace_provenance(provenance, EffectiveField.DEPARTURE, amendment)
                resolved_fields.add("departure")
            else:
                provenance = _replace_provenance(
                    provenance, EffectiveField.RETURN_OR_DURATION, amendment
                )
                resolved_fields.add("return_or_duration")

    departure = _latest_window(contributions, TemporalContributionKind.DEPARTURE_WINDOW)
    explicit_return = _latest_window(contributions, TemporalContributionKind.RETURN_WINDOW)
    duration = _latest_duration(contributions)
    return_window = explicit_return or _derived_return(departure, duration)
    conflicts = tuple(detect_conflicts(departure, return_window, duration))

    return EffectiveRequest(
        raw_text=effective.raw_text,
        context=effective.context,
        travelers=travelers,
        origins=origins,
        destinations=destinations,
        departure_window=departure,
        return_window=return_window,
        interpreted_duration=duration,
        cabins=effective.cabins,
        search_modes=effective.search_modes,
        repositioning_allowed=effective.repositioning_allowed,
        hard_constraints=effective.hard_constraints,
        unknowns=_remove_unknowns(effective.unknowns, resolved_fields),
        conflicts=conflicts,
        field_provenance=provenance,
        temporal_contributions=contributions,
    )


__all__ = ["apply_amendments"]
