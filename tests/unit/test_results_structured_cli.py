"""Structured CLI uses the same exact facts as the replayable workspace API."""

from __future__ import annotations

import json
from pathlib import Path

from award_agent.cli import results
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import ResultsConfig


def test_structured_measure_is_offline_and_keeps_every_option(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    config.write_text(ResultsConfig(model="offline-test", max_output_tokens=2000,
        timeout_seconds=20, context_limit_tokens=10_000_000,
        prompt_overhead_tokens=200).model_dump_json())
    output = tmp_path / "measurement.json"
    assert results.main(["measure", "--structured", "--projection",
        "evidence/ranking-stage/m2/solutions/exact_business.json", "--config", str(config),
        "--output", str(output)]) == 0
    measurement = json.loads(output.read_bytes())
    assert measurement["prepared_version"] == "results-prepared-v5"
    assert measurement["eligible_alternatives"] == 106
    assert measurement["input_bytes"] > 0
    assert measurement["token_measurement"] == "conservative_utf8_upper_bound"


def test_incomplete_structured_author_and_replay_preserve_lead_facts(tmp_path: Path) -> None:
    from award_agent.results.structured import prepare_structured_results

    source = json.loads(Path(
        "evidence/results-stage/m2/compact-input/2026-10-20-luna/incomplete/artifact.json"
    ).read_bytes())["projection"]
    projection = SolutionProjection.model_validate(source)
    settings = ResultsConfig(model="offline-test", max_output_tokens=2000,
        timeout_seconds=20, context_limit_tokens=10_000_000, prompt_overhead_tokens=200)
    prepared = prepare_structured_results(projection, settings)
    alias, observation_id = next(iter(prepared.references.awards.items()))
    projection_path, config, draft, output = (
        tmp_path / name for name in ("projection.json", "config.json", "draft.json", "artifact.json"))
    projection_path.write_text(json.dumps(source))
    config.write_text(settings.model_dump_json())
    draft.write_text(json.dumps({"selection": {"incomplete_observation_ids": [alias]}, "blocks": [
        {"kind": "narrative", "text": "No complete journey was found."},
        {"kind": "reference", "reference_kind": "lead", "reference_id": alias,
         "label": "Potential lead", "text": "This needs full itinerary details."}]}))
    assert results.main(["author", "--structured", "--projection", str(projection_path),
        "--config", str(config), "--draft", str(draft), "--output", str(output)]) == 0
    artifact = json.loads(output.read_bytes())
    assert artifact["evidence"]["journeys"] == []
    resolved = artifact["resolved"]
    assert resolved["selected_journey_ids"] == []
    assert resolved["blocks"][1]["canonical_id"] == observation_id
    assert resolved["blocks"][1]["unavailable"] is False
    assert resolved["blocks"][1]["lead"]["missing_information"]
    assert resolved["blocks"][1]["component"]["observation_id"] == observation_id
    replayed = tmp_path / "resolved.json"
    assert results.main(["replay", "--artifact", str(output), "--output", str(replayed)]) == 0
    assert json.loads(replayed.read_bytes()) == resolved
