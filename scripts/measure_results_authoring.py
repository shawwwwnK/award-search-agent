"""Measure V4 and compact V5 Results request sizes on the frozen 006 cases.

This is an offline byte-accounting utility. It does not call a model or tokenize
the request. Historical token receipts are reported separately from the newly
serialized request sizes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, prepare_results
from award_agent.results.contracts import CheckFinding, ResultsDocument
from award_agent.results.core import authoring_payload
from award_agent.results.request import token_request

REPO = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO / "evidence/end-to-end/presentation/iterations/006"
CASES = ("admitted", "conditional", "incomplete")
DEFAULT_CONFIG = SOURCE_ROOT / "config.json"
DEFAULT_OUTPUT = REPO / "evidence/results-stage/m2/compact-input/2026-10-20-luna/offline-measurement.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


_HASH64 = re.compile(r"\b[a-fA-F0-9]{64}\b")


def _replace_hash_strings(value: object, aliases: dict[str, str]) -> object:
    if isinstance(value, str):
        return _HASH64.sub(lambda match: aliases[match.group(0)], value)
    if isinstance(value, list):
        return [_replace_hash_strings(item, aliases) for item in value]
    if isinstance(value, dict):
        replaced: dict[object, object] = {}
        for key, item in value.items():
            new_key = _replace_hash_strings(key, aliases) if isinstance(key, str) else key
            replaced[new_key] = _replace_hash_strings(item, aliases)
        return replaced
    return value


def _shorten_hash_ids(request: dict[str, object]) -> tuple[dict[str, object], int]:
    """Measurement-only structural replacement of embedded 64-hex strings."""
    result = copy.deepcopy(request)
    input_value = result.get("input")
    if not isinstance(input_value, str):
        raise TypeError("token request input must be serialized JSON")
    input_object = json.loads(input_value)
    matches = set(_HASH64.findall(input_value))
    # Also consider structured non-input request fields (instructions/schema).
    outer_bytes = _json_bytes({key: value for key, value in result.items() if key != "input"})
    matches.update(_HASH64.findall(outer_bytes.decode("utf-8")))
    aliases = {value: f"ID{index}" for index, value in enumerate(sorted(matches), 1)}
    replaced_input = _replace_hash_strings(input_object, aliases)
    result["input"] = json.dumps(replaced_input, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"))
    replaced_outer = _replace_hash_strings({key: value for key, value in result.items()
                                            if key != "input"}, aliases)
    result.update(cast(dict[str, object], replaced_outer))
    return result, len(aliases)


def _filter_rejected_alternatives(request: dict[str, object]) -> tuple[dict[str, object], int]:
    """Remove only rejected alternative rows; keep all linked source tables intact."""
    result = copy.deepcopy(request)
    input_value = result.get("input")
    if not isinstance(input_value, str):
        raise TypeError("token request input must be serialized JSON")
    body = cast(dict[str, Any], json.loads(input_value))
    prepared = cast(dict[str, Any], body["prepared"])
    source = cast(dict[str, Any], prepared["source"])
    alternatives = cast(list[dict[str, Any]], source["alternatives"])
    retained = [item for item in alternatives if item.get("status") != "rejected"]
    removed = len(alternatives) - len(retained)
    source["alternatives"] = retained
    result["input"] = json.dumps(body, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"))
    return result, removed


def _expand_compact_groups(request: dict[str, object]) -> tuple[dict[str, object], dict[str, int]]:
    """Counterfactually repeat each multi-member group's facts for its members."""
    result = copy.deepcopy(request)
    input_value = result.get("input")
    if not isinstance(input_value, str):
        raise TypeError("token request input must be serialized JSON")
    body = cast(dict[str, Any], json.loads(input_value))
    prepared = cast(dict[str, Any], body["prepared"])
    view = cast(dict[str, Any], prepared["view"])
    stats: dict[str, int] = {}
    for key in ("journeys", "components"):
        groups = cast(list[dict[str, Any]], view.get(key, []))
        expanded: list[dict[str, Any]] = []
        for group in groups:
            members = cast(list[dict[str, Any]], group.get("members", []))
            if len(members) > 1:
                stats[f"{key}_groups_expanded"] = stats.get(f"{key}_groups_expanded", 0) + 1
                stats[f"{key}_extra_members"] = stats.get(f"{key}_extra_members", 0) + len(members) - 1
            for member in members:
                expanded.append({"facts": group["facts"], "members": [member]})
        view[key] = expanded
        stats[f"{key}_before"] = len(groups)
        stats[f"{key}_after"] = len(expanded)
    result["input"] = json.dumps(body, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"))
    return result, stats


def _historical_counts(artifact: dict[str, Any]) -> dict[str, object]:
    attempts = artifact.get("attempts", [])
    receipts = [attempt.get("input_token_receipt") for attempt in attempts]
    tokens = [receipt.get("input_tokens") if receipt else None for receipt in receipts]
    return {"attempt_count": len(attempts), "input_tokens": tokens,
            "writer_usage": [attempt.get("writer_receipt", {}).get("usage")
                             if attempt.get("writer_receipt") else None for attempt in attempts]}


def measure_case(case: str, config: ResultsConfig) -> dict[str, object]:
    case_dir = SOURCE_ROOT / case
    source_path = case_dir / "artifact.json"
    source_artifact = json.loads(source_path.read_text())
    projection = SolutionProjection.model_validate(source_artifact["projection"])
    baseline = prepare_results(projection, config, version="results-artifact-v4")
    compact = prepare_results(projection, config, version="results-artifact-v5")

    baseline_initial_payload = authoring_payload(baseline)
    compact_initial_payload = authoring_payload(compact)
    baseline_request = token_request(baseline, config, baseline_initial_payload)
    compact_request = token_request(compact, config, compact_initial_payload)

    historical_initial = source_artifact["attempts"][0]
    historical_findings = tuple(
        # Use the saved V4 initial findings as representative correction feedback.
        CheckFinding.model_validate(item)
        for item in historical_initial.get("findings", [])
    )
    historical_document_data = historical_initial.get("document")
    historical_document = None
    if historical_document_data:
        historical_document = ResultsDocument.model_validate(historical_document_data)
    baseline_correction_payload = authoring_payload(
        baseline, historical_findings, historical_document)
    compact_correction_payload = authoring_payload(
        compact, historical_findings, historical_document)
    baseline_correction = token_request(baseline, config, baseline_correction_payload)
    compact_correction = token_request(compact, config, compact_correction_payload)

    baseline_initial_bytes = _json_bytes(baseline_request)
    compact_initial_bytes = _json_bytes(compact_request)
    baseline_correction_bytes = _json_bytes(baseline_correction)
    compact_correction_bytes = _json_bytes(compact_correction)
    shortened_ids_request, shortened_id_count = _shorten_hash_ids(baseline_request)
    filtered_rejected_request, rejected_rows_removed = _filter_rejected_alternatives(
        baseline_request)
    expanded_groups_request, grouping_stats = _expand_compact_groups(compact_request)
    shortened_ids_bytes = _json_bytes(shortened_ids_request)
    filtered_rejected_bytes = _json_bytes(filtered_rejected_request)
    expanded_groups_bytes = _json_bytes(expanded_groups_request)
    eligible = [item for item in projection.view.alternatives
                if item.status in {"admitted", "conditional"}]
    rejected = [item for item in projection.view.alternatives
                if item.status == "rejected"]
    authoring_view = compact.authoring_view
    groups = (cast(list[object], authoring_view.view.get("journeys", []))
              if authoring_view is not None else [])
    component_groups = (cast(list[object], authoring_view.view.get("components", []))
                        if authoring_view is not None else [])
    return {
        "case": case,
        "source_artifact": str(source_path.relative_to(REPO)),
        "source_artifact_sha256": _sha256(source_path.read_bytes()),
        "canonical_source_digest": compact.source_digest,
        "historical_iteration_006": _historical_counts(source_artifact),
        "candidate_counts": {"canonical_total": len(projection.view.alternatives),
                             "eligible_selectable": len(eligible),
                             "rejected_summarized": len(rejected),
                             "compact_journey_groups": len(groups),
                             "journeys_factored": len(eligible) - len(groups),
                             "compact_component_groups": len(component_groups)},
        "requests": {
            "v4_baseline": {
                "contract_version": baseline.contract_version,
                "instructions_bytes": len(baseline.instructions.encode("utf-8")),
                "schema_bytes": len(_json_bytes(cast(dict[str, Any], baseline_request["text"])
                                                  ["format"]["schema"])),
                "input_string_bytes": len(baseline_initial_payload.encode("utf-8")),
                "initial_json_bytes": len(baseline_initial_bytes),
                "initial_sha256": _sha256(baseline_initial_bytes),
                "representative_correction_json_bytes": len(baseline_correction_bytes),
                "representative_correction_sha256": _sha256(baseline_correction_bytes),
            },
            "v5_compact": {
                "contract_version": compact.contract_version,
                "instructions_bytes": len(compact.instructions.encode("utf-8")),
                "schema_bytes": len(_json_bytes(cast(dict[str, Any], compact_request["text"])
                                                  ["format"]["schema"])),
                "input_string_bytes": len(compact_initial_payload.encode("utf-8")),
                "initial_json_bytes": len(compact_initial_bytes),
                "initial_sha256": _sha256(compact_initial_bytes),
                "representative_correction_json_bytes": len(compact_correction_bytes),
                "representative_correction_sha256": _sha256(compact_correction_bytes),
            },
        },
        "byte_reduction_percent": {
            "initial": round(100 * (1 - len(compact_initial_bytes) / len(baseline_initial_bytes)), 2),
            "representative_correction": round(
                100 * (1 - len(compact_correction_bytes) / len(baseline_correction_bytes)), 2),
        },
        "counterfactual_report": {
            "nonadditive": True,
            "simulation_not_production": True,
            "directions": {
                "opaque_identifier_shortening": {
                    "method": "Replace every structural 64-hex match in baseline request keys and "
                              "string values, including embedded IDs, with deterministic ID labels. "
                              "Labels estimate size only; no production replacement is proposed.",
                    "distinct_64hex_identifiers": shortened_id_count,
                    "baseline_request_json_bytes": len(baseline_initial_bytes),
                    "counterfactual_request_json_bytes": len(shortened_ids_bytes),
                    "byte_saving": len(baseline_initial_bytes) - len(shortened_ids_bytes),
                },
                "rejected_candidate_row_filtering": {
                    "method": "Remove rejected alternative rows from the V4 baseline source while "
                              "retaining all linked tables and metadata as a conservative isolated "
                              "filtering estimate.",
                    "rejected_rows_removed": rejected_rows_removed,
                    "baseline_request_json_bytes": len(baseline_initial_bytes),
                    "counterfactual_request_json_bytes": len(filtered_rejected_bytes),
                    "byte_saving": len(baseline_initial_bytes) - len(filtered_rejected_bytes),
                },
                "observation_grouping": {
                    "method": "Expand each multi-member compact journey/component group into "
                              "singleton entries by repeating its shared facts once per member.",
                    **grouping_stats,
                    "compact_request_json_bytes": len(compact_initial_bytes),
                    "ungrouped_counterfactual_request_json_bytes": len(expanded_groups_bytes),
                    "byte_saving_from_grouping": len(expanded_groups_bytes) - len(compact_initial_bytes),
                },
            },
            "note": "These isolated counterfactuals overlap with each other and with the combined "
                    "V4-to-V5 representation change. Their savings must not be added.",
        },
        "interpretation": "Serialized UTF-8 byte counts only; no new token count was requested. "
                          "The correction is reconstructed from saved V4 feedback and draft, "
                          "then translated into the compact alias namespace.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="Saved ResultsConfig; model is set to GPT-6 Luna for comparability")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="New JSON report path; existing files are never overwritten")
    args = parser.parse_args()
    config = ResultsConfig.model_validate_json(args.config.read_text()).model_copy(
        update={"model": "gpt-6-luna"})
    result = {
        "method": "offline complete token-bearing Results request serialization",
        "model_setting": config.model,
        "config_source": str(args.config.relative_to(REPO)) if args.config.is_relative_to(REPO)
        else str(args.config),
        "config_sha256": _sha256(args.config.read_bytes()),
        "cases": [measure_case(case, config) for case in CASES],
        "bytes_are_not_tokens": True,
    }
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
