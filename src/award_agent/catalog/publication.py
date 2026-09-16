"""Deterministic, offline publication of the prepared Milestone 1 source bundle.

The publication boundary intentionally has no planner dependency.  It consumes
only the compact local bundle and produces one immutable SQLite release plus its
canonical JSON receipt.  SQLite is used as a build store; Pydantic validates the
small boundary contracts and never materializes the catalog as a model graph.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator, Mapping
from datetime import date
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from math import isfinite
from pathlib import Path
from typing import Any
from zoneinfo import TZPATH, ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from award_agent.search_planning.knowledge import normalize_location_alias

CATALOG_SCHEMA_VERSION = "2"
SUPPORTED_CATALOG_SCHEMA_VERSIONS = frozenset({"1", CATALOG_SCHEMA_VERSION})
MANIFEST_FORMAT_VERSION = "2"
SUPPORTED_MANIFEST_FORMAT_VERSIONS = frozenset({"1", MANIFEST_FORMAT_VERSION})
DATABASE_FILENAME = "catalog.sqlite"
MANIFEST_FILENAME = "manifest.json"
REQUIRED_FILES = (
    "geonames_admin_corroboration.tsv",
    "geonames_airport_candidates.tsv",
    "geonames_base_aliases.tsv",
    "geonames_current_aliases.tsv",
    "geonames_entities.tsv",
    "geonames_iata_crossrefs.tsv",
    "ourairports_airports.csv",
    "ourairports_countries.csv",
    "ourairports_regions.csv",
    "quarantine.tsv",
)
RAW_RECORDS_FILENAME = "source_raw_records.tsv"
SOURCE_SCHEMAS_FILENAME = "source_schemas.json"
RAW_RECORD_HEADERS = ("source_name", "source_record_id", "values_json")
EXPECTED_HEADERS = {
    "geonames_admin_corroboration.tsv": (
        "geoname_id",
        "expected_feature_code",
        "corroborated_by_active_allcountries",
    ),
    "geonames_airport_candidates.tsv": (
        "geoname_id",
        "name",
        "asciiname",
        "country_code",
        "latitude",
        "longitude",
        "timezone",
        "modification_date",
        "source_record_id",
    ),
    "geonames_base_aliases.tsv": (
        "geoname_id",
        "entity_id",
        "alias",
        "alias_kind",
        "source_record_id",
    ),
    "geonames_current_aliases.tsv": (
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
    ),
    "geonames_entities.tsv": (
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
    ),
    "geonames_iata_crossrefs.tsv": (
        "alternate_name_id",
        "iata_code",
        "geoname_id",
        "country_code",
        "timezone",
        "is_historic",
        "from",
        "to",
        "source_record_id",
    ),
    "ourairports_airports.csv": (
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
    ),
    "ourairports_countries.csv": ("id", "code", "name", "continent", "wikipedia_link", "keywords"),
    "ourairports_regions.csv": (
        "id",
        "code",
        "local_code",
        "name",
        "continent",
        "iso_country",
        "wikipedia_link",
        "keywords",
    ),
    "quarantine.tsv": ("record_kind", "source_record_id", "reason_code", "detail"),
}
OURAIRPORTS_REQUIRED_HEADERS = {
    "ourairports_airports.csv": EXPECTED_HEADERS["ourairports_airports.csv"],
    "ourairports_countries.csv": EXPECTED_HEADERS["ourairports_countries.csv"],
    "ourairports_regions.csv": EXPECTED_HEADERS["ourairports_regions.csv"],
}
RULE_DEFINITIONS = {
    "normalization": "NFKC, casefold, whitespace-collapse; no fuzzy matching",
    "reconciliation": "current IATA evidence, exact country, valid IANA timezone, one-to-one candidate",
}


def _rule_receipts() -> dict[str, dict[str, str]]:
    return {
        name: {"id": f"{name}-v1", "sha256": hashlib.sha256(text.encode()).hexdigest()}
        for name, text in sorted(RULE_DEFINITIONS.items())
    }


def _timezone_tree_digest(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for root in sorted(paths, key=str):
        if not root.is_dir():
            continue
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=str):
            digest.update(str(root).encode())
            digest.update(str(path.relative_to(root)).encode())
            digest.update(_sha256(path).encode())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def timezone_validator_identity() -> str:
    """Identify the actual local IANA validator, not a caller-provided label."""
    try:
        tzdata_version = version("tzdata")
    except PackageNotFoundError:
        tzdata_version = "system-zoneinfo"
    return (
        f"{tzdata_version};zoneinfo_tree_sha256={_timezone_tree_digest(tuple(map(Path, TZPATH)))}"
    )


def _publication_context(context: PublicationContext) -> dict[str, str]:
    return {**context.model_dump(mode="json"), "timezone_validator": timezone_validator_identity()}


class CatalogPublicationError(ValueError):
    """A bundle or release cannot safely be published or inspected."""


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PublicationContext(_Contract):
    """Owner-supplied reproducibility inputs which are absent from the bundle."""

    source_date: date


class PublicationResult(_Contract):
    release_id: str
    release_path: Path
    manifest_path: Path
    database_path: Path
    logical_content_sha256: str
    database_sha256: str
    counts: dict[str, int]


class Receipt(_Contract):
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class BundleManifest(_Contract):
    bundle_id: str = Field(min_length=1)
    format_version: str
    outputs: dict[str, Receipt]
    source_files_read: dict[str, Receipt] = {}
    filters: dict[str, Any] = {}
    purpose: str = ""
    record_counts: dict[str, int] = {}
    limitations: tuple[str, ...] = ()


class DatabaseReceipt(Receipt):
    filename: str = DATABASE_FILENAME


class SourceBundleReceipt(_Contract):
    bundle_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_receipts: dict[str, Receipt]
    source_files_read: dict[str, Receipt]
    filters: dict[str, Any]
    purpose: str
    record_counts: dict[str, int]
    limitations: tuple[str, ...]


class QuarantineReceipt(_Contract):
    reason_counts: dict[str, int]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    detail_storage: str


class CatalogManifest(_Contract):
    format_version: str
    catalog_schema_version: str
    release_id: str
    logical_content_sha256: str
    database: DatabaseReceipt
    source_bundle: SourceBundleReceipt
    publication_context: dict[str, str]
    rules: dict[str, dict[str, str]]
    counts: dict[str, int]
    coverage: dict[str, Any]
    quarantine: QuarantineReceipt


class _EntityRow(_Contract):
    entity_id: str
    entity_kind: str
    taxonomy: str
    geoname_id: str
    label: str
    asciiname: str = ""
    country_code: str = ""
    iso3: str = ""
    iso_numeric: str = ""
    continent: str = ""
    source_record_id: str
    feature_class: str = ""
    feature_code: str = ""
    latitude: str = ""
    longitude: str = ""
    admin1_code: str = ""
    admin2_code: str = ""
    population: str = ""
    timezone: str = ""
    modification_date: str = ""


class _CandidateRow(_Contract):
    geoname_id: str
    name: str
    asciiname: str = ""
    country_code: str
    latitude: str = ""
    longitude: str = ""
    timezone: str
    modification_date: str = ""
    source_record_id: str


class _IataRow(_Contract):
    alternate_name_id: str
    iata_code: str
    geoname_id: str
    country_code: str
    timezone: str
    is_historic: str = ""
    from_: str = Field(default="", alias="from")
    to: str = ""
    source_record_id: str

    @field_validator("iata_code")
    @classmethod
    def _iata(cls, value: str) -> str:
        if len(value) != 3 or not value.isascii() or not value.isalpha() or value != value.upper():
            raise ValueError("IATA code must be three uppercase ASCII letters")
        return value

    @field_validator("alternate_name_id")
    @classmethod
    def _alternate_id(cls, value: str) -> str:
        if not value.isdecimal():
            raise ValueError("alternate_name_id must be decimal")
        return value

    @field_validator("country_code")
    @classmethod
    def _country(cls, value: str) -> str:
        if len(value) != 2 or not value.isascii() or not value.isalpha() or value != value.upper():
            raise ValueError("country code must be two uppercase ASCII letters")
        return value

    @field_validator("is_historic")
    @classmethod
    def _historic(cls, value: str) -> str:
        if value not in {"", "1"}:
            raise ValueError("is_historic must be blank or 1")
        return value


class _AirportRow(_Contract):
    id: str
    ident: str = ""
    type: str
    name: str
    latitude_deg: str = ""
    longitude_deg: str = ""
    iso_country: str
    iso_region: str = ""
    scheduled_service: str
    icao_code: str = ""
    iata_code: str
    gps_code: str = ""
    local_code: str = ""
    wikipedia_link: str = ""

    @field_validator("iata_code")
    @classmethod
    def _iata(cls, value: str) -> str:
        if len(value) != 3 or not value.isascii() or not value.isalpha() or value != value.upper():
            raise ValueError("IATA code must be three uppercase ASCII letters")
        return value


class _CountryRow(_Contract):
    id: str
    code: str
    name: str
    continent: str = ""
    wikipedia_link: str = ""
    keywords: str = ""


class _RegionRow(_Contract):
    id: str
    code: str
    local_code: str = ""
    name: str
    continent: str = ""
    iso_country: str
    wikipedia_link: str = ""
    keywords: str = ""


class _AdminCorroborationRow(_Contract):
    geoname_id: str
    expected_feature_code: str
    corroborated_by_active_allcountries: str


class _InputQuarantineRow(_Contract):
    record_kind: str
    source_record_id: str
    reason_code: str
    detail: str = ""


class _AliasRow(_Contract):
    geoname_id: str
    entity_id: str
    alias: str = ""
    alias_kind: str = ""
    source_record_id: str = ""
    alternate_name_id: str = ""
    iso_language: str = ""
    alternate_name: str = ""
    is_preferred_name: str = ""
    is_short_name: str = ""
    is_colloquial: str = ""
    is_historic: str = ""
    from_: str = Field(default="", alias="from")
    to: str = ""

    def value(self) -> str:
        return self.alias or self.alternate_name


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source_key(filename: str, source_record_id: str) -> str:
    return f"{filename}:{source_record_id}"


RAW_SOURCE_BY_PREFIX = {
    "allCountries": "allCountries.txt",
    "countryInfo": "countryInfo.txt",
    "admin1CodesASCII": "admin1CodesASCII.txt",
    "admin2Codes": "admin2Codes.txt",
    "alternateNamesV2": "alternateNamesV2.txt",
}
RAW_SOURCE_BY_DERIVED_FILE = {
    "ourairports_airports.csv": "airports.csv",
    "ourairports_countries.csv": "countries.csv",
    "ourairports_regions.csv": "regions.csv",
}


def _expected_raw_source_name(filename: str, source_record_id: str) -> str | None:
    """Resolve a derived evidence record to its one allowed raw source file."""
    if source_record_id.startswith("ourairports:"):
        return RAW_SOURCE_BY_DERIVED_FILE.get(filename)
    return RAW_SOURCE_BY_PREFIX.get(source_record_id.split(":", 1)[0])


def _reader(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t" if path.suffix == ".tsv" else ",")
        fields = tuple(reader.fieldnames or ())
        if path.name in OURAIRPORTS_REQUIRED_HEADERS:
            if len(fields) != len(set(fields)) or set(
                OURAIRPORTS_REQUIRED_HEADERS[path.name]
            ) - set(fields):
                raise CatalogPublicationError(f"unexpected header in {path.name}")
        elif fields != EXPECTED_HEADERS[path.name]:
            raise CatalogPublicationError(f"unexpected header in {path.name}")
        yield from reader


def _ensure_bundle(bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise CatalogPublicationError("prepared bundle manifest is missing")
    try:
        parsed = BundleManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise CatalogPublicationError("prepared bundle manifest is invalid JSON") from exc
    if parsed.format_version not in {"1", "2"}:
        raise CatalogPublicationError("prepared bundle manifest has unsupported identity")
    required_files = REQUIRED_FILES + (
        (RAW_RECORDS_FILENAME, SOURCE_SCHEMAS_FILENAME) if parsed.format_version == "2" else ()
    )
    for filename in required_files:
        receipt = parsed.outputs.get(filename)
        path = bundle / filename
        if receipt is None or not path.is_file():
            raise CatalogPublicationError(f"prepared bundle is missing required file: {filename}")
        if receipt.bytes != path.stat().st_size or receipt.sha256 != _sha256(path):
            raise CatalogPublicationError(f"prepared bundle receipt mismatch: {filename}")
    return parsed.model_dump(mode="json")


def _validate_headers(bundle: Path) -> None:
    for filename in REQUIRED_FILES:
        path = bundle / filename
        with path.open(encoding="utf-8", newline="") as input_file:
            reader = csv.reader(input_file, delimiter="\t" if path.suffix == ".tsv" else ",")
            fields = tuple(next(reader, ()))
            if filename in OURAIRPORTS_REQUIRED_HEADERS:
                valid = len(fields) == len(set(fields)) and not (
                    set(OURAIRPORTS_REQUIRED_HEADERS[filename]) - set(fields)
                )
            else:
                valid = fields == EXPECTED_HEADERS[filename]
            if not valid:
                raise CatalogPublicationError(f"unexpected header in {filename}")


def _load_raw_source_records(connection: sqlite3.Connection, bundle: Path) -> None:
    """Load v2 lossless sidecars before derived evidence references them.

    Values remain an ordered JSON array paired with a separately received source
    header.  They are deliberately not query aliases or relationship evidence.
    """
    schemas_path = bundle / SOURCE_SCHEMAS_FILENAME
    records_path = bundle / RAW_RECORDS_FILENAME
    if not schemas_path.is_file() and not records_path.is_file():
        return  # v1 fixtures remain useful publication-contract coverage.
    if not schemas_path.is_file() or not records_path.is_file():
        raise CatalogPublicationError("incomplete lossless source-record sidecars")
    try:
        schemas = json.loads(schemas_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CatalogPublicationError("invalid source schema sidecar") from exc
    if not isinstance(schemas, dict) or not schemas:
        raise CatalogPublicationError("source schema sidecar is empty or malformed")
    for source_name, headers in sorted(schemas.items()):
        if (
            not isinstance(source_name, str)
            or not isinstance(headers, list)
            or not all(isinstance(header, str) and header for header in headers)
            or len(headers) != len(set(headers))
        ):
            raise CatalogPublicationError(f"invalid source schema: {source_name!r}")
        if source_name not in {
            "allCountries.txt",
            "countryInfo.txt",
            "admin1CodesASCII.txt",
            "admin2Codes.txt",
            "alternateNamesV2.txt",
            "airports.csv",
            "countries.csv",
            "regions.csv",
        }:
            raise CatalogPublicationError(f"unexpected source schema: {source_name}")
        connection.execute(
            "INSERT INTO source_schema VALUES (?,?)", (source_name, _canonical_json(headers))
        )
    with records_path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file, delimiter="\t")
        if tuple(reader.fieldnames or ()) != RAW_RECORD_HEADERS:
            raise CatalogPublicationError("unexpected raw source-record header")
        for raw in reader:
            source_name = raw.get("source_name", "")
            source_record_id = raw.get("source_record_id", "")
            if source_name not in schemas or not source_record_id:
                raise CatalogPublicationError("raw source-record schema or identity is invalid")
            try:
                values = json.loads(raw.get("values_json", ""))
            except json.JSONDecodeError as exc:
                raise CatalogPublicationError("raw source-record values are invalid JSON") from exc
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise CatalogPublicationError("raw source-record values must be a string array")
            if len(values) != len(schemas[source_name]):
                raise CatalogPublicationError("raw source-record value count disagrees with schema")
            key = _source_key(source_name, source_record_id)
            try:
                connection.execute(
                    "INSERT INTO source_record(source_record_key, artifact_name, source_record_id, compact_row_id, source_schema_name, raw_values_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        source_name,
                        source_record_id,
                        source_record_id,
                        source_name,
                        _canonical_json(values),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise CatalogPublicationError(
                    f"duplicate raw source record: {source_name}/{source_record_id}"
                ) from exc


def _create_source_record_lookup_index(connection: sqlite3.Connection) -> None:
    """Index exact raw evidence joins before derived records are loaded."""
    connection.execute(
        "CREATE INDEX source_record_raw_identity_idx "
        "ON source_record(source_schema_name, source_record_id)"
    )


def _create_deferred_source_record_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE INDEX source_record_artifact_idx ON source_record(artifact_name, source_record_id)"
    )


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
CREATE TABLE catalog_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_artifact (
  artifact_name TEXT PRIMARY KEY, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL
);
CREATE TABLE source_schema (
  source_name TEXT PRIMARY KEY, headers_json TEXT NOT NULL
);
CREATE TABLE source_record (
  source_record_key TEXT PRIMARY KEY, artifact_name TEXT NOT NULL REFERENCES source_artifact,
  source_record_id TEXT NOT NULL, compact_row_id TEXT NOT NULL,
  source_schema_name TEXT REFERENCES source_schema, raw_values_json TEXT,
  UNIQUE(artifact_name, source_record_id)
);
CREATE TABLE taxonomy (taxonomy_id TEXT PRIMARY KEY);
CREATE TABLE entity (
  entity_id TEXT PRIMARY KEY, geoname_id TEXT NOT NULL UNIQUE, entity_kind TEXT NOT NULL,
  taxonomy_id TEXT NOT NULL REFERENCES taxonomy, label TEXT NOT NULL, asciiname TEXT NOT NULL,
  country_code TEXT NOT NULL, iso3 TEXT NOT NULL, iso_numeric TEXT NOT NULL, continent TEXT NOT NULL,
  feature_class TEXT NOT NULL, feature_code TEXT NOT NULL, latitude TEXT NOT NULL, longitude TEXT NOT NULL,
  admin1_code TEXT NOT NULL, admin2_code TEXT NOT NULL, population TEXT NOT NULL, timezone TEXT NOT NULL,
  modification_date TEXT NOT NULL, source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE entity_alias_evidence (
  alias_evidence_id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entity,
  normalized_alias TEXT NOT NULL, display_alias TEXT NOT NULL, alias_kind TEXT NOT NULL,
  language TEXT NOT NULL, source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE geonames_admin_corroboration (
  entity_id TEXT PRIMARY KEY REFERENCES entity, expected_feature_code TEXT NOT NULL,
  corroborated_by_active_allcountries TEXT NOT NULL,
  source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE ourairports_country (
  country_id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, continent TEXT NOT NULL,
  source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE ourairports_region (
  region_id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, local_code TEXT NOT NULL, name TEXT NOT NULL,
  continent TEXT NOT NULL, iso_country TEXT NOT NULL REFERENCES ourairports_country(code), source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE geonames_airport_candidate (
  candidate_id TEXT PRIMARY KEY, geoname_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, asciiname TEXT NOT NULL,
  country_code TEXT NOT NULL, latitude TEXT NOT NULL, longitude TEXT NOT NULL, timezone TEXT NOT NULL,
  modification_date TEXT NOT NULL, source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE geonames_iata_evidence (
  evidence_id TEXT PRIMARY KEY, iata_code TEXT NOT NULL, candidate_id TEXT NOT NULL REFERENCES geonames_airport_candidate,
  country_code TEXT NOT NULL, timezone TEXT NOT NULL, is_historic TEXT NOT NULL, valid_from TEXT NOT NULL,
  valid_to TEXT NOT NULL, source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE airport (
  airport_id TEXT PRIMARY KEY, ourairports_id TEXT NOT NULL UNIQUE REFERENCES ourairports_endpoint_input(ourairports_id), iata_code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL, airport_type TEXT NOT NULL, iso_country TEXT NOT NULL, iso_region TEXT NOT NULL,
  latitude TEXT NOT NULL, longitude TEXT NOT NULL, timezone TEXT NOT NULL,
  source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE ourairports_endpoint_input (
  ourairports_id TEXT PRIMARY KEY, iata_code TEXT NOT NULL UNIQUE, iso_country TEXT NOT NULL REFERENCES ourairports_country(code),
  iso_region TEXT NOT NULL REFERENCES ourairports_region(code), source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE airport_alias (
  alias_evidence_id TEXT PRIMARY KEY, airport_id TEXT NOT NULL REFERENCES airport,
  normalized_alias TEXT NOT NULL, display_alias TEXT NOT NULL, alias_kind TEXT NOT NULL,
  source_record_key TEXT NOT NULL REFERENCES source_record
);
CREATE TABLE airport_reconciliation (
  airport_id TEXT PRIMARY KEY REFERENCES airport, iata_code TEXT NOT NULL, candidate_id TEXT NOT NULL REFERENCES geonames_airport_candidate,
  evidence_id TEXT NOT NULL REFERENCES geonames_iata_evidence, outcome TEXT NOT NULL, rule_id TEXT NOT NULL
);
CREATE TABLE quarantine_record (
  quarantine_id TEXT PRIMARY KEY, record_kind TEXT NOT NULL, source_record_key TEXT,
  subject_id TEXT NOT NULL, reason_code TEXT NOT NULL, detail TEXT NOT NULL, rule_id TEXT NOT NULL,
  FOREIGN KEY(source_record_key) REFERENCES source_record
);
CREATE INDEX entity_alias_exact_idx ON entity_alias_evidence(normalized_alias, entity_id, alias_evidence_id);
CREATE INDEX airport_alias_exact_idx ON airport_alias(normalized_alias, airport_id, alias_evidence_id);
CREATE INDEX entity_taxonomy_idx ON entity(taxonomy_id, entity_id);
CREATE INDEX airport_country_region_idx ON airport(iso_country, iso_region, iata_code);
CREATE INDEX iata_evidence_iata_idx ON geonames_iata_evidence(iata_code, candidate_id, evidence_id);
CREATE INDEX quarantine_reason_idx ON quarantine_record(reason_code, subject_id);
"""


def _insert_source_record(
    connection: sqlite3.Connection,
    filename: str,
    source_record_id: str,
    compact_row_id: str | None = None,
) -> str:
    if not source_record_id.strip():
        raise CatalogPublicationError(f"empty source record identity in {filename}")
    expected_source = _expected_raw_source_name(filename, source_record_id)
    raw_match = (
        connection.execute(
            "SELECT source_record_key FROM source_record WHERE source_record_id = ? AND source_schema_name = ?",
            (source_record_id, expected_source),
        ).fetchall()
        if expected_source is not None
        else []
    )
    if len(raw_match) == 1:
        return str(raw_match[0][0])
    if len(raw_match) > 1:
        raise CatalogPublicationError(f"ambiguous raw source record identity: {source_record_id}")
    if (
        expected_source is not None
        and connection.execute("SELECT COUNT(*) FROM source_schema").fetchone()[0]
    ):
        raise CatalogPublicationError(f"missing retained raw source record: {source_record_id}")
    key = _source_key(filename, source_record_id)
    connection.execute(
        "INSERT OR IGNORE INTO source_record(source_record_key, artifact_name, source_record_id, compact_row_id, source_schema_name, raw_values_json) VALUES (?, ?, ?, ?, NULL, NULL)",
        (key, filename, source_record_id, compact_row_id or source_record_id),
    )
    return key


def _row(model: type[_Contract], raw: Mapping[str, str], filename: str) -> Any:
    try:
        accepted = {
            field.alias or name: raw[field.alias or name]
            for name, field in model.model_fields.items()
            if (field.alias or name) in raw
        }
        return model.model_validate(accepted)
    except Exception as exc:  # Pydantic's detailed public error is useful at the boundary.
        raise CatalogPublicationError(f"invalid {filename} row: {exc}") from exc


def _require_nonblank(value: str, label: str) -> None:
    if not value.strip():
        raise CatalogPublicationError(f"blank required value: {label}")


def _require_finite_decimal(value: str, label: str) -> None:
    _require_nonblank(value, label)
    try:
        number = float(value)
    except ValueError as exc:
        raise CatalogPublicationError(f"invalid numeric value: {label}") from exc
    if not isfinite(number):
        raise CatalogPublicationError(f"non-finite numeric value: {label}")


def _valid_entity_shape(row: _EntityRow) -> bool:
    allowed = {
        ("country", "geonames:country", "A", "PCLI"),
        ("region", "geonames:admin1", "A", "ADM1"),
        ("region", "geonames:admin2", "A", "ADM2"),
        ("region", "geonames:continent", "L", "CONT"),
        ("region", "geonames:geographic_region", "L", "RGN"),
        ("region", "geonames:geographic_region", "L", "RGNE"),
    }
    return (row.entity_kind, row.taxonomy, row.feature_class, row.feature_code) in allowed or (
        row.entity_kind == "city"
        and row.taxonomy == "geonames:populated_place"
        and row.feature_class == "P"
        and row.feature_code
        in {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "STLMT"}
    )


def _load_entities(connection: sqlite3.Connection, bundle: Path) -> None:
    filename = "geonames_entities.tsv"
    for raw in _reader(bundle / filename):
        row = _row(_EntityRow, raw, filename)
        if row.entity_id != f"geonames:{row.geoname_id}" or not _valid_entity_shape(row):
            raise CatalogPublicationError(f"invalid entity identity: {row.entity_id}")
        for value, label in (
            (row.entity_id, "entity_id"),
            (row.geoname_id, "geoname_id"),
            (row.label, "entity label"),
            (row.source_record_id, "entity source_record_id"),
        ):
            _require_nonblank(value, label)
        if row.entity_kind == "city":
            _require_finite_decimal(row.latitude, "city latitude")
            _require_finite_decimal(row.longitude, "city longitude")
        key = _insert_source_record(connection, filename, row.source_record_id)
        connection.execute(
            "INSERT OR IGNORE INTO taxonomy(taxonomy_id) VALUES (?)", (row.taxonomy,)
        )
        try:
            connection.execute(
                """INSERT INTO entity VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row.entity_id,
                    row.geoname_id,
                    row.entity_kind,
                    row.taxonomy,
                    row.label,
                    row.asciiname,
                    row.country_code,
                    row.iso3,
                    row.iso_numeric,
                    row.continent,
                    row.feature_class,
                    row.feature_code,
                    row.latitude,
                    row.longitude,
                    row.admin1_code,
                    row.admin2_code,
                    row.population,
                    row.timezone,
                    row.modification_date,
                    key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(f"duplicate or dangling entity: {row.entity_id}") from exc


def _load_aliases(connection: sqlite3.Connection, bundle: Path, filename: str) -> None:
    for raw in _reader(bundle / filename):
        row = _row(_AliasRow, raw, filename)
        value = row.value()
        normalized = normalize_location_alias(value)
        if not normalized or row.entity_id != f"geonames:{row.geoname_id}":
            raise CatalogPublicationError(f"invalid alias identity in {filename}")
        if filename == "geonames_base_aliases.tsv":
            entity_source = connection.execute(
                """SELECT source.source_record_id FROM entity
                   JOIN source_record AS source ON source.source_record_key = entity.source_record_key
                   WHERE entity.entity_id = ?""",
                (row.entity_id,),
            ).fetchone()
            if (
                row.alias_kind not in {"name", "asciiname"}
                or entity_source is None
                or row.source_record_id != entity_source[0]
            ):
                raise CatalogPublicationError(f"invalid base alias evidence: {row.geoname_id}")
        else:
            if (
                not row.alternate_name_id
                or not row.iso_language
                or not re.fullmatch(
                    r"(?:abbr|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)", row.iso_language
                )
                or row.is_historic
                or row.is_colloquial
                or row.to
            ):
                raise CatalogPublicationError(
                    f"alias violates current-alias filter: {row.alternate_name_id}"
                )
        native_id = row.alternate_name_id or f"{row.geoname_id}:{row.alias_kind}:{normalized}"
        source_id = row.source_record_id or f"alternateNamesV2:{native_id}"
        key = _insert_source_record(connection, filename, source_id, native_id)
        evidence_id = f"{filename}:{native_id}"
        try:
            connection.execute(
                "INSERT INTO entity_alias_evidence VALUES (?,?,?,?,?,?,?)",
                (
                    evidence_id,
                    row.entity_id,
                    normalized,
                    value,
                    row.alias_kind or "current_alias",
                    row.iso_language,
                    key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(
                f"duplicate or dangling alias evidence: {evidence_id}"
            ) from exc


def _load_admin_corroboration(connection: sqlite3.Connection, bundle: Path) -> None:
    filename = "geonames_admin_corroboration.tsv"
    for raw in _reader(bundle / filename):
        row = _row(_AdminCorroborationRow, raw, filename)
        geoname_id = row.geoname_id
        feature_code = row.expected_feature_code
        corroborated = row.corroborated_by_active_allcountries
        if not geoname_id or not feature_code or corroborated != "true":
            raise CatalogPublicationError(f"invalid administrative corroboration: {geoname_id}")
        entity = connection.execute(
            "SELECT taxonomy_id, feature_code FROM entity WHERE entity_id = ?",
            (f"geonames:{geoname_id}",),
        ).fetchone()
        if (
            entity is None
            or entity[0] not in {"geonames:admin1", "geonames:admin2"}
            or entity[1] != feature_code
        ):
            raise CatalogPublicationError(
                f"administrative corroboration disagrees with entity: {geoname_id}"
            )
        key = _insert_source_record(connection, filename, f"admin-corroboration:{geoname_id}")
        try:
            connection.execute(
                "INSERT INTO geonames_admin_corroboration VALUES (?,?,?,?)",
                (f"geonames:{geoname_id}", feature_code, corroborated, key),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(
                f"dangling or duplicate administrative corroboration: {geoname_id}"
            ) from exc
    missing = connection.execute(
        """SELECT entity_id FROM entity
           WHERE taxonomy_id IN ('geonames:admin1', 'geonames:admin2')
           EXCEPT SELECT entity_id FROM geonames_admin_corroboration
           ORDER BY entity_id LIMIT 1"""
    ).fetchone()
    if missing is not None:
        raise CatalogPublicationError(f"missing administrative corroboration: {missing[0]}")


def _load_ourairports_metadata(connection: sqlite3.Connection, bundle: Path) -> None:
    for filename, model, table, columns in (
        (
            "ourairports_countries.csv",
            _CountryRow,
            "ourairports_country",
            ("id", "code", "name", "continent"),
        ),
        (
            "ourairports_regions.csv",
            _RegionRow,
            "ourairports_region",
            ("id", "code", "local_code", "name", "continent", "iso_country"),
        ),
    ):
        for raw in _reader(bundle / filename):
            row = _row(model, raw, filename)
            native_id = row.id
            for value, label in (
                (native_id, "OurAirports ID"),
                (row.code, "OurAirports code"),
                (row.name, "OurAirports name"),
            ):
                _require_nonblank(value, label)
            if filename == "ourairports_regions.csv":
                _require_nonblank(row.iso_country, "OurAirports region country")
            key = _insert_source_record(connection, filename, f"ourairports:{native_id}")
            values = tuple(getattr(row, column) for column in columns)
            try:
                connection.execute(
                    f"INSERT INTO {table} VALUES ({','.join('?' for _ in range(len(values) + 1))})",
                    (*values, key),
                )
            except sqlite3.IntegrityError as exc:
                raise CatalogPublicationError(
                    f"duplicate OurAirports metadata in {filename}: {native_id}"
                ) from exc


def _load_candidates(connection: sqlite3.Connection, bundle: Path) -> None:
    filename = "geonames_airport_candidates.tsv"
    for raw in _reader(bundle / filename):
        row = _row(_CandidateRow, raw, filename)
        for value, label in (
            (row.geoname_id, "candidate geoname_id"),
            (row.name, "candidate name"),
            (row.country_code, "candidate country"),
            (row.source_record_id, "candidate source"),
        ):
            _require_nonblank(value, label)
        _require_finite_decimal(row.latitude, "candidate latitude")
        _require_finite_decimal(row.longitude, "candidate longitude")
        if row.source_record_id != f"allCountries:{row.geoname_id}":
            raise CatalogPublicationError(
                f"airport candidate source identity disagrees: {row.geoname_id}"
            )
        key = _insert_source_record(connection, filename, row.source_record_id)
        try:
            connection.execute(
                "INSERT INTO geonames_airport_candidate VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    f"geonames:{row.geoname_id}",
                    row.geoname_id,
                    row.name,
                    row.asciiname,
                    row.country_code,
                    row.latitude,
                    row.longitude,
                    row.timezone,
                    row.modification_date,
                    key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(f"duplicate airport candidate: {row.geoname_id}") from exc


def _load_iata_evidence(connection: sqlite3.Connection, bundle: Path) -> None:
    filename = "geonames_iata_crossrefs.tsv"
    for raw in _reader(bundle / filename):
        row = _row(_IataRow, raw, filename)
        if row.source_record_id != f"alternateNamesV2:{row.alternate_name_id}":
            raise CatalogPublicationError(
                f"IATA evidence source identity disagrees: {row.alternate_name_id}"
            )
        candidate = connection.execute(
            "SELECT country_code, timezone, source_record_key FROM geonames_airport_candidate WHERE candidate_id = ?",
            (f"geonames:{row.geoname_id}",),
        ).fetchone()
        if candidate is None:
            raise CatalogPublicationError(
                f"IATA evidence cites missing candidate: {row.geoname_id}"
            )
        # The cross-reference and airport-candidate source records are intentionally
        # distinct GeoNames records.  Their shared candidate facts must agree.
        if tuple(candidate[:2]) != (row.country_code, row.timezone):
            raise CatalogPublicationError(
                f"IATA evidence disagrees with candidate: {row.alternate_name_id}"
            )
        key = _insert_source_record(connection, filename, row.source_record_id)
        try:
            connection.execute(
                "INSERT INTO geonames_iata_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    f"{filename}:{row.alternate_name_id}",
                    row.iata_code,
                    f"geonames:{row.geoname_id}",
                    row.country_code,
                    row.timezone,
                    row.is_historic,
                    row.from_,
                    row.to,
                    key,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(
                f"duplicate IATA evidence: {row.alternate_name_id}"
            ) from exc


def _quarantine(
    connection: sqlite3.Connection,
    *,
    subject_id: str,
    source_key: str | None,
    reason: str,
    detail: str,
    rule_id: str,
) -> None:
    quarantine_id = f"publication:{reason}:{subject_id}"
    connection.execute(
        "INSERT INTO quarantine_record VALUES (?,?,?,?,?,?,?)",
        (quarantine_id, "airport_endpoint", source_key, subject_id, reason, detail, rule_id),
    )


def _load_airports_and_reconcile(
    connection: sqlite3.Connection, bundle: Path, context: PublicationContext
) -> None:
    filename = "ourairports_airports.csv"
    # Stage all retained endpoints first.  Reconciliation may then enforce the
    # reverse candidate-to-IATA cardinality without depending on source order.
    for raw in _reader(bundle / filename):
        row = _row(_AirportRow, raw, filename)
        _require_nonblank(row.id, "airport ID")
        _require_nonblank(row.iata_code, "airport IATA")
        if not row.iso_region.startswith(f"{row.iso_country}-"):
            raise CatalogPublicationError(
                f"airport region is not prefixed by airport country: {row.iso_region}"
            )
        region_country = connection.execute(
            "SELECT iso_country FROM ourairports_region WHERE code = ?", (row.iso_region,)
        ).fetchone()
        if region_country is None or region_country[0] != row.iso_country:
            raise CatalogPublicationError(
                f"airport region country disagrees with airport country: {row.iso_region}"
            )
        key = _insert_source_record(connection, filename, f"ourairports:{row.id}", row.id)
        try:
            connection.execute(
                "INSERT INTO ourairports_endpoint_input VALUES (?,?,?,?,?)",
                (row.id, row.iata_code, row.iso_country, row.iso_region, key),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(
                f"duplicate or dangling OurAirports endpoint/IATA: ourairports:{row.id}/{row.iata_code}"
            ) from exc
    for raw in _reader(bundle / filename):
        row = _row(_AirportRow, raw, filename)
        airport_id = f"ourairports:{row.id}"
        if row.type not in {"large_airport", "medium_airport"} or row.scheduled_service != "yes":
            raise CatalogPublicationError(f"endpoint violates bundle filter: {airport_id}")
        for value, label in (
            (row.id, "airport ID"),
            (row.name, "airport name"),
            (row.iso_country, "airport country"),
            (row.iso_region, "airport region"),
        ):
            _require_nonblank(value, label)
        _require_finite_decimal(row.latitude_deg, "airport latitude")
        _require_finite_decimal(row.longitude_deg, "airport longitude")
        key = _insert_source_record(connection, filename, f"ourairports:{row.id}", row.id)
        candidates = connection.execute(
            """SELECT e.candidate_id, e.evidence_id, e.country_code, e.timezone
               FROM geonames_iata_evidence e
               WHERE e.iata_code = ? AND e.is_historic = '' AND e.valid_to = ''
               ORDER BY e.candidate_id, e.evidence_id""",
            (row.iata_code,),
        ).fetchall()
        distinct = {candidate[0]: candidate for candidate in candidates}
        if not distinct:
            _quarantine(
                connection,
                subject_id=airport_id,
                source_key=key,
                reason="iata_no_eligible_geonames_candidate",
                detail=row.iata_code,
                rule_id=_rule_receipts()["reconciliation"]["id"],
            )
            continue
        if len(distinct) != 1:
            _quarantine(
                connection,
                subject_id=airport_id,
                source_key=key,
                reason="iata_ambiguous_geonames_candidate",
                detail=row.iata_code,
                rule_id=_rule_receipts()["reconciliation"]["id"],
            )
            continue
        candidate_id, evidence_id, country, timezone = distinct[min(distinct)]
        iata_count = connection.execute(
            """SELECT COUNT(DISTINCT e.iata_code) FROM geonames_iata_evidence e
               JOIN ourairports_endpoint_input o ON o.iata_code = e.iata_code
               WHERE e.candidate_id = ? AND e.is_historic = '' AND e.valid_to = ''""",
            (candidate_id,),
        ).fetchone()[0]
        if iata_count != 1:
            _quarantine(
                connection,
                subject_id=airport_id,
                source_key=key,
                reason="iata_candidate_multiple_current_iatas",
                detail=candidate_id,
                rule_id=_rule_receipts()["reconciliation"]["id"],
            )
            continue
        if country != row.iso_country:
            _quarantine(
                connection,
                subject_id=airport_id,
                source_key=key,
                reason="iata_country_conflict",
                detail=f"{row.iso_country}!={country}",
                rule_id=_rule_receipts()["reconciliation"]["id"],
            )
            continue
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            _quarantine(
                connection,
                subject_id=airport_id,
                source_key=key,
                reason="iata_timezone_unusable",
                detail=timezone,
                rule_id=_rule_receipts()["reconciliation"]["id"],
            )
            continue
        try:
            connection.execute(
                "INSERT INTO airport VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    airport_id,
                    row.id,
                    row.iata_code,
                    row.name,
                    row.type,
                    row.iso_country,
                    row.iso_region,
                    row.latitude_deg,
                    row.longitude_deg,
                    timezone,
                    key,
                ),
            )
            connection.execute(
                "INSERT INTO airport_alias VALUES (?,?,?,?,?,?)",
                (
                    f"ourairports_airports.csv:{row.id}:official_name",
                    airport_id,
                    normalize_location_alias(row.name),
                    row.name,
                    "official_name",
                    key,
                ),
            )
            connection.execute(
                "INSERT INTO airport_reconciliation VALUES (?,?,?,?,?,?)",
                (
                    airport_id,
                    row.iata_code,
                    candidate_id,
                    evidence_id,
                    "accepted",
                    _rule_receipts()["reconciliation"]["id"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise CatalogPublicationError(f"duplicate airport publication: {airport_id}") from exc


def _load_input_quarantine(
    connection: sqlite3.Connection, bundle: Path, context: PublicationContext
) -> None:
    filename = "quarantine.tsv"
    for raw in _reader(bundle / filename):
        row = _row(_InputQuarantineRow, raw, filename)
        source_id = row.source_record_id
        source_key = _insert_source_record(connection, filename, source_id) if source_id else None
        subject = source_id or row.record_kind or "unknown"
        connection.execute(
            "INSERT INTO quarantine_record VALUES (?,?,?,?,?,?,?)",
            (
                f"source:{filename}:{subject}:{row.reason_code}",
                row.record_kind or "source",
                source_key,
                subject,
                f"source_{row.reason_code}",
                row.detail,
                "prepared-bundle-v1",
            ),
        )


def _logical_digest(connection: sqlite3.Connection) -> str:
    """Hash schema-independent ordered rows, not SQLite's variable byte layout."""
    digest = hashlib.sha256()
    tables: tuple[str, ...] = (
        "source_record",
        "taxonomy",
        "entity",
        "entity_alias_evidence",
        "geonames_admin_corroboration",
        "ourairports_country",
        "ourairports_region",
        "ourairports_endpoint_input",
        "geonames_airport_candidate",
        "geonames_iata_evidence",
        "airport",
        "airport_alias",
        "airport_reconciliation",
        "quarantine_record",
    )
    if connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_schema'"
    ).fetchone():
        tables = ("source_schema", *tables)
    for table in tables:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
        cursor = connection.execute(f"SELECT * FROM {table} ORDER BY {','.join(columns)}")
        for row in cursor:
            digest.update(_canonical_json([table, list(row)]).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = (
        "taxonomy",
        "entity",
        "entity_alias_evidence",
        "geonames_admin_corroboration",
        "ourairports_country",
        "ourairports_region",
        "ourairports_endpoint_input",
        "geonames_airport_candidate",
        "geonames_iata_evidence",
        "airport",
        "airport_alias",
        "airport_reconciliation",
        "quarantine_record",
    )
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in tables
    }


def _coverage(connection: sqlite3.Connection) -> dict[str, Any]:
    entity_kinds = dict(
        connection.execute(
            "SELECT entity_kind, COUNT(*) FROM entity GROUP BY entity_kind ORDER BY entity_kind"
        )
    )
    taxonomies = dict(
        connection.execute(
            "SELECT taxonomy_id, COUNT(*) FROM entity GROUP BY taxonomy_id ORDER BY taxonomy_id"
        )
    )
    accepted = int(connection.execute("SELECT COUNT(*) FROM airport").fetchone()[0])
    endpoints = int(
        connection.execute("SELECT COUNT(*) FROM ourairports_endpoint_input").fetchone()[0]
    )
    return {
        "catalog_role": "geographic and airport identity facts only",
        "airport_group_coverage": "none_in_this_release",
        "route_coverage": "none",
        "airport_serving_relationships": "none",
        "entity_kinds": entity_kinds,
        "taxonomies": taxonomies,
        "endpoints": {
            "retained_input": endpoints,
            "accepted": accepted,
            "quarantined": endpoints - accepted,
        },
    }


def _quarantine_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    digest = hashlib.sha256()
    cursor = connection.execute("SELECT * FROM quarantine_record ORDER BY quarantine_id")
    for row in cursor:
        digest.update(_canonical_json(list(row)).encode("utf-8"))
        digest.update(b"\n")
    return {
        "reason_counts": dict(
            connection.execute(
                "SELECT reason_code, COUNT(*) FROM quarantine_record GROUP BY reason_code ORDER BY reason_code"
            )
        ),
        "digest": digest.hexdigest(),
        "detail_storage": "catalog.sqlite",
    }


def _source_artifact_receipts(
    connection: sqlite3.Connection, *, artifact_names: set[str] | None = None
) -> dict[str, dict[str, Any]]:
    where = (
        ""
        if artifact_names is None
        else " WHERE artifact_name IN ({})".format(",".join("?" for _ in artifact_names))
    )
    return {
        row[0]: {"bytes": row[1], "sha256": row[2]}
        for row in connection.execute(
            f"SELECT artifact_name, bytes, sha256 FROM source_artifact{where} ORDER BY artifact_name",
            tuple(sorted(artifact_names or ())),
        )
    }


def _release_identity(
    logical_digest: str,
    bundle_manifest_sha256: str,
    context: PublicationContext,
    *,
    catalog_schema_version: str = CATALOG_SCHEMA_VERSION,
) -> str:
    identity = {
        "catalog_schema_version": catalog_schema_version,
        "logical_content_sha256": logical_digest,
        "bundle_manifest_sha256": bundle_manifest_sha256,
        "publication_context": _publication_context(context),
        "rules": _rule_receipts(),
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _validate_connection(connection: sqlite3.Connection) -> None:
    errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    if errors:
        raise CatalogPublicationError(f"catalog foreign key violation: {errors[0]}")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise CatalogPublicationError(f"catalog integrity check failed: {integrity}")
    duplicate_iata = connection.execute(
        "SELECT iata_code FROM airport GROUP BY iata_code HAVING COUNT(*) != 1"
    ).fetchone()
    if duplicate_iata:
        raise CatalogPublicationError(f"published airport IATA is not unique: {duplicate_iata[0]}")


def _make_manifest(
    bundle_manifest: Mapping[str, Any],
    context: PublicationContext,
    *,
    release_id: str,
    logical_digest: str,
    database_sha256: str,
    database_bytes: int,
    counts: Mapping[str, int],
    bundle_manifest_sha256: str,
    coverage: Mapping[str, Any],
    quarantine: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = CatalogManifest.model_validate(
        {
            "format_version": MANIFEST_FORMAT_VERSION,
            "catalog_schema_version": CATALOG_SCHEMA_VERSION,
            "release_id": release_id,
            "logical_content_sha256": logical_digest,
            "database": {
                "filename": DATABASE_FILENAME,
                "bytes": database_bytes,
                "sha256": database_sha256,
            },
            "source_bundle": {
                "bundle_id": bundle_manifest["bundle_id"],
                "manifest_sha256": bundle_manifest_sha256,
                "output_receipts": bundle_manifest["outputs"],
                "source_files_read": bundle_manifest.get("source_files_read", {}),
                "filters": bundle_manifest["filters"],
                "purpose": bundle_manifest["purpose"],
                "record_counts": bundle_manifest["record_counts"],
                "limitations": bundle_manifest["limitations"],
            },
            "publication_context": _publication_context(context),
            "rules": _rule_receipts(),
            "counts": dict(sorted(counts.items())),
            "coverage": dict(coverage),
            "quarantine": dict(quarantine),
        }
    )
    return manifest.model_dump(mode="json")


def publish_catalog(
    bundle_path: Path, release_parent: Path, context: PublicationContext
) -> PublicationResult:
    """Publish one immutable release, atomically, from a verified local bundle.

    ``release_parent`` is intentionally caller-chosen and should be ignored local
    storage in 1A.  No current-pointer or serving selection is created.  The
    release parent is a single-writer publication boundary: an existing complete
    release ID is rejected and the final directory rename never merges content.
    """
    bundle = Path(bundle_path)
    parent = Path(release_parent)
    bundle_manifest = _ensure_bundle(bundle)
    _validate_headers(bundle)
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".catalog-staging-", dir=parent))
    try:
        database = staging / DATABASE_FILENAME
        connection = sqlite3.connect(database)
        try:
            connection.executescript(SCHEMA_SQL)
            artifacts = {
                **bundle_manifest.get("source_files_read", {}),
                **bundle_manifest["outputs"],
            }
            for filename, receipt in sorted(artifacts.items()):
                connection.execute(
                    "INSERT INTO source_artifact VALUES (?,?,?)",
                    (filename, receipt["bytes"], receipt["sha256"]),
                )
            connection.commit()
            connection.execute("BEGIN")
            _load_raw_source_records(connection, bundle)
            _create_source_record_lookup_index(connection)
            _load_entities(connection, bundle)
            _load_aliases(connection, bundle, "geonames_base_aliases.tsv")
            _load_aliases(connection, bundle, "geonames_current_aliases.tsv")
            _load_admin_corroboration(connection, bundle)
            _load_ourairports_metadata(connection, bundle)
            _load_candidates(connection, bundle)
            _load_iata_evidence(connection, bundle)
            _load_airports_and_reconcile(connection, bundle, context)
            _load_input_quarantine(connection, bundle, context)
            _create_deferred_source_record_indexes(connection)
            connection.execute("COMMIT")
            _validate_connection(connection)
            logical_digest = _logical_digest(connection)
            counts = _counts(connection)
            coverage = _coverage(connection)
            quarantine = _quarantine_summary(connection)
            bundle_manifest_sha256 = _sha256(bundle / MANIFEST_FILENAME)
            release_identity = _release_identity(logical_digest, bundle_manifest_sha256, context)
            release_id = f"m1a-{release_identity[:16]}"
            metadata = {
                "catalog_schema_version": CATALOG_SCHEMA_VERSION,
                "logical_content_sha256": logical_digest,
                "release_id": release_id,
                "bundle_id": bundle_manifest["bundle_id"],
                "bundle_manifest_sha256": bundle_manifest_sha256,
                "publication_context": _canonical_json(_publication_context(context)),
                "rules": _canonical_json(_rule_receipts()),
                "source_files_read": _canonical_json(bundle_manifest.get("source_files_read", {})),
                "bundle_metadata": _canonical_json(
                    {
                        "filters": bundle_manifest["filters"],
                        "purpose": bundle_manifest["purpose"],
                        "record_counts": bundle_manifest["record_counts"],
                        "limitations": bundle_manifest["limitations"],
                    }
                ),
            }
            connection.executemany(
                "INSERT INTO catalog_metadata VALUES (?,?)", sorted(metadata.items())
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        database_sha256 = _sha256(database)
        release = parent / release_id
        if release.exists():
            raise CatalogPublicationError(f"release already exists: {release_id}")
        manifest = _make_manifest(
            bundle_manifest,
            context,
            release_id=release_id,
            logical_digest=logical_digest,
            database_sha256=database_sha256,
            database_bytes=database.stat().st_size,
            counts=counts,
            bundle_manifest_sha256=bundle_manifest_sha256,
            coverage=coverage,
            quarantine=quarantine,
        )
        (staging / MANIFEST_FILENAME).write_text(_canonical_json(manifest) + "\n", encoding="utf-8")
        validate_release(staging, _allow_staging_directory=True)
        os.rename(staging, release)
        return PublicationResult(
            release_id=release_id,
            release_path=release,
            manifest_path=release / MANIFEST_FILENAME,
            database_path=release / DATABASE_FILENAME,
            logical_content_sha256=logical_digest,
            database_sha256=database_sha256,
            counts=counts,
        )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def validate_release(
    release_path: Path, *, _allow_staging_directory: bool = False
) -> dict[str, Any]:
    """Open a completed release read-only and validate its receipt and database."""
    release = Path(release_path)
    try:
        parsed = CatalogManifest.model_validate_json(
            (release / MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CatalogPublicationError("release manifest is unavailable or invalid") from exc
    manifest = parsed.model_dump(mode="json")
    if (
        parsed.format_version not in SUPPORTED_MANIFEST_FORMAT_VERSIONS
        or parsed.catalog_schema_version not in SUPPORTED_CATALOG_SCHEMA_VERSIONS
    ):
        raise CatalogPublicationError("unsupported catalog schema version")
    database = release / DATABASE_FILENAME
    receipt = parsed.database
    if (
        receipt.filename != DATABASE_FILENAME
        or database.name != DATABASE_FILENAME
        or not database.is_file()
        or receipt.sha256 != _sha256(database)
        or receipt.bytes != database.stat().st_size
    ):
        raise CatalogPublicationError("database receipt mismatch")
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        _validate_connection(connection)
        logical_digest = _logical_digest(connection)
        if logical_digest != parsed.logical_content_sha256:
            raise CatalogPublicationError("logical catalog digest mismatch")
        counts = _counts(connection)
        coverage = _coverage(connection)
        quarantine = _quarantine_summary(connection)
        output_receipts = _source_artifact_receipts(
            connection, artifact_names=set(parsed.source_bundle.output_receipts)
        )
        source_input_receipts = _source_artifact_receipts(
            connection, artifact_names=set(parsed.source_bundle.source_files_read)
        )
        metadata = dict(connection.execute("SELECT key, value FROM catalog_metadata ORDER BY key"))
        try:
            recorded_context = json.loads(metadata["publication_context"])
            if recorded_context.pop("timezone_validator", None) != timezone_validator_identity():
                raise CatalogPublicationError("timezone validator identity mismatch")
            context = PublicationContext.model_validate(recorded_context)
        except (KeyError, ValueError) as exc:
            raise CatalogPublicationError(
                "catalog publication context metadata is invalid"
            ) from exc
        expected_identity = _release_identity(
            logical_digest,
            metadata.get("bundle_manifest_sha256", ""),
            context,
            catalog_schema_version=parsed.catalog_schema_version,
        )
        expected_release_id = f"m1a-{expected_identity[:16]}"
        expected_metadata = {
            "catalog_schema_version": parsed.catalog_schema_version,
            "logical_content_sha256": logical_digest,
            "release_id": expected_release_id,
            "bundle_id": parsed.source_bundle.bundle_id,
            "bundle_manifest_sha256": parsed.source_bundle.manifest_sha256,
            "publication_context": _canonical_json(_publication_context(context)),
            "rules": _canonical_json(_rule_receipts()),
            "source_files_read": _canonical_json(
                {
                    name: receipt.model_dump(mode="json")
                    for name, receipt in parsed.source_bundle.source_files_read.items()
                }
            ),
            "bundle_metadata": _canonical_json(
                {
                    "filters": parsed.source_bundle.filters,
                    "purpose": parsed.source_bundle.purpose,
                    "record_counts": parsed.source_bundle.record_counts,
                    "limitations": parsed.source_bundle.limitations,
                }
            ),
        }
        if metadata != expected_metadata:
            raise CatalogPublicationError("catalog metadata mismatch")
        if (
            (not _allow_staging_directory and release.name != expected_release_id)
            or parsed.release_id != expected_release_id
            or parsed.counts != counts
            or parsed.coverage != coverage
            or parsed.quarantine.model_dump(mode="json") != quarantine
            or parsed.source_bundle.output_receipts
            != {name: Receipt.model_validate(receipt) for name, receipt in output_receipts.items()}
            or (
                parsed.catalog_schema_version == CATALOG_SCHEMA_VERSION
                and parsed.source_bundle.source_files_read
                != {
                    name: Receipt.model_validate(receipt)
                    for name, receipt in source_input_receipts.items()
                }
            )
            or parsed.rules != _rule_receipts()
            or parsed.publication_context != _publication_context(context)
        ):
            raise CatalogPublicationError("manifest-derived catalog fields mismatch")
    finally:
        connection.close()
    return manifest


def inspect_release(release_path: Path) -> dict[str, Any]:
    """Return small deterministic inspection data; this does not serve planner queries."""
    manifest = validate_release(release_path)
    database = Path(release_path) / DATABASE_FILENAME
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        quarantine = [
            {"reason_code": row[0], "count": row[1]}
            for row in connection.execute(
                "SELECT reason_code, COUNT(*) FROM quarantine_record GROUP BY reason_code ORDER BY reason_code"
            )
        ]
    finally:
        connection.close()
    return {
        "release_id": manifest["release_id"],
        "counts": manifest["counts"],
        "quarantine": quarantine,
    }
