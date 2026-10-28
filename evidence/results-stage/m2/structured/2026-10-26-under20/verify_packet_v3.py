"""Offline audit for every source role and fact in the readable v3 packet."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from award_agent.providers.contracts import content_digest
from award_agent.results.interactive_contracts import InteractivePreparedInput
from award_agent.results.interactive_packet_v2 import build_packet as build_v2
from award_agent.results.interactive_packet_v3 import (
    _replace_refs,
    alias_map,
    reference_grammar_mode,
)
from award_agent.results.interactive_packet_v3 import (
    build_packet as build_v3,
)
from award_agent.results.interactive_wire_v3 import (
    alias_for_canonical,
    decode,
    instructions,
    schema,
)
from award_agent.results.structured_contracts import StructuredResultsArtifact

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "2026-10-25-cost-experiments/luna-retest/round-1"


def _case(name: str) -> dict[str, object]:
    artifact = StructuredResultsArtifact.model_validate_json(
        (SOURCE / name / "artifact.json").read_text(encoding="utf-8"))
    original = build_v2(artifact.prepared, artifact.evidence.source, artifact.evidence)
    actual = build_v3(artifact.prepared, artifact.evidence.source, artifact.evidence)
    expected = alias_map(original)
    assert actual["wire_aliases"] == {new: old for old, new in expected.items()}
    assert len(set(expected.values())) == len(expected)
    assert actual["outcome_mode"] == ("complete_choices" if original["journeys"]
                                      else "no_complete_journey")
    assert actual["wire_reference_grammar"] == reference_grammar_mode(actual)
    restored = deepcopy(actual)
    _replace_refs(restored, actual["wire_aliases"])
    for field in ("wire_aliases", "wire_reference_grammar", "outcome_mode"):
        restored.pop(field)
    restored["format"] = "decision-joined-v2"
    assert restored == original, "inverse reference rewrite must retain every old fact"

    prepared = InteractivePreparedInput(structured=artifact.prepared, packet=actual,
        packet_digest=content_digest(actual), source_digest=artifact.evidence.source.receipt.view_digest)
    roles = {section: [member["ref"] for group in actual[section]
                       for member in group["members"]]
             for section in ("journeys", "benchmarks", "leads")}
    generated = schema(prepared)
    options = generated["properties"]["blocks"]["items"]["anyOf"]
    role_enums = [option["properties"]["r"].get("enum")
                  for option in options if "r" in option["properties"]]
    if actual["wire_reference_grammar"] == "exact_role_enums":
        assert sum(len(values) for values in role_enums) + sum(
            len(option["properties"]["k"]["enum"]) for option in options) <= 1000
        assert all(len(values) <= 250 or sum(map(len, values)) <= 15000
                   for values in role_enums)
    else:
        assert all(values is None for values in role_enums)
    assert bool(roles["journeys"]) == any(
        option["properties"]["k"]["enum"] == ["p", "a"] for option in options)
    assert bool(roles["leads"]) == any(
        option["properties"]["k"]["enum"] == ["l"] for option in options)
    assert instructions(prepared)
    refs = artifact.prepared.references
    for role, table in (("journeys", refs.journeys), ("benchmarks", refs.cash),
                        ("leads", refs.awards | refs.cash)):
        for alias in roles[role]:
            canonical = table[actual["wire_aliases"][alias]]
            assert alias_for_canonical(prepared, canonical) == alias
    if roles["journeys"]:
        alias = roles["journeys"][0]
        doc = decode({"blocks": [{"k": "p", "r": alias, "n": "Choice", "v": "Context"}]},
                     prepared, artifact.evidence.source)
        assert doc.selection.journey_ids == (refs.journeys[actual["wire_aliases"][alias]],)
    elif roles["leads"]:
        alias = roles["leads"][0]
        doc = decode({"blocks": [{"k": "l", "r": alias, "n": "Lead", "v": "Context"}]},
                     prepared, artifact.evidence.source)
        assert doc.selection.incomplete_observation_ids
        try:
            decode({"blocks": [{"k": "p", "r": alias, "n": "Wrong", "v": "Context"}]},
                   prepared, artifact.evidence.source)
        except ValueError:
            pass
        else:
            raise AssertionError("lead cannot be selected as a journey")
    try:
        decode({"blocks": [{"k": "t", "v": "x"},
                           {"k": "l", "r": "A3@2027-01-04", "n": "Wrong", "v": "x"}]},
               prepared, artifact.evidence.source)
    except ValueError:
        pass
    else:
        raise AssertionError("fabricated readable alias must fail exactly")

    return {"journeys": len(roles["journeys"]), "benchmarks": len(roles["benchmarks"]),
            "leads": len(roles["leads"]), "all_aliases": len(expected),
            "reference_grammar": actual["wire_reference_grammar"],
            "max_alias_chars": max(map(len, expected.values())),
            "max_enum_chars": max((sum(map(len, values)) for values in role_enums
                                   if values is not None), default=0),
            "packet_bytes": len(json.dumps(actual, ensure_ascii=False).encode()),
            "inverse_source_equality": "passed"}


def _synthetic_guards() -> None:
    # A legitimate carrier or flight string can equal a short source alias.
    # Only declared reference paths may be rewritten.
    sample = {"journeys": [{"members": [{"ref": "J1", "award_ref": "A1", "cash_ref": None}],
                             "facts": {"award": {"carriers": ["A3"], "flight_number": "J1"}}}],
              "benchmarks": [], "leads": [], "ranking_hints": {"time": ["J1"]},
              "relations": {"same_award_arrival_alternatives": [],
                            "timing_match_cross_cabin": [], "lead_relevance": []}}
    _replace_refs(sample, {"J1": "journey-readable", "A1": "award-readable"})
    assert sample["journeys"][0]["facts"]["award"] == {
        "carriers": ["A3"], "flight_number": "J1"}
    assert sample["journeys"][0]["members"][0]["ref"] == "journey-readable"
    # Source date precision must survive in an identity label.
    from award_agent.results.interactive_packet_v3 import _alias
    precise = {"route": {"origin": "SFO", "destination": "BKK"},
               "date": "2027-01-01", "cabin": "business",
               "departure": {"local_iso": "2027-01-01T10:11:12.123456-08:00"}}
    assert "10:11:12.123456-08:00" in _alias("A1", precise)
    assert "date-unknown" in _alias("A1", {"route": precise["route"], "cabin": "business"})
    # Kind enum values count against the 1000-value API ceiling.
    many = {"journeys": [{"members": [{"ref": f"J{i}"} for i in range(997)]}],
            "benchmarks": [], "leads": []}
    assert reference_grammar_mode(many) == "exact_role_enums"
    many["journeys"][0]["members"].append({"ref": "J997"})
    assert reference_grammar_mode(many) == "role_only_exact_decoder"
    long = {"journeys": [{"members": [{"ref": f"J{i:03d}" + "x" * 56}
                                     for i in range(260)]}],
            "benchmarks": [], "leads": []}
    assert reference_grammar_mode(long) == "role_only_exact_decoder"


def main() -> None:
    _synthetic_guards()
    cases = {name: _case(name) for name in ("admitted", "conditional", "incomplete")}
    result = {"cases": cases, "source_preservation": "inverse equality for all saved facts; "
              "synthetic carrier/flight collisions unchanged", "role_and_alias_validation": "passed"}
    (HERE / "packet-v3-audit.json").write_text(json.dumps(result, indent=2) + "\n",
                                               encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
