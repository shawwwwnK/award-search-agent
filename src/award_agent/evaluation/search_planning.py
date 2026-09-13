"""Offline golden evaluation for the deterministic search-planning boundary.

The evaluator deliberately builds only fixture-grade input records.  It never
reads a provider credential, calls a provider, or treats a golden result as an
availability observation.  Cases use compact JSON surface data and assert a
canonical digest of the complete typed planning result, alongside a few
human-reviewable semantic assertions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from award_agent.domain import (
    CabinClass,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    InitialSnapshotSource,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
    UnknownField,
    UnknownReason,
)
from award_agent.search_planning import (
    KnowledgeSnapshot,
    PlanningInputEnvelope,
    PlanningPolicy,
    PlanningSource,
    SearchPlanningOutcome,
    load_default_cached_search_capability,
    load_default_knowledge_snapshot,
    plan_searches,
    verify_capability_source_artifacts,
)

DEFAULT_SEARCH_PLANNING_CASES = (
    Path(__file__).resolve().parents[3] / "evals" / "search_planning" / "cases_v1.json"
)


class _FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocationFixture(_FixtureModel):
    kind: LocationKind
    value: str = Field(min_length=1)
    raw_text: str | None = None


class RequestFixture(_FixtureModel):
    raw_text: str = "Offline planning fixture"
    reference_date: date = date(2026, 9, 12)
    timezone: str = "America/Los_Angeles"
    travelers: int | None = Field(default=2, ge=1)
    origins: tuple[LocationFixture, ...] = ()
    destinations: tuple[LocationFixture, ...] = ()
    departure_start: date | None = None
    departure_end: date | None = None
    cabins: tuple[CabinClass, ...] = ()
    search_modes: tuple[SearchMode, ...] = (SearchMode.AWARD,)
    repositioning_allowed: bool | None = None
    hard_constraints: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def dates_are_complete(self) -> RequestFixture:
        if (self.departure_start is None) != (self.departure_end is None):
            raise ValueError("departure_start and departure_end must be supplied together")
        if (
            self.departure_start is not None
            and self.departure_end is not None
            and self.departure_end < self.departure_start
        ):
            raise ValueError("departure_end precedes departure_start")
        return self


class ExpectedFixture(_FixtureModel):
    outcome: SearchPlanningOutcome
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    endpoint_pairs: tuple[str, ...] = ()
    selected_origin_iata: tuple[str, ...] = ()
    selected_destination_iata: tuple[str, ...] = ()
    issue_codes: tuple[str, ...] = ()
    path_count: int | None = Field(default=None, ge=0)
    deferred_constraint_count: int | None = Field(default=None, ge=0)
    manual_cash_template_count: int | None = Field(default=None, ge=0)
    expected_repositioning_receipt: bool | None = None
    no_all_cash_pattern: bool = False
    endpoint_probe_count: int | None = Field(default=None, ge=0)
    budget_receipt_count: int | None = Field(default=None, ge=0)
    path_candidate_budget_observed: int | None = Field(default=None, ge=0)
    path_candidate_budget_limit: int | None = Field(default=None, ge=0)


class GoldenCoverageTag(str, Enum):
    """End-to-end behaviors required of the small fixture-grade corpus."""

    JAPAN_AIRPORT_GROUP = "japan_airport_group"
    NEW_YORK_CITY_AIRPORT_GROUP = "new_york_city_airport_group"
    EXPLICIT_AIRPORT_PRESERVATION = "explicit_airport_preservation"
    COUNTRY_DESTINATION_NO_ONWARD = "country_destination_no_onward"
    UNRESOLVED_AND_AMBIGUOUS_LOCATION = "unresolved_and_ambiguous_location"
    KNOWLEDGE_EVIDENCE_FAILURE = "knowledge_evidence_failure"
    DIRECTIONAL_PATH_AND_MIXED_PAYMENT = "directional_path_and_mixed_payment"
    DEFERRED_CONSTRAINT_AND_OPTIONAL_UNKNOWN = "deferred_constraint_and_optional_unknown"
    TEMPORAL_CASH_FIRST_BOUNDARY = "temporal_cash_first_boundary"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    OPTIONAL_PATH_BUDGET_DEGRADATION = "optional_path_budget_degradation"
    CANONICAL_OUTPUT_DETERMINISM = "canonical_output_determinism"


class SearchPlanningGoldenCase(_FixtureModel):
    case_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    snapshot_variant: Literal[
        "seed",
        "seed_reordered",
        "synthetic_path",
        "stale_seed",
        "without_japan_policy",
        "ambiguous_japan",
    ] = "seed"
    request: RequestFixture
    policy: dict[str, Any] = Field(default_factory=dict)
    source_session_id: str = "golden-session"
    source_revision: int = Field(default=1, ge=0)
    canonical_peer_case_id: str | None = None
    expected: ExpectedFixture


class SearchPlanningGoldenCorpus(_FixtureModel):
    schema_version: Literal["search-planning-golden-v1"]
    fixture_grade_only: Literal[True]
    knowledge_snapshot_id: str = Field(min_length=1)
    knowledge_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    capability_id: Literal["seats_aero.cached_search.v1"]
    capability_version: str = Field(min_length=1)
    capability_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    default_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    coverage_matrix: dict[GoldenCoverageTag, tuple[str, ...]]
    cases: tuple[SearchPlanningGoldenCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids_and_peers(self) -> SearchPlanningGoldenCorpus:
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            raise ValueError("golden case IDs must be unique")
        unknown_peers = {
            case.canonical_peer_case_id
            for case in self.cases
            if case.canonical_peer_case_id is not None
        } - set(ids)
        if unknown_peers:
            raise ValueError(f"golden cases name unknown canonical peers: {sorted(unknown_peers)}")
        self_peers = tuple(
            case.case_id
            for case in self.cases
            if case.canonical_peer_case_id == case.case_id
        )
        if self_peers:
            raise ValueError(
                f"golden cases cannot name themselves as canonical peers: {list(self_peers)}"
            )
        required_tags = frozenset(GoldenCoverageTag)
        supplied_tags = frozenset(self.coverage_matrix)
        if supplied_tags != required_tags:
            missing = sorted(tag.value for tag in required_tags - supplied_tags)
            unexpected = sorted(tag.value for tag in supplied_tags - required_tags)
            raise ValueError(
                "golden coverage matrix must declare every required category"
                f" (missing={missing}, unexpected={unexpected})"
            )
        for tag, case_ids in self.coverage_matrix.items():
            if not case_ids:
                raise ValueError(f"golden coverage category {tag.value!r} cannot be empty")
            if len(case_ids) != len(set(case_ids)):
                raise ValueError(
                    f"golden coverage category {tag.value!r} cannot repeat case IDs"
                )
            unknown_case_ids = sorted(set(case_ids) - set(ids))
            if unknown_case_ids:
                raise ValueError(
                    f"golden coverage category {tag.value!r} names unknown cases: {unknown_case_ids}"
                )
        return self


def canonical_sha256(value: object) -> str:
    """Fingerprint a typed evaluator result with a stable JSON encoding."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", round_trip=True)
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def load_search_planning_golden_corpus(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> SearchPlanningGoldenCorpus:
    with path.open(encoding="utf-8") as handle:
        return SearchPlanningGoldenCorpus.model_validate(json.load(handle))


def preflight_search_planning_golden_corpus(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> SearchPlanningGoldenCorpus:
    """Strictly validate the corpus and its declared fixture identities."""

    corpus = load_search_planning_golden_corpus(path)
    snapshot = load_default_knowledge_snapshot()
    capability = load_default_cached_search_capability()
    if corpus.knowledge_snapshot_id != snapshot.metadata.snapshot_id:
        raise ValueError("golden corpus names a different default knowledge snapshot")
    if corpus.capability_id != capability.capability_id:
        raise ValueError("golden corpus names a different default capability record")
    if corpus.knowledge_snapshot_sha256 != canonical_sha256(snapshot):
        raise ValueError("golden corpus knowledge snapshot canonical SHA-256 does not match")
    if corpus.capability_version != capability.capability_version:
        raise ValueError("golden corpus names a different default capability version")
    if corpus.capability_sha256 != canonical_sha256(capability):
        raise ValueError("golden corpus capability canonical SHA-256 does not match")
    if corpus.default_policy_sha256 != canonical_sha256(PlanningPolicy()):
        raise ValueError("golden corpus default policy canonical SHA-256 does not match")
    verify_capability_source_artifacts(capability)
    return corpus


def _request_from_fixture(fixture: RequestFixture) -> EffectiveRequest:
    field_values: list[EffectiveField] = [
        EffectiveField.ORIGIN,
        EffectiveField.DESTINATION,
        EffectiveField.TRAVELERS,
        EffectiveField.DEPARTURE,
        EffectiveField.SEARCH_MODE,
    ]
    if fixture.cabins:
        field_values.append(EffectiveField.CABIN)
    if fixture.hard_constraints:
        field_values.append(EffectiveField.HARD_CONSTRAINTS)
    if fixture.repositioning_allowed is not None:
        field_values.append(EffectiveField.REPOSITIONING)
    provenance = tuple(
        FieldProvenance(field=field, source=InitialSnapshotSource(field=field))
        for field in sorted(set(field_values), key=lambda item: item.value)
    )
    unknowns = tuple(
        UnknownField(field=field, reason=UnknownReason.MISSING, detail=f"fixture unknown: {field}")
        for field in fixture.unknown_fields
    )
    departure_window = (
        None
        if fixture.departure_start is None
        else DateWindow(
            start=fixture.departure_start,
            # ``RequestFixture``'s model validator guarantees paired dates;
            # the assertion also gives static analysis that invariant.
            end=_fixture_departure_end(fixture),
            precision=DateWindowPrecision.WINDOW,
            raw_text="fixture bounded departure window",
        )
    )
    return EffectiveRequest(
        raw_text=fixture.raw_text,
        context=RequestContext(reference_date=fixture.reference_date, timezone=fixture.timezone),
        travelers=fixture.travelers,
        origins=tuple(
            LocationRef(kind=item.kind, value=item.value, raw_text=item.raw_text or item.value)
            for item in fixture.origins
        ),
        destinations=tuple(
            LocationRef(kind=item.kind, value=item.value, raw_text=item.raw_text or item.value)
            for item in fixture.destinations
        ),
        departure_window=departure_window,
        cabins=fixture.cabins,
        search_modes=fixture.search_modes,
        repositioning_allowed=fixture.repositioning_allowed,
        hard_constraints=fixture.hard_constraints,
        unknowns=unknowns,
        field_provenance=provenance,
    )


def _fixture_departure_end(fixture: RequestFixture) -> date:
    if fixture.departure_end is None:  # pragma: no cover - guarded by model validation
        raise ValueError("fixture departure_end is required when departure_start is supplied")
    return fixture.departure_end


def _snapshot_variant(name: str) -> KnowledgeSnapshot:
    document = load_default_knowledge_snapshot().model_dump(mode="json", round_trip=True)
    if name == "seed":
        return KnowledgeSnapshot.model_validate(document)
    if name == "seed_reordered":
        for key in (
            "sources",
            "entities",
            "airports",
            "relations",
            "selection_policies",
            "route_edges",
        ):
            document[key] = list(reversed(document[key]))
        return KnowledgeSnapshot.model_validate(document)
    if name == "synthetic_path":
        document["sources"].append(
            {
                "source_id": "golden-synthetic-topology",
                "title": "Golden synthetic topology fixture",
                "url": "https://example.test/golden-synthetic-topology",
                "license_note": "Synthetic test fixture only.",
                "verified_on": "2026-09-12",
                "version_or_capture_id": "golden-v1",
                "verification_scope": "Offline golden evaluation only.",
            }
        )
        document["route_edges"] = [
            {
                "edge_id": "golden:sfo-jfk",
                "origin_airport_id": "airport:sfo",
                "destination_airport_id": "airport:jfk",
                "evidence_kind": "synthetic_test_fixture",
                "source_ids": ["golden-synthetic-topology"],
            },
            {
                "edge_id": "golden:jfk-hnd",
                "origin_airport_id": "airport:jfk",
                "destination_airport_id": "airport:hnd",
                "evidence_kind": "synthetic_test_fixture",
                "source_ids": ["golden-synthetic-topology"],
            },
        ]
        return KnowledgeSnapshot.model_validate(document)
    if name == "stale_seed":
        document["metadata"]["verification_date"] = "2025-01-01"
        for source in document["sources"]:
            source["verified_on"] = "2025-01-01"
        return KnowledgeSnapshot.model_validate(document)
    if name == "without_japan_policy":
        document["selection_policies"] = [
            item for item in document["selection_policies"] if item["entity_id"] != "country:jp"
        ]
        return KnowledgeSnapshot.model_validate(document)
    if name == "ambiguous_japan":
        document["entities"].append(
            {
                "entity_id": "country:jp-ambiguous-fixture",
                "kind": "country",
                "label": "Japan fixture ambiguity",
                "aliases": ["Japan"],
                "source_ids": ["japan-mlit-airports"],
            }
        )
        return KnowledgeSnapshot.model_validate(document)
    raise ValueError(f"unknown snapshot fixture variant: {name}")


def _actual_summary(result: Any) -> dict[str, Any]:
    plan = result.plan
    if plan is None:
        return {
            "endpoint_pairs": (),
            "selected_origin_iata": (),
            "selected_destination_iata": (),
            "issue_codes": tuple(issue.code.value for issue in result.issues),
            "path_count": None,
            "deferred_constraint_count": None,
            "manual_cash_template_count": None,
            "repositioning_receipt": None,
            "no_all_cash_pattern": True,
            "endpoint_probe_count": None,
            "budget_receipt_count": None,
            "path_candidate_budget_observed": None,
            "path_candidate_budget_limit": None,
        }
    endpoints = tuple(
        f"{probe.origin_endpoint.airport_iata}->{probe.destination_endpoint.airport_iata}"
        for probe in plan.endpoint_probes
    )
    all_modes = tuple(
        mode.value
        for pattern in plan.payment_patterns
        for mode in pattern.component_payment_modes
    )
    return {
        "endpoint_pairs": endpoints,
        "selected_origin_iata": tuple(
            airport.airport_iata
            for result_item in plan.location_results
            if result_item.role == "origin" and result_item.selection is not None
            for airport in result_item.selection.airports
        ),
        "selected_destination_iata": tuple(
            airport.airport_iata
            for result_item in plan.location_results
            if result_item.role == "destination" and result_item.selection is not None
            for airport in result_item.selection.airports
        ),
        "issue_codes": (),
        "path_count": len(plan.explicit_path_hypotheses),
        "deferred_constraint_count": len(plan.deferred_constraints),
        "manual_cash_template_count": len(plan.manual_cash_check_templates),
        "repositioning_receipt": plan.repositioning_policy_receipt.decision
        == "enabled_not_consumed_v1",
        "no_all_cash_pattern": "manual_cash" not in all_modes or all(
            any(mode.value == "award" for mode in pattern.component_payment_modes)
            for pattern in plan.payment_patterns
        ),
        "endpoint_probe_count": len(plan.endpoint_probes),
        "budget_receipt_count": len(plan.budget_receipts),
        "path_candidate_budget_observed": next(
            receipt.observed
            for receipt in plan.budget_receipts
            if receipt.kind.value == "path_candidate_count"
        ),
        "path_candidate_budget_limit": next(
            receipt.limit
            for receipt in plan.budget_receipts
            if receipt.kind.value == "path_candidate_count"
        ),
    }


def run_search_planning_golden_eval(
    path: Path = DEFAULT_SEARCH_PLANNING_CASES,
) -> dict[str, Any]:
    """Run fixture-only golden cases and return a deterministic public artifact."""

    corpus = preflight_search_planning_golden_corpus(path)
    snapshot = load_default_knowledge_snapshot()
    capability = load_default_cached_search_capability()
    records: list[dict[str, Any]] = []
    digest_by_case: dict[str, str] = {}
    for case in corpus.cases:
        request = _request_from_fixture(case.request)
        result = plan_searches(
            PlanningInputEnvelope(
                source=PlanningSource(
                    session_id=case.source_session_id,
                    revision=case.source_revision,
                ),
                effective_request=request,
            ),
            policy=PlanningPolicy.model_validate(case.policy),
            snapshot=_snapshot_variant(case.snapshot_variant),
            capability=capability,
        )
        actual = _actual_summary(result)
        digest = canonical_sha256(result)
        digest_by_case[case.case_id] = digest
        expected = case.expected
        checks = {
            "outcome": result.outcome is expected.outcome,
            "result_sha256": digest == expected.result_sha256,
            "endpoint_pairs": actual["endpoint_pairs"] == expected.endpoint_pairs,
            "selected_origin_iata": actual["selected_origin_iata"] == expected.selected_origin_iata,
            "selected_destination_iata": actual["selected_destination_iata"]
            == expected.selected_destination_iata,
            "issue_codes": actual["issue_codes"] == expected.issue_codes,
        }
        optional_checks = {
            "path_count": expected.path_count,
            "deferred_constraint_count": expected.deferred_constraint_count,
            "manual_cash_template_count": expected.manual_cash_template_count,
            "repositioning_receipt": expected.expected_repositioning_receipt,
            "endpoint_probe_count": expected.endpoint_probe_count,
            "budget_receipt_count": expected.budget_receipt_count,
            "path_candidate_budget_observed": expected.path_candidate_budget_observed,
            "path_candidate_budget_limit": expected.path_candidate_budget_limit,
        }
        for name, expected_value in optional_checks.items():
            if expected_value is not None:
                checks[name] = actual[name] == expected_value
        if expected.no_all_cash_pattern:
            checks["no_all_cash_pattern"] = bool(actual["no_all_cash_pattern"])
        records.append(
            {
                "case_id": case.case_id,
                "status": "passed" if all(checks.values()) else "failed",
                "checks": checks,
                "result_sha256": digest,
                "outcome": result.outcome.value,
            }
        )
    for record, case in zip(records, corpus.cases, strict=True):
        if case.canonical_peer_case_id is not None:
            record["checks"]["canonical_peer"] = (
                record["result_sha256"] == digest_by_case[case.canonical_peer_case_id]
            )
            record["status"] = "passed" if all(record["checks"].values()) else "failed"
    passed = sum(record["status"] == "passed" for record in records)
    return {
        "schema_version": "search-planning-golden-evaluation-v1",
        "fixture_grade_only": True,
        "corpus_sha256": canonical_sha256(corpus),
        "input_identities": {
            "knowledge_snapshot": {
                "snapshot_id": snapshot.metadata.snapshot_id,
                "canonical_sha256": canonical_sha256(snapshot),
            },
            "capability": {
                "capability_id": capability.capability_id,
                "capability_version": capability.capability_version,
                "canonical_sha256": canonical_sha256(capability),
                "source_artifacts": [
                    {
                        "source_id": source.source_id,
                        "local_path": source.local_path,
                        "content_sha256": source.content_sha256,
                    }
                    for source in capability.sources
                ],
            },
            "default_policy": {
                "policy_version": PlanningPolicy().policy_version,
                "canonical_sha256": canonical_sha256(PlanningPolicy()),
            },
        },
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
