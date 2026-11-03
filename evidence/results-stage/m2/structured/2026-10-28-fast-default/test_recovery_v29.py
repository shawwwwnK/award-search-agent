"""Focused offline V29 branch, quota, failed-check correction, and replay control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import verify
from run import DEFAULT_CONFIG, RECOVERY_GUIDANCE, append_recovery_guidance


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "tests/unit"))
    from test_results_focused import FakeMeasurer, _source as complete_source_factory
    from test_results_focused_v21 import _source as incomplete_source_factory

    from award_agent.results.contracts import ResultsConfig, WriterReceipt
    from award_agent.results.focused import replay_focused_results, run_focused_results

    config = ResultsConfig.model_validate_json(DEFAULT_CONFIG.read_bytes())
    config = config.model_copy(update={"authoring_guidance": append_recovery_guidance(
        config.authoring_guidance, RECOVERY_GUIDANCE.read_text(encoding="utf-8"))})

    class V29Writer:
        def __init__(self, *, incomplete: bool, inject_failure: bool) -> None:
            self.incomplete = incomplete
            self.inject_failure = inject_failure
            self.calls: list[dict[str, object]] = []
            self.receipts: list[WriterReceipt] = []
            self.pending: WriterReceipt | None = None

        def author(self, request, _config, settings):
            index = len(self.calls)
            expected_effort = ("medium" if self.incomplete and index == 0 else
                               "low" if index == 0 or index == 2 else
                               "low" if self.incomplete else "medium")
            assert settings.reasoning_effort == expected_effort
            assert settings.service_tier == "fast"
            self.calls.append(request)
            payload = json.loads(request["input"])
            packet = payload["packet"]
            if index == 0:
                if self.incomplete:
                    records = [member["record"]
                               for group in packet["lead_program_groups"]
                               for member in group["members"]]
                    refs = [row["A_or_C"] for row in records[:2]]
                    role = "l"
                else:
                    refs = list(packet["journey_records"])[:2]
                    role = "j"
                assert len(refs) == 2
                raw = {"choices": [
                    {"k": role, "r": ref, "purpose": "Compare a source-backed choice",
                     "compare_to": refs[(index_choice + 1) % len(refs)]}
                    for index_choice, ref in enumerate(refs)]}
            else:
                refs = [ref for ref, record in packet["authoring_records"].items()
                        if record["role"] in {"journey", "lead"}][:2]
                assert len(refs) == 2
                lead_only = all(packet["authoring_records"][ref]["role"] == "lead"
                                for ref in refs)
                if index == 1:
                    first = "" if self.inject_failure else "A useful source-backed explanation."
                    blocks = ([{"k": "l", "r": refs[0], "n": "First lead", "v": first},
                               {"k": "l", "r": refs[1], "n": "Second lead",
                                "v": "A useful alternative explanation."}]
                              if lead_only else
                              [{"k": "p", "r": refs[0], "n": "First choice", "v": first},
                               {"k": "a", "r": refs[1], "n": "Alternative",
                                "v": "A useful alternative explanation."}])
                    if self.inject_failure:
                        assert self.incomplete and lead_only
                else:
                    assert index == 2 and payload["feedback"]
                    assert all(row["outcome"] == "failed" for row in payload["feedback"])
                    blocks = ([{"k": "l", "r": refs[0], "n": "First lead",
                                "v": "A useful source-backed explanation."},
                               {"k": "l", "r": refs[1], "n": "Second lead",
                                "v": "A useful alternative explanation."}]
                              if lead_only else
                              [{"k": "p", "r": refs[0], "n": "First choice",
                                "v": "A useful source-backed explanation."},
                               {"k": "a", "r": refs[1], "n": "Alternative",
                                "v": "A useful alternative explanation."}])
                blocks.append({"k": "t", "v": "Source-bound limitations apply."})
                raw = {"blocks": blocks}
            text = json.dumps(raw)
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority",
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": text}]}]}))
            return text

        def take_receipt(self):
            receipt, self.pending = self.pending, None
            return receipt

    complete_source = complete_source_factory()
    complete_writer = V29Writer(incomplete=False, inject_failure=False)
    complete = run_focused_results(complete_source, config, complete_writer, FakeMeasurer(),
                                   profile="focused-v29")
    assert complete.contract_version == "results-artifact-v11"
    assert complete.selector_prepared.packet["selection_format"] == "roles-v28"
    assert complete.focus_prepared.packet["composition_format"] == "complete-v26"
    assert complete.selector_settings.reasoning_effort == "low"
    assert complete.composer_settings.reasoning_effort == "medium"
    assert complete.correction_settings.reasoning_effort == "low"
    assert len(complete.passes) == len(complete_writer.calls) == 2
    assert replay_focused_results(complete) == complete.resolved

    incomplete_source, _, _ = incomplete_source_factory("scout-v19-incomplete")
    incomplete_writer = V29Writer(incomplete=True, inject_failure=True)
    incomplete = run_focused_results(incomplete_source, config, incomplete_writer,
                                     FakeMeasurer(), profile="focused-v29")
    assert incomplete.selector_prepared.packet["selection_format"] == "roles-v29"
    assert incomplete.focus_prepared.packet["composition_format"] == "complete-v27"
    assert incomplete.selector_settings.reasoning_effort == "medium"
    assert incomplete.composer_settings.reasoning_effort == "low"
    assert incomplete.correction_settings.reasoning_effort == "low"
    assert len(incomplete.passes) == len(incomplete_writer.calls) == 3
    assert any(finding.outcome == "failed" for finding in incomplete.passes[1].findings)
    assert not any(finding.outcome == "failed" for finding in incomplete.passes[2].findings)
    selector_pass = incomplete.passes[0]
    assert not verify._v28_selector_issues(
        selector_pass.request, selector_pass.raw_wire, selector_pass.selection)
    assert not verify._v29_selector_issues(selector_pass.request,
                                            incomplete.selector_prepared)
    assert not verify._v23_correction_issues(incomplete.passes[1], incomplete.passes[2])
    assert replay_focused_results(incomplete) == incomplete.resolved
    print("V29 complete and grouped-incomplete correction/replay controls passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
