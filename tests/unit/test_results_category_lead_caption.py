"""C10 anchors lead captions in the schema without changing the wire."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from award_agent.results.category import (
    _PROFILE_INSTRUCTIONS,
    _document_schema,
    _requests,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((ROOT / case / "artifact.json").read_bytes())


def _lead_branch(schema: dict[str, object]) -> dict[str, Any]:
    branches = cast(dict[str, Any], schema)["properties"]["blocks"]["items"]["anyOf"]
    return next(branch for branch in branches
                if branch["properties"]["k"]["enum"] == ["l"])


@pytest.mark.parametrize("case", ["c09-scout-prior-conditional",
                                      "c09-scout-prior-incomplete"])
def test_c10_only_lead_v_schema_description_changes(case: str) -> None:
    saved = _saved(case)
    focus = saved.focus_prepared
    assert focus is not None
    old = _document_schema(focus, "category-c09")
    new = cast(dict[str, Any], _document_schema(focus, "category-c10"))
    assert _document_schema(focus, "category-c09") == old
    description = _lead_branch(new)["properties"]["v"]["description"]
    assert "conditional reason to check" in description
    assert "source card shows research status" in description
    copied = deepcopy(new)
    del _lead_branch(copied)["properties"]["v"]["description"]
    assert copied == old
    for branch in new["properties"]["blocks"]["items"]["anyOf"]:
        if branch["properties"]["k"]["enum"] != ["l"]:
            assert "description" not in branch["properties"]["v"]
    raw = saved.passes[1].raw_wire
    assert raw is not None
    assert Draft202012Validator(old).is_valid(json.loads(raw))
    assert Draft202012Validator(new).is_valid(json.loads(raw))
    old_request = _requests(saved.evidence.source, saved.config,
                            saved.selector_prepared, focus, "category-c09")
    new_request = _requests(saved.evidence.source, saved.config,
                            saved.selector_prepared, focus, "category-c10")
    assert old_request.request["input"] == new_request.request["input"]
    assert old_request.request["reasoning"] == new_request.request["reasoning"] == {
        "effort": "medium"}
    assert _PROFILE_INSTRUCTIONS["category-c09"][0] == _PROFILE_INSTRUCTIONS["category-c10"][0]
    assert "For every k=l lead" in _PROFILE_INSTRUCTIONS["category-c10"][1]
    assert "all leads are date-only" not in _PROFILE_INSTRUCTIONS["category-c10"][1]


def test_c10_saved_mixed_answer_lead_text_is_verbatim_and_replays() -> None:
    saved = _saved("c09-scout-prior-conditional")
    raw_wires = [item.raw_wire for item in saved.passes]
    assert len(raw_wires) == 2 and all(isinstance(raw, str) for raw in raw_wires)

    class SavedWriter:
        def __init__(self) -> None:
            self.calls = 0
            self.pending: WriterReceipt | None = None

        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: InteractiveSettings) -> str:
            raw = raw_wires[self.calls]
            assert isinstance(raw, str)
            self.calls += 1
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

        def take_receipt(self) -> WriterReceipt | None:
            result, self.pending = self.pending, None
            return result

    writer = SavedWriter()
    artifact = run_category_results(saved.evidence.source, saved.config, writer,
                                    profile="category-c10")
    assert writer.calls == 2
    assert artifact.validation_outcome == saved.validation_outcome
    assert artifact.resolved == saved.resolved
    assert artifact.passes[1].document == saved.passes[1].document
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_c10_complete_only_schema_has_no_lead_branch_and_still_authors() -> None:
    saved = _saved("c09-scout-prior-admitted")
    focus = saved.focus_prepared
    assert focus is not None
    old = _document_schema(focus, "category-c09")
    new = cast(dict[str, Any], _document_schema(focus, "category-c10"))
    assert old == new
    assert all(branch["properties"]["k"]["enum"] != ["l"]
               for branch in new["properties"]["blocks"]["items"]["anyOf"])
    raw = saved.passes[1].raw_wire
    assert raw is not None
    assert Draft202012Validator(new).is_valid(json.loads(raw))
    request = _requests(saved.evidence.source, saved.config,
                        saved.selector_prepared, focus, "category-c10")
    assert request.request["reasoning"] == {"effort": "medium"}
