"""Category-led selection, source cards, cash sentence and exact replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from award_agent.cli import results as results_cli
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.category import (
    _selection_format,
    category_profiles,
    parse_category_artifact,
    replay_category_results,
    run_category_results,
)
from award_agent.results.contracts import ResultsConfig, ResultsWriterError, WriterReceipt
from award_agent.results.focused import prepare_focused_selector
from award_agent.results.focused_selector_records import selector_packet
from award_agent.results.presentation import resolve_workspace

SOURCE = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q119/evidence.json")
PARTIAL = Path("evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q121/evidence.json")


def _source() -> SolutionProjection:
    return SolutionProjection.model_validate(json.loads(SOURCE.read_text())["source"])


def _config() -> ResultsConfig:
    return ResultsConfig.model_validate_json(Path("data/results/fast-default.json").read_text())


class CategoryWriter:
    def __init__(self, *, duplicate: bool = False, cash_paragraph: bool = False,
                 repeat_cash: bool = False,
                 omit_premium: bool = False, drop_premium_card: bool = False,
                 fail_composition: bool = False) -> None:
        self.duplicate = duplicate
        self.cash_paragraph = cash_paragraph
        self.repeat_cash = repeat_cash
        self.omit_premium = omit_premium
        self.drop_premium_card = drop_premium_card
        self.fail_composition = fail_composition
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
        self.requests.append(request)
        packet = json.loads(str(request["input"]))["packet"]
        if len(self.requests) == 1:
            hints = packet["ranking_hints"]
            choices = [{"k": "j", "r": hints["time"][0]},
                       {"k": "b", "r": packet["benchmark_refs"][0]}]
            if not self.omit_premium:
                choices.insert(1, {"k": "j", "r": hints["premium"][0]})
            result = {"choices": choices,
                      "omitted": ([{"style": "premium", "reason": "No materially useful premium choice"}]
                                  if self.omit_premium else [])}
        else:
            if self.fail_composition:
                raise ResultsWriterError("incomplete", "API returned an incomplete answer")
            assert packet["category_landscape"]["available_counts"]["premium"] > 0
            rows = cast(dict[str, Any], request["text"])["format"]["schema"]["properties"]["blocks"]["items"]["anyOf"]
            journeys = next(row for row in rows if row["properties"]["k"]["enum"] == ["p", "a"])["properties"]["r"]["enum"]
            cash = next(row for row in rows if row["properties"]["k"]["enum"] == ["b"])["properties"]["r"]["enum"][0]
            blocks = [{"k": "t", "v": "For a shorter journey, start with the economy option."},
                      {"k": "p", "r": journeys[0], "n": "Shorter journey",
                       "v": "A quicker economy trip; choose the other option for business class."}]
            if len(journeys) > 1 and not self.drop_premium_card:
                blocks.append({"k": "a", "r": journeys[1], "n": "Business cabin",
                               "v": "Business class with a longer journey and separate flight."})
            if self.duplicate:
                blocks.append(blocks[1])
            blocks.append({"k": "b", "r": cash, "n": "Cash comparison",
                           "v": ("A cash itinerary was quoted at USD 440, with its total unconfirmed. "
                                 "Verify the fare." if self.cash_paragraph else
                                 "A cash itinerary was quoted at USD 440, with its total unconfirmed.")})
            if self.repeat_cash:
                blocks.append(blocks[-1])
            result = {"blocks": blocks}
        raw = json.dumps(result)
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        result, self.pending = self.pending, None
        return result


def test_category_cards_cash_sentence_and_replay() -> None:
    writer = CategoryWriter()
    artifact = run_category_results(_source(), _config(), writer)
    assert [part.outcome for part in artifact.passes] == ["recoverable", "recoverable"]
    assert artifact.validation_outcome == "clean"
    assert artifact.resolved is not None
    assert [part.kind for part in artifact.resolved.blocks] == [
        "text", "journey_card", "journey_card", "cash_sentence"]
    assert all(part.award_component is not None and part.ranking_assessments
               for part in artifact.resolved.blocks if part.kind == "journey_card")
    assert artifact.resolved.blocks[-1].benchmark_component is not None
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


@pytest.mark.parametrize(("duplicate", "cash_paragraph", "finding"), [
    (True, False, "duplicate_journey_card"),
    (False, True, "cash_not_one_sentence"),
])
def test_category_controls_trigger_repair(duplicate: bool, cash_paragraph: bool,
                                          finding: str) -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter(
        duplicate=duplicate, cash_paragraph=cash_paragraph))
    assert len(artifact.passes) == 3
    assert finding in {row.code for row in artifact.passes[1].findings}
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_audited_omission_is_visible_and_not_writer_fact() -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter(omit_premium=True))
    assert artifact.resolved is not None
    assert artifact.selection_findings[0].outcome == "unchecked"
    assert artifact.selection_findings[0] in artifact.resolved.findings
    assert "No materially useful premium choice" not in str(artifact.passes[1].request["input"])
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_selected_category_requires_a_visible_card() -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter(drop_premium_card=True))
    assert len(artifact.passes) == 3
    assert "selected_category_not_shown" in {row.code for row in artifact.passes[1].findings}
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_cash_comparison_cannot_be_repeated() -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter(repeat_cash=True))
    assert "repeated_cash_sentence" in {row.code for row in artifact.passes[1].findings}
    assert len(artifact.passes) == 3


def test_incomplete_research_leads_are_cards_without_styles() -> None:
    projection = SolutionProjection.model_validate(json.loads(PARTIAL.read_text())["source"])

    class LeadWriter(CategoryWriter):
        def author(self, request: dict[str, object], config: ResultsConfig, settings: object) -> str:
            self.requests.append(request)
            packet = json.loads(str(request["input"]))["packet"]
            if len(self.requests) == 1:
                aliases = [row[0] for row in packet["lead_rows"][:2]]
                result = {"choices": [{"k": "l", "r": alias} for alias in aliases] +
                          [{"k": "b", "r": packet["benchmark_refs"][0]}],
                          "omitted": []}
            else:
                rows = cast(dict[str, Any], request["text"])["format"]["schema"]["properties"]["blocks"]["items"]["anyOf"]
                leads = next(row for row in rows if row["properties"]["k"]["enum"] == ["l"])["properties"]["r"]["enum"]
                cash = next(row for row in rows if row["properties"]["k"]["enum"] == ["b"])["properties"]["r"]["enum"][0]
                result = {"blocks": [{"k": "t", "v": "No complete award journey is available to recommend."},
                                     *[{"k": "l", "r": alias, "n": "Research lead",
                                        "v": "Check this program for a complete schedule and current availability."}
                                       for alias in leads],
                                     {"k": "b", "r": cash, "n": "Cash context",
                                      "v": "A separate full-cash journey has a reported quote with an unconfirmed total."}]}
            raw = json.dumps(result)
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

    artifact = run_category_results(projection, _config(), LeadWriter())
    assert artifact.resolved is not None
    assert artifact.resolved.selected_journey_ids == ()
    assert [part.kind for part in artifact.resolved.blocks] == [
        "text", "lead_card", "lead_card", "cash_sentence"]
    assert all(part.lead_component is not None for part in artifact.resolved.blocks[1:3])
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_incomplete_api_answer_is_explicit_and_replayable() -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter(fail_composition=True))
    assert artifact.generation_outcome == "generation_error"
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.passes[-1].failure_subtype == "incomplete"
    assert artifact.resolved is None
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) is None


def test_replay_rejects_changed_card_source() -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter())
    raw = artifact.model_dump(mode="json")
    raw["resolved"]["blocks"][1]["text"] = "Altered recommendation"
    with pytest.raises(ValueError, match="outcome differs"):
        replay_category_results(parse_category_artifact(json.dumps(raw)))


@pytest.mark.parametrize("part", ["config", "selector_prepared", "request"])
def test_replay_rejects_tampered_inputs(part: str) -> None:
    artifact = run_category_results(_source(), _config(), CategoryWriter())
    raw = artifact.model_dump(mode="json")
    if part == "config":
        raw["config"]["authoring_guidance"] = "Changed"
    elif part == "selector_prepared":
        raw["selector_prepared"]["packet"]["selection_format"] = "roles-v19"
    else:
        raw["passes"][1]["request"]["instructions"] = "Changed"
    with pytest.raises(ValueError):
        replay_category_results(parse_category_artifact(json.dumps(raw)))


def test_category_cli_measure_and_replay(tmp_path: Path) -> None:
    source = tmp_path / "projection.json"
    config = tmp_path / "config.json"
    measured = tmp_path / "measured.json"
    saved = tmp_path / "artifact.json"
    replayed = tmp_path / "answer.json"
    source.write_text(_source().model_dump_json())
    config.write_text(_config().model_dump_json())
    assert results_cli.main(["measure", "--projection", str(source), "--config",
                             str(config), "--output", str(measured),
                             "--category-profile", "category-c02"]) == 0
    assert json.loads(measured.read_text())["profile"] == "category-c02"
    artifact = run_category_results(_source(), _config(), CategoryWriter())
    saved.write_text(artifact.model_dump_json())
    assert results_cli.main(["replay", "--artifact", str(saved),
                             "--output", str(replayed)]) == 0
    assert artifact.resolved is not None
    assert json.loads(replayed.read_text()) == artifact.resolved.model_dump(mode="json")


def test_category_cli_author_uses_owned_zero_retry_client(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    import openai

    from award_agent.results import category as category_module
    from award_agent.results import interactive_adapter

    source = tmp_path / "projection.json"
    config = tmp_path / "config.json"
    output = tmp_path / "artifact.json"
    source.write_text(_source().model_dump_json())
    config.write_text(_config().model_dump_json())
    expected = run_category_results(_source(), _config(), CategoryWriter(),
                                    profile="category-c02")
    clients: list[Client] = []

    class Client:
        def __init__(self, *, max_retries: int, timeout: float) -> None:
            assert max_retries == 0 and timeout == _config().timeout_seconds
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(openai, "OpenAI", Client)
    monkeypatch.setattr(interactive_adapter, "OpenAIInteractiveResultsWriter", lambda client: object())
    monkeypatch.setattr(results_cli, "OpenAIResultsInputMeasurer", lambda client: object())

    def fake_run(projection: SolutionProjection, selected_config: ResultsConfig,
                 writer: object, input_measurer: object, *, profile: str) -> object:
        assert projection == _source() and selected_config == _config()
        assert profile == "category-c02"
        return expected

    monkeypatch.setattr(category_module, "run_category_results", fake_run)
    assert results_cli.main(["author", "--projection", str(source), "--config",
                             str(config), "--output", str(output), "--live",
                             "--category-profile", "category-c02"]) == 0
    assert clients and all(client.closed for client in clients)
    assert parse_category_artifact(output.read_bytes()) == expected


def test_category_c02_preserves_c01_exact_requests() -> None:
    source, config = _source(), _config()
    old = run_category_results(source, config, CategoryWriter(), profile="category-c01")
    new = run_category_results(source, config, CategoryWriter(), profile="category-c02")
    assert old.passes[0].request != new.passes[0].request
    assert old.passes[1].request != new.passes[1].request
    assert replay_category_results(parse_category_artifact(old.model_dump_json())) == old.resolved
    assert replay_category_results(parse_category_artifact(new.model_dump_json())) == new.resolved


def test_category_c03_groups_incomplete_leads_without_legacy_reference_cap() -> None:
    projection = SolutionProjection.model_validate(json.loads(PARTIAL.read_text())["source"])
    baseline = selector_packet(prepare_focused_selector(projection, _config(),
        resolve_workspace(projection), selection_format="roles-v20"))
    flat_leads = {row[0] for row in cast(list[list[str]], baseline["lead_rows"])}

    class GroupedLeadWriter(CategoryWriter):
        def author(self, request: dict[str, object], config: ResultsConfig,
                   settings: object) -> str:
            self.requests.append(request)
            packet = json.loads(str(request["input"]))["packet"]
            if len(self.requests) == 1:
                assert packet["selection_format"] == "roles-v30"
                grouped = [member["record"]["A_or_C"]
                           for group in packet["lead_program_groups"]
                           for member in group["members"]]
                assert len(grouped) == len(set(grouped)) == len(flat_leads)
                assert set(grouped) == flat_leads
                assert len(grouped) >= 3
                result = {"choices": [{"k": "l", "r": alias} for alias in grouped[:3]] +
                          [{"k": "b", "r": packet["benchmark_refs"][0]}], "omitted": []}
            else:
                assert packet["category_landscape"]["available_counts"] == {
                    "time": 0, "cost": 0, "premium": 0}
                rows = cast(dict[str, Any], request["text"])["format"]["schema"]["properties"]["blocks"]["items"]["anyOf"]
                leads = next(row for row in rows if row["properties"]["k"]["enum"] == ["l"])["properties"]["r"]["enum"]
                cash = next(row for row in rows if row["properties"]["k"]["enum"] == ["b"])["properties"]["r"]["enum"][0]
                assert len(leads) == 3
                result = {"blocks": [{"k": "t", "v": "These are research leads, not complete journeys."},
                                     *[{"k": "l", "r": alias, "n": "Research lead",
                                        "v": "Check its full itinerary."} for alias in leads],
                                     {"k": "b", "r": cash, "n": "Cash context",
                                      "v": "A full-cash journey has a reported quote with unknown scope."}]}
            raw = json.dumps(result)
            self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
                "status": "completed", "service_tier": "priority", "output": [
                    {"type": "message", "content": [{"type": "output_text", "text": raw}]}]}))
            return raw

    artifact = run_category_results(projection, _config(), GroupedLeadWriter(),
                                    profile="category-c03")
    assert artifact.resolved is not None
    assert [block.kind for block in artifact.resolved.blocks].count("lead_card") == 3
    assert artifact.selector_prepared.packet["selection_format"] == "roles-v30"
    assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_category_profile_registry_and_prior_request_replay() -> None:
    assert category_profiles() == ("category-c01", "category-c02", "category-c03",
                                   "category-c04", "category-c05", "category-c06",
                                   "category-c07", "category-c08", "category-c09",
                                   "category-c10", "category-c11", "category-c12",
                                   "category-c13", "category-c14", "category-c15",
                                   "category-c16", "category-c17", "category-c18",
                                   "category-c19", "category-c20")
    source, config = _source(), _config()
    for profile in category_profiles()[:6]:
        artifact = run_category_results(source, config, CategoryWriter(), profile=profile)
        assert artifact.selector_prepared.packet["selection_format"] == "roles-v20"
        assert replay_category_results(parse_category_artifact(artifact.model_dump_json())) == artifact.resolved


def test_category_c03_uses_incomplete_grouping_with_only_rejected_alternatives() -> None:
    source = _source()
    rejected = tuple(journey.model_copy(update={"status": "rejected"})
                     for journey in source.view.alternatives)
    research_only = source.model_copy(update={"view": source.view.model_copy(
        update={"alternatives": rejected, "comparison_pool_ids": ()})})
    assert rejected
    assert _selection_format("category-c03", research_only) == "roles-v30"
    assert _selection_format("category-c02", research_only) == "roles-v20"
