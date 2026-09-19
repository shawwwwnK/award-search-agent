"""Offline tests for deterministic Milestone 2B candidate validation and replay."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
    SelectedAirport,
)
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryGeneratorConfiguration,
    GatewayDiscoveryInput,
    GatewayDiscoveryOutcome,
    GatewayDiscoveryReplayError,
    GatewayDiscoveryResult,
    discover_gateway_candidates,
    replay_gateway_discovery_result,
    validate_gateway_candidate_proposal,
)
from award_agent.search_planning.gateway_generator import (
    GatewayCandidateProposal,
    GatewayOutboundDateContext,
)
from award_agent.search_planning.knowledge import Airport, AirportSelectionMetadata
from award_agent.search_planning.market_policy import (
    classify_and_gate_airport_markets,
    load_default_planning_market_policy,
)


class _Generator:
    def __init__(self, proposal: GatewayCandidateProposal | Exception) -> None:
        self.proposal = proposal
        self.calls = 0

    def propose(self, _: object) -> GatewayCandidateProposal:
        self.calls += 1
        if isinstance(self.proposal, Exception):
            raise self.proposal
        return self.proposal


class _Factory:
    def __init__(self, generator: _Generator | Exception) -> None:
        self.generator = generator
        self.calls = 0

    def __call__(self) -> _Generator:
        self.calls += 1
        if isinstance(self.generator, Exception):
            raise self.generator
        return self.generator


class _CaptureFailingGenerator(_Generator):
    def take_call_traces(self) -> list[object]:
        raise RuntimeError("telemetry unavailable")

    def take_usage(self) -> dict[str, int]:
        return {"calls": 1, "input_tokens": 2, "output_tokens": 3, "total_tokens": 5}


class _Repository:
    def __init__(self) -> None:
        locations = {
            "SFO": ("US", "US-CA"),
            "LAX": ("US", "US-CA"),
            "ORD": ("US", "US-IL"),
            "JFK": ("US", "US-NY"),
            "ATL": ("US", "US-GA"),
            "DFW": ("US", "US-TX"),
            "SEA": ("US", "US-WA"),
            "KTI": ("ZZ", "ZZ-TEST"),
            "CDG": ("FR", "FR-IDF"),
        }
        self.airports = {
            iata: Airport(
                airport_id=f"test:{iata}",
                iata=iata,
                label=iata,
                country_entity_id=f"country:{country}",
                timezone="America/Los_Angeles" if country == "US" else "Europe/Paris",
                aliases=(iata.lower(),),
                source_ids=(f"source:{iata}",),
            )
            for iata, (country, _) in locations.items()
        }
        self.metadata = {
            airport.airport_id: AirportSelectionMetadata(
                airport_id=airport.airport_id,
                country_code=locations[iata][0],
                iso_region=locations[iata][1],
                airport_type="large_airport",
                latitude=0,
                longitude=0,
            )
            for iata, airport in self.airports.items()
        }
        self.knowledge_receipt = CatalogKnowledgeReceipt(
            release_id="test-catalog",
            schema_version="v1",
            source_date=date(2026, 9, 18),
            logical_content_sha256="1" * 64,
            manifest_sha256="2" * 64,
            database_sha256="3" * 64,
            source_bundle_manifest_sha256="4" * 64,
            source_artifacts=(
                CatalogSourceArtifactReceipt(artifact_name="test", bytes=1, sha256="5" * 64),
            ),
        )

    def lookup_airport_iata(self, iata: str) -> Airport | None:
        return self.airports.get(iata)

    def airport(self, airport_id: str) -> Airport | None:
        return next(
            (airport for airport in self.airports.values() if airport.airport_id == airport_id),
            None,
        )

    def airport_selection_metadata(self, airport_id: str) -> AirportSelectionMetadata | None:
        return self.metadata.get(airport_id)


@pytest.fixture
def repository() -> _Repository:
    return _Repository()


def _input(
    repository: _Repository, origins: tuple[str, ...], destinations: tuple[str, ...]
) -> GatewayDiscoveryInput:
    def selected(iata: str) -> SelectedAirport:
        airport = repository.lookup_airport_iata(iata)
        assert airport is not None, iata
        return SelectedAirport(
            airport_id=airport.airport_id,
            airport_iata=airport.iata,
            airport_evidence_source_ids=airport.source_ids,
        )

    return GatewayDiscoveryInput(
        origin_endpoints=tuple(selected(item) for item in origins),
        destination_endpoints=tuple(selected(item) for item in destinations),
        outbound_date=GatewayOutboundDateContext(
            start=date(2026, 10, 5),
            end=date(2026, 10, 7),
            timezone="America/Los_Angeles",
            effective_window_precision="day",
        ),
    )


def _proposal(**updates: object) -> GatewayCandidateProposal:
    base: dict[str, object] = {
        "endpoint_market_assessments": [],
        "origin_access_gateways": [],
        "destination_access_gateways": [],
        "intermediate_hubs": [],
    }
    base.update(updates)
    return GatewayCandidateProposal.model_validate(base)


def _config() -> GatewayDiscoveryGeneratorConfiguration:
    return GatewayDiscoveryGeneratorConfiguration(
        model="offline-test",
        prompt_version="test-v1",
        adapter_version="test-adapter-v1",
        response_schema_sha256="0" * 64,
    )


def _discover(
    repository: _Repository, discovery_input: GatewayDiscoveryInput, generator: _Generator
) -> GatewayDiscoveryResult:
    return discover_gateway_candidates(
        discovery_input=discovery_input,
        policy=load_default_planning_market_policy().model_copy(update={"airport_overrides": ()}),
        repository=repository,
        generator_factory=lambda: generator,
        generator_configuration=_config(),
    )


def test_known_single_market_skips_without_model_call(repository: _Repository) -> None:
    generator = _Generator(_proposal())
    result = _discover(repository, _input(repository, ("SFO",), ("LAX",)), generator)

    assert generator.calls == 0
    assert result.outcome is GatewayDiscoveryOutcome.POLICY_SKIPPED
    assert (
        replay_gateway_discovery_result(
            record=result,
            policy=load_default_planning_market_policy().model_copy(
                update={"airport_overrides": ()}
            ),
            repository=repository,
        )
        == result
    )


def test_cross_market_validates_grouped_relationships_and_mismatch_is_advisory(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        endpoint_market_assessments=[
            {
                "role": "origin",
                "airport_id": "wrong",
                "airport_iata": "SFO",
                "model_asserted_market_id": "europe",
            }
        ],
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "alternate departure",
                "material_uncertainty": None,
                "model_asserted_market_id": "europe",
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "optional hypothesis",
                "material_uncertainty": None,
                "model_asserted_market_id": "us",
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "LAX"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ],
    )
    generator = _Generator(proposal)
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), generator)

    assert generator.calls == 1
    assert result.outcome is GatewayDiscoveryOutcome.SUCCESS_NONEMPTY
    assert result.accepted_origin_access_gateways[0].market_comparison.advisory is True
    assert result.endpoint_market_assessment_decisions[0].comparison.advisory is True
    assert result.accepted_intermediate_hubs[0].scopes[0].expanded_original_origin_iata_codes == (
        "SFO",
    )
    assert (
        replay_gateway_discovery_result(
            record=result,
            policy=load_default_planning_market_policy().model_copy(
                update={"airport_overrides": ()}
            ),
            repository=repository,
        )
        == result
    )


def test_mapping_gap_and_equal_multi_market_sets_each_make_one_grouped_call(
    repository: _Repository,
) -> None:
    gap_generator = _Generator(_proposal())
    gap_result = _discover(repository, _input(repository, ("KTI",), ("SFO",)), gap_generator)
    multi_generator = _Generator(_proposal())
    multi_result = _discover(
        repository, _input(repository, ("SFO", "CDG"), ("SFO", "CDG")), multi_generator
    )

    assert gap_generator.calls == multi_generator.calls == 1
    assert gap_result.outcome is GatewayDiscoveryOutcome.SUCCESS_EMPTY
    assert multi_result.outcome is GatewayDiscoveryOutcome.SUCCESS_EMPTY


def test_empty_endpoint_input_is_an_error_without_model_call(repository: _Repository) -> None:
    generator = _Generator(_proposal())
    result = _discover(repository, _input(repository, (), ("CDG",)), generator)

    assert generator.calls == 0
    assert result.outcome is GatewayDiscoveryOutcome.INPUT_ERROR


def test_gateway_rejection_prunes_only_dependent_hub_scope_and_no_refill(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "ZZZ",
                "reason": "invalid",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            },
            {
                "airport_iata": "LAX",
                "reason": "valid",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            },
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "two scopes",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "ZZZ"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    },
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    },
                ],
            }
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert len(result.accepted_origin_access_gateways) == 1
    assert len(result.accepted_intermediate_hubs[0].scopes) == 1
    assert not result.candidate_decisions[-1].scope_decisions[0].accepted


def test_generation_failure_and_forged_replay_are_explicit(repository: _Repository) -> None:
    result = _discover(
        repository, _input(repository, ("SFO",), ("CDG",)), _Generator(RuntimeError("offline"))
    )

    assert result.outcome is GatewayDiscoveryOutcome.GENERATION_FAILURE
    assert (
        replay_gateway_discovery_result(
            record=result,
            policy=load_default_planning_market_policy().model_copy(
                update={"airport_overrides": ()}
            ),
            repository=repository,
        )
        == result
    )
    forged = result.model_copy(update={"result_digest": "f" * 64})
    with pytest.raises(GatewayDiscoveryReplayError, match="forged"):
        replay_gateway_discovery_result(
            record=forged,
            policy=load_default_planning_market_policy().model_copy(
                update={"airport_overrides": ()}
            ),
            repository=repository,
        )


def test_accepted_access_changes_hub_cap_without_refill(repository: _Repository) -> None:
    hub_codes = ("JFK", "ATL", "DFW", "SEA")
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "access",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": code,
                "reason": "bounded",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
            for code in hub_codes
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert len(result.accepted_intermediate_hubs) == 3
    assert result.candidate_decisions[-1].issues[0].code == "over_pool_cap"


def test_lazy_factory_and_factory_failure(repository: _Repository) -> None:
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})
    factory = _Factory(_Generator(_proposal()))
    skipped = discover_gateway_candidates(
        discovery_input=_input(repository, ("SFO",), ("LAX",)),
        policy=policy,
        repository=repository,
        generator_factory=factory,
        generator_configuration=_config(),
    )
    failure = discover_gateway_candidates(
        discovery_input=_input(repository, ("SFO",), ("CDG",)),
        policy=policy,
        repository=repository,
        generator_factory=_Factory(RuntimeError("construct")),
        generator_configuration=_config(),
    )

    assert factory.calls == 0
    assert skipped.outcome is GatewayDiscoveryOutcome.POLICY_SKIPPED
    assert failure.outcome is GatewayDiscoveryOutcome.GENERATION_FAILURE


def test_capture_accessor_failure_is_redacted_and_nonfatal(repository: _Repository) -> None:
    result = _discover(
        repository,
        _input(repository, ("SFO",), ("CDG",)),
        _CaptureFailingGenerator(_proposal()),
    )

    assert result.outcome is GatewayDiscoveryOutcome.SUCCESS_EMPTY
    assert result.generator_invocation is not None
    assert result.generator_invocation.trace_count == 0
    assert result.generator_invocation.capture_issue_codes == ("take_call_traces_failure",)
    assert "call_traces" not in result.generator_invocation.model_dump(mode="json")


def test_failed_generation_replay_preserves_redacted_capture_receipt(
    repository: _Repository,
) -> None:
    result = _discover(
        repository,
        _input(repository, ("SFO",), ("CDG",)),
        _CaptureFailingGenerator(RuntimeError("offline")),
    )
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})

    assert result.generator_invocation is not None
    assert (
        replay_gateway_discovery_result(record=result, policy=policy, repository=repository)
        == result
    )


def test_pure_validator_rejects_foreign_gate(repository: _Repository) -> None:
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})
    foreign_input = _input(repository, ("SFO",), ("LAX",))
    foreign_gate = classify_and_gate_airport_markets(
        origin_endpoints=foreign_input.origin_endpoints,
        destination_endpoints=foreign_input.destination_endpoints,
        policy=policy,
        repository=repository,
    )
    with pytest.raises(ValueError, match="does not reproduce"):
        validate_gateway_candidate_proposal(
            discovery_input=_input(repository, ("SFO",), ("CDG",)),
            policy=policy,
            repository=repository,
            gate=foreign_gate,
            proposal=_proposal(),
            generator_configuration=_config(),
        )


def test_overlapping_hub_scope_relationship_is_pruned(repository: _Repository) -> None:
    proposal = _proposal(
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "two scopes",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    },
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": "repeat",
                    },
                ],
            }
        ]
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    decision = result.candidate_decisions[0]
    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert decision.accepted
    assert decision.scope_decisions[1].issues[0].code == "duplicate_scope_relationship"
    assert decision.scope_decisions[1].issues[0].candidate_index == 0


def test_no_accepted_access_keeps_five_hub_cap_after_rejection(repository: _Repository) -> None:
    hub_codes = ("JFK", "ATL", "DFW", "SEA", "LAX", "ORD")
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "ZZZ",
                "reason": "invalid",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": code,
                "reason": "bounded",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
            for code in hub_codes
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert len(result.accepted_intermediate_hubs) == 5
    assert result.candidate_decisions[-1].issues[0].code == "over_pool_cap"


def test_destination_gateway_and_global_duplicate_preserve_valid_cross_product(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "origin access",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        destination_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "duplicate",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_destination_iata_codes": ["CDG"],
                "applicable_original_origin_iata_codes": ["SFO"],
            },
            {
                "airport_iata": "DFW",
                "reason": "destination access",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_destination_iata_codes": ["CDG"],
                "applicable_original_origin_iata_codes": ["SFO"],
            },
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "scoped",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "LAX"}],
                        "destination_side": [
                            {"kind": "destination_access_gateway", "airport_iata": "DFW"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert result.candidate_decisions[1].issues[0].code == "duplicate_candidate"
    assert result.accepted_destination_access_gateways[0].airport.airport_iata == "DFW"
    assert result.accepted_intermediate_hubs[0].scopes[
        0
    ].expanded_original_destination_iata_codes == ("CDG",)


def test_typed_gateway_scope_relationship_is_distinct_from_its_original_endpoint(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "access",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "two search forms",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "LAX"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    },
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    },
                ],
            }
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.SUCCESS_NONEMPTY
    assert len(result.accepted_intermediate_hubs[0].scopes) == 2


def test_blank_candidate_reason_rejects_only_that_candidate(repository: _Repository) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "  ",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "valid sibling",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ],
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert result.candidate_decisions[0].issues[0].code == "missing_candidate_reason"
    assert result.accepted_intermediate_hubs


def test_direct_and_implied_hub_self_references_are_rejected(repository: _Repository) -> None:
    direct = _proposal(
        intermediate_hubs=[
            {
                "airport_iata": "SFO",
                "reason": "bad direct",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ]
    )
    implied = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "access",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": "SFO",
                "reason": "bad implied",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "LAX"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ],
    )

    direct_result = _discover(
        repository, _input(repository, ("SFO",), ("CDG",)), _Generator(direct)
    )
    implied_result = _discover(
        repository, _input(repository, ("SFO",), ("CDG",)), _Generator(implied)
    )

    assert direct_result.outcome is GatewayDiscoveryOutcome.REJECTED_ALL
    assert (
        direct_result.candidate_decisions[0].scope_decisions[0].issues[0].code
        == "hub_equals_scope_reference"
    )
    assert implied_result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert (
        implied_result.candidate_decisions[-1].scope_decisions[0].issues[0].code
        == "hub_equals_implied_endpoint"
    )


def test_rejected_all_candidate_mapping_gap_and_endpoint_elsewhere_allowed(
    repository: _Repository,
) -> None:
    rejected = _discover(
        repository,
        _input(repository, ("SFO",), ("CDG",)),
        _Generator(
            _proposal(
                intermediate_hubs=[
                    {
                        "airport_iata": "ZZZ",
                        "reason": "not snapshot-validated",
                        "material_uncertainty": None,
                        "model_asserted_market_id": None,
                        "scopes": [
                            {
                                "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                                "destination_side": [
                                    {"kind": "original_destination", "airport_iata": "CDG"}
                                ],
                                "reason": None,
                            }
                        ],
                    }
                ]
            )
        ),
    )
    gap = _discover(
        repository,
        _input(repository, ("SFO",), ("CDG",)),
        _Generator(
            _proposal(
                intermediate_hubs=[
                    {
                        "airport_iata": "KTI",
                        "reason": "gap remains a hypothesis",
                        "material_uncertainty": None,
                        "model_asserted_market_id": "southeast_asia",
                        "scopes": [
                            {
                                "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                                "destination_side": [
                                    {"kind": "original_destination", "airport_iata": "CDG"}
                                ],
                                "reason": None,
                            }
                        ],
                    }
                ]
            )
        ),
    )
    elsewhere = _discover(
        repository,
        _input(repository, ("SFO", "CDG"), ("LAX",)),
        _Generator(
            _proposal(
                intermediate_hubs=[
                    {
                        "airport_iata": "CDG",
                        "reason": "endpoint on other relationship",
                        "material_uncertainty": None,
                        "model_asserted_market_id": None,
                        "scopes": [
                            {
                                "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                                "destination_side": [
                                    {"kind": "original_destination", "airport_iata": "LAX"}
                                ],
                                "reason": None,
                            }
                        ],
                    }
                ]
            )
        ),
    )

    assert rejected.outcome is GatewayDiscoveryOutcome.REJECTED_ALL
    assert gap.accepted_intermediate_hubs and gap.market_coverage.value == "candidate_mapping_gaps"
    assert elsewhere.outcome is GatewayDiscoveryOutcome.SUCCESS_NONEMPTY


def test_validation_failure_replays_only_when_fault_reproduces() -> None:
    class FaultyRepository(_Repository):
        def lookup_airport_iata(self, iata: str) -> Airport | None:
            if iata == "ORD":
                raise RuntimeError("catalog fault")
            return super().lookup_airport_iata(iata)

    repository = FaultyRepository()
    proposal = _proposal(
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "triggers fault",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "original_origin", "airport_iata": "SFO"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "CDG"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ]
    )
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), _Generator(proposal))
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})

    assert result.outcome is GatewayDiscoveryOutcome.VALIDATION_FAILURE
    assert (
        replay_gateway_discovery_result(record=result, policy=policy, repository=repository)
        == result
    )
    with pytest.raises(GatewayDiscoveryReplayError, match="not reproducible"):
        replay_gateway_discovery_result(record=result, policy=policy, repository=_Repository())


def test_nested_read_values_are_isolated_and_invariant_forgery_is_rejected(
    repository: _Repository,
) -> None:
    generator = _CaptureFailingGenerator(_proposal())
    result = _discover(repository, _input(repository, ("SFO",), ("CDG",)), generator)
    assert result.generator_invocation is not None
    result.generator_invocation.usage["calls"] = 99  # type: ignore[index]
    assert result.generator_invocation.usage["calls"] == 1  # type: ignore[index]

    payload = result.model_dump(mode="json", round_trip=True)
    payload["outcome"] = "generation_failure"
    payload_without_digest = {
        key: value for key, value in payload.items() if key != "result_digest"
    }
    payload["result_digest"] = hashlib.sha256(
        json.dumps(
            payload_without_digest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="generation-failure outcome"):
        GatewayDiscoveryResult.model_validate(payload)


def test_origin_access_self_pair_is_rejected_when_it_is_only_applicability(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "only self pair",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["CDG"],
                "applicable_original_destination_iata_codes": ["LAX"],
            }
        ]
    )
    result = _discover(repository, _input(repository, ("CDG",), ("LAX",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.REJECTED_ALL
    codes = {issue.code for issue in result.candidate_decisions[0].issues}
    assert "gateway_equals_applicable_opposite_endpoint" in codes
    assert "no_applicable_relationship_after_self_pair_pruning" in codes


def test_mixed_origin_self_pair_is_pruned_and_hub_cannot_revive_it(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        origin_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "mixed applicability",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_origin_iata_codes": ["SFO"],
                "applicable_original_destination_iata_codes": ["LAX", "CDG"],
            }
        ],
        intermediate_hubs=[
            {
                "airport_iata": "ORD",
                "reason": "cannot revive pair",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "scopes": [
                    {
                        "origin_side": [{"kind": "origin_access_gateway", "airport_iata": "LAX"}],
                        "destination_side": [
                            {"kind": "original_destination", "airport_iata": "LAX"}
                        ],
                        "reason": None,
                    }
                ],
            }
        ],
    )
    discovery_input = _input(repository, ("SFO",), ("LAX", "CDG"))
    result = _discover(repository, discovery_input, _Generator(proposal))
    policy = load_default_planning_market_policy().model_copy(update={"airport_overrides": ()})

    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert result.accepted_origin_access_gateways[0].applicable_original_destination_iata_codes == (
        "CDG",
    )
    assert result.candidate_decisions[0].relationship_pruned
    assert result.candidate_decisions[-1].scope_decisions[0].issues[0].code == (
        "origin_gateway_applicability_violation"
    )
    assert (
        replay_gateway_discovery_result(record=result, policy=policy, repository=repository)
        == result
    )


def test_destination_access_self_pair_mirror_prunes_only_unsafe_origins(
    repository: _Repository,
) -> None:
    proposal = _proposal(
        destination_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "mixed mirror",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_destination_iata_codes": ["CDG"],
                "applicable_original_origin_iata_codes": ["LAX", "SFO"],
            }
        ]
    )
    result = _discover(
        repository, _input(repository, ("LAX", "SFO"), ("CDG",)), _Generator(proposal)
    )

    assert result.outcome is GatewayDiscoveryOutcome.PARTIAL_ACCEPTANCE
    assert result.accepted_destination_access_gateways[0].applicable_original_origin_iata_codes == (
        "SFO",
    )
    assert result.candidate_decisions[0].relationship_pruned


def test_destination_access_only_self_pair_is_rejected(repository: _Repository) -> None:
    proposal = _proposal(
        destination_access_gateways=[
            {
                "airport_iata": "LAX",
                "reason": "only self mirror",
                "material_uncertainty": None,
                "model_asserted_market_id": None,
                "supported_original_destination_iata_codes": ["CDG"],
                "applicable_original_origin_iata_codes": ["LAX"],
            }
        ]
    )
    result = _discover(repository, _input(repository, ("LAX",), ("CDG",)), _Generator(proposal))

    assert result.outcome is GatewayDiscoveryOutcome.REJECTED_ALL
    assert "gateway_equals_applicable_opposite_endpoint" in {
        issue.code for issue in result.candidate_decisions[0].issues
    }
