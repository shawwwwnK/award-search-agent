"""Deterministic source-backed temporal comparisons for selected journeys."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from typing import Literal

from .focused_comparison_contracts import (
    TemporalComparisonFact,
    TemporalComparisonRegistry,
    TemporalComparisonSource,
)
from .workspace_contracts import JourneyView, LocalFlightTime, WorkspaceEvidence

TemporalMetric = Literal["departure", "arrival", "elapsed"]
TemporalRelation = Literal[
    "first_earlier", "second_earlier", "first_shorter", "second_shorter", "equal",
]
_METRICS: tuple[TemporalMetric, ...] = ("departure", "arrival", "elapsed")


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(UTC)


def _source(journey: JourneyView, metric: TemporalMetric) -> TemporalComparisonSource:
    local_time: LocalFlightTime | None = (
        journey.departure if metric == "departure" else
        journey.arrival if metric == "arrival" else None
    )
    return TemporalComparisonSource(
        origin=journey.origin,
        destination=journey.destination,
        departure_local_iso=journey.departure.local_iso,
        arrival_local_iso=journey.arrival.local_iso,
        local_iso=local_time.local_iso if local_time is not None else None,
        instant=local_time.instant if local_time is not None else None,
        timezone=local_time.timezone if local_time is not None else None,
        day_change=local_time.day_change if local_time is not None else None,
        elapsed_minutes=journey.elapsed_minutes if metric == "elapsed" else None,
    )


def _comparison(
    first: JourneyView, second: JourneyView, metric: TemporalMetric,
) -> tuple[TemporalRelation, Decimal] | None:
    """Return relation and absolute minute delta only for like-scope values."""
    if metric == "departure":
        if first.origin != second.origin:
            return None
        left = _aware(first.departure.instant)
        right = _aware(second.departure.instant)
        relation_early: tuple[TemporalRelation, TemporalRelation] = (
            "first_earlier", "second_earlier",
        )
    elif metric == "arrival":
        if first.destination != second.destination:
            return None
        left = _aware(first.arrival.instant)
        right = _aware(second.arrival.instant)
        relation_early = ("first_earlier", "second_earlier")
    else:
        if first.origin != second.origin or first.destination != second.destination:
            return None
        left_elapsed = first.elapsed_minutes
        right_elapsed = second.elapsed_minutes
        if (left_elapsed is None or right_elapsed is None or
                not left_elapsed.is_finite() or not right_elapsed.is_finite()):
            return None
        if left_elapsed == right_elapsed:
            return "equal", Decimal(0)
        return (("first_shorter" if left_elapsed < right_elapsed else "second_shorter"),
                abs(left_elapsed - right_elapsed))

    if left is None or right is None:
        return None
    if left == right:
        return "equal", Decimal(0)
    delta = abs(left - right)
    microseconds = ((delta.days * 86400 + delta.seconds) * 1_000_000 +
                    delta.microseconds)
    minutes = Decimal(microseconds) / Decimal(60_000_000)
    return (relation_early[0] if left < right else relation_early[1]), minutes


def build_temporal_registry(
    evidence: WorkspaceEvidence,
    journey_ids: tuple[str, ...],
    source_aliases: dict[str, str],
) -> TemporalComparisonRegistry:
    """Build stable Txx facts from eligible canonical workspace journeys.

    ``source_aliases`` maps each selected composer J alias to one canonical
    journey ID. Comparisons are omitted when a temporal value is unknown or
    the relevant airport scope differs.
    """
    if len(set(journey_ids)) != len(journey_ids):
        raise ValueError("selected journey IDs must be unique")
    aliases = dict(source_aliases)
    if (any(not isinstance(alias, str) or not alias for alias in aliases) or
            len(set(aliases.values())) != len(aliases) or
            set(aliases.values()) != set(journey_ids)):
        raise ValueError("source aliases must map one-to-one to selected journey IDs")

    eligible = {
        alternative.candidate_id
        for alternative in evidence.source.view.alternatives
        if alternative.status in {"admitted", "conditional"}
    }
    by_id = {journey.candidate_id: journey for journey in evidence.journeys}
    for journey_id in journey_ids:
        if journey_id not in eligible or journey_id not in by_id:
            raise ValueError("selected journey ID is not an eligible canonical workspace journey")

    alias_by_id = {journey_id: alias for alias, journey_id in aliases.items()}
    selected = sorted(journey_ids)
    facts: list[TemporalComparisonFact] = []
    for first_id, second_id in combinations(selected, 2):
        first, second = by_id[first_id], by_id[second_id]
        for metric in _METRICS:
            compared = _comparison(first, second, metric)
            if compared is None:
                continue
            relation, difference = compared
            comparison_id = f"T{len(facts) + 1:02d}"
            facts.append(TemporalComparisonFact(
                comparison_id=comparison_id,
                metric=metric,
                first_journey_id=first_id,
                second_journey_id=second_id,
                first_alias=alias_by_id[first_id],
                second_alias=alias_by_id[second_id],
                first_source=_source(first, metric),
                second_source=_source(second, metric),
                difference_minutes=difference,
                relation=relation,
                source_digest=evidence.source_binding.view_digest,
            ))
    return TemporalComparisonRegistry(
        evidence_contract_version=evidence.contract_version,
        source_digest=evidence.source_binding.view_digest,
        facts=tuple(facts),
    )


def validate_temporal_registry(
    registry: TemporalComparisonRegistry,
    evidence: WorkspaceEvidence,
    journey_ids: tuple[str, ...],
    source_aliases: dict[str, str],
) -> None:
    """Reject stale or edited registries by recomputing from canonical evidence."""
    expected = build_temporal_registry(evidence, journey_ids, source_aliases)
    if registry != expected:
        raise ValueError("temporal comparison registry differs from canonical workspace evidence")
