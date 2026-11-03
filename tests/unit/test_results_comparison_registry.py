"""Canonical source binding and arithmetic for V11 temporal references."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from award_agent.results.comparison_registry import (
    build_temporal_registry,
    validate_temporal_registry,
)
from award_agent.results.focused_comparison_contracts import TemporalComparisonRegistry
from award_agent.results.workspace_contracts import LocalFlightTime, WorkspaceEvidence

EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q018/evidence.json"
)
FIRST = "28b5a832f590e31794a56935985a19ac2add1203a766c16aa9bb5edbcf8a1a82"
SECOND = "cc11925bdbf1b454bd01da92f122569d8f1caab2a21cc915493675159f29111a"
ALIASES = {"J1": FIRST, "J2": SECOND}


@pytest.fixture
def evidence() -> WorkspaceEvidence:
    return WorkspaceEvidence.model_validate_json(EVIDENCE_PATH.read_bytes())


def _journeys(evidence: WorkspaceEvidence):
    return {item.candidate_id: item for item in evidence.journeys}


def _registry(evidence: WorkspaceEvidence, ids: tuple[str, ...] = (FIRST, SECOND),
              aliases: dict[str, str] = ALIASES) -> TemporalComparisonRegistry:
    return build_temporal_registry(evidence, ids, aliases)


def test_q018_comparison_catches_arrival_elapsed_mixup_and_binds_sources(
    evidence: WorkspaceEvidence,
) -> None:
    registry = _registry(evidence)
    elapsed = next(item for item in registry.facts if item.metric == "elapsed")
    arrival = next(item for item in registry.facts if item.metric == "arrival")
    assert elapsed.difference_minutes == Decimal(40)
    assert elapsed.relation == "second_shorter"
    assert arrival.difference_minutes == Decimal(730)
    assert arrival.relation == "second_earlier"
    assert (elapsed.first_journey_id, elapsed.second_journey_id) == (FIRST, SECOND)
    assert elapsed.first_alias == "J1" and elapsed.second_alias == "J2"
    assert elapsed.first_source.elapsed_minutes == Decimal(1220)
    assert elapsed.second_source.elapsed_minutes == Decimal(1180)
    assert elapsed.first_source.departure_local_iso == "2027-01-15T23:15:00-08:00"
    assert elapsed.second_source.departure_local_iso == "2027-01-15T11:45:00-08:00"
    assert elapsed.first_source.arrival_local_iso == "2027-01-17T10:35:00+07:00"
    assert elapsed.second_source.arrival_local_iso == "2027-01-16T22:25:00+07:00"
    assert arrival.first_source.local_iso == "2027-01-17T10:35:00+07:00"
    assert arrival.second_source.local_iso == "2027-01-16T22:25:00+07:00"
    assert arrival.first_source.destination == arrival.second_source.destination == "BKK"
    assert registry.source_digest == evidence.source_binding.view_digest
    assert registry.evidence_contract_version == evidence.contract_version


def test_reversed_selection_order_keeps_sorted_ids_and_frozen_opaque_ids(
    evidence: WorkspaceEvidence,
) -> None:
    normal = _registry(evidence)
    reversed_registry = _registry(evidence, (SECOND, FIRST), {"J2": SECOND, "J1": FIRST})
    assert [(item.comparison_id, item.metric, item.first_journey_id,
             item.second_journey_id) for item in normal.facts] == [
        (item.comparison_id, item.metric, item.first_journey_id,
         item.second_journey_id) for item in reversed_registry.facts
    ]
    assert [item.comparison_id for item in normal.facts] == ["T01", "T02", "T03"]
    assert reversed_registry == normal


def test_instant_comparisons_use_offsets_and_preserve_subminute_deltas(
    evidence: WorkspaceEvidence,
) -> None:
    first, second = (_journeys(evidence)[FIRST], _journeys(evidence)[SECOND])
    # A 30-second difference represented with different offsets across a date boundary.
    first_departure = LocalFlightTime(
        instant=datetime.fromisoformat("2027-01-16T00:00:30+00:00"),
        local_iso="2027-01-15T16:00:30-08:00", timezone="America/Los_Angeles", day_change=0,
    )
    second_departure = LocalFlightTime(
        instant=datetime.fromisoformat("2027-01-15T19:00:00-05:00"),
        local_iso="2027-01-15T19:00:00-05:00", timezone="America/New_York", day_change=0,
    )
    edited_first = first.model_copy(update={"departure": first_departure})
    edited_second = second.model_copy(update={"departure": second_departure})
    altered = evidence.model_copy(update={
        "journeys": tuple(edited_first if item.candidate_id == FIRST else
                          edited_second if item.candidate_id == SECOND else item
                          for item in evidence.journeys)
    })
    departure = next(item for item in _registry(altered).facts if item.metric == "departure")
    assert departure.difference_minutes == Decimal("0.5")
    assert departure.relation == "second_earlier"
    assert departure.first_source.local_iso == "2027-01-15T16:00:30-08:00"
    assert departure.second_source.local_iso == "2027-01-15T19:00:00-05:00"

    equal_first = first.model_copy(update={"departure": first_departure.model_copy(update={
        "instant": datetime.fromisoformat("2027-01-16T00:00:00+00:00")
    })})
    equal = evidence.model_copy(update={
        "journeys": tuple(equal_first if item.candidate_id == FIRST else
                          second.model_copy(update={"departure": second_departure})
                          if item.candidate_id == SECOND else item
                          for item in evidence.journeys)
    })
    tie = next(item for item in _registry(equal).facts if item.metric == "departure")
    assert tie.relation == "equal" and tie.difference_minutes == Decimal(0)


def test_missing_naive_values_are_omitted_without_fabrication(evidence: WorkspaceEvidence) -> None:
    journeys = _journeys(evidence)
    first, second = journeys[FIRST], journeys[SECOND]
    missing = first.model_copy(update={"departure": first.departure.model_copy(update={
        "instant": None,
    })})
    naive = second.model_copy(update={"arrival": second.arrival.model_copy(update={
        "instant": datetime.fromisoformat("2027-01-16T22:25:00"),
    })})
    altered = evidence.model_copy(update={
        "journeys": tuple(missing if item.candidate_id == FIRST else
                          naive if item.candidate_id == SECOND else item
                          for item in evidence.journeys)
    })
    metrics = {item.metric for item in _registry(altered).facts}
    assert "departure" not in metrics and "arrival" not in metrics
    assert "elapsed" in metrics


@pytest.mark.parametrize(
    ("first_route", "second_route", "expected_metrics"),
    [
        (("SFO", "NRT"), ("SFO", "BKK"), {"departure"}),
        (("LAX", "BKK"), ("SFO", "BKK"), {"arrival"}),
        (("LAX", "NRT"), ("SFO", "BKK"), set()),
    ],
)
def test_only_matching_airport_scope_is_compared(
    evidence: WorkspaceEvidence,
    first_route: tuple[str, str],
    second_route: tuple[str, str],
    expected_metrics: set[str],
) -> None:
    journeys = _journeys(evidence)
    first = journeys[FIRST].model_copy(update={"origin": first_route[0],
                                               "destination": first_route[1]})
    second = journeys[SECOND].model_copy(update={"origin": second_route[0],
                                                 "destination": second_route[1]})
    altered = evidence.model_copy(update={
        "journeys": tuple(first if item.candidate_id == FIRST else
                          second if item.candidate_id == SECOND else item
                          for item in evidence.journeys)
    })
    assert {item.metric for item in _registry(altered).facts} == expected_metrics


def test_selected_identity_and_alias_membership_are_validated(evidence: WorkspaceEvidence) -> None:
    with pytest.raises(ValueError, match="eligible canonical"):
        build_temporal_registry(evidence, ("0" * 64,), {"J1": "0" * 64})
    with pytest.raises(ValueError, match="one-to-one"):
        build_temporal_registry(evidence, (FIRST, SECOND), {"J1": FIRST})
    with pytest.raises(ValueError, match="one-to-one"):
        build_temporal_registry(evidence, (FIRST, SECOND), {"J1": FIRST, "J2": FIRST})


def test_incomplete_only_selection_has_an_empty_registry(evidence: WorkspaceEvidence) -> None:
    registry = build_temporal_registry(evidence, (), {})
    assert registry.facts == ()
    assert registry.source_digest == evidence.source_binding.view_digest


@pytest.mark.parametrize("mutation", ["version", "digest", "source", "value", "delta"])
def test_replay_recomputes_registry_and_rejects_stale_or_edited_facts(
    evidence: WorkspaceEvidence, mutation: str,
) -> None:
    registry = _registry(evidence)
    if mutation == "version":
        edited = registry.model_copy(update={"evidence_contract_version": "results-workspace-evidence-v1"})
    elif mutation == "digest":
        edited = registry.model_copy(update={"source_digest": "0" * 64})
    else:
        first_fact = registry.facts[0]
        if mutation == "source":
            fact = first_fact.model_copy(update={"first_source": first_fact.second_source})
        elif mutation == "value":
            source = first_fact.first_source.model_copy(update={
                "instant": datetime.fromisoformat("2030-01-01T00:00:00+00:00")
            })
            fact = first_fact.model_copy(update={"first_source": source})
        else:
            fact = first_fact.model_copy(update={"difference_minutes": Decimal(999)})
        edited = registry.model_copy(update={"facts": (fact, *registry.facts[1:])})
    with pytest.raises(ValueError, match="differs from canonical"):
        validate_temporal_registry(edited, evidence, (FIRST, SECOND), ALIASES)


def test_unknown_canonical_source_digest_is_rejected(evidence: WorkspaceEvidence) -> None:
    registry = _registry(evidence)
    changed_evidence = evidence.model_copy(update={
        "source_binding": evidence.source_binding.model_copy(update={"view_digest": "0" * 64})
    })
    with pytest.raises(ValueError, match="differs from canonical"):
        validate_temporal_registry(registry, changed_evidence, (FIRST, SECOND), ALIASES)
