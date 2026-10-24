"""The Results workspace preserves exact source options independently of authoring."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.presentation import resolve_workspace, select_groups
from award_agent.results.workspace_contracts import (
    ComponentView,
    ComponentViewV1,
    WorkspaceEvidence,
)


@pytest.mark.parametrize(("case", "eligible"), [
    ("admitted", 258),
    ("conditional", 232),
    ("incomplete", 0),
])
def test_saved_projection_preserves_every_exact_eligible_variant(case: str, eligible: int) -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006") / case / "artifact.json"
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    expected = {alternative.candidate_id for alternative in projection.view.alternatives
                if alternative.status in {"admitted", "conditional"}}
    actual = {journey.candidate_id for journey in evidence.journeys}
    grouped = [member for group in evidence.groups for member in group.member_ids]
    assert len(actual) == eligible
    assert actual == expected
    assert set(grouped) == expected
    assert len(grouped) == len(expected)
    assert all(group.representative_id in group.member_ids for group in evidence.groups)
    assert evidence.source_binding.view_digest == projection.receipt.view_digest
    assert evidence.source_binding.fx_snapshot_digest == projection.receipt.fx_snapshot_digest
    assert evidence.source == projection
    selected = select_groups(evidence)
    assert {item.group_id for item in selected} == {group.group_id for group in evidence.groups}
    assert evidence.direct_cash_benchmark_ids == projection.view.direct_cash_observation_ids
    assert {lead.award_observation_id for lead in evidence.leads
            if lead.candidate_id is None and lead.award_observation_id is not None} == set(
        projection.view.unmatched_award_observation_ids
        + projection.view.award_summary_observation_ids
    )
    assert {lead.reference_id for lead in evidence.leads if lead.candidate_id is None} == {
        identifier for identifier in (
            projection.view.unmatched_award_observation_ids
            + projection.view.award_summary_observation_ids
            + projection.view.unpaired_positioning_observation_ids
        )
    }


def test_filter_chooses_a_surviving_exact_variant_without_combining_facts() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/admitted/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    group = next(group for group in evidence.groups if len(group.member_ids) > 1)
    other = next(member for member in group.member_ids
                 if member != group.representative_id)
    selected = select_groups(evidence, candidate_ids={other})
    assert len(selected) == 1
    assert selected[0].group_id == group.group_id
    assert selected[0].representative_id == other
    assert selected[0].representative == next(
        journey for journey in evidence.journeys if journey.candidate_id == other
    )
    assert group.representative_id != other


def test_unknown_filter_id_is_explicit_error() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/incomplete/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    with pytest.raises(ValueError, match="unavailable eligible journey"):
        select_groups(evidence, candidate_ids={"x" * 64})


def test_lowest_cash_uses_only_complete_observed_money_of_one_variant() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/admitted/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    group = next(group for group in evidence.groups if len(group.member_ids) > 1)
    first, second = group.member_ids[:2]
    journeys = tuple(item.model_copy(update={"money": item.money.model_copy(update={
        "observed_cash_per_traveler_usd": (
            Decimal(240) if item.candidate_id == first else
            Decimal(120) if item.candidate_id == second else None
        ),
    })}) for item in evidence.journeys)
    changed = evidence.model_copy(update={"journeys": journeys})
    selected = select_groups(changed, candidate_ids={first, second}, sort="lowest_cash")
    assert selected[0].representative_id == second
    assert selected[0].representative.money.observed_cash_per_traveler_usd == Decimal(120)


def test_points_sort_requires_program_scope() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/admitted/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    with pytest.raises(ValueError, match="program"):
        select_groups(evidence, sort="fewest_points")


def test_summary_lead_retains_known_date_when_flight_clock_is_unavailable() -> None:
    path = Path("evidence/end-to-end/presentation/iterations/006/incomplete/artifact.json")
    projection = SolutionProjection.model_validate(json.loads(path.read_text())["projection"])
    evidence = resolve_workspace(projection)
    source = {item.observation_id: item for item in projection.view.components}
    lead = next(item for item in evidence.leads
                if item.award_observation_id is not None
                and source[item.award_observation_id].departure_date is not None)
    component = next(item for item in evidence.components
                     if item.observation_id == lead.reference_id)
    assert evidence.contract_version == "results-workspace-evidence-v2"
    assert isinstance(component, ComponentView)
    assert component.departure_date == source[lead.reference_id].departure_date
    assert component.legs[0].departure.local_iso is None


@pytest.mark.parametrize("case", ("admitted", "conditional", "incomplete"))
def test_saved_round_one_v1_workspace_replays_with_original_component_shape(case: str) -> None:
    path = Path("evidence/results-stage/m2/structured/2026-10-24-luna/round-1") / case / "artifact.json"
    saved = json.loads(path.read_text())["evidence"]
    original = WorkspaceEvidence.model_validate(saved)
    assert original.contract_version == "results-workspace-evidence-v1"
    assert isinstance(original.components[0], ComponentViewV1)
    assert original.model_dump(mode="json") == saved
    replayed = resolve_workspace(original.source, version="v1",
                                 fx_acquisition=original.fx_acquisition)
    assert replayed.model_dump(mode="json") == saved
    with pytest.raises(ValueError, match="workspace v2 requires source departure dates"):
        WorkspaceEvidence.model_validate(saved | {
            "contract_version": "results-workspace-evidence-v2",
        })
    current = resolve_workspace(original.source)
    with pytest.raises(ValueError, match="workspace v1 requires the original component shape"):
        WorkspaceEvidence.model_validate(current.model_dump(mode="json") | {
            "contract_version": "results-workspace-evidence-v1",
        })
