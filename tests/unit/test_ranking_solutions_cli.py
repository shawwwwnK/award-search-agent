"""Offline CLI tests for deterministic Ranking M2 solution projection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from award_agent.ranking.project_solutions import project_solutions

from award_agent.cli import ranking_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankedJourneySet

RANKED = Path("evidence/ranking-stage/m2/styled/sfo_to_bkk_positioning.json")


def _arguments(tmp_path: Path, output: Path) -> list[str]:
    ranked_copy = tmp_path / "ranked.json"
    ranked_copy.write_bytes(RANKED.read_bytes())
    return ["--ranked", str(ranked_copy), "--output", str(output)]


def test_cli_writes_round_trip_equivalent_projection_and_minimal_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "solutions.json"
    arguments = _arguments(tmp_path, output)
    ranked = RankedJourneySet.model_validate_json(Path(arguments[1]).read_bytes())
    expected = project_solutions(ranked)

    assert ranking_solutions.main(arguments) == 0

    actual = SolutionProjection.model_validate_json(output.read_bytes())
    assert actual == expected
    summary = json.loads(capsys.readouterr().out)
    assert summary == {
        "output": str(output),
        "total_candidates": actual.receipt.total_candidates,
        "eligible_alternatives": actual.receipt.eligible_alternatives,
        "bytes": output.stat().st_size,
    }


def test_cli_rejects_invalid_input_without_creating_output(tmp_path: Path) -> None:
    output = tmp_path / "solutions.json"
    arguments = _arguments(tmp_path, output)
    Path(arguments[1]).write_text("{not json", encoding="utf-8")

    with pytest.raises((ValueError, TypeError)):
        ranking_solutions.main(arguments)

    assert not output.exists()


def test_cli_rechecks_input_before_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "solutions.json"
    arguments = _arguments(tmp_path, output)
    ranked_path = Path(arguments[1])
    original = ranking_solutions.project_solutions

    def project_then_change(ranked: RankedJourneySet) -> SolutionProjection:
        result = original(ranked)
        ranked_path.write_text("changed", encoding="utf-8")
        return result

    monkeypatch.setattr(ranking_solutions, "project_solutions", project_then_change)
    with pytest.raises(ValueError, match="changed during solution projection"):
        ranking_solutions.main(arguments)

    assert not output.exists()


def test_cli_never_overwrites_file_or_symlink(tmp_path: Path) -> None:
    existing = tmp_path / "existing.json"
    existing.write_text("existing evidence", encoding="utf-8")
    link = tmp_path / "linked.json"
    link.symlink_to(existing)
    arguments_by_output = {output: _arguments(tmp_path, output) for output in (existing, link)}

    for output, arguments in arguments_by_output.items():
        with pytest.raises(SystemExit, match="2"):
            ranking_solutions.main(arguments)
        assert output.is_symlink() or output.read_text(encoding="utf-8") == "existing evidence"

    assert existing.read_text(encoding="utf-8") == "existing evidence"


def test_cli_requires_ranked_and_output_arguments() -> None:
    with pytest.raises(SystemExit, match="2"):
        ranking_solutions.main([])
