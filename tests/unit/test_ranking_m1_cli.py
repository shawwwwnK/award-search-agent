"""Offline Ranking M1 command, using plan-linked provider evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from award_agent.cli.ranking_match import main
from award_agent.providers.contracts import ProviderResultSet

CORPUS = Path("evidence/provider-stage/saved-searches/runs")
MIXED = CORPUS / "mixed_access"
EXACT = CORPUS / "exact_business"


def test_cli_replays_deterministically_without_provider_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_live_call(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Ranking M1 must not call a provider")

    monkeypatch.setattr("subprocess.run", no_live_call)
    outputs = [tmp_path / "matched-1.json", tmp_path / "matched-2.json"]
    for output in outputs:
        assert main([
            "--bundle", str(MIXED / "bundle.json"),
            "--result", str(MIXED / "result.json"),
            "--output", str(output),
        ]) == 0
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    assert isinstance(json.loads(outputs[0].read_text()), dict)


def test_cli_rejects_result_from_a_different_plan(tmp_path: Path) -> None:
    output = tmp_path / "matched.json"
    with pytest.raises(ValueError):
        main([
            "--bundle", str(EXACT / "bundle.json"),
            "--result", str(MIXED / "result.json"),
            "--output", str(output),
        ])
    assert not output.exists()


def test_cli_rejects_stale_result(tmp_path: Path) -> None:
    source = ProviderResultSet.model_validate_json((MIXED / "result.json").read_text())
    stale = source.model_copy(update={"status": "stale"})
    stale_path = tmp_path / "stale-result.json"
    stale_path.write_text(stale.model_dump_json())
    output = tmp_path / "matched.json"
    with pytest.raises(ValueError, match="stale"):
        main([
            "--bundle", str(MIXED / "bundle.json"),
            "--result", str(stale_path),
            "--output", str(output),
        ])
    assert not output.exists()


def test_cli_never_overwrites_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "matched.json"
    output.write_text("existing evidence\n")
    with pytest.raises(SystemExit, match="2"):
        main([
            "--bundle", str(MIXED / "bundle.json"),
            "--result", str(MIXED / "result.json"),
            "--output", str(output),
        ])
    assert output.read_text() == "existing evidence\n"


def test_cli_requires_positive_combination_bound(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="2"):
        main([
            "--bundle", str(MIXED / "bundle.json"),
            "--result", str(MIXED / "result.json"),
            "--output", str(tmp_path / "matched.json"),
            "--max-combinations", "0",
        ])
