"""Qualification tests for the fixture-only search-planning golden evaluator."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.evaluation.search_planning import (
    GoldenCoverageTag,
    _request_from_fixture,
    canonical_sha256,
    load_search_planning_golden_corpus,
    preflight_search_planning_golden_corpus,
    run_search_planning_golden_eval,
)
from award_agent.search_planning import (
    PlanHandoffCheck,
    PlanHandoffStatus,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    check_plan_handoff,
    load_default_cached_search_capability,
    load_default_knowledge_snapshot,
    plan_searches,
    verify_capability_source_artifacts,
)


def test_golden_corpus_preflight_and_exact_gate_pass_without_live_dependencies() -> None:
    corpus = preflight_search_planning_golden_corpus()
    artifact = run_search_planning_golden_eval()

    assert corpus.fixture_grade_only is True
    assert artifact["fixture_grade_only"] is True
    assert artifact["input_identities"] == {
        "knowledge_snapshot": {
            "snapshot_id": corpus.knowledge_snapshot_id,
            "canonical_sha256": corpus.knowledge_snapshot_sha256,
        },
        "capability": {
            "capability_id": corpus.capability_id,
            "capability_version": corpus.capability_version,
            "canonical_sha256": corpus.capability_sha256,
            "source_artifacts": [
                {
                    "source_id": "seats-aero-cached-search-local-2026-09-08",
                    "local_path": ".provider-docs/seats-aero/cached-search.md",
                    "content_sha256": "86cfe87ef7052dd72b356e53a09e98795de5cb47a5268338ebbd21c0345d0640",
                }
            ],
        },
        "default_policy": {
            "policy_version": "search-planning-v1",
            "canonical_sha256": corpus.default_policy_sha256,
        },
    }
    assert artifact["summary"] == {
        "runs": 10,
        "passed": 10,
        "failed": 0,
        "exact_gate": {"passed": True},
    }
    assert all(record["status"] == "passed" for record in artifact["cases"])


def test_optional_path_budget_golden_case_proves_endpoints_and_receipts_survive() -> None:
    corpus = load_search_planning_golden_corpus()
    assert corpus.coverage_matrix[GoldenCoverageTag.OPTIONAL_PATH_BUDGET_DEGRADATION] == (
        "optional_path_budget_omission",
    )

    record = next(
        item
        for item in run_search_planning_golden_eval()["cases"]
        if item["case_id"] == "optional_path_budget_omission"
    )
    assert record["status"] == "passed"
    assert record["checks"]["endpoint_probe_count"] is True
    assert record["checks"]["budget_receipt_count"] is True
    assert record["checks"]["path_candidate_budget_observed"] is True
    assert record["checks"]["path_candidate_budget_limit"] is True


def test_corpus_result_fingerprints_are_stable_and_reordered_fixture_is_a_peer() -> None:
    first = run_search_planning_golden_eval()
    second = run_search_planning_golden_eval()

    assert canonical_sha256(first) == canonical_sha256(second)
    reordered = next(record for record in first["cases"] if record["case_id"] == "japan_sfo_reordered")
    assert reordered["checks"]["canonical_peer"] is True


def test_caller_handoff_rejects_stale_revision_and_stale_request_without_mutation() -> None:
    corpus = load_search_planning_golden_corpus()
    case = next(item for item in corpus.cases if item.case_id == "japan_sfo_no_onward")
    request = _request_from_fixture(case.request)
    before = deepcopy(request.model_dump(mode="json", round_trip=True))
    result = plan_searches(
        PlanningInputEnvelope(
            source=PlanningSource(session_id="handoff-session", revision=7),
            effective_request=request,
        ),
        policy=PlanningPolicy(),
        snapshot=load_default_knowledge_snapshot(),
        capability=load_default_cached_search_capability(),
    )
    assert result.plan is not None

    current = check_plan_handoff(
        result.plan,
        current_session_id="handoff-session",
        current_revision=7,
        current_effective_request=request,
    )
    stale_revision = check_plan_handoff(
        result.plan,
        current_session_id="handoff-session",
        current_revision=8,
        current_effective_request=request,
    )
    changed_request = request.model_copy(update={"raw_text": "A later caller request"})
    stale_request = check_plan_handoff(
        result.plan,
        current_session_id="handoff-session",
        current_revision=7,
        current_effective_request=changed_request,
    )

    assert current.status is PlanHandoffStatus.CURRENT and current.executable is True
    assert stale_revision.status is PlanHandoffStatus.STALE_SESSION_OR_REVISION
    assert not stale_revision.executable
    assert stale_request.status is PlanHandoffStatus.STALE_EFFECTIVE_REQUEST
    assert stale_request.executable is False
    assert request.model_dump(mode="json", round_trip=True) == before


def test_preflight_rejects_unknown_fixture_fields(tmp_path: Path) -> None:
    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["unexpected"] = True
    path = tmp_path / "bad-cases.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(Exception, match="unexpected"):
        preflight_search_planning_golden_corpus(path)


@pytest.mark.parametrize(
    ("field", "replacement", "match"),
    [
        ("knowledge_snapshot_sha256", "0" * 64, "knowledge snapshot canonical SHA-256"),
        ("capability_version", "0.0.0", "capability version"),
        ("capability_sha256", "0" * 64, "capability canonical SHA-256"),
        ("default_policy_sha256", "0" * 64, "default policy canonical SHA-256"),
    ],
)
def test_preflight_rejects_tampered_default_input_pins(
    tmp_path: Path, field: str, replacement: str, match: str
) -> None:
    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source[field] = replacement
    path = tmp_path / "tampered-pins.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match=match):
        preflight_search_planning_golden_corpus(path)


def test_preflight_rejects_missing_coverage_category_and_self_canonical_peer(
    tmp_path: Path,
) -> None:
    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["coverage_matrix"].pop("budget_exhaustion")
    missing_coverage = tmp_path / "missing-coverage.json"
    missing_coverage.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="every required category"):
        preflight_search_planning_golden_corpus(missing_coverage)

    source = load_search_planning_golden_corpus().model_dump(mode="json")
    source["cases"][0]["canonical_peer_case_id"] = source["cases"][0]["case_id"]
    self_peer = tmp_path / "self-peer.json"
    self_peer.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot name themselves"):
        preflight_search_planning_golden_corpus(self_peer)


@pytest.mark.parametrize(
    ("source_change", "match"),
    [
        ({"local_path": "../outside"}, "resolves outside the repository"),
        ({"content_sha256": "0" * 64}, "content SHA-256 does not match"),
    ],
)
def test_capability_source_artifact_verification_rejects_unsafe_or_tampered_evidence(
    source_change: dict[str, str], match: str
) -> None:
    document = load_default_cached_search_capability().model_dump(mode="json")
    document["sources"][0].update(source_change)
    capability = type(load_default_cached_search_capability()).model_validate(document)

    with pytest.raises(ValueError, match=match):
        verify_capability_source_artifacts(capability)


def test_handoff_receipt_model_rejects_forged_status_and_executable_bits() -> None:
    current = PlanHandoffCheck(
        status=PlanHandoffStatus.CURRENT,
        plan_session_id="session",
        plan_revision=1,
        current_session_id="session",
        current_revision=1,
        plan_effective_request_digest="a" * 64,
        current_effective_request_digest="a" * 64,
    )
    assert current.executable is True

    forged_status = current.model_dump(mode="json")
    forged_status["current_revision"] = 2
    with pytest.raises(ValidationError, match="status must be derived"):
        PlanHandoffCheck.model_validate(forged_status)

    forged_executable = current.model_dump(mode="json")
    forged_executable["executable"] = False
    with pytest.raises(ValidationError, match="executable must match"):
        PlanHandoffCheck.model_validate(forged_executable)
