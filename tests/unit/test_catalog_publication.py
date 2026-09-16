from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from award_agent.catalog import (
    CatalogPublicationError,
    PublicationContext,
    inspect_release,
    publish_catalog,
    validate_release,
)
from award_agent.catalog.publication import _timezone_tree_digest, timezone_validator_identity
from award_agent.search_planning.knowledge import CatalogKnowledgeRepository

CONTEXT = PublicationContext(
    source_date=date(2026, 9, 14),
)


def _write_rows(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=headers, delimiter="\t" if path.suffix == ".tsv" else ","
        )
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(
    tmp_path: Path,
    *,
    candidate_country: str = "US",
    evidence_country: str = "US",
    second_candidate: bool = False,
    historic_second: bool = False,
    entity_source_id: str = "allCountries:1",
) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    _write_rows(
        bundle / "geonames_entities.tsv",
        [
            "entity_id",
            "entity_kind",
            "taxonomy",
            "geoname_id",
            "label",
            "asciiname",
            "country_code",
            "iso3",
            "iso_numeric",
            "continent",
            "source_record_id",
            "feature_class",
            "feature_code",
            "latitude",
            "longitude",
            "admin1_code",
            "admin2_code",
            "population",
            "timezone",
            "modification_date",
        ],
        [
            {
                "entity_id": "geonames:1",
                "entity_kind": "country",
                "taxonomy": "geonames:country",
                "geoname_id": "1",
                "label": "United States",
                "asciiname": "United States",
                "country_code": "US",
                "iso3": "USA",
                "iso_numeric": "840",
                "continent": "NA",
                "source_record_id": entity_source_id,
                "feature_class": "A",
                "feature_code": "PCLI",
                "latitude": "",
                "longitude": "",
                "admin1_code": "",
                "admin2_code": "",
                "population": "",
                "timezone": "America/New_York",
                "modification_date": "2026-01-01",
            }
        ],
    )
    _write_rows(
        bundle / "geonames_base_aliases.tsv",
        ["geoname_id", "entity_id", "alias", "alias_kind", "source_record_id"],
        [
            {
                "geoname_id": "1",
                "entity_id": "geonames:1",
                "alias": "United States",
                "alias_kind": "name",
                "source_record_id": entity_source_id,
            }
        ],
    )
    _write_rows(
        bundle / "geonames_current_aliases.tsv",
        [
            "alternate_name_id",
            "geoname_id",
            "entity_id",
            "iso_language",
            "alternate_name",
            "is_preferred_name",
            "is_short_name",
            "is_colloquial",
            "is_historic",
            "from",
            "to",
        ],
        [
            {
                "alternate_name_id": "100",
                "geoname_id": "1",
                "entity_id": "geonames:1",
                "iso_language": "en",
                "alternate_name": "USA",
                "is_preferred_name": "1",
                "is_short_name": "",
                "is_colloquial": "",
                "is_historic": "",
                "from": "",
                "to": "",
            }
        ],
    )
    candidate_headers = [
        "geoname_id",
        "name",
        "asciiname",
        "country_code",
        "latitude",
        "longitude",
        "timezone",
        "modification_date",
        "source_record_id",
    ]
    candidates = [
        {
            "geoname_id": "9",
            "name": "Test Airport",
            "asciiname": "Test Airport",
            "country_code": candidate_country,
            "latitude": "1",
            "longitude": "2",
            "timezone": "America/New_York",
            "modification_date": "2026-01-01",
            "source_record_id": "allCountries:9",
        }
    ]
    if second_candidate:
        candidates.append(
            {**candidates[0], "geoname_id": "10", "source_record_id": "allCountries:10"}
        )
    _write_rows(bundle / "geonames_airport_candidates.tsv", candidate_headers, candidates)
    evidence_headers = [
        "alternate_name_id",
        "iata_code",
        "geoname_id",
        "country_code",
        "timezone",
        "is_historic",
        "from",
        "to",
        "source_record_id",
    ]
    evidence = [
        {
            "alternate_name_id": "200",
            "iata_code": "TST",
            "geoname_id": "9",
            "country_code": evidence_country,
            "timezone": "America/New_York",
            "is_historic": "",
            "from": "",
            "to": "",
            "source_record_id": "alternateNamesV2:200",
        }
    ]
    if second_candidate:
        evidence.append(
            {
                **evidence[0],
                "alternate_name_id": "201",
                "geoname_id": "10",
                "source_record_id": "alternateNamesV2:201",
                "is_historic": "1" if historic_second else "",
            }
        )
    _write_rows(bundle / "geonames_iata_crossrefs.tsv", evidence_headers, evidence)
    _write_rows(
        bundle / "ourairports_airports.csv",
        [
            "id",
            "ident",
            "type",
            "name",
            "latitude_deg",
            "longitude_deg",
            "iso_country",
            "iso_region",
            "scheduled_service",
            "icao_code",
            "iata_code",
            "gps_code",
            "local_code",
            "wikipedia_link",
        ],
        [
            {
                "id": "42",
                "ident": "KTST",
                "type": "medium_airport",
                "name": "Test Airport",
                "latitude_deg": "1",
                "longitude_deg": "2",
                "iso_country": "US",
                "iso_region": "US-NY",
                "scheduled_service": "yes",
                "icao_code": "KTST",
                "iata_code": "TST",
                "gps_code": "",
                "local_code": "",
                "wikipedia_link": "",
            }
        ],
    )
    _write_rows(
        bundle / "ourairports_countries.csv",
        ["id", "code", "name", "continent", "wikipedia_link", "keywords"],
        [
            {
                "id": "1",
                "code": "US",
                "name": "United States",
                "continent": "NA",
                "wikipedia_link": "",
                "keywords": "",
            }
        ],
    )
    _write_rows(
        bundle / "ourairports_regions.csv",
        [
            "id",
            "code",
            "local_code",
            "name",
            "continent",
            "iso_country",
            "wikipedia_link",
            "keywords",
        ],
        [
            {
                "id": "2",
                "code": "US-NY",
                "local_code": "NY",
                "name": "New York",
                "continent": "NA",
                "iso_country": "US",
                "wikipedia_link": "",
                "keywords": "",
            }
        ],
    )
    _write_rows(
        bundle / "geonames_admin_corroboration.tsv",
        ["geoname_id", "expected_feature_code", "corroborated_by_active_allcountries"],
        [],
    )
    _write_rows(
        bundle / "quarantine.tsv", ["record_kind", "source_record_id", "reason_code", "detail"], []
    )
    outputs = {
        path.name: {"bytes": path.stat().st_size, "sha256": _sha(path)} for path in bundle.iterdir()
    }
    (bundle / "manifest.json").write_text(
        json.dumps({"bundle_id": "test-bundle", "format_version": "1", "outputs": outputs}),
        encoding="utf-8",
    )
    return bundle


def _refresh_receipts(bundle: Path) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"] = {
        path.name: {"bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in bundle.iterdir()
        if path.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _add_lossless_source_sidecars(bundle: Path) -> None:
    """Upgrade the compact fixture to the v2 raw-record retention contract."""
    schemas = {
        "allCountries.txt": ["geonameid", "name"],
        "countryInfo.txt": ["ISO", "Country"],
        "admin1CodesASCII.txt": ["code", "name"],
        "admin2Codes.txt": ["code", "name"],
        "alternateNamesV2.txt": ["alternateNameId", "name"],
        "airports.csv": ["id", "municipality", "keywords"],
        "countries.csv": ["id", "keywords"],
        "regions.csv": ["id", "keywords"],
    }
    (bundle / "source_schemas.json").write_text(json.dumps(schemas), encoding="utf-8")
    records = [
        ("countryInfo.txt", "countryInfo:US", ["US", "United States"]),
        ("allCountries.txt", "allCountries:1", ["1", "United States"]),
        ("allCountries.txt", "allCountries:9", ["9", "Test Airport"]),
        # Deliberately overlap an ID across raw source files.  Publication
        # must follow the derived-record source mapping, not ID alone.
        ("alternateNamesV2.txt", "allCountries:9", ["allCountries:9", "wrong source"]),
        ("alternateNamesV2.txt", "alternateNamesV2:100", ["100", "United States"]),
        ("alternateNamesV2.txt", "alternateNamesV2:200", ["200", "TST"]),
        ("airports.csv", "ourairports:42", ["42", "Testville", "test, TST"]),
        ("countries.csv", "ourairports:1", ["1", "united states"]),
        ("regions.csv", "ourairports:2", ["2", "new york"]),
    ]
    _write_rows(
        bundle / "source_raw_records.tsv",
        ["source_name", "source_record_id", "values_json"],
        [
            {
                "source_name": source_name,
                "source_record_id": source_record_id,
                "values_json": json.dumps(values, separators=(",", ":")),
            }
            for source_name, source_record_id, values in records
        ],
    )
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["format_version"] = "2"
    manifest["source_files_read"] = {name: {"bytes": 1, "sha256": "0" * 64} for name in schemas}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_receipts(bundle)


def test_publishes_immutable_catalog_with_manifest_and_exact_name_alias(tmp_path: Path) -> None:
    result = publish_catalog(_bundle(tmp_path), tmp_path / "releases", CONTEXT)
    manifest = validate_release(result.release_path)
    assert result.release_id.startswith("m1a-")
    assert manifest["coverage"]["airport_group_coverage"] == "none_in_this_release"
    assert manifest["coverage"]["route_coverage"] == "none"
    assert manifest["publication_context"]["source_date"] == "2026-09-14"
    assert manifest["publication_context"]["timezone_validator"] == timezone_validator_identity()
    assert inspect_release(result.release_path)["counts"]["airport"] == 1
    with sqlite3.connect(f"file:{result.database_path}?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT airport_id, timezone FROM airport").fetchall() == [
            ("ourairports:42", "America/New_York")
        ]
        assert connection.execute("SELECT normalized_alias FROM airport_alias").fetchall() == [
            ("test airport",)
        ]
        assert connection.execute("SELECT COUNT(*) FROM airport_reconciliation").fetchone()[0] == 1
    prior_database_sha = _sha(result.database_path)
    prior_manifest = result.manifest_path.read_bytes()
    with pytest.raises(CatalogPublicationError, match="release already exists"):
        publish_catalog(_bundle(tmp_path / "other"), tmp_path / "releases", CONTEXT)
    assert _sha(result.database_path) == prior_database_sha
    assert result.manifest_path.read_bytes() == prior_manifest


def test_lossless_source_payload_is_inspectable_but_not_an_airport_alias(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    _add_lossless_source_sidecars(bundle)
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    with sqlite3.connect(f"file:{result.database_path}?mode=ro", uri=True) as connection:
        record = connection.execute(
            """SELECT schema.headers_json, source.raw_values_json
                 FROM source_record AS source
                 JOIN source_schema AS schema ON schema.source_name = source.source_schema_name
                WHERE source.source_record_key = 'airports.csv:ourairports:42'"""
        ).fetchone()
        assert record == (
            '["id","municipality","keywords"]',
            '["42","Testville","test, TST"]',
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM airport_alias WHERE normalized_alias = 'testville'"
            ).fetchone()[0]
            == 0
        )
        query_plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT source_record_key FROM source_record "
            "WHERE source_schema_name = ? AND source_record_id = ?",
            ("airports.csv", "ourairports:42"),
        ).fetchall()
        assert any("source_record_raw_identity_idx" in row[3] for row in query_plan)
    with CatalogKnowledgeRepository(result.release_path) as repository:
        source_record = repository.source_record("airports.csv:ourairports:42")
    assert source_record is not None
    assert source_record.source_headers == ("id", "municipality", "keywords")
    assert source_record.raw_values == ("42", "Testville", "test, TST")


def test_conflicts_and_ambiguity_are_quarantined_not_published(tmp_path: Path) -> None:
    result = publish_catalog(
        _bundle(tmp_path, candidate_country="CA", evidence_country="CA"),
        tmp_path / "releases",
        CONTEXT,
    )
    assert result.counts["airport"] == 0
    assert inspect_release(result.release_path)["quarantine"] == [
        {"reason_code": "iata_country_conflict", "count": 1}
    ]
    ambiguous = publish_catalog(
        _bundle(tmp_path / "ambiguous", second_candidate=True),
        tmp_path / "ambiguous-releases",
        CONTEXT,
    )
    assert inspect_release(ambiguous.release_path)["quarantine"] == [
        {"reason_code": "iata_ambiguous_geonames_candidate", "count": 1}
    ]


def test_candidate_crossref_disagreement_rejects_without_release(tmp_path: Path) -> None:
    with pytest.raises(CatalogPublicationError, match="disagrees with candidate"):
        publish_catalog(
            _bundle(tmp_path, candidate_country="US", evidence_country="CA"),
            tmp_path / "releases",
            CONTEXT,
        )
    assert not list((tmp_path / "releases").glob("m1a-*"))


def test_release_validation_detects_database_tampering(tmp_path: Path) -> None:
    result = publish_catalog(_bundle(tmp_path), tmp_path / "releases", CONTEXT)
    with result.database_path.open("ab") as output:
        output.write(b"tamper")
    with pytest.raises(CatalogPublicationError, match="database receipt mismatch"):
        validate_release(result.release_path)


def test_reordered_source_rows_have_the_same_logical_catalog_digest(tmp_path: Path) -> None:
    first = publish_catalog(
        _bundle(tmp_path / "first", second_candidate=True, historic_second=True),
        tmp_path / "first-releases",
        CONTEXT,
    )
    reordered_bundle = _bundle(tmp_path / "second", second_candidate=True, historic_second=True)
    for name in ("geonames_airport_candidates.tsv", "geonames_iata_crossrefs.tsv"):
        path = reordered_bundle / name
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join([lines[0], *reversed(lines[1:])]) + "\n", encoding="utf-8")
    _refresh_receipts(reordered_bundle)
    second = publish_catalog(reordered_bundle, tmp_path / "second-releases", CONTEXT)
    assert first.logical_content_sha256 == second.logical_content_sha256


def test_rejects_a_receipt_or_header_mismatch_before_creating_a_release(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    (bundle / "geonames_entities.tsv").write_text("wrong\n", encoding="utf-8")
    with pytest.raises(CatalogPublicationError, match="receipt mismatch"):
        publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    assert not (tmp_path / "releases").exists()


def test_duplicate_evidence_for_same_candidate_is_not_an_ambiguity(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "geonames_iata_crossrefs.tsv"
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = list(csv.DictReader(input_file, delimiter="\t"))
    rows.append({**rows[0], "alternate_name_id": "201", "source_record_id": "alternateNamesV2:201"})
    _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    assert result.counts["airport"] == 1


@pytest.mark.parametrize("field,value", [("is_historic", "1"), ("to", "2026-01-01")])
def test_historic_or_expired_evidence_is_ineligible(tmp_path: Path, field: str, value: str) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "geonames_iata_crossrefs.tsv"
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = list(csv.DictReader(input_file, delimiter="\t"))
    rows[0][field] = value
    _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    assert inspect_release(result.release_path)["quarantine"] == [
        {"reason_code": "iata_no_eligible_geonames_candidate", "count": 1}
    ]


@pytest.mark.parametrize("timezone", ["", "Not/AZone"])
def test_blank_or_invalid_timezone_is_quarantined(tmp_path: Path, timezone: str) -> None:
    bundle = _bundle(tmp_path)
    for name in ("geonames_airport_candidates.tsv", "geonames_iata_crossrefs.tsv"):
        path = bundle / name
        with path.open(encoding="utf-8", newline="") as input_file:
            rows = list(csv.DictReader(input_file, delimiter="\t"))
        rows[0]["timezone"] = timezone
        _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    assert inspect_release(result.release_path)["quarantine"] == [
        {"reason_code": "iata_timezone_unusable", "count": 1}
    ]


def test_one_candidate_cannot_publish_multiple_current_iatas(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    evidence_path = bundle / "geonames_iata_crossrefs.tsv"
    airport_path = bundle / "ourairports_airports.csv"
    with evidence_path.open(encoding="utf-8", newline="") as input_file:
        evidence = list(csv.DictReader(input_file, delimiter="\t"))
    evidence.append(
        {
            **evidence[0],
            "alternate_name_id": "201",
            "iata_code": "OTH",
            "source_record_id": "alternateNamesV2:201",
        }
    )
    _write_rows(evidence_path, list(evidence[0]), evidence)
    with airport_path.open(encoding="utf-8", newline="") as input_file:
        airports = list(csv.DictReader(input_file))
    airports.append({**airports[0], "id": "43", "iata_code": "OTH", "ident": "KOTH"})
    _write_rows(airport_path, list(airports[0]), airports)
    _refresh_receipts(bundle)
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    assert result.counts["airport"] == 0
    assert inspect_release(result.release_path)["quarantine"] == [
        {"reason_code": "iata_candidate_multiple_current_iatas", "count": 2}
    ]


def test_duplicate_iata_or_false_admin_corroboration_rejects(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path / "duplicate")
    airport_path = bundle / "ourairports_airports.csv"
    with airport_path.open(encoding="utf-8", newline="") as input_file:
        airports = list(csv.DictReader(input_file))
    airports.append({**airports[0], "id": "43"})
    _write_rows(airport_path, list(airports[0]), airports)
    _refresh_receipts(bundle)
    with pytest.raises(CatalogPublicationError, match="duplicate or dangling OurAirports endpoint"):
        publish_catalog(bundle, tmp_path / "duplicate-releases", CONTEXT)
    admin_bundle = _bundle(tmp_path / "false-admin")
    _write_rows(
        admin_bundle / "geonames_admin_corroboration.tsv",
        ["geoname_id", "expected_feature_code", "corroborated_by_active_allcountries"],
        [
            {
                "geoname_id": "1",
                "expected_feature_code": "PCLI",
                "corroborated_by_active_allcountries": "false",
            }
        ],
    )
    _refresh_receipts(admin_bundle)
    with pytest.raises(CatalogPublicationError, match="invalid administrative corroboration"):
        publish_catalog(admin_bundle, tmp_path / "admin-releases", CONTEXT)


def test_manifest_derived_fields_and_original_source_ids_are_verified(tmp_path: Path) -> None:
    result = publish_catalog(_bundle(tmp_path), tmp_path / "releases", CONTEXT)
    with sqlite3.connect(f"file:{result.database_path}?mode=ro", uri=True) as connection:
        assert connection.execute(
            "SELECT source_record_id FROM source_record WHERE source_record_key = ?",
            ("geonames_iata_crossrefs.tsv:alternateNamesV2:200",),
        ).fetchone() == ("alternateNamesV2:200",)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest["counts"]["airport"] = 99
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CatalogPublicationError, match="manifest-derived catalog fields mismatch"):
        validate_release(result.release_path)


def test_base_alias_accepts_entity_consistent_non_allcountries_source(tmp_path: Path) -> None:
    result = publish_catalog(
        _bundle(tmp_path, entity_source_id="countryInfo:US"), tmp_path / "releases", CONTEXT
    )
    assert result.counts["entity_alias_evidence"] == 2


def test_bundle_manifest_metadata_is_typed_and_preserved_in_release(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "manifest.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(
        {
            "filters": {"countries": {"current": True}},
            "purpose": "fixture publication input",
            "record_counts": {"entities": 1},
            "limitations": ["fixture only"],
        }
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    result = publish_catalog(bundle, tmp_path / "releases", CONTEXT)
    manifest = validate_release(result.release_path)
    assert manifest["source_bundle"]["filters"] == document["filters"]
    assert manifest["source_bundle"]["purpose"] == document["purpose"]
    assert manifest["source_bundle"]["record_counts"] == document["record_counts"]
    assert manifest["source_bundle"]["limitations"] == document["limitations"]


def test_airport_region_must_match_airport_country(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "ourairports_airports.csv"
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    rows[0]["iso_country"] = "CA"
    _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    with pytest.raises(CatalogPublicationError, match="not prefixed by airport country"):
        publish_catalog(bundle, tmp_path / "releases", CONTEXT)


def test_malformed_alias_iata_and_admin_flags_reject(tmp_path: Path) -> None:
    alias_bundle = _bundle(tmp_path / "alias")
    alias_path = alias_bundle / "geonames_current_aliases.tsv"
    with alias_path.open(encoding="utf-8", newline="") as input_file:
        aliases = list(csv.DictReader(input_file, delimiter="\t"))
    aliases[0]["iso_language"] = "not an iso tag"
    _write_rows(alias_path, list(aliases[0]), aliases)
    _refresh_receipts(alias_bundle)
    with pytest.raises(CatalogPublicationError, match="current-alias filter"):
        publish_catalog(alias_bundle, tmp_path / "alias-releases", CONTEXT)
    iata_bundle = _bundle(tmp_path / "iata")
    iata_path = iata_bundle / "geonames_iata_crossrefs.tsv"
    with iata_path.open(encoding="utf-8", newline="") as input_file:
        iata = list(csv.DictReader(input_file, delimiter="\t"))
    iata[0]["is_historic"] = "yes"
    _write_rows(iata_path, list(iata[0]), iata)
    _refresh_receipts(iata_bundle)
    with pytest.raises(CatalogPublicationError, match="is_historic"):
        publish_catalog(iata_bundle, tmp_path / "iata-releases", CONTEXT)
    admin_bundle = _bundle(tmp_path / "admin")
    _write_rows(
        admin_bundle / "geonames_admin_corroboration.tsv",
        ["geoname_id", "expected_feature_code", "corroborated_by_active_allcountries"],
        [
            {
                "geoname_id": "1",
                "expected_feature_code": "ADM1",
                "corroborated_by_active_allcountries": "true",
            }
        ],
    )
    _refresh_receipts(admin_bundle)
    with pytest.raises(CatalogPublicationError, match="disagrees with entity"):
        publish_catalog(admin_bundle, tmp_path / "admin-releases", CONTEXT)


def test_database_filename_and_timezone_tree_content_are_verified(tmp_path: Path) -> None:
    result = publish_catalog(_bundle(tmp_path), tmp_path / "releases", CONTEXT)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    manifest["database"]["filename"] = "other.sqlite"
    result.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CatalogPublicationError, match="database receipt mismatch"):
        validate_release(result.release_path)
    root = tmp_path / "zoneinfo"
    root.mkdir()
    zone = root / "UTC"
    zone.write_bytes(b"first")
    first = _timezone_tree_digest((root,))
    zone.write_bytes(b"second")
    assert _timezone_tree_digest((root,)) != first


@pytest.mark.parametrize("language", ["en-x", "eng-abcdefghijk"])
def test_current_alias_language_requires_preparer_compatible_tag(
    tmp_path: Path, language: str
) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "geonames_current_aliases.tsv"
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = list(csv.DictReader(input_file, delimiter="\t"))
    rows[0]["iso_language"] = language
    _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    with pytest.raises(CatalogPublicationError, match="current-alias filter"):
        publish_catalog(bundle, tmp_path / "releases", CONTEXT)


@pytest.mark.parametrize("language", ["EN", "abbr"])
def test_current_alias_language_accepts_preparer_compatible_base_or_abbr(
    tmp_path: Path, language: str
) -> None:
    bundle = _bundle(tmp_path)
    path = bundle / "geonames_current_aliases.tsv"
    with path.open(encoding="utf-8", newline="") as input_file:
        rows = list(csv.DictReader(input_file, delimiter="\t"))
    rows[0]["iso_language"] = language
    _write_rows(path, list(rows[0]), rows)
    _refresh_receipts(bundle)
    assert publish_catalog(bundle, tmp_path / "releases", CONTEXT).counts["airport"] == 1


def test_every_admin_entity_requires_exactly_one_corroboration_row(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    entity_path = bundle / "geonames_entities.tsv"
    with entity_path.open(encoding="utf-8", newline="") as input_file:
        entities = list(csv.DictReader(input_file, delimiter="\t"))
    entities[0].update(
        {"entity_kind": "region", "taxonomy": "geonames:admin1", "feature_code": "ADM1"}
    )
    _write_rows(entity_path, list(entities[0]), entities)
    _refresh_receipts(bundle)
    with pytest.raises(CatalogPublicationError, match="missing administrative corroboration"):
        publish_catalog(bundle, tmp_path / "releases", CONTEXT)
