"""Compact Results request and binding at the public writer boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from openai import OpenAI

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    CheckFinding,
    DeclaredClaim,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    SharedDisclosureBinding,
    authoring_payload,
    check_document,
    prepare_results,
    render_results,
    replay_results,
    run_results,
)
from award_agent.results.adapter import OpenAIResultsWriter
from award_agent.results.request import token_request


def _source() -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_text())


def _config() -> ResultsConfig:
    return ResultsConfig(model="offline-test", max_output_tokens=1000, timeout_seconds=10,
                         context_limit_tokens=10_000_000, prompt_overhead_tokens=0)


def _response(document: ResultsDocument) -> dict[str, Any]:
    return {"id": "resp_offline", "object": "response", "created_at": 0,
            "status": "completed", "model": "offline-test", "output": [{
                "id": "msg_offline", "type": "message", "role": "assistant",
                "status": "completed", "content": [{"type": "output_text",
                    "text": document.model_dump_json(), "annotations": []}]}],
            "usage": {"input_tokens": 80, "output_tokens": 30, "total_tokens": 110}}


def test_compact_request_and_correction_bind_the_same_journey() -> None:
    source = _source()
    prepared = prepare_results(source, _config())
    assert prepared.contract_version == "results-prepared-v4"
    assert prepared.authoring_view is not None
    alias, canonical = next(iter(prepared.authoring_view.references.journeys.items()))
    authored = ResultsDocument(selection=ResultsSelection(journey_ids=(alias,)), parts=(
        ResultsPart(scope="shared", markdown="Overview."),
        ResultsPart(scope="journey", reference_id=alias, identifier="Option A",
                    markdown="Option A. {{fact:route}}.")))
    requests: list[dict[str, Any]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=_response(authored))

    client = OpenAI(api_key="offline", http_client=httpx.Client(
        transport=httpx.MockTransport(respond)))
    writer = OpenAIResultsWriter(client=client)
    first = writer.author(prepared, _config())
    assert first.selection.journey_ids == (canonical,)
    assert first.parts[1].reference_id == canonical
    assert canonical not in requests[0]["input"]
    assert prepared.source_digest not in requests[0]["input"]
    assert "alias_to_canonical" not in requests[0]["input"]
    assert requests[0]["input"] == token_request(prepared, _config(),
                                                  authoring_payload(prepared))["input"]

    feedback = (CheckFinding(code="sample", outcome="failed", scope="journey",
                             reference_id=canonical, message="Check wording."),)
    second = writer.author(prepared, _config(), feedback, first)
    assert second == first
    correction = json.loads(requests[1]["input"])
    assert correction["feedback"][0]["reference_id"] == alias
    assert correction["previous_document"]["selection"]["journey_ids"] == [alias]
    assert canonical not in requests[1]["input"]


def test_compact_writer_rebinds_shared_disclosures_and_full_comparison_pool() -> None:
    prepared = prepare_results(_source(), _config())
    assert prepared.authoring_view is not None
    refs = prepared.authoring_view.references
    first, second = tuple(refs.journeys)[:2]
    authored = ResultsDocument(selection=ResultsSelection(journey_ids=(first, second)), parts=(
        ResultsPart(scope="shared", markdown="Options A and B. {{fact:coverage}}",
                    shared_disclosures=(SharedDisclosureBinding(key="coverage",
                        journey_ids=(first, second)),),
                    claims=(DeclaredClaim(claim_id="comparison", kind="comparison",
                        proposition="fastest", scope_ids=("P1",), text="Fastest option"),)),
        ResultsPart(scope="journey", reference_id=first, identifier="Option A",
                    markdown="Option A. {{fact:route}}."),
        ResultsPart(scope="journey", reference_id=second, identifier="Option B",
                    markdown="Option B. {{fact:route}}.")))
    client = OpenAI(api_key="offline", http_client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=_response(authored)))))
    result = OpenAIResultsWriter(client=client).author(prepared, _config())
    assert result.selection.journey_ids == (refs.journeys[first], refs.journeys[second])
    assert result.parts[0].shared_disclosures[0].journey_ids == result.selection.journey_ids
    assert result.parts[0].claims[0].scope_ids == refs.comparison_pools["P1"]


def test_compact_writer_rejects_wrong_kind_and_unknown_references_without_guessing() -> None:
    prepared = prepare_results(_source(), _config())
    assert prepared.authoring_view is not None
    cash = next(iter(prepared.authoring_view.references.cash))
    authored = ResultsDocument(selection=ResultsSelection(journey_ids=(cash, "J99999")), parts=(
        ResultsPart(scope="shared", markdown="Overview."),
        ResultsPart(scope="journey", reference_id=cash, identifier="Option A",
                    markdown="Option A. {{fact:route}}.")))
    client = OpenAI(api_key="offline", http_client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=_response(authored)))))
    result = OpenAIResultsWriter(client=client).author(prepared, _config())
    canonical_ids = set(prepared.authoring_view.references.journeys.values())
    assert not canonical_ids.intersection(result.selection.journey_ids)
    assert all(value.startswith("invalid-authoring-reference:journey")
               for value in result.selection.journey_ids)
    assert result.parts[1].reference_id == result.selection.journey_ids[0]


def test_new_artifact_replays_and_rejects_tampered_binding() -> None:
    source = _source()
    canonical_draft = ResultsDocument(selection=ResultsSelection(), parts=(
        ResultsPart(scope="shared", markdown=(
            "{{fact:coverage}} {{fact:provider_status}} {{fact:benchmark_status}}")),))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> ResultsDocument:
            return canonical_draft

    artifact = run_results(source, _config(), FrozenWriter())
    assert artifact.contract_version == "results-artifact-v5"
    assert replay_results(artifact) == artifact.rendered_markdown
    assert artifact.prepared.authoring_view is not None
    tampered_view = artifact.prepared.authoring_view.model_copy(update={"binding_digest": "wrong"})
    tampered_prepared = artifact.prepared.model_copy(update={"authoring_view": tampered_view})
    tampered = artifact.model_copy(update={"prepared": tampered_prepared})
    with pytest.raises(ValueError, match="compact authoring view"):
        replay_results(tampered)


def test_compact_authoring_references_are_copy_isolated() -> None:
    prepared = prepare_results(_source(), _config())
    assert prepared.authoring_view is not None
    original = prepared.authoring_view
    original.view["request"] = "tampered"
    original.references.journeys["J1"] = "tampered"
    assert prepared.authoring_view.view["request"] != "tampered"
    assert prepared.authoring_view.references.journeys["J1"] != "tampered"


@pytest.mark.parametrize("seed", [11, 23, 37])
def test_saved_live_incomplete_artifact_replays_across_hash_seeds(seed: int) -> None:
    path = Path("evidence/results-stage/m2/compact-input/2026-10-20-luna/incomplete/artifact.json")
    command = (
        "from pathlib import Path; "
        "from award_agent.results import ResultsArtifact, replay_results; "
        f"a=ResultsArtifact.model_validate_json(Path({str(path)!r}).read_bytes()); "
        "assert replay_results(a)==a.rendered_markdown"
    )
    result = subprocess.run([sys.executable, "-c", command],
                            env={**os.environ, "PYTHONHASHSEED": str(seed)},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("count", [7, 10])
def test_more_than_five_compact_choices_remain_distinct_and_renderable(count: int) -> None:
    source = SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json").read_text())
    prepared = prepare_results(source, _config())
    assert prepared.authoring_view is not None
    selected = tuple(prepared.authoring_view.references.journeys.items())[:count]
    draft = ResultsDocument(selection=ResultsSelection(journey_ids=tuple(alias for alias, _ in selected)),
        parts=(ResultsPart(scope="shared", markdown="{{fact:coverage}}"),) + tuple(
            ResultsPart(scope="journey", reference_id=alias, identifier=f"Option {index}",
                        markdown=f"Option {index}. {{{{fact:route}}}}.")
            for index, (alias, _) in enumerate(selected, 1)))
    client = OpenAI(api_key="offline", http_client=httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=_response(draft)))))
    bound = OpenAIResultsWriter(client=client).author(prepared, _config())
    assert bound.selection.journey_ids == tuple(canonical for _, canonical in selected)
    assert len(set(bound.selection.journey_ids)) == count
    findings = check_document(bound, source)
    assert any(finding.code == "over_target" for finding in findings)
    rendered, facts = render_results(bound, source)
    assert all(f"Option {index}" in rendered for index in range(1, count + 1))
    assert len([fact for fact in facts if fact.key == "route" and fact.scope == "journey"]) == count
