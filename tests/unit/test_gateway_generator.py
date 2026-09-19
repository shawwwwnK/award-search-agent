"""Offline contract tests for the grouped Milestone 2B model generator."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from typing import Any, cast

import pytest
from openai import OpenAI
from pydantic import ValidationError

from award_agent.observability.llm_trace import response_schema_sha256
from award_agent.search_planning import (
    GATEWAY_GENERATOR_PROMPT_VERSION,
    GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
    GatewayCandidateProposal,
    GatewayGeneratorModelInput,
    GatewayOutboundDateContext,
    OpenAIGatewayGenerator,
    OpenAIGatewayGeneratorConfig,
    OpenAIGatewayGeneratorError,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
    SelectedAirport,
)
from award_agent.search_planning.market_policy import (
    AirportMarketAssignment,
    MarketAssignmentSource,
    MarketGenerationGate,
    MarketGenerationGateStatus,
    MarketPolicyCatalogCompatibility,
    PlanningMarket,
)


class _Responses:
    def __init__(self, output: object | Exception) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.output, Exception):
            raise self.output
        return SimpleNamespace(
            output_parsed=self.output,
            usage={"input_tokens": 19, "output_tokens": 23, "total_tokens": 42},
        )


class _Client:
    def __init__(self, output: object | Exception) -> None:
        self.responses = _Responses(output)


def _input() -> GatewayGeneratorModelInput:
    return GatewayGeneratorModelInput.model_validate(
        {
            "origin_endpoints": [
                {
                    "role": "origin",
                    "airport_id": "ourairports:1",
                    "airport_iata": "SFO",
                    "catalog_country_code": "US",
                    "catalog_iso_region": "US-CA",
                    "policy_market_id": "us",
                    "policy_market_name": "United States",
                    "policy_market_known": True,
                    "policy_assignment_source": "country_assignment",
                },
                {
                    "role": "origin",
                    "airport_id": "ourairports:2",
                    "airport_iata": "HNL",
                    "catalog_country_code": "US",
                    "catalog_iso_region": "US-HI",
                    "policy_market_id": None,
                    "policy_market_name": None,
                    "policy_market_known": False,
                    "policy_assignment_source": "override_coverage_drift",
                },
            ],
            "destination_endpoints": [
                {
                    "role": "destination",
                    "airport_id": "ourairports:3",
                    "airport_iata": "CDG",
                    "catalog_country_code": "FR",
                    "catalog_iso_region": "FR-IDF",
                    "policy_market_id": "europe",
                    "policy_market_name": "Europe",
                    "policy_market_known": True,
                    "policy_assignment_source": "country_assignment",
                }
            ],
            "approved_markets": [
                {
                    "market_id": "europe",
                    "name": "Europe",
                    "definition": "Product planning-market policy label.",
                },
                {
                    "market_id": "us",
                    "name": "United States",
                    "definition": "Product planning-market policy label.",
                },
            ],
            "outbound_date": GatewayOutboundDateContext(
                start=date(2026, 10, 5),
                end=date(2026, 10, 7),
                timezone="America/Los_Angeles",
                effective_window_precision="day",
            ),
        }
    )


def _proposal() -> GatewayCandidateProposal:
    return GatewayCandidateProposal.model_validate(
        {
            "endpoint_market_assessments": [
                {
                    "role": "origin",
                    "airport_id": "ourairports:1",
                    "airport_iata": "SFO",
                    "model_asserted_market_id": "us",
                },
                {
                    "role": "origin",
                    "airport_id": "ourairports:2",
                    "airport_iata": "HNL",
                    "model_asserted_market_id": "pacific_islands",
                },
                {
                    "role": "destination",
                    "airport_id": "ourairports:3",
                    "airport_iata": "CDG",
                    "model_asserted_market_id": "europe",
                },
            ],
            "origin_access_gateways": [
                {
                    "airport_iata": "LAX",
                    "reason": "Alternative international departure point.",
                    "material_uncertainty": "No route or inventory is asserted.",
                    "model_asserted_market_id": "us",
                    "supported_original_origin_iata_codes": ["SFO"],
                    "applicable_original_destination_iata_codes": ["CDG"],
                }
            ],
            "destination_access_gateways": [],
            "intermediate_hubs": [
                {
                    "airport_iata": "ORD",
                    "reason": "A complementary search hypothesis.",
                    "material_uncertainty": None,
                    "model_asserted_market_id": "us",
                    "scopes": [
                        {
                            "origin_side": [
                                {"kind": "original_origin", "airport_iata": "SFO"},
                                {"kind": "origin_access_gateway", "airport_iata": "LAX"},
                            ],
                            "destination_side": [
                                {"kind": "original_destination", "airport_iata": "CDG"}
                            ],
                            "reason": "The paired scope is deliberately explicit.",
                        }
                    ],
                }
            ],
        }
    )


def test_adapter_uses_one_structured_call_with_only_resolved_context_and_trace() -> None:
    client = _Client(_proposal())
    generator = OpenAIGatewayGenerator(
        OpenAIGatewayGeneratorConfig(model="test-gateway-generator"),
        client=cast(OpenAI, client),
        capture_llm_io=True,
    )

    assert generator.propose(_input()) == _proposal()
    assert len(client.responses.calls) == 1
    request = client.responses.calls[0]
    assert request["store"] is False
    assert request["text_format"] is GatewayCandidateProposal
    payload = json.loads(cast(str, request["input"]))
    assert payload["origin_endpoints"][1]["policy_market_known"] is False
    assert payload["origin_endpoints"][1]["policy_market_id"] is None
    assert payload["origin_endpoints"][0]["catalog_country_code"] == "US"
    assert payload["approved_markets"][0]["definition"]
    assert payload["outbound_date"]["start"] == "2026-10-05"
    assert "raw" not in payload
    assert "milestone" not in str(request["instructions"]).casefold()
    assert GATEWAY_GENERATOR_PROMPT_VERSION == "gateway-generator-prompt-v2"
    for required_rule in (
        "relative to the opposite market",
        "do not omit them to unlock more hubs",
        "cross-market portions",
        "third market",
        "positioning is allowed",
        "geographic quotas",
        "general knowledge without browsing",
        "each supported original endpoint",
        "because it helps a sibling",
        "equals any applicable opposite-side endpoint",
        "separate scope from a relationship that depends on an access gateway",
        "independent original relationship depend solely on a gateway",
        "materially circuitous candidates",
        "airport size or correct market alone is insufficient",
        "as hypotheses",
        "connection or connection quality",
        "feasibility as fact",
    ):
        assert required_rule in " ".join(str(request["instructions"]).casefold().split())
    assert generator.take_usage() == {
        "calls": 1,
        "captured_calls": 1,
        "missing_calls": 0,
        "input_tokens": 19,
        "output_tokens": 23,
        "total_tokens": 42,
    }
    trace = generator.take_call_traces()[0]
    assert trace["stage"] == "gateway_candidate_generator"
    assert trace["request"]["store"] is False
    assert trace["adapter"]["response_schema_sha256"]


def test_adapter_supports_empty_grouped_output_and_typed_errors() -> None:
    empty = GatewayCandidateProposal(
        endpoint_market_assessments=(),
        origin_access_gateways=(),
        destination_access_gateways=(),
        intermediate_hubs=(),
    )
    generator = OpenAIGatewayGenerator(
        OpenAIGatewayGeneratorConfig(model="test-gateway-generator"),
        client=cast(OpenAI, _Client(empty)),
    )
    assert generator.propose(_input()) == empty

    failing_client = _Client(ValueError("transport"))
    failing = OpenAIGatewayGenerator(
        OpenAIGatewayGeneratorConfig(model="test-gateway-generator"),
        client=cast(OpenAI, failing_client),
    )
    with pytest.raises(OpenAIGatewayGeneratorError):
        failing.propose(_input())
    assert len(failing_client.responses.calls) == 1
    assert failing.take_usage() == {
        "calls": 1,
        "captured_calls": 0,
        "missing_calls": 1,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }

    wrong_type_client = _Client(object())
    wrong_type = OpenAIGatewayGenerator(
        OpenAIGatewayGeneratorConfig(model="test-gateway-generator"),
        client=cast(OpenAI, wrong_type_client),
    )
    with pytest.raises(OpenAIGatewayGeneratorError, match="unexpected gateway-candidate output type"):
        wrong_type.propose(_input())
    assert len(wrong_type_client.responses.calls) == 1


def test_wire_schema_allows_over_product_cap_and_defers_iata_and_relationship_checks() -> None:
    raw = _proposal().model_dump(mode="python")
    raw["origin_access_gateways"] = [
        {
            "airport_iata": code,
            "reason": "",
            "material_uncertainty": "",
            "model_asserted_market_id": None,
            "supported_original_origin_iata_codes": [],
            "applicable_original_destination_iata_codes": [],
        }
        for code in ("one", "two", "three")
    ]
    parsed = GatewayCandidateProposal.model_validate(raw)
    assert [item.airport_iata for item in parsed.origin_access_gateways] == ["one", "two", "three"]
    assert parsed.origin_access_gateways[0].reason == ""

    raw["origin_access_gateways"] = raw["origin_access_gateways"] * 7
    with pytest.raises(ValidationError):
        GatewayCandidateProposal.model_validate(raw)


def test_wire_schema_defers_empty_scopes_sides_and_bad_endpoint_assessments() -> None:
    raw = _proposal().model_dump(mode="python")
    raw["endpoint_market_assessments"] = [
        {"role": "origin", "airport_id": "", "airport_iata": "", "model_asserted_market_id": ""}
    ]
    raw["intermediate_hubs"][0]["airport_iata"] = ""
    raw["intermediate_hubs"][0]["reason"] = ""
    raw["intermediate_hubs"][0]["scopes"] = [
        {"origin_side": [], "destination_side": [], "reason": ""}
    ]
    parsed = GatewayCandidateProposal.model_validate(raw)
    assert parsed.endpoint_market_assessments[0].airport_iata == ""
    assert parsed.intermediate_hubs[0].scopes[0].origin_side == ()


def test_wire_structural_safety_ceilings_apply_to_all_pools_scopes_and_references() -> None:
    raw = _proposal().model_dump(mode="python")
    candidate = raw["origin_access_gateways"][0]
    raw["origin_access_gateways"] = [candidate] * 21
    raw["destination_access_gateways"] = [
        {**candidate, "supported_original_destination_iata_codes": [], "applicable_original_origin_iata_codes": []}
    ] * 21
    raw["intermediate_hubs"] = [_proposal().model_dump(mode="python")["intermediate_hubs"][0]] * 21
    with pytest.raises(ValidationError):
        GatewayCandidateProposal.model_validate(raw)

    raw = _proposal().model_dump(mode="python")
    scope = raw["intermediate_hubs"][0]["scopes"][0]
    raw["intermediate_hubs"][0]["scopes"] = [scope] * 41
    with pytest.raises(ValidationError):
        GatewayCandidateProposal.model_validate(raw)
    raw = _proposal().model_dump(mode="python")
    reference = raw["intermediate_hubs"][0]["scopes"][0]["origin_side"][0]
    raw["intermediate_hubs"][0]["scopes"][0]["origin_side"] = [reference] * 41
    with pytest.raises(ValidationError):
        GatewayCandidateProposal.model_validate(raw)


def test_input_rejects_incoherent_market_context_and_bad_dates() -> None:
    raw = _input().model_dump(mode="python")
    raw["origin_endpoints"][0]["policy_market_name"] = "Wrong"
    with pytest.raises(ValidationError, match="name disagrees"):
        GatewayGeneratorModelInput.model_validate(raw)
    raw = _input().model_dump(mode="python")
    raw["origin_endpoints"][0]["role"] = "destination"
    with pytest.raises(ValidationError, match="role does not match"):
        GatewayGeneratorModelInput.model_validate(raw)
    raw = _input().model_dump(mode="python")
    raw["approved_markets"] = (*raw["approved_markets"], raw["approved_markets"][0])
    with pytest.raises(ValidationError, match="unique"):
        GatewayGeneratorModelInput.model_validate(raw)
    raw = _input().model_dump(mode="python")
    raw["outbound_date"]["start"] = "2026-10-08"
    with pytest.raises(ValidationError, match="end precedes"):
        GatewayGeneratorModelInput.model_validate(raw)


def _gate_for_builder() -> tuple[MarketGenerationGate, tuple[PlanningMarket, ...]]:
    origin = SelectedAirport(
        airport_id="airport:origin", airport_iata="SFO", airport_evidence_source_ids=("catalog",)
    )
    destination = SelectedAirport(
        airport_id="airport:destination", airport_iata="CDG", airport_evidence_source_ids=("catalog",)
    )
    receipt = CatalogKnowledgeReceipt(
        release_id="test", schema_version="1", source_date=date(2026, 1, 1),
        logical_content_sha256="a" * 64, manifest_sha256="b" * 64,
        database_sha256="c" * 64, source_bundle_manifest_sha256="d" * 64,
        source_artifacts=(CatalogSourceArtifactReceipt(artifact_name="source", bytes=1, sha256="e" * 64),),
    )
    compatibility = MarketPolicyCatalogCompatibility(
        authoring_release_id="test", authoring_logical_content_sha256="a" * 64,
        runtime_catalog_receipt=receipt, authoring_identity_matches_runtime=True,
    )
    gate = MarketGenerationGate(
        origin_endpoints=(origin,), destination_endpoints=(destination,),
        assignments=(
            AirportMarketAssignment(
                role="origin", endpoint=origin, catalog_country_code="US", catalog_iso_region="US-CA",
                market_id="us", source=MarketAssignmentSource.COUNTRY_ASSIGNMENT, mapping_gap=False,
            ),
            AirportMarketAssignment(
                role="destination", endpoint=destination, catalog_country_code="FR", catalog_iso_region="FR-IDF",
                market_id="europe", source=MarketAssignmentSource.COUNTRY_ASSIGNMENT, mapping_gap=False,
            ),
        ),
        compatibility=compatibility, status=MarketGenerationGateStatus.GENERATION_REQUIRED,
        known_market_ids=("europe", "us"),
    )
    markets = (
        PlanningMarket(market_id="europe", name="Europe", definition="A product policy market."),
        PlanningMarket(market_id="us", name="United States", definition="A product policy market."),
    )
    return gate, markets


def test_market_gate_builder_rejects_non_generation_and_order_mismatches() -> None:
    gate, markets = _gate_for_builder()
    outbound_date = GatewayOutboundDateContext(
        start=date(2026, 10, 5), end=date(2026, 10, 7), timezone="UTC", effective_window_precision="day"
    )
    built = GatewayGeneratorModelInput.from_market_gate(gate, markets, outbound_date)
    assert built.origin_endpoints[0].airport_iata == "SFO"
    assert built.destination_endpoints[0].catalog_iso_region == "FR-IDF"

    for status in (MarketGenerationGateStatus.SKIP_SINGLE_MARKET, MarketGenerationGateStatus.INPUT_ERROR):
        with pytest.raises(ValueError, match="generation-required"):
            GatewayGeneratorModelInput.from_market_gate(
                gate.model_copy(update={"status": status}), markets, outbound_date
            )
    wrong_assignment = gate.assignments[1].model_copy(update={"endpoint": gate.origin_endpoints[0]})
    with pytest.raises(ValueError, match="ordered endpoint"):
        GatewayGeneratorModelInput.from_market_gate(
            gate.model_copy(update={"assignments": (gate.assignments[0], wrong_assignment)}),
            markets,
            outbound_date,
        )


def test_schema_identity_strict_conversion_and_copy_isolation() -> None:
    assert GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256 == response_schema_sha256(
        GatewayCandidateProposal
    )
    from openai.lib._parsing import type_to_response_format_param

    converted = cast(dict[str, Any], type_to_response_format_param(GatewayCandidateProposal))
    assert cast(dict[str, Any], converted["json_schema"])["strict"] is True
    proposal = _proposal()
    assert proposal.origin_access_gateways is not proposal.origin_access_gateways
    assert proposal.origin_access_gateways[0] is not proposal.origin_access_gateways[0]
