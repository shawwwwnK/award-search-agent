"""C05 source-owned selected-journey temporal facts and replay isolation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from award_agent.results.category import (
    _PROFILE_INSTRUCTIONS,
    _focus,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
)
from award_agent.results.structured_contracts import StructuredSelection

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((ROOT / case / "artifact.json").read_bytes())


def test_c05_q011_equal_arrival_and_opposite_departure_duration_directions() -> None:
    saved = _saved("c04-scout-prior-conditional")
    selection = saved.passes[0].selection
    assert selection is not None and len(selection.journey_ids) == 2
    focus = _focus(selection, saved.selector_prepared, saved.evidence.source,
                   saved.evidence, profile="category-c05")
    packet = _writer_input(focus, profile="category-c05")
    records = cast(dict[str, dict[str, Any]], packet["authoring_records"])
    journeys = {alias: record for alias, record in records.items()
                if record["role"] == "journey"}
    assert len(journeys) == 2
    facts = cast(list[dict[str, str]], packet["selected_temporal_relations"])
    assert {item["metric"] for item in facts} == {"departure", "arrival", "elapsed"}
    assert all({item["first_alias"], item["second_alias"]} == set(journeys)
               for item in facts)
    by_metric = {item["metric"]: item for item in facts}
    assert by_metric["arrival"]["relation"] == "equal"
    assert by_metric["arrival"]["difference_minutes"] == "0"
    assert by_metric["departure"]["difference_minutes"] == "187"
    assert by_metric["elapsed"]["difference_minutes"] == "187"
    business = next(alias for alias, record in journeys.items()
                    if record["facts"]["award_cabin"] == "business")
    economy = next(alias for alias, record in journeys.items()
                   if record["facts"]["award_cabin"] == "economy")
    assert by_metric["departure"]["relation"] == (
        "first_earlier" if by_metric["departure"]["first_alias"] == business
        else "second_earlier")
    assert by_metric["elapsed"]["relation"] == (
        "first_shorter" if by_metric["elapsed"]["first_alias"] == economy
        else "second_shorter")


def test_c05_one_or_no_journey_has_no_temporal_pair() -> None:
    complete = _saved("c04-scout-prior-conditional")
    selection = complete.passes[0].selection
    assert selection is not None
    one = _focus(StructuredSelection(journey_ids=selection.journey_ids[:1]),
                 complete.selector_prepared, complete.evidence.source,
                 complete.evidence, profile="category-c05")
    assert _writer_input(one, profile="category-c05")["selected_temporal_relations"] == []
    incomplete = _saved("c04-scout-prior-incomplete")
    lead_selection = incomplete.passes[0].selection
    assert lead_selection is not None and not lead_selection.journey_ids
    none = _focus(lead_selection, incomplete.selector_prepared,
                  incomplete.evidence.source, incomplete.evidence,
                  profile="category-c05")
    assert _writer_input(none, profile="category-c05")["selected_temporal_relations"] == []


def test_c05_guide_distinguishes_ranking_membership_from_pair_relation() -> None:
    guide = _PROFILE_INSTRUCTIONS["category-c05"][1]
    assert "membership alone does not mean it arrives before" in guide
    assert "preserve equal arrivals as equal" in guide
    assert "if one journey offers both earlier arrival and a premium cabin" not in guide


def test_saved_c04_artifact_replays_without_c05_packet() -> None:
    saved = _saved("c04-scout-prior-conditional")
    assert "selected_temporal_relations" not in saved.focus_prepared.packet
    assert replay_category_results(saved) == saved.resolved
