"""Bounded tests for Ranking M2 corpus artifact generation and verification."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Inexact, localcontext
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

MATCHED_CASE = Path("evidence/ranking-stage/m1/exact_business.json")
FX_SNAPSHOT = Path("data/ranking/m2/fx-2026-09-29.json")
SCRIPT_SPEC = spec_from_file_location(
    "ranking_style_corpus_script", Path("scripts/ranking_style_corpus.py")
)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
SCRIPT_MODULE = module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(SCRIPT_MODULE)
main = SCRIPT_MODULE.main


def test_corpus_generation_verification_tamper_and_no_overwrite(tmp_path: Path) -> None:
    matched_directory = tmp_path / "matched"
    matched_directory.mkdir()
    (matched_directory / MATCHED_CASE.name).write_bytes(MATCHED_CASE.read_bytes())
    output_directory = tmp_path / "generated"
    arguments = [
        "--matched-dir", str(matched_directory),
        "--fx-snapshot", str(FX_SNAPSHOT),
        "--output-dir", str(output_directory),
    ]

    with localcontext() as decimal_context:
        decimal_context.prec = 5
        decimal_context.rounding = ROUND_DOWN
        decimal_context.traps[Inexact] = True
        assert main(arguments) == 0

    index_path = output_directory / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    case = index["cases"][0]
    counts = case["counts"]
    assert counts["time_members"] >= 0
    assert counts["cost_members"] >= 0
    assert counts["premium_members"] >= 0
    assert counts["possible_cost_members"] >= 0
    assert counts["premium_economy_addons"] >= 0
    assert counts["definite_highlights"] >= 0
    assert counts["possible_highlights"] >= 0
    assert "cost_reference_usd" in case
    assert "cost_threshold_usd" in case
    assert "eligible_cost_assessment_states" in counts
    assert "estimated_cost_components_all_retained" in counts
    assert "estimated_cost_components_eligible" in counts
    assert "estimated_cost_candidates_all_retained" in counts
    assert "estimated_cost_candidates_eligible" in counts

    assert main([*arguments, "--verify"]) == 0

    output_path = output_directory / case["output"]
    output_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="saved output differs"):
        main([*arguments, "--verify"])

    tampered_content = output_path.read_bytes()
    with pytest.raises(ValueError, match="output directory must be new"):
        main(arguments)
    assert output_path.read_bytes() == tampered_content


def test_corpus_rejects_matched_endpoint_changed_from_provider_evidence(
    tmp_path: Path,
) -> None:
    matched_directory = tmp_path / "matched"
    matched_directory.mkdir()
    raw_matched = json.loads(MATCHED_CASE.read_text(encoding="utf-8"))
    source_journey = next(
        journey for journey in raw_matched["journeys"]
        if journey["departure_instant"] is not None
    )
    departure = datetime.fromisoformat(source_journey["departure_instant"])
    source_journey["departure_instant"] = (departure + timedelta(seconds=1)).isoformat()
    raw_observations = {
        observation["observation_id"]: observation
        for observation in raw_matched["provider_result"]["observations"]
    }
    with pytest.raises(ValueError, match="endpoint instants differ"):
        SCRIPT_MODULE._assert_source_timing(source_journey, raw_observations)
    matched_path = matched_directory / MATCHED_CASE.name
    matched_path.write_text(json.dumps(raw_matched), encoding="utf-8")
    output_directory = tmp_path / "generated"

    with pytest.raises(ValueError, match="endpoints differ"):
        main([
            "--matched-dir", str(matched_directory),
            "--fx-snapshot", str(FX_SNAPSHOT),
            "--output-dir", str(output_directory),
        ])

    assert not (output_directory / MATCHED_CASE.name).exists()
