"""Thin Results CLI contracts: offline output, replay and immutable evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from award_agent.cli import results
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import (
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
)

SOURCE = Path("evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json")


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    config = tmp_path / "config.json"
    config.write_text(ResultsConfig(model="offline-test", max_output_tokens=3000,
        timeout_seconds=20, context_limit_tokens=10000000,
        prompt_overhead_tokens=200).model_dump_json())
    draft = tmp_path / "draft.json"
    draft.write_text(ResultsDocument(selection=ResultsSelection(), parts=(
        ResultsPart(scope="shared", markdown="Observed award possibilities."),
    )).model_dump_json())
    return config, draft, tmp_path / "artifact.json"


def test_offline_author_and_exact_replay(tmp_path: Path) -> None:
    config, draft, output = _inputs(tmp_path)
    assert results.main(["author", "--projection", str(SOURCE), "--config", str(config),
                         "--draft", str(draft), "--output", str(output)]) == 0
    artifact = ResultsArtifact.model_validate_json(output.read_bytes())
    assert artifact.delivery_outcome == "delivered"
    assert artifact.validation_outcome == "annotated"
    assert len(artifact.attempts) == 2
    rendered = tmp_path / "answer.md"
    assert results.main(["replay", "--artifact", str(output), "--output", str(rendered)]) == 0
    assert rendered.read_bytes() == artifact.rendered_markdown.encode("utf-8")


def test_measure_records_complete_input_without_authoring(tmp_path: Path) -> None:
    config, _, output = _inputs(tmp_path)
    assert results.main(["measure", "--projection", str(SOURCE), "--config", str(config),
                         "--output", str(output)]) == 0
    measurement = json.loads(output.read_bytes())
    assert measurement["alternatives"] == 123
    assert measurement["input_bytes"] > 1000
    assert measurement["max_output_tokens"] == 3000
    assert measurement["token_measurement"] == "conservative_utf8_upper_bound"


def test_cli_never_overwrites_existing_evidence(tmp_path: Path) -> None:
    config, draft, output = _inputs(tmp_path)
    output.write_text("existing evidence")
    with pytest.raises(SystemExit, match="2"):
        results.main(["author", "--projection", str(SOURCE), "--config", str(config),
                      "--draft", str(draft), "--output", str(output)])
    assert output.read_text() == "existing evidence"


def test_cli_requires_explicit_mode_and_runtime_settings() -> None:
    with pytest.raises(SystemExit, match="2"):
        results.main(["author", "--projection", str(SOURCE), "--output", "/unused"])


def test_cli_rechecks_inputs_before_atomic_publish(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    config, _, output = _inputs(tmp_path)
    original = results.prepare_results

    def changing_input(projection: SolutionProjection,
                       settings: ResultsConfig) -> PreparedResultsInput:
        config.write_text("changed configuration")
        return original(projection, settings)

    monkeypatch.setattr(results, "prepare_results", changing_input)
    with pytest.raises(ValueError, match="changed during processing"):
        results.main(["measure", "--projection", str(SOURCE), "--config", str(config),
                      "--output", str(output)])
    assert not output.exists()


def test_cli_rejects_invalid_source_without_creating_output(tmp_path: Path) -> None:
    config, _, output = _inputs(tmp_path)
    bad_source = tmp_path / "bad.json"
    bad_source.write_text("{}")
    with pytest.raises(ValueError):
        results.main(["measure", "--projection", str(bad_source), "--config", str(config),
                      "--output", str(output)])
    assert not output.exists()
