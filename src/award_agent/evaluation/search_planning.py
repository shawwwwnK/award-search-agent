"""Offline golden evaluation for the current search-strategy compiler."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from award_agent.domain import (
    DateWindow,
    DateWindowPrecision,
    EffectiveRequest,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
)
from award_agent.search_planning import (
    DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
    CatalogKnowledgeRepository,
    DirectGroundingSource,
    GatewayCandidateProposal,
    GatewayDiscoveryInput,
    GatewayOutboundDateContext,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningInput,
    SearchPlanningOutcome,
    discover_gateway_candidates,
    ground_endpoint,
    load_default_planning_market_policy,
    plan_searches,
    planning_market_policy_digest,
)

DEFAULT_SEARCH_PLANNING_CASES = (
    Path(__file__).resolve().parents[3] / "evals" / "search_planning" / "cases_v2.json"
)
DEFAULT_SEARCH_PLANNING_CATALOG = Path(
    "data/search_planning/catalogs/m1a-3cb7981519612945"
)


class _FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestFixture(_FixtureModel):
    raw_text: str = "Offline compiler fixture"
    origins: tuple[str, ...] = Field(min_length=1)
    destinations: tuple[str, ...] = Field(min_length=1)
    departure_start: date
    departure_end: date
    travelers: int = Field(default=1, ge=1)
    repositioning_allowed: bool | None = None

    @model_validator(mode="after")
    def valid_window(self) -> RequestFixture:
        if self.departure_end < self.departure_start:
            raise ValueError("departure_end precedes departure_start")
        return self


class ExpectedFixture(_FixtureModel):
    outcome: SearchPlanningOutcome
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mandatory_pairs: int = Field(ge=0)
    logical_queries: int = Field(ge=0)
    supplemental_strategies: int = Field(ge=0)
    issue_codes: tuple[str, ...] = ()


class GoldenCoverageTag(str, Enum):
    MANDATORY_POLICY_SKIP = "mandatory_policy_skip"
    OPTIONAL_EMPTY = "optional_empty"
    OPTIONAL_FAILURE_DEGRADATION = "optional_failure_degradation"
    CANONICAL_OUTPUT_DETERMINISM = "canonical_output_determinism"
    IDENTITY_AND_STRUCTURAL_LIMIT_RECEIPTS = "identity_and_structural_limit_receipts"


class SearchPlanningGoldenCase(_FixtureModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    gateway_scenario: Literal["policy_skip", "success_empty", "generation_failure"]
    request: RequestFixture
    source_session_id: str = "golden-search-planning"
    source_revision: int = Field(default=1, ge=0)
    canonical_peer_case_id: str | None = None
    expected: ExpectedFixture


class SearchPlanningGoldenCorpus(_FixtureModel):
    schema_version: Literal["search-planning-golden-v4"]
    fixture_grade_only: Literal[True]
    catalog_release_id: str = Field(min_length=1)
    planning_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    market_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_matrix: dict[GoldenCoverageTag, tuple[str, ...]]
    cases: tuple[SearchPlanningGoldenCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_casebook(self) -> SearchPlanningGoldenCorpus:
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            raise ValueError("golden case IDs must be unique")
        if set(self.coverage_matrix) != set(GoldenCoverageTag):
            raise ValueError("golden coverage matrix must declare every required category")
        for tag, case_ids in self.coverage_matrix.items():
            if not case_ids or set(case_ids) - set(ids):
                raise ValueError(f"coverage category {tag.value!r} is empty or names unknown cases")
        for case in self.cases:
            if case.canonical_peer_case_id == case.case_id:
                raise ValueError("golden cases cannot name themselves as canonical peers")
            if case.canonical_peer_case_id is not None and case.canonical_peer_case_id not in ids:
                raise ValueError("golden case names an unknown canonical peer")
        return self


class _Generator:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def propose(self, _: object) -> GatewayCandidateProposal:
        if self.scenario == "generation_failure":
            raise RuntimeError("offline fixture generation failure")
        return GatewayCandidateProposal.model_validate(
            {
                "endpoint_market_assessments": [],
                "origin_access_gateways": [],
                "destination_access_gateways": [],
                "intermediate_hubs": [],
            }
        )


def canonical_sha256(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", round_trip=True)
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode()).hexdigest()


def load_search_planning_golden_corpus(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> SearchPlanningGoldenCorpus:
    return SearchPlanningGoldenCorpus.model_validate_json(path.read_text(encoding="utf-8"))


def preflight_search_planning_golden_corpus(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> SearchPlanningGoldenCorpus:
    corpus = load_search_planning_golden_corpus(path)
    market_policy = load_default_planning_market_policy()
    if corpus.catalog_release_id != DEFAULT_SEARCH_PLANNING_CATALOG.name:
        raise ValueError("golden corpus names a different catalog release")
    if corpus.planning_policy_sha256 != canonical_sha256(PlanningPolicy()):
        raise ValueError("golden corpus planning policy canonical SHA-256 does not match")
    if corpus.market_policy_sha256 != planning_market_policy_digest(market_policy):
        raise ValueError("golden corpus market policy SHA-256 does not match")
    return corpus


def _request(fixture: RequestFixture) -> EffectiveRequest:
    return EffectiveRequest(
        raw_text=fixture.raw_text,
        context=RequestContext(
            reference_date=date(2026, 9, 19), timezone="America/Los_Angeles"
        ),
        travelers=fixture.travelers,
        origins=tuple(
            LocationRef(kind=LocationKind.AIRPORT, value=item, raw_text=item)
            for item in fixture.origins
        ),
        destinations=tuple(
            LocationRef(kind=LocationKind.AIRPORT, value=item, raw_text=item)
            for item in fixture.destinations
        ),
        departure_window=DateWindow(
            start=fixture.departure_start,
            end=fixture.departure_end,
            precision=DateWindowPrecision.WINDOW,
            raw_text="offline golden window",
        ),
        search_modes=(SearchMode.AWARD,),
        repositioning_allowed=fixture.repositioning_allowed,
    )


def _run_case(
    case: SearchPlanningGoldenCase,
    repository: CatalogKnowledgeRepository,
) -> Any:
    request = _request(case.request)
    policy = PlanningPolicy()
    market_policy = load_default_planning_market_policy()
    origin_selections = tuple(
        ground_endpoint(item, "origin", repository, policy).selection for item in request.origins
    )
    destination_selections = tuple(
        ground_endpoint(item, "destination", repository, policy).selection
        for item in request.destinations
    )
    if not all(item is not None for item in (*origin_selections, *destination_selections)):
        raise ValueError("golden fixture endpoint did not ground")
    assert request.departure_window is not None
    discovery = discover_gateway_candidates(
        discovery_input=GatewayDiscoveryInput(
            origin_endpoints=tuple(
                airport
                for selection in origin_selections
                if selection is not None
                for airport in selection.airports
            ),
            destination_endpoints=tuple(
                airport
                for selection in destination_selections
                if selection is not None
                for airport in selection.airports
            ),
            outbound_date=GatewayOutboundDateContext(
                start=request.departure_window.start,
                end=request.departure_window.end,
                timezone=request.context.timezone,
                effective_window_precision=request.departure_window.precision.value,
            ),
        ),
        policy=market_policy,
        repository=repository,
        generator_factory=lambda: _Generator(case.gateway_scenario),
        generator_configuration=DEFAULT_GATEWAY_DISCOVERY_GENERATOR_CONFIGURATION,
    )
    if case.gateway_scenario == "policy_skip" and discovery.outcome.value != "policy_skipped":
        raise ValueError("policy-skip fixture does not classify as one market")
    return plan_searches(
        SearchPlanningInput(
            envelope=PlanningInputEnvelope(
                source=PlanningSource(
                    session_id=case.source_session_id, revision=case.source_revision
                ),
                effective_request=request,
            ),
            endpoint_source=DirectGroundingSource(),
            gateway_discovery_result=discovery,
        ),
        repository=repository,
        policy=policy,
        market_policy=market_policy,
    )


def run_search_planning_golden_eval(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> dict[str, Any]:
    corpus = preflight_search_planning_golden_corpus(path)
    records: list[dict[str, Any]] = []
    digests: dict[str, str] = {}
    with CatalogKnowledgeRepository(DEFAULT_SEARCH_PLANNING_CATALOG) as repository:
        for case in corpus.cases:
            result = _run_case(case, repository)
            digest = canonical_sha256(result)
            digests[case.case_id] = digest
            plan = result.plan
            actual = {
                "outcome": result.outcome,
                "mandatory_pairs": 0 if plan is None else plan.coverage.mandatory_required_pairs,
                "logical_queries": 0 if plan is None else len(plan.logical_queries),
                "supplemental_strategies": 0 if plan is None else len(plan.supplemental_strategies),
                "issue_codes": tuple(str(item.code.value if hasattr(item.code, "value") else item.code) for item in result.issues),
            }
            expected = case.expected
            checks = {
                "outcome": actual["outcome"] is expected.outcome,
                "result_sha256": digest == expected.result_sha256,
                "mandatory_pairs": actual["mandatory_pairs"] == expected.mandatory_pairs,
                "logical_queries": actual["logical_queries"] == expected.logical_queries,
                "supplemental_strategies": actual["supplemental_strategies"] == expected.supplemental_strategies,
                "issue_codes": actual["issue_codes"] == expected.issue_codes,
                "identity_bound": plan is None or bool(plan.identity.compilation_binding_digest),
                "one_structural_limit_receipt": (
                    plan is None or len(plan.structural_limit_receipts) == 1
                ),
            }
            records.append(
                {
                    "case_id": case.case_id,
                    "status": "passed" if all(checks.values()) else "failed",
                    "checks": checks,
                    "result_sha256": digest,
                    "outcome": result.outcome.value,
                }
            )
    for case, record in zip(corpus.cases, records, strict=True):
        if case.canonical_peer_case_id is not None:
            record["checks"]["canonical_peer"] = (
                record["result_sha256"] == digests[case.canonical_peer_case_id]
            )
            record["status"] = "passed" if all(record["checks"].values()) else "failed"
    passed = sum(item["status"] == "passed" for item in records)
    return {
        "schema_version": "search-planning-golden-evaluation-v4",
        "fixture_grade_only": True,
        "corpus_sha256": canonical_sha256(corpus),
        "cases": records,
        "summary": {
            "runs": len(records),
            "passed": passed,
            "failed": len(records) - passed,
            "exact_gate": {"passed": passed == len(records)},
        },
    }


__all__ = [
    "DEFAULT_SEARCH_PLANNING_CASES",
    "GoldenCoverageTag",
    "SearchPlanningGoldenCase",
    "SearchPlanningGoldenCorpus",
    "canonical_sha256",
    "load_search_planning_golden_corpus",
    "preflight_search_planning_golden_corpus",
    "run_search_planning_golden_eval",
]
