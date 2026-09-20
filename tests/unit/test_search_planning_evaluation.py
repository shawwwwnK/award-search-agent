"""Offline evaluator and immutable handoff checks for the current compiler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.evaluation.search_planning import (
    GoldenCoverageTag,
    load_search_planning_golden_corpus,
    preflight_search_planning_golden_corpus,
    run_search_planning_golden_eval,
)
from award_agent.search_planning import (
    PlanHandoffCheck,
    PlanHandoffStatus,
    load_default_cached_search_capability,
    verify_capability_source_artifacts,
)


@pytest.fixture(scope="module")
def artifact() -> dict[str, object]:
    return run_search_planning_golden_eval()


def test_golden_corpus_preflight_and_exact_gate_pass_without_live_dependencies(
    artifact: dict[str, object],
) -> None:
    corpus = preflight_search_planning_golden_corpus()
    assert set(corpus.coverage_matrix) == set(GoldenCoverageTag)
    summary = artifact["summary"]
    assert isinstance(summary, dict)
    assert summary == {
        "runs": 4,
        "passed": 4,
        "failed": 0,
        "exact_gate": {"passed": True},
    }


def test_golden_cases_pin_complete_result_bytes_and_expected_outcomes(
    artifact: dict[str, object],
) -> None:
    records = artifact["cases"]
    assert isinstance(records, list)
    assert all(item["status"] == "passed" for item in records)
    assert all(len(item["result_sha256"]) == 64 for item in records)
    by_id = {item["case_id"]: item for item in records}
    assert by_id["domestic_mandatory"]["result_sha256"] == by_id[
        "domestic_mandatory_peer"
    ]["result_sha256"]
    assert by_id["cross_market_generation_failure"]["outcome"] == "reduced_coverage"


def test_preflight_rejects_unknown_fields_and_tampered_input_pins(tmp_path: Path) -> None:
    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValidationError, match="unexpected"):
        preflight_search_planning_golden_corpus(unknown)

    source.pop("unexpected")
    source["planning_policy_sha256"] = "0" * 64
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="planning policy canonical SHA-256"):
        preflight_search_planning_golden_corpus(tampered)


def test_preflight_rejects_incomplete_coverage_and_invalid_peer(tmp_path: Path) -> None:
    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["coverage_matrix"].pop("optional_empty")
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="every required category"):
        preflight_search_planning_golden_corpus(missing)

    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["cases"][0]["canonical_peer_case_id"] = source["cases"][0]["case_id"]
    invalid_peer = tmp_path / "peer.json"
    invalid_peer.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot name themselves"):
        preflight_search_planning_golden_corpus(invalid_peer)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"local_path": "../outside"}, "resolves outside the repository"),
        ({"content_sha256": "0" * 64}, "content SHA-256 does not match"),
    ],
)
def test_capability_source_verification_rejects_unsafe_or_tampered_evidence(
    change: dict[str, str], match: str
) -> None:
    document = load_default_cached_search_capability().model_dump(mode="json")
    document["sources"][0].update(change)
    capability = type(load_default_cached_search_capability()).model_validate(document)
    with pytest.raises(ValueError, match=match):
        verify_capability_source_artifacts(capability)


def test_handoff_receipt_rejects_forged_binding_status_and_executable_bit() -> None:
    kwargs = {
        "plan_session_id": "session",
        "plan_revision": 2,
        "current_session_id": "session",
        "current_revision": 2,
        "plan_effective_request_digest": "a" * 64,
        "current_effective_request_digest": "a" * 64,
        "plan_compilation_binding_digest": "b" * 64,
        "expected_compilation_binding_digest": "b" * 64,
    }
    current = PlanHandoffCheck(status=PlanHandoffStatus.CURRENT, **kwargs)
    assert current.executable is True
    with pytest.raises(ValidationError, match="status must be derived"):
        PlanHandoffCheck(
            status=PlanHandoffStatus.CURRENT,
            **{**kwargs, "expected_compilation_binding_digest": "c" * 64},
        )
    with pytest.raises(ValidationError, match="executable"):
        PlanHandoffCheck(status=PlanHandoffStatus.CURRENT, executable=False, **kwargs)
