"""Offline tests for Ranking M2 solution corpus generation and replay verification."""

from __future__ import annotations

import hashlib
import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import RankedJourneySet

SOURCE_DIR = Path("evidence/ranking-stage/m2/styled")
SCRIPT_SPEC = spec_from_file_location(
    "ranking_solution_corpus_script", Path("scripts/ranking_solution_corpus.py")
)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
SCRIPT_MODULE = module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(SCRIPT_MODULE)

EXPECTED = {
    "mixed_access": {
        "candidates": 473,
        "eligible": 257,
        "statuses": {"admitted": 17, "conditional": 240, "rejected": 216},
    },
    "exact_business": {
        "candidates": 396,
        "eligible": 106,
        "statuses": {"conditional": 106, "rejected": 290},
    },
    "sfo_to_bkk_positioning": {
        "candidates": 123,
        "eligible": 64,
        "statuses": {"admitted": 5, "conditional": 59, "rejected": 58,
                     "research_lead": 1},
    },
}


def _run(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["ranking_solution_corpus.py", *arguments])
    return SCRIPT_MODULE.main()


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _arguments(source_dir: Path, output_dir: Path) -> list[str]:
    return ["--source-dir", str(source_dir), "--output-dir", str(output_dir)]


def test_corpus_generation_and_verification_bind_exact_bytes_hashes_and_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = _arguments(SOURCE_DIR, output_dir)

    assert _run(monkeypatch, arguments) == 0

    index_bytes = (output_dir / "index.json").read_bytes()
    index = json.loads(index_bytes)
    assert index["version"] == "ranking-solution-corpus-v1"
    assert set(index["cases"]) == set(SCRIPT_MODULE.CASES)
    for case in SCRIPT_MODULE.CASES:
        source_bytes = (SOURCE_DIR / f"{case}.json").read_bytes()
        ranked = RankedJourneySet.model_validate_json(source_bytes)
        expected_projection = project_solutions(ranked)
        expected_bytes = (expected_projection.model_dump_json(indent=2) + "\n").encode()
        artifact_path = output_dir / f"{case}.json"
        artifact_bytes = artifact_path.read_bytes()
        entry = index["cases"][case]
        projection = SolutionProjection.model_validate_json(artifact_bytes)
        expected_counts = EXPECTED[case]

        assert artifact_bytes == expected_bytes
        assert projection == expected_projection
        assert entry["source_sha256"] == _sha(source_bytes)
        assert entry["output_sha256"] == _sha(artifact_bytes)
        assert entry["source_bytes"] == len(source_bytes)
        assert entry["artifact_bytes"] == len(artifact_bytes)
        assert entry["compact_view_bytes"] == len(projection.view.model_dump_json().encode())
        assert entry["source_digest"] == projection.receipt.source_digest
        assert entry["view_digest"] == projection.receipt.view_digest
        assert entry["candidates"] == expected_counts["candidates"]
        assert entry["eligible"] == expected_counts["eligible"]
        assert entry["statuses"] == expected_counts["statuses"]
        assert entry["components"] == len(projection.view.components)

    assert _run(monkeypatch, [*arguments, "--verify"]) == 0


def test_corpus_verification_rejects_tampered_saved_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "generated"
    arguments = _arguments(SOURCE_DIR, output_dir)
    _run(monkeypatch, arguments)
    output_path = output_dir / "mixed_access.json"
    output_path.write_bytes(output_path.read_bytes() + b" ")

    with pytest.raises(ValueError, match="saved export or index differs"):
        _run(monkeypatch, [*arguments, "--verify"])


def test_corpus_rejects_source_mutated_after_projection_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source_path = source_dir / "mixed_access.json"
    source_path.write_bytes((SOURCE_DIR / "mixed_access.json").read_bytes())
    output_dir = tmp_path / "generated"
    original_project = SCRIPT_MODULE.project_solutions

    def project_then_change(ranked: RankedJourneySet) -> SolutionProjection:
        projection = original_project(ranked)
        source_path.write_bytes(source_path.read_bytes() + b" ")
        return projection

    monkeypatch.setattr(SCRIPT_MODULE, "project_solutions", project_then_change)
    with pytest.raises(ValueError, match="source changed during projection"):
        _run(monkeypatch, _arguments(source_dir, output_dir))

    assert output_dir.is_dir()
    assert not (output_dir / "mixed_access.json").exists()
    assert not (output_dir / "index.json").exists()
