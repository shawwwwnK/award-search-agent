"""Offline inverse and all-member source audit of the second candidate input."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import candidate as v1
import candidate_v2 as v2

from award_agent.results.structured_contracts import StructuredResultsArtifact

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "2026-10-25-cost-experiments/luna-retest/round-1"
CASES = ("admitted", "conditional", "incomplete")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _components(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {member["ref"]: group["facts"] for group in view["components"]
            for member in group["members"]}


def audit(case: str) -> dict[str, Any]:
    source = SOURCE / case
    raw_request = (source / "01-request.json").read_bytes()
    raw_artifact = (source / "artifact.json").read_bytes()
    request = json.loads(raw_request)
    artifact = StructuredResultsArtifact.model_validate_json(raw_artifact)
    original_body = json.loads(request["input"])
    original_view = original_body["prepared"]["view"]
    first = v1.transform(request, artifact.prepared)
    second = v2.transform(request, artifact.prepared)
    assert v2.restore(second) == request
    assert v1.inventories(json.loads(second["input"])["prepared"]["view"]) == \
        v1.inventories(original_view)
    assert second["instructions"] == first["instructions"] + v2.GUIDE
    assert second["model"] == request["model"]
    assert second["text"] == request["text"]
    first_view = json.loads(first["input"])["prepared"]["view"]
    second_view = json.loads(second["input"])["prepared"]["view"]
    assert first_view["same_schedule"] == second_view["same_schedule"]
    assert first_view["journey_fact_catalog"] == second_view["journey_fact_catalog"]
    assert first_view["incomplete_leads"] == second_view["incomplete_leads"]
    assert first_view["benchmarks"] == second_view["benchmarks"]
    assert first_view["components"] == second_view["components"]
    component_by_ref = _components(original_view)
    checked = 0
    known_dates = 0
    known_travelers = 0
    unknown_travelers = 0
    for source_group, revised_group, prior_group in zip(
        original_view["journeys"], second_view["journeys"], first_view["journeys"], strict=True
    ):
        facts = source_group["facts"]
        expected_reasons = [{key: reason[key] for key in ("code", "state", "detail")}
                            for reason in facts["reasons"]
                            if reason["code"] in v2.TRAVELER_REASON_CODES]
        assert len(source_group["members"]) == len(revised_group["members"])
        for source_member, revised, prior in zip(source_group["members"],
                                                 revised_group["members"],
                                                 prior_group["members"], strict=True):
            assert revised["ref"] == source_member["ref"] == prior["ref"]
            choice = revised["choice"]
            first_choice = prior["choice"]
            assert choice["identity"] == {field: facts[field] for field in v2.IDENTITY_FIELDS}
            assert choice["traveler_seat_assessment"] == expected_reasons
            award = component_by_ref[source_member["award"]]
            assert choice["award_quote"]["carriers"] == award["carriers"]
            assert choice["award_quote"]["cabin"] == award["cabin"]
            assert {k: value for k, value in choice.items()
                    if k not in {"identity", "traveler_seat_assessment"}} == {
                        **first_choice,
                        "award_quote": {**first_choice["award_quote"],
                                        "carriers": award["carriers"], "cabin": award["cabin"]},
                    }
            assert {k: value for k, value in revised.items() if k != "choice"} == \
                {k: value for k, value in prior.items() if k != "choice"}
            checked += 1
            known_dates += facts["departure"]["local_iso"] is not None and \
                facts["arrival"]["local_iso"] is not None
            known_travelers += any(reason["code"] == "award_travelers_supported" and
                                   reason["state"] == "passed" for reason in expected_reasons)
            unknown_travelers += any(reason["code"] == "award_travelers_unknown" and
                                     reason["state"] == "unknown" for reason in expected_reasons)
    assert checked == len(v1.inventories(original_view)["journeys"])
    assert original_body["prepared"]["view"] == artifact.prepared.authoring_view.view
    correction_body = json.loads(request["input"])
    correction_body["feedback"] = [{"code": "diagnostic"}]
    correction_body["previous_document"] = {"diagnostic": True}
    correction_request = dict(request, input=v1.compact(correction_body))
    assert v2.restore(v2.transform(correction_request, artifact.prepared)) == correction_request
    return {
        "source_request_sha256": digest(raw_request),
        "source_artifact_sha256": digest(raw_artifact),
        "candidate_v1_request_sha256": digest(v1.compact(first).encode()),
        "candidate_v2_request_sha256": digest(v1.compact(second).encode()),
        "inverse_full_request_equal": True,
        "inverse_synthetic_correction_equal": True,
        "unchanged_reference_inventory": True,
        "exact_identity_quote_and_assessment_joins": checked,
        "members_with_dated_endpoints": known_dates,
        "members_with_supported_traveler_reason": known_travelers,
        "members_with_unknown_traveler_reason": unknown_travelers,
        "benchmark_aliases": len(original_view["benchmarks"]),
        "lead_aliases": len(original_view["incomplete_leads"]),
        "candidate_v1_prompt_bytes": len(first["input"].encode()) + len(first["instructions"].encode()),
        "candidate_v2_prompt_bytes": len(second["input"].encode()) + len(second["instructions"].encode()),
        "original_prompt_bytes": len(request["input"].encode()) + len(request["instructions"].encode()),
    }


def main() -> None:
    result = {
        "method": "reversible_candidate_v2_exact_member_locality",
        "scope": "Offline saved-source and request audit; no live count, interpretation or latency claim.",
        "cases": {case: audit(case) for case in CASES},
    }
    (ROOT / "candidate-v2-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
