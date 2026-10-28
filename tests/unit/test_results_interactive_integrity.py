"""Saved v7 response evidence must agree with a recoverable draft."""

import json
from pathlib import Path

import pytest

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive import (
    prepare_interactive_results,
    replay_interactive_results,
    run_interactive_results,
)
from award_agent.results.interactive_contracts import (
    InteractiveResultsArtifact,
    InteractiveSettings,
)


@pytest.fixture(scope="module")
def saved_artifact() -> InteractiveResultsArtifact:
    return InteractiveResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/structured/2026-10-26-under20/runs/"
        "confirm-1-admitted/artifact.json").read_bytes())


def _tampered(saved: InteractiveResultsArtifact) -> dict[str, object]:
    return saved.model_dump(mode="json")


def test_saved_recoverable_response_still_replays(
        saved_artifact: InteractiveResultsArtifact) -> None:
    assert replay_interactive_results(saved_artifact) == saved_artifact.resolved


@pytest.mark.parametrize("field,value", (("error", "schema_error"),
                                         ("failure_subtype", "schema_error")))
def test_recoverable_cannot_carry_failure_metadata(
        saved_artifact: InteractiveResultsArtifact, field: str, value: str) -> None:
    raw = _tampered(saved_artifact)
    raw["attempts"][0][field] = value
    with pytest.raises(ValueError, match="failure metadata"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_recoverable_raw_response_must_be_completed(
        saved_artifact: InteractiveResultsArtifact) -> None:
    raw = _tampered(saved_artifact)
    receipt = raw["attempts"][0]["writer_receipt"]
    response = json.loads(receipt["raw_response"])
    response["status"] = "incomplete"
    receipt["raw_response"] = json.dumps(response)
    receipt["status"] = "incomplete"
    with pytest.raises(ValueError, match="not completed"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_recoverable_raw_response_cannot_contain_refusal(
        saved_artifact: InteractiveResultsArtifact) -> None:
    raw = _tampered(saved_artifact)
    receipt = raw["attempts"][0]["writer_receipt"]
    response = json.loads(receipt["raw_response"])
    response["output"].append({"type": "message", "content": [
        {"type": "refusal", "refusal": "declined"}]})
    receipt["raw_response"] = json.dumps(response)
    with pytest.raises(ValueError, match="refusal"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_measurement_error_cannot_claim_writer_invocation(
        saved_artifact: InteractiveResultsArtifact) -> None:
    raw = _tampered(saved_artifact)
    attempt = raw["attempts"][0]
    attempt["outcome"] = "measurement_error"
    attempt["document"] = None
    attempt["findings"] = []
    attempt["raw_wire"] = None
    with pytest.raises(ValueError, match="measurement error invoked writer"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(raw))


def test_joined_v4_packet_keeps_local_alias_registry_out_of_writer_input() -> None:
    projection = SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())
    config = ResultsConfig(model="offline-test", max_output_tokens=1000, timeout_seconds=10,
                           context_limit_tokens=10_000_000, prompt_overhead_tokens=0)
    prepared = prepare_interactive_results(projection, config, packet_profile="joined-v4")
    assert prepared.packet["format"] == "decision-joined-v4"
    alias = next(new for new, old in prepared.packet["wire_aliases"].items()
                 if old in prepared.structured.references.journeys)
    wire = json.dumps({"blocks": [{"k": "p", "r": alias,
                                    "n": "Useful choice", "v": "Consider this itinerary."}]})

    class FakeWriter:
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            return wire

        def take_receipt(self) -> WriterReceipt:
            return WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": wire}]}]}))

    artifact = run_interactive_results(projection, config,
        InteractiveSettings(reasoning_effort="none"), FakeWriter(), packet_profile="joined-v4")
    assert artifact.delivery_outcome == "delivered"
    assert artifact.prepared.packet["wire_aliases"][alias] in prepared.structured.references.journeys
    payload = json.loads(artifact.attempts[0].request["input"])
    assert payload["packet"]["format"] == "decision-joined-v4"
    assert "wire_aliases" not in payload["packet"]
    assert replay_interactive_results(artifact) == artifact.resolved

    tampered = artifact.model_dump(mode="json")
    tampered["prepared"]["packet"]["wire_aliases"][alias] = "J999"
    with pytest.raises(ValueError, match="preparation"):
        replay_interactive_results(InteractiveResultsArtifact.model_validate(tampered))
