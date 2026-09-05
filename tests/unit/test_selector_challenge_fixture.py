from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path

import pytest
import yaml

from award_agent.evaluation.selector_challenge_cases import (
    ChallengeTopology,
    challenge_surface_registry,
)
from award_agent.evaluation.selector_challenge_fixture import (
    DEFAULT_CONTROL_FIXTURE,
    DEFAULT_SELECTOR_CHALLENGE_FIXTURE,
    PreparedSelectorChallengeCase,
    SelectorChallengeFixtureError,
    canonical_topology_signature,
    challenge_fixture_payload,
    load_selector_challenge_fixture,
    preflight_selector_challenge_fixture,
    privacy_violations,
)


def test_checked_in_challenge_fixture_has_exactly_two_variants_per_surface() -> None:
    prepared = preflight_selector_challenge_fixture()

    assert len(prepared) == 28
    assert Counter(item.topology for item in prepared) == {
        topology.value: 4 for topology in ChallengeTopology
    }
    assert Counter(item.order_variant for item in prepared) == {
        "canonical": 14,
        "permuted": 14,
    }
    assert {
        (item.surface_id, item.order_variant)
        for item in prepared
    } == {
        (surface.surface_id, variant)
        for surface in challenge_surface_registry().values()
        for variant in ("canonical", "permuted")
    }


def test_permuted_cases_are_bijective_and_not_canonical_payload_copies() -> None:
    prepared = preflight_selector_challenge_fixture()
    by_surface: dict[str, dict[str, PreparedSelectorChallengeCase]] = {}
    for item in prepared:
        by_surface.setdefault(item.surface_id, {})[item.order_variant] = item

    for variants in by_surface.values():
        canonical = variants["canonical"].model_input
        permuted = variants["permuted"].model_input
        assert canonical.model_dump(mode="json") != permuted.model_dump(mode="json")
        assert {
            item.handle for item in canonical.ordered_evidence
        } == {f"e{index}" for index in range(len(canonical.ordered_evidence))}
        assert {
            item.handle for item in permuted.ordered_evidence
        } == {f"e{index}" for index in range(len(permuted.ordered_evidence))}
        assert {
            item.handle for group in canonical.candidate_groups for item in group.candidates
        } == {
            f"c{index}"
            for index, _item in enumerate(
                item for group in canonical.candidate_groups for item in group.candidates
            )
        }
        assert {
            item.handle for group in permuted.candidate_groups for item in group.candidates
        } == {
            f"c{index}"
            for index, _item in enumerate(
                item for group in permuted.candidate_groups for item in group.candidates
            )
        }
        assert set(canonical._candidate_handles.values()) == set(permuted._candidate_handles.values())
        assert set(canonical._group_handles.values()) == set(permuted._group_handles.values())
        assert set(canonical._evidence_handles.values()) == set(permuted._evidence_handles.values())
        assert set(canonical._anchor_handles.values()) == set(permuted._anchor_handles.values())
        assert set(canonical._production_slots.values()) == set(permuted._production_slots.values())


def test_private_topology_signatures_are_unique_and_subtypes_are_published() -> None:
    surfaces = tuple(challenge_surface_registry().values())
    signatures = {canonical_topology_signature(surface) for surface in surfaces}

    assert len(signatures) == len(surfaces)
    assert all(item.subtype_id for item in preflight_selector_challenge_fixture())


def test_v2_overlaps_are_explicit_control_only_cases() -> None:
    prepared = preflight_selector_challenge_fixture()
    controls = [item for item in prepared if item.control_only]

    assert controls
    assert all(item.order_variant in {"canonical", "permuted"} for item in controls)
    assert all(item.topology != "depth_two_composition_chain" for item in controls)
    assert all(item.topology != "two_independent_groups" for item in controls)


def test_public_fixture_contains_no_private_catalog_data_or_resolved_calendar_state() -> None:
    payload = challenge_fixture_payload()

    assert privacy_violations(payload) == ()
    serialized = yaml.safe_dump(payload, sort_keys=False)
    assert "manual:" not in serialized
    assert "reference_date" not in serialized
    assert "timezone" not in serialized
    assert "2026-08-29" not in serialized
    assert "oracle_rationale" not in serialized
    assert "candidate_rationales" not in serialized


def test_fixture_loader_exposes_fixture_and_control_sha_bindings() -> None:
    loaded = load_selector_challenge_fixture()

    assert loaded.path == DEFAULT_SELECTOR_CHALLENGE_FIXTURE
    assert loaded.control_path == DEFAULT_CONTROL_FIXTURE
    assert len(loaded.sha256) == 64
    assert len(loaded.control_sha256) == 64


def test_preflight_rejects_public_projection_drift(tmp_path: Path) -> None:
    copied = tmp_path / DEFAULT_SELECTOR_CHALLENGE_FIXTURE.name
    payload = yaml.safe_load(DEFAULT_SELECTOR_CHALLENGE_FIXTURE.read_text())
    payload["scenarios"][0]["public_input"]["ordered_evidence"][0]["text"] = "October 6"
    copied.write_text(yaml.safe_dump(payload, sort_keys=False))

    with pytest.raises(SelectorChallengeFixtureError, match="does not match"):
        preflight_selector_challenge_fixture(copied)


def test_preflight_rejects_control_sha_drift(tmp_path: Path) -> None:
    copied = tmp_path / DEFAULT_SELECTOR_CHALLENGE_FIXTURE.name
    payload = copy.deepcopy(yaml.safe_load(DEFAULT_SELECTOR_CHALLENGE_FIXTURE.read_text()))
    payload["control_fixture"]["sha256"] = "0" * 64
    copied.write_text(yaml.safe_dump(payload, sort_keys=False))

    with pytest.raises(SelectorChallengeFixtureError, match="control fixture SHA"):
        preflight_selector_challenge_fixture(copied)


def test_privacy_scanner_reports_private_and_resolved_values() -> None:
    violations = privacy_violations(
        {
            "scenarios": [
                {
                    "public_input": {
                        "summary": "manual:secret",
                        "resolved": "2026-09-07",
                    }
                }
            ]
        }
    )

    assert violations
