"""Offline source, reference, inverse and schedule audit of candidate.py."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from candidate import (
    AWARD_FIELDS,
    CASH_FIELDS,
    GUIDE,
    SCHEDULE_FIELDS,
    compact,
    inventories,
    restore,
    schedule_is_complete,
    transform,
)

from award_agent.results.structured_contracts import StructuredResultsArtifact

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CASES = ("admitted", "conditional", "incomplete")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _by_alias(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {member["ref"]: group["facts"] for group in view["components"]
            for member in group["members"]}


def audit(case: str) -> dict[str, Any]:
    source = SOURCE / case
    request_bytes = (source / "01-request.json").read_bytes()
    source_bytes = (source / "artifact.json").read_bytes()
    original = json.loads(request_bytes)
    artifact = StructuredResultsArtifact.model_validate_json(source_bytes)
    original_view = json.loads(original["input"])["prepared"]["view"]
    candidate = transform(original, artifact.prepared)
    transformed = json.loads(candidate["input"])
    view = transformed["prepared"]["view"]
    assert restore(candidate) == original
    assert inventories(view) == inventories(original_view)
    assert candidate["instructions"] == original["instructions"] + GUIDE
    assert candidate["model"] == original["model"]
    assert candidate["text"] == original["text"]
    assert candidate["input"].startswith('{"prepared":')
    assert list(transformed) == ["prepared", "feedback", "previous_document"]
    assert transformed["feedback"] == json.loads(original["input"])["feedback"]
    assert transformed["previous_document"] == json.loads(original["input"])["previous_document"]
    assert transformed["prepared"]["contract_version"] == artifact.prepared.contract_version

    components = _by_alias(original_view)
    original_groups = original_view["journeys"]
    transformed_groups = view["journeys"]
    assert len(original_groups) == len(transformed_groups)
    source_members: dict[str, dict[str, Any]] = {}
    candidate_members: dict[str, dict[str, Any]] = {}
    expected_schedules: dict[str, dict[str, Any]] = {}
    for original_group, candidate_group in zip(original_groups, transformed_groups, strict=True):
        assert [m["ref"] for m in original_group["members"]] == [
            m["ref"] for m in candidate_group["members"]]
        facts = original_group["facts"]
        schedule = {field: facts[field] for field in SCHEDULE_FIELDS}
        for member, revised in zip(original_group["members"],
                                   candidate_group["members"], strict=True):
            alias = member["ref"]
            assert alias not in source_members
            complete = schedule_is_complete(schedule)
            key = compact(schedule) if complete else f"unknown:{alias}"
            expected = {"schedule": schedule, "choices": []}
            if not complete:
                expected["relationship"] = "schedule_unknown_singleton"
            entry = expected_schedules.setdefault(key, expected)
            award = components[member["award"]]
            cash = components[member["cash"]] if member["cash"] is not None else None
            choice = revised["choice"]
            assert choice["award_quote"] == {field: award[field] for field in AWARD_FIELDS}
            assert choice["cash_quote"] == (None if cash is None else
                                            {field: cash[field] for field in CASH_FIELDS})
            assert {k: v for k, v in revised.items() if k != "choice"} == member
            source_members[alias] = member
            candidate_members[alias] = revised
            entry["choices"].append({
                "ref": alias, "cabin": facts["award_cabin"],
                "program": choice["award_quote"]["program"],
                "points": choice["award_quote"]["points"],
                "booking_obligation": facts["booking_obligation"],
            })
    assert view["same_schedule"] == list(expected_schedules.values())
    indexed_refs = [item["ref"] for group in view["same_schedule"]
                    for item in group["choices"]]
    assert sorted(indexed_refs) == sorted(source_members)
    assert len(indexed_refs) == len(set(indexed_refs))
    assert set(candidate_members) == set(source_members)

    # Synthetic correction alters only changing fields. This proves local string
    # placement, not actual cache behavior or response speed.
    changed_original = json.loads(original["input"])
    changed_original["feedback"] = [{"code": "diagnostic"}]
    changed_original["previous_document"] = {"diagnostic": True}
    correction = dict(original, input=compact(changed_original))
    revised_correction = transform(correction, artifact.prepared)
    assert restore(revised_correction) == correction

    def prefix(a: str, b: str) -> int:
        return next((i for i, (left, right) in enumerate(zip(a, b, strict=False))
                     if left != right), min(len(a), len(b)))

    original_prefix = prefix(original["input"], correction["input"])
    revised_prefix = prefix(candidate["input"], revised_correction["input"])
    assert revised_prefix > original_prefix

    if original_groups:
        # A missing timestamp must never create a purported match, even when
        # several exact aliases belonged to one otherwise matching source group.
        unknown_request = copy.deepcopy(original)
        unknown_body = json.loads(unknown_request["input"])
        unknown_view = unknown_body["prepared"]["view"]
        unknown_view["journeys"][0]["facts"]["departure"]["local_iso"] = None
        unknown_request["input"] = compact(unknown_body)
        unknown_prepared = artifact.prepared.model_copy(update={"authoring_view":
            artifact.prepared.authoring_view.model_copy(update={"view": unknown_view})})
        unknown_candidate = transform(unknown_request, unknown_prepared)
        assert restore(unknown_candidate) == unknown_request
        unknown_index = json.loads(unknown_candidate["input"])["prepared"]["view"]["same_schedule"]
        first_refs = {member["ref"] for member in unknown_view["journeys"][0]["members"]}
        for ref in first_refs:
            entries = [entry for entry in unknown_index
                       if any(item["ref"] == ref for item in entry["choices"])]
            assert len(entries) == 1
            assert entries[0]["relationship"] == "schedule_unknown_singleton"
            assert [item["ref"] for item in entries[0]["choices"]] == [ref]
    return {
        "original_request_sha256": sha256(request_bytes),
        "source_artifact_sha256": sha256(source_bytes),
        "candidate_request_sha256": sha256(compact(candidate).encode()),
        "inverse_full_request_equal": True,
        "exact_reference_inventory_equal": True,
        "quoted_member_facts_match_source": len(source_members),
        "same_schedule_index_members_match_source": len(indexed_refs),
        "same_schedule_groups": len(expected_schedules),
        "unknown_timestamp_does_not_group": bool(original_groups),
        "eligible_aliases": len(source_members),
        "benchmark_aliases": len(view["benchmarks"]),
        "lead_aliases": len(view["incomplete_leads"]),
        "original_input_bytes": len(original["input"].encode()),
        "candidate_input_bytes": len(candidate["input"].encode()),
        "original_prompt_bytes": len(original["input"].encode()) + len(original["instructions"].encode()),
        "candidate_prompt_bytes": len(candidate["input"].encode()) + len(candidate["instructions"].encode()),
        "synthetic_correction_original_shared_prefix_bytes": original_prefix,
        "synthetic_correction_candidate_shared_prefix_bytes": revised_prefix,
    }


def main() -> None:
    report = {
        "method": "reversible_candidate_v1_from_saved_authoring_view",
        "limits": "Byte and prefix checks are offline; model interpretation, cache reuse, source-review quality and latency require live evidence.",
        "cases": {case: audit(case) for case in CASES},
    }
    (ROOT / "candidate-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
