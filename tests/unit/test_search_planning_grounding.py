"""Focused tests for the first grounded-endpoint planning increment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from award_agent.domain import LocationKind, LocationRef
from award_agent.search_planning import (
    AirportSelectionKind,
    FreshnessClass,
    KnowledgeRepository,
    KnowledgeSnapshot,
    LocationResolutionStatus,
    PlanningIssueCode,
    PlanningPolicy,
    default_snapshot_path,
    ground_endpoint,
    load_default_knowledge_snapshot,
)


def location(kind: LocationKind, value: str, raw_text: str | None = None) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=raw_text or value)


@pytest.fixture
def repository() -> KnowledgeRepository:
    return KnowledgeRepository(load_default_knowledge_snapshot())


def test_explicit_preserved_iata_is_a_singleton_with_airport_evidence(
    repository: KnowledgeRepository,
) -> None:
    result = ground_endpoint(
        location(LocationKind.AIRPORT, "SFO"), "origin", repository, PlanningPolicy()
    )

    assert result.selection is not None
    assert result.selection.kind is AirportSelectionKind.EXPLICIT_IATA
    assert [airport.airport_iata for airport in result.selection.airports] == ["SFO"]
    selected = result.selection.airports[0]
    assert selected.relation_id is None
    assert selected.selection_policy_id is None
    assert selected.airport_evidence_source_ids
    assert result.snapshot_id == "search-planning-seed-v1"
    assert result.freshness is FreshnessClass.CURRENT


@pytest.mark.parametrize("raw_text", ["SFO", " sfo\t"])
def test_explicit_iata_requires_raw_identifier_equal_to_value_case_insensitively(
    repository: KnowledgeRepository, raw_text: str
) -> None:
    result = ground_endpoint(
        location(LocationKind.AIRPORT, "SFO", raw_text), "origin", repository, PlanningPolicy()
    )

    assert result.selection is not None
    assert result.selection.kind is AirportSelectionKind.EXPLICIT_IATA


def test_model_proposed_iata_normalization_cannot_bypass_named_alias_resolution(
    repository: KnowledgeRepository,
) -> None:
    result = ground_endpoint(
        location(LocationKind.AIRPORT, "SFO", "San Francisco"),
        "origin",
        repository,
        PlanningPolicy(),
    )

    assert result.selection is not None
    assert result.selection.kind is AirportSelectionKind.NAMED_AIRPORT


def test_japan_uses_factual_relations_and_separate_policy(repository: KnowledgeRepository) -> None:
    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"), "destination", repository, PlanningPolicy()
    )

    assert result.selection is not None
    assert result.selection.kind is AirportSelectionKind.GEOGRAPHIC_GROUP
    assert [airport.airport_iata for airport in result.selection.airports] == ["HND", "NRT", "KIX"]
    assert all(airport.relation_id for airport in result.selection.airports)
    assert all(
        airport.selection_policy_id == "policy:jp-representative-gateways-v1"
        for airport in result.selection.airports
    )


def test_nyc_alias_uses_serves_city_relations(repository: KnowledgeRepository) -> None:
    result = ground_endpoint(
        location(LocationKind.CITY, "nyc"), "origin", repository, PlanningPolicy()
    )

    assert result.selection is not None
    assert [airport.airport_iata for airport in result.selection.airports] == ["JFK", "EWR", "LGA"]
    assert all(
        airport.relation_id and "serves-city" in airport.relation_id
        for airport in result.selection.airports
    )


def test_named_airport_is_resolved_narrowly_without_group_expansion(
    repository: KnowledgeRepository,
) -> None:
    result = ground_endpoint(
        location(LocationKind.AIRPORT, "San Francisco International Airport", "SFO airport"),
        "origin",
        repository,
        PlanningPolicy(),
    )

    assert result.selection is not None
    assert result.selection.kind is AirportSelectionKind.NAMED_AIRPORT
    assert [airport.airport_iata for airport in result.selection.airports] == ["SFO"]


def test_unapproved_deaccenting_does_not_match_an_alias() -> None:
    document = _read_snapshot()
    document["airports"][0]["aliases"].append("São Fixture Airport")
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(
        location(LocationKind.AIRPORT, "Sao Fixture Airport"),
        "origin",
        repository,
        PlanningPolicy(),
    )

    assert result.selection is None
    assert result.resolution.status is LocationResolutionStatus.UNRESOLVED


@pytest.mark.parametrize(
    ("candidate", "kind", "expected_status", "expected_issue"),
    [
        (
            "Atlantis",
            LocationKind.CITY,
            LocationResolutionStatus.UNRESOLVED,
            PlanningIssueCode.UNRESOLVED_LOCATION,
        ),
        (
            "Japan",
            LocationKind.CITY,
            LocationResolutionStatus.KIND_MISMATCH,
            PlanningIssueCode.LOCATION_KIND_MISMATCH,
        ),
        (
            "ZZZ",
            LocationKind.AIRPORT,
            LocationResolutionStatus.EVIDENCE_FAILURE,
            PlanningIssueCode.MISSING_AIRPORT_EVIDENCE,
        ),
    ],
)
def test_unresolved_kind_mismatch_and_missing_airport_are_typed(
    repository: KnowledgeRepository,
    candidate: str,
    kind: LocationKind,
    expected_status: LocationResolutionStatus,
    expected_issue: PlanningIssueCode,
) -> None:
    result = ground_endpoint(location(kind, candidate), "destination", repository, PlanningPolicy())

    assert result.selection is None
    assert result.resolution.status is expected_status
    assert [issue.code for issue in result.issues] == [expected_issue]


def test_resolved_geography_without_policy_is_not_silently_expanded(
    repository: KnowledgeRepository,
) -> None:
    result = ground_endpoint(
        location(LocationKind.COUNTRY, "USA"), "origin", repository, PlanningPolicy()
    )

    assert result.selection is None
    assert [issue.code for issue in result.issues] == [PlanningIssueCode.MISSING_SELECTION_POLICY]


def test_policy_cap_failure_never_silently_drops_airports(repository: KnowledgeRepository) -> None:
    policy = PlanningPolicy(max_automatic_group_airports=2)
    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"), "destination", repository, policy
    )

    assert result.selection is None
    assert [issue.code for issue in result.issues] == [
        PlanningIssueCode.SELECTION_POLICY_CAP_EXCEEDED
    ]


def test_stale_snapshot_is_explicit_evidence_failure() -> None:
    document = _read_snapshot()
    document["sources"][0]["verified_on"] = "2020-01-01"
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"), "destination", repository, PlanningPolicy()
    )

    assert result.selection is None
    assert result.resolution.status is LocationResolutionStatus.EVIDENCE_FAILURE
    assert [issue.code for issue in result.issues] == [PlanningIssueCode.STALE_KNOWLEDGE]
    assert result.freshness is FreshnessClass.STALE


def test_unrelated_stale_source_does_not_block_japan() -> None:
    document = _read_snapshot()
    _add_stale_source(document, "unrelated-nyc-source")
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        repository,
        PlanningPolicy(),
    )

    assert result.selection is not None
    assert result.freshness is FreshnessClass.CURRENT


@pytest.mark.parametrize("stale_record", ["entity", "relation", "airport", "policy"])
def test_each_stale_japan_selection_evidence_blocks_japan(stale_record: str) -> None:
    document = _read_snapshot()
    source_id = f"stale-japan-{stale_record}"
    _add_stale_source(document, source_id)
    if stale_record == "entity":
        next(entity for entity in document["entities"] if entity["entity_id"] == "country:jp")[
            "source_ids"
        ] = [source_id]
    elif stale_record == "relation":
        next(
            relation
            for relation in document["relations"]
            if relation["relation_id"] == "relation:jp-hnd-within-geography"
        )["source_ids"] = [source_id]
    elif stale_record == "airport":
        next(airport for airport in document["airports"] if airport["airport_id"] == "airport:hnd")[
            "source_ids"
        ] = [source_id]
    else:
        next(
            policy
            for policy in document["selection_policies"]
            if policy["policy_id"] == "policy:jp-representative-gateways-v1"
        )["source_ids"] = [source_id]
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        repository,
        PlanningPolicy(),
    )

    assert result.selection is None
    assert result.resolution.status is LocationResolutionStatus.EVIDENCE_FAILURE
    assert [issue.code for issue in result.issues] == [PlanningIssueCode.STALE_KNOWLEDGE]
    assert result.freshness is FreshnessClass.STALE


@pytest.mark.parametrize(
    ("candidate", "kind", "expected_status"),
    [
        ("Atlantis", LocationKind.CITY, LocationResolutionStatus.UNRESOLVED),
        ("Japan", LocationKind.CITY, LocationResolutionStatus.KIND_MISMATCH),
    ],
)
def test_unresolved_outcomes_are_not_reclassified_by_unrelated_stale_evidence(
    candidate: str,
    kind: LocationKind,
    expected_status: LocationResolutionStatus,
) -> None:
    document = _read_snapshot()
    _add_stale_source(document, "unrelated-nyc-source")
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(location(kind, candidate), "destination", repository, PlanningPolicy())

    assert result.selection is None
    assert result.resolution.status is expected_status
    assert result.freshness is FreshnessClass.CURRENT


def test_freshness_uses_snapshot_as_of_and_policy_not_wall_clock() -> None:
    document = _read_snapshot()
    document["metadata"]["as_of"] = "2030-01-01"
    document["metadata"]["verification_date"] = "2030-01-01"
    for source in document["sources"]:
        source["verified_on"] = "2029-12-31"
    repository = KnowledgeRepository(KnowledgeSnapshot.model_validate(document))

    result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        repository,
        PlanningPolicy(max_source_evidence_age_days=1),
    )

    assert result.selection is not None
    assert result.freshness is FreshnessClass.CURRENT


def test_snapshot_rejects_source_verification_after_its_as_of_date() -> None:
    document = _read_snapshot()
    document["sources"][0]["verified_on"] = "2026-09-13"

    with pytest.raises(ValidationError, match="cannot be after snapshot as_of"):
        KnowledgeSnapshot.model_validate(document)


def test_snapshot_rejects_snapshot_verification_after_its_as_of_date() -> None:
    document = _read_snapshot()
    document["metadata"]["verification_date"] = "2026-09-13"

    with pytest.raises(ValidationError, match="verification_date cannot be after as_of"):
        KnowledgeSnapshot.model_validate(document)


def test_reordered_snapshot_records_have_identical_grounding_output() -> None:
    baseline = _read_snapshot()
    reordered = _read_snapshot()
    for collection in ("sources", "entities", "airports", "relations", "selection_policies"):
        reordered[collection].reverse()
    for collection in ("entities", "airports"):
        for record in reordered[collection]:
            record["aliases"].reverse()
            record["source_ids"].reverse()
    for collection in ("relations", "selection_policies"):
        for record in reordered[collection]:
            record["source_ids"].reverse()
    baseline_result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        KnowledgeRepository(KnowledgeSnapshot.model_validate(baseline)),
        PlanningPolicy(),
    )
    reordered_result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        KnowledgeRepository(KnowledgeSnapshot.model_validate(reordered)),
        PlanningPolicy(),
    )

    assert baseline_result.model_dump(mode="json") == reordered_result.model_dump(mode="json")
    assert reordered_result.selection is not None
    assert [airport.airport_iata for airport in reordered_result.selection.airports] == [
        "HND",
        "NRT",
        "KIX",
    ]


def test_ambiguous_candidates_are_stably_canonicalized() -> None:
    baseline = _read_snapshot()
    baseline["entities"].append(
        {
            "entity_id": "country:jp-alternate",
            "kind": "country",
            "label": "Japan Alternate",
            "aliases": ["Japan"],
            "source_ids": ["japan-mlit-airports"],
        }
    )
    reordered = json.loads(json.dumps(baseline))
    reordered["entities"].reverse()

    baseline_result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        KnowledgeRepository(KnowledgeSnapshot.model_validate(baseline)),
        PlanningPolicy(),
    )
    reordered_result = ground_endpoint(
        location(LocationKind.COUNTRY, "Japan"),
        "destination",
        KnowledgeRepository(KnowledgeSnapshot.model_validate(reordered)),
        PlanningPolicy(),
    )

    assert baseline_result.resolution.status is LocationResolutionStatus.AMBIGUOUS
    assert baseline_result.resolution.candidate_ids == ("country:jp", "country:jp-alternate")
    assert baseline_result.model_dump(mode="json") == reordered_result.model_dump(mode="json")


def test_grounding_deeply_isolates_source_location(repository: KnowledgeRepository) -> None:
    source = location(LocationKind.AIRPORT, "SFO")
    result = ground_endpoint(source, "origin", repository, PlanningPolicy())
    source.value = "ZZZ"

    assert result.resolution.location.value == "SFO"
    read_copy = result.resolution.location
    read_copy.value = "LAX"
    assert result.resolution.location.value == "SFO"


def test_snapshot_rejects_policy_without_a_factual_relation() -> None:
    document = _read_snapshot()
    document["relations"] = [
        relation for relation in document["relations"] if relation["airport_id"] != "airport:kix"
    ]

    with pytest.raises(ValidationError, match="needs a factual entity-airport relation"):
        KnowledgeSnapshot.model_validate(document)


def test_snapshot_rejects_non_country_airport_link_and_unstable_evidence_lists() -> None:
    document = _read_snapshot()
    document["airports"][0]["country_entity_id"] = "city:new-york-city"

    with pytest.raises(ValidationError, match="country link must cite a country entity"):
        KnowledgeSnapshot.model_validate(document)

    document = _read_snapshot()
    document["entities"][0]["aliases"].append("  japan  ")

    with pytest.raises(ValidationError, match="aliases must be unique after normalization"):
        KnowledgeSnapshot.model_validate(document)

    document = _read_snapshot()
    document["entities"][0]["source_ids"].append("japan-mlit-airports")

    with pytest.raises(ValidationError, match="source IDs must be unique"):
        KnowledgeSnapshot.model_validate(document)


def _read_snapshot() -> dict[str, Any]:
    with Path(default_snapshot_path()).open(encoding="utf-8") as file:
        return cast(dict[str, Any], json.load(file))


def _add_stale_source(document: dict[str, Any], source_id: str) -> None:
    source = dict(document["sources"][0])
    source["source_id"] = source_id
    source["verified_on"] = "2020-01-01"
    document["sources"].append(source)
