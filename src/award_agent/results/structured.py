"""Structured, source-resolved Results authoring with exact offline replay."""

from __future__ import annotations

import json
from typing import Literal, cast

from openai.lib._pydantic import to_strict_json_schema

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .contracts import (
    CheckFinding,
    CompactAuthoringInput,
    InputTokenReceipt,
    ResultsConfig,
    ResultsInputMeasurer,
    ResultsPart,
    WriterReceipt,
)
from .core import _claim_check, prepare_results
from .currency import FxAcquisition
from .presentation import resolve_workspace
from .runner import RequestEnvelope, choose_recoverable, run_attempts
from .structured_contracts import (
    ResolvedStructuredAnswer,
    ResolvedStructuredBlock,
    StructuredAttempt,
    StructuredBlock,
    StructuredDocument,
    StructuredPreparedInput,
    StructuredResultsArtifact,
    StructuredResultsWriter,
    StructuredSelection,
)
from .workspace_contracts import WorkspaceEvidence

INSTRUCTIONS = """Write a useful travel answer from the supplied compact evidence. You control
headings, order, narrative and which exact journeys to recommend. Use ordered narrative blocks
and exact typed reference blocks; use J aliases for journeys, C aliases for direct cash benchmarks,
and A/C aliases for incomplete leads. A group is not a selectable journey. Recommend only complete
eligible journeys. Discuss meaningful differences and a notable unselected alternative when it
changes the choice. Keep benchmarks and incomplete leads separate. Give each selected option a
short stable traveler-facing label. Explain tradeoffs without copying complete flight facts:
the application resolves schedules, prices, cabins and source details from references. Never claim
current seats, protected connections, complete unreported prices, or booking availability. Do not
print internal IDs, statuses or checklist labels in traveler prose. Source observations are dated,
not real-time. Known original currency and USD conversion are factual; Ranking estimated comparison
cost, points valuation and estimated taxes are heuristic, never payable cash. Use full local dates
for arrival comparisons. Declared claims must copy their literal text into the block and use exact
scope aliases; full-pool comparison uses P1. Omit claims you cannot precisely support. This
channel requires no Markdown fact slots or mandatory status/requirements inventory. Output only
the requested structured document.
"""


def _schema() -> dict[str, object]:
    return cast(dict[str, object], to_strict_json_schema(StructuredDocument))


def structured_payload(prepared: StructuredPreparedInput,
                       feedback: tuple[CheckFinding, ...] = (),
                       previous_document: StructuredDocument | None = None) -> str:
    refs = prepared.references
    reverse = {value: key for key, value in (
        refs.journeys | refs.awards | refs.cash).items()}
    reverse_pools = {tuple(value): key for key, value in refs.comparison_pools.items()}
    rows = []
    for finding in feedback:
        row = finding.model_dump(mode="json")
        row["reference_id"] = (reverse.get(finding.reference_id, finding.reference_id)
                               if finding.reference_id is not None else None)
        rows.append(row)
    prior = previous_document.model_dump(mode="json") if previous_document else None
    if prior is not None:
        selection = cast(dict[str, object], prior["selection"])
        selection["journey_ids"] = [reverse.get(value, value) for value in
                                    cast(list[str], selection["journey_ids"])]
        benchmark_id = cast(str | None, selection["benchmark_observation_id"])
        selection["benchmark_observation_id"] = (
            reverse.get(benchmark_id, benchmark_id) if benchmark_id is not None else None)
        selection["incomplete_observation_ids"] = [reverse.get(value, value) for value in
                                                    cast(list[str], selection["incomplete_observation_ids"])]
        for block in cast(list[dict[str, object]], prior["blocks"]):
            reference_id = cast(str | None, block["reference_id"])
            block["reference_id"] = (reverse.get(reference_id, reference_id)
                                     if reference_id is not None else None)
            for claim in cast(list[dict[str, object]], block["claims"]):
                scope_ids = cast(list[str], claim["scope_ids"])
                claim["scope_ids"] = ([reverse_pools[tuple(scope_ids)]]
                                      if tuple(scope_ids) in reverse_pools else
                                      [reverse.get(value, value) for value in scope_ids])
    body = {"prepared": {"contract_version": prepared.contract_version,
                         "view": prepared.authoring_view.view},
            "feedback": rows, "previous_document": prior}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def structured_token_request(prepared: StructuredPreparedInput, config: ResultsConfig,
                             payload: str) -> dict[str, object]:
    return {"model": config.model, "instructions": prepared.instructions,
            "input": payload,
            "text": {"format": {"type": "json_schema", "name": "StructuredResultsDocument",
                                "strict": True, "schema": _schema()}}}


def _envelope(prepared: StructuredPreparedInput, config: ResultsConfig,
              feedback: tuple[CheckFinding, ...] = (),
              previous: StructuredDocument | None = None) -> RequestEnvelope:
    payload = structured_payload(prepared, feedback, previous)
    schema_text = json.dumps(_schema(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    prompt = prepared.instructions + payload
    size = len(prompt.encode("utf-8")) + len(schema_text.encode("utf-8"))
    return RequestEnvelope(structured_token_request(prepared, config, payload), size,
        size + config.prompt_overhead_tokens + config.max_output_tokens,
        content_digest(prompt), content_digest(schema_text))


def prepare_structured_results(projection: SolutionProjection,
                               config: ResultsConfig) -> StructuredPreparedInput:
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    legacy = prepare_results(trusted, config)
    compact = legacy.authoring_view
    if compact is None:
        raise ValueError("compact authoring view is missing")
    # V5's fact compression is reusable, but its prose-slot obligation metadata is
    # not a requirement of the structured channel. Preserve every member and alias.
    view = compact.view
    for key in ("presentation_required_keys", "display_slot_vocabulary",
                "slot_key_catalog", "disclosure_profiles"):
        view.pop(key, None)
    for group in cast(list[dict[str, object]], view["journeys"]):
        cast(dict[str, object], group["facts"]).pop("disclosure_profile", None)
    compact = CompactAuthoringInput(source_digest=compact.source_digest,
        view=view, references=compact.references,
        binding_digest=content_digest({"source_digest": compact.source_digest,
            "view": view, "references": compact.references.model_dump(mode="json")}))
    instructions = INSTRUCTIONS
    if config.authoring_guidance and config.authoring_guidance.strip():
        instructions += "\n" + config.authoring_guidance
    initial = StructuredPreparedInput(source_digest=trusted.receipt.view_digest,
        authoring_view=compact, instructions=instructions,
        input_bytes=0, estimated_input_tokens=0, estimated_total_tokens=0)
    envelope = _envelope(initial, config)
    return initial.model_copy(update={"input_bytes": envelope.input_bytes,
        "estimated_input_tokens": envelope.estimated_total_tokens - config.max_output_tokens,
        "estimated_total_tokens": envelope.estimated_total_tokens})


def _canonical(prepared: StructuredPreparedInput, kind: str | None,
               reference: str | None) -> str | None:
    if reference is None:
        return None
    refs = prepared.references
    mapping = refs.journeys if kind == "journey" else (
        refs.cash if kind == "benchmark" else refs.awards | refs.cash)
    return mapping.get(reference, reference)


def _bound_document(prepared: StructuredPreparedInput,
                    document: StructuredDocument) -> StructuredDocument:
    selection = document.selection
    bound = StructuredSelection(
        journey_ids=tuple(_canonical(prepared, "journey", value) or value
                          for value in selection.journey_ids),
        benchmark_observation_id=_canonical(prepared, "benchmark",
                                           selection.benchmark_observation_id),
        incomplete_observation_ids=tuple(_canonical(prepared, "lead", value) or value
                                         for value in selection.incomplete_observation_ids))
    blocks = []
    for block in document.blocks:
        claims = []
        for claim in block.claims:
            scopes: list[str] = []
            for value in claim.scope_ids:
                if value in prepared.references.comparison_pools:
                    scopes.extend(prepared.references.comparison_pools[value])
                else:
                    scopes.append(_canonical(prepared, block.reference_kind, value) or value)
            claims.append(claim.model_copy(update={"scope_ids": tuple(scopes)}))
        blocks.append(block.model_copy(update={
            "reference_id": _canonical(prepared, block.reference_kind, block.reference_id),
            "claims": tuple(claims)}))
    return StructuredDocument(selection=bound, blocks=tuple(blocks))


def check_structured_document(document: StructuredDocument,
                              projection: SolutionProjection,
                              prepared: StructuredPreparedInput) -> tuple[CheckFinding, ...]:
    document = _bound_document(prepared, document)
    view = projection.view
    eligible = {item.candidate_id for item in view.alternatives
                if item.status in {"admitted", "conditional"}}
    benchmark = set(view.direct_cash_observation_ids)
    leads = (set(view.award_summary_observation_ids) |
             set(view.unmatched_award_observation_ids) |
             set(view.unpaired_positioning_observation_ids))
    findings = []
    for candidate in document.selection.journey_ids:
        if candidate not in eligible:
            findings.append(CheckFinding(code="invalid_recommendation", outcome="failed",
                scope="journey", reference_id=candidate,
                message="Selected journey is not an eligible source option."))
    if document.selection.benchmark_observation_id not in benchmark and \
            document.selection.benchmark_observation_id is not None:
        findings.append(CheckFinding(code="invalid_benchmark", outcome="failed",
            scope="benchmark", reference_id=document.selection.benchmark_observation_id,
            message="Selected benchmark is not a direct cash comparison."))
    for oid in document.selection.incomplete_observation_ids:
        if oid not in leads:
            findings.append(CheckFinding(code="invalid_lead", outcome="failed",
                scope="incomplete", reference_id=oid,
                message="Selected lead is not an incomplete source observation."))
    referenced_journeys: set[str | None] = set()
    referenced_benchmarks: set[str | None] = set()
    referenced_leads: set[str | None] = set()
    for index, block in enumerate(document.blocks):
        if block.kind != "reference":
            if block.claims:
                findings.append(CheckFinding(code="unscoped_claim", outcome="failed",
                    scope="shared", part_index=index,
                    message="Narrative claim has no exact source reference."))
            continue
        ref = block.reference_id
        kind = block.reference_kind
        scope: Literal["journey", "benchmark", "incomplete"] = (
            "journey" if kind == "journey" else
            "benchmark" if kind == "benchmark" else "incomplete")
        valid = ref in (eligible if kind == "journey" else benchmark if kind == "benchmark" else leads)
        if not valid:
            findings.append(CheckFinding(code="invalid_reference", outcome="failed",
                scope=scope, reference_id=ref, part_index=index,
                message="Reference kind or exact source association is unavailable."))
            continue
        if kind == "journey":
            referenced_journeys.add(ref)
        elif kind == "benchmark":
            referenced_benchmarks.add(ref)
        else:
            referenced_leads.add(ref)
        selected = (ref in document.selection.journey_ids if kind == "journey" else
                    ref == document.selection.benchmark_observation_id if kind == "benchmark" else
                    ref in document.selection.incomplete_observation_ids)
        if selected and kind == "journey" and not (block.label or "").strip():
            findings.append(CheckFinding(code="missing_option_label", outcome="failed",
                scope="journey", reference_id=ref, part_index=index,
                message="Selected option needs a short traveler-facing label."))
        if not selected and kind != "journey":
            findings.append(CheckFinding(code="unselected_reference", outcome="failed",
                scope=scope, reference_id=ref, part_index=index,
                message="Supporting result was not selected in the document."))
        for claim in block.claims:
            if claim.text not in block.text:
                findings.append(CheckFinding(code="invisible_claim", outcome="failed",
                    scope=scope, reference_id=ref, part_index=index, claim_id=claim.claim_id,
                    message="Declared claim text is absent from its visible block."))
                continue
            scope_valid = (kind == "journey" and ref in claim.scope_ids and
                           claim.scope_ids == view.comparison_pool_ids) if \
                claim.kind == "comparison" else claim.scope_ids == (ref,)
            if not scope_valid:
                findings.append(CheckFinding(code="claim_scope_mismatch", outcome="failed",
                    scope=scope, reference_id=ref, part_index=index, claim_id=claim.claim_id,
                    message="Declared claim lacks the exact supported source scope."))
                continue
            part = ResultsPart(scope=scope, reference_id=ref, markdown=block.text)
            findings.append(_claim_check(claim, part, index, view))
    for candidate in document.selection.journey_ids:
        if candidate in eligible and candidate not in referenced_journeys:
            findings.append(CheckFinding(code="missing_selected_reference", outcome="failed",
                scope="journey", reference_id=candidate,
                message="Selected recommendation has no exact reference block."))
    benchmark_id = document.selection.benchmark_observation_id
    if benchmark_id in benchmark and benchmark_id not in referenced_benchmarks:
        findings.append(CheckFinding(code="missing_selected_benchmark", outcome="failed",
            scope="benchmark", reference_id=benchmark_id,
            message="Selected direct cash comparison has no exact reference block."))
    for oid in document.selection.incomplete_observation_ids:
        if oid in leads and oid not in referenced_leads:
            findings.append(CheckFinding(code="missing_selected_lead", outcome="failed",
                scope="incomplete", reference_id=oid,
                message="Selected incomplete lead has no exact reference block."))
    return tuple(findings)


def resolve_structured_document(document: StructuredDocument,
                                prepared: StructuredPreparedInput,
                                evidence: WorkspaceEvidence,
                                findings: tuple[CheckFinding, ...] = ()) -> ResolvedStructuredAnswer:
    document = _bound_document(prepared, document)
    journeys = {item.candidate_id: item for item in evidence.journeys}
    components = {item.observation_id: item for item in evidence.components}
    leads = {item.reference_id: item for item in evidence.leads}
    benchmark = set(evidence.direct_cash_benchmark_ids)
    blocks = []
    for block in document.blocks:
        ref = block.reference_id
        kind = block.reference_kind
        journey = journeys.get(ref or "") if kind == "journey" else None
        lead = leads.get(ref or "") if kind == "lead" else None
        component = (components.get(ref or "") if (
            kind == "benchmark" and ref in benchmark or
            kind == "lead" and lead is not None) else None)
        available = block.kind == "narrative" or (
            journey is not None if kind == "journey" else
            ref in benchmark and component is not None if kind == "benchmark" else
            lead is not None)
        blocks.append(ResolvedStructuredBlock(kind=block.kind, text=block.text,
            label=block.label, reference_kind=kind, canonical_id=ref,
            journey=journey, component=component, lead=lead, unavailable=not available))
    return ResolvedStructuredAnswer(
        contract_version=("results-resolved-v1" if evidence.contract_version ==
                          "results-workspace-evidence-v1" else "results-resolved-v2"),
        selected_journey_ids=document.selection.journey_ids,
        blocks=tuple(blocks), availability_guidance=evidence.availability_guidance,
        findings=findings)


def _writer_receipt(writer: StructuredResultsWriter) -> WriterReceipt | None:
    take = getattr(writer, "take_receipt", None)
    result = take() if callable(take) else None
    return WriterReceipt.model_validate(result) if result is not None else None


def run_structured_results(projection: SolutionProjection, config: ResultsConfig,
                           writer: StructuredResultsWriter,
                           input_measurer: ResultsInputMeasurer | None = None,
                           *, fx_acquisition: FxAcquisition | None = None,
                           ) -> StructuredResultsArtifact:
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    prepared = prepare_structured_results(projection, config)

    def invoke(feedback: tuple[CheckFinding, ...],
               previous: StructuredDocument | None) -> StructuredDocument:
        authored = writer.author(prepared, config, feedback=feedback, previous_document=previous)
        parsed = (authored if isinstance(authored, StructuredDocument)
                  else StructuredDocument.model_validate(authored))
        return _bound_document(prepared, parsed)

    outcome = run_attempts(config, input_measurer,
        request_for=lambda feedback, previous: _envelope(prepared, config, feedback, previous),
        invoke=invoke,
        check=lambda document: check_structured_document(document, projection, prepared),
        take_receipt=lambda: _writer_receipt(writer))
    attempts = tuple(StructuredAttempt(**vars(item)) for item in outcome.attempts)
    selected = outcome.selected_attempt
    if selected is None:
        artifact = StructuredResultsArtifact(evidence=evidence, config=config, prepared=prepared,
            attempts=attempts, selected_attempt=None, selection_reason=outcome.selection_reason,
            generation_outcome=outcome.generation_outcome, validation_outcome="unavailable",
            delivery_outcome="not_delivered")
    else:
        document = attempts[selected].document
        assert document is not None
        findings = attempts[selected].findings
        resolved = resolve_structured_document(document, prepared, evidence, findings)
        artifact = StructuredResultsArtifact(evidence=evidence, config=config, prepared=prepared,
            attempts=attempts, selected_attempt=selected, selection_reason=outcome.selection_reason,
            generation_outcome="success", validation_outcome="annotated" if any(
                f.outcome == "failed" for f in findings) else "clean",
            delivery_outcome="delivered", resolved=resolved,
            resolved_digest=content_digest(resolved.model_dump(mode="json")))
    replay_structured_results(artifact)
    return artifact


def replay_structured_results(artifact: StructuredResultsArtifact) -> ResolvedStructuredAnswer | None:
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    if artifact.evidence != resolve_workspace(
            projection, fx_acquisition=artifact.evidence.fx_acquisition,
            version=("v1" if artifact.evidence.contract_version ==
                     "results-workspace-evidence-v1" else "v2")):
        raise ValueError("saved workspace evidence differs from source")
    legacy = prepare_results(projection, artifact.config)
    verify_authoring_view(projection, legacy)
    prepared = prepare_structured_results(projection, artifact.config)
    if artifact.prepared != prepared:
        raise ValueError("saved structured preparation differs from source")
    if len(artifact.attempts) > 2 or tuple(a.phase for a in artifact.attempts) != tuple(
            ("initial", "correction")[:len(artifact.attempts)]):
        raise ValueError("saved structured attempt sequence is invalid")
    feedback: tuple[CheckFinding, ...] = ()
    previous = None
    for index, attempt in enumerate(artifact.attempts):
        envelope = _envelope(prepared, artifact.config, feedback, previous)
        if (attempt.input_bytes, attempt.estimated_total_tokens, attempt.prompt_digest,
                attempt.schema_digest) != (envelope.input_bytes, envelope.estimated_total_tokens,
                                          envelope.prompt_digest, envelope.schema_digest):
            raise ValueError("saved structured attempt request differs")
        count = attempt.input_token_receipt
        if count is not None:
            if InputTokenReceipt.model_validate(count.model_dump(mode="json")).request_digest != \
                    content_digest(envelope.request):
                raise ValueError("saved structured token request differs")
            within = (artifact.config.max_input_tokens is None or
                      count.input_tokens <= artifact.config.max_input_tokens) and (
                count.input_tokens + artifact.config.max_output_tokens +
                artifact.config.prompt_overhead_tokens <= artifact.config.context_limit_tokens)
        else:
            within = (envelope.estimated_total_tokens <= artifact.config.context_limit_tokens and
                (artifact.config.max_input_tokens is None or
                 envelope.estimated_total_tokens - artifact.config.max_output_tokens <=
                 artifact.config.max_input_tokens))
        if attempt.writer_called and not within:
            raise ValueError("saved structured writer exceeded context limit")
        if not attempt.writer_called and not (
            (attempt.outcome == "generation_error" and attempt.error == "context_limit" and
             not within and attempt.document is None) or
            (attempt.outcome == "measurement_error" and
             attempt.error == "input_token_measurement_failed" and
             count is None and attempt.document is None)):
            raise ValueError("saved structured noninvocation outcome is invalid")
        if index == 1 and (previous is None or not feedback):
            raise ValueError("saved structured correction has no failed initial draft")
        if attempt.document is not None:
            if attempt.outcome != "recoverable" or not attempt.writer_called or \
                    attempt.error is not None or attempt.findings != check_structured_document(
                    attempt.document, projection, prepared):
                raise ValueError("saved structured findings differ from source")
            previous = attempt.document
            feedback = tuple(f for f in attempt.findings if f.outcome == "failed")
        elif attempt.outcome == "recoverable":
            raise ValueError("saved structured recoverable attempt has no document")
        else:
            feedback = ()
        if attempt.outcome == "api_error" and attempt.failure_subtype != "api_error":
            raise ValueError("saved structured API failure subtype is inconsistent")
        if attempt.outcome == "measurement_error" and attempt.writer_called:
            raise ValueError("saved structured measurement error invoked writer")
        if attempt.outcome == "generation_error" and attempt.writer_called and \
                attempt.failure_subtype not in {"refusal", "incomplete", "schema_error"}:
            raise ValueError("saved structured generation failure subtype is inconsistent")
    if (len(artifact.attempts) == 1 and artifact.attempts[0].outcome == "recoverable" and
            any(f.outcome == "failed" for f in artifact.attempts[0].findings)):
        raise ValueError("saved structured correction attempt is missing")
    recoverable = [(index, attempt) for index, attempt in enumerate(artifact.attempts)
                   if attempt.outcome == "recoverable" and attempt.document is not None]
    if artifact.selected_attempt is None:
        if recoverable or artifact.resolved is not None or artifact.resolved_digest is not None or \
                artifact.delivery_outcome != "not_delivered" or artifact.validation_outcome != "unavailable":
            raise ValueError("saved structured undelivered outcome is inconsistent")
        terminal = artifact.attempts[-1] if artifact.attempts else None
        expected_generation = ("context_limit" if terminal and terminal.error == "context_limit" else
            "measurement_error" if terminal and terminal.outcome == "measurement_error" else
            "api_error" if terminal and terminal.outcome == "api_error" else
            "generation_error" if terminal else "context_limit")
        if artifact.generation_outcome != expected_generation:
            raise ValueError("saved structured generation outcome is inconsistent")
        if not artifact.attempts and not (
            prepared.estimated_total_tokens > artifact.config.context_limit_tokens or
            (artifact.config.max_input_tokens is not None and
             prepared.estimated_input_tokens > artifact.config.max_input_tokens)):
            raise ValueError("saved structured empty context failure is inconsistent")
        expected_reason = "context_limit" if expected_generation == "context_limit" else \
            "no_recoverable_draft"
        if artifact.selection_reason != expected_reason:
            raise ValueError("saved structured selection reason is inconsistent")
        return None
    if not recoverable:
        raise ValueError("selected structured attempt is unavailable")
    expected, expected_reason = choose_recoverable(tuple(
        (index, attempt.findings) for index, attempt in recoverable))
    if artifact.selected_attempt != expected:
        raise ValueError("saved structured selection differs from findings")
    if artifact.selection_reason != expected_reason:
        raise ValueError("saved structured selection reason differs from checks")
    selected = artifact.attempts[expected]
    assert selected.document is not None
    resolved = resolve_structured_document(selected.document, prepared, artifact.evidence,
                                           selected.findings)
    if artifact.resolved != resolved or artifact.resolved_digest != content_digest(
            resolved.model_dump(mode="json")):
        raise ValueError("saved structured answer does not replay exactly")
    if artifact.delivery_outcome != "delivered" or artifact.generation_outcome != "success" or \
            artifact.validation_outcome != ("annotated" if any(
                f.outcome == "failed" for f in selected.findings) else "clean"):
        raise ValueError("saved structured delivery receipt is inconsistent")
    return resolved


__all__ = [
    "StructuredBlock",
    "StructuredDocument",
    "StructuredPreparedInput",
    "StructuredResultsArtifact",
    "StructuredSelection",
    "check_structured_document",
    "prepare_structured_results",
    "replay_structured_results",
    "resolve_structured_document",
    "run_structured_results",
    "structured_payload",
    "structured_token_request",
]
