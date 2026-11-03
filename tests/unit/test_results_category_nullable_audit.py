"""C08 schema aligns represented and unavailable category reasons with decoder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator
from test_results_category import CategoryWriter

from award_agent.results.category import (
    _decode_selection,
    _focus,
    _selection_schema,
    _style_aliases,
    _writer_input,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")
CASES = ("c07-scout-prior-admitted", "c07-scout-prior-conditional",
         "c07-scout-prior-incomplete")


def _saved(case: str) -> Any:
    return parse_category_artifact((ROOT / case / "artifact.json").read_bytes())


def _prospective(raw: str, aliases: dict[str, list[str]]) -> dict[str, Any]:
    value = json.loads(raw)
    for style, row in value["style_audit"].items():
        if row["r"] is not None or not aliases[style]:
            row["omission_reason"] = None
    return cast(dict[str, Any], value)


@pytest.mark.parametrize("case", CASES)
def test_c08_schema_rejects_actual_c07_wires_and_accepts_nullable_equivalent(
        case: str) -> None:
    saved = _saved(case)
    source = saved.evidence.source
    selector = saved.selector_prepared
    raw = saved.passes[0].raw_wire
    assert raw is not None
    original = json.loads(raw)
    old_schema = _selection_schema(selector, source, "category-c07")
    new_schema = _selection_schema(selector, source, "category-c08")
    assert Draft202012Validator(old_schema).is_valid(original)
    assert not Draft202012Validator(new_schema).is_valid(original)
    assert saved.passes[0].outcome == "generation_error"
    assert replay_category_results(saved) is None
    with pytest.raises(ValueError, match="omission requires"):
        _decode_selection(raw, selector, source, "category-c07")
    prospective = _prospective(raw, _style_aliases(selector, source))
    assert Draft202012Validator(new_schema).is_valid(prospective)
    selected = _decode_selection(json.dumps(prospective), selector, source,
                                 "category-c08")
    assert selected.benchmark_observation_id is not None
    if case.endswith("incomplete"):
        assert not selected.journey_ids
        assert len(selected.incomplete_observation_ids) == 6
        focus = _focus(selected, selector, source, saved.evidence,
                       profile="category-c08")
        records = cast(dict[str, Any], _writer_input(
            focus, profile="category-c08")["authoring_records"])
        assert len(records) == 7
    else:
        assert len(selected.journey_ids) >= 2


def test_c08_available_witness_and_omission_branches_keep_decoder_semantics() -> None:
    saved = _saved("c07-scout-prior-admitted")
    source, selector = saved.evidence.source, saved.selector_prepared
    raw = saved.passes[0].raw_wire
    assert raw is not None
    aliases = _style_aliases(selector, source)
    valid = _prospective(raw, aliases)
    schema = _selection_schema(selector, source, "category-c08")
    assert Draft202012Validator(schema).is_valid(valid)
    witness_bad = json.loads(json.dumps(valid))
    witness_bad["style_audit"]["premium"]["omission_reason"] = ""
    assert not Draft202012Validator(schema).is_valid(witness_bad)
    absent_bad = json.loads(json.dumps(valid))
    absent_bad["style_audit"]["cost"]["omission_reason"] = "No cost category"
    assert not Draft202012Validator(schema).is_valid(absent_bad)
    omission = json.loads(json.dumps(valid))
    omission["style_audit"]["premium"] = {
        "r": None, "omission_reason": "No distinct premium choice for this brief"}
    assert Draft202012Validator(schema).is_valid(omission)
    omission["style_audit"]["premium"]["omission_reason"] = "   "
    assert Draft202012Validator(schema).is_valid(omission)
    with pytest.raises(ValueError, match="omission requires"):
        _decode_selection(json.dumps(omission), selector, source, "category-c08")


def test_c08_completed_two_pass_run_replays() -> None:
    saved = _saved("c07-scout-prior-admitted")
    raw = saved.passes[0].raw_wire
    assert raw is not None
    selection_raw = json.dumps(_prospective(raw,
        _style_aliases(saved.selector_prepared, saved.evidence.source)))

    class NullableWriter(CategoryWriter):
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            if self.requests:
                return super().author(request, config, settings)
            self.requests.append(request)
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text",
                                                     "text": selection_raw}]}]}))
            return selection_raw

    artifact = run_category_results(saved.evidence.source, saved.config,
                                    NullableWriter(), profile="category-c08")
    assert artifact.validation_outcome == "clean"
    assert artifact.resolved is not None
    assert len(artifact.passes) == 2
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
