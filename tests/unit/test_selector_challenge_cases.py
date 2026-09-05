from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product

import pytest

from award_agent.evaluation.frozen_selector_eval import StaticFrozenHolidayProvider
from award_agent.evaluation.selector_challenge_cases import (
    ChallengeTopology,
    challenge_surface_registry,
    challenge_surface_variants,
    compile_challenge_oracle,
    selector_oracle_candidates,
)
from award_agent.intent.temporal_candidates import CandidateRelation
from award_agent.intent.temporal_compiler import (
    TemporalCandidateValidationError,
    compile_temporal_candidates,
)
from award_agent.intent.temporal_selector import plan_temporal_selection


def test_private_structural_challenge_has_exactly_two_surfaces_per_topology() -> None:
    registry = challenge_surface_registry()

    assert len(registry) == 14
    assert Counter(surface.topology_id for surface in registry.values()) == {
        topology: 2 for topology in ChallengeTopology
    }
    assert set(registry) == {surface.surface_id for surface in registry.values()}
    assert all(surface.subtype_id for surface in registry.values())
    assert {
        surface.subtype_id
        for surface in registry.values()
        if surface.topology_id is ChallengeTopology.ANCHORED_REFERENCE_SCOPE_FORK
    } == {"weekend_after_anchor", "unbounded_after_anchor"}
    assert {
        surface.subtype_id
        for surface in registry.values()
        if surface.topology_id is ChallengeTopology.UNSUPPORTED_FORK
    } == {"season", "first_week"}
    assert all(
        "leave" in surface.request.text.casefold() or "depart" in surface.request.text.casefold()
        for surface in registry.values()
        if surface.topology_id is ChallengeTopology.SINGLE_COMPOSITION
    )


def test_every_private_surface_has_complete_oracle_and_private_rationales() -> None:
    for surface in challenge_surface_registry().values():
        by_group: dict[str, list[str]] = defaultdict(list)
        for candidate in surface.catalog.candidates:
            by_group[candidate.exclusive_group].append(candidate.handle)

        assert set(surface.candidate_rationales) == {
            candidate.handle for candidate in surface.catalog.candidates
        }
        assert all(surface.candidate_rationales.values())
        assert surface.oracle_rationale
        assert all(
            len(set(handles) & set(surface.oracle_candidates)) == 1
            for handles in by_group.values()
        )


def test_private_challenge_oracles_compile_through_the_real_compiler() -> None:
    for surface in challenge_surface_registry().values():
        compiled = compile_challenge_oracle(surface)

        assert compiled.graph.constraints
        assert len(compiled.graph.constraints) == len(
            [
                candidate
                for candidate in surface.oracle_candidates
                if surface.catalog.by_handle(candidate).relation is not CandidateRelation.UNRESOLVED
            ]
        ) or all(
            surface.catalog.by_handle(candidate).relation is CandidateRelation.UNRESOLVED
            for candidate in surface.oracle_candidates
        )


def test_conservative_all_unresolved_private_selection_compiles() -> None:
    for surface in challenge_surface_registry().values():
        grouped: dict[str, list[str]] = defaultdict(list)
        for candidate in surface.catalog.candidates:
            grouped[candidate.exclusive_group].append(candidate.handle)
        conservative = tuple(
            next(
                (
                    handle
                    for handle in handles
                    if surface.catalog.by_handle(handle).relation is CandidateRelation.UNRESOLVED
                ),
                handles[0],
            )
            for handles in grouped.values()
        )

        compiled = compile_temporal_candidates(
            surface.request,
            surface.catalog,
            conservative,
            holiday_provider=StaticFrozenHolidayProvider(),
        )
        assert compiled.graph.constraints


def test_every_supported_candidate_compiles_in_at_least_one_complete_private_selection() -> None:
    """A selectable distractor is structurally real, not a dead invalid catalog branch."""

    for surface in challenge_surface_registry().values():
        grouped: dict[str, list[str]] = defaultdict(list)
        for candidate in surface.catalog.candidates:
            grouped[candidate.exclusive_group].append(candidate.handle)
        successful_supported: set[str] = set()
        for selection in product(*grouped.values()):
            try:
                compile_temporal_candidates(
                    surface.request,
                    surface.catalog,
                    selection,
                    holiday_provider=StaticFrozenHolidayProvider(),
                )
            except (TemporalCandidateValidationError, ValueError, AssertionError):
                continue
            successful_supported.update(
                handle
                for handle in selection
                if surface.catalog.by_handle(handle).relation is not CandidateRelation.UNRESOLVED
            )

        assert successful_supported == {
            candidate.handle
            for candidate in surface.catalog.candidates
            if candidate.relation is not CandidateRelation.UNRESOLVED
        }


def test_every_dependency_open_complete_selection_fails_for_missing_production() -> None:
    """Open dependency branches fail for their dependency, never malformed relation metadata."""

    for surface in challenge_surface_registry().values():
        grouped: dict[str, list[str]] = defaultdict(list)
        for candidate in surface.catalog.candidates:
            grouped[candidate.exclusive_group].append(candidate.handle)
        for selection in product(*grouped.values()):
            produced = {
                slot
                for handle in selection
                for slot in surface.catalog.by_handle(handle).produces
            }
            has_open_dependency = any(
                set(surface.catalog.by_handle(handle).requires) - produced
                for handle in selection
            )
            if not has_open_dependency:
                continue
            with pytest.raises(TemporalCandidateValidationError, match="requires unproduced value"):
                compile_temporal_candidates(
                    surface.request,
                    surface.catalog,
                    selection,
                    holiday_provider=StaticFrozenHolidayProvider(),
                )


def test_selector_oracle_excludes_only_deterministic_private_groups() -> None:
    for surface in challenge_surface_registry().values():
        plan = plan_temporal_selection(surface.catalog)
        selector_groups = set(plan.selector_groups)

        assert selector_oracle_candidates(surface) == tuple(
            handle
            for handle in surface.oracle_candidates
            if surface.catalog.by_handle(handle).exclusive_group in selector_groups
        )


def test_each_surface_reserves_canonical_and_permuted_public_variants() -> None:
    for surface in challenge_surface_registry().values():
        variants = challenge_surface_variants(surface)

        assert [variant.order_variant for variant in variants] == ["canonical", "permuted"]
        assert all(variant.surface is surface for variant in variants)
