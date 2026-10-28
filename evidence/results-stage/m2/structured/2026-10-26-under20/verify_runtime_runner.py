"""Deterministic controls for the actual-runtime confirmation harness."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import runtime_runner as runner

from award_agent.results.contracts import InputTokenReceipt, WriterReceipt


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    campaign_utils = runner.campaign_utils
    old_here = campaign_utils.HERE
    try:
        with tempfile.TemporaryDirectory(prefix="runtime-runner-check-") as temp:
            root = Path(temp)
            campaign_utils.HERE = root
            calls = root / "calls"
            calls.mkdir()
            campaign = {"maximum_input_count_calls": 2, "maximum_generation_calls": 2}
            campaign_utils.require_two_attempt_headroom(campaign)
            campaign_utils.write_json(calls / "count-001.json", {"status": "reserved"})
            try:
                campaign_utils.require_two_attempt_headroom(campaign)
            except ValueError as exc:
                check("two-call headroom" in str(exc), "headroom rejected for wrong reason")
            else:
                raise AssertionError("headroom check accepted only one remaining count slot")

            directory = root / "runs" / "wrapper-control"
            directory.mkdir(parents=True)
            measured_raw = {"object": "response.input_tokens", "input_tokens": 7}

            class FakeMeasurer:
                calls = 0

                def measure(self, request, config):
                    self.calls += 1
                    return InputTokenReceipt(request_digest=runner._digest(request),
                                             input_tokens=7, raw_response=measured_raw)

            fake_measurer = FakeMeasurer()
            recorder = runner.RecordingInputMeasurer(fake_measurer, directory, campaign)
            count_request = {"model": "fake", "input": "same token request"}
            receipt = recorder.measure(count_request, SimpleNamespace())
            saved_request = json.loads((directory / "final-01/count-request.json").read_text())
            saved_receipt = json.loads((directory / "final-01/count-receipt.json").read_text())
            check(fake_measurer.calls == 1, "count delegate was not called exactly once")
            check(saved_request == count_request, "count request was not preserved exactly")
            check(saved_receipt == receipt.model_dump(mode="json"),
                  "count receipt was not preserved exactly")

            response = {
                "id": "resp_fake", "status": "completed", "service_tier": "priority",
                "usage": {"input_tokens": 20, "output_tokens": 8, "total_tokens": 28,
                          "input_tokens_details": {"cached_tokens": 3},
                          "output_tokens_details": {"reasoning_tokens": 2}},
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": "{\"blocks\": []}"}]}]}
            raw = json.dumps(response)

            class FakeWriter:
                calls = 0

                def __init__(self):
                    self.pending = None

                def author(self, request, config, settings):
                    self.calls += 1
                    self.pending = WriterReceipt(raw_response=raw, status="completed",
                        usage={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28,
                               "first_event_ms": 11, "first_text_ms": 14},
                        latency_seconds=0.02)
                    return "{\"blocks\": []}"

                def take_receipt(self):
                    receipt, self.pending = self.pending, None
                    return receipt

            fake_writer = FakeWriter()
            writer = runner.RecordingInteractiveWriter(fake_writer, directory, campaign, "fast")
            request = {"model": "fake", "input": "payload"}
            config = SimpleNamespace(max_output_tokens=8192)
            settings = SimpleNamespace()
            output = writer.author(request, config, settings)
            captured = writer.take_receipt()
            check(output == "{\"blocks\": []}", "writer output changed")
            check(fake_writer.calls == 1, "writer delegate was not called exactly once")
            check(captured is not None and captured.raw_response == raw,
                  "writer raw receipt was not preserved")
            check(writer.take_receipt() is None, "captured writer receipt was returned twice")
            sdk_body = json.loads((directory / "final-01/generation-request.json").read_text())
            check(sdk_body == dict(request, max_output_tokens=8192, store=False,
                                   truncation="disabled", stream=True, service_tier="fast"),
                  "recorded generation body differs from the adapter's SDK request")
            timing = json.loads((directory / "final-01/generation-timing.json").read_text())
            check(timing["first_event_ms"] == 11 and timing["first_text_ms"] == 14,
                  "stream timing receipt fields were lost")
            check(json.loads((directory / "final-01/raw-response.json").read_text()) == response,
                  "raw response was not saved")

            before = len(list(calls.glob("*.json")))
            original_client = runner.OpenAI

            def forbidden_client(*args, **kwargs):
                raise AssertionError("offline mode constructed OpenAI")

            runner.OpenAI = forbidden_client
            try:
                offline = runner.run("admitted", "low", "offline-control", live=False,
                                     packet_profile="joined-v3")
            finally:
                runner.OpenAI = original_client
            check(offline["mode"] == "offline" and offline["live_calls"] == 0,
                  "default offline run did not report zero calls")
            check(offline["packet_profile"] == "joined-v3",
                  "offline v3 packet profile was not preserved")
            check(len(list(calls.glob("*.json"))) == before,
                  "offline mode consumed campaign budget")
            check(not (runner.HERE / "runs" / "offline-control").exists(),
                  "offline mode created a run directory")
    finally:
        campaign_utils.HERE = old_here
    print("runtime runner controls passed")


if __name__ == "__main__":
    main()
