"""Additional source-state and real-repair controls for category Results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from test_ranking_m2 import _snapshot, _synthetic_match
from test_results_category import CategoryWriter, _config, _source

from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankingStylePolicy
from award_agent.ranking.styles import assign_journey_styles
from award_agent.results.category import (
    _focus,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig
from award_agent.results.focused import prepare_focused_selector
from award_agent.results.presentation import resolve_workspace
from award_agent.results.structured_contracts import StructuredSelection


def _selected_record(projection: SolutionProjection, candidate_id: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = resolve_workspace(projection)
    selector = prepare_focused_selector(projection, _config(), evidence,
                                        selection_format="roles-v20")
    focus = _focus(StructuredSelection(journey_ids=(candidate_id,)),
                   selector, projection, evidence)
    packet = _writer_input(focus)
    records = cast(dict[str, dict[str, Any]], packet["authoring_records"])
    alias = next(alias for alias, record in records.items()
                 if record["role"] == "journey")
    return records[alias], cast(dict[str, Any], packet["category_landscape"]), alias


def test_synthetic_cost_states_keep_possible_distinct_from_definite() -> None:
    """Real Ranking assignment flows into the author packet without invented cost status."""
    baseline = assign_journey_styles(_synthetic_match(),
                                      policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    definite = baseline.indexes.cost[0]
    source = project_solutions(baseline)
    record, landscape, alias = _selected_record(source, definite)
    assert record["facts"]["styles"]["cost"] == "member"
    assert alias in landscape["selected_members"]["cost"]
    assert landscape["available_counts"]["cost"] > 0

    premium_target = next(feature for feature in baseline.features
                          if feature.candidate_id in baseline.indexes.premium
                          and feature.candidate_id not in baseline.indexes.time
                          and feature.cash_observation_id is not None
                          and feature.award_cabin.value == "business")
    modified = assign_journey_styles(
        _synthetic_match(missing_cash_id=premium_target.cash_observation_id),
        policy=RankingStylePolicy(), fx_snapshot=_snapshot())
    possible = modified.indexes.possible_cost[0]
    record, landscape, alias = _selected_record(project_solutions(modified), possible)
    assert record["facts"]["styles"]["cost"] == "possible"
    assert alias not in landscape["selected_members"]["cost"]
    assert landscape["possible_cost_count"] > 0

    undetermined = next(journey.candidate_id for journey in _source().view.alternatives
                        if journey.candidate_id in _source().view.comparison_pool_ids)
    record, landscape, alias = _selected_record(_source(), undetermined)
    assert record["facts"]["styles"]["cost"] == "undetermined"
    assert alias not in landscape["selected_members"]["cost"]
    assert landscape["available_counts"]["cost"] == 0


def test_real_overlap_has_one_exact_writer_identity() -> None:
    saved = json.loads(Path(
        "evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q120/evidence.json"
    ).read_text())
    source = SolutionProjection.model_validate(saved["source"])
    overlapping = next(candidate for candidate in source.view.indexes.time
                       if candidate in source.view.indexes.premium)
    record, landscape, alias = _selected_record(source, overlapping)
    assert record["facts"]["styles"]["time"] == "member"
    assert record["facts"]["styles"]["premium"] == "member"
    assert landscape["selected_members"]["time"] == [alias]
    assert landscape["selected_members"]["premium"] == [alias]


def test_successful_bounded_correction_replaces_failed_draft() -> None:
    class RepairWriter(CategoryWriter):
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            self.duplicate = len(self.requests) == 1
            return super().author(request, config, settings)

    artifact = run_category_results(_source(), _config(), RepairWriter())
    assert len(artifact.passes) == 3
    assert artifact.passes[1].outcome == "recoverable"
    assert "duplicate_journey_card" in {row.code for row in artifact.passes[1].findings}
    assert artifact.passes[2].outcome == "recoverable"
    assert not any(row.outcome == "failed" for row in artifact.passes[2].findings)
    assert artifact.selected_pass_index == 2
    assert artifact.validation_outcome == "clean"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
