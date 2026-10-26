"""Structured Results at the public source, writer and replay boundaries."""

import json
from pathlib import Path

import httpx
import pytest
from openai import OpenAI

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results.adapter import OpenAIStructuredResultsWriter
from award_agent.results.contracts import (
    DeclaredClaim,
    ResultsArtifact,
    ResultsConfig,
    ResultsWriterError,
)
from award_agent.results.structured import (
    StructuredBlock,
    StructuredDocument,
    StructuredSelection,
    check_structured_document,
    prepare_structured_results,
    replay_structured_results,
    resolve_structured_document,
    run_structured_results,
)
from award_agent.results.structured_contracts import (
    StructuredPreparedInput,
    StructuredResultsArtifact,
)
from award_agent.results.workspace_contracts import ComponentView


def _projection() -> SolutionProjection:
    return SolutionProjection.model_validate_json(Path(
        "evidence/ranking-stage/m2/solutions/exact_business.json").read_bytes())


def _config() -> ResultsConfig:
    return ResultsConfig(model="offline-test", max_output_tokens=1000, timeout_seconds=10,
                         context_limit_tokens=10_000_000, prompt_overhead_tokens=0)


@pytest.mark.parametrize("case", ("admitted", "conditional", "incomplete"))
def test_saved_round_one_artifact_retains_original_instruction_boundary(case: str) -> None:
    path = Path("evidence/results-stage/m2/structured/2026-10-24-luna/round-1") / case / "artifact.json"
    artifact = StructuredResultsArtifact.model_validate_json(path.read_bytes())
    assert artifact.evidence.contract_version == "results-workspace-evidence-v1"
    assert artifact.resolved is not None
    assert artifact.resolved.contract_version == "results-resolved-v1"
    assert artifact.prepared.instructions != prepare_structured_results(
        artifact.evidence.source, artifact.config).instructions
    with pytest.raises(ValueError, match="saved structured preparation differs from source"):
        replay_structured_results(artifact)


def _first_award_summary_lead(prepared: StructuredPreparedInput) -> tuple[str, str]:
    rows = prepared.authoring_view.view["incomplete_leads"]
    assert isinstance(rows, list)
    row = next(item for item in rows
               if isinstance(item, dict) and item.get("kind") == "award_summary")
    reference = row.get("ref")
    assert isinstance(reference, str)
    return reference, prepared.references.awards[reference]


def test_incomplete_lead_identity_matches_every_exact_source_member() -> None:
    saved = ResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/compact-input/2026-10-20-luna/incomplete/artifact.json"
    ).read_bytes())
    prepared = prepare_structured_results(saved.projection, _config())
    rows = prepared.authoring_view.view["incomplete_leads"]
    assert isinstance(rows, list)
    source = {item.observation_id: item.model_dump(mode="json")
              for item in saved.projection.view.components}
    aliases = prepared.references.awards | prepared.references.cash
    expected_ids = dict.fromkeys((
        *saved.projection.view.award_summary_observation_ids,
        *saved.projection.view.unmatched_award_observation_ids,
        *saved.projection.view.unpaired_positioning_observation_ids))
    assert [aliases[row["ref"]] for row in rows] == list(expected_ids)
    for row in rows:
        item = source[aliases[row["ref"]]]
        identity = row["identity"]
        assert {field: identity[field] for field in (
            "origin", "destination", "departure_date", "price_scope")} == {
                field: item[field] for field in (
                    "origin", "destination", "departure_date", "price_scope")}
        for field in ("program", "cabin", "points", "cash_amount", "cash_currency"):
            assert identity[field] == {key: item[field][key] for key in ("state", "value")}
    alaska = [row for row in rows if row["identity"]["program"]["value"] == "alaska"
              and row["identity"]["departure_date"] == "2027-01-17"
              and row["identity"]["points"]["value"] in {42500, 55000}]
    assert {(row["identity"]["cabin"]["value"],
             row["identity"]["points"]["value"]) for row in alaska} == {
                 ("economy", 42500), ("premium_economy", 55000)}

    selected_aliases = tuple(row["ref"] for row in alaska)
    document = StructuredDocument(selection=StructuredSelection(
        incomplete_observation_ids=selected_aliases), blocks=(
        StructuredBlock(kind="narrative", text="Two incomplete Alaska leads need verification."),
        *(StructuredBlock(kind="reference", reference_kind="lead", reference_id=alias,
                           label="Award lead", text="") for alias in selected_aliases)))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return document

    artifact = run_structured_results(saved.projection, _config(), FrozenWriter())
    assert artifact.resolved is not None
    assert not [f for f in artifact.resolved.findings if f.outcome == "failed"]
    for block in artifact.resolved.blocks[1:]:
        assert block.component is not None
        assert block.component.observation_id == block.canonical_id
        assert str(block.component.departure_date) == "2027-01-17"
        assert block.component.program.value == "alaska"
    assert replay_structured_results(artifact) == artifact.resolved


def test_structured_answer_resolves_exact_selected_variant_and_preserves_explorer() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    assert "presentation_required_keys" not in prepared.authoring_view.view
    assert "disclosure_profiles" not in prepared.authoring_view.view
    assert "slot_key_catalog" not in prepared.authoring_view.view
    alias, candidate_id = next(iter(prepared.references.journeys.items()))
    document = StructuredDocument(
        selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="narrative", text="A useful choice with caveats."),
                StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, label="Option A",
                                text="Consider this itinerary.")))
    assert not [f for f in check_structured_document(document, projection, prepared)
                if f.outcome == "failed"]

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return document

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert artifact.delivery_outcome == "delivered"
    assert artifact.resolved is not None
    assert artifact.evidence.contract_version == "results-workspace-evidence-v2"
    assert artifact.resolved.contract_version == "results-resolved-v2"
    assert artifact.resolved.blocks[1].canonical_id == candidate_id
    assert artifact.resolved.blocks[1].journey is not None
    assert artifact.resolved.blocks[1].journey.candidate_id == candidate_id
    assert {journey.candidate_id for journey in artifact.evidence.journeys} == {
        item.candidate_id for item in projection.view.alternatives
        if item.status in {"admitted", "conditional"}}
    assert replay_structured_results(artifact) == artifact.resolved


def test_connected_answer_keeps_embedded_exact_refs_and_shared_limitations() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    first, second = tuple(prepared.references.journeys)[:2]
    benchmark = next(iter(prepared.references.cash))
    document = StructuredDocument(selection=StructuredSelection(
        journey_ids=(first, second), benchmark_observation_id=benchmark), blocks=(
        StructuredBlock(kind="narrative", text="This arrival makes the first journey worth a look."),
        StructuredBlock(kind="reference", reference_kind="journey", reference_id=first,
                        label="Earlier arrival", text=""),
        StructuredBlock(kind="narrative", text="The second changes the choice if departure matters more."),
        StructuredBlock(kind="reference", reference_kind="journey", reference_id=second,
                        label="Later departure", text=""),
        StructuredBlock(kind="narrative", text="The observed cash search gives the awards context."),
        StructuredBlock(kind="reference", reference_kind="benchmark", reference_id=benchmark,
                        label="Cash baseline", text=""),
        StructuredBlock(kind="narrative", text=(
            "Both award quotes need scope confirmation; the cash quote also needs scope "
            "confirmation. Check current availability before booking.")),
    ))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return document

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert artifact.resolved is not None
    assert artifact.delivery_outcome == "delivered"
    assert not [f for f in artifact.resolved.findings if f.outcome == "failed"]
    assert [block.kind for block in artifact.resolved.blocks] == [
        "narrative", "reference", "narrative", "reference", "narrative",
        "reference", "narrative"]
    assert [block.canonical_id for block in artifact.resolved.blocks if
            block.kind == "reference"] == [
        prepared.references.journeys[first], prepared.references.journeys[second],
        prepared.references.cash[benchmark]]
    assert artifact.resolved.blocks[-1].text.startswith("Both award quotes")
    assert {item.candidate_id for item in artifact.evidence.journeys} == {
        item.candidate_id for item in projection.view.alternatives
        if item.status in {"admitted", "conditional"}}
    assert replay_structured_results(artifact) == artifact.resolved


def test_structured_writer_sends_new_schema_and_keeps_raw_receipt() -> None:
    prepared = prepare_structured_results(_projection(), _config())
    alias = next(iter(prepared.references.journeys))
    draft = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, label="Option A", text="This is a choice."),))
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "resp_structured", "object": "response",
            "created_at": 0, "status": "completed", "model": "offline-test",
            "output": [{"id": "msg_structured", "type": "message", "role": "assistant",
                        "status": "completed", "content": [{"type": "output_text",
                            "text": draft.model_dump_json(), "annotations": []}]}],
            "usage": {"input_tokens": 80, "output_tokens": 30, "total_tokens": 110}})

    client = OpenAI(api_key="offline", http_client=httpx.Client(
        transport=httpx.MockTransport(respond)))
    writer = OpenAIStructuredResultsWriter(client=client)
    authored = writer.author(prepared, _config())
    assert authored.selection.journey_ids == (alias,)
    assert requests
    format_options = requests[0].get("text")
    assert isinstance(format_options, dict)
    response_format = format_options.get("format")
    assert isinstance(response_format, dict)
    assert response_format.get("name") == "StructuredResultsDocument"
    instructions = requests[0].get("instructions")
    assert isinstance(instructions, str)
    assert "{{fact:" not in instructions
    receipt = writer.take_receipt()
    assert receipt is not None and receipt.usage["input_tokens"] == 80
    assert 'resp_structured' in (receipt.raw_response or "")


def test_wrong_kind_reference_uses_one_correction_and_exact_variant() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    alias, candidate_id = next(iter(prepared.references.journeys.items()))
    benchmark_alias = next(iter(prepared.references.cash))
    wrong = StructuredDocument(selection=StructuredSelection(journey_ids=(benchmark_alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=benchmark_alias, text="Try this."),))
    corrected = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, label="Option A",
                                text="Choose this option."),))
    calls = []

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            calls.append(kwargs)
            return wrong if len(calls) == 1 else corrected

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert len(calls) == 2
    assert artifact.selected_attempt == 1
    assert artifact.selection_reason == "correction_fewer_failures"
    assert artifact.resolved is not None
    assert artifact.resolved.blocks[0].canonical_id == candidate_id
    assert replay_structured_results(artifact) == artifact.resolved


def test_unrecoverable_writer_keeps_source_evidence_available() -> None:
    projection = _projection()
    calls = 0

    class FailingWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            nonlocal calls
            calls += 1
            raise ResultsWriterError("schema_error", "Malformed response")

    artifact = run_structured_results(projection, _config(), FailingWriter())
    assert calls == 1
    assert artifact.delivery_outcome == "not_delivered"
    assert artifact.resolved is None
    assert len(artifact.evidence.journeys) == sum(
        item.status in {"admitted", "conditional"} for item in projection.view.alternatives)
    assert replay_structured_results(artifact) is None


def test_replay_rejects_changed_resolved_fact() -> None:
    projection = _projection()
    alias = next(iter(prepare_structured_results(projection, _config()).references.journeys))
    draft = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, label="Option A",
                                text="A useful option."),))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return draft

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert artifact.resolved is not None
    changed = artifact.resolved.model_copy(update={"availability_guidance": "Book immediately."})
    with pytest.raises(ValueError, match="replay exactly"):
        replay_structured_results(artifact.model_copy(update={"resolved": changed}))


def test_incomplete_award_observation_resolves_to_a_source_bound_lead() -> None:
    saved = ResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/compact-input/2026-10-20-luna/incomplete/artifact.json"
    ).read_bytes())
    projection = saved.projection
    prepared = prepare_structured_results(projection, _config())
    alias, source_id = _first_award_summary_lead(prepared)
    draft = StructuredDocument(selection=StructuredSelection(
        incomplete_observation_ids=(alias,)), blocks=(
            StructuredBlock(kind="narrative", text="No complete award itinerary is available."),
            StructuredBlock(kind="reference", reference_kind="lead", reference_id=alias,
                            label="Lead A", text="This needs more flight details.")))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return draft

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert artifact.resolved is not None
    assert not artifact.resolved.selected_journey_ids
    assert artifact.resolved.blocks[1].canonical_id == source_id
    assert isinstance(artifact.resolved.blocks[1].component, ComponentView)
    source_component = next(item for item in projection.view.components
                            if item.observation_id == source_id)
    assert source_component.departure_date is not None
    assert artifact.resolved.blocks[1].component.departure_date == \
        source_component.departure_date
    assert artifact.resolved.blocks[1].lead is not None
    assert not artifact.resolved.blocks[1].unavailable
    assert replay_structured_results(artifact) == artifact.resolved


def test_wrong_kind_lead_does_not_attach_unrelated_benchmark_facts() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    benchmark_alias = next(iter(prepared.references.cash))
    benchmark_id = prepared.references.cash[benchmark_alias]
    document = StructuredDocument(selection=StructuredSelection(
        incomplete_observation_ids=(benchmark_alias,)), blocks=(
            StructuredBlock(kind="reference", reference_kind="lead",
                            reference_id=benchmark_alias, label="Lead A", text="Needs inspection."),))
    from award_agent.results.presentation import resolve_workspace

    resolved = resolve_structured_document(document, prepared, resolve_workspace(projection))
    assert resolved.blocks[0].canonical_id == benchmark_id
    assert resolved.blocks[0].unavailable
    assert resolved.blocks[0].component is None
    assert resolved.blocks[0].lead is None
    assert any(f.code == "invalid_reference" for f in check_structured_document(
        document, projection, prepared))


def test_correction_tie_selects_later_attempt_and_failure_retains_initial() -> None:
    projection = _projection()
    bad = StructuredDocument(selection=StructuredSelection(journey_ids=("J999",)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id="J999", text="Unknown."),))

    class SameWriter:
        def __init__(self, fail_correction: bool = False) -> None:
            self.calls = 0
            self.fail_correction = fail_correction

        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            self.calls += 1
            if self.calls == 2 and self.fail_correction:
                raise ResultsWriterError("api_error", "Correction unavailable")
            return bad

    tie_writer = SameWriter()
    tie = run_structured_results(projection, _config(), tie_writer)
    assert tie_writer.calls == 2
    assert tie.selected_attempt == 1 and tie.selection_reason == "correction_tie"
    assert replay_structured_results(tie) == tie.resolved
    fail_writer = SameWriter(fail_correction=True)
    failed = run_structured_results(projection, _config(), fail_writer)
    assert fail_writer.calls == 2
    assert failed.selected_attempt == 0 and failed.delivery_outcome == "delivered"
    assert replay_structured_results(failed) == failed.resolved


def test_worse_correction_keeps_initial_and_context_overflow_skips_writer() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    alias = next(iter(prepared.references.journeys))
    initial = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, text="This option needs a label."),))
    worse = StructuredDocument(selection=StructuredSelection(journey_ids=("J999",)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id="J999", text="Unknown."),))

    class Writer:
        def __init__(self) -> None:
            self.calls = 0

        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            self.calls += 1
            return initial if self.calls == 1 else worse

    writer = Writer()
    artifact = run_structured_results(projection, _config(), writer)
    assert writer.calls == 2
    assert artifact.selected_attempt == 0
    assert artifact.selection_reason == "initial_fewer_failures"
    assert replay_structured_results(artifact) == artifact.resolved

    small = _config().model_copy(update={"context_limit_tokens": 100})
    blocked_writer = Writer()
    blocked = run_structured_results(projection, small, blocked_writer)
    assert blocked_writer.calls == 0
    assert blocked.generation_outcome == "context_limit"
    assert blocked.evidence.journeys
    assert replay_structured_results(blocked) is None


def test_replay_rejects_alias_schema_and_source_mutations() -> None:
    projection = _projection()
    alias = next(iter(prepare_structured_results(projection, _config()).references.journeys))
    draft = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=alias, label="Option A", text="A grounded option."),))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return draft

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    changed_alias = artifact.prepared.authoring_view.model_copy(update={"binding_digest": "wrong"})
    changed_prepared = artifact.prepared.model_copy(update={"authoring_view": changed_alias})
    with pytest.raises(ValueError, match="preparation"):
        replay_structured_results(artifact.model_copy(update={"prepared": changed_prepared}))
    changed_attempt = artifact.attempts[0].model_copy(update={"schema_digest": "wrong"})
    with pytest.raises(ValueError, match="request differs"):
        replay_structured_results(artifact.model_copy(update={"attempts": (changed_attempt,)}))
    changed_evidence = artifact.evidence.model_copy(update={"availability_guidance": "Book now."})
    with pytest.raises(ValueError, match="workspace evidence"):
        replay_structured_results(artifact.model_copy(update={"evidence": changed_evidence}))
    original = artifact.attempts[0].document
    assert original is not None
    claim = DeclaredClaim(claim_id="c1", kind="comparison", proposition="fastest",
                          scope_ids=("unrelated-candidate",), text="Fastest option")
    changed_block = original.blocks[0].model_copy(update={
        "text": "A grounded option. Fastest option", "claims": (claim,)})
    changed_document = original.model_copy(update={"blocks": (changed_block,)})
    changed_claim_attempt = artifact.attempts[0].model_copy(update={"document": changed_document})
    with pytest.raises(ValueError, match="findings differ"):
        replay_structured_results(artifact.model_copy(update={"attempts": (changed_claim_attempt,)}))


def test_claim_scope_must_match_exact_reference_and_full_comparison_pool() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    first, foreign = tuple(prepared.references.journeys)[:2]
    benchmark = next(iter(prepared.references.cash))
    claim = DeclaredClaim(claim_id="cabin", kind="cabin", proposition="journey_business",
                          scope_ids=(foreign,), text="Business cabin")
    wrong_journey = StructuredDocument(selection=StructuredSelection(journey_ids=(first,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
                                reference_id=first, label="Option A", text="Business cabin",
                                claims=(claim,)),))
    findings = check_structured_document(wrong_journey, projection, prepared)
    assert any(f.code == "claim_scope_mismatch" and f.outcome == "failed" for f in findings)
    assert not any(f.code.startswith("claim:") and f.outcome == "supported" for f in findings)

    wrong_benchmark = StructuredDocument(selection=StructuredSelection(
        benchmark_observation_id=benchmark), blocks=(StructuredBlock(kind="reference",
        reference_kind="benchmark", reference_id=benchmark, text="Per traveler quote",
        claims=(DeclaredClaim(claim_id="price", kind="price_scope",
                              proposition="per_traveler", scope_ids=(first,),
                              text="Per traveler quote"),)),))
    assert any(f.code == "claim_scope_mismatch" for f in check_structured_document(
        wrong_benchmark, projection, prepared))

    wrong_comparison = StructuredDocument(selection=StructuredSelection(journey_ids=(first,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
            reference_id=first, label="Option A", text="Fastest option",
            claims=(DeclaredClaim(claim_id="fastest", kind="comparison", proposition="fastest",
                scope_ids=(first,), text="Fastest option"),)),))
    assert any(f.code == "claim_scope_mismatch" for f in check_structured_document(
        wrong_comparison, projection, prepared))


def test_replay_rejects_claim_scope_only_mutation() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    alias = next(iter(prepared.references.journeys))
    claim = DeclaredClaim(claim_id="cabin", kind="cabin", proposition="journey_business",
                          scope_ids=(alias,), text="Business cabin")
    draft = StructuredDocument(selection=StructuredSelection(journey_ids=(alias,)),
        blocks=(StructuredBlock(kind="reference", reference_kind="journey",
            reference_id=alias, label="Option A", text="Business cabin", claims=(claim,)),))

    class FrozenWriter:
        def author(self, *args: object, **kwargs: object) -> StructuredDocument:
            return draft

    artifact = run_structured_results(projection, _config(), FrozenWriter())
    assert artifact.validation_outcome == "clean"
    document = artifact.attempts[0].document
    assert document is not None
    changed_claim = document.blocks[0].claims[0].model_copy(update={"scope_ids": ("FOREIGN",)})
    changed_block = document.blocks[0].model_copy(update={"claims": (changed_claim,)})
    changed_document = document.model_copy(update={"blocks": (changed_block,)})
    changed_attempt = artifact.attempts[0].model_copy(update={"document": changed_document})
    with pytest.raises(ValueError, match="findings differ"):
        replay_structured_results(artifact.model_copy(update={"attempts": (changed_attempt,)}))


def test_selected_benchmark_and_lead_require_exact_visible_reference_blocks() -> None:
    projection = _projection()
    prepared = prepare_structured_results(projection, _config())
    benchmark = next(iter(prepared.references.cash))
    only_narrative = (StructuredBlock(kind="narrative", text="A source-backed comparison."),)
    benchmark_document = StructuredDocument(selection=StructuredSelection(
        benchmark_observation_id=benchmark), blocks=only_narrative)
    findings = check_structured_document(benchmark_document, projection, prepared)
    assert any(f.code == "missing_selected_benchmark" and f.outcome == "failed"
               for f in findings)

    saved = ResultsArtifact.model_validate_json(Path(
        "evidence/results-stage/m2/compact-input/2026-10-20-luna/incomplete/artifact.json"
    ).read_bytes())
    lead_prepared = prepare_structured_results(saved.projection, _config())
    lead, _source_id = _first_award_summary_lead(lead_prepared)
    lead_document = StructuredDocument(selection=StructuredSelection(
        incomplete_observation_ids=(lead,)), blocks=only_narrative)
    lead_findings = check_structured_document(lead_document, saved.projection, lead_prepared)
    assert any(f.code == "missing_selected_lead" and f.outcome == "failed"
               for f in lead_findings)
    wrong_lead_scope = StructuredDocument(selection=StructuredSelection(
        incomplete_observation_ids=(lead,)), blocks=(StructuredBlock(
            kind="reference", reference_kind="lead", reference_id=lead,
            label="Lead A", text="Per traveler quote",
            claims=(DeclaredClaim(claim_id="lead-price", kind="price_scope",
                proposition="per_traveler", scope_ids=("FOREIGN",),
                text="Per traveler quote"),)),))
    assert any(f.code == "claim_scope_mismatch" for f in check_structured_document(
        wrong_lead_scope, saved.projection, lead_prepared))
