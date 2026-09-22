"""Focused Milestone 1B tests over a tiny published catalog release."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

# The 1A suite owns a deliberately tiny, valid source-bundle constructor.  It
# keeps this serving suite independent of the ignored 1.36 GB owner-reviewed
# release while exercising the same publication/validation boundary.
from test_catalog_publication import CONTEXT, _bundle, _refresh_receipts

from award_agent.catalog import CatalogPublicationError, publish_catalog
from award_agent.cli.catalog_inspect import inspect_catalog
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
)
from award_agent.search_planning import (
    AirportSelectionCategory,
    CatalogKnowledgeReceipt,
    CatalogKnowledgeRepository,
    CatalogLookupStatus,
    PlanningInputEnvelope,
    PlanningIssueCode,
    PlanningPolicy,
    PlanningSource,
    context_for_resolved_location,
    ground_endpoint,
)


def _release(
    tmp_path: Path,
    *,
    country_entity_matches_airport: bool = True,
    duplicate_country_entity: bool = False,
    ambiguous_region_alias: bool = False,
) -> Path:
    bundle = _bundle(tmp_path)
    entities = bundle / "geonames_entities.tsv"
    lines = entities.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    base = dict(zip(header, lines[1].split("\t"), strict=True))
    if not country_entity_matches_airport:
        base["country_code"] = "CA"
        lines[1] = "\t".join(base[key] for key in header)
    city = {
        **base,
        "entity_id": "geonames:2",
        "entity_kind": "city",
        "taxonomy": "geonames:populated_place",
        "geoname_id": "2",
        "label": "Test City",
        "asciiname": "Test City",
        "source_record_id": "allCountries:2",
        "feature_class": "P",
        "feature_code": "PPL",
        "latitude": "1",
        "longitude": "2",
    }
    region = {
        **base,
        "entity_id": "geonames:3",
        "entity_kind": "region",
        "taxonomy": "geonames:geographic_region",
        "geoname_id": "3",
        "label": "Test Region",
        "asciiname": "Test Region",
        "source_record_id": "allCountries:3",
        "feature_class": "L",
        "feature_code": "RGN",
    }
    additional_entities: list[dict[str, str]] = []
    additional_aliases: list[str] = []
    if duplicate_country_entity:
        additional_entities.append(
            {
                **base,
                "entity_id": "geonames:4",
                "entity_kind": "country",
                "taxonomy": "geonames:country",
                "geoname_id": "4",
                "label": "Duplicate United States",
                "asciiname": "Duplicate United States",
                "country_code": "US",
                "source_record_id": "allCountries:4",
                "feature_class": "A",
                "feature_code": "PCLI",
            }
        )
        additional_aliases.append("4\tgeonames:4\tDuplicate United States\tname\tallCountries:4")
    if ambiguous_region_alias:
        additional_entities.append(
            {
                **region,
                "entity_id": "geonames:5",
                "geoname_id": "5",
                "label": "Other Test Region",
                "asciiname": "Other Test Region",
                "source_record_id": "allCountries:5",
            }
        )
        additional_aliases.append("5\tgeonames:5\tTest Region\tname\tallCountries:5")
    entities.write_text(
        "\n".join(
            [
                lines[0],
                lines[1],
                *("\t".join(item[key] for key in header) for item in (city, region)),
                *("\t".join(item[key] for key in header) for item in additional_entities),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    aliases = bundle / "geonames_base_aliases.tsv"
    alias_lines = aliases.read_text(encoding="utf-8").splitlines()
    alias_header = alias_lines[0].split("\t")
    aliases.write_text(
        "\n".join(
            [
                *alias_lines,
                "2\tgeonames:2\tTest City\tname\tallCountries:2",
                "3\tgeonames:3\tTest Region\tname\tallCountries:3",
                *additional_aliases,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert alias_header == ["geoname_id", "entity_id", "alias", "alias_kind", "source_record_id"]
    _refresh_receipts(bundle)
    return publish_catalog(bundle, tmp_path / "releases", CONTEXT).release_path


def _location(kind: LocationKind, value: str) -> LocationRef:
    return LocationRef(kind=kind, value=value, raw_text=value)


def _ready_envelope(origin: LocationRef, destination: LocationRef) -> PlanningInputEnvelope:
    return PlanningInputEnvelope(
        source=PlanningSource(session_id="catalog-serving", revision=1),
        effective_request=EffectiveRequest(
            raw_text="test",
            context=RequestContext(reference_date=date(2026, 9, 14), timezone="America/New_York"),
            travelers=1,
            origins=(origin,),
            destinations=(destination,),
            departure_window=DateWindow(
                start=date(2026, 10, 1),
                end=date(2026, 10, 1),
                precision=DateWindowPrecision.EXACT,
                raw_text="October 1",
            ),
            cabins=(CabinClass.BUSINESS,),
            search_modes=(SearchMode.AWARD,),
            field_provenance=(
                FieldProvenance(
                    field=EffectiveField.CABIN,
                    source=InitialSnapshotSource(field=EffectiveField.CABIN),
                ),
            ),
        ),
    )


def test_catalog_repository_is_exact_read_only_and_carries_receipts(tmp_path: Path) -> None:
    release = _release(tmp_path)
    database = release / "catalog.sqlite"
    before = database.read_bytes()
    with CatalogKnowledgeRepository(release) as repository:
        assert [
            item.entity_id for item in repository.resolve_entities(LocationKind.CITY, "test city")
        ] == ["geonames:2"]
        assert repository.resolve_entities(LocationKind.CITY, "test") == ()
        assert repository.taxonomy_for_entity("geonames:3") == "geonames:geographic_region"
        assert repository.taxonomy_ids() == tuple(sorted(repository.taxonomy_ids()))
        city = repository.get_entity("geonames:2")
        assert city is not None
        city_metadata = repository.entity_selection_metadata(city.entity_id)
        assert city_metadata is not None
        assert city_metadata.taxonomy_id == "geonames:populated_place"
        assert city_metadata.feature_code == "PPL"
        assert city_metadata.latitude == 1.0 and city_metadata.longitude == 2.0
        city_resolution = ground_endpoint(
            _location(LocationKind.CITY, "Test City"), "origin", repository, PlanningPolicy()
        ).resolution
        city_context = context_for_resolved_location(city_resolution, repository)
        assert city_context.category is AirportSelectionCategory.CITY_METROPOLITAN
        assert city_context.taxonomy_id == "geonames:populated_place"
        assert set(city_resolution.evidence_source_ids) <= set(city_context.evidence_source_ids)
        region_lookup = repository.lookup_exact_location(
            LocationKind.REGION,
            "Test Region",
            taxonomy_id="geonames:geographic_region",
        )
        assert region_lookup.status is CatalogLookupStatus.RESOLVED
        assert region_lookup.candidates[0].candidate_id == "geonames:3"
        airport = repository.lookup_airport_iata("TST")
        assert airport is not None and airport.iata == "TST"
        airport_metadata = repository.airport_selection_metadata(airport.airport_id)
        assert airport_metadata is not None
        assert airport_metadata.country_code == "US"
        assert airport_metadata.iso_region == "US-NY"
        assert airport_metadata.latitude is not None and airport_metadata.longitude is not None
        airport_sources = repository.source_records_for_airport(airport.airport_id)
        assert "geonames_entities.tsv:allCountries:1" in airport.source_ids
        assert "geonames_entities.tsv:allCountries:1" in {
            source.source_record_key for source in airport_sources
        }
        assert (
            repository.freshness_for_source_ids(
                airport.source_ids, max_source_evidence_age_days=0
            ).value
            == "current"
        )
        with pytest.raises(ValueError, match="unknown source IDs"):
            repository.freshness_for_source_ids(("invented",), max_source_evidence_age_days=0)
        assert not hasattr(repository, "_source_ids")
        with pytest.raises(ValueError, match="unknown-500"):
            repository.freshness_for_source_ids(
                tuple(f"unknown-{index}" for index in range(501)),
                max_source_evidence_age_days=0,
            )
        with pytest.raises(sqlite3.OperationalError):
            repository._connection.execute("CREATE TABLE forbidden(value TEXT)")
        receipt = repository.knowledge_receipt
        assert isinstance(receipt, CatalogKnowledgeReceipt)
        assert receipt.release_id == release.name
        assert receipt.source_bundle_manifest_sha256
    assert database.read_bytes() == before


def test_catalog_grounding_selects_only_explicit_or_uniquely_named_airports(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path)
    with CatalogKnowledgeRepository(release) as repository:
        planned = ground_endpoint(
            _location(LocationKind.AIRPORT, "TST"), "origin", repository, PlanningPolicy()
        )
        assert planned.selection is not None
        assert planned.selection.airports[0].airport_iata == "TST"
        assert planned.selection.kind.value == "explicit_iata"
        named = ground_endpoint(
            _location(LocationKind.AIRPORT, "Test Airport"),
            "origin",
            repository,
            PlanningPolicy(),
        )
        assert named.selection is not None
        assert named.selection.airports[0].airport_iata == "TST"
        assert named.selection.kind.value == "named_airport"
        assert isinstance(repository.knowledge_receipt, CatalogKnowledgeReceipt)
        geography = ground_endpoint(
            _location(LocationKind.CITY, "Test City"),
            "origin",
            repository,
            PlanningPolicy(),
        )
        assert geography.resolution.resolved_entity_id == "geonames:2"
        assert geography.selection is None
        assert [issue.code for issue in geography.issues] == [
            PlanningIssueCode.M2A_SELECTION_REQUIRED
        ]


def test_catalog_open_rejects_tampering_and_inspector_is_read_only(tmp_path: Path) -> None:
    release = _release(tmp_path)
    inspection = inspect_catalog(release, alias="Test City")
    assert inspection["lookups"]["city"]["candidates"][0]["candidate_id"] == "geonames:2"
    scoped = inspect_catalog(
        release,
        alias="Test Region",
        taxonomy="geonames:geographic_region",
    )
    assert scoped["lookup"]["status"] == CatalogLookupStatus.RESOLVED.value
    assert inspect_catalog(release, airport="TST")["airport"]["iata"] == "TST"
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["release_id"] = "m1a-forged"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CatalogPublicationError):
        CatalogKnowledgeRepository(release)


def test_missing_catalog_country_metadata_is_an_explicit_airport_evidence_failure(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path, country_entity_matches_airport=False)
    with CatalogKnowledgeRepository(release) as repository:
        assert repository.lookup_airport_iata("TST") is None
        assert repository.resolve_airports_by_alias("test airport") == ()
        for location in (
            _location(LocationKind.AIRPORT, "TST"),
            _location(LocationKind.AIRPORT, "Test Airport"),
        ):
            result = ground_endpoint(location, "origin", repository, PlanningPolicy())
            assert result.selection is None
            assert [issue.code for issue in result.issues] == [
                PlanningIssueCode.MISSING_AIRPORT_EVIDENCE
            ]


def test_catalog_exact_lookup_reports_stable_taxonomy_and_query_statuses(tmp_path: Path) -> None:
    release = _release(tmp_path)
    with CatalogKnowledgeRepository(release) as repository:
        assert (
            repository.lookup_exact_location(
                LocationKind.REGION,
                "Test Region",
                taxonomy_id="geonames:country",
            ).status
            is CatalogLookupStatus.TAXONOMY_MISMATCH
        )
        assert (
            repository.lookup_exact_location(
                LocationKind.REGION,
                "Test City",
                taxonomy_id="geonames:geographic_region",
            ).status
            is CatalogLookupStatus.KIND_MISMATCH
        )
        assert (
            repository.lookup_exact_location(
                LocationKind.REGION,
                "Missing Place",
                taxonomy_id="geonames:geographic_region",
            ).status
            is CatalogLookupStatus.NOT_FOUND
        )
        assert (
            repository.lookup_exact_location(
                LocationKind.REGION,
                "Test Region",
                taxonomy_id="missing:taxonomy",
            ).status
            is CatalogLookupStatus.MISSING_METADATA
        )
    ambiguous_release = _release(tmp_path / "ambiguous", ambiguous_region_alias=True)
    with CatalogKnowledgeRepository(ambiguous_release) as repository:
        lookup = repository.lookup_exact_location(
            LocationKind.REGION,
            "Test Region",
            taxonomy_id="geonames:geographic_region",
        )
        assert lookup.status is CatalogLookupStatus.AMBIGUOUS
        assert [candidate.candidate_id for candidate in lookup.candidates] == [
            "geonames:3",
            "geonames:5",
        ]


def test_duplicate_catalog_country_metadata_is_an_explicit_airport_evidence_failure(
    tmp_path: Path,
) -> None:
    release = _release(tmp_path, duplicate_country_entity=True)
    with CatalogKnowledgeRepository(release) as repository:
        assert (
            repository.lookup_exact_location(LocationKind.AIRPORT, "TST").status
            is CatalogLookupStatus.MISSING_METADATA
        )
        assert repository.lookup_airport_iata("TST") is None
        result = ground_endpoint(
            _location(LocationKind.AIRPORT, "TST"), "origin", repository, PlanningPolicy()
        )
        assert result.selection is None
        assert [issue.code for issue in result.issues] == [
            PlanningIssueCode.MISSING_AIRPORT_EVIDENCE
        ]
