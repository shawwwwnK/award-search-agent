"""Offline coverage for the bounded M2B gateway-discovery evaluator."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Self

import pytest

from award_agent.evaluation.gateway_discovery_live import (
    DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES,
    GatewayDiscoveryLiveFixtureError,
    load_gateway_discovery_live_cases,
    run_gateway_discovery_live_eval,
)
from award_agent.search_planning.contracts import (
    CatalogKnowledgeReceipt,
    CatalogSourceArtifactReceipt,
)
from award_agent.search_planning.gateway_generator import GatewayCandidateProposal
from award_agent.search_planning.knowledge import Airport, AirportSelectionMetadata
from award_agent.search_planning.market_policy import load_default_planning_market_policy


class _Generator:
    calls = 0

    def __init__(self, _config: object, *, fail: bool = False) -> None:
        self.fail = fail

    def propose(self, _input: object) -> GatewayCandidateProposal:
        type(self).calls += 1
        if self.fail:
            raise RuntimeError("private provider sentinel")
        return GatewayCandidateProposal(
            endpoint_market_assessments=(),
            origin_access_gateways=(),
            destination_access_gateways=(),
            intermediate_hubs=(),
        )

    def take_usage(self) -> dict[str, int]:
        return {
            "calls": 1,
            "captured_calls": 1,
            "missing_calls": 0,
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }

    def take_call_traces(self) -> list[dict[str, Any]]:
        return [{"input": "RAW_SENTINEL", "response": "PRIVATE_SENTINEL"}]


class _Repository:
    def __init__(self, _path: Path) -> None:
        cases = load_gateway_discovery_live_cases()
        policy = load_default_planning_market_policy()
        details: dict[str, tuple[str, str, str, str]] = {}
        for case in cases:
            for iata, value in case["catalog_endpoints"].items():
                details[iata] = (
                    value["airport_id"],
                    value["country_code"],
                    value["iso_region"],
                    value["airport_type"],
                )
        for override in policy.airport_overrides:
            details.setdefault(
                override.expected_iata,
                (
                    override.airport_id,
                    override.expected_country_code,
                    override.expected_iso_region,
                    "large_airport",
                ),
            )
        self.airports = {
            iata: Airport(
                airport_id=item[0],
                iata=iata,
                label=iata,
                country_entity_id=f"country:{item[1]}",
                timezone="UTC",
                aliases=(iata,),
                source_ids=(f"source:{iata}",),
            )
            for iata, item in details.items()
        }
        self.metadata = {
            airport.airport_id: AirportSelectionMetadata(
                airport_id=airport.airport_id,
                country_code=details[iata][1],
                iso_region=details[iata][2],
                airport_type=details[iata][3],
                latitude=0,
                longitude=0,
            )
            for iata, airport in self.airports.items()
        }
        self.knowledge_receipt = CatalogKnowledgeReceipt(
            release_id="m1a-3cb7981519612945",
            schema_version="v1",
            source_date=date(2026, 9, 18),
            logical_content_sha256="8066652e581947400badef958916dad9dd641de1a0d423a1a601e0e91bcff1d8",
            manifest_sha256="1" * 64,
            database_sha256="2" * 64,
            source_bundle_manifest_sha256="3" * 64,
            source_artifacts=(
                CatalogSourceArtifactReceipt(artifact_name="test", bytes=1, sha256="4" * 64),
            ),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def lookup_airport_iata(self, iata: str) -> Airport | None:
        return self.airports.get(iata)

    def airport(self, airport_id: str) -> Airport | None:
        return next(
            (item for item in self.airports.values() if item.airport_id == airport_id), None
        )

    def airport_selection_metadata(self, airport_id: str) -> AirportSelectionMetadata | None:
        return self.metadata.get(airport_id)


def test_complete_casebook_loads_with_one_skip_and_expected_examples() -> None:
    cases = load_gateway_discovery_live_cases()
    assert DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES == Path(
        "evals/gateway_discovery/development_cases_v1.yaml"
    )
    assert len(cases) == 8
    assert sum(case["expected_gate"] == "skip_single_market" for case in cases) == 1
    assert {"west_coast_to_paris_multi_origin", "san_francisco_to_southeast_asia_endpoints"} <= {
        case["id"] for case in cases
    }


def test_fixture_rejects_policy_version_drift(tmp_path: Path) -> None:
    contents = DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES.read_text().replace(
        "planning-market-v1", "bad-policy", 1
    )
    path = tmp_path / "bad.yaml"
    path.write_text(contents)
    with pytest.raises(GatewayDiscoveryLiveFixtureError, match="does not bind"):
        run_gateway_discovery_live_eval(fixture_path=path, repository_factory=_Repository)


def test_two_trial_fake_run_is_bounded_redacted_and_replayable(tmp_path: Path) -> None:
    _Generator.calls = 0
    artifact = run_gateway_discovery_live_eval(
        trials=2, trace_dir=tmp_path, generator_factory=_Generator, repository_factory=_Repository
    )
    public = json.dumps(artifact)
    assert artifact["summary"]["mechanically_completed"] is True
    assert artifact["summary"]["expected_calls"] == 14
    assert artifact["summary"]["attempted_calls"] == 14
    assert artifact["summary"]["constructed_calls"] == 14
    assert _Generator.calls == 14
    assert "RAW_SENTINEL" not in public and "PRIVATE_SENTINEL" not in public
    sidecar = Path(artifact["records"][0]["private_trace"]["path"])
    assert "RAW_SENTINEL" in sidecar.read_text()
    private_record = Path(artifact["records"][0]["private_trace"]["record_path"])
    assert json.loads(private_record.read_text())["gateway_discovery_result"] is not None
    skip = next(
        record for record in artifact["records"] if record["expected_gate"] == "skip_single_market"
    )
    assert skip["trace_reconciliation"]["constructed"] is False
    assert all(
        record["gate_expectation_matches"] and record["endpoint_preserved"]
        for record in artifact["records"]
    )


def test_provider_failure_is_a_typed_completed_generation_failure(tmp_path: Path) -> None:
    artifact = run_gateway_discovery_live_eval(
        trials=1,
        max_cases=1,
        trace_dir=tmp_path,
        generator_factory=lambda config: _Generator(config, fail=True),
        repository_factory=_Repository,
    )
    record = artifact["records"][0]
    assert record["status"] == "completed"
    assert record["outcome"] == "generation_failure"
    assert record["trace_reconciliation"]["reconciled"] is True


class _MissingTelemetryGenerator(_Generator):
    def take_usage(self) -> dict[str, int]:
        return {}


class _TraceAccessorFailureGenerator(_Generator):
    def take_call_traces(self) -> list[dict[str, Any]]:
        raise RuntimeError("private trace failure")


@pytest.mark.parametrize("generator", [_MissingTelemetryGenerator, _TraceAccessorFailureGenerator])
def test_missing_or_failed_capture_makes_run_mechanically_incomplete(
    tmp_path: Path, generator: type[_Generator]
) -> None:
    artifact = run_gateway_discovery_live_eval(
        trials=1,
        max_cases=1,
        trace_dir=tmp_path,
        generator_factory=generator,
        repository_factory=_Repository,
    )
    assert artifact["records"][0]["status"] == "completed"
    assert artifact["records"][0]["trace_reconciliation"]["reconciled"] is False
    assert artifact["summary"]["mechanically_completed"] is False


def test_complete_preflight_rejects_late_fixture_drift_before_any_generator_call(
    tmp_path: Path,
) -> None:
    _Generator.calls = 0
    contents = DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES.read_text().replace(
        "union: [europe, us]", "union: [europe]", 1
    )
    fixture = tmp_path / "drift.yaml"
    fixture.write_text(contents)
    with pytest.raises(GatewayDiscoveryLiveFixtureError, match="expected union"):
        run_gateway_discovery_live_eval(
            fixture_path=fixture,
            generator_factory=_Generator,
            repository_factory=_Repository,
        )
    assert _Generator.calls == 0


def test_preflight_gate_drift_constructs_no_generator(tmp_path: Path) -> None:
    _Generator.calls = 0
    contents = DEFAULT_GATEWAY_DISCOVERY_LIVE_FIXTURES.read_text().replace(
        "origin: [us]\n      destination: [europe]\n      union: [europe, us]",
        "origin: [europe]\n      destination: [europe]\n      union: [europe]",
        1,
    )
    fixture = tmp_path / "gate-drift.yaml"
    fixture.write_text(contents)
    with pytest.raises(GatewayDiscoveryLiveFixtureError, match="does not reproduce"):
        run_gateway_discovery_live_eval(
            fixture_path=fixture,
            generator_factory=_Generator,
            repository_factory=_Repository,
        )
    assert _Generator.calls == 0


def test_private_evaluator_error_retains_message_while_public_does_not(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import award_agent.evaluation.gateway_discovery_live as evaluator

    monkeypatch.setattr(
        evaluator,
        "replay_gateway_discovery_result",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("PRIVATE_EVALUATOR_SENTINEL")),
    )
    artifact = evaluator.run_gateway_discovery_live_eval(
        trials=1,
        max_cases=1,
        trace_dir=tmp_path,
        generator_factory=_Generator,
        repository_factory=_Repository,
    )
    public = json.dumps(artifact)
    private = Path(artifact["records"][0]["private_trace"]["record_path"]).read_text()
    assert "PRIVATE_EVALUATOR_SENTINEL" not in public
    assert "PRIVATE_EVALUATOR_SENTINEL" in private


def test_cli_writes_artifact_and_returns_mechanical_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from award_agent.cli import gateway_discovery_live_eval as cli

    monkeypatch.setattr(
        cli,
        "run_gateway_discovery_live_eval",
        lambda **_kwargs: {"summary": {"mechanically_completed": True}, "records": []},
    )
    output = tmp_path / "artifact.json"
    assert cli.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text())["summary"]["mechanically_completed"] is True
