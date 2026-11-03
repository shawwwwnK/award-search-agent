"""Offline mutation controls for the campaign verifier."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ledger
import verify


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fixture(root: Path) -> Path:
    from run import _preview, snapshot_paths

    from award_agent.providers.contracts import content_digest
    from award_agent.results.focused import parse_focused_artifact

    source = (verify.HERE.parent / "2026-10-26-under20/runs/"
              "confirm-f3-1-admitted/artifact.json")
    artifact = parse_focused_artifact(source.read_bytes())
    run = root / "runs" / "fixture"
    run.mkdir(parents=True)
    shutil.copyfile(source, run / "artifact.json")
    assert artifact.resolved is not None
    _write(run / "resolved.json", artifact.resolved.model_dump(mode="json"))
    (run / "answer-preview.md").write_text(_preview(artifact.resolved), encoding="utf-8")
    paths = snapshot_paths("admitted")
    default_key = "data/results/fast-default.json"
    historical_default = artifact.config.model_dump_json().encode("utf-8")
    hashes = {str(path.relative_to(verify.HERE.parents[4])):
              hashlib.sha256(historical_default).hexdigest()
              if str(path.relative_to(verify.HERE.parents[4])) == default_key
              else ledger.sha256(path) for path in paths}
    _write(run / "source-snapshot.json", hashes)
    with zipfile.ZipFile(run / "source-snapshot.zip", "x") as archive:
        for path in paths:
            member = str(path.relative_to(verify.HERE.parents[4]))
            if member == default_key:
                archive.writestr(member, historical_default)
            else:
                archive.write(path, member)
    source_path = verify.HERE.parent / "2026-10-25-cost-experiments/"
    source_path /= "luna-retest/round-1/admitted/artifact.json"
    _write(run / "settings.json", {
        "case": "admitted", "profile": "focused-v3",
        "model": "gpt-6-luna", "max_retries": 0,
        "source_sha256": ledger.sha256(source_path),
        "config_sha256": ledger.sha256(source_path.parent / "config.json"),
        "campaign_sha256": ledger.sha256(ledger.CAMPAIGN),
        "max_output_tokens": artifact.config.max_output_tokens,
        "timeout_seconds": artifact.config.timeout_seconds,
        "manifest_sha256": None})
    selected = artifact.passes[-1]
    _write(run / "summary.json", {
        "case": "admitted", "profile": "focused-v3", "count_calls": 2,
        "generation_calls": 2, "outer_results_completion_seconds": 8.0,
        "generation_outcome": artifact.generation_outcome,
        "validation_outcome": artifact.validation_outcome,
        "delivery_outcome": artifact.delivery_outcome,
        "selected_pass_index": 1,
        "failed_findings": [finding.model_dump(mode="json") for finding in selected.findings
                            if finding.outcome == "failed"],
        "passes": [{"phase": item.phase, "outcome": item.outcome,
                    "returned_service_tier": item.returned_service_tier,
                    "usage": json.loads(item.writer_receipt.raw_response).get("usage")}
                   for item in artifact.passes]})
    for index, item in enumerate(artifact.passes, 1):
        folder = run / f"pass-{index:02d}"
        count_request = item.request
        generation_request = dict(item.request, max_output_tokens=artifact.config.max_output_tokens,
                                  store=False, truncation="disabled", stream=True,
                                  service_tier="fast")
        _write(folder / "count-request.json", count_request)
        _write(folder / "count-receipt.json",
               item.input_token_receipt.model_dump(mode="json"))
        _write(folder / "generation-request.json", generation_request)
        _write(folder / "writer-receipt.json", item.writer_receipt.model_dump(mode="json"))
        _write(folder / "raw-response.json", json.loads(item.writer_receipt.raw_response))
        for kind, request in (("count", count_request),
                              ("generation", generation_request)):
            _write(root / "calls" / f"{kind}-{index:03d}.json", {
                "run_name": "fixture", "label": f"pass-{index:02d}",
                "request_digest": content_digest(request)})
    return run


def _v19_pair_packet_controls() -> None:
    artifact = ledger.read_json(verify.RUNS / "scout-v19-admitted" / "artifact.json")
    composition = next(row for row in artifact["passes"] if row["phase"] == "composition")
    payload = json.loads(composition["request"]["input"])
    packet = payload["packet"]
    assert not verify._pair_packet_issues(
        packet, selection_format="roles-v18", composition_format="complete-v16")

    missing = deepcopy(packet)
    del missing["comparison_pairs"]
    assert any("comparison_pairs is missing" in issue
               for issue in verify._pair_packet_issues(
                   missing, selection_format="roles-v18", composition_format="complete-v16"))

    malformed = deepcopy(packet)
    malformed["comparison_pairs"][0] = {
        "left_ref": "left", "right_ref": "right", "left": {}, "right": {},
        "card_ids": []}
    assert any("lacks required pair fields" in issue
               for issue in verify._pair_packet_issues(
                   malformed, selection_format="roles-v18", composition_format="complete-v16"))


def _v20_incomplete_packet_control() -> None:
    artifact = ledger.read_json(verify.RUNS / "scout-v20-incomplete" / "artifact.json")
    composition = next(row for row in artifact["passes"] if row["phase"] == "composition")
    packet = json.loads(composition["request"]["input"])["packet"]
    pairs = packet["comparison_pairs"]
    assert len(pairs) == 3
    assert all(pair["left"]["role"] == pair["right"]["role"] == "lead"
               for pair in pairs)
    assert not verify._pair_packet_issues(
        packet, selection_format="roles-v19", composition_format="complete-v17",
        require_traveler_evidence=True)

    malformed = deepcopy(packet)
    malformed["comparison_pairs"][0]["left"]["role"] = "journey"
    assert any("source records or relations are malformed" in issue
               for issue in verify._pair_packet_issues(
                   malformed, selection_format="roles-v19",
                   composition_format="complete-v17",
                   require_traveler_evidence=True))


def _v24_canonical_lead_projection_controls() -> None:
    from award_agent.ranking.projection_contracts import SolutionProjection
    from award_agent.results.focused import parse_focused_artifact, prepare_focused_selector
    from award_agent.results.focused_selector_records import selector_packet

    old = parse_focused_artifact(
        (verify.RUNS / "confirm-v23-default-1-incomplete" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    prepared = prepare_focused_selector(source, old.config, selection_format="roles-v22")
    packet = selector_packet(prepared)
    request = {"input": json.dumps({"packet": packet})}
    assert not verify._v24_selector_issues(request, prepared)
    prepared_v25 = prepare_focused_selector(source, old.config, selection_format="roles-v23")
    packet_v25 = selector_packet(prepared_v25)
    request_v25 = {"input": json.dumps({"packet": packet_v25})}
    assert not verify._v24_selector_issues(
        request_v25, prepared_v25, incomplete_format="roles-v23")
    assert packet_v25["lead_records"] == packet["lead_records"]
    assert packet_v25["exact_details"] == packet["exact_details"]
    prepared_v26 = prepare_focused_selector(source, old.config, selection_format="roles-v24")
    packet_v26 = selector_packet(prepared_v26)
    request_v26 = {"input": json.dumps({"packet": packet_v26})}
    assert not verify._v24_selector_issues(
        request_v26, prepared_v26, incomplete_format="roles-v24")
    normalized_v25 = deepcopy(packet_v25)
    normalized_v26 = deepcopy(packet_v26)
    normalized_v25["selection_format"] = "roles-v24"
    assert normalized_v26 == normalized_v25
    prepared_v27 = prepare_focused_selector(source, old.config, selection_format="roles-v25")
    packet_v27 = selector_packet(prepared_v27)
    request_v27 = {"input": json.dumps({"packet": packet_v27})}
    assert not verify._v24_selector_issues(
        request_v27, prepared_v27, incomplete_format="roles-v25")
    normalized_v26["selection_format"] = "roles-v25"
    assert packet_v27 == normalized_v26
    assert prepared.packet["journey_rows"] == []
    assert len(packet["lead_records"]) == 378

    missing_quote = deepcopy(packet)
    del missing_quote["lead_records"][0]["original_quote"]
    assert any("ordered lead records or original quotes differ" in issue
               for issue in verify._v24_selector_issues(
                   {"input": json.dumps({"packet": missing_quote})}, prepared))

    reordered = deepcopy(packet)
    reordered["lead_records"][0], reordered["lead_records"][1] = (
        reordered["lead_records"][1], reordered["lead_records"][0])
    assert any("ordered lead records or original quotes differ" in issue
               for issue in verify._v24_selector_issues(
                   {"input": json.dumps({"packet": reordered})}, prepared))

    positional = deepcopy(packet)
    positional["lead_rows"] = prepared.packet["lead_rows"]
    assert any("retains positional lead rows" in issue
               for issue in verify._v24_selector_issues(
                   {"input": json.dumps({"packet": positional})}, prepared))

    complete = parse_focused_artifact(
        (verify.RUNS / "confirm-v23-default-1-admitted" / "artifact.json").read_bytes())
    complete_request = complete.passes[0].request
    assert not verify._v24_selector_issues(complete_request, complete.selector_prepared)


def _scout_evidence_digest_compatibility() -> None:
    manifest = ledger.read_json(verify.HERE / "confirmation-v23-default.json")
    metadata = manifest["scout_source_evidence"]
    assert "canonical_sha256" not in metadata  # frozen V23 uses the original raw-byte meaning
    evidence_bytes = (verify.HERE / metadata["path_name"]).read_bytes()
    assert hashlib.sha256(evidence_bytes).hexdigest() == metadata["sha256"]
    assert not verify._scout_source_evidence_issues(metadata, verify.HERE)

    document = {"proof": [{"run": "source-scout", "pass_index": 1}],
                "purpose": "prospective source evidence only"}
    pretty = json.dumps(document, indent=2).encode("utf-8")
    compact = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_digest = hashlib.sha256(compact).hexdigest()
    assert hashlib.sha256(pretty).hexdigest() != hashlib.sha256(compact).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, data in (("pretty.json", pretty), ("compact.json", compact)):
            (root / name).write_bytes(data)
            entry = {"path_name": name, "sha256": hashlib.sha256(data).hexdigest(),
                     "document": document, "use": "prospective source evidence only"}
            assert not verify._scout_source_evidence_issues(entry, root)
            entry["canonical_sha256"] = canonical_digest
            assert not verify._scout_source_evidence_issues(entry, root)
            entry["canonical_sha256"] = "tampered"
            assert any("canonical-document digest differs" in issue
                       for issue in verify._scout_source_evidence_issues(entry, root))


def _v28_selection_ceilings() -> None:
    request = {"text": {"format": {"schema": {"properties": {
        "choices": {"maxItems": 3}}}}}}
    selected = SimpleNamespace(journey_ids=("j1", "j2"),
                               incomplete_observation_ids=(),
                               benchmark_observation_id="b1")
    raw = json.dumps({"choices": [{"k": "j"}, {"k": "l"}, {"k": "b"}]})
    assert not verify._v28_selector_issues(request, raw, selected)
    empty_selection = SimpleNamespace(journey_ids=(), incomplete_observation_ids=(),
                                      benchmark_observation_id=None)
    assert not verify._v28_selector_issues(
        request, json.dumps({"choices": []}), empty_selection)
    complete_source = SimpleNamespace(packet={"journey_rows": [{}], "lead_rows": []})
    assert any("omitted an available journey" in issue for issue in
               verify._v28_source_selection_issues(
                   complete_source, empty_selection, "delivered"))
    assert not verify._v28_source_selection_issues(
        complete_source, empty_selection, "not_delivered")
    incomplete_source = SimpleNamespace(packet={"journey_rows": [], "lead_rows": [{}]})
    assert any("omitted an available lead" in issue for issue in
               verify._v28_source_selection_issues(
                   incomplete_source, empty_selection, "delivered"))

    bad_schema = deepcopy(request)
    bad_schema["text"]["format"]["schema"]["properties"]["choices"]["maxItems"] = 4
    assert any("schema does not enforce" in issue
               for issue in verify._v28_selector_issues(bad_schema, raw, selected))
    three_nonbenchmark = json.dumps({"choices": [{"k": "j"}, {"k": "l"}, {"k": "j"}]})
    assert any("two nonbenchmark or one benchmark" in issue
               for issue in verify._v28_selector_issues(request, three_nonbenchmark, None))
    two_benchmarks = json.dumps({"choices": [{"k": "j"}, {"k": "b"}, {"k": "b"}]})
    assert any("two nonbenchmark or one benchmark" in issue
               for issue in verify._v28_selector_issues(request, two_benchmarks, None))
    overdecoded = SimpleNamespace(journey_ids=("j1", "j2", "j3"),
                                  incomplete_observation_ids=(),
                                  benchmark_observation_id="b1")
    decoded_issues = verify._v28_selector_issues(request, raw, overdecoded)
    assert any("exceeds three total" in issue for issue in decoded_issues)
    assert any("two plus one" in issue for issue in decoded_issues)


def _grouped_lead_inverse_controls() -> None:
    from award_agent.ranking.projection_contracts import SolutionProjection
    from award_agent.results.focused import parse_focused_artifact, prepare_focused_selector
    from award_agent.results.focused_selector_records import selector_packet

    old = parse_focused_artifact(
        (verify.RUNS / "confirm-v23-default-1-incomplete" / "artifact.json").read_bytes())
    source = SolutionProjection.model_validate(old.evidence.source.model_dump(mode="json"))
    prepared = prepare_focused_selector(source, old.config, selection_format="roles-v29")
    packet = selector_packet(prepared)
    request = {"input": json.dumps({"packet": packet})}
    assert not verify._grouped_lead_selector_issues(
        request, prepared, selection_format="roles-v29")
    assert "lead_records" not in packet and "lead_rows" not in packet

    groups = packet["lead_program_groups"]
    ordinals = [member["source_ordinal"] for group in groups
                for member in group["members"]]
    assert sorted(ordinals) == list(range(len(prepared.packet["lead_rows"])))

    reordered_groups = deepcopy(packet)
    reordered_groups["lead_program_groups"].reverse()
    assert any("first-encounter source grouping" in issue
               for issue in verify._grouped_lead_selector_issues(
                   {"input": json.dumps({"packet": reordered_groups})}, prepared,
                   selection_format="roles-v29"))

    reordered_members = deepcopy(packet)
    first_group = reordered_members["lead_program_groups"][0]
    if len(first_group["members"]) > 1:
        first_group["members"].reverse()
        assert any("first-encounter source grouping" in issue
                   for issue in verify._grouped_lead_selector_issues(
                       {"input": json.dumps({"packet": reordered_members})}, prepared,
                       selection_format="roles-v29"))

    duplicate_ordinal = deepcopy(packet)
    if len(duplicate_ordinal["lead_program_groups"]) > 1:
        duplicate_ordinal["lead_program_groups"][1]["members"][0][
            "source_ordinal"] = duplicate_ordinal["lead_program_groups"][0][
                "members"][0]["source_ordinal"]
    else:
        duplicate_ordinal["lead_program_groups"][0]["members"][0][
            "source_ordinal"] = len(prepared.packet["lead_rows"])
    assert any("source ordinals are missing" in issue
               for issue in verify._grouped_lead_selector_issues(
                   {"input": json.dumps({"packet": duplicate_ordinal})}, prepared,
                   selection_format="roles-v29"))

    altered_record = deepcopy(packet)
    altered_record["lead_program_groups"][0]["members"][0]["record"][
        "original_quote"] = {"state": "altered"}
    assert any("invert to exact source rows and quotes" in issue
               for issue in verify._grouped_lead_selector_issues(
                   {"input": json.dumps({"packet": altered_record})}, prepared,
                   selection_format="roles-v29"))

    prepared_v30 = prepare_focused_selector(source, old.config, selection_format="roles-v30")
    packet_v30 = selector_packet(prepared_v30)
    request_v30 = {"input": json.dumps({"packet": packet_v30})}
    assert not verify._grouped_lead_selector_issues(
        request_v30, prepared_v30, selection_format="roles-v30")
    normalized_v29 = deepcopy(packet)
    normalized_v29["selection_format"] = "roles-v30"
    assert packet_v30 == normalized_v29


def _v30_guidance_scope_controls() -> None:
    v29_guidance = (
        "Do not compare points across programs as economic value, or prices across "
        "currencies or unknown scopes as total savings. Inspect the full source groups "
        "for a real date, cabin, or same-program quote contrast. In this incomplete-only "
        "selector view, lead_program_groups replaces lead_rows. The groups preserve "
        "every original lead, not a ranking.")
    clarification = (
        "Each rewards program has its own points unit. A smaller number in another "
        "program is not a supported advantage, even when called stated, nominal, "
        "or potential, and cannot supply the upside of a points-versus-fees "
        "tradeoff. Original program quotes remain reportable separately. Before "
        "retaining a comparator, remove cross-program numerical magnitude from the "
        "rationale and identify the source-supported benefit for which a traveler "
        "might accept its downside. An unspecified program preference alone does "
        "not establish that benefit. If no benefit remains, examine other leads in "
        "the full inventory. A supported conditional choice can suffice; no "
        "program, date, cabin, or count quota applies. Do not compare prices across "
        "currencies or unknown scopes as total savings.")
    assert not verify._v30_selector_guidance_issues(
        {"instructions": v29_guidance}, incomplete=False)
    assert not verify._v30_selector_guidance_issues(
        {"instructions": v29_guidance.replace(
            "Do not compare points across programs as economic value, or prices across "
            "currencies or unknown scopes as total savings.", clarification)},
        incomplete=True)
    missing_no_quota = v29_guidance.replace(
        "Do not compare points across programs as economic value, or prices across "
        "currencies or unknown scopes as total savings.", clarification).replace(
            "no program, date, cabin, or count quota applies", "")
    assert any("exact cross-program clarification" in issue for issue in
               verify._v30_selector_guidance_issues(
                   {"instructions": missing_no_quota}, incomplete=True))
    assert any("differs from the V29" in issue for issue in
               verify._v30_selector_guidance_issues(
                   {"instructions": v29_guidance + " " + clarification}, incomplete=False))


def main() -> int:
    original_runs, original_calls = verify.RUNS, ledger.CALLS
    try:
        _v19_pair_packet_controls()
        _v20_incomplete_packet_control()
        _v24_canonical_lead_projection_controls()
        _scout_evidence_digest_compatibility()
        _v28_selection_ceilings()
        _grouped_lead_inverse_controls()
        _v30_guidance_scope_controls()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            verify.RUNS, ledger.CALLS = root / "runs", root / "calls"
            run = _fixture(root)
            baseline = verify.report()["integrity_issues"]
            assert not baseline, baseline
            settings_path = run / "settings.json"
            settings = ledger.read_json(settings_path)
            settings["effective_config_source"] = "data/results/fast-default.json"
            settings["default_config_sha256"] = "invalid"
            _write(settings_path, settings)
            assert any("proposed default config hash differs" in issue
                       for issue in verify.report()["integrity_issues"])
            settings.pop("effective_config_source")
            settings.pop("default_config_sha256")
            _write(settings_path, settings)
            request_path = run / "pass-01/generation-request.json"
            request = ledger.read_json(request_path)
            request["instructions"] += " tampered"
            _write(request_path, request)
            # Rebind ledger digest too: a self-consistent archive still must fail
            # when it disagrees with the replayed Results artifact.
            from award_agent.providers.contracts import content_digest
            call_path = ledger.CALLS / "generation-001.json"
            call = ledger.read_json(call_path)
            call["request_digest"] = content_digest(request)
            _write(call_path, call)
            assert any("generation request differs from artifact" in issue
                       for issue in verify.report()["integrity_issues"])
            _write(request_path, dict(request, instructions=request["instructions"][:-9]))
            call["request_digest"] = content_digest(ledger.read_json(request_path))
            _write(call_path, call)
            summary_path = run / "summary.json"
            summary = ledger.read_json(summary_path)
            summary["delivery_outcome"] = "not_delivered"
            _write(summary_path, summary)
            assert any("summary outcome differs from artifact" in issue
                       for issue in verify.report()["integrity_issues"])
    finally:
        verify.RUNS, ledger.CALLS = original_runs, original_calls
    print("verifier baseline and mutation controls passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
