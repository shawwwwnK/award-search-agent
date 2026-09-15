"""Focused contract checks for the local Milestone 1 source-preparation rules."""

from __future__ import annotations

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
