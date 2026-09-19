"""Offline checks for Milestone 2B's deterministic planning-market gate."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
    SelectedAirport,
)
from award_agent.search_planning.knowledge import (
    AirportSelectionMetadata,
    CatalogKnowledgeRepository,
)
from award_agent.search_planning.market_policy import (
    AirportMarketAssignment,
    MarketAssignmentSource,
    MarketGateIssueCode,
    MarketGenerationGate,
    MarketGenerationGateStatus,
    PlanningMarketPolicy,
    PlanningMarketPolicyCompatibilityError,
    classify_and_gate_airport_markets,
    default_planning_market_policy_path,
    load_default_planning_market_policy,
    planning_market_policy_digest,
    validate_planning_market_policy_for_catalog,
)

CATALOG = Path("data/search_planning/catalogs/m1a-3cb7981519612945")


@pytest.fixture(scope="module")
def repository() -> Iterator[CatalogKnowledgeRepository]:
    with CatalogKnowledgeRepository(CATALOG) as opened:
        yield opened


def _selected(repository: CatalogKnowledgeRepository, iata: str) -> SelectedAirport:
    airport = repository.lookup_airport_iata(iata)
    assert airport is not None, iata
    return SelectedAirport(
        airport_id=airport.airport_id,
        airport_iata=airport.iata,
        airport_evidence_source_ids=airport.source_ids,
    )


def _gate(
    repository: CatalogKnowledgeRepository, origins: tuple[str, ...], destinations: tuple[str, ...]
) -> MarketGenerationGate:
    return classify_and_gate_airport_markets(
        origin_endpoints=tuple(_selected(repository, item) for item in origins),
        destination_endpoints=tuple(_selected(repository, item) for item in destinations),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )


def test_default_policy_covers_every_catalog_country_code_or_explicit_gap() -> None:
    policy = load_default_planning_market_policy()
    with sqlite3.connect(CATALOG / "catalog.sqlite") as connection:
        codes = {row[0] for row in connection.execute("SELECT code FROM ourairports_country")}

    assert codes == set(policy.country_assignments) | set(policy.explicit_unknown_country_codes)
    assert not set(policy.country_assignments) & set(policy.explicit_unknown_country_codes)
    assert len(policy.country_assignments) == 248
    assert policy.explicit_unknown_country_codes == ("ZZ",)
    assert len(policy.markets) == 22
    assert default_planning_market_policy_path().name == "planning-market-policy-v1.json"
    assert planning_market_policy_digest(policy) == "4e2d9436659b4123f340b2619a4620f843a53ae198469fe9cde5e312e965285a"


def test_policy_mutable_collections_are_copy_isolated_and_digest_stable() -> None:
    policy = load_default_planning_market_policy()
    digest = planning_market_policy_digest(policy)

    policy.country_assignments["US"] = "pacific_islands"
    policy.override_coverage_regions["US-HI"] = "us"

    assert policy.country_assignments["US"] == "us"
    assert policy.override_coverage_regions["US-HI"] == "pacific_islands"
    assert planning_market_policy_digest(policy) == digest


def test_exact_hawaii_and_ipc_overrides_win_over_country_defaults(
    repository: CatalogKnowledgeRepository,
) -> None:
    policy = load_default_planning_market_policy()
    gate = _gate(repository, ("HNL", "IPC"), ("SFO",))

    assignments = {item.endpoint.airport_iata: item for item in gate.assignments}
    assert assignments["HNL"].market_id == "pacific_islands"
    assert assignments["HNL"].source is MarketAssignmentSource.AIRPORT_OVERRIDE
    assert assignments["IPC"].market_id == "pacific_islands"
    assert assignments["IPC"].source is MarketAssignmentSource.AIRPORT_OVERRIDE
    assert policy.country_assignments["US"] == "us"
    assert policy.country_assignments["CL"] == "south_america"
    assert gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED


def test_all_overrides_match_exact_catalog_identity_country_and_region(
    repository: CatalogKnowledgeRepository,
) -> None:
    policy = load_default_planning_market_policy()

    compatibility = validate_planning_market_policy_for_catalog(policy, repository)

    assert compatibility.override_metadata_validated is True
    for override in policy.airport_overrides:
        airport = repository.airport(override.airport_id)
        metadata = repository.airport_selection_metadata(override.airport_id)
        assert airport is not None and metadata is not None
        assert (airport.iata, metadata.country_code, metadata.iso_region) == (
            override.expected_iata,
            override.expected_country_code,
            override.expected_iso_region,
        )
        if override.expected_iso_region in policy.override_coverage_regions:
            assert override.market_id == policy.override_coverage_regions[override.expected_iso_region]


def test_alaska_has_no_override_and_stays_in_us_market(
    repository: CatalogKnowledgeRepository,
) -> None:
    gate = _gate(repository, ("ANC",), ("SEA",))

    assert gate.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET
    assert {item.market_id for item in gate.assignments} == {"us"}
    assert all(item.source is MarketAssignmentSource.COUNTRY_ASSIGNMENT for item in gate.assignments)


def test_unknown_market_is_explicit_but_still_requires_generation() -> None:
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})
    endpoint = SelectedAirport(
        airport_id="test:unknown",
        airport_iata="ZZZ",
        airport_evidence_source_ids=("test:source",),
    )
    metadata = AirportSelectionMetadata(
        airport_id="test:unknown",
        country_code="ZZ",
        iso_region="ZZ-TEST",
        airport_type="medium_airport",
        latitude=0,
        longitude=0,
    )
    base_receipt = _catalog_receipt()
    repository = _FakeRepository(endpoint.airport_id, endpoint.airport_iata, metadata, base_receipt)

    gate = classify_and_gate_airport_markets(
        origin_endpoints=(endpoint,), destination_endpoints=(endpoint,), policy=policy, repository=repository
    )

    assert gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
    assert all(item.mapping_gap for item in gate.assignments)
    assert all(item.source is MarketAssignmentSource.EXPLICIT_UNKNOWN_COUNTRY for item in gate.assignments)
    assert [item.code for item in gate.issues] == [
        MarketGateIssueCode.MAPPING_GAP,
        MarketGateIssueCode.MAPPING_GAP,
    ]


def test_non_zz_unmapped_country_is_explicit_but_still_requires_generation() -> None:
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})
    endpoint = SelectedAirport(
        airport_id="test:unmapped",
        airport_iata="QZZ",
        airport_evidence_source_ids=("test:source",),
    )
    metadata = AirportSelectionMetadata(
        airport_id=endpoint.airport_id,
        country_code="QZ",
        iso_region="QZ-TEST",
        airport_type="medium_airport",
        latitude=0,
        longitude=0,
    )
    repository = _FakeRepository(endpoint.airport_id, endpoint.airport_iata, metadata, _catalog_receipt())

    gate = classify_and_gate_airport_markets(
        origin_endpoints=(endpoint,), destination_endpoints=(endpoint,), policy=policy, repository=repository
    )

    assert gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
    assert all(item.source is MarketAssignmentSource.UNMAPPED_COUNTRY for item in gate.assignments)


def test_new_hawaii_airport_is_a_mapping_gap_not_a_silent_us_fallback() -> None:
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})
    endpoint = SelectedAirport(
        airport_id="test:new-hawaii", airport_iata="NHI", airport_evidence_source_ids=("test:source",)
    )
    metadata = AirportSelectionMetadata(
        airport_id=endpoint.airport_id,
        country_code="US",
        iso_region="US-HI",
        airport_type="medium_airport",
        latitude=0,
        longitude=0,
    )
    repository = _FakeRepository(endpoint.airport_id, endpoint.airport_iata, metadata, _catalog_receipt())

    gate = classify_and_gate_airport_markets(
        origin_endpoints=(endpoint,), destination_endpoints=(endpoint,), policy=policy, repository=repository
    )

    assert gate.status is MarketGenerationGateStatus.GENERATION_REQUIRED
    assert gate.assignments[0].source is MarketAssignmentSource.OVERRIDE_COVERAGE_DRIFT
    assert gate.assignments[0].market_id is None


def test_empty_or_catalog_inconsistent_input_is_an_input_error(
    repository: CatalogKnowledgeRepository,
) -> None:
    sfo = _selected(repository, "SFO")
    mismatch = sfo.model_copy(update={"airport_iata": "LAX"})
    empty = classify_and_gate_airport_markets(
        origin_endpoints=(),
        destination_endpoints=(sfo,),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )
    invalid = classify_and_gate_airport_markets(
        origin_endpoints=(mismatch,),
        destination_endpoints=(sfo,),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )

    assert empty.status is MarketGenerationGateStatus.INPUT_ERROR
    assert empty.issues[0].code is MarketGateIssueCode.EMPTY_ORIGIN_ENDPOINTS
    assert invalid.status is MarketGenerationGateStatus.INPUT_ERROR
    assert invalid.issues[0].code is MarketGateIssueCode.ENDPOINT_IDENTITY_MISMATCH


def test_same_side_duplicates_are_input_errors_but_cross_side_overlap_is_valid(
    repository: CatalogKnowledgeRepository,
) -> None:
    sfo = _selected(repository, "SFO")
    duplicate = classify_and_gate_airport_markets(
        origin_endpoints=(sfo, sfo),
        destination_endpoints=(_selected(repository, "LAX"),),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )
    overlap = classify_and_gate_airport_markets(
        origin_endpoints=(sfo,),
        destination_endpoints=(sfo,),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )

    assert duplicate.status is MarketGenerationGateStatus.INPUT_ERROR
    assert any(item.code is MarketGateIssueCode.DUPLICATE_ENDPOINT for item in duplicate.issues)
    assert overlap.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET
    assert [item.role for item in overlap.assignments] == ["origin", "destination"]


def test_one_market_skips_but_equal_multi_market_sides_invoke_and_preserve_inputs(
    repository: CatalogKnowledgeRepository,
) -> None:
    same_market = _gate(repository, ("SFO",), ("LAX",))
    origins = (_selected(repository, "SFO"), _selected(repository, "CDG"))
    destinations = (_selected(repository, "LAX"), _selected(repository, "CDG"))
    multi_market = classify_and_gate_airport_markets(
        origin_endpoints=origins,
        destination_endpoints=destinations,
        policy=load_default_planning_market_policy(),
        repository=repository,
    )

    assert same_market.status is MarketGenerationGateStatus.SKIP_SINGLE_MARKET
    assert multi_market.status is MarketGenerationGateStatus.GENERATION_REQUIRED
    assert multi_market.known_market_ids == ("europe", "us")
    assert multi_market.origin_endpoints == origins
    assert multi_market.destination_endpoints == destinations


def test_runtime_catalog_identity_is_recorded_but_not_required_to_match_authoring_identity(
    repository: CatalogKnowledgeRepository,
) -> None:
    policy = load_default_planning_market_policy().model_copy(
        update={"catalog_release_id": "later-compatible-release"}
    )
    compatibility = validate_planning_market_policy_for_catalog(policy, repository)

    assert compatibility.override_metadata_validated is True
    assert compatibility.authoring_identity_matches_runtime is False


def test_region_drift_in_an_override_is_a_policy_compatibility_failure(
    repository: CatalogKnowledgeRepository,
) -> None:
    policy_data = load_default_planning_market_policy().model_dump(mode="python")
    policy_data["airport_overrides"][0]["expected_iso_region"] = "US-AK"
    policy = PlanningMarketPolicy.model_validate(policy_data)

    with pytest.raises(PlanningMarketPolicyCompatibilityError, match="does not match runtime catalog"):
        validate_planning_market_policy_for_catalog(policy, repository)


def test_malformed_policy_references_are_rejected() -> None:
    policy_data = load_default_planning_market_policy().model_dump(mode="python")
    policy_data["airport_overrides"][0]["market_id"] = "not_a_market"
    with pytest.raises(ValidationError, match="airport override names an unknown market"):
        PlanningMarketPolicy.model_validate(policy_data)

    policy_data = load_default_planning_market_policy().model_dump(mode="python")
    policy_data["airport_overrides"][0]["market_id"] = "us"
    with pytest.raises(ValidationError, match="guarded region"):
        PlanningMarketPolicy.model_validate(policy_data)


def test_public_assignment_and_gate_contracts_reject_impossible_constructions(
    repository: CatalogKnowledgeRepository,
) -> None:
    endpoint = _selected(repository, "SFO")
    with pytest.raises(ValidationError, match="mapping-gap assignment source"):
        AirportMarketAssignment(
            role="origin",
            endpoint=endpoint,
            catalog_country_code="US",
            catalog_iso_region="US-CA",
            market_id="us",
            source=MarketAssignmentSource.UNMAPPED_COUNTRY,
            mapping_gap=True,
        )

    gate = _gate(repository, ("SFO",), ("LAX",))
    data = gate.model_dump(mode="python")
    data["known_market_ids"] = ()
    with pytest.raises(ValidationError, match="known market IDs must be derived"):
        MarketGenerationGate.model_validate(data)

    data = gate.model_dump(mode="python")
    data["assignments"] = ()
    data["known_market_ids"] = ()
    with pytest.raises(ValidationError, match="assignments must cover"):
        MarketGenerationGate.model_validate(data)

    data = gate.model_dump(mode="python")
    data["issues"] = (
        {
            "code": "mapping_gap",
            "message": "forged gap",
            "role": "origin",
            "airport_id": endpoint.airport_id,
            "airport_iata": endpoint.airport_iata,
        },
    )
    with pytest.raises(ValidationError, match="mapping-gap issues must exactly record"):
        MarketGenerationGate.model_validate(data)


def test_input_error_gate_records_reject_forged_assignment_and_issue_details(
    repository: CatalogKnowledgeRepository,
) -> None:
    gate = _gate(repository, ("SFO",), ("LAX",))
    endpoint = _selected(repository, "SFO")
    data = gate.model_dump(mode="python")
    data["status"] = "input_error"
    data["issues"] = (
        {
            "code": "endpoint_not_in_catalog",
            "message": "forged catalog failure",
            "role": "origin",
            "airport_id": endpoint.airport_id,
            "airport_iata": endpoint.airport_iata,
        },
    )
    with pytest.raises(ValidationError, match="invalid endpoint cannot retain"):
        MarketGenerationGate.model_validate(data)

    data = gate.model_dump(mode="python")
    data["status"] = "input_error"
    data["issues"] = (
        {
            "code": "endpoint_not_in_catalog",
            "message": "forged endpoint",
            "role": "origin",
            "airport_id": "forged:airport",
            "airport_iata": "FOR",
        },
    )
    data["assignments"] = ()
    data["known_market_ids"] = ()
    with pytest.raises(ValidationError, match="actual input endpoint"):
        MarketGenerationGate.model_validate(data)

    duplicate = classify_and_gate_airport_markets(
        origin_endpoints=(endpoint, endpoint),
        destination_endpoints=(_selected(repository, "LAX"),),
        policy=load_default_planning_market_policy(),
        repository=repository,
    )
    data = duplicate.model_dump(mode="python")
    for origin in data["origin_endpoints"]:
        origin["airport_evidence_source_ids"] = ("forged:source",)
    with pytest.raises(ValidationError, match="completely match an input endpoint"):
        MarketGenerationGate.model_validate(data)


@dataclass(frozen=True)
class _FakeAirport:
    iata: str


class _FakeRepository:
    def __init__(
        self,
        airport_id: str,
        iata: str,
        metadata: AirportSelectionMetadata,
        receipt: CatalogKnowledgeReceipt,
    ) -> None:
        self._airport_id = airport_id
        self._airport = _FakeAirport(iata=iata)
        self._metadata = metadata
        self._knowledge_receipt = receipt

    @property
    def knowledge_receipt(self) -> CatalogKnowledgeReceipt:
        return self._knowledge_receipt

    def airport(self, airport_id: str) -> _FakeAirport | None:
        return self._airport if airport_id == self._airport_id else None

    def airport_selection_metadata(self, airport_id: str) -> AirportSelectionMetadata | None:
        return self._metadata if airport_id == self._airport_id else None


def _catalog_receipt() -> CatalogKnowledgeReceipt:
    # This deliberately avoids opening a full catalog in fake-repository tests.
    # Its fields only need to satisfy the runtime receipt contract.
    return CatalogKnowledgeReceipt(
        release_id="test-release",
        schema_version="2",
        source_date=date(2026, 9, 16),
        logical_content_sha256="0" * 64,
        manifest_sha256="1" * 64,
        database_sha256="2" * 64,
        source_bundle_manifest_sha256="3" * 64,
        source_artifacts=(CatalogSourceArtifactReceipt(artifact_name="test", bytes=0, sha256="4" * 64),),
    )
