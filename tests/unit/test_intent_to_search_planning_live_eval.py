"""Offline tests for the active-corpus end-to-end connector."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Self

import pytest

from award_agent.domain import (
    CabinClass,
    DateWindow,
    DateWindowPrecision,
    EffectiveRequest,
    LocationKind,
    RequestContext,
    SearchMode,
)
from award_agent.evaluation.intent_to_search_planning_live import (
    CORPUS_SHA256,
    DEFAULT_CORPUS,
    EndToEndFixtureError,
    _gateway_outbound_date,
    _load_corpus,
    run_intent_to_search_planning_live_eval,
)
from award_agent.intent.semantic import (
    CalendarOperationKind,
    SemanticFact,
    SemanticFactTarget,
    SemanticIntentProposal,
    SemanticTemporalFact,
    SemanticTemporalTarget,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
    FreshnessClass,
)
from award_agent.search_planning.gateway_generator import GatewayCandidateProposal
from award_agent.search_planning.knowledge import Airport, AirportSelectionMetadata
from award_agent.search_planning.market_policy import load_default_planning_market_policy


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


class _RuntimeRepository(_PreflightRepository):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        details = {
            "SFO": ("ourairports:3878", "US", "US-CA", "large_airport"),
            "BKK": ("ourairports:28118", "TH", "TH-10", "large_airport"),
        }
        for override in load_default_planning_market_policy().airport_overrides:
            details.setdefault(
                override.expected_iata,
                (
                    override.airport_id,
                    override.expected_country_code,
                    override.expected_iso_region,
                    "large_airport",
                ),
            )
        self.airports = {
            code: Airport(
                airport_id=airport_id,
                iata=code,
                label=code,
                country_entity_id=f"country:{country_code}",
                timezone="UTC",
                aliases=(code,),
                source_ids=(f"source:{code}",),
            )
            for code, (airport_id, country_code, _, _) in details.items()
        }
        self.metadata = {
            airport_id: AirportSelectionMetadata(
                airport_id=airport_id,
                country_code=country_code,
                iso_region=region,
                airport_type=airport_type,
                latitude=0,
                longitude=0,
            )
            for airport_id, country_code, region, airport_type in details.values()
        }

    def lookup_airport_iata(self, code: str) -> Airport | None:
        return self.airports.get(code)

    @property
    def snapshot_id(self) -> str:
        return self.knowledge_receipt.release_id

    def freshness_for_source_ids(
        self, _source_ids: object, *, max_source_evidence_age_days: int
    ) -> FreshnessClass:
        return FreshnessClass.CURRENT

    def airport(self, airport_id: str) -> Airport | None:
        return next(
            (item for item in self.airports.values() if item.airport_id == airport_id), None
        )

    def airport_selection_metadata(self, airport_id: str) -> AirportSelectionMetadata | None:
        return self.metadata.get(airport_id)


class _RuntimeAdapter:
    def __init__(self, _config: object) -> None:
        self.calls = 0

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": self.calls,
            "captured_calls": self.calls,
            "missing_calls": 0,
            "input_tokens": self.calls,
            "output_tokens": self.calls,
            "total_tokens": self.calls * 2,
        }

    def take_call_traces(self) -> list[dict[str, Any]]:
        return [{"private_input": "PRIVATE_TRACE_SENTINEL"}] * self.calls


class _RuntimeIntent(_RuntimeAdapter):
    def interpret(self, _input: object) -> SemanticIntentProposal:
        self.calls += 1
        return SemanticIntentProposal(
            facts=(
                SemanticFact(
                    target=SemanticFactTarget.ORIGIN,
                    quote="SFO",
                    location_kind=LocationKind.AIRPORT,
                    location_value="SFO",
                ),
                SemanticFact(
                    target=SemanticFactTarget.DESTINATION,
                    quote="BKK",
                    location_kind=LocationKind.AIRPORT,
                    location_value="BKK",
                ),
                SemanticFact(target=SemanticFactTarget.TRAVELERS, quote="two", travelers=2),
                SemanticFact(
                    target=SemanticFactTarget.CABIN,
                    quote="business",
                    cabin=CabinClass.BUSINESS,
                ),
                SemanticFact(
                    target=SemanticFactTarget.SEARCH_MODE,
                    quote="award",
                    search_mode=SearchMode.AWARD,
                ),
            ),
            temporal_facts=(
                SemanticTemporalFact(
                    fact_id="departure",
                    target=SemanticTemporalTarget.DEPARTURE,
                    quote="October 5",
                    operation=CalendarOperationKind.LITERAL_INTERVAL,
                    start_month=10,
                    start_day=5,
                ),
            ),
        )


class _RuntimeGateway(_RuntimeAdapter):
    def propose(self, _input: object) -> GatewayCandidateProposal:
        self.calls += 1
        return GatewayCandidateProposal(
            endpoint_market_assessments=(),
            origin_access_gateways=(),
            destination_access_gateways=(),
            intermediate_hubs=(),
        )


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
    assert "capability" not in artifact["identities"]
    assert set(artifact["compiler_policy"]).isdisjoint(
        {
            "max_supplemental_relationship_bundles",
            "max_unique_logical_queries",
            "max_query_date_days",
        }
    )
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


def test_bounded_runtime_forwards_gateway_trace_and_usage_offline(tmp_path: Path) -> None:
    artifact = run_intent_to_search_planning_live_eval(
        case_ids=("ready_exact_airports",),
        private_root=tmp_path,
        repository_factory=_RuntimeRepository,
        intent_factory=_RuntimeIntent,
        composer_factory=_RuntimeAdapter,
        selector_factory=_RuntimeAdapter,
        gateway_factory=_RuntimeGateway,
    )

    assert artifact["selected_case_ids"] == ["ready_exact_airports"]
    assert artifact["summary"]["runs"] == 1
    record = artifact["records"][0]
    assert record["intent_behavior_passed"] is True
    assert record["terminal_stage"] == "m2c_handoff"
    assert record["terminal_outcome"] == "planned"
    assert record["trace_reconciliation"] == {
        "attempted_calls": 2,
        "private_trace_calls": 2,
        "within_ceiling": True,
        "reconciled": True,
    }
    assert record["usage"] == {
        "calls": 2,
        "input_tokens": 2,
        "output_tokens": 2,
        "total_tokens": 4,
    }
    assert "PRIVATE_TRACE_SENTINEL" not in json.dumps(artifact)
    trace_files = list(tmp_path.glob("run-*/ready_exact_airports__trial-1.json"))
    assert len(trace_files) == 1
    assert json.dumps(json.loads(trace_files[0].read_text())).count("PRIVATE_TRACE_SENTINEL") == 2
