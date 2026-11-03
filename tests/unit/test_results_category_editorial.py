"""C06 authoring pool is optional while selected source roles remain exact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest

from award_agent.results.category import (
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, WriterReceipt

ROOT = Path("evidence/results-stage/m2/structured/2026-10-29-category-led/runs")


class SubsetWriter:
    def __init__(self, saved: Any) -> None:
        self.saved = saved
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig,
               settings: object) -> str:
        self.requests.append(request)
        if len(self.requests) == 1:
            assert self.saved.passes[0].raw_wire is not None
            raw = self.saved.passes[0].raw_wire
            assert isinstance(raw, str)
        else:
            packet = json.loads(str(request["input"]))["packet"]
            records = packet["authoring_records"]
            cash = next(alias for alias, record in records.items()
                        if record["role"] == "benchmark")
            cash_text = next(block.text for block in self.saved.resolved.blocks
                             if block.kind == "cash_sentence")
            if packet["selection_scope"]["journey_count"]:
                landscape = packet["category_landscape"]["selected_members"]
                chosen = list(dict.fromkeys([landscape["time"][0], landscape["premium"][0]]))
                assert len(records) == 6 and len(chosen) == 2
                blocks = [
                    {"k": "p", "r": chosen[0], "n": "Shorter journey",
                     "v": "Consider this for the shorter trip."},
                    {"k": "a", "r": chosen[1], "n": "Business cabin",
                     "v": "Consider this if the business cabin matters more."},
                ]
            else:
                chosen = [alias for alias, record in records.items()
                          if record["role"] == "lead"][:2]
                assert len(records) == 5 and len(chosen) == 2
                blocks = [
                    {"k": "l", "r": chosen[0], "n": "First research lead",
                     "v": "If this program and date suit you, check its full itinerary."},
                    {"k": "l", "r": chosen[1], "n": "Alternative research lead",
                     "v": "If this date is easier, check the program's full itinerary."},
                ]
            raw = json.dumps({"blocks": [
                {"k": "t", "v": "These choices need confirmation before booking."},
                *blocks,
                {"k": "t", "v": "Quote scope and current availability are unconfirmed."},
                {"k": "b", "r": cash, "n": "Cash context", "v": cash_text},
            ]})
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        result, self.pending = self.pending, None
        return result


@pytest.mark.parametrize(("case", "pool_size", "card_kind"), [
    ("c05-scout-prior-admitted", 5, "journey_card"),
    ("c05-scout-prior-incomplete", 4, "lead_card"),
])
def test_c06_author_can_show_useful_subset_with_one_shared_note(
        case: str, pool_size: int, card_kind: Literal["journey_card", "lead_card"]) -> None:
    saved = parse_category_artifact((ROOT / case / "artifact.json").read_bytes())
    writer = SubsetWriter(saved)
    artifact = run_category_results(saved.evidence.source, saved.config, writer,
                                    profile="category-c06")
    assert artifact.passes[0].selection is not None
    selected = artifact.passes[0].selection
    assert len(selected.journey_ids or selected.incomplete_observation_ids) == pool_size
    assert len(artifact.passes) == 2
    assert artifact.validation_outcome == "clean"
    assert artifact.resolved is not None
    assert [block.kind for block in artifact.resolved.blocks].count(card_kind) == 2
    assert [block.kind for block in artifact.resolved.blocks].count("text") == 2
    assert [block.kind for block in artifact.resolved.blocks].count("cash_sentence") == 1
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved
