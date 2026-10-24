"""Fixed bounded Results authoring attempts shared by document versions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from award_agent.providers.contracts import content_digest

from .contracts import (
    CheckFinding,
    InputTokenReceipt,
    ResultsConfig,
    ResultsInputMeasurer,
    ResultsWriterError,
    WriterReceipt,
)


@dataclass(frozen=True)
class RequestEnvelope:
    request: dict[str, object]
    input_bytes: int
    estimated_total_tokens: int
    prompt_digest: str
    schema_digest: str


@dataclass(frozen=True)
class RunAttempt[D]:
    phase: Literal["initial", "correction"]
    outcome: Literal["recoverable", "api_error", "generation_error", "measurement_error"]
    document: D | None = None
    findings: tuple[CheckFinding, ...] = ()
    error: str | None = None
    failure_subtype: Literal["api_error", "refusal", "incomplete", "schema_error"] | None = None
    writer_receipt: WriterReceipt | None = None
    input_bytes: int = 0
    estimated_total_tokens: int = 0
    prompt_digest: str | None = None
    schema_digest: str | None = None
    writer_called: bool = True
    input_token_receipt: InputTokenReceipt | None = None


@dataclass(frozen=True)
class RunOutcome[D]:
    attempts: tuple[RunAttempt[D], ...]
    selected_attempt: int | None
    selection_reason: str
    generation_outcome: Literal["success", "api_error", "generation_error", "context_limit", "measurement_error"]


def choose_recoverable(
    findings_by_index: tuple[tuple[int, tuple[CheckFinding, ...]], ...],
) -> tuple[int, str]:
    """Choose the draft with fewer material failures; correction wins a tie."""
    selected, _ = min(findings_by_index, key=lambda pair: (
        sum(f.outcome == "failed" for f in pair[1]), -pair[0]))
    if len(findings_by_index) == 1:
        return selected, "initial_only"
    initial_failures = sum(f.outcome == "failed" for f in findings_by_index[0][1])
    correction_failures = sum(f.outcome == "failed" for f in findings_by_index[1][1])
    if selected == 1:
        return selected, ("correction_fewer_failures" if correction_failures < initial_failures
                          else "correction_tie")
    return selected, "initial_fewer_failures"


def _selection[D](attempts: tuple[RunAttempt[D], ...]) -> tuple[int | None, str,
                                                              Literal["success", "api_error", "generation_error", "measurement_error"]]:
    recoverable = [(index, attempt) for index, attempt in enumerate(attempts)
                   if attempt.outcome == "recoverable" and attempt.document is not None]
    if not recoverable:
        terminal = attempts[-1] if attempts else None
        generation: Literal["measurement_error", "api_error", "generation_error"] = (
            "measurement_error" if terminal and terminal.outcome == "measurement_error"
            else "api_error" if terminal and terminal.outcome == "api_error"
            else "generation_error")
        return None, "no_recoverable_draft", generation
    selected, reason = choose_recoverable(tuple(
        (index, attempt.findings) for index, attempt in recoverable))
    return selected, reason, "success"


def run_attempts[D](
    config: ResultsConfig,
    input_measurer: ResultsInputMeasurer | None,
    *,
    request_for: Callable[[tuple[CheckFinding, ...], D | None], RequestEnvelope],
    invoke: Callable[[tuple[CheckFinding, ...], D | None], D],
    check: Callable[[D], tuple[CheckFinding, ...]],
    take_receipt: Callable[[], WriterReceipt | None],
) -> RunOutcome[D]:
    attempts: list[RunAttempt[D]] = []
    feedback: tuple[CheckFinding, ...] = ()
    previous: D | None = None
    for phase in ("initial", "correction"):
        envelope = request_for(feedback, previous)
        size = envelope.input_bytes
        total = envelope.estimated_total_tokens
        prompt_digest = envelope.prompt_digest
        schema_digest = envelope.schema_digest
        token_receipt: InputTokenReceipt | None = None
        if input_measurer is not None:
            try:
                measured = input_measurer.measure(envelope.request, config)
                token_receipt = InputTokenReceipt.model_validate(measured.model_dump(mode="json"))
                if token_receipt.request_digest != content_digest(envelope.request):
                    raise ValueError("input token receipt request digest differs")
            except (AttributeError, ResultsWriterError, ValueError, TypeError):
                attempts.append(RunAttempt(phase=phase, outcome="measurement_error",
                    error="input_token_measurement_failed", input_bytes=size,
                    estimated_total_tokens=total, prompt_digest=prompt_digest,
                    schema_digest=schema_digest, writer_called=False))
                break
        counted_overflow = token_receipt is not None and (
            (config.max_input_tokens is not None and
             token_receipt.input_tokens > config.max_input_tokens) or
            token_receipt.input_tokens + config.max_output_tokens +
            config.prompt_overhead_tokens > config.context_limit_tokens)
        byte_overflow = token_receipt is None and input_measurer is None and (
            total > config.context_limit_tokens or
            (config.max_input_tokens is not None and
             total - config.max_output_tokens > config.max_input_tokens))
        if counted_overflow or byte_overflow:
            if not attempts:
                if token_receipt is not None:
                    attempts.append(RunAttempt(phase="initial", outcome="generation_error",
                        error="context_limit", input_bytes=size, estimated_total_tokens=total,
                        prompt_digest=prompt_digest, schema_digest=schema_digest,
                        writer_called=False, input_token_receipt=token_receipt))
                return RunOutcome(tuple(attempts), None, "context_limit", "context_limit")
            attempts.append(RunAttempt(phase="correction", outcome="generation_error",
                error="context_limit", input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest,
                writer_called=False, input_token_receipt=token_receipt))
            break
        try:
            document = invoke(feedback, previous)
            findings = check(document)
            attempts.append(RunAttempt(phase=phase, outcome="recoverable",
                document=document, findings=findings, writer_receipt=take_receipt(),
                input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest,
                input_token_receipt=token_receipt))
            failed = tuple(item for item in findings if item.outcome == "failed")
            if phase == "initial" and failed:
                feedback = failed
                previous = document
                continue
            break
        except ResultsWriterError as exc:
            outcome: Literal["api_error", "generation_error"] = (
                "api_error" if exc.outcome == "api_error" else "generation_error")
            receipt = take_receipt() or WriterReceipt(raw_response=exc.raw_response)
            attempts.append(RunAttempt(phase=phase, outcome=outcome,
                error=str(exc), failure_subtype=exc.outcome, writer_receipt=receipt,
                input_bytes=size, estimated_total_tokens=total,
                prompt_digest=prompt_digest, schema_digest=schema_digest,
                input_token_receipt=token_receipt))
            break
        except (ValueError, TypeError) as exc:
            attempts.append(RunAttempt(phase=phase, outcome="generation_error",
                error=f"schema_error: {exc}", failure_subtype="schema_error",
                writer_receipt=take_receipt(), input_bytes=size,
                estimated_total_tokens=total, prompt_digest=prompt_digest,
                schema_digest=schema_digest, input_token_receipt=token_receipt))
            break
    selected, reason, generation = _selection(tuple(attempts))
    return RunOutcome(tuple(attempts), selected, reason, generation)
