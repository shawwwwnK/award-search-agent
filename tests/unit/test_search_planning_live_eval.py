"""Offline tests for the integrated M2A/M2B/M2C live-evaluation harness."""

from __future__ import annotations

import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self, cast

import pytest

from award_agent.clarification.calendar_plan import CalendarDay, LiteralIntervalOperation
from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import CabinClass, LocationKind, MessageSpan, SearchMode
from award_agent.evaluation import search_planning_live
from award_agent.evaluation.search_planning_live import (
    DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK,
    SearchPlanningLiveFixtureError,
    _accepted_relationship_count,
    load_search_planning_live_cases,
    run_search_planning_live_eval,
)
from award_agent.intent.semantic import (
    CalendarOperationKind,
    SemanticFact,
    SemanticFactTarget,
    SemanticIntentProposal,
    SemanticTemporalFact,
    SemanticTemporalTarget,
)
from award_agent.search_planning.airport_selector import (
    AirportSelectionProposal,
    AirportSelectionProposalOutcome,
)
from award_agent.search_planning.compilation_contracts import (
    SearchPlanningOutcome,
    SearchPlanningResult,
    StrategyCompilationIssue,
    StrategyCompilationIssueCode,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
)
from award_agent.search_planning.gateway_generator import GatewayCandidateProposal
from award_agent.search_planning.knowledge import Airport


class _PreflightRepository:
    def __init__(self, _path: Path) -> None:
        self.knowledge_receipt = CatalogKnowledgeReceipt(
            release_id="m1a-3cb7981519612945",
            schema_version="2",
            source_date=date(2026, 9, 16),
            logical_content_sha256=(
                "8066652e581947400badef958916dad9dd641de1a0d423a1a601e0e91bcff1d8"
            ),
            manifest_sha256="1" * 64,
            database_sha256="2" * 64,
            source_bundle_manifest_sha256="3" * 64,
            source_artifacts=(
                CatalogSourceArtifactReceipt(artifact_name="fixture", bytes=1, sha256="4" * 64),
            ),
        )
        labels = {
            "geonames:1861060": "Japan",
            "geonames:2996944": "Lyon",
            "geonames:3017382": "France",
            "geonames:6252001": "United States",
            "geonames:1269750": "India",
        }
        self.entities = {
            entity_id: SimpleNamespace(
                entity_id=entity_id,
                label=label,
                source_ids=(f"source:{entity_id}",),
            )
            for entity_id, label in labels.items()
        }

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def get_entity(self, entity_id: str) -> Any | None:
        return self.entities.get(entity_id)

    def resolve_entities(self, _kind: object, normalized_alias: str) -> tuple[Any, ...]:
        return tuple(
            entity
            for entity in self.entities.values()
            if entity.label.casefold() == normalized_alias
        )

    def lookup_airport_iata(self, iata: str) -> Airport | None:
        if iata not in {"SFO", "NRT"}:
            return None
        return Airport(
            airport_id=f"airport:{iata}",
            iata=iata,
            label=iata,
            country_entity_id="country:test",
            timezone="UTC",
            aliases=(iata,),
            source_ids=(f"source:{iata}",),
        )


class _AmbiguousPreflightRepository(_PreflightRepository):
    def resolve_entities(self, kind: object, normalized_alias: str) -> tuple[Any, ...]:
        resolved = super().resolve_entities(kind, normalized_alias)
        if normalized_alias != "lyon":
            return resolved
        return (
            *resolved,
            SimpleNamespace(
                entity_id="geonames:ambiguous-lyon",
                label="Lyon",
                source_ids=("source:ambiguous-lyon",),
            ),
        )


class _Selector:
    def __init__(self, _config: object) -> None:
        self.calls = 0

    def propose(self, model_input: Any) -> AirportSelectionProposal:
        self.calls += 1
        code = "SFO" if model_input.entity_id == "geonames:6252001" else "NRT"
        return AirportSelectionProposal(
            outcome=AirportSelectionProposalOutcome.PROPOSED, airport_iata_codes=(code,)
        )

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
        return [{"private_selector": "sentinel"}] * self.calls


class _Gateway:
    def __init__(self, _config: object) -> None:
        self.calls = 0

    def propose(self, _model_input: Any) -> GatewayCandidateProposal:
        self.calls += 1
        return GatewayCandidateProposal(
            endpoint_market_assessments=(),
            origin_access_gateways=(),
            destination_access_gateways=(),
            intermediate_hubs=(),
        )

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
        return [{"private_gateway": "sentinel"}] * self.calls


class _Intent:
    def __init__(self, _config: object, *, include_date: bool = True) -> None:
        self.calls = 0
        self.include_date = include_date

    def interpret(self, _input: object) -> SemanticIntentProposal:
        self.calls += 1
        temporal = (
            (
                SemanticTemporalFact(
                    fact_id="departure",
                    target=SemanticTemporalTarget.DEPARTURE,
                    quote="March 10 through March 12, 2027",
                    operation=CalendarOperationKind.LITERAL_INTERVAL,
                    start_year=2027,
                    start_month=3,
                    start_day=10,
                    end_year=2027,
                    end_month=3,
                    end_day=12,
                ),
            )
            if self.include_date
            else ()
        )
        return SemanticIntentProposal(
            facts=(
                SemanticFact(
                    target=SemanticFactTarget.ORIGIN,
                    quote="United States",
                    location_kind=LocationKind.COUNTRY,
                    location_value="United States",
                ),
                SemanticFact(
                    target=SemanticFactTarget.DESTINATION,
                    quote="Japan",
                    location_kind=LocationKind.COUNTRY,
                    location_value="Japan",
                ),
                SemanticFact(target=SemanticFactTarget.TRAVELERS, quote="Two", travelers=2),
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
            temporal_facts=temporal,
        )

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
        return [{"private_intent": "sentinel"}] * self.calls


class _DirectIntent(_Intent):
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
                    quote="NRT",
                    location_kind=LocationKind.AIRPORT,
                    location_value="NRT",
                ),
                SemanticFact(target=SemanticFactTarget.TRAVELERS, quote="One", travelers=1),
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
                    quote="March 10 through March 12, 2027",
                    operation=CalendarOperationKind.LITERAL_INTERVAL,
                    start_year=2027,
                    start_month=3,
                    start_day=10,
                    end_year=2027,
                    end_month=3,
                    end_day=12,
                ),
            ),
        )


class _CashOnlyIntent(_DirectIntent):
    def interpret(self, input: object) -> SemanticIntentProposal:
        proposal = super().interpret(input)
        facts = tuple(
            fact.model_copy(update={"search_mode": SearchMode.CASH, "quote": "cash-only"})
            if fact.target is SemanticFactTarget.SEARCH_MODE
            else fact
            for fact in proposal.facts
        )
        return proposal.model_copy(update={"facts": facts})


class _Composer:
    def __init__(self, _config: object) -> None:
        self.calls = 0

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.calls += 1
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question="What departure window should be used?",
                )
                for requirement in input.requirements
            )
        )

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
        return [{"private_composer": "sentinel"}] * self.calls


class _Clarifier:
    def __init__(self, _config: object) -> None:
        self.calls = 0

    def interpret(self, input: Any) -> ClarificationAnswerInterpretation:
        self.calls += 1
        quote = "March 10 through March 12, 2027"
        start = input.text.index(quote)
        return ClarificationAnswerInterpretation(
            facts=(
                ClarificationSemanticFact(
                    fact_id="departure",
                    span=MessageSpan(
                        message_id=input.message_id,
                        start=start,
                        end=start + len(quote),
                        text=quote,
                    ),
                    target=SemanticTarget.DEPARTURE_WINDOW,
                    calendar_operation=LiteralIntervalOperation(
                        start=CalendarDay(year=2027, month=3, day=10),
                        end=CalendarDay(year=2027, month=3, day=12),
                    ),
                ),
            )
        )

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
        return [{"private_clarifier": "sentinel"}] * self.calls


def test_casebook_has_reviewed_multi_milestone_call_bound() -> None:
    cases = load_search_planning_live_cases()
    assert DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK == Path(
        "evals/search_planning_live/casebook-v2.yaml"
    )
    assert [case["id"] for case in cases] == [
        "direct_sfo_to_nrt",
        "united_states_to_japan",
        "lyon_city_to_france",
        "united_states_to_india",
        "united_states_to_japan_clarified_date",
        "cash_only_scope_stop",
    ]


def test_casebook_validation_accepts_a_finite_window_longer_than_31_days(
    tmp_path: Path,
) -> None:
    casebook = tmp_path / "long-window.yaml"
    casebook.write_text(
        DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK.read_text().replace(
            "end: 2027-03-12", "end: 2027-05-12", 1
        )
    )

    cases = load_search_planning_live_cases(casebook)

    assert cases[0]["departure"]["start"] == date(2027, 3, 10)
    assert cases[0]["departure"]["end"] == date(2027, 5, 12)


def test_preflight_validates_full_call_plan_without_constructing_adapters() -> None:
    def forbidden(_config: object) -> Any:
        raise AssertionError("preflight constructed a model adapter")

    artifact = run_search_planning_live_eval(
        preflight_only=True,
        trials=2,
        selector_factory=forbidden,
        gateway_factory=forbidden,
        repository_factory=_PreflightRepository,
    )
    assert artifact["call_plan"] == {
        "full_casebook_per_trial": 28,
        "selected_total": 56,
        "maximum_total": 56,
    }
    assert artifact["summary"]["preflight_passed"] is True
    assert artifact["summary"]["attempted_calls"] == 0
    assert artifact["summary"]["mechanically_completed"] is False


def test_ambiguous_casebook_entity_fails_before_adapter_construction() -> None:
    def forbidden(_config: object) -> Any:
        raise AssertionError("preflight constructed a model adapter")

    with pytest.raises(SearchPlanningLiveFixtureError, match="not one unambiguous"):
        run_search_planning_live_eval(
            preflight_only=True,
            intent_factory=forbidden,
            composer_factory=forbidden,
            clarification_factory=forbidden,
            selector_factory=forbidden,
            gateway_factory=forbidden,
            repository_factory=_AmbiguousPreflightRepository,
        )


def test_fake_adapters_run_m2a_m2b_m2c_and_keep_raw_io_private(tmp_path: Path) -> None:
    artifact = run_search_planning_live_eval(
        trials=1,
        case_ids=("united_states_to_japan",),
        trace_dir=tmp_path,
        intent_factory=_Intent,
        selector_factory=_Selector,
        gateway_factory=_Gateway,
    )
    assert artifact["run_kind"] == "smoke_partial"
    assert artifact["summary"]["planned_calls"] == 5
    assert artifact["summary"]["attempted_calls"] == 4
    assert artifact["summary"]["mechanically_completed"] is False
    record = artifact["records"][0]
    assert record["status"] == "completed"
    assert record["same_record_replay"]["equal"] is True
    assert record["same_record_replay"]["source_bundle_reloaded"] is True
    assert record["handoff"]["status"] == "current"
    assert record["handoff"]["executable"] is True
    assert len(record["m2a"]["record_bindings"]) == 2
    assert "capability" not in artifact["identities"]
    assert set(artifact["compiler_policy"]).isdisjoint(
        {
            "max_supplemental_relationship_bundles",
            "max_unique_logical_queries",
            "max_query_date_days",
        }
    )
    assert record["m2c"]["compiled_relationships"] == record["m2c"][
        "accepted_relationships"
    ]
    assert "admitted_relationships" not in record["m2c"]
    assert "omitted_budget_relationships" not in record["m2c"]
    assert "query_date_days" not in record["m2c"]
    public_json = json.dumps(artifact)
    assert "private_selector" not in public_json
    assert "private_gateway" not in public_json
    assert "private_intent" not in public_json
    private_trace = Path(record["private_trace"]["path"]).read_text()
    assert "private_selector" in private_trace
    assert "private_gateway" in private_trace
    assert "private_intent" in private_trace


def test_offline_v2_recompile_evidence_preserves_history_and_compiles_every_relationship() -> None:
    evidence_path = Path(
        "evals/search_planning_live/recompile/"
        "2026-09-20-united-states-japan-clarified-trial-1-m2c-v2.json"
    )
    evidence = json.loads(evidence_path.read_text())
    historical = Path(evidence["source"]["historical_public_artifact"])

    assert sha256(historical.read_bytes()).hexdigest() == evidence["source"][
        "historical_public_artifact_sha256"
    ]
    assert evidence["execution"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "gateway_replay_equal": True,
        "compile_replay_equal": True,
        "typed_plan_reload_equal": True,
        "handoff_status": "current",
        "handoff_executable": True,
    }
    assert evidence["compiler"]["provider_capability_bound"] is False
    result = evidence["result"]
    assert result["outcome"] == "planned"
    assert result["plan_digest"] == (
        "6b6313e7d39a6fa53dc7ec84dc9d114a0ec1e3efc80c06342bc69f8b6293f840"
    )
    assert result["compilation_binding_digest"] == (
        "fa91756cb1467dead136501721de76eaa583571f031faec03a6a705ba3f4cbcf"
    )
    assert result["accepted_relationship_ledger_digest"] == (
        "a0891427d6f81dacac2f0fbd01b2fc49cc0ffa9f668fc133ec8cde7b12b40c78"
    )
    assert result["relationship_disposition_digest"] == (
        "97f2425cbdd273628342734bfb2e3c9467a6bc966fef8a83a607cc3350504e1f"
    )
    assert result["mandatory_required_pairs"] == result["mandatory_covered_pairs"] == 40
    assert result["accepted_relationships"] == result["compiled_relationships"] == 52
    assert result["logical_queries"] == 57
    assert result["supplemental_strategies"] == 52
    assert result["strategy_query_uses"] == 68
    assert result["relationship_dispositions"] == {"compiled": 52}
    assert "omitted_budget_relationships" not in result

    historical_hashes = {
        "2026-09-19-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v1-2-trials.json": (
            "c5303db7a8c6e6f9cb2eb958c548841b08d70c70011fef5dc005cd64a4daa633"
        ),
        "2026-09-19-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v1-lyon-fix-2-trials.json": (
            "4f4956a2f6cd3acfd3fee93c93bb803962fb8a68ccacd73de805eb66aa7c821d"
        ),
    }
    baseline = Path("evals/search_planning_live/baseline")
    assert {
        name: sha256((baseline / name).read_bytes()).hexdigest()
        for name in historical_hashes
    } == historical_hashes


def test_upstream_blocked_case_never_counts_as_completed(tmp_path: Path) -> None:
    artifact = run_search_planning_live_eval(
        trials=1,
        case_ids=("united_states_to_japan",),
        trace_dir=tmp_path,
        intent_factory=lambda config: _Intent(config, include_date=False),
        selector_factory=_Selector,
        gateway_factory=_Gateway,
    )
    assert artifact["records"][0]["status"] == "upstream_blocked"
    assert artifact["summary"]["completed"] == 0
    assert artifact["summary"]["errors"] == 1
    assert artifact["summary"]["mechanically_completed"] is False


def test_no_plan_result_is_an_error_not_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    failed = SearchPlanningResult(
        outcome=SearchPlanningOutcome.EVIDENCE_FAILURE,
        issues=(
            StrategyCompilationIssue(
                code=StrategyCompilationIssueCode.COMPILER_CONTRACT_FAILURE,
                stage="compilation",
                severity="evidence_failure",
                message="offline fixture compilation failure",
            ),
        ),
    )
    monkeypatch.setattr(
        search_planning_live,
        "plan_searches",
        lambda *_args, **_kwargs: failed,
    )
    artifact = run_search_planning_live_eval(
        trials=1,
        case_ids=("direct_sfo_to_nrt",),
        trace_dir=tmp_path,
        intent_factory=_DirectIntent,
        gateway_factory=_Gateway,
    )
    assert artifact["records"][0]["status"] == "error"
    assert artifact["summary"]["completed"] == 0
    assert artifact["summary"]["mechanically_completed"] is False


def test_predefined_clarification_reaches_ready_before_planning(tmp_path: Path) -> None:
    artifact = run_search_planning_live_eval(
        trials=1,
        case_ids=("united_states_to_japan_clarified_date",),
        trace_dir=tmp_path,
        intent_factory=lambda config: _Intent(config, include_date=False),
        composer_factory=_Composer,
        clarification_factory=_Clarifier,
        selector_factory=_Selector,
        gateway_factory=_Gateway,
    )
    record = artifact["records"][0]
    assert record["status"] == "completed"
    assert record["upstream"] == {
        "status": "ready",
        "revision": 1,
        "clarification_turns": 1,
    }
    assert record["handoff"]["status"] == "current"


def test_expected_cash_only_scope_stop_completes_without_downstream_calls(
    tmp_path: Path,
) -> None:
    def forbidden(_config: object) -> Any:
        raise AssertionError("blocked trajectory constructed a downstream adapter")

    artifact = run_search_planning_live_eval(
        trials=1,
        case_ids=("cash_only_scope_stop",),
        trace_dir=tmp_path,
        intent_factory=_CashOnlyIntent,
        selector_factory=forbidden,
        gateway_factory=forbidden,
    )
    record = artifact["records"][0]
    assert record["status"] == "completed"
    assert record["trajectory_outcome"] == "upstream_blocked"
    assert record["trajectory_matches"] is True
    assert "m2a" not in record and "m2b" not in record and "m2c" not in record


def test_relationship_metric_counts_products_not_candidates() -> None:
    gateway = SimpleNamespace(
        accepted_origin_access_gateways=(
            SimpleNamespace(
                supported_original_origin_iata_codes=("SFO", "LAX"),
                applicable_original_destination_iata_codes=("NRT", "HND", "KIX"),
            ),
        ),
        accepted_destination_access_gateways=(
            SimpleNamespace(
                supported_original_destination_iata_codes=("NRT", "HND"),
                applicable_original_origin_iata_codes=("SFO",),
            ),
        ),
        accepted_intermediate_hubs=(
            SimpleNamespace(
                scopes=(
                    SimpleNamespace(
                        expanded_original_origin_iata_codes=("SFO", "LAX"),
                        expanded_original_destination_iata_codes=("NRT", "HND"),
                    ),
                )
            ),
        ),
    )
    assert _accepted_relationship_count(cast(Any, gateway)) == 12


def test_preflight_rejects_call_bound_drift_before_adapter_construction(
    tmp_path: Path,
) -> None:
    payload = DEFAULT_SEARCH_PLANNING_LIVE_CASEBOOK.read_text().replace(
        "max_calls_per_trial: 28", "max_calls_per_trial: 27"
    )
    casebook = tmp_path / "casebook.yaml"
    casebook.write_text(payload)

    def forbidden(_config: object) -> Any:
        raise AssertionError("preflight constructed an adapter")

    with pytest.raises(SearchPlanningLiveFixtureError, match="call plan exceeds"):
        run_search_planning_live_eval(
            casebook_path=casebook,
            preflight_only=True,
            intent_factory=forbidden,
            composer_factory=forbidden,
            clarification_factory=forbidden,
            selector_factory=forbidden,
            gateway_factory=forbidden,
            repository_factory=_PreflightRepository,
        )
