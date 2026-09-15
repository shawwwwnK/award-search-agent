"""Prepare compact, current GeoNames and OurAirports inputs for Milestone 1.

The script is intentionally local and dependency-free.  It never calls a
network service and does not publish a planner knowledge snapshot.  Instead,
it turns the large acquired source files into a documented, inspectable input
bundle for the future importer.

Run without ``--prune-raw`` first.  The option removes only the known source
files superseded by a successfully verified bundle; it never removes the
bundle itself.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIRECTORY = ROOT / "data" / "source-inputs"
BUNDLE_NAME = "m1-current-travel-identity"

CITY_CODES = frozenset({"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG", "STLMT"})
ADMIN_SEAT_CODES = frozenset({"PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC"})
GEOGRAPHIC_REGION_CODES = frozenset({"RGN", "RGNE"})
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")

RAW_FILES_SUPERSEDED_BY_BUNDLE = (
    "allCountries.txt",
    "allCountries.zip",
    "alternateNamesV2.txt",
    "alternateNamesV2.zip",
    "hierarchy.txt",
    "hierarchy.zip",
    "timeZones.txt",
    "iso-languagecodes.txt",
    "countryInfo.txt",
    "admin1CodesASCII.txt",
    "admin2Codes.txt",
    "airports.csv",
    "countries.csv",
    "regions.csv",
)
SOURCE_FILES_READ = (
    "allCountries.txt",
    "alternateNamesV2.txt",
    "countryInfo.txt",
    "admin1CodesASCII.txt",
    "admin2Codes.txt",
    "airports.csv",
    "countries.csv",
    "regions.csv",
)


@dataclass(frozen=True)
class Feature:
    geoname_id: str
    name: str
    asciiname: str
    latitude: str
    longitude: str
    feature_class: str
    feature_code: str
    country_code: str
    admin1_code: str
    admin2_code: str
    population: str
    timezone: str
    modification_date: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_geonames_features(path: Path) -> Iterable[Feature]:
    with path.open("r", encoding="utf-8", newline="") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            values = line.rstrip("\r\n").split("\t")
            if len(values) != 19:
                raise ValueError(f"{path.name}:{line_number}: expected 19 GeoNames fields")
            yield Feature(
                geoname_id=values[0],
                name=values[1],
                asciiname=values[2],
                latitude=values[4],
                longitude=values[5],
                feature_class=values[6],
                feature_code=values[7],
                country_code=values[8],
                admin1_code=values[10],
                admin2_code=values[11],
                population=values[14],
                timezone=values[17],
                modification_date=values[18],
            )


def _population(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _entity_id(geoname_id: str) -> str:
    return f"geonames:{geoname_id}"


def _normalised_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _write_tsv(path: Path, headers: tuple[str, ...], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=headers,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _copy_csv_subset(input_path: Path, output_path: Path, fields: tuple[str, ...]) -> int:
    count = 0
    with (
        input_path.open("r", encoding="utf-8", newline="") as input_file,
        output_path.open("w", encoding="utf-8", newline="") as output_file,
    ):
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None or set(fields) - set(reader.fieldnames):
            raise ValueError(f"{input_path.name}: required CSV columns are missing")
        writer = csv.DictWriter(output_file, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            writer.writerow({field: row[field] for field in fields})
            count += 1
    return count


def _read_current_countries(path: Path) -> list[dict[str, str]]:
    countries: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip() or line.startswith("#"):
                continue
            values = line.rstrip("\r\n").split("\t")
            if len(values) != 19:
                raise ValueError(f"{path.name}:{line_number}: expected 19 country fields")
            countries.append(
                {
                    "geoname_id": values[16],
                    "label": values[4],
                    "asciiname": values[4],
                    "country_code": values[0],
                    "iso3": values[1],
                    "iso_numeric": values[2],
                    "continent": values[8],
                    "taxonomy": "geonames:country",
                    "entity_kind": "country",
                    "source_record_id": f"countryInfo:{values[0]}",
                    "feature_class": "A",
                    "feature_code": "PCLI",
                    "latitude": "",
                    "longitude": "",
                    "admin1_code": "",
                    "admin2_code": "",
                    "population": values[7],
                    "timezone": "",
                    "modification_date": "",
                }
            )
    return countries


def _read_admin_entities(path: Path, *, level: int) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            values = line.rstrip("\r\n").split("\t")
            if len(values) != 4:
                raise ValueError(f"{path.name}:{line_number}: expected four admin fields")
            code, label, asciiname, geoname_id = values
            code_parts = code.split(".")
            if len(code_parts) != level + 1:
                raise ValueError(
                    f"{path.name}:{line_number}: malformed administrative code {code!r}"
                )
            entities.append(
                {
                    "geoname_id": geoname_id,
                    "label": label,
                    "asciiname": asciiname,
                    "country_code": code_parts[0],
                    "iso3": "",
                    "iso_numeric": "",
                    "continent": "",
                    "taxonomy": f"geonames:admin{level}",
                    "entity_kind": "region",
                    "source_record_id": f"{path.stem}:{code}",
                    "feature_class": "A",
                    "feature_code": f"ADM{level}",
                    "latitude": "",
                    "longitude": "",
                    "admin1_code": code_parts[1],
                    "admin2_code": code_parts[2] if level == 2 else "",
                    "population": "",
                    "timezone": "",
                    "modification_date": "",
                }
            )
    return entities


def _add_entity(
    entity: dict[str, str],
    entities: dict[str, dict[str, str]],
    quarantine: list[dict[str, str]],
) -> None:
    geoname_id = entity["geoname_id"]
    previous = entities.get(geoname_id)
    if previous is None:
        entities[geoname_id] = entity
        return
    if previous == entity:
        return
    quarantine.append(
        {
            "record_kind": "entity",
            "source_record_id": entity["source_record_id"],
            "reason_code": "conflicting_geonames_entity_id",
            "detail": f"conflicts with {previous['source_record_id']}",
        }
    )


def _feature_entity(feature: Feature, *, taxonomy: str, entity_kind: str) -> dict[str, str]:
    return {
        "geoname_id": feature.geoname_id,
        "label": feature.name,
        "asciiname": feature.asciiname,
        "country_code": feature.country_code,
        "iso3": "",
        "iso_numeric": "",
        "continent": "",
        "taxonomy": taxonomy,
        "entity_kind": entity_kind,
        "source_record_id": f"allCountries:{feature.geoname_id}",
        "feature_class": feature.feature_class,
        "feature_code": feature.feature_code,
        "latitude": feature.latitude,
        "longitude": feature.longitude,
        "admin1_code": feature.admin1_code,
        "admin2_code": feature.admin2_code,
        "population": feature.population,
        "timezone": feature.timezone,
        "modification_date": feature.modification_date,
    }


def _is_kept_city(feature: Feature) -> bool:
    return (
        feature.feature_class == "P"
        and feature.feature_code in CITY_CODES
        and (_population(feature.population) > 500 or feature.feature_code in ADMIN_SEAT_CODES)
    )


def _is_current_alias(language: str, historic: str, colloquial: str, end_date: str) -> bool:
    return (
        bool(language)
        and historic != "1"
        and colloquial != "1"
        and not end_date
        and (language == "abbr" or LANGUAGE_TAG.fullmatch(language) is not None)
    )


def _verify_bundle(bundle: Path) -> dict[str, int]:
    required = {
        "geonames_entities.tsv",
        "geonames_base_aliases.tsv",
        "geonames_current_aliases.tsv",
        "geonames_airport_candidates.tsv",
        "geonames_iata_crossrefs.tsv",
        "geonames_admin_corroboration.tsv",
        "ourairports_airports.csv",
        "ourairports_countries.csv",
        "ourairports_regions.csv",
        "quarantine.tsv",
        "manifest.json",
    }
    missing = sorted(name for name in required if not (bundle / name).is_file())
    if missing:
        raise ValueError(f"bundle is missing required files: {missing}")
    with (bundle / "manifest.json").open(encoding="utf-8") as input_file:
        manifest = json.load(input_file)
    for filename, receipt in manifest["outputs"].items():
        path = bundle / filename
        if path.stat().st_size != receipt["bytes"] or _sha256(path) != receipt["sha256"]:
            raise ValueError(f"output receipt does not match local file: {filename}")

    entities: dict[str, dict[str, str]] = {}
    with (bundle / "geonames_entities.tsv").open(encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file, delimiter="\t"):
            entity_id = row["geoname_id"]
            if entity_id in entities:
                raise ValueError(f"duplicate GeoNames entity ID in bundle: {entity_id}")
            if row["entity_kind"] not in {"country", "city", "region"}:
                raise ValueError(f"unknown entity kind in bundle: {row['entity_kind']}")
            entities[entity_id] = row

    aliases = 0
    with (bundle / "geonames_current_aliases.tsv").open(encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file, delimiter="\t"):
            aliases += 1
            if row["geoname_id"] not in entities:
                raise ValueError(f"alias has unknown GeoNames entity: {row['geoname_id']}")
            if not _is_current_alias(
                row["iso_language"], row["is_historic"], row["is_colloquial"], row["to"]
            ):
                raise ValueError(
                    f"alias does not meet current-alias rule: {row['alternate_name_id']}"
                )
            if not _normalised_alias(row["alternate_name"]):
                raise ValueError(f"alias is empty after normalization: {row['alternate_name_id']}")

    airport_codes: set[str] = set()
    airports = 0
    with (bundle / "ourairports_airports.csv").open(encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file):
            airports += 1
            if row["type"] not in {"large_airport", "medium_airport"}:
                raise ValueError(f"airport has excluded type: {row['id']}")
            if row["scheduled_service"] != "yes" or not row["iata_code"]:
                raise ValueError(f"airport violates retained endpoint rule: {row['id']}")
            if row["iata_code"] in airport_codes:
                raise ValueError(f"duplicate OurAirports IATA code: {row['iata_code']}")
            airport_codes.add(row["iata_code"])

    with (bundle / "geonames_iata_crossrefs.tsv").open(encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file, delimiter="\t"):
            if row["iata_code"] not in airport_codes:
                raise ValueError(f"cross-reference has an unretained IATA code: {row['iata_code']}")

    return {"entities": len(entities), "current_aliases": aliases, "airports": airports}


def _prune_raw_files(source_directory: Path) -> None:
    for filename in RAW_FILES_SUPERSEDED_BY_BUNDLE:
        path = source_directory / filename
        if path.exists():
            path.unlink()


def _write_manifest(bundle: Path, *, counts: Counter[str], source_directory: Path) -> None:
    files = sorted(
        path for path in bundle.iterdir() if path.is_file() and path.name != "manifest.json"
    )
    document = {
        "bundle_id": BUNDLE_NAME,
        "format_version": "1",
        "purpose": "Compact current travel-identity inputs; not a published planner snapshot.",
        "filters": {
            "cities": {
                "feature_codes": sorted(CITY_CODES),
                "population_rule": "population > 500, except retained administrative seats",
                "administrative_seat_codes": sorted(ADMIN_SEAT_CODES),
            },
            "regions": {
                "taxonomies": [
                    "geonames:continent",
                    "geonames:admin1",
                    "geonames:admin2",
                    "geonames:geographic_region",
                    "ourairports:iso3166-2",
                ],
                "geonames_geographic_region_feature_codes": sorted(GEOGRAPHIC_REGION_CODES),
            },
            "aliases": {
                "exclude": ["historic", "expired", "colloquial", "blank language", "metadata tags"],
                "include_language": "ISO-like language tag or abbr",
            },
            "ourairports": {
                "type": ["large_airport", "medium_airport"],
                "scheduled_service": "yes",
                "iata_code": "nonempty",
            },
        },
        "source_files_read": {
            filename: {
                "bytes": (source_directory / filename).stat().st_size,
                "sha256": _sha256(source_directory / filename),
            }
            for filename in SOURCE_FILES_READ
        },
        "record_counts": dict(sorted(counts.items())),
        "outputs": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in files
        },
        "limitations": [
            "Source order is not a publication order; the future importer must canonicalize records.",
            "GeoNames airport candidates are reconciliation evidence only, not published airports.",
            "No municipality, keyword, coordinate, or distance rule creates a serving relationship.",
            "No airport group, route, schedule, provider, or booking claim is included.",
        ],
    }
    with (bundle / "manifest.json").open("w", encoding="utf-8", newline="") as output_file:
        json.dump(document, output_file, ensure_ascii=False, indent=2, sort_keys=True)
        output_file.write("\n")


def prepare(
    source_directory: Path, *, prune_raw: bool, replace_existing_bundle: bool = False
) -> Path:
    source_directory = source_directory.resolve()
    final_bundle = source_directory / BUNDLE_NAME
    if final_bundle.exists():
        if not replace_existing_bundle and not prune_raw:
            raise FileExistsError(f"bundle already exists: {final_bundle}")
        if not replace_existing_bundle:
            _verify_bundle(final_bundle)
            _prune_raw_files(source_directory)
            return final_bundle

    missing = sorted(name for name in SOURCE_FILES_READ if not (source_directory / name).is_file())
    if missing:
        raise FileNotFoundError(f"missing source inputs: {missing}")

    counts: Counter[str] = Counter()
    quarantine: list[dict[str, str]] = []
    entities: dict[str, dict[str, str]] = {}
    for country in _read_current_countries(source_directory / "countryInfo.txt"):
        _add_entity(country, entities, quarantine)
        counts["countries"] += 1
    for level, filename in ((1, "admin1CodesASCII.txt"), (2, "admin2Codes.txt")):
        for entity in _read_admin_entities(source_directory / filename, level=level):
            _add_entity(entity, entities, quarantine)
            counts[f"admin{level}_regions"] += 1

    admin_expected_ids = {
        geoname_id: entity["feature_code"]
        for geoname_id, entity in entities.items()
        if entity["feature_code"] in {"ADM1", "ADM2"}
    }
    active_admin_ids: set[str] = set()
    airport_candidates: dict[str, Feature] = {}
    for feature in _read_geonames_features(source_directory / "allCountries.txt"):
        if _is_kept_city(feature):
            _add_entity(
                _feature_entity(feature, taxonomy="geonames:populated_place", entity_kind="city"),
                entities,
                quarantine,
            )
            counts["cities"] += 1
        elif feature.feature_class == "L" and feature.feature_code == "CONT":
            _add_entity(
                _feature_entity(feature, taxonomy="geonames:continent", entity_kind="region"),
                entities,
                quarantine,
            )
            counts["continents"] += 1
        elif feature.feature_class == "L" and feature.feature_code in GEOGRAPHIC_REGION_CODES:
            _add_entity(
                _feature_entity(
                    feature, taxonomy="geonames:geographic_region", entity_kind="region"
                ),
                entities,
                quarantine,
            )
            counts["geographic_regions"] += 1
        elif feature.feature_class == "S" and feature.feature_code == "AIRP":
            airport_candidates[feature.geoname_id] = feature
            counts["airport_candidates"] += 1

        if (
            feature.geoname_id in admin_expected_ids
            and feature.feature_class == "A"
            and feature.feature_code == admin_expected_ids[feature.geoname_id]
        ):
            active_admin_ids.add(feature.geoname_id)

    for geoname_id, expected_feature_code in sorted(admin_expected_ids.items()):
        if geoname_id not in active_admin_ids:
            quarantine.append(
                {
                    "record_kind": "administrative_region",
                    "source_record_id": _entity_id(geoname_id),
                    "reason_code": "not_corroborated_by_active_allcountries_record",
                    "detail": f"expected active {expected_feature_code}",
                }
            )

    airport_fields = (
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
    )
    temporary_parent = Path(tempfile.mkdtemp(prefix="m1-source-prep-", dir=source_directory))
    bundle = temporary_parent / BUNDLE_NAME
    bundle.mkdir()
    try:
        airports = _copy_csv_subset(
            source_directory / "airports.csv", bundle / "ourairports_airports.csv", airport_fields
        )
        counts["ourairports_airports"] = airports
        with (bundle / "ourairports_airports.csv").open(encoding="utf-8", newline="") as input_file:
            airport_iatas = {row["iata_code"] for row in csv.DictReader(input_file)}
        counts["ourairports_countries"] = _copy_csv_subset(
            source_directory / "countries.csv",
            bundle / "ourairports_countries.csv",
            ("id", "code", "name", "continent", "wikipedia_link", "keywords"),
        )
        counts["ourairports_regions"] = _copy_csv_subset(
            source_directory / "regions.csv",
            bundle / "ourairports_regions.csv",
            (
                "id",
                "code",
                "local_code",
                "name",
                "continent",
                "iso_country",
                "wikipedia_link",
                "keywords",
            ),
        )

        entity_headers = (
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
        )
        entity_rows: list[dict[str, str]] = []
        base_alias_rows: list[dict[str, str]] = []
        for geoname_id, entity in sorted(entities.items(), key=lambda item: int(item[0])):
            entity_rows.append({"entity_id": _entity_id(geoname_id), **entity})
            aliases = (("name", entity["label"]),)
            if _normalised_alias(entity["asciiname"]) != _normalised_alias(entity["label"]):
                aliases += (("asciiname", entity["asciiname"]),)
            for alias_kind, alias in aliases:
                if _normalised_alias(alias):
                    base_alias_rows.append(
                        {
                            "geoname_id": geoname_id,
                            "entity_id": _entity_id(geoname_id),
                            "alias": alias,
                            "alias_kind": alias_kind,
                            "source_record_id": entity["source_record_id"],
                        }
                    )
        _write_tsv(bundle / "geonames_entities.tsv", entity_headers, entity_rows)
        _write_tsv(
            bundle / "geonames_base_aliases.tsv",
            ("geoname_id", "entity_id", "alias", "alias_kind", "source_record_id"),
            sorted(
                base_alias_rows,
                key=lambda row: (int(row["geoname_id"]), row["alias_kind"], row["alias"]),
            ),
        )

        _write_tsv(
            bundle / "geonames_airport_candidates.tsv",
            (
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
            (
                {
                    "geoname_id": feature.geoname_id,
                    "name": feature.name,
                    "asciiname": feature.asciiname,
                    "country_code": feature.country_code,
                    "latitude": feature.latitude,
                    "longitude": feature.longitude,
                    "timezone": feature.timezone,
                    "modification_date": feature.modification_date,
                    "source_record_id": f"allCountries:{feature.geoname_id}",
                }
                for _, feature in sorted(airport_candidates.items(), key=lambda item: int(item[0]))
            ),
        )

        retained_entity_ids = set(entities)
        alias_headers = (
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
        )
        crossref_rows: list[dict[str, str]] = []
        with (
            (source_directory / "alternateNamesV2.txt").open(
                "r", encoding="utf-8", newline=""
            ) as input_file,
            (bundle / "geonames_current_aliases.tsv").open(
                "w", encoding="utf-8", newline=""
            ) as output_file,
        ):
            alias_writer = csv.DictWriter(
                output_file, fieldnames=alias_headers, delimiter="\t", lineterminator="\n"
            )
            alias_writer.writeheader()
            for line_number, line in enumerate(input_file, start=1):
                values = line.rstrip("\r\n").split("\t")
                if len(values) != 10:
                    raise ValueError(
                        f"alternateNamesV2.txt:{line_number}: expected 10 alternate-name fields"
                    )
                (
                    alternate_name_id,
                    geoname_id,
                    iso_language,
                    alternate_name,
                    is_preferred_name,
                    is_short_name,
                    is_colloquial,
                    is_historic,
                    start_date,
                    end_date,
                ) = values
                if (
                    geoname_id in retained_entity_ids
                    and _is_current_alias(iso_language, is_historic, is_colloquial, end_date)
                    and _normalised_alias(alternate_name)
                ):
                    alias_writer.writerow(
                        {
                            "alternate_name_id": alternate_name_id,
                            "geoname_id": geoname_id,
                            "entity_id": _entity_id(geoname_id),
                            "iso_language": iso_language,
                            "alternate_name": alternate_name,
                            "is_preferred_name": is_preferred_name,
                            "is_short_name": is_short_name,
                            "is_colloquial": is_colloquial,
                            "is_historic": is_historic,
                            "from": start_date,
                            "to": end_date,
                        }
                    )
                    counts["current_aliases"] += 1
                if (
                    iso_language == "iata"
                    and geoname_id in airport_candidates
                    and alternate_name.upper() in airport_iatas
                ):
                    feature = airport_candidates[geoname_id]
                    crossref_rows.append(
                        {
                            "alternate_name_id": alternate_name_id,
                            "iata_code": alternate_name.upper(),
                            "geoname_id": geoname_id,
                            "country_code": feature.country_code,
                            "timezone": feature.timezone,
                            "is_historic": is_historic,
                            "from": start_date,
                            "to": end_date,
                            "source_record_id": f"alternateNamesV2:{alternate_name_id}",
                        }
                    )
                    counts["iata_crossrefs"] += 1
        _write_tsv(
            bundle / "geonames_iata_crossrefs.tsv",
            (
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
            sorted(
                crossref_rows, key=lambda row: (row["iata_code"], int(row["alternate_name_id"]))
            ),
        )
        _write_tsv(
            bundle / "geonames_admin_corroboration.tsv",
            ("geoname_id", "expected_feature_code", "corroborated_by_active_allcountries"),
            (
                {
                    "geoname_id": geoname_id,
                    "expected_feature_code": code,
                    "corroborated_by_active_allcountries": str(
                        geoname_id in active_admin_ids
                    ).lower(),
                }
                for geoname_id, code in sorted(
                    admin_expected_ids.items(), key=lambda item: int(item[0])
                )
            ),
        )
        _write_tsv(
            bundle / "quarantine.tsv",
            ("record_kind", "source_record_id", "reason_code", "detail"),
            sorted(quarantine, key=lambda row: (row["reason_code"], row["source_record_id"])),
        )
        counts["entities"] = len(entities)
        counts["base_aliases"] = len(base_alias_rows)
        counts["quarantine_records"] = len(quarantine)
        _write_manifest(bundle, counts=counts, source_directory=source_directory)
        verification = _verify_bundle(bundle)
        counts.update({f"verified_{key}": value for key, value in verification.items()})

        if final_bundle.exists():
            previous_bundle = temporary_parent / f"{BUNDLE_NAME}.previous"
            final_bundle.replace(previous_bundle)
            try:
                bundle.replace(final_bundle)
            except BaseException:
                previous_bundle.replace(final_bundle)
                raise
        else:
            bundle.replace(final_bundle)
    finally:
        if temporary_parent.exists():
            shutil.rmtree(temporary_parent)

    if prune_raw:
        _prune_raw_files(source_directory)
    return final_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-directory", type=Path, default=DEFAULT_SOURCE_DIRECTORY)
    parser.add_argument(
        "--prune-raw",
        action="store_true",
        help="remove source files superseded by a successfully verified compact bundle",
    )
    parser.add_argument(
        "--replace-existing-bundle",
        action="store_true",
        help="atomically replace an existing compact bundle after processing a fresh source download",
    )
    arguments = parser.parse_args()
    bundle = prepare(
        arguments.source_directory,
        prune_raw=arguments.prune_raw,
        replace_existing_bundle=arguments.replace_existing_bundle,
    )
    print(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
