"""C09 changes composition reasoning only; source and replay stay phase-bound."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from test_results_category import CategoryWriter

from award_agent.results.category import (
    _SETTINGS,
    _decode_selection,
    _focus,
    _requests,
    _style_aliases,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt
from award_agent.results.interactive_contracts import InteractiveSettings

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


def _saved(case: str) -> Any:
    return parse_category_artifact((ROOT / case / "artifact.json").read_bytes())


def _nullable_selection(saved: Any) -> str:
    raw = saved.passes[0].raw_wire
    assert raw is not None
    value = json.loads(raw)
    aliases = _style_aliases(saved.selector_prepared, saved.evidence.source)
    for style, row in value["style_audit"].items():
        if row["r"] is not None or not aliases[style]:
            row["omission_reason"] = None
    return json.dumps(value)


@pytest.mark.parametrize("case", ["c07-scout-prior-admitted",
                                      "c07-scout-prior-incomplete"])
def test_c09_same_selector_focus_schema_and_guide_as_c08(case: str) -> None:
    saved = _saved(case)
    source, selector = saved.evidence.source, saved.selector_prepared
    selection_raw = _nullable_selection(saved)
    c08 = _decode_selection(selection_raw, selector, source, "category-c08")
    c09 = _decode_selection(selection_raw, selector, source, "category-c09")
    assert c08 == c09
    selector08 = _requests(source, saved.config, selector, None, "category-c08")
    selector09 = _requests(source, saved.config, selector, None, "category-c09")
    assert selector08.request == selector09.request
    focus08 = _focus(c08, selector, source, saved.evidence, profile="category-c08")
    focus09 = _focus(c09, selector, source, saved.evidence, profile="category-c09")
    assert focus08 == focus09
    author08 = _requests(source, saved.config, selector, focus08, "category-c08")
    author09 = _requests(source, saved.config, selector, focus09, "category-c09")
    for field in ("instructions", "input", "text", "model"):
        assert author08.request[field] == author09.request[field]
    assert author08.request["reasoning"] == {"effort": "low"}
    assert author09.request["reasoning"] == {"effort": "medium"}
    assert author08.schema_digest == author09.schema_digest


class PhaseWriter(CategoryWriter):
    def __init__(self, selection_raw: str, *, duplicate_cash: bool = False) -> None:
        super().__init__()
        self.selection_raw = selection_raw
        self.duplicate_cash = duplicate_cash
        self.efforts: list[str] = []

    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: object) -> str:
        self.efforts.append(cast(InteractiveSettings, settings).reasoning_effort)
        if not self.requests:
            self.requests.append(request)
            raw = self.selection_raw
        else:
            raw = super().author(request, config, settings)
            if self.duplicate_cash and len(self.requests) == 2:
                document = json.loads(raw)
                cash = next(block["v"] for block in document["blocks"]
                            if block["k"] == "b")
                document["blocks"].insert(-1, {"k": "t", "v": cash})
                raw = json.dumps(document)
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
        return raw


def test_c09_phase_settings_and_correction_remain_low() -> None:
    saved = _saved("c07-scout-prior-admitted")
    writer = PhaseWriter(_nullable_selection(saved), duplicate_cash=True)
    artifact = run_category_results(saved.evidence.source, saved.config, writer,
                                    profile="category-c09")
    assert writer.efforts == ["low", "medium", "low"]
    assert [item.request["reasoning"] for item in artifact.passes] == [
        {"effort": "low"}, {"effort": "medium"}, {"effort": "low"}]
    assert artifact.selector_settings == _SETTINGS
    assert artifact.composer_settings.reasoning_effort == "medium"
    assert artifact.correction_settings == _SETTINGS
    assert len(artifact.passes) == 3
    assert "duplicate_cash_sentence_in_prose" in {
        row.code for row in artifact.passes[1].findings}
    assert artifact.validation_outcome == "clean"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
    tampered = artifact.model_copy(update={"composer_settings": _SETTINGS})
    with pytest.raises(ValueError, match="profile/settings differ"):
        replay_category_results(tampered)
    tampered_correction = artifact.model_copy(update={
        "correction_settings": InteractiveSettings(reasoning_effort="medium",
                                                   service_tier="fast")})
    with pytest.raises(ValueError, match="profile/settings differ"):
        replay_category_results(tampered_correction)
