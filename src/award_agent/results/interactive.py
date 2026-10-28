"""Explicit low latency Results channel with source-bound offline replay."""

from __future__ import annotations

import json
import time
from typing import Literal, cast

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection

from .authoring import verify_authoring_view
from .contracts import CheckFinding, ResultsConfig, ResultsInputMeasurer, WriterReceipt
from .core import prepare_results
from .currency import FxAcquisition
from .interactive_contracts import (
    InteractiveAttempt,
    InteractivePreparedInput,
    InteractiveResultsArtifact,
    InteractiveSettings,
    InteractiveWriter,
)
from .interactive_packet import build_packet
from .interactive_wire import INSTRUCTIONS, WIRE_SCHEMA, decode_wire
from .presentation import resolve_workspace
from .runner import RequestEnvelope, choose_recoverable, run_attempts
from .structured import (
    check_structured_document,
    prepare_structured_results,
    resolve_structured_document,
)
from .structured_contracts import ResolvedStructuredAnswer, StructuredDocument
from .workspace_contracts import WorkspaceEvidence


def prepare_interactive_results(projection: SolutionProjection, config: ResultsConfig,
                                evidence: WorkspaceEvidence | None = None,
                                *, packet_profile: Literal["indexed-v1", "joined-v2", "joined-v3", "joined-v4"] = "indexed-v1",
                                ) -> InteractivePreparedInput:
    trusted = SolutionProjection.model_validate(projection.model_dump(mode="json"))
    workspace = evidence or resolve_workspace(trusted)
    structured = prepare_structured_results(trusted, config)
    if packet_profile == "indexed-v1":
        raw_packet = build_packet(structured, trusted, workspace)
    elif packet_profile == "joined-v2":
        from .interactive_packet_v2 import build_packet as build_joined_packet

        raw_packet = build_joined_packet(structured, trusted, workspace)
        if raw_packet.get("format") != "decision-joined-v2":
            raise ValueError("joined packet builder returned an unexpected format")
    elif packet_profile == "joined-v3":
        from .interactive_packet_v3 import build_packet as build_identity_packet

        raw_packet = build_identity_packet(structured, trusted, workspace)
        if raw_packet.get("format") != "decision-joined-v3":
            raise ValueError("identity packet builder returned an unexpected format")
    elif packet_profile == "joined-v4":
        from .interactive_packet_v4 import build_packet as build_compact_identity_packet

        raw_packet = build_compact_identity_packet(structured, trusted, workspace)
        if raw_packet.get("format") != "decision-joined-v4":
            raise ValueError("compact identity packet builder returned an unexpected format")
    else:
        raise ValueError("unknown interactive packet profile")
    # Freeze the JSON wire shape: the indexed builder's column-name tuples serialize as lists.
    packet = json.loads(json.dumps(raw_packet,
                                   ensure_ascii=False))
    return InteractivePreparedInput(structured=structured, packet=packet,
        packet_digest=content_digest(packet), source_digest=trusted.receipt.view_digest)


def _feedback_rows(prepared: InteractivePreparedInput,
                   feedback: tuple[CheckFinding, ...]) -> list[dict[str, object]]:
    refs = prepared.structured.references
    reverse = {value: key for key, value in (refs.journeys | refs.awards | refs.cash).items()}
    rows = []
    for finding in feedback:
        row = finding.model_dump(mode="json")
        if finding.reference_id is not None:
            if prepared.packet.get("format") in {"decision-joined-v3", "decision-joined-v4"}:
                if prepared.packet["format"] == "decision-joined-v4":
                    from .interactive_wire_v4 import alias_for_canonical
                else:
                    from .interactive_wire_v3 import alias_for_canonical

                row["reference_id"] = (alias_for_canonical(prepared, finding.reference_id)
                                       or finding.reference_id)
            else:
                row["reference_id"] = reverse.get(finding.reference_id, finding.reference_id)
        rows.append(row)
    return rows


def interactive_payload(prepared: InteractivePreparedInput,
                        feedback: tuple[CheckFinding, ...] = (),
                        previous_wire: str | None = None) -> str:
    prior = json.loads(previous_wire) if previous_wire is not None else None
    packet = prepared.packet
    if packet.get("format") == "decision-joined-v4":
        packet = {key: value for key, value in packet.items() if key != "wire_aliases"}
    return json.dumps({"packet": packet, "feedback": _feedback_rows(prepared, feedback),
                       "previous_wire": prior}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def interactive_token_request(prepared: InteractivePreparedInput, config: ResultsConfig,
                              settings: InteractiveSettings, payload: str) -> dict[str, object]:
    if prepared.packet.get("format") == "decision-joined-v3":
        from .interactive_wire_v3 import instructions as identity_instructions
        from .interactive_wire_v3 import schema as identity_schema

        base_instructions = identity_instructions(prepared)
        wire_schema = identity_schema(prepared)
    elif prepared.packet.get("format") == "decision-joined-v4":
        from .interactive_wire_v4 import instructions as compact_identity_instructions
        from .interactive_wire_v4 import schema as compact_identity_schema

        base_instructions = compact_identity_instructions(prepared)
        wire_schema = compact_identity_schema(prepared)
    else:
        base_instructions = INSTRUCTIONS
        wire_schema = WIRE_SCHEMA
    instructions = base_instructions + ("\n" + config.authoring_guidance
                                   if config.authoring_guidance and config.authoring_guidance.strip() else "")
    return {"model": config.model, "reasoning": {"effort": settings.reasoning_effort},
            "instructions": instructions, "input": payload,
            "text": {"format": {"type": "json_schema", "name": "InteractiveResultsWire",
                                "strict": True, "schema": wire_schema}}}


def _envelope(prepared: InteractivePreparedInput, config: ResultsConfig,
              settings: InteractiveSettings, feedback: tuple[CheckFinding, ...] = (),
              previous_wire: str | None = None) -> RequestEnvelope:
    payload = interactive_payload(prepared, feedback, previous_wire)
    request = interactive_token_request(prepared, config, settings, payload)
    text_format = cast(dict[str, object], cast(dict[str, object], request["text"])["format"])
    schema = json.dumps(text_format["schema"], sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"))
    prompt = cast(str, request["instructions"]) + payload
    size = len(prompt.encode()) + len(schema.encode())
    return RequestEnvelope(request, size, size + config.prompt_overhead_tokens +
                           config.max_output_tokens, content_digest(prompt), content_digest(schema))


def _receipt(writer: InteractiveWriter) -> WriterReceipt | None:
    result = writer.take_receipt()
    return WriterReceipt.model_validate(result) if result is not None else None


def _returned_tier(receipt: WriterReceipt | None) -> str | None:
    if receipt is None or receipt.raw_response is None:
        return None
    try:
        value = json.loads(receipt.raw_response).get("service_tier")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def _response_text(receipt: WriterReceipt | None) -> str | None:
    if receipt is None or receipt.raw_response is None:
        return None
    try:
        raw = json.loads(receipt.raw_response)
        parts = [part["text"] for item in raw["output"]
                 if item.get("type") == "message" for part in item.get("content", [])
                 if part.get("type") == "output_text"]
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    return "".join(parts)


def _validate_recoverable_response(receipt: WriterReceipt | None) -> None:
    """A saved recoverable draft needs a completed, non-refusal raw response."""
    if receipt is None or receipt.raw_response is None:
        return
    try:
        raw = json.loads(receipt.raw_response)
        if not isinstance(raw, dict) or raw.get("status") != "completed" or \
                receipt.status != raw["status"]:
            raise ValueError("saved interactive recoverable response is not completed")
        output = raw.get("output")
        if not isinstance(output, list):
            raise TypeError("saved interactive recoverable response lacks output")
        if any(item.get("type") == "message" and any(
                part.get("type") == "refusal" for part in item.get("content", []))
               for item in output):
            raise ValueError("saved interactive recoverable response contains refusal")
    except (TypeError, AttributeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("saved interactive recoverable raw response is invalid") from exc


def run_interactive_results(projection: SolutionProjection, config: ResultsConfig,
                            settings: InteractiveSettings, writer: InteractiveWriter,
                            input_measurer: ResultsInputMeasurer | None = None,
                            *, fx_acquisition: FxAcquisition | None = None,
                            packet_profile: Literal["indexed-v1", "joined-v2", "joined-v3", "joined-v4"] = "indexed-v1",
                            ) -> InteractiveResultsArtifact:
    started = time.perf_counter()
    evidence = resolve_workspace(projection, fx_acquisition=fx_acquisition)
    prepared = prepare_interactive_results(projection, config, evidence,
                                           packet_profile=packet_profile)
    raw_by_phase: dict[str, str] = {}
    request_by_phase: dict[str, RequestEnvelope] = {}
    phase = "initial"

    def request_for(feedback: tuple[CheckFinding, ...],
                    previous: StructuredDocument | None) -> RequestEnvelope:
        nonlocal phase
        phase = "correction" if previous is not None else "initial"
        prior = raw_by_phase.get("initial") if previous is not None else None
        envelope = _envelope(prepared, config, settings, feedback, prior)
        request_by_phase[phase] = envelope
        return envelope

    def invoke(feedback: tuple[CheckFinding, ...],
               previous: StructuredDocument | None) -> StructuredDocument:
        del feedback, previous
        raw = writer.author(request_by_phase[phase].request, config, settings)
        raw_by_phase[phase] = raw
        if prepared.packet.get("format") == "decision-joined-v3":
            from .interactive_wire_v3 import decode as decode_identity_wire

            return decode_identity_wire(raw, prepared, projection)
        if prepared.packet.get("format") == "decision-joined-v4":
            from .interactive_wire_v4 import decode as decode_compact_identity_wire

            return decode_compact_identity_wire(raw, prepared, projection)
        return decode_wire(raw, prepared.structured, projection)

    outcome = run_attempts(config, input_measurer, request_for=request_for, invoke=invoke,
        check=lambda document: check_structured_document(document, projection, prepared.structured),
        take_receipt=lambda: _receipt(writer))
    attempts = tuple(InteractiveAttempt(**vars(item),
        request=request_by_phase[item.phase].request,
        request_digest=content_digest(request_by_phase[item.phase].request),
        raw_wire=raw_by_phase.get(item.phase),
        returned_service_tier=_returned_tier(item.writer_receipt)) for item in outcome.attempts)
    selected = outcome.selected_attempt
    resolved = None
    resolved_digest = None
    if selected is not None:
        document = attempts[selected].document
        assert document is not None
        resolved = resolve_structured_document(document, prepared.structured, evidence,
                                               attempts[selected].findings)
        resolved_digest = content_digest(resolved.model_dump(mode="json"))
    artifact = InteractiveResultsArtifact(evidence=evidence, config=config, settings=settings,
        prepared=prepared, attempts=attempts, selected_attempt=selected,
        selection_reason=outcome.selection_reason, generation_outcome=outcome.generation_outcome,
        validation_outcome="unavailable" if selected is None else "annotated" if any(
            f.outcome == "failed" for f in attempts[selected].findings) else "clean",
        delivery_outcome="not_delivered" if selected is None else "delivered",
        resolved=resolved, resolved_digest=resolved_digest,
        runtime_seconds=0)
    return artifact.model_copy(update={"runtime_seconds": time.perf_counter() - started})


def replay_interactive_results(artifact: InteractiveResultsArtifact) -> ResolvedStructuredAnswer | None:
    projection = SolutionProjection.model_validate(artifact.evidence.source.model_dump(mode="json"))
    evidence = resolve_workspace(projection, fx_acquisition=artifact.evidence.fx_acquisition)
    if artifact.evidence != evidence:
        raise ValueError("saved interactive workspace differs from source")
    legacy = prepare_results(projection, artifact.config)
    verify_authoring_view(projection, legacy)
    packet = artifact.prepared.packet
    if "format" not in packet:
        profile: Literal["indexed-v1", "joined-v2", "joined-v3", "joined-v4"] = "indexed-v1"
    elif packet["format"] == "decision-joined-v2":
        profile = "joined-v2"
    elif packet["format"] == "decision-joined-v3":
        profile = "joined-v3"
    elif packet["format"] == "decision-joined-v4":
        profile = "joined-v4"
    else:
        raise ValueError("saved interactive packet format is unknown")
    prepared = prepare_interactive_results(projection, artifact.config, evidence,
                                           packet_profile=profile)
    if artifact.prepared != prepared:
        raise ValueError("saved interactive preparation differs from source")
    if len(artifact.attempts) > 2 or tuple(a.phase for a in artifact.attempts) != tuple(
            ("initial", "correction")[:len(artifact.attempts)]):
        raise ValueError("saved interactive attempt sequence is invalid")
    previous: StructuredDocument | None = None
    previous_wire: str | None = None
    feedback: tuple[CheckFinding, ...] = ()
    for index, attempt in enumerate(artifact.attempts):
        if index == 1 and (previous is None or not feedback):
            raise ValueError("saved interactive correction lacks failed draft")
        envelope = _envelope(prepared, artifact.config, artifact.settings, feedback, previous_wire)
        if (attempt.request != envelope.request or attempt.request_digest != content_digest(envelope.request)
                or attempt.input_bytes != envelope.input_bytes or
                attempt.estimated_total_tokens != envelope.estimated_total_tokens or
                attempt.prompt_digest != envelope.prompt_digest or
                attempt.schema_digest != envelope.schema_digest):
            raise ValueError("saved interactive request differs")
        count = attempt.input_token_receipt
        if count is not None and count.request_digest != attempt.request_digest:
            raise ValueError("saved interactive input count differs")
        if attempt.returned_service_tier != _returned_tier(attempt.writer_receipt):
            raise ValueError("saved interactive returned tier differs")
        response_text = _response_text(attempt.writer_receipt)
        if attempt.raw_wire is not None and response_text != attempt.raw_wire:
            raise ValueError("saved interactive wire differs from raw writer response")
        within = ((count.input_tokens + artifact.config.max_output_tokens +
                   artifact.config.prompt_overhead_tokens <= artifact.config.context_limit_tokens and
                   (artifact.config.max_input_tokens is None or
                    count.input_tokens <= artifact.config.max_input_tokens)) if count else
                  (envelope.estimated_total_tokens <= artifact.config.context_limit_tokens and
                   (artifact.config.max_input_tokens is None or
                    envelope.estimated_total_tokens - artifact.config.max_output_tokens <=
                    artifact.config.max_input_tokens)))
        if attempt.writer_called and not within:
            raise ValueError("saved interactive writer exceeded context")
        if attempt.outcome == "recoverable":
            if not attempt.writer_called or attempt.raw_wire is None or attempt.document is None:
                raise ValueError("saved interactive draft missing wire evidence")
            if attempt.error is not None or attempt.failure_subtype is not None:
                raise ValueError("saved interactive recoverable attempt has failure metadata")
            _validate_recoverable_response(attempt.writer_receipt)
            if profile == "joined-v3":
                from .interactive_wire_v3 import decode as decode_identity_wire

                document = decode_identity_wire(attempt.raw_wire, prepared, projection)
            elif profile == "joined-v4":
                from .interactive_wire_v4 import decode as decode_compact_identity_wire

                document = decode_compact_identity_wire(attempt.raw_wire, prepared, projection)
            else:
                document = decode_wire(attempt.raw_wire, prepared.structured, projection)
            if document != attempt.document or attempt.findings != check_structured_document(
                    document, projection, prepared.structured):
                raise ValueError("saved interactive wire or findings differ")
            previous, previous_wire = document, attempt.raw_wire
            feedback = tuple(f for f in attempt.findings if f.outcome == "failed")
        else:
            if attempt.document is not None or attempt.findings:
                raise ValueError("saved interactive failure has document")
            if attempt.outcome == "measurement_error" and attempt.writer_called:
                raise ValueError("saved interactive measurement error invoked writer")
            if not attempt.writer_called and not (
                attempt.outcome == "measurement_error" and count is None or
                attempt.error == "context_limit" and not within):
                raise ValueError("saved interactive noninvocation is invalid")
            if attempt.outcome == "api_error" and attempt.failure_subtype != "api_error":
                raise ValueError("saved interactive API failure subtype differs")
            if attempt.outcome == "generation_error" and attempt.writer_called and (
                    attempt.failure_subtype not in {"schema_error", "refusal", "incomplete"}):
                raise ValueError("saved interactive generation failure subtype differs")
            if attempt.raw_wire is not None and attempt.failure_subtype == "schema_error":
                try:
                    if profile == "joined-v3":
                        from .interactive_wire_v3 import decode as decode_identity_wire

                        decode_identity_wire(attempt.raw_wire, prepared, projection)
                    elif profile == "joined-v4":
                        from .interactive_wire_v4 import decode as decode_compact_identity_wire

                        decode_compact_identity_wire(attempt.raw_wire, prepared, projection)
                    else:
                        decode_wire(attempt.raw_wire, prepared.structured, projection)
                except (ValueError, TypeError, json.JSONDecodeError):
                    pass
                else:
                    raise ValueError("saved interactive schema failure decoded successfully")
            feedback = ()
    if len(artifact.attempts) == 1 and feedback:
        raise ValueError("saved interactive correction is missing")
    recoverable = [(i, a.findings) for i, a in enumerate(artifact.attempts)
                   if a.outcome == "recoverable"]
    if recoverable:
        selected, reason = choose_recoverable(tuple(recoverable))
        if artifact.selected_attempt != selected or artifact.selection_reason != reason:
            raise ValueError("saved interactive selection differs")
        attempt = artifact.attempts[selected]
        assert attempt.document is not None
        resolved = resolve_structured_document(attempt.document, prepared.structured,
                                               evidence, attempt.findings)
        if artifact.resolved != resolved or artifact.resolved_digest != content_digest(
                resolved.model_dump(mode="json")):
            raise ValueError("saved interactive answer differs")
        if (artifact.generation_outcome != "success" or artifact.delivery_outcome != "delivered" or
                artifact.validation_outcome != ("annotated" if any(
                    f.outcome == "failed" for f in attempt.findings) else "clean")):
            raise ValueError("saved interactive outcome differs")
        return resolved
    if (artifact.selected_attempt is not None or artifact.resolved is not None or
            artifact.resolved_digest is not None or artifact.delivery_outcome != "not_delivered" or
            artifact.validation_outcome != "unavailable"):
        raise ValueError("saved interactive undelivered outcome differs")
    terminal = artifact.attempts[-1] if artifact.attempts else None
    expected_generation = (
        "context_limit" if terminal is None or terminal.error == "context_limit" else
        "measurement_error" if terminal.outcome == "measurement_error" else
        "api_error" if terminal.outcome == "api_error" else "generation_error")
    expected_reason = ("context_limit" if expected_generation == "context_limit"
                       else "no_recoverable_draft")
    if (artifact.generation_outcome != expected_generation or
            artifact.selection_reason != expected_reason):
        raise ValueError("saved interactive generation outcome differs")
    if terminal is None:
        initial = _envelope(prepared, artifact.config, artifact.settings)
        if (initial.estimated_total_tokens <= artifact.config.context_limit_tokens and
                (artifact.config.max_input_tokens is None or
                 initial.estimated_total_tokens - artifact.config.max_output_tokens <=
                 artifact.config.max_input_tokens)):
            raise ValueError("saved interactive empty context outcome differs")
    return None
