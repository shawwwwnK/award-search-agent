"""Offline CLI tests for deterministic Ranking M2 style assignment."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from award_agent.cli import ranking_styles
from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.style_contracts import (
    CurrencyConversionSnapshot,
    RankedJourneySet,
    RankingStylePolicy,
)

MATCHED = Path("evidence/ranking-stage/m1/mixed_access.json")


def _snapshot_file(path: Path) -> Path:
    snapshot = CurrencyConversionSnapshot(
        snapshot_id="cli-test-fx-v1",
        as_of=date(2026, 10, 1),
        source="unit test fixture",
        source_digest="0" * 64,
        rates_to_usd={"USD": Decimal(1)},
    )
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def _policy_file(path: Path) -> Path:
    policy = RankingStylePolicy()
    path.write_text(policy.model_dump_json(indent=2), encoding="utf-8")
    return path


def _arguments(
    tmp_path: Path,
    output: Path,
    snapshot: Path,
    policy: Path | None = None,
) -> list[str]:
    matched_copy = tmp_path / "matched.json"
    matched_copy.write_bytes(MATCHED.read_bytes())
    arguments = [
        "--matched", str(matched_copy),
        "--fx-snapshot", str(snapshot),
        "--output", str(output),
    ]
    if policy is not None:
        arguments.extend(["--policy", str(policy)])
    return arguments


def test_cli_serializes_returned_model_and_prints_minimal_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot = _snapshot_file(tmp_path / "fx.json")
    output = tmp_path / "styled.json"

    assert ranking_styles.main(_arguments(tmp_path, output, snapshot)) == 0

    serialized = json.loads(output.read_text(encoding="utf-8"))
    summary = json.loads(capsys.readouterr().out)
    assert isinstance(serialized, dict)
    assert summary == {"output": str(output)}


def test_cli_accepts_explicit_policy(tmp_path: Path) -> None:
    snapshot = _snapshot_file(tmp_path / "fx.json")
    policy = _policy_file(tmp_path / "policy.json")
    output = tmp_path / "styled.json"

    assert ranking_styles.main(_arguments(tmp_path, output, snapshot, policy)) == 0
    assert output.is_file()


@pytest.mark.parametrize("source", ["matched", "snapshot", "policy"])
def test_cli_rejects_malformed_supplied_input(
    tmp_path: Path, source: str,
) -> None:
    snapshot = _snapshot_file(tmp_path / "fx.json")
    policy = _policy_file(tmp_path / "policy.json")
    output = tmp_path / "styled.json"
    arguments = _arguments(tmp_path, output, snapshot, policy)
    matched_copy = Path(arguments[1])
    source_paths = {"matched": matched_copy, "snapshot": snapshot, "policy": policy}
    source_path = source_paths[source]
    if source == "matched":
        source_path = matched_copy
    source_path.write_text("{not json", encoding="utf-8")

    with pytest.raises((ValueError, TypeError)):
        ranking_styles.main(arguments)

    assert not output.exists()


@pytest.mark.parametrize("source", ["matched", "snapshot", "policy"])
def test_cli_rechecks_supplied_inputs_before_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    snapshot = _snapshot_file(tmp_path / "fx.json")
    policy = _policy_file(tmp_path / "policy.json")
    output = tmp_path / "styled.json"
    arguments = _arguments(tmp_path, output, snapshot, policy)
    matched_copy = Path(arguments[1])
    source_paths = {"matched": matched_copy, "snapshot": snapshot, "policy": policy}
    source_path = source_paths[source]
    original = ranking_styles.assign_journey_styles

    def assign_then_change(
        matched: MatchedJourneySet,
        *,
        policy: RankingStylePolicy,
        fx_snapshot: CurrencyConversionSnapshot,
    ) -> RankedJourneySet:
        result = original(matched, policy=policy, fx_snapshot=fx_snapshot)
        source_path.write_text("changed", encoding="utf-8")
        return result

    monkeypatch.setattr(ranking_styles, "assign_journey_styles", assign_then_change)
    with pytest.raises((ValueError, OSError)):
        ranking_styles.main(arguments)

    assert not output.exists()


def test_cli_never_overwrites_file_or_symlink(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot_file(tmp_path / "fx.json")
    existing = tmp_path / "existing.json"
    existing.write_text("existing evidence", encoding="utf-8")
    link = tmp_path / "linked.json"
    link.symlink_to(existing)

    for output in (existing, link):
        with pytest.raises(SystemExit, match="2"):
            ranking_styles.main(_arguments(tmp_path, output, snapshot))

    assert existing.read_text(encoding="utf-8") == "existing evidence"


def test_cli_requires_all_but_policy_arguments() -> None:
    with pytest.raises(SystemExit, match="2"):
        ranking_styles.main([])
