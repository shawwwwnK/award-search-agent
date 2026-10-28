"""Two-pass focused Results source, request, and replay boundaries."""

import json
from pathlib import Path

import pytest

from award_agent.cli import results as results_cli
from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.contracts import InputTokenReceipt, ResultsConfig, WriterReceipt
from award_agent.results.focused import (
    prepare_focused_selector,
    replay_focused_results,
    run_focused_results,
)
from award_agent.results.focused_contracts import FocusedResultsArtifact
from award_agent.results.focused_packet import (
    _observed_path,
    decode_selection_v2,
    selection_schema_v2,
)


def _source() -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())


def _config() -> ResultsConfig:
    return ResultsConfig(model="gpt-6-luna", max_output_tokens=1000,
                         timeout_seconds=10, context_limit_tokens=10_000_000,
                         prompt_overhead_tokens=0)


class FakeMeasurer:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def measure(self, request: dict[str, object], config: ResultsConfig) -> InputTokenReceipt:
        self.requests.append(request)
        return InputTokenReceipt(request_digest=content_digest(request), input_tokens=100,
            raw_response={"object": "response.input_tokens", "input_tokens": 100})


class FakeWriter:
    def __init__(self, *, bad_selection: bool = False, v2: bool = False) -> None:
        self.bad_selection = bad_selection
        self.v2 = v2
        self.requests: list[dict[str, object]] = []
        self.pending: WriterReceipt | None = None

    def author(self, request: dict[str, object], config: ResultsConfig, settings) -> str:
        self.requests.append(request)
        packet = json.loads(request["input"])["packet"]
        if len(self.requests) == 1:
            alias = packet["journey_rows"][0][0]
            if self.bad_selection:
                alias = "C999"
            raw = (json.dumps({"choices": [{"k": "j", "r": alias}]}) if self.v2 else
                   json.dumps({"journeys": [alias], "benchmark": None, "leads": []}))
            assert settings.reasoning_effort == "none"
        else:
            alias = packet["journeys"][0]["members"][0]["ref"]
            raw = json.dumps({"blocks": [{"k": "p", "r": alias,
                                            "n": "Choice", "v": "Consider this journey."}]})
            assert settings.reasoning_effort == "low"
            assert "wire_aliases" not in packet
        assert settings.service_tier == "fast"
        self.pending = WriterReceipt(status="completed", raw_response=json.dumps({
            "status": "completed", "service_tier": "priority",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": raw}]}]}))
        return raw

    def take_receipt(self) -> WriterReceipt | None:
        receipt, self.pending = self.pending, None
        return receipt


def test_two_pass_focused_run_and_exact_replay() -> None:
    source = _source()
    prepared = prepare_focused_selector(source, _config())
    assert len(prepared.packet["journey_rows"]) == source.receipt.eligible_alternatives
    writer, measurer = FakeWriter(), FakeMeasurer()
    artifact = run_focused_results(source, _config(), writer, measurer)
    assert artifact.contract_version == "results-artifact-v8"
    assert artifact.delivery_outcome == "delivered"
    assert len(artifact.passes) == len(writer.requests) == len(measurer.requests) == 2
    assert [item.phase for item in artifact.passes] == ["selection", "composition"]
    assert [item.request["reasoning"] for item in artifact.passes] == [
        {"effort": "none"}, {"effort": "low"}]
    assert artifact.focus_prepared is not None
    assert "wire_aliases" in artifact.focus_prepared.packet
    assert artifact.runtime_seconds > 0
    assert replay_focused_results(artifact) == artifact.resolved
    assert replay_focused_results(FocusedResultsArtifact.model_validate_json(
        artifact.model_dump_json())) == artifact.resolved

    tampered = artifact.model_dump(mode="json")
    tampered["passes"][0]["request"]["input"] = "tampered"
    with pytest.raises(ValueError, match="request"):
        replay_focused_results(FocusedResultsArtifact.model_validate(tampered))

    tampered = artifact.model_dump(mode="json")
    response = json.loads(tampered["passes"][1]["writer_receipt"]["raw_response"])
    response["status"] = "incomplete"
    tampered["passes"][1]["writer_receipt"]["raw_response"] = json.dumps(response)
    with pytest.raises(ValueError, match="completed"):
        replay_focused_results(FocusedResultsArtifact.model_validate(tampered))


def test_invalid_selector_is_explicit_failure_without_composer_call() -> None:
    writer, measurer = FakeWriter(bad_selection=True), FakeMeasurer()
    artifact = run_focused_results(_source(), _config(), writer, measurer)
    assert artifact.delivery_outcome == "not_delivered"
    assert len(artifact.passes) == len(writer.requests) == len(measurer.requests) == 1
    assert artifact.passes[0].failure_subtype == "schema_error"
    assert artifact.focus_prepared is None
    assert replay_focused_results(artifact) is None


def test_v2_total_schema_limit_and_replay() -> None:
    source, config = _source(), _config()
    selector = prepare_focused_selector(source, config, selection_format="roles-v2")
    assert selector.packet["selection_format"] == "roles-v2"
    schema = selection_schema_v2(selector.structured, source)
    choices = schema["properties"]["choices"]
    assert choices["maxItems"] == 8
    assert {branch["properties"]["k"]["enum"][0]
            for branch in choices["items"]["anyOf"]} == {"j", "b", "l"}
    writer, measurer = FakeWriter(v2=True), FakeMeasurer()
    artifact = run_focused_results(source, config, writer, measurer,
                                   selection_format="roles-v2")
    assert artifact.delivery_outcome == "delivered"
    assert len(writer.requests) == len(measurer.requests) == 2
    assert replay_focused_results(FocusedResultsArtifact.model_validate_json(
        artifact.model_dump_json())) == artifact.resolved
    assert "selection_format" not in prepare_focused_selector(source, config).packet


def test_v2_selector_rejects_over_budget_duplicate_and_wrong_role() -> None:
    source = _source()
    selector = prepare_focused_selector(source, _config(), selection_format="roles-v2")
    refs = selector.structured.references
    journey, cash = next(iter(refs.journeys)), next(iter(refs.cash))
    leads = list(refs.awards)[:7]
    valid = {"choices": [{"k": "j", "r": journey}, {"k": "b", "r": cash}]}
    assert decode_selection_v2(valid, selector.structured, source).journey_ids
    with pytest.raises(ValueError, match="eight-reference"):
        decode_selection_v2({"choices": [*valid["choices"],
                                         *({"k": "l", "r": ref} for ref in leads)]},
                            selector.structured, source)
    with pytest.raises(ValueError, match="duplicate"):
        decode_selection_v2({"choices": [{"k": "j", "r": journey},
                                        {"k": "j", "r": journey}]}, selector.structured, source)
    with pytest.raises(ValueError, match="cash benchmark"):
        decode_selection_v2({"choices": [{"k": "j", "r": journey},
                                        {"k": "b", "r": cash},
                                        {"k": "b", "r": cash}]}, selector.structured, source)
    with pytest.raises(ValueError, match="wrong-role"):
        decode_selection_v2({"choices": [{"k": "j", "r": cash}]}, selector.structured, source)


def test_observed_path_preserves_unknown_and_rejects_known_contradiction() -> None:
    assert _observed_path({"topology": "award_only", "award": {},
                           "route": {"origin": "SFO", "destination": "BKK"}}) is None
    mixed = {"topology": "cash_access_award", "award": {"airports": ["LAX", "BKK"]},
             "cash": {"airports": []},
             "route": {"origin": "SFO", "destination": "BKK"}}
    assert _observed_path(mixed) is None
    mixed["cash"]["airports"] = ["SFO", "JFK"]
    with pytest.raises(ValueError, match="join exactly"):
        _observed_path(mixed)


def test_focused_cli_measure_author_and_replay_without_network(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, config = _source(), _config()
    source_path, config_path = tmp_path / "source.json", tmp_path / "config.json"
    source_path.write_text(source.model_dump_json())
    config_path.write_text(config.model_dump_json())
    common = ["--interactive", "--packet-profile", "focused-v1",
              "--projection", str(source_path), "--config", str(config_path)]
    measure_path = tmp_path / "measure.json"
    assert results_cli.main(["measure", *common, "--output", str(measure_path)]) == 0
    assert json.loads(measure_path.read_text())["source_digest"] == source.receipt.view_digest
    v2_common = [*common[:2], "focused-v2", *common[3:]]
    v2_measure_path = tmp_path / "measure-v2.json"
    assert results_cli.main(["measure", *v2_common,
                             "--output", str(v2_measure_path)]) == 0
    assert json.loads(v2_measure_path.read_text())["source_digest"] == source.receipt.view_digest

    from award_agent.results import focused as focused_module

    artifact = run_focused_results(source, config, FakeWriter(), FakeMeasurer())
    captured: list[tuple[object, ...]] = []

    def fake_run(*args: object, **kwargs: object) -> FocusedResultsArtifact:
        captured.append(args)
        return artifact

    monkeypatch.setattr(focused_module, "run_focused_results", fake_run)
    artifact_path = tmp_path / "artifact.json"
    assert results_cli.main(["author", *common, "--live", "--output", str(artifact_path)]) == 0
    assert len(captured) == 1
    assert captured[0][0] == source
    assert FocusedResultsArtifact.model_validate_json(artifact_path.read_bytes()) == artifact
    answer_path = tmp_path / "answer.json"
    assert results_cli.main(["replay", "--artifact", str(artifact_path),
                             "--output", str(answer_path)]) == 0
    assert json.loads(answer_path.read_text())["contract_version"] == "results-resolved-v2"

    with pytest.raises(SystemExit):
        results_cli.main(["measure", *common, "--reasoning-effort", "none",
                          "--output", str(tmp_path / "invalid.json")])
