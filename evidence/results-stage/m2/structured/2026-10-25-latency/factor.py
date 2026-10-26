"""Build losslessly factored, offline Results writer requests from saved Luna inputs.

This is experiment material only. It does not change the Results runtime.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "2026-10-25-cost-experiments" / "luna-retest" / "round-1"
CASES = ("admitted", "conditional", "incomplete")
FACT_FIELDS = ("reasons", "cost", "assessments", "positioning_reason")
ENCODING_GUIDE = (
    "\n\nJourney fact catalog: in each journey group, reasons_ref, cost_ref, "
    "assessments_ref and positioning_reason_ref are zero-based indexes into the "
    "same-named arrays in prepared.view.journey_fact_catalog. Read each indexed "
    "value as that group's full fact. Journey members and J references remain "
    "individual exact choices.\n"
)


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def aliases(view: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "journeys": sorted(member["ref"] for group in view["journeys"]
                           for member in group["members"]),
        "components": sorted(member["ref"] for group in view["components"]
                             for member in group["members"]),
        "leads": sorted(lead["ref"] for lead in view["incomplete_leads"]),
        "benchmarks": sorted(view["benchmarks"]),
    }


def factor(request: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(request)
    body = json.loads(result["input"])
    groups = body["prepared"]["view"]["journeys"]
    if not groups:
        return result

    catalog: dict[str, list[Any]] = {}
    for field in FACT_FIELDS:
        seen: dict[str, int] = {}
        values: list[Any] = []
        for group in groups:
            facts = group["facts"]
            value = facts.pop(field)
            serialized = compact(value)
            if serialized not in seen:
                seen[serialized] = len(values)
                values.append(value)
            facts[f"{field}_ref"] = seen[serialized]
        catalog[field] = values
    body["prepared"]["view"]["journey_fact_catalog"] = catalog
    result["input"] = compact(body)
    result["instructions"] += ENCODING_GUIDE
    return result


def restore(request: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(request)
    body = json.loads(result["input"])
    view = body["prepared"]["view"]
    catalog = view.pop("journey_fact_catalog", None)
    if catalog is None:
        return result
    for group in view["journeys"]:
        facts = group["facts"]
        for field in FACT_FIELDS:
            index = facts.pop(f"{field}_ref")
            facts[field] = copy.deepcopy(catalog[field][index])
    result["input"] = compact(body)
    assert result["instructions"].endswith(ENCODING_GUIDE)
    result["instructions"] = result["instructions"][:-len(ENCODING_GUIDE)]
    return result


def main() -> None:
    audit: dict[str, Any] = {"method": "journey_fact_catalog_v1", "cases": {}}
    for case in CASES:
        source_path = SOURCE / case / "01-request.json"
        source_bytes = source_path.read_bytes()
        original = json.loads(source_bytes)
        original_body = json.loads(original["input"])
        assert original["input"] == compact(original_body)

        factored = factor(original)
        factored_body = json.loads(factored["input"])
        restored = restore(factored)
        assert restored == original, f"request did not round-trip: {case}"
        assert restored["input"] == original["input"]
        before_aliases = aliases(original_body["prepared"]["view"])
        after_aliases = aliases(factored_body["prepared"]["view"])
        assert before_aliases == after_aliases, f"aliases changed: {case}"

        output_path = HERE / f"{case}-factored-request.json"
        output_bytes = (json.dumps(factored, indent=2, ensure_ascii=False) + "\n").encode()
        output_path.write_bytes(output_bytes)
        original_input_bytes = len(original["input"].encode())
        factored_input_bytes = len(factored["input"].encode())
        original_prompt_bytes = original_input_bytes + len(original["instructions"].encode())
        factored_prompt_bytes = factored_input_bytes + len(factored["instructions"].encode())
        audit["cases"][case] = {
            "source": str(source_path.relative_to(HERE.parent)),
            "source_sha256": sha256(source_bytes),
            "output": output_path.name,
            "output_sha256": sha256(output_bytes),
            "original_input_bytes": original_input_bytes,
            "factored_input_bytes": factored_input_bytes,
            "input_bytes_saved": original_input_bytes - factored_input_bytes,
            "original_prompt_bytes": original_prompt_bytes,
            "factored_prompt_bytes": factored_prompt_bytes,
            "prompt_bytes_saved": original_prompt_bytes - factored_prompt_bytes,
            "journey_groups": len(original_body["prepared"]["view"]["journeys"]),
            "catalog_distinct_values": {
                field: len(factored_body["prepared"]["view"].get(
                    "journey_fact_catalog", {}).get(field, [])) for field in FACT_FIELDS
            },
            "alias_counts": {key: len(value) for key, value in before_aliases.items()},
            "full_request_round_trip_equal": True,
            "alias_inventory_equal": True,
        }
    (HERE / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    for case, entry in audit["cases"].items():
        print(case, entry["original_input_bytes"], entry["factored_input_bytes"],
              entry["input_bytes_saved"], entry["alias_counts"])


if __name__ == "__main__":
    main()
