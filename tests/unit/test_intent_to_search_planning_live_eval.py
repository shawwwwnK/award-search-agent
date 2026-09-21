"""Offline preflight tests for the active-corpus end-to-end connector."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Self

import pytest

from award_agent.domain import DateWindow, DateWindowPrecision, EffectiveRequest, RequestContext
from award_agent.evaluation.intent_to_search_planning_live import (
    CORPUS_SHA256,
    DEFAULT_CORPUS,
    EndToEndFixtureError,
    _gateway_outbound_date,
    _load_corpus,
    run_intent_to_search_planning_live_eval,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
)


class _PreflightRepository:
    def __init__(self, _path: Path) -> None:
        self.knowledge_receipt = CatalogKnowledgeReceipt(
            release_id="test-release",
            schema_version="2",
            source_date=date(2026, 9, 20),
            logical_content_sha256="0" * 64,
            manifest_sha256="1" * 64,
            database_sha256="2" * 64,
            source_bundle_manifest_sha256="3" * 64,
            source_artifacts=(
                CatalogSourceArtifactReceipt(artifact_name="fixture", bytes=1, sha256="4" * 64),
            ),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _adapter_must_not_be_constructed(_config: object) -> Any:
    raise AssertionError("preflight constructed a live model adapter")


def test_active_corpus_contract_and_identity_are_bound() -> None:
    cases = _load_corpus(DEFAULT_CORPUS)
    assert len(cases) == 19
    assert len({case["coverage_family"] for case in cases}) == 19
    assert CORPUS_SHA256 == "52a98b9ca316b9a2744c21072d6d0d603bcf4265f45328b6358ef2f1a238607a"


def test_same_shape_corpus_copy_is_rejected_after_byte_drift(tmp_path: Path) -> None:
    changed = tmp_path / "cases.yaml"
    changed.write_bytes(DEFAULT_CORPUS.read_bytes() + b"\n")
    with pytest.raises(EndToEndFixtureError, match="identity drifted"):
        _load_corpus(changed)


def test_models_and_trials_are_hard_bounded_before_catalog_access() -> None:
    with pytest.raises(ValueError, match="pinned"):
        run_intent_to_search_planning_live_eval(model="other", preflight_only=True)
    with pytest.raises(ValueError, match="exactly one"):
        run_intent_to_search_planning_live_eval(trials=2, preflight_only=True)


def test_preflight_binds_denominator_and_constructs_no_model_adapters() -> None:
    artifact = run_intent_to_search_planning_live_eval(
        preflight_only=True,
        repository_factory=_PreflightRepository,
        intent_factory=_adapter_must_not_be_constructed,
        composer_factory=_adapter_must_not_be_constructed,
        selector_factory=_adapter_must_not_be_constructed,
        gateway_factory=_adapter_must_not_be_constructed,
    )

    assert artifact["corpus"] == {
        "path": str(DEFAULT_CORPUS),
        "contract_version": "intent_behavior_v1",
        "sha256": CORPUS_SHA256,
        "denominator": 19,
    }
    assert len(artifact["selected_case_ids"]) == 19
    assert artifact["call_ceiling"] == {"per_case": 6, "selected_total": 114}
    assert artifact["travel_provider_calls"] == 0
    assert artifact["summary"] == {
        "preflight_passed": True,
        "runs": 0,
        "mechanically_completed": False,
    }


def test_gateway_date_context_preserves_exact_effective_request_precision() -> None:
    request = EffectiveRequest(
        context=RequestContext(reference_date=date(2026, 9, 20), timezone="UTC"),
        departure_window=DateWindow(
            start=date(2027, 3, 10),
            end=date(2027, 3, 10),
            precision=DateWindowPrecision.EXACT,
            raw_text="March 10",
        ),
    )

    assert _gateway_outbound_date(request).model_dump(mode="json") == {
        "start": "2027-03-10",
        "end": "2027-03-10",
        "timezone": "UTC",
        "effective_window_precision": "exact",
    }
