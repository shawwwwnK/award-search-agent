"""Audit the v4 traveler presentation against its exact v3 source packet."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from award_agent.providers.contracts import content_digest
from award_agent.results.interactive_contracts import InteractivePreparedInput
from award_agent.results.interactive_packet_v3 import _replace_refs
from award_agent.results.interactive_packet_v3 import build_packet as build_v3
from award_agent.results.interactive_packet_v4 import (
    build_packet as build_v4,
)
from award_agent.results.interactive_packet_v4 import (
    present_v3_packet,
)
from award_agent.results.interactive_wire_v4 import (
    alias_for_canonical,
    decode,
    instructions,
    schema,
)
from award_agent.results.structured_contracts import StructuredResultsArtifact

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def _audit(name: str) -> dict[str, object]:
    artifact = StructuredResultsArtifact.model_validate_json(
        (SOURCE / name / "artifact.json").read_text(encoding="utf-8"))
    before = build_v3(artifact.prepared, artifact.evidence.source, artifact.evidence)
    after = build_v4(artifact.prepared, artifact.evidence.source, artifact.evidence)
    assert after == present_v3_packet(before)
    assert set(after["wire_aliases"].values()) == set(before["wire_aliases"].values())
    restored = deepcopy(after)
    old_by_short = {short: alias for alias, short in before["wire_aliases"].items()}
    _replace_refs(restored, {new: old_by_short[short] for new, short in
                            after["wire_aliases"].items()})
    restored["wire_aliases"] = before["wire_aliases"]
    restored["wire_reference_grammar"] = before["wire_reference_grammar"]
    restored["format"] = "decision-joined-v3"
    restored["legend"].pop("award_only")
    renamed = 0
    for group in restored["journeys"]:
        if group["facts"]["topology"] == "award_only":
            group["facts"]["topology"] = "direct_award"
            renamed += len(group["members"])
    assert restored == before, "v4 must be exactly reversible to all v3 facts"
    expected_renamed = sum(len(group["members"]) for group in before["journeys"]
                           if group["facts"]["topology"] == "direct_award")
    assert renamed == expected_renamed
    prepared = InteractivePreparedInput(structured=artifact.prepared, packet=after,
        packet_digest=content_digest(after), source_digest=artifact.evidence.source.receipt.view_digest)
    actual_schema = schema(prepared)
    assert actual_schema["properties"]["blocks"]["items"]["anyOf"]
    brief = instructions(prepared)
    assert "award_only means one award itinerary" in brief
    assert "direct cash context" not in brief
    assert "currently bookable" in brief
    assert "not directly comparable" in brief
    assert "Never borrow a neighboring candidate's time" in brief
    roles = {section: [member["ref"] for group in after[section]
                       for member in group["members"]]
             for section in ("journeys", "benchmarks", "leads")}
    assert sum(map(len, roles.values())) <= len(after["wire_aliases"])
    for group in after["journeys"]:
        arrival = group["facts"].get("arrival")
        if isinstance(arrival, dict) and isinstance(arrival.get("local_iso"), str):
            expected_local = arrival["local_iso"][:16]
            assert all(member["ref"].split(">")[-1].startswith(expected_local)
                       for member in group["members"])
    old_refs = artifact.prepared.references
    for alias in roles["journeys"]:
        canonical = old_refs.journeys[after["wire_aliases"][alias]]
        assert alias_for_canonical(prepared, canonical) == alias
    if roles["journeys"]:
        alias = roles["journeys"][0]
        document = decode({"blocks": [{"k": "p", "r": alias,
                                         "n": "Choice", "v": "Context"}]},
                          prepared, artifact.evidence.source)
        assert document.selection.journey_ids
    elif roles["leads"]:
        alias = roles["leads"][0]
        document = decode({"blocks": [{"k": "l", "r": alias,
                                         "n": "Lead", "v": "Context"}]},
                          prepared, artifact.evidence.source)
        assert document.selection.incomplete_observation_ids
        try:
            decode({"blocks": [{"k": "p", "r": alias,
                                  "n": "Wrong", "v": "Context"}]},
                   prepared, artifact.evidence.source)
        except ValueError:
            pass
        else:
            raise AssertionError("no-complete source cannot select a journey")
    return {"journeys": len(roles["journeys"]),
            "award_only_journeys": renamed,
            "benchmarks": len(roles["benchmarks"]),
            "leads": len(roles["leads"]),
            "reference_grammar": after["wire_reference_grammar"],
            "max_journey_alias_chars": max(map(len, roles["journeys"]), default=0),
            "journey_enum_chars": sum(map(len, roles["journeys"])),
            "inverse_equality": "passed", "wire_roles": "passed"}


def main() -> None:
    results = {name: _audit(name) for name in ("admitted", "conditional", "incomplete")}
    output = {"cases": results,
              "source_preservation": "all v3 packet facts recoverable from v4; "
              "direct_award presented as award_only and journey aliases gain "
              "source-local arrival identity", "wire_binding": "passed"}
    (HERE / "packet-v4-audit.json").write_text(json.dumps(output, indent=2) + "\n",
                                               encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
