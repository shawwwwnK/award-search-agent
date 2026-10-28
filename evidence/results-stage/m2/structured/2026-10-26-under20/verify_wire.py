"""Offline controls for exact-role lean wire and request accounting."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import harness
import httpx
from wire import decode_wire

from award_agent.providers.contracts import content_digest
from award_agent.results.contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsWriterError,
    WriterReceipt,
)
from award_agent.results.runner import run_attempts
from award_agent.results.structured import check_structured_document, prepare_structured_results
from award_agent.results.structured_contracts import StructuredResultsArtifact


def fails(fn, phrase: str) -> None:
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), (phrase, str(exc))
    else:
        raise AssertionError(f"expected {phrase}")


def main() -> None:
    source = harness.SOURCE / "admitted" / "artifact.json"
    config_path = harness.SOURCE / "admitted" / "config.json"
    artifact = StructuredResultsArtifact.model_validate_json(source.read_text())
    projection = artifact.evidence.source
    config = ResultsConfig.model_validate_json(config_path.read_text())
    prepared = prepare_structured_results(projection, config)
    refs = prepared.references
    eligible = {x.candidate_id for x in projection.view.alternatives
                if x.status in {"admitted", "conditional"}}
    journey = next(alias for alias, canonical in refs.journeys.items() if canonical in eligible)
    benchmark = next(alias for alias, canonical in refs.cash.items()
                     if canonical in projection.view.direct_cash_observation_ids)
    benchmark2 = next(alias for alias, canonical in refs.cash.items()
                      if canonical in projection.view.direct_cash_observation_ids and alias != benchmark)
    leads = (set(projection.view.award_summary_observation_ids) |
             set(projection.view.unmatched_award_observation_ids) |
             set(projection.view.unpaired_positioning_observation_ids))
    lead = next(alias for alias, canonical in (refs.awards | refs.cash).items()
                if canonical in leads)
    p = {"k": "p", "r": journey, "n": "First choice", "v": "A useful option."}
    a = {"k": "a", "r": journey, "n": "Another view", "v": "Still an option."}
    b = {"k": "b", "r": benchmark, "n": "Cash", "v": "Direct cash context."}
    l = {"k": "l", "r": lead, "n": "Lead", "v": "Incomplete option."}
    t = {"k": "t", "v": "These are the limits."}
    doc = decode_wire({"blocks": [t, a, p, a, p, b, b, l]}, prepared, projection)
    assert len(doc.blocks) == 8 and doc.blocks[0].kind == "narrative"
    assert doc.selection.journey_ids == (refs.journeys[journey],)
    assert doc.selection.benchmark_observation_id == refs.cash[benchmark]
    assert doc.selection.incomplete_observation_ids == ((refs.awards | refs.cash)[lead],)
    assert all(block.claims == () for block in doc.blocks)
    assert doc.blocks[1].reference_id == doc.blocks[2].reference_id
    fails(lambda: decode_wire({"blocks": [dict(p, r="J999999")]}, prepared, projection), "unknown or wrong-role")
    fails(lambda: decode_wire({"blocks": [dict(p, r=benchmark)]}, prepared, projection), "unknown or wrong-role")
    fails(lambda: decode_wire({"blocks": [dict(b, r=journey)]}, prepared, projection), "unknown or wrong-role")
    fails(lambda: decode_wire({"blocks": [dict(l, r=benchmark)]}, prepared, projection), "unknown or wrong-role")
    fails(lambda: decode_wire({"blocks": [dict(p, n="  ")]}, prepared, projection), "nonblank")
    fails(lambda: decode_wire({"blocks": [b, dict(b, r=benchmark2)]}, prepared, projection), "one distinct benchmark")
    fails(lambda: decode_wire({"blocks": [dict(t, r=journey)]}, prepared, projection), "invalid wire fields")

    request = harness.request_for_packet({"cards": []}, config, "none", prepared)
    assert request["reasoning"] == {"effort": "none"}
    assert request["text"]["format"]["schema"]["properties"]["blocks"]["items"]["anyOf"]
    envelope = harness._envelope(request, config)
    assert envelope.prompt_digest and envelope.schema_digest
    assert harness.run("admitted", "none", "offline", live=False)["live_calls"] == 0

    with tempfile.TemporaryDirectory() as tmp:
        old_here = harness.HERE
        harness.HERE = Path(tmp)
        try:
            campaign = {"maximum_input_count_calls": 1, "maximum_generation_calls": 1}
            ordinal = harness.reserve("count", "first", campaign, run_name="fake",
                                      request_digest=content_digest(request))
            assert ordinal == 1
            saved = json.loads((Path(tmp) / "calls/count-001.json").read_text())
            assert saved["request_digest"] == content_digest(request)
            fails(lambda: harness.reserve("count", "second", campaign, run_name="fake",
                                          request_digest="other"), "bound exhausted")
        finally:
            harness.HERE = old_here

    with tempfile.TemporaryDirectory() as tmp:
        old_here, old_campaign = harness.HERE, harness.CAMPAIGN
        harness.HERE = Path(tmp)
        harness.CAMPAIGN = Path(tmp) / "campaign.json"
        campaign = {"maximum_input_count_calls": 48, "maximum_generation_calls": 48}
        harness.CAMPAIGN.write_text(json.dumps(campaign))
        (Path(tmp) / "calls").mkdir()
        for index in range(47):
            (Path(tmp) / "calls" / f"count-{index + 1:03}.json").write_text("{}")
        try:
            fails(lambda: harness.run("admitted", "none", "blocked", live=True),
                  "two-call headroom")
            assert not (Path(tmp) / "runs/blocked").exists()
        finally:
            harness.HERE, harness.CAMPAIGN = old_here, old_campaign

    class TimedOutResponses:
        def create(self, **_kwargs):
            raise httpx.ReadTimeout("synthetic stream timeout")

    class TimedOutClient:
        responses = TimedOutResponses()
        def with_options(self, **_kwargs):
            return self

    with tempfile.TemporaryDirectory() as tmp:
        old_here = harness.HERE
        harness.HERE = Path(tmp)
        try:
            endpoint = harness.Endpoint(Path(tmp) / "run", {
                "maximum_input_count_calls": 1, "maximum_generation_calls": 1},
                config, TimedOutClient(), "fast")
            try:
                endpoint.generate(request, "final-01", max_output_tokens=8192)
            except ResultsWriterError as exc:
                assert exc.outcome == "api_error"
            else:
                raise AssertionError("synthetic timeout must surface")
            generation_request = json.loads((Path(tmp) / "run/final-01/generation-request.json").read_text())
            assert generation_request["service_tier"] == "fast"
            assert "service_tier" not in request  # execution control excluded from count input
            assert (Path(tmp) / "run/final-01/generation-error.json").is_file()
            assert (Path(tmp) / "calls/generation-001.json").is_file()
        finally:
            harness.HERE = old_here

    class FakeMeasurer:
        def measure(self, value: dict[str, object], _config: ResultsConfig) -> InputTokenReceipt:
            return InputTokenReceipt(request_digest=content_digest(value), input_tokens=100,
                                     raw_response={"object": "response.input_tokens", "input_tokens": 100})

    called = 0
    def invoke(_feedback, _previous):
        nonlocal called
        called += 1
        return doc

    outcome = run_attempts(config, FakeMeasurer(), request_for=lambda _f, _p: envelope,
                           invoke=invoke, check=lambda _d: (),
                           take_receipt=lambda: WriterReceipt(status="completed"))
    assert called == 1 and outcome.attempts[0].input_token_receipt is not None
    correction_requests = []
    failed = CheckFinding(code="synthetic_correction", outcome="failed", scope="journey",
                          reference_id=refs.journeys[journey], part_index=2,
                          message="Reconsider this option.")

    def second_request(feedback, previous):
        value = harness.request_for_packet({"cards": []}, config, "low", prepared,
                                           feedback, previous)
        correction_requests.append(value)
        return harness._envelope(value, config)

    corrected = run_attempts(config, FakeMeasurer(), request_for=second_request,
                             invoke=lambda _f, _p: doc,
                             check=lambda _d: (failed,) if len(correction_requests) == 1 else (),
                             take_receipt=lambda: WriterReceipt(status="completed"))
    assert len(corrected.attempts) == 2
    second_input = json.loads(correction_requests[1]["input"])
    assert second_input["feedback"][0]["r"] == journey
    prior_blocks = second_input["previous_wire"]["blocks"]
    assert [row["k"] for row in prior_blocks] == ["t", "p", "p", "p", "p", "b", "b", "l"]
    assert [row.get("r") for row in prior_blocks] == [None, journey, journey, journey,
                                                      journey, benchmark, benchmark, lead]
    assert [row["v"] for row in prior_blocks] == [row["v"] for row in [t, a, p, a, p, b, b, l]]
    assert refs.journeys[journey] not in correction_requests[1]["input"]
    assert refs.cash[benchmark] not in correction_requests[1]["input"]
    assert (refs.awards | refs.cash)[lead] not in correction_requests[1]["input"]
    bad = run_attempts(config, FakeMeasurer(), request_for=lambda _f, _p: envelope,
                       invoke=lambda _f, _p: decode_wire({"blocks": [b, dict(b, r=benchmark2)]},
                                                          prepared, projection),
                       check=lambda _d: (), take_receipt=lambda: None)
    assert len(bad.attempts) == 1 and bad.attempts[0].failure_subtype == "schema_error"
    # Existing checker remains active independently of omitted claim declarations.
    assert isinstance(check_structured_document(doc, projection, prepared), tuple)
    print("wire controls passed: roles, selections, schema failure, claims, request binding, cap, timeout, tier, offline gate")


if __name__ == "__main__":
    main()
