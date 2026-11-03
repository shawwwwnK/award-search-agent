"""Offline V11-V23 induced-fault recovery and authoring replay."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from run import DEFAULT_CONFIG, RECOVERY_GUIDANCE, append_recovery_guidance
import verify


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "tests/unit"))
    from test_results_focused import FakeMeasurer, _source

    from award_agent.results.contracts import ResultsConfig, WriterReceipt
    from award_agent.results.focused import replay_focused_results, run_focused_results

    guidance = RECOVERY_GUIDANCE.read_text(encoding="utf-8")
    candidate = ResultsConfig.model_validate_json(DEFAULT_CONFIG.read_bytes())
    assert candidate.authoring_guidance
    assert append_recovery_guidance(candidate.authoring_guidance, guidance) == \
        candidate.authoring_guidance + "\n" + guidance

    class DiagnosticWriter:
        def __init__(self, composer_effort: str, selector_effort: str,
                     editor_effort: str = "medium", *,
                     overflow_choices: bool = False,
                     profile: str = "",
                     inject_alias_fault: bool = True) -> None:
            self.composer_effort = composer_effort
            self.selector_effort = selector_effort
            self.editor_effort = editor_effort
            self.overflow_choices = overflow_choices
            self.profile = profile
            self.inject_alias_fault = inject_alias_fault
            self.calls = []
            self.pending = None

        def author(self, request, config, settings):
            index = len(self.calls)
            assert settings.service_tier == "fast"
            is_editor = request["text"]["format"]["name"] == "FocusedResultsEditorialPatch"
            assert settings.reasoning_effort == (self.composer_effort if index == 1 else
                                                self.selector_effort if index == 0 else
                                                self.editor_effort if is_editor else "low")
            self.calls.append(request)
            payload = json.loads(request["input"])
            packet = payload["packet"]
            if index == 0:
                assert guidance in request["instructions"]
                if packet.get("selection_format") in {"roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v27"}:
                    refs = [row["A_or_C"] for row in packet["lead_records"][:2]]
                elif "journey_records" in packet:
                    refs = list(packet["journey_records"])[
                        :5 if self.overflow_choices else 2]
                else:
                    refs = [row[0] for row in packet["journey_rows"][:2]]
                role = "l" if packet.get("selection_format") in {"roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v27"} else "j"
                raw = json.dumps({"choices": ([
                    {"k": role, "r": ref, "purpose": "Compare a real decision tradeoff",
                     "compare_to": refs[(i + 1) % len(refs)]} for i, ref in enumerate(refs)]
                    if packet.get("selection_format") in {"roles-v13", "roles-v14", "roles-v15", "roles-v16", "roles-v17", "roles-v18", "roles-v19", "roles-v20", "roles-v21", "roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v26", "roles-v27"} else
                    [{"k": "j", "r": ref} for ref in refs])})
            elif self.profile in {"focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28"} and index == 2:
                assert payload["feedback"] and all(row["outcome"] == "failed"
                                                    for row in payload["feedback"])
                selected_records = [(ref, row) for ref, row in packet["authoring_records"].items()
                                    if row["role"] in {"journey", "lead"}]
                refs = [ref for ref, _ in selected_records]
                lead_only = all(row["role"] == "lead" for _, row in selected_records)
                blocks = ([
                    {"k": "l", "r": refs[0], "n": "First lead", "v": "Useful first check."},
                    {"k": "l", "r": refs[1], "n": "Second lead", "v": "Useful alternative check."}]
                    if lead_only else [
                    {"k": "p", "r": refs[0], "n": "First", "v": "Useful first choice."},
                    {"k": "a", "r": refs[1], "n": "Second", "v": "Useful alternative."}])
                raw = json.dumps({"blocks": [
                    *blocks,
                    *([{"k": "x", "r": packet["temporal_comparisons"][0]["id"]}]
                      if packet.get("temporal_comparisons") else []),
                    {"k": "t", "v": "Source-bound limitations apply."}]})
            elif packet.get("composition_format") in {"complete-v14", "complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19"} and index == 2:
                assert payload["revision_trigger"] == "editorial_revision"
                assert payload["feedback"]
                if packet.get("composition_format") in {"complete-v15", "complete-v16", "complete-v17", "complete-v18", "complete-v19"}:
                    assert "numbered_draft" not in payload
                    assert all(row["index"] == i for i, row in enumerate(
                        payload["previous_wire"]["blocks"]))
                end = len(payload["previous_wire"]["blocks"])
                raw = json.dumps({"edits": [{"start": end - 1, "end": end,
                    "blocks": [{"k": "t", "v": "Source-bound limitations apply."}]}]})
            else:
                assert guidance in request["instructions"]
                selected_records = ([(ref, row) for ref, row in packet["authoring_records"].items()
                                     if row["role"] in {"journey", "lead"}]
                        if "authoring_records" in packet else
                        [(member["ref"], {}) for group in packet["journeys"]
                         for member in group["members"]])
                refs = [ref for ref, _ in selected_records]
                lead_only = bool(selected_records) and all(
                    row.get("role") == "lead" for _, row in selected_records)
                blocks = ([{"k": "l", "r": refs[0], "n": "First lead", "v": "Useful first check."},
                           {"k": "l", "r": refs[1], "n": "Second lead", "v": "Useful alternative check."}]
                          if lead_only else
                          [{"k": "p", "r": refs[0], "n": "First", "v": "Useful first choice."},
                           {"k": "a", "r": refs[1], "n": "Second", "v": "Useful alternative."}])
                if packet.get("temporal_comparisons"):
                    blocks.append({"k": "x", "r": packet["temporal_comparisons"][0]["id"]})
                if index == 1:
                    assert "previous_wire" not in payload
                    if self.inject_alias_fault:
                        if lead_only:
                            blocks[0]["v"] = ""
                        else:
                            alias = refs[0].split("@")[0]
                            blocks.append({"k": "t", "v": f"Internal note {alias} is visible."})
                else:
                    assert "previous_wire" in payload and payload["feedback"]
                raw = json.dumps({"blocks": blocks})
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority",
                "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": raw}]}]}))
            return raw

        def take_receipt(self):
            receipt, self.pending = self.pending, None
            return receipt

    config = candidate.model_copy(update={"authoring_guidance":
        append_recovery_guidance(candidate.authoring_guidance, guidance)})
    v23_complete_requests = None
    for profile, effort, formats in (("focused-v11", "medium", ("roles-v10", "complete-v8")),
                                     ("focused-v12", "low", ("roles-v11", "complete-v9")),
                                     ("focused-v13", "medium", ("roles-v12", "complete-v10")),
                                     ("focused-v14", "medium", ("roles-v13", "complete-v11")),
                                     ("focused-v15", "medium", ("roles-v14", "complete-v12")),
                                     ("focused-v16", "medium", ("roles-v15", "complete-v13")),
                                     ("focused-v17", "low", ("roles-v16", "complete-v14")),
                                     ("focused-v18", "low", ("roles-v17", "complete-v15")),
                                     ("focused-v19", "low", ("roles-v18", "complete-v16")),
                                     ("focused-v20", "low", ("roles-v19", "complete-v17")),
                                     ("focused-v21", "low", ("roles-v20", "complete-v18")),
                                     ("focused-v22", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v23", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v24", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v25", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v26", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v27", "low", ("roles-v21", "complete-v19")),
                                     ("focused-v28", "medium", ("roles-v26", "complete-v24"))):
        writer = DiagnosticWriter(effort,
                                  "none" if profile == "focused-v21" else
                                  "none" if profile in {"focused-v22", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28"} else
                                  "medium" if profile == "focused-v14" else "low",
                                  "low" if profile in {"focused-v18", "focused-v19", "focused-v20", "focused-v23", "focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28"} else "medium",
                                  profile=profile)
        artifact = run_focused_results(_source(), config, writer, FakeMeasurer(),
                                       profile=profile)
        assert len(writer.calls) == len(artifact.passes) == 3
        assert [item.phase for item in artifact.passes] == [
            "selection", "composition",
            "editorial_revision" if profile in {"focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22"} else "correction"]
        assert (artifact.selector_prepared.packet["selection_format"],
                artifact.focus_prepared.packet["composition_format"]) == formats
        assert any(f.code == "visible_internal_alias" and f.outcome == "failed"
                   for f in artifact.passes[1].findings)
        assert not any(f.code == "visible_internal_alias" and f.outcome == "failed"
                       for f in artifact.passes[2].findings)
        assert artifact.composer_settings.reasoning_effort == effort
        if profile == "focused-v23":
            assert artifact.correction_settings.reasoning_effort == "low"
            assert artifact.correction_settings.service_tier == "fast"
            packet = json.loads(writer.calls[1]["input"])["packet"]
            assert not verify._pair_packet_issues(
                packet, selection_format="roles-v21", composition_format="complete-v19",
                require_traveler_evidence=True)
            correction = artifact.passes[2]
            assert correction.phase == "correction"
            assert not verify._v23_correction_issues(artifact.passes[1], correction)
            bad_feedback = json.loads(correction.request["input"])
            bad_feedback["feedback"].append({"code": "made_up", "outcome": "failed",
                                             "message": "not an actual check"})
            malformed = correction.model_copy(update={"request": dict(
                correction.request, input=json.dumps(bad_feedback))})
            assert any("differs from actual failed findings" in issue
                       for issue in verify._v23_correction_issues(
                           artifact.passes[1], malformed))
            bad_wire = json.loads(correction.request["input"])
            bad_wire["previous_wire"] = {"blocks": []}
            malformed_wire = correction.model_copy(update={"request": dict(
                correction.request, input=json.dumps(bad_wire))})
            assert any("exact full initial wire" in issue
                       for issue in verify._v23_correction_issues(
                           artifact.passes[1], malformed_wire))
            v23_complete_requests = [item.request for item in artifact.passes[:2]]
        if profile in {"focused-v24", "focused-v25", "focused-v26", "focused-v27"}:
            assert artifact.contract_version == "results-artifact-v11"
            assert artifact.selector_settings.reasoning_effort == (
                "medium" if profile == "focused-v27" and
                not artifact.selector_prepared.packet.get("journey_rows") else
                "low" if profile == "focused-v26" and
                not artifact.selector_prepared.packet.get("journey_rows") else "none")
            assert artifact.composer_settings.reasoning_effort == (
                "medium" if profile == "focused-v27" and
                not artifact.selector_prepared.packet.get("journey_rows") else "low")
            assert artifact.correction_settings.reasoning_effort == "low"
            assert all(item.request == expected for item, expected in
                       zip(artifact.passes[:2], v23_complete_requests, strict=True))
            selector_pass = artifact.passes[0]
            assert not verify._v24_selector_issues(
                selector_pass.request, artifact.selector_prepared,
                incomplete_format=("roles-v25" if profile == "focused-v27" else
                                   "roles-v24" if profile == "focused-v26" else
                                   "roles-v23" if profile == "focused-v25" else "roles-v22"))
            assert not verify._v22_selector_issues(
                selector_pass.request, selector_pass.raw_wire, selector_pass.selection)
            composition_input = json.loads(artifact.passes[1].request["input"])
            assert not verify._pair_packet_issues(
                composition_input["packet"], selection_format="roles-v21",
                composition_format="complete-v19", require_traveler_evidence=True)
            assert not verify._v23_correction_issues(
                artifact.passes[1], artifact.passes[2])
        if profile == "focused-v28":
            assert artifact.contract_version == "results-artifact-v11"
            assert artifact.selector_settings.reasoning_effort == "none"
            assert artifact.composer_settings.reasoning_effort == "medium"
            assert artifact.correction_settings.reasoning_effort == "low"
            assert all(setting.service_tier == "fast" for setting in (
                artifact.selector_settings, artifact.composer_settings,
                artifact.correction_settings))
            selector_pass = artifact.passes[0]
            assert not verify._v28_selector_issues(
                selector_pass.request, selector_pass.raw_wire,
                selector_pass.selection)
            assert not verify._v24_selector_issues(
                selector_pass.request, artifact.selector_prepared,
                complete_format="roles-v26", incomplete_format="roles-v27")
            selector_input = json.loads(selector_pass.request["input"])
            assert not verify._v22_inventory_issues(
                selector_input["packet"], artifact.selector_prepared)
            composition_input = json.loads(artifact.passes[1].request["input"])
            assert not verify._pair_packet_issues(
                composition_input["packet"], selection_format="roles-v26",
                composition_format="complete-v24", require_traveler_evidence=True)
            assert not verify._v23_correction_issues(
                artifact.passes[1], artifact.passes[2])
        if profile in {"focused-v17", "focused-v18", "focused-v19", "focused-v20", "focused-v21", "focused-v22"}:
            assert artifact.revision_settings.reasoning_effort == (
                "medium" if profile in {"focused-v21", "focused-v22"} else
                "low" if profile in {"focused-v18", "focused-v19", "focused-v20"} else "medium")
            assert artifact.revision_trigger == "editorial_revision"
            if profile in {"focused-v19", "focused-v20", "focused-v21", "focused-v22"}:
                patch = artifact.passes[2].patch
                assert patch is not None
                assert all(edit.end - edit.start == 1 and len(edit.blocks) <= 1
                           for edit in patch.edits)
            if profile in {"focused-v20", "focused-v21", "focused-v22"}:
                packet = json.loads(writer.calls[1]["input"])["packet"]
                selection_format, composition_format = {
                    "focused-v20": ("roles-v19", "complete-v17"),
                    "focused-v21": ("roles-v20", "complete-v18"),
                    "focused-v22": ("roles-v21", "complete-v19"),
                }[profile]
                assert not verify._pair_packet_issues(
                    packet, selection_format=selection_format,
                    composition_format=composition_format,
                    require_traveler_evidence=True)
                assert artifact.selector_settings.reasoning_effort == (
                    "none" if profile in {"focused-v21", "focused-v22"} else "low")
                assert artifact.composer_settings.reasoning_effort == "low"
                if profile in {"focused-v21", "focused-v22"}:
                    assert artifact.revision_settings.reasoning_effort == "medium"
                    assert all(settings.service_tier == "fast" for settings in (
                        artifact.selector_settings, artifact.composer_settings,
                        artifact.revision_settings))
                if profile == "focused-v22":
                    selector_pass = artifact.passes[0]
                    assert not verify._v22_selector_issues(
                        selector_pass.request, selector_pass.raw_wire,
                        selector_pass.selection)
                    oversized_schema = deepcopy(selector_pass.request)
                    oversized_schema["text"]["format"]["schema"]["properties"][
                        "choices"]["maxItems"] = 8
                    assert any("does not enforce one through four choices" in issue
                               for issue in verify._v22_selector_issues(
                                   oversized_schema, selector_pass.raw_wire,
                                   selector_pass.selection))
                    five_refs = selector_pass.selection.model_copy(update={
                        "journey_ids": ("J1", "J2", "J3"),
                        "incomplete_observation_ids": ("A1",),
                        "benchmark_observation_id": "C1"})
                    assert any("selected authoring references exceed four" in issue
                               for issue in verify._v22_selector_issues(
                                   selector_pass.request, selector_pass.raw_wire,
                                   five_refs))
                    selection_packet = json.loads(selector_pass.request["input"])["packet"]
                    assert not verify._v22_inventory_issues(
                        selection_packet, artifact.selector_prepared)
                    assert len(selection_packet["journey_records"]) == len(
                        artifact.selector_prepared.packet["journey_rows"])
                    assert selection_packet["lead_rows"] == \
                        artifact.selector_prepared.packet["lead_rows"]
                    trimmed = deepcopy(selection_packet)
                    trimmed["journey_records"].pop(next(iter(trimmed["journey_records"])))
                    assert verify._v22_inventory_issues(
                        trimmed, artifact.selector_prepared)
            if profile == "focused-v20":
                packet = json.loads(writer.calls[1]["input"])["packet"]
                broken = deepcopy(packet)
                journey_ref = next(ref for ref, row in broken["authoring_records"].items()
                                   if row["role"] == "journey")
                del broken["authoring_records"][journey_ref]["traveler_evidence"]
                assert any("lacks required traveler_evidence" in issue
                           for issue in verify._pair_packet_issues(
                               broken, selection_format="roles-v19",
                               composition_format="complete-v17",
                               require_traveler_evidence=True))
                malformed = deepcopy(packet)
                malformed["authoring_records"][journey_ref]["traveler_evidence"][
                    "award_reported_seats"] = None
                assert any("traveler_evidence values are malformed" in issue
                           for issue in verify._pair_packet_issues(
                               malformed, selection_format="roles-v19",
                               composition_format="complete-v17",
                               require_traveler_evidence=True))
        else:
            assert artifact.correction_settings.reasoning_effort == "low"
        assert artifact.resolved is not None and artifact.selected_pass_index == 2
        assert artifact.comparison_registry is not None
        assert replay_focused_results(artifact) == artifact.resolved
    from test_results_focused_v21 import _source as archived_v21_source

    incomplete_source, incomplete_config, _ = archived_v21_source("scout-v19-incomplete")
    incomplete_writer = DiagnosticWriter("low", "none", "low", profile="focused-v24")
    incomplete = run_focused_results(incomplete_source, config, incomplete_writer,
                                     FakeMeasurer(), profile="focused-v24")
    assert len(incomplete_writer.calls) == len(incomplete.passes) == 3, (
        len(incomplete_writer.calls), [(item.phase, item.outcome, item.failure_subtype,
        item.raw_wire,
        [(finding.code, finding.outcome) for finding in item.findings])
        for item in incomplete.passes])
    assert incomplete.selector_prepared.packet["selection_format"] == "roles-v22"
    assert incomplete.focus_prepared.packet["composition_format"] == "complete-v20"
    assert any(finding.code == "empty_explanation" and finding.outcome == "failed"
               for finding in incomplete.passes[1].findings)
    incomplete_selector_input = json.loads(incomplete.passes[0].request["input"])
    incomplete_selector_packet = incomplete_selector_input["packet"]
    assert not verify._v24_selector_issues(incomplete.passes[0].request,
                                           incomplete.selector_prepared)
    assert incomplete_selector_packet["lead_records"]
    assert "lead_rows" not in incomplete_selector_packet
    incomplete_composition_packet = json.loads(incomplete.passes[1].request["input"])["packet"]
    assert not verify._pair_packet_issues(
        incomplete_composition_packet, selection_format="roles-v22",
        composition_format="complete-v20", require_traveler_evidence=True)
    assert not verify._v23_correction_issues(incomplete.passes[1], incomplete.passes[2])
    assert incomplete.delivery_outcome == "delivered"
    assert replay_focused_results(incomplete) == incomplete.resolved
    incomplete_v25_writer = DiagnosticWriter("medium", "none", "low",
                                              profile="focused-v25")
    incomplete_v25 = run_focused_results(
        incomplete_source, config, incomplete_v25_writer, FakeMeasurer(),
        profile="focused-v25")
    assert len(incomplete_v25_writer.calls) == len(incomplete_v25.passes) == 3
    assert incomplete_v25.selector_prepared.packet["selection_format"] == "roles-v23"
    assert incomplete_v25.focus_prepared.packet["composition_format"] == "complete-v21"
    assert incomplete_v25.selector_settings.reasoning_effort == "none"
    assert incomplete_v25.composer_settings.reasoning_effort == "medium"
    assert incomplete_v25.correction_settings.reasoning_effort == "low"
    assert any(finding.code == "empty_explanation" and finding.outcome == "failed"
               for finding in incomplete_v25.passes[1].findings)
    assert not verify._v24_selector_issues(
        incomplete_v25.passes[0].request, incomplete_v25.selector_prepared,
        incomplete_format="roles-v23")
    incomplete_v25_packet = json.loads(
        incomplete_v25.passes[1].request["input"])["packet"]
    assert not verify._pair_packet_issues(
        incomplete_v25_packet, selection_format="roles-v23",
        composition_format="complete-v21", require_traveler_evidence=True)
    assert not verify._v23_correction_issues(incomplete_v25.passes[1],
                                              incomplete_v25.passes[2])
    assert incomplete_v25.delivery_outcome == "delivered"
    assert replay_focused_results(incomplete_v25) == incomplete_v25.resolved
    incomplete_v26_writer = DiagnosticWriter("medium", "low", "low",
                                              profile="focused-v26")
    incomplete_v26 = run_focused_results(
        incomplete_source, config, incomplete_v26_writer, FakeMeasurer(),
        profile="focused-v26")
    assert len(incomplete_v26_writer.calls) == len(incomplete_v26.passes) == 3
    assert incomplete_v26.selector_prepared.packet["selection_format"] == "roles-v24"
    assert incomplete_v26.focus_prepared.packet["composition_format"] == "complete-v22"
    assert incomplete_v26.selector_settings.reasoning_effort == "low"
    assert incomplete_v26.composer_settings.reasoning_effort == "medium"
    assert incomplete_v26.correction_settings.reasoning_effort == "low"
    assert any(finding.code == "empty_explanation" and finding.outcome == "failed"
               for finding in incomplete_v26.passes[1].findings)
    assert not verify._v24_selector_issues(
        incomplete_v26.passes[0].request, incomplete_v26.selector_prepared,
        incomplete_format="roles-v24")
    incomplete_v26_packet = json.loads(
        incomplete_v26.passes[1].request["input"])["packet"]
    assert not verify._pair_packet_issues(
        incomplete_v26_packet, selection_format="roles-v24",
        composition_format="complete-v22", require_traveler_evidence=True)
    assert not verify._v23_correction_issues(incomplete_v26.passes[1],
                                              incomplete_v26.passes[2])
    assert replay_focused_results(incomplete_v26) == incomplete_v26.resolved
    incomplete_v27_writer = DiagnosticWriter("medium", "medium", "low",
                                              profile="focused-v27")
    incomplete_v27 = run_focused_results(
        incomplete_source, config, incomplete_v27_writer, FakeMeasurer(),
        profile="focused-v27")
    assert len(incomplete_v27_writer.calls) == len(incomplete_v27.passes) == 3
    assert incomplete_v27.selector_prepared.packet["selection_format"] == "roles-v25"
    assert incomplete_v27.focus_prepared.packet["composition_format"] == "complete-v23"
    assert incomplete_v27.selector_settings.reasoning_effort == "medium"
    assert incomplete_v27.composer_settings.reasoning_effort == "medium"
    assert incomplete_v27.correction_settings.reasoning_effort == "low"
    assert any(finding.code == "empty_explanation" and finding.outcome == "failed"
               for finding in incomplete_v27.passes[1].findings)
    assert not verify._v24_selector_issues(
        incomplete_v27.passes[0].request, incomplete_v27.selector_prepared,
        incomplete_format="roles-v25")
    incomplete_v27_packet = json.loads(
        incomplete_v27.passes[1].request["input"])["packet"]
    assert not verify._pair_packet_issues(
        incomplete_v27_packet, selection_format="roles-v25",
        composition_format="complete-v23", require_traveler_evidence=True)
    assert not verify._v23_correction_issues(incomplete_v27.passes[1],
                                              incomplete_v27.passes[2])
    assert replay_focused_results(incomplete_v27) == incomplete_v27.resolved
    incomplete_v28_writer = DiagnosticWriter("low", "medium", "low",
                                              profile="focused-v28")
    incomplete_v28 = run_focused_results(
        incomplete_source, config, incomplete_v28_writer, FakeMeasurer(),
        profile="focused-v28")
    assert len(incomplete_v28_writer.calls) == len(incomplete_v28.passes) == 3
    assert incomplete_v28.selector_prepared.packet["selection_format"] == "roles-v27"
    assert incomplete_v28.focus_prepared.packet["composition_format"] == "complete-v25"
    assert incomplete_v28.selector_settings.reasoning_effort == "medium"
    assert incomplete_v28.composer_settings.reasoning_effort == "low"
    assert incomplete_v28.correction_settings.reasoning_effort == "low"
    assert all(setting.service_tier == "fast" for setting in (
        incomplete_v28.selector_settings, incomplete_v28.composer_settings,
        incomplete_v28.correction_settings))
    assert any(finding.code == "empty_explanation" and finding.outcome == "failed"
               for finding in incomplete_v28.passes[1].findings)
    assert not verify._v28_selector_issues(
        incomplete_v28.passes[0].request, incomplete_v28.passes[0].raw_wire,
        incomplete_v28.passes[0].selection)
    assert not verify._v24_selector_issues(
        incomplete_v28.passes[0].request, incomplete_v28.selector_prepared,
        complete_format="roles-v26", incomplete_format="roles-v27")
    incomplete_v28_composer = json.loads(
        incomplete_v28.passes[1].request["input"])["packet"]
    assert not verify._pair_packet_issues(
        incomplete_v28_composer, selection_format="roles-v27",
        composition_format="complete-v25", require_traveler_evidence=True)
    assert not verify._v23_correction_issues(
        incomplete_v28.passes[1], incomplete_v28.passes[2])
    assert replay_focused_results(incomplete_v28) == incomplete_v28.resolved
    clean_writer = DiagnosticWriter("low", "none", "low", profile="focused-v23",
                                     inject_alias_fault=False)
    clean = run_focused_results(_source(), config, clean_writer, FakeMeasurer(),
                                profile="focused-v23")
    assert len(clean_writer.calls) == len(clean.passes) == 2
    assert [item.phase for item in clean.passes] == ["selection", "composition"]
    assert not any(finding.outcome == "failed" for finding in clean.passes[1].findings)
    assert clean.delivery_outcome == "delivered"
    assert replay_focused_results(clean) == clean.resolved
    overflow_writer = DiagnosticWriter("low", "none", "medium", overflow_choices=True,
                                       profile="focused-v22")
    overflow = run_focused_results(_source(), config, overflow_writer, FakeMeasurer(),
                                   profile="focused-v22")
    assert len(overflow_writer.calls) == len(overflow.passes) == 1
    assert overflow.passes[0].outcome == "generation_error"
    assert overflow.passes[0].failure_subtype == "schema_error"
    assert overflow.delivery_outcome == "not_delivered"
    assert len(json.loads(overflow_writer.calls[0]["input"])["packet"][
        "journey_records"]) > 4
    print("V11-V28 diagnostic guidance, named-lead projection, phase settings and replay passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
