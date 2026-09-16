"""Focused contract checks for the local Milestone 1 source-preparation rules."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_source_preparation_module() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "prepare_m1_source_subsets.py"
    specification = importlib.util.spec_from_file_location("prepare_m1_source_subsets", path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_city_filter_keeps_current_meaningful_places_and_administrative_seats() -> None:
    module = _load_source_preparation_module()
    feature = module.Feature

    ordinary_city = feature(
        "1", "Example", "Example", "", "", "P", "PPL", "US", "", "", "501", "", ""
    )
    small_locality = feature("2", "Small", "Small", "", "", "P", "PPL", "US", "", "", "500", "", "")
    administrative_seat = feature(
        "3", "Seat", "Seat", "", "", "P", "PPLA2", "US", "", "", "0", "", ""
    )
    historic_place = feature(
        "4", "Historic", "Historic", "", "", "P", "PPLH", "US", "", "", "10000", "", ""
    )

    assert module._is_kept_city(ordinary_city)
    assert not module._is_kept_city(small_locality)
    assert module._is_kept_city(administrative_seat)
    assert not module._is_kept_city(historic_place)


def test_alias_filter_excludes_historic_expired_colloquial_and_metadata_tags() -> None:
    module = _load_source_preparation_module()

    assert module._is_current_alias("ja", "", "", "")
    assert module._is_current_alias("abbr", "", "", "")
    assert not module._is_current_alias("", "", "", "")
    assert not module._is_current_alias("wkdt", "", "", "")
    assert not module._is_current_alias("en", "1", "", "")
    assert not module._is_current_alias("en", "", "1", "")
    assert not module._is_current_alias("en", "", "", "2020-01-01")


def test_existing_bundle_requires_an_explicit_replacement_flag(tmp_path: Path) -> None:
    module = _load_source_preparation_module()
    (tmp_path / module.BUNDLE_NAME).mkdir()

    try:
        module.prepare(tmp_path, prune_raw=False)
    except FileExistsError as error:
        assert str(tmp_path / module.BUNDLE_NAME) in str(error)
    else:
        raise AssertionError("an existing bundle must not be overwritten implicitly")


def test_ourairports_retention_keeps_extra_columns_and_exact_endpoint_filter(
    tmp_path: Path,
) -> None:
    module = _load_source_preparation_module()
    source = tmp_path / "airports.csv"
    output = tmp_path / "retained.csv"
    headers = ["id", "type", "scheduled_service", "iata_code", "municipality", "keywords", "new"]
    rows = [
        {
            "id": "1",
            "type": "large_airport",
            "scheduled_service": "yes",
            "iata_code": "AAA",
            "municipality": "Alpha",
            "keywords": "alpha",
            "new": "kept",
        },
        {
            "id": "2",
            "type": "medium_airport",
            "scheduled_service": "yes",
            "iata_code": "BBB",
            "municipality": "Bravo",
            "keywords": "bravo",
            "new": "kept-too",
        },
        {
            "id": "3",
            "type": "small_airport",
            "scheduled_service": "yes",
            "iata_code": "CCC",
            "municipality": "Nope",
            "keywords": "",
            "new": "drop",
        },
        {
            "id": "4",
            "type": "large_airport",
            "scheduled_service": "no",
            "iata_code": "DDD",
            "municipality": "Nope",
            "keywords": "",
            "new": "drop",
        },
        {
            "id": "5",
            "type": "medium_airport",
            "scheduled_service": "yes",
            "iata_code": "",
            "municipality": "Nope",
            "keywords": "",
            "new": "drop",
        },
    ]
    with source.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    raw_records: dict[tuple[str, str], tuple[str, ...]] = {}
    count = module._copy_csv_subset(
        source,
        output,
        ("id", "type", "scheduled_service", "iata_code"),
        predicate=lambda row: (
            row["type"] in {"large_airport", "medium_airport"}
            and row["scheduled_service"] == "yes"
            and bool(row["iata_code"])
        ),
        raw_records=raw_records,
        source_name="airports.csv",
        source_record_id=lambda row: f"ourairports:{row['id']}",
    )
    with output.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        assert tuple(reader.fieldnames or ()) == tuple(headers)
        retained = list(reader)
    assert count == 2
    assert retained == rows[:2]
    assert raw_records[("airports.csv", "ourairports:1")] == tuple(
        rows[0][header] for header in headers
    )


def test_source_preparation_rejects_pruning_without_catalog_validation(tmp_path: Path) -> None:
    module = _load_source_preparation_module()
    try:
        module.prepare(tmp_path, prune_raw=True, replace_existing_bundle=True)
    except ValueError as error:
        assert "cannot prune raw inputs" in str(error)
    else:
        raise AssertionError("preparation must not prune without catalog validation")
