"""Check local call bounds, immutable request receipts, snapshots and exact replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import ledger

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def _check_archive(run: Path, issues: list[str]) -> dict[str, bytes]:
    paths = ledger.read_json(run / "source-snapshot.json")
    archived: dict[str, bytes] = {}
    with zipfile.ZipFile(run / "source-snapshot.zip") as archive:
        if set(archive.namelist()) != set(paths):
            issues.append(f"{run.name}: snapshot archive members differ")
        for member, digest in paths.items():
            try:
                archived[member] = archive.read(member)
                observed = hashlib.sha256(archived[member]).hexdigest()
            except KeyError:
                observed = None
            if observed != digest:
                issues.append(f"{run.name}: snapshot digest differs: {member}")
    return archived


def _matches(run: Path, label: str, actual: object, expected: object,
             issues: list[str]) -> None:
    if actual != expected:
        issues.append(f"{run.name}: {label} differs from artifact")


def _pair_packet_issues(packet: object, *, selection_format: str,
                        composition_format: str,
                        require_traveler_evidence: bool = False) -> list[str]:
    """Check the actual writer packet, not its replay-oriented prepared packet."""
    if not isinstance(packet, dict):
        return ["packet is not an object"]
    issues: list[str] = []
    if packet.get("format") != "focused-authoring-records-v3":
        issues.append("packet format differs")
    if (packet.get("selection_format"), packet.get("composition_format")) != (
            selection_format, composition_format):
        issues.append("packet profile markers differ")
    if "selected_comparisons" in packet or "temporal_comparisons" in packet:
        issues.append("legacy flat comparison fields are present")
    if require_traveler_evidence:
        records = packet.get("authoring_records")
        if not isinstance(records, dict) or not records:
            issues.append("authoring_records is missing or malformed")
        else:
            evidence_fields = {
                "requested_travelers", "award_component_ref",
                "award_support_for_requested_party", "award_minimum_seats_check",
                "award_reported_seats", "award_returned_travelers",
                "cash_component_ref", "cash_returned_travelers", "meaning",
            }

            def count_valid(value: object) -> bool:
                return (isinstance(value, dict) and
                        {"state", "value", "source_field"} <= set(value) and
                        isinstance(value["state"], str) and bool(value["state"]) and
                        (value["source_field"] is None or
                         isinstance(value["source_field"], str)))

            for ref, record in records.items():
                if not isinstance(record, dict):
                    issues.append(f"authoring_records[{ref}] is malformed")
                    continue
                traveler_evidence = record.get("traveler_evidence")
                if record.get("role") == "journey":
                    if not isinstance(traveler_evidence, dict) or \
                            not evidence_fields <= set(traveler_evidence):
                        issues.append(f"authoring_records[{ref}] lacks required traveler_evidence")
                        continue
                    if (not isinstance(traveler_evidence["requested_travelers"], int) or
                            isinstance(traveler_evidence["requested_travelers"], bool) or
                            traveler_evidence["requested_travelers"] < 1 or
                            not isinstance(traveler_evidence["award_component_ref"], str) or
                            not traveler_evidence["award_component_ref"] or
                            not isinstance(traveler_evidence[
                                "award_support_for_requested_party"], str) or
                            traveler_evidence["award_support_for_requested_party"] not in
                            {"passed", "failed", "unknown"} or
                            not isinstance(traveler_evidence[
                                "award_minimum_seats_check"], str) or
                            traveler_evidence["award_minimum_seats_check"] not in
                            {"passed", "failed", "unknown"} or
                            not count_valid(traveler_evidence["award_reported_seats"]) or
                            not count_valid(traveler_evidence["award_returned_travelers"]) or
                            not isinstance(traveler_evidence["meaning"], str) or
                            not traveler_evidence["meaning"]):
                        issues.append(f"authoring_records[{ref}] traveler_evidence values are malformed")
                    cash_ref = traveler_evidence["cash_component_ref"]
                    cash_count = traveler_evidence["cash_returned_travelers"]
                    if ((cash_ref is not None and
                         (not isinstance(cash_ref, str) or not cash_ref or
                          not count_valid(cash_count))) or
                            (cash_ref is None and cash_count is not None)):
                        issues.append(f"authoring_records[{ref}] cash traveler_evidence is malformed")
                elif traveler_evidence is not None:
                    issues.append(f"authoring_records[{ref}] has traveler_evidence outside a journey")
    pairs = packet.get("comparison_pairs")
    if not isinstance(pairs, list) or not pairs:
        issues.append("comparison_pairs is missing, empty, or not a list")
        return issues
    seen_pairs: set[tuple[str, str]] = set()
    allowed_metrics = {"departure", "arrival", "elapsed"}
    required_pair_fields = {"left_ref", "right_ref", "left", "right", "relations", "card_ids"}
    for index, row in enumerate(pairs):
        if not isinstance(row, dict) or not required_pair_fields <= set(row):
            issues.append(f"comparison_pairs[{index}] lacks required pair fields")
            continue
        left_ref, right_ref = row["left_ref"], row["right_ref"]
        if (not isinstance(left_ref, str) or not left_ref or
                not isinstance(right_ref, str) or not right_ref or left_ref == right_ref):
            issues.append(f"comparison_pairs[{index}] has invalid endpoint references")
            continue
        pair_key = tuple(sorted((left_ref, right_ref)))
        if pair_key in seen_pairs:
            issues.append(f"comparison_pairs[{index}] duplicates an earlier pair")
        seen_pairs.add(pair_key)
        left, right, relations = row["left"], row["right"], row["relations"]
        left_role = left.get("role") if isinstance(left, dict) else None
        right_role = right.get("role") if isinstance(right, dict) else None
        if (not isinstance(left, dict) or not isinstance(right, dict) or
                left.get("ref") != left_ref or right.get("ref") != right_ref or
                not isinstance(left_role, str) or left_role not in {"journey", "lead"} or
                right_role != left_role or
                not isinstance(relations, dict) or not relations):
            issues.append(f"comparison_pairs[{index}] source records or relations are malformed")
        cards = row["card_ids"]
        if not isinstance(cards, list):
            issues.append(f"comparison_pairs[{index}].card_ids is not a list")
            continue
        for card_index, card in enumerate(cards):
            if not isinstance(card, dict) or not {"id", "metric", "first_ref", "second_ref"} <= set(card):
                issues.append(f"comparison_pairs[{index}].card_ids[{card_index}] is malformed")
                continue
            if (not isinstance(card["id"], str) or not card["id"] or
                    not isinstance(card["first_ref"], str) or
                    not isinstance(card["second_ref"], str) or
                    not isinstance(card["metric"], str) or
                    card["metric"] not in allowed_metrics or
                    {card["first_ref"], card["second_ref"]} != {left_ref, right_ref}):
                issues.append(f"comparison_pairs[{index}].card_ids[{card_index}] differs from its pair")
    return issues


def _v22_selector_issues(request: object, raw_wire: object,
                         selection: object) -> list[str]:
    """Verify the four-reference bound in the actual selector request and result."""
    issues: list[str] = []
    if not isinstance(request, dict):
        return ["selector request is malformed"]
    try:
        schema = request["text"]["format"]["schema"]
        choices_schema = schema["properties"]["choices"]
    except (KeyError, TypeError):
        return ["selector choices schema is missing"]
    if (not isinstance(choices_schema, dict) or
            choices_schema.get("maxItems") != 4 or choices_schema.get("minItems") != 1):
        issues.append("selector choices schema does not enforce one through four choices")
    try:
        raw = json.loads(raw_wire) if isinstance(raw_wire, str) else raw_wire
    except (ValueError, TypeError):
        raw = None
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not isinstance(choices, list) or len(choices) > 4:
        issues.append("selector response does not contain one through four choices")
    if selection is not None:
        ref_count = (len(selection.journey_ids) + len(selection.incomplete_observation_ids) +
                     int(selection.benchmark_observation_id is not None))
        if ref_count > 4:
            issues.append("selected authoring references exceed four")
    return issues


def _v22_inventory_issues(packet: object, prepared: Any) -> list[str]:
    """Ensure the four-choice ceiling did not trim the selector/explorer inventory."""
    if not isinstance(packet, dict):
        return ["selector inventory packet is malformed"]
    from award_agent.results.focused_selector_records import selector_packet

    try:
        expected = selector_packet(prepared)
    except (KeyError, TypeError, ValueError):
        return ["prepared full inventory could not be projected"]
    return [] if packet == expected else ["selector/explorer full inventory differs"]


def _v28_selector_issues(request: object, raw_wire: object,
                         selection: object) -> list[str]:
    """Check V28 total and per-kind ceilings at schema, response, and decode layers."""
    if not isinstance(request, dict):
        return ["V28 selector request is malformed"]
    issues: list[str] = []
    try:
        choices_schema = request["text"]["format"]["schema"]["properties"]["choices"]
    except (KeyError, TypeError):
        return ["V28 choices schema is missing"]
    if not isinstance(choices_schema, dict) or choices_schema.get("maxItems") != 3:
        issues.append("V28 choices schema does not enforce the three-choice ceiling")
    try:
        raw = json.loads(raw_wire) if isinstance(raw_wire, str) else raw_wire
    except (ValueError, TypeError):
        raw = None
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if not isinstance(choices, list) or len(choices) > 3:
        issues.append("V28 selector response exceeds three choices")
    elif any(not isinstance(row, dict) or row.get("k") not in {"j", "l", "b"}
             for row in choices):
        issues.append("V28 selector response contains an unknown choice kind")
    else:
        nonbenchmark = sum(row["k"] in {"j", "l"} for row in choices)
        benchmark = sum(row["k"] == "b" for row in choices)
        if nonbenchmark > 2 or benchmark > 1:
            issues.append("V28 selector response exceeds two nonbenchmark or one benchmark")
    if selection is not None:
        journey_count = len(selection.journey_ids)
        lead_count = len(selection.incomplete_observation_ids)
        benchmark_count = int(selection.benchmark_observation_id is not None)
        if journey_count + lead_count + benchmark_count > 3:
            issues.append("V28 decoded selection exceeds three total references")
        if journey_count + lead_count > 2 or benchmark_count > 1:
            issues.append("V28 decoded selection exceeds its two plus one reference ceiling")
    return issues


def _v28_source_selection_issues(prepared: Any, selection: object,
                                delivery_outcome: str) -> list[str]:
    """Retain the existing requirement to select an available journey or lead."""
    if delivery_outcome != "delivered":
        return []
    try:
        packet = prepared.packet
        journeys, leads = packet["journey_rows"], packet["lead_rows"]
    except (AttributeError, KeyError, TypeError):
        return ["V28 source-selection inventory is malformed"]
    if not isinstance(journeys, list) or not isinstance(leads, list):
        return ["V28 source-selection inventory is malformed"]
    if not journeys and not leads:
        return []
    if selection is None:
        return ["V28 delivered result has no decoded source selection"]
    try:
        if journeys and not selection.journey_ids:
            return ["V28 delivered result omitted an available journey selection"]
        if not journeys and leads and not selection.incomplete_observation_ids:
            return ["V28 delivered result omitted an available lead selection"]
    except AttributeError:
        return ["V28 delivered result has malformed decoded source selection"]
    return []


def _v30_selector_guidance_issues(request: object, *, incomplete: bool) -> list[str]:
    """Keep V30's clarified point-unit guidance scoped to incomplete selection."""
    if not isinstance(request, dict) or not isinstance(request.get("instructions"), str):
        return ["V30 selector instructions are malformed"]
    instructions = request["instructions"]
    old_policy = ("Do not compare points across programs as economic value, or prices across "
                 "currencies or unknown scopes as total savings.")
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
    if incomplete:
        if clarification not in instructions or old_policy in instructions:
            return ["V30 incomplete selector lacks the exact cross-program clarification"]
        if ("In this incomplete-only selector view, lead_program_groups replaces lead_rows." not in
                instructions or
                "The groups preserve every original lead, not a ranking." not in instructions):
            return ["V30 incomplete selector lost its lossless grouped-source guidance"]
    elif old_policy not in instructions or clarification in instructions:
        return ["V30 complete selector differs from the V29 inherited point-unit guidance"]
    return []


def _grouped_lead_selector_issues(request: object, prepared: Any, *,
                                  selection_format: str) -> list[str]:
    """Verify grouped lead records invert exactly to the canonical source rows."""
    label = selection_format.replace("roles-v", "V")
    if not isinstance(request, dict):
        return [f"{label} selector request is malformed"]
    try:
        actual_input = json.loads(request["input"])
        actual_packet = actual_input["packet"]
        canonical = prepared.packet
        columns = canonical["legend"]["lead_row"]
        lead_rows = canonical["lead_rows"]
        quote_map = canonical["exact_details"]["component_quotes"]
    except (AttributeError, KeyError, TypeError, ValueError):
        return [f"{label} canonical or selector packet is malformed"]
    if (not isinstance(canonical, dict) or not isinstance(actual_packet, dict) or
            canonical.get("selection_format") != selection_format or
            actual_packet.get("selection_format") != selection_format or
            canonical.get("journey_rows") or not isinstance(columns, list) or
            not isinstance(lead_rows, list) or not isinstance(quote_map, dict)):
        return [f"{label} grouped lead projection has an invalid source or marker"]
    expected_records: list[dict[str, Any]] = []
    refs: set[str] = set()
    for row in lead_rows:
        if not isinstance(row, list) or len(row) != len(columns):
            return [f"{label} canonical lead row differs from its source legend"]
        record = dict(zip(columns, row, strict=True))
        ref = record.get("A_or_C")
        if not isinstance(ref, str) or ref in refs or ref not in quote_map:
            return [f"{label} canonical lead alias or quote is missing or duplicated"]
        refs.add(ref)
        record["original_quote"] = quote_map[ref]
        expected_records.append(record)

    expected_groups: list[dict[str, Any]] = []
    for ordinal, record in enumerate(expected_records):
        program = record.get("program")
        group = next((item for item in expected_groups
                      if type(item["program"]) is type(program) and
                      item["program"] == program), None)
        if group is None:
            group = {"program": program, "members": []}
            expected_groups.append(group)
        group["members"].append({"source_ordinal": ordinal, "record": record})

    groups = actual_packet.get("lead_program_groups")
    if not isinstance(groups, list):
        return [f"{label} grouped lead records are missing"]
    flattened: list[tuple[int, object]] = []
    for group in groups:
        if (not isinstance(group, dict) or set(group) != {"program", "members"} or
                not isinstance(group.get("members"), list)):
            return [f"{label} lead group shape is malformed"]
        for member in group["members"]:
            if (not isinstance(member, dict) or
                    set(member) != {"source_ordinal", "record"} or
                    type(member.get("source_ordinal")) is not int):
                return [f"{label} lead group member wrapper is malformed"]
            flattened.append((member["source_ordinal"], member["record"]))
    ordinals = [ordinal for ordinal, _record in flattened]
    if sorted(ordinals) != list(range(len(expected_records))):
        return [f"{label} source ordinals are missing, duplicated, or out of range"]
    restored = [record for _ordinal, record in sorted(flattened)]
    if json.dumps(restored, ensure_ascii=False, sort_keys=True, separators=(",", ":")) != \
            json.dumps(expected_records, ensure_ascii=False, sort_keys=True, separators=(",", ":")):
        return [f"{label} grouped lead records do not invert to exact source rows and quotes"]
    if json.dumps(groups, ensure_ascii=False, sort_keys=True, separators=(",", ":")) != \
            json.dumps(expected_groups, ensure_ascii=False, sort_keys=True, separators=(",", ":")):
        return [f"{label} program groups differ from first-encounter source grouping"]
    if "lead_records" in actual_packet or "lead_rows" in actual_packet:
        return [f"{label} model view retains a flat or positional lead collection"]
    try:
        from award_agent.results.focused_selector_records import selector_packet

        if selector_packet(prepared) != actual_packet:
            return [f"{label} selector packet differs from canonical projection"]
    except (KeyError, TypeError, ValueError):
        return [f"{label} selector packet could not be reconstructed"]
    return []


def _v24_selector_issues(request: object, prepared: Any, *,
                         complete_format: str = "roles-v21",
                         incomplete_format: str = "roles-v22") -> list[str]:
    """Verify a dynamic named-lead selection projection against its prepared source."""
    if not isinstance(request, dict):
        return ["V24 selector request is malformed"]
    try:
        actual_input = json.loads(request["input"])
        actual_packet = actual_input["packet"]
        canonical = prepared.packet
        journey_rows = canonical["journey_rows"]
        lead_rows = canonical["lead_rows"]
        legend = canonical["legend"]
        exact_details = canonical["exact_details"]
    except (AttributeError, KeyError, TypeError, ValueError):
        return ["V24 canonical or selector packet is malformed"]
    if (not isinstance(actual_packet, dict) or not isinstance(canonical, dict) or
            not isinstance(journey_rows, list) or not isinstance(lead_rows, list)):
        return ["V24 canonical journey/lead inventory is malformed"]
    selection_format = complete_format if journey_rows else incomplete_format
    issues: list[str] = []
    if canonical.get("selection_format") != selection_format:
        issues.append("V24 canonical selector marker disagrees with complete-source inventory")
    if actual_packet.get("selection_format") != selection_format:
        issues.append("V24 model-facing selector marker differs from canonical source")
    if not journey_rows:
        if journey_rows or not lead_rows:
            issues.append("V24 named lead projection is not an incomplete-only source")
        columns = legend.get("lead_row") if isinstance(legend, dict) else None
        quote_map = exact_details.get("component_quotes") if isinstance(exact_details, dict) else None
        lead_records = actual_packet.get("lead_records")
        if (not isinstance(columns, list) or not isinstance(quote_map, dict) or
                not isinstance(lead_records, list) or len(lead_records) != len(lead_rows)):
            issues.append("V24 ordered named lead records or source quote map is malformed")
        else:
            expected_records = []
            refs: set[str] = set()
            for row in lead_rows:
                if not isinstance(row, list) or len(row) != len(columns):
                    issues.append("V24 canonical lead row differs from its legend")
                    continue
                record = dict(zip(columns, row, strict=True))
                ref = record.get("A_or_C")
                if not isinstance(ref, str) or not ref or ref in refs or ref not in quote_map:
                    issues.append("V24 lead row lacks a unique exact quote source")
                    continue
                refs.add(ref)
                record["original_quote"] = quote_map[ref]
                expected_records.append(record)
            if lead_records != expected_records:
                issues.append("V24 ordered lead records or original quotes differ from canonical rows")
            if "lead_rows" in actual_packet:
                issues.append("V24 model-facing packet retains positional lead rows")
            model_details = actual_packet.get("exact_details")
            model_quotes = (model_details.get("component_quotes")
                            if isinstance(model_details, dict) else None)
            expected_remaining = {ref: quote for ref, quote in quote_map.items()
                                  if ref not in refs}
            if model_quotes != expected_remaining:
                issues.append("V24 lead quotes were not relocated out of the flat quote map")
            actual_legend = actual_packet.get("legend")
            if (not isinstance(actual_legend, dict) or "lead_row" in actual_legend or
                    actual_legend.get("lead_records") != [*columns, "original_quote"]):
                issues.append("V24 named lead legend differs from canonical row legend")
    try:
        from award_agent.results.focused_selector_records import selector_packet

        if selector_packet(prepared) != actual_packet:
            issues.append("V24 selector packet differs from canonical projection")
    except (KeyError, TypeError, ValueError):
        issues.append("V24 canonical selector projection could not be reconstructed")
    return issues


def _v23_correction_issues(composition: Any, correction: Any) -> list[str]:
    """Require one correction over the exact draft with only its failed checks."""
    if getattr(correction, "phase", None) != "correction":
        return ["V23 recovery pass is not a V11 correction"]
    try:
        correction_input = json.loads(correction.request["input"])
        composition_input = json.loads(composition.request["input"])
        composition_wire = json.loads(composition.raw_wire)
    except (AttributeError, KeyError, TypeError, ValueError):
        return ["V23 correction input or initial wire is malformed"]
    issues: list[str] = []
    if correction_input.get("previous_wire") != composition_wire:
        issues.append("V23 correction does not receive the exact full initial wire")
    if correction_input.get("packet") != composition_input.get("packet"):
        issues.append("V23 correction does not retain the exact frozen source packet")
    feedback = correction_input.get("feedback")
    expected_failed = [finding for finding in composition.findings
                       if finding.outcome == "failed"]
    if not isinstance(feedback, list) or not feedback:
        return issues + ["V23 correction feedback is missing actual failures"]
    if any(not isinstance(row, dict) or row.get("outcome") != "failed"
           for row in feedback):
        issues.append("V23 correction feedback includes a non-failed finding")
    observed_signature = sorted((row.get("code"), row.get("outcome"), row.get("message"))
                                for row in feedback if isinstance(row, dict))
    expected_signature = sorted((finding.code, finding.outcome, finding.message)
                                for finding in expected_failed)
    if not expected_failed or observed_signature != expected_signature:
        issues.append("V23 correction feedback differs from actual failed findings")
    return issues


def _scout_source_evidence_issues(metadata: object, evidence_root: Path) -> list[str]:
    """Validate legacy raw-file hashes and optional canonical-object hashes."""
    if not isinstance(metadata, dict):
        return ["scout source evidence metadata is malformed"]
    path_name = metadata.get("path_name")
    document = metadata.get("document")
    raw_digest = metadata.get("sha256")
    use = metadata.get("use")
    if (not isinstance(path_name, str) or not path_name or
            Path(path_name).name != path_name or not isinstance(document, dict) or
            not isinstance(raw_digest, str) or
            not isinstance(use, str) or "source evidence only" not in use):
        return ["scout source evidence metadata is malformed"]
    evidence_path = evidence_root / path_name
    if not evidence_path.is_file():
        return ["scout source evidence file is missing"]
    evidence_bytes = evidence_path.read_bytes()
    issues: list[str] = []
    if hashlib.sha256(evidence_bytes).hexdigest() != raw_digest:
        issues.append("scout source evidence raw-file digest differs")
    try:
        observed_document = json.loads(evidence_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        observed_document = None
    if observed_document != document:
        issues.append("scout source evidence file and embedded document differ")
    canonical = json.dumps(document, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    canonical_digest = hashlib.sha256(canonical).hexdigest()
    stored_canonical_digest = metadata.get("canonical_sha256")
    if stored_canonical_digest is not None and stored_canonical_digest != canonical_digest:
        issues.append("scout source evidence canonical-document digest differs")
    return issues


def _artifact_integrity(run: Path, artifact: Any, summary: dict[str, Any],
                        settings: dict[str, Any], archived: dict[str, bytes],
                        reservations: dict[str, list[dict[str, Any]]],
                        issues: list[str]) -> None:
    from run import RECOVERY_DIAGNOSTIC_PROFILES, _preview, append_recovery_guidance

    from award_agent.results.contracts import ResultsConfig
    from award_agent.results.structured_contracts import StructuredResultsArtifact

    campaign_key = str(ledger.CAMPAIGN.relative_to(HERE.parents[4]))
    campaign = json.loads(archived[campaign_key])
    _matches(run, "campaign execution settings",
             (settings["model"], settings["max_output_tokens"],
              settings["timeout_seconds"], settings["max_retries"]),
             (campaign["model"], campaign["max_output_tokens"],
              campaign["timeout_seconds"], campaign["automatic_retries"]), issues)
    version = ("results-artifact-v11" if settings["profile"] in
               {"focused-v23", "focused-v24", "focused-v25", "focused-v26",
                "focused-v27", "focused-v28", "focused-v29", "focused-v30"} else
               "results-artifact-v12" if settings["profile"] in
               {"focused-v17", "focused-v18", "focused-v19", "focused-v20",
                "focused-v21", "focused-v22"} else
               "results-artifact-v11" if settings["profile"] in
               {"focused-v11", "focused-v12", "focused-v13", "focused-v14", "focused-v15", "focused-v16"} else
               "results-artifact-v10" if settings["profile"] in
               {"focused-v8", "focused-v9", "focused-v10"} else
               "results-artifact-v8" if settings["profile"] == "focused-v3" else
               "results-artifact-v9")
    _matches(run, "artifact version for profile", artifact.contract_version,
             version, issues)
    profile_formats = {
        "focused-v3": ("roles-v2", "comparisons-v1"),
        "focused-v4": ("roles-v3", "complete-v1"),
        "focused-v5": ("roles-v4", "complete-v2"),
        "focused-v6": ("roles-v5", "complete-v3"),
        "focused-v7": ("roles-v6", "complete-v4"),
        "focused-v8": ("roles-v7", "complete-v5"),
        "focused-v9": ("roles-v8", "complete-v6"),
        "focused-v10": ("roles-v9", "complete-v7"),
        "focused-v11": ("roles-v10", "complete-v8"),
        "focused-v12": ("roles-v11", "complete-v9"),
        "focused-v13": ("roles-v12", "complete-v10"),
        "focused-v14": ("roles-v13", "complete-v11"),
        "focused-v15": ("roles-v14", "complete-v12"),
        "focused-v16": ("roles-v15", "complete-v13"),
        "focused-v17": ("roles-v16", "complete-v14"),
        "focused-v18": ("roles-v17", "complete-v15"),
        "focused-v19": ("roles-v18", "complete-v16"),
        "focused-v20": ("roles-v19", "complete-v17"),
        "focused-v21": ("roles-v20", "complete-v18"),
        "focused-v22": ("roles-v21", "complete-v19"),
        "focused-v23": ("roles-v21", "complete-v19"),
    }
    if settings["profile"] == "focused-v24":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v21", "complete-v19") if canonical_rows else
                            ("roles-v22", "complete-v20"))
    elif settings["profile"] == "focused-v25":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v21", "complete-v19") if canonical_rows else
                            ("roles-v23", "complete-v21"))
    elif settings["profile"] == "focused-v26":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v21", "complete-v19") if canonical_rows else
                            ("roles-v24", "complete-v22"))
    elif settings["profile"] == "focused-v27":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v21", "complete-v19") if canonical_rows else
                            ("roles-v25", "complete-v23"))
    elif settings["profile"] == "focused-v28":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v26", "complete-v24") if canonical_rows else
                            ("roles-v27", "complete-v25"))
    elif settings["profile"] == "focused-v29":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v28", "complete-v26") if canonical_rows else
                            ("roles-v29", "complete-v27"))
    elif settings["profile"] == "focused-v30":
        canonical_rows = artifact.selector_prepared.packet.get("journey_rows")
        expected_formats = (("roles-v28", "complete-v26") if canonical_rows else
                            ("roles-v30", "complete-v28"))
    else:
        expected_formats = profile_formats[settings["profile"]]
    observed_formats = (artifact.selector_prepared.packet.get("selection_format"),
                        artifact.focus_prepared.packet.get("composition_format")
                        if artifact.focus_prepared is not None else None)
    if observed_formats[1] is not None:
        _matches(run, "profile selection/composition formats", observed_formats,
                 expected_formats, issues)
    else:
        _matches(run, "profile selection format", observed_formats[0],
                 expected_formats[0], issues)
    case = settings["case"]
    source_key = str((HERE.parent /
        "2026-10-25-cost-experiments/luna-retest/round-1" /
        case / "artifact.json").relative_to(HERE.parents[4]))
    config_key = str((HERE.parent /
        "2026-10-25-cost-experiments/luna-retest/round-1" /
        case / "config.json").relative_to(HERE.parents[4]))
    source = StructuredResultsArtifact.model_validate_json(archived[source_key])
    original_config = ResultsConfig.model_validate_json(archived[config_key])
    _matches(run, "original case config hash", settings.get("config_sha256"),
             hashlib.sha256(archived[config_key]).hexdigest(), issues)
    diagnostic = settings.get("recovery_diagnostic", False)
    guidance_key = str((HERE / "recovery-guidance.txt").relative_to(HERE.parents[4]))
    if diagnostic and (settings["profile"] not in RECOVERY_DIAGNOSTIC_PROFILES or
                       settings.get("manifest_sha256") is not None):
        issues.append(f"{run.name}: diagnostic was used for incompatible profile or confirmation")
    if diagnostic and settings.get("recovery_guidance_sha256") != hashlib.sha256(
            archived[guidance_key]).hexdigest():
        issues.append(f"{run.name}: diagnostic guidance hash differs")
    default_key = "data/results/fast-default.json"
    if settings.get("effective_config_source") is None:
        if settings.get("default_config_sha256") is not None:
            issues.append(f"{run.name}: default config hash lacks source marker")
        expected_config = original_config.model_copy(update={
            "model": "gpt-6-luna", "max_output_tokens": settings["max_output_tokens"],
            "timeout_seconds": float(settings["timeout_seconds"]),
            **({"authoring_guidance": archived[guidance_key].decode("utf-8")}
               if diagnostic else {})})
    else:
        _matches(run, "effective config source", settings["effective_config_source"],
                 default_key, issues)
        _matches(run, "proposed default config hash", settings.get("default_config_sha256"),
                 hashlib.sha256(archived[default_key]).hexdigest(), issues)
        candidate = ResultsConfig.model_validate_json(archived[default_key])
        _matches(run, "proposed default campaign model/output/timeout",
                 (candidate.model, candidate.max_output_tokens, candidate.timeout_seconds),
                 (campaign["model"], campaign["max_output_tokens"],
                  campaign["timeout_seconds"]), issues)
        expected_config = candidate.model_copy(update={"authoring_guidance":
            append_recovery_guidance(candidate.authoring_guidance,
                archived[guidance_key].decode("utf-8"))}) if diagnostic else candidate
    _matches(run, "source", artifact.evidence.source, source.evidence.source, issues)
    _matches(run, "effective config", artifact.config, expected_config, issues)
    if default_key in archived and not diagnostic and \
            settings.get("effective_config_source") is None:
        _matches(run, "snapshotted proposed default config",
                 artifact.config, ResultsConfig.model_validate_json(archived[default_key]), issues)
    _matches(run, "summary case", summary["case"], case, issues)
    _matches(run, "summary profile", summary["profile"], settings["profile"], issues)
    _matches(run, "summary diagnostic marker", summary.get("recovery_diagnostic", False),
             diagnostic, issues)
    _matches(run, "editorial revision marker", summary.get("editorial_revision", False),
             artifact.contract_version in {"results-artifact-v10", "results-artifact-v12"}, issues)
    if artifact.contract_version == "results-artifact-v10":
        _matches(run, "revision trigger", summary.get("revision_trigger"),
                 artifact.revision_trigger, issues)
        _matches(run, "revision setting", artifact.revision_settings.reasoning_effort,
                 "low" if settings["profile"] == "focused-v9" else "medium", issues)
        if settings["profile"] == "focused-v10":
            _matches(run, "V10 draft effort", artifact.composer_settings.reasoning_effort,
                     "none", issues)
            _matches(run, "V10 selector effort", artifact.selector_settings.reasoning_effort,
                     "low", issues)
    if artifact.contract_version == "results-artifact-v11":
        v23 = settings["profile"] == "focused-v23"
        v24 = settings["profile"] == "focused-v24"
        v25 = settings["profile"] == "focused-v25"
        v26 = settings["profile"] == "focused-v26"
        v27 = settings["profile"] == "focused-v27"
        v28 = settings["profile"] == "focused-v28"
        v29 = settings["profile"] == "focused-v29"
        v30 = settings["profile"] == "focused-v30"
        _matches(run, "V11 selector effort", artifact.selector_settings.reasoning_effort,
                 "none" if v23 or v24 or v25 or (v26 and bool(
                     artifact.selector_prepared.packet.get("journey_rows"))) or
                     (v27 and bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                     (v28 and bool(artifact.selector_prepared.packet.get("journey_rows"))) else
                 "low" if v26 or (v29 and bool(
                     artifact.selector_prepared.packet.get("journey_rows"))) or
                     (v30 and bool(
                     artifact.selector_prepared.packet.get("journey_rows"))) else
                 "medium" if v27 or v28 or v29 or v30 else
                 "medium" if settings["profile"] == "focused-v14" else "low", issues)
        _matches(run, "V11 composer effort", artifact.composer_settings.reasoning_effort,
                 "low" if v23 or v24 or
                 ((v25 or v26) and bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                 (v27 and bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                 (v28 and not bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                 (v29 and not bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                 (v30 and not bool(artifact.selector_prepared.packet.get("journey_rows"))) or
                 settings["profile"] == "focused-v12" else "medium", issues)
        _matches(run, "V11 correction effort", artifact.correction_settings.reasoning_effort,
                 "low", issues)
        from award_agent.providers.contracts import content_digest

        _matches(run, "V11 registry digest", summary.get("comparison_registry_digest"),
                 content_digest(artifact.comparison_registry.model_dump(mode="json"))
                 if artifact.comparison_registry is not None else None, issues)
        _matches(run, "V11 visible comparison cards", summary.get("comparison_cards"),
                 [block.comparison.comparison_id for block in artifact.resolved.blocks
                  if block.kind == "comparison"] if artifact.resolved is not None else [], issues)
        if v23:
            _matches(run, "V23 Fast settings", (
                artifact.selector_settings.service_tier,
                artifact.composer_settings.service_tier,
                artifact.correction_settings.service_tier), ("fast", "fast", "fast"), issues)
            composition = next((item for item in artifact.passes
                                if item.phase == "composition"), None)
            correction = next((item for item in artifact.passes
                               if item.phase == "correction"), None)
            expected_phases = (["selection", "composition", "correction"] if correction
                               else ["selection", "composition"])
            _matches(run, "V23 pass phases", [item.phase for item in artifact.passes],
                     expected_phases, issues)
            if composition is None:
                issues.append(f"{run.name}: V23 composition pass is missing")
            else:
                try:
                    composition_input = json.loads(composition.request["input"])
                    pair_packet = composition_input.get("packet", {})
                except (KeyError, TypeError, ValueError):
                    pair_packet = {}
                for issue in _pair_packet_issues(
                        pair_packet, selection_format="roles-v21",
                        composition_format="complete-v19",
                        require_traveler_evidence=True):
                    issues.append(f"{run.name}: V23 {issue}")
                if correction is not None:
                    for issue in _v23_correction_issues(composition, correction):
                        issues.append(f"{run.name}: {issue}")
                elif any(finding.outcome == "failed" for finding in composition.findings):
                    issues.append(f"{run.name}: V23 omitted correction despite failed checks")
                if correction is not None and not any(
                        finding.outcome == "failed" for finding in composition.findings):
                    issues.append(f"{run.name}: V23 made an unjustified correction call")
            selector = next((item for item in artifact.passes
                             if item.phase == "selection"), None)
            for issue in _v22_selector_issues(
                    selector.request if selector else None,
                    selector.raw_wire if selector else None,
                    selector.selection if selector else None):
                issues.append(f"{run.name}: V23 {issue}")
            try:
                selector_input = json.loads(selector.request["input"]) if selector else {}
                selector_packet_value = (selector_input.get("packet", {})
                    if isinstance(selector_input, dict) else {})
            except (KeyError, TypeError, ValueError):
                selector_packet_value = {}
            for issue in _v22_inventory_issues(
                    selector_packet_value, artifact.selector_prepared):
                issues.append(f"{run.name}: V23 {issue}")
        if v24 or v25 or v26 or v27 or v28 or v29 or v30:
            label = "V30" if v30 else "V29" if v29 else "V28" if v28 else "V27" if v27 else "V26" if v26 else "V25" if v25 else "V24"
            _matches(run, f"{label} Fast settings", (
                artifact.selector_settings.service_tier,
                artifact.composer_settings.service_tier,
                artifact.correction_settings.service_tier), ("fast", "fast", "fast"), issues)
            composition = next((item for item in artifact.passes
                                if item.phase == "composition"), None)
            correction = next((item for item in artifact.passes
                               if item.phase == "correction"), None)
            expected_phases = (["selection", "composition", "correction"] if correction
                               else ["selection", "composition"])
            _matches(run, f"{label} pass phases", [item.phase for item in artifact.passes],
                     expected_phases, issues)
            if composition is None:
                issues.append(f"{run.name}: {label} composition pass is missing")
            else:
                try:
                    composition_input = json.loads(composition.request["input"])
                    pair_packet = composition_input.get("packet", {})
                except (KeyError, TypeError, ValueError):
                    pair_packet = {}
                selection_format, composition_format = expected_formats
                for issue in _pair_packet_issues(
                        pair_packet, selection_format=selection_format,
                        composition_format=composition_format,
                        require_traveler_evidence=True):
                    issues.append(f"{run.name}: {label} {issue}")
                try:
                    from award_agent.results.focused_records import writer_packet

                    if writer_packet(artifact.focus_prepared) != pair_packet:
                        issues.append(f"{run.name}: {label} writer packet differs from prepared source")
                except (KeyError, TypeError, ValueError):
                    issues.append(f"{run.name}: {label} prepared writer packet cannot be projected")
                if correction is not None:
                    for issue in _v23_correction_issues(composition, correction):
                        issues.append(f"{run.name}: {label} {issue}")
                elif any(finding.outcome == "failed" for finding in composition.findings):
                    issues.append(f"{run.name}: {label} omitted correction despite failed checks")
                if correction is not None and not any(
                        finding.outcome == "failed" for finding in composition.findings):
                    issues.append(f"{run.name}: {label} made an unjustified correction call")
            selector = next((item for item in artifact.passes
                             if item.phase == "selection"), None)
            selector_request = selector.request if selector else None
            selector_wire = selector.raw_wire if selector else None
            selector_selection = selector.selection if selector else None
            selector_issues = (_v28_selector_issues(selector_request, selector_wire,
                                                     selector_selection) if v28 or v29 or v30 else
                               _v22_selector_issues(selector_request, selector_wire,
                                                    selector_selection))
            for issue in selector_issues:
                issues.append(f"{run.name}: {label} {issue}")
            if (v29 or v30) and not artifact.selector_prepared.packet.get("journey_rows"):
                selector_projection_issues = _grouped_lead_selector_issues(
                    selector.request if selector else None, artifact.selector_prepared,
                    selection_format="roles-v30" if v30 else "roles-v29")
            else:
                selector_projection_issues = _v24_selector_issues(
                    selector.request if selector else None, artifact.selector_prepared,
                    complete_format="roles-v28" if v29 or v30 else "roles-v26" if v28 else "roles-v21",
                    incomplete_format=("roles-v30" if v30 else "roles-v29" if v29 else
                                       "roles-v27" if v28 else
                                       "roles-v25" if v27 else "roles-v24" if v26 else
                                       "roles-v23" if v25 else "roles-v22"))
            for issue in selector_projection_issues:
                issues.append(f"{run.name}: {issue}")
            if v30:
                for issue in _v30_selector_guidance_issues(
                        selector_request,
                        incomplete=not bool(artifact.selector_prepared.packet.get("journey_rows"))):
                    issues.append(f"{run.name}: {issue}")
            if v28 or v29 or v30:
                for issue in _v28_source_selection_issues(
                        artifact.selector_prepared, selector_selection,
                        artifact.delivery_outcome):
                    issues.append(f"{run.name}: {issue}")
                try:
                    selector_input = json.loads(selector.request["input"]) if selector else {}
                    selector_packet_value = (selector_input.get("packet", {})
                        if isinstance(selector_input, dict) else {})
                except (KeyError, TypeError, ValueError):
                    selector_packet_value = {}
                for issue in _v22_inventory_issues(
                        selector_packet_value, artifact.selector_prepared):
                    issues.append(f"{run.name}: {label} {issue}")
    if artifact.contract_version == "results-artifact-v12":
        _matches(run, "V17 revision trigger", summary.get("revision_trigger"),
                 artifact.revision_trigger, issues)
        expected_patch_reasoning = (("none", "low", "medium")
            if settings["profile"] in {"focused-v21", "focused-v22"} else
            ("low", "low", "low" if settings["profile"] in {
                "focused-v18", "focused-v19", "focused-v20"} else "medium"))
        _matches(run, "patch profile reasoning settings", (
            artifact.selector_settings.reasoning_effort,
            artifact.composer_settings.reasoning_effort,
            artifact.revision_settings.reasoning_effort), expected_patch_reasoning, issues)
        from award_agent.providers.contracts import content_digest

        _matches(run, "V17 registry digest", summary.get("comparison_registry_digest"),
                 content_digest(artifact.comparison_registry.model_dump(mode="json"))
                 if artifact.comparison_registry is not None else None, issues)
        _matches(run, "V17 visible comparison cards", summary.get("comparison_cards"),
                 [block.comparison.comparison_id for block in artifact.resolved.blocks
                  if block.kind == "comparison"] if artifact.resolved is not None else [], issues)
        if settings["profile"] in {"focused-v19", "focused-v20", "focused-v21", "focused-v22"}:
            _matches(run, f"{settings['profile']} reasoning/Fast settings", (
                artifact.selector_settings.reasoning_effort,
                artifact.composer_settings.reasoning_effort,
                artifact.revision_settings.reasoning_effort,
                artifact.selector_settings.service_tier,
                artifact.composer_settings.service_tier,
                artifact.revision_settings.service_tier),
                expected_patch_reasoning + ("fast", "fast", "fast"), issues)
            composition = next((item for item in artifact.passes
                                if item.phase == "composition"), None)
            try:
                payload = json.loads(composition.request["input"]) if composition else {}
                packet = payload.get("packet", {}) if isinstance(payload, dict) else {}
            except (KeyError, TypeError, ValueError):
                packet = {}
            formats = {"focused-v19": ("roles-v18", "complete-v16"),
                       "focused-v20": ("roles-v19", "complete-v17"),
                       "focused-v21": ("roles-v20", "complete-v18"),
                       "focused-v22": ("roles-v21", "complete-v19")}
            selection_format, composition_format = formats[settings["profile"]]
            for issue in _pair_packet_issues(packet, selection_format=selection_format,
                                             composition_format=composition_format,
                                             require_traveler_evidence=(
                                                 settings["profile"] in {
                                                     "focused-v20", "focused-v21", "focused-v22"})):
                issues.append(f"{run.name}: {settings['profile']} {issue}")
            if settings["profile"] == "focused-v22":
                selector = next((item for item in artifact.passes
                                 if item.phase == "selection"), None)
                for issue in _v22_selector_issues(
                        selector.request if selector else None,
                        selector.raw_wire if selector else None,
                        selector.selection if selector else None):
                    issues.append(f"{run.name}: V22 {issue}")
                try:
                    selector_payload = json.loads(selector.request["input"]) if selector else {}
                    selector_packet_value = (selector_payload.get("packet", {})
                        if isinstance(selector_payload, dict) else {})
                except (KeyError, TypeError, ValueError):
                    selector_packet_value = {}
                for issue in _v22_inventory_issues(
                        selector_packet_value, artifact.selector_prepared):
                    issues.append(f"{run.name}: V22 {issue}")
            revision = artifact.passes[2] if len(artifact.passes) == 3 else None
            if revision is not None and revision.patch is not None:
                if any(edit.end != edit.start + 1 or len(edit.blocks) > 1
                       for edit in revision.patch.edits):
                    issues.append(f"{run.name}: {settings['profile']} patch is not a one-block replace/delete")
    if diagnostic:
        expected_fault_code = (
            "empty_explanation" if settings["profile"] in {"focused-v24", "focused-v25", "focused-v26", "focused-v27", "focused-v28", "focused-v29", "focused-v30"} and
            artifact.selector_prepared.packet.get("selection_format") in {"roles-v22", "roles-v23", "roles-v24", "roles-v25", "roles-v27", "roles-v29", "roles-v30"} else
            "visible_internal_alias")
        _matches(run, "diagnostic correction trigger", summary["recovery_triggered"],
                 len(artifact.passes) == 3 and
                 artifact.contract_version != "results-artifact-v12", issues)
        _matches(run, "diagnostic fault observed", summary["diagnostic_fault_observed"],
                 len(artifact.passes) > 1 and any(
                     f.code == expected_fault_code and f.outcome == "failed"
                     for f in artifact.passes[1].findings), issues)
        expected_failed = ([f.model_dump(mode="json") for f in artifact.passes[1].findings
                            if f.outcome == "failed"] if len(artifact.passes) > 1 else [])
        _matches(run, "diagnostic initial findings",
                 summary["initial_composition_failed_findings"], expected_failed, issues)
    _matches(run, "summary outcome", (
        summary["generation_outcome"], summary["validation_outcome"],
        summary["delivery_outcome"]), (
        artifact.generation_outcome, artifact.validation_outcome,
        artifact.delivery_outcome), issues)
    _matches(run, "summary pass phases/outcomes",
             [(row["phase"], row["outcome"]) for row in summary["passes"]],
             [(item.phase, item.outcome) for item in artifact.passes], issues)
    for index, item in enumerate(artifact.passes):
        raw = json.loads(item.writer_receipt.raw_response) if (
            item.writer_receipt and item.writer_receipt.raw_response) else {}
        _matches(run, f"pass {index + 1} summary tier and usage",
                 (summary["passes"][index]["returned_service_tier"],
                  summary["passes"][index]["usage"]),
                 (item.returned_service_tier, raw.get("usage")), issues)
    selected = getattr(artifact, "selected_pass_index", None)
    if selected is None and artifact.resolved is not None:
        selected = next((i for i in range(len(artifact.passes) - 1, -1, -1)
                         if artifact.passes[i].document is not None), None)
    _matches(run, "selected pass", summary["selected_pass_index"], selected, issues)
    selected_findings = artifact.passes[selected].findings if selected is not None else ()
    _matches(run, "selected failed findings", summary["failed_findings"],
             [finding.model_dump(mode="json") for finding in selected_findings
              if finding.outcome == "failed"], issues)
    if artifact.resolved is not None:
        _matches(run, "resolved.json", ledger.read_json(run / "resolved.json"),
                 artifact.resolved.model_dump(mode="json"), issues)
        _matches(run, "answer preview", (run / "answer-preview.md").read_text(),
                 _preview(artifact.resolved), issues)
    elif (run / "resolved.json").exists() or (run / "answer-preview.md").exists():
        issues.append(f"{run.name}: unavailable run has resolved answer files")
    for kind in ("count", "generation"):
        calls = [item for item in reservations[kind] if item["run_name"] == run.name]
        _matches(run, f"{kind} call count", len(calls), summary[f"{kind}_calls"], issues)
        if len(calls) > 3:
            issues.append(f"{run.name}: per-run {kind} bound exceeded")
    _matches(run, "generation calls and artifact",
             summary["generation_calls"], sum(item.writer_called for item in artifact.passes),
             issues)
    for index, item in enumerate(artifact.passes, 1):
        folder = run / f"pass-{index:02d}"
        if (folder / "count-request.json").exists():
            _matches(run, f"pass {index} count request",
                     ledger.read_json(folder / "count-request.json"), item.request, issues)
        if item.input_token_receipt is not None:
            _matches(run, f"pass {index} count receipt",
                     ledger.read_json(folder / "count-receipt.json"),
                     item.input_token_receipt.model_dump(mode="json"), issues)
        if item.writer_called:
            expected = dict(item.request, max_output_tokens=artifact.config.max_output_tokens,
                            store=False, truncation="disabled", stream=True)
            tier = (artifact.selector_settings.service_tier if index == 1 else
                    artifact.correction_settings.service_tier if index == 3 and
                    artifact.contract_version == "results-artifact-v11" else
                    artifact.revision_settings.service_tier if index == 3 and
                    artifact.contract_version in {"results-artifact-v10", "results-artifact-v12"} else
                    artifact.composer_settings.service_tier)
            if tier == "fast":
                expected["service_tier"] = "fast"
            _matches(run, f"pass {index} generation request",
                     ledger.read_json(folder / "generation-request.json"), expected, issues)
            if item.writer_receipt is not None:
                _matches(run, f"pass {index} writer receipt",
                         ledger.read_json(folder / "writer-receipt.json"),
                         item.writer_receipt.model_dump(mode="json"), issues)
                if item.writer_receipt.raw_response is not None:
                    _matches(run, f"pass {index} raw response",
                             ledger.read_json(folder / "raw-response.json"),
                             json.loads(item.writer_receipt.raw_response), issues)


def _manifest_integrity(run: Path, settings: dict[str, Any],
                        snapshot: dict[str, str], issues: list[str]) -> None:
    if settings.get("manifest_sha256") is None:
        return
    manifest_path = run / "manifest.json"
    if ledger.sha256(manifest_path) != settings["manifest_sha256"]:
        issues.append(f"{run.name}: frozen manifest hash differs")
    manifest = ledger.read_json(manifest_path)
    source_evidence = manifest.get("scout_source_evidence")
    if source_evidence is not None:
        for issue in _scout_source_evidence_issues(source_evidence, HERE):
            issues.append(f"{run.name}: {issue}")
    rows = [row for row in manifest["runs"] if row["name"] == run.name]
    if (len(rows) != 1 or rows[0]["case"] != settings["case"] or
            rows[0]["profile"] != settings["profile"] or
            rows[0]["source_sha256"] != settings["source_sha256"] or
            rows[0]["snapshot_hashes"] != snapshot or
            manifest["campaign_sha256"] != settings["campaign_sha256"]):
        issues.append(f"{run.name}: frozen manifest membership/source/code differs")


def report() -> dict[str, Any]:
    campaign = ledger.campaign()
    issues: list[str] = []
    reservations: dict[str, list[dict[str, Any]]] = {}
    for kind in ("count", "generation"):
        files = sorted(ledger.CALLS.glob(f"{kind}-*.json"))
        if len(files) > campaign["maximum_input_count_calls" if kind == "count"
                                 else "maximum_generation_calls"]:
            issues.append(f"{kind}: bound exceeded")
        ordinals = [int(file.stem.rsplit("-", 1)[-1]) for file in files]
        if ordinals != list(range(1, len(files) + 1)):
            issues.append(f"{kind}: reservation sequence has a gap")
        reservations[kind] = [ledger.read_json(path) for path in files]
    from award_agent.providers.contracts import content_digest
    from award_agent.results.focused import parse_focused_artifact, replay_focused_results
    summaries = []
    for run in sorted(RUNS.iterdir()) if RUNS.exists() else []:
        if not run.is_dir():
            continue
        try:
            settings = ledger.read_json(run / "settings.json")
            archived = _check_archive(run, issues)
            snapshot = ledger.read_json(run / "source-snapshot.json")
            if settings["source_sha256"] != snapshot[
                    str((HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1" /
                         settings["case"] / "artifact.json").relative_to(HERE.parents[4]))]:
                issues.append(f"{run.name}: saved source hash differs")
            if settings["campaign_sha256"] != snapshot[str(ledger.CAMPAIGN.relative_to(HERE.parents[4]))]:
                issues.append(f"{run.name}: campaign snapshot hash differs")
            _manifest_integrity(run, settings, snapshot, issues)
            artifact_path = run / "artifact.json"
            summary_path = run / "summary.json"
            if artifact_path.is_file() and summary_path.is_file():
                artifact = parse_focused_artifact(artifact_path.read_bytes())
                summary = ledger.read_json(summary_path)
                if replay_focused_results(artifact) != artifact.resolved:
                    issues.append(f"{run.name}: replay differs")
                _artifact_integrity(run, artifact, summary, settings, archived,
                                    reservations, issues)
                summaries.append({"run": run.name, "case": summary["case"],
                                  "profile": summary["profile"],
                                  "recovery_diagnostic": summary.get("recovery_diagnostic", False),
                                  "recovery_triggered": summary.get("recovery_triggered", False),
                                  "diagnostic_fault_observed": summary.get(
                                      "diagnostic_fault_observed", False),
                                  "seconds": summary["outer_results_completion_seconds"],
                                  "delivery": summary["delivery_outcome"],
                                  "validation": summary["validation_outcome"]})
            elif not (run / "run-error.json").is_file():
                issues.append(f"{run.name}: missing artifact/summary and error receipt")
            for kind in ("count", "generation"):
                for reservation in (item for item in reservations[kind]
                                    if item["run_name"] == run.name):
                    folder = run / reservation["label"]
                    request_path = folder / f"{kind}-request.json"
                    if not request_path.is_file():
                        issues.append(f"{run.name}: missing {kind} request")
                    elif content_digest(ledger.read_json(request_path)) != reservation["request_digest"]:
                        issues.append(f"{run.name}: {kind} request digest differs")
                    if not any((folder / file).is_file() for file in
                               (("count-receipt.json", "count-error.json") if kind == "count"
                                else ("writer-receipt.json", "generation-error.json"))):
                        issues.append(f"{run.name}: {kind} has no response/error receipt")
        except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as exc:
            issues.append(f"{run.name}: verification error {type(exc).__name__}: {exc}")
    for kind in ("count", "generation"):
        for item in reservations[kind]:
            if not (RUNS / item["run_name"]).is_dir():
                issues.append(f"{kind}: reservation for missing run {item['run_name']}")
    return {"campaign": str(ledger.CAMPAIGN),
            "generation_reservations": len(reservations["generation"]),
            "count_reservations": len(reservations["count"]),
            "runs": summaries,
            "natural_runs": [row for row in summaries if not row["recovery_diagnostic"]],
            "recovery_diagnostic_runs": [row for row in summaries if row["recovery_diagnostic"]],
            "integrity_issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = report()
    print(json.dumps(result, indent=2))
    return 1 if args.verify and result["integrity_issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
