"""Public, optimistic-concurrency controller for clarification sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from award_agent.clarification.blockers import (
    build_clarification_prompt,
    collect_blocking_requirements,
)
from award_agent.clarification.composer import (
    ClarificationPromptComposer,
    ClarificationPromptComposerInput,
    compose_prompt,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpreter,
    ClarificationAnswerInterpreterInput,
    ClarificationDiscourseAct,
    ClarificationSemanticFact,
    interpret_answer,
)
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.projection import project_initial_request
from award_agent.clarification.reducer import apply_amendments
from award_agent.clarification.semantic import (
    CompiledSemanticTemporalFact,
    SemanticOperation,
    SemanticTarget,
    SemanticTemporalCompileError,
    compile_temporal_ast,
)
from award_agent.domain import (
    AmendmentTarget,
    AnswerTurn,
    BlockingRequirement,
    ClarificationAnswerCommand,
    ClarificationIssue,
    ClarificationPrompt,
    ClarificationSession,
    ClarificationSessionLimits,
    ClarificationSessionRevision,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateWindow,
    EffectiveRequest,
    LocationAmendment,
    LocationRef,
    MessageSpan,
    PendingPromptTransition,
    PromptCompositionSource,
    RejectedFragment,
    RejectedFragmentReason,
    RequestUnderstandingResult,
    ResolutionOutcome,
    TemporalAmendment,
    TemporalContribution,
    TravelersAmendment,
    TypedAmendment,
)


class ClarificationCommandError(ValueError):
    """A caller command cannot be applied to this session state."""


class ClarificationPromptCompositionFailedError(RuntimeError):
    """A retryable composer failure prevented a prompt-bearing transition.

    A prompt is part of an immutable session revision.  Callers must retry the
    same command (or restart initial-session creation) with a healthy
    composer; no revision is returned or recorded when composition fails.
    """

    code = "prompt_composition_failed"


@dataclass(frozen=True)
class ClarificationTransition:
    """The recorded state transition and its resulting immutable session view."""

    session: ClarificationSession
    revision: ClarificationSessionRevision
    replayed: bool = False


@dataclass(frozen=True)
class ClarificationCompositionPending:
    """Caller-storable result when only LLM presentation remains retryable."""

    session: ClarificationSession
    pending: PendingPromptTransition


def _build_prompt(
    effective: EffectiveRequest,
    *,
    requirements: tuple[BlockingRequirement, ...],
    revision: int,
    composer: ClarificationPromptComposer | None,
    rejected_fragments: tuple[RejectedFragment, ...] = (),
    issues: tuple[ClarificationIssue, ...] | None = None,
) -> ClarificationPrompt | None:
    """Compose one prompt from the authoritative post-reduction issue set."""

    if not requirements:
        return None
    issues = issues or derive_clarification_issues(
        requirements, rejected_fragments=rejected_fragments
    )
    if composer is None:
        raise ClarificationPromptCompositionFailedError(
            "prompt_composition_failed: no clarification prompt composer is configured"
        )
    try:
        composition = compose_prompt(
            composer,
            ClarificationPromptComposerInput(
                requirements=requirements,
                issues=issues,
            ),
        )
    except Exception as exc:  # A model or contract failure is retryable and non-mutating.
        raise ClarificationPromptCompositionFailedError(
            "prompt_composition_failed: clarification prompt composition failed"
        ) from exc
    return build_clarification_prompt(
        effective,
        revision=revision,
        issues=issues,
        question_items=tuple(item.question for item in composition.question_items),
        composition_source=PromptCompositionSource.MODEL,
    )


def _composition_key(
    *,
    base_revision: int,
    requirements: tuple[BlockingRequirement, ...],
    issues: tuple[ClarificationIssue, ...],
) -> str:
    payload = {
        "base_revision": base_revision,
        "requirements": [item.model_dump(mode="json") for item in requirements],
        "issues": [item.model_dump(mode="json") for item in issues],
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def start_clarification(
    initial_result: RequestUnderstandingResult,
    *,
    session_id: str | None = None,
    limits: ClarificationSessionLimits | None = None,
    composer: ClarificationPromptComposer | None = None,
) -> ClarificationSession:
    """Create an additive session without modifying the frozen initial result."""

    effective = project_initial_request(initial_result.parsed_request)
    requirements = collect_blocking_requirements(effective)
    prompt = _build_prompt(
        effective,
        requirements=requirements,
        revision=0,
        composer=composer,
    )
    status = (
        ClarificationSessionStatus.AWAITING_ANSWER
        if prompt is not None
        else ClarificationSessionStatus.READY
    )
    revision = ClarificationSessionRevision(
        revision=0,
        effective_request=effective,
        prompt=prompt,
        status=status,
    )
    return ClarificationSession(
        session_id=session_id or f"clarification-{uuid4().hex}",
        initial_result=initial_result,
        limits=limits or ClarificationSessionLimits(),
        revisions=(revision,),
    )


def _session_at_revision(
    session: ClarificationSession,
    revision: ClarificationSessionRevision,
) -> ClarificationSession:
    return ClarificationSession(
        session_id=session.session_id,
        initial_result=session.initial_result,
        limits=session.limits,
        revisions=session.revisions[: revision.revision + 1],
    )


def _correction_eligible_targets(effective: EffectiveRequest) -> tuple[SemanticTarget, ...]:
    targets: list[SemanticTarget] = []
    if effective.origins:
        targets.append(SemanticTarget.ORIGIN)
    if effective.destinations:
        targets.append(SemanticTarget.DESTINATION)
    if effective.travelers is not None:
        targets.append(SemanticTarget.TRAVELERS)
    if effective.departure_window is not None:
        targets.append(SemanticTarget.DEPARTURE_WINDOW)
    if effective.return_window is not None:
        targets.append(SemanticTarget.RETURN_WINDOW)
    if effective.interpreted_duration is not None:
        targets.append(SemanticTarget.DURATION)
    return tuple(targets)


def _materialize_semantic_facts(
    facts: tuple[ClarificationSemanticFact, ...],
    *,
    effective: EffectiveRequest,
) -> tuple[
    tuple[TypedAmendment, ...],
    dict[str, tuple[TemporalContribution, ...]],
    tuple[RejectedFragment, ...],
]:
    """Compile independent receiver facts without reading answer semantics."""
    amendments: list[TypedAmendment] = []
    compiled: dict[str, tuple[TemporalContribution, ...]] = {}
    prior_compiled: dict[str, CompiledSemanticTemporalFact] = {}
    rejected: list[RejectedFragment] = []
    for fact in facts:
        correction = fact.operation is SemanticOperation.REPLACE
        amendment: TypedAmendment
        if fact.target in {SemanticTarget.ORIGIN, SemanticTarget.DESTINATION}:
            assert fact.location_kind is not None and fact.location_value is not None
            amendment = LocationAmendment(
                amendment_id=fact.fact_id,
                target=AmendmentTarget.ORIGIN
                if fact.target is SemanticTarget.ORIGIN
                else AmendmentTarget.DESTINATION,
                requirement_ids=fact.requirement_ids,
                span=fact.span,
                is_correction=correction,
                locations=(
                    LocationRef(
                        kind=fact.location_kind,
                        value=fact.location_value,
                        raw_text=fact.location_value,
                    ),
                ),
            )
        elif fact.target is SemanticTarget.TRAVELERS:
            assert fact.travelers is not None
            amendment = TravelersAmendment(
                amendment_id=fact.fact_id,
                target=AmendmentTarget.TRAVELERS,
                requirement_ids=fact.requirement_ids,
                span=fact.span,
                is_correction=correction,
                travelers=fact.travelers,
            )
        else:
            assert fact.temporal is not None
            if fact.target is SemanticTarget.DEPARTURE_WINDOW:
                amendment = TemporalAmendment(
                    amendment_id=fact.fact_id,
                    target=AmendmentTarget.DEPARTURE,
                    requirement_ids=fact.requirement_ids,
                    span=fact.span,
                    is_correction=correction,
                    temporal_text=fact.span.text,
                )
            else:
                amendment = TemporalAmendment(
                    amendment_id=fact.fact_id,
                    target=AmendmentTarget.RETURN_OR_DURATION,
                    requirement_ids=fact.requirement_ids,
                    span=fact.span,
                    is_correction=correction,
                    temporal_text=fact.span.text,
                )
            try:
                compiled_fact = compile_temporal_ast(
                    amendment_id=fact.fact_id,
                    target=fact.target,
                    ast=fact.temporal,
                    span=fact.span,
                    context=effective.context,
                    prior_compiled_facts=prior_compiled,
                )
            except SemanticTemporalCompileError:
                rejected.append(
                    RejectedFragment(
                        span=fact.span,
                        reason=RejectedFragmentReason.AMBIGUOUS,
                        detail="receiver semantic fact could not be compiled",
                        requirement_ids=fact.requirement_ids,
                        reason_code="receiver.semantic_compile",
                    )
                )
                continue
            compiled[fact.fact_id] = (compiled_fact.contribution,)
            prior_compiled[fact.fact_id] = compiled_fact
        amendments.append(amendment)
    return tuple(amendments), compiled, tuple(rejected)


def _amendment_field(amendment: TypedAmendment) -> str | None:
    return {
        "origin": "origin",
        "destination": "destination",
        "travelers": "travelers",
        "departure": "departure",
        "return_or_duration": "return_or_duration",
    }.get(amendment.target.value)


def _is_supported_correction(amendment: TypedAmendment, effective: EffectiveRequest) -> bool:
    field = _amendment_field(amendment)
    if field == "origin":
        return bool(effective.origins)
    if field == "destination":
        return bool(effective.destinations)
    if field == "travelers":
        return effective.travelers is not None
    if field == "departure":
        return effective.departure_window is not None
    if field == "return_or_duration":
        return effective.return_window is not None or effective.interpreted_duration is not None
    # A date-conflict amendment is scoped by an active conflict, never used to
    # smuggle a new unconstrained field into a session.
    return bool(effective.conflicts)


def _filter_corrections_and_collisions(
    amendments: tuple[TypedAmendment, ...],
    *,
    effective: EffectiveRequest,
) -> tuple[tuple[TypedAmendment, ...], tuple[RejectedFragment, ...]]:
    """Reject unsupported corrections; receiver contract owns fact uniqueness."""
    accepted: list[TypedAmendment] = []
    rejected: list[RejectedFragment] = []
    for amendment in amendments:
        if amendment.is_correction and not _is_supported_correction(amendment, effective):
            rejected.append(
                RejectedFragment(
                    span=amendment.span,
                    reason=RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION,
                    detail="a correction can revise only an already-resolved supported field",
                    requirement_ids=amendment.requirement_ids,
                )
            )
        else:
            accepted.append(amendment)
    return tuple(accepted), tuple(rejected)


def _semantic_effective_fingerprint(effective: EffectiveRequest) -> tuple[object, ...]:
    """Projection meaning used for no-progress; deliberately excludes provenance."""

    def locations(values: tuple[LocationRef, ...]) -> tuple[tuple[str, str], ...]:
        return tuple((item.kind.value, item.value) for item in values)

    def window(value: DateWindow | None) -> tuple[object, object, str] | None:
        return None if value is None else (value.start, value.end, value.precision.value)

    duration = effective.interpreted_duration
    return (
        effective.travelers,
        locations(effective.origins),
        locations(effective.destinations),
        window(effective.departure_window),
        window(effective.return_window),
        None if duration is None else (duration.minimum_days, duration.maximum_days),
        tuple(item.value for item in effective.cabins),
        tuple(item.value for item in effective.search_modes),
        effective.repositioning_allowed,
        effective.hard_constraints,
        tuple(
            (
                item.kind.value,
                window(item.date_window),
                None
                if item.interpreted_duration is None
                else (
                    item.interpreted_duration.minimum_days,
                    item.interpreted_duration.maximum_days,
                ),
            )
            for item in effective.temporal_contributions
        ),
        tuple((item.code, tuple(item.fields)) for item in effective.conflicts),
        tuple((item.field, item.reason.value) for item in effective.unknowns),
    )


def _consecutive_no_progress(
    session: ClarificationSession,
    effective: EffectiveRequest,
    blocker_ids: tuple[str, ...],
) -> int:
    current_blockers = tuple(
        requirement.requirement_id
        for requirement in collect_blocking_requirements(session.effective_request)
    )
    if (
        _semantic_effective_fingerprint(effective)
        != _semantic_effective_fingerprint(session.effective_request)
        or blocker_ids != current_blockers
    ):
        return 0
    # The candidate transition is itself one no-progress turn. Then count
    # immediately preceding processed answers with the same fingerprint.
    count = 1
    prior_effective = effective
    prior_blockers = blocker_ids
    # Revision zero is the initial snapshot, not a processed answer; it must
    # not make the first no-progress user response consume both allowed turns.
    for revision in reversed(session.revisions[1:]):
        current_blockers = tuple(
            requirement.requirement_id
            for requirement in collect_blocking_requirements(revision.effective_request)
        )
        if (
            _semantic_effective_fingerprint(revision.effective_request)
            != _semantic_effective_fingerprint(prior_effective)
            or current_blockers != prior_blockers
        ):
            break
        count += 1
        prior_effective = revision.effective_request
        prior_blockers = current_blockers
    return count


def apply_clarification_answer(
    session: ClarificationSession,
    command: ClarificationAnswerCommand,
    interpreter: ClarificationAnswerInterpreter,
    composer: ClarificationPromptComposer | None = None,
) -> ClarificationTransition | ClarificationCompositionPending:
    """Apply one answer atomically, or raise without writing a new revision.

    Replay lookup intentionally precedes revision freshness and terminal checks;
    a replay returns the originally recorded session prefix and transition.
    """

    if command.session_id != session.session_id:
        raise ClarificationCommandError("answer command session ID does not match the session")
    for revision in session.revisions[1:]:
        assert revision.answer_turn is not None
        if revision.answer_turn.message.message_id == command.message_id:
            if revision.answer_turn.message.text != command.text:
                raise ClarificationCommandError("message ID was already used with different text")
            return ClarificationTransition(
                session=_session_at_revision(session, revision), revision=revision, replayed=True
            )

    current = session.current_revision
    if current.status is not ClarificationSessionStatus.AWAITING_ANSWER:
        raise ClarificationCommandError("terminal clarification sessions do not accept new answers")
    if command.expected_revision != current.revision:
        raise ClarificationCommandError("answer command revision is stale")
    assert current.prompt is not None
    if command.prompt_id != current.prompt.prompt_id:
        raise ClarificationCommandError(
            "answer command prompt ID does not match the pending prompt"
        )

    answer_span = MessageSpan(
        message_id=command.message_id,
        start=0,
        end=len(command.text),
        text=command.text,
    )
    answer_turn = AnswerTurn(
        turn_number=current.revision + 1,
        expected_revision=current.revision,
        prompt_id=current.prompt.prompt_id,
        message=answer_span,
    )
    interpretation = interpret_answer(
        interpreter,
        ClarificationAnswerInterpreterInput(
            message_id=command.message_id,
            text=command.text,
            ordered_requirements=current.prompt.requirements,
            correction_eligible_targets=_correction_eligible_targets(current.effective_request),
        ),
    )
    if interpretation.discourse_act is ClarificationDiscourseAct.CANCEL:
        next_revision = ClarificationSessionRevision(
            revision=current.revision + 1,
            effective_request=current.effective_request,
            answer_turn=answer_turn,
            outcome=ResolutionOutcome(),
            status=ClarificationSessionStatus.STOPPED,
            stop_reason=ClarificationStopReason.CANCELLED,
        )
        next_session = ClarificationSession(
            session_id=session.session_id,
            initial_result=session.initial_result,
            limits=session.limits,
            revisions=session.revisions + (next_revision,),
        )
        return ClarificationTransition(session=next_session, revision=next_revision)

    materialized, compiled_temporal_contributions, compilation_rejections = (
        _materialize_semantic_facts(interpretation.facts, effective=current.effective_request)
    )
    scoped, scope_rejections = _filter_corrections_and_collisions(
        materialized,
        effective=current.effective_request,
    )
    accepted = scoped
    effective = apply_amendments(
        current.effective_request,
        accepted,
        answer_text=command.text,
        requirements=current.prompt.requirements,
        compiled_temporal_contributions=(compiled_temporal_contributions),
    )
    rejected = (
        tuple(
            RejectedFragment(
                span=item.span,
                reason=RejectedFragmentReason.AMBIGUOUS,
                detail="receiver could not resolve this answer fragment",
                requirement_ids=item.requirement_ids,
                reason_code=f"receiver.{item.reason}",
            )
            for item in interpretation.unresolved_fragments
        )
        + compilation_rejections
        + scope_rejections
    )
    blocker_ids = tuple(
        requirement.requirement_id for requirement in collect_blocking_requirements(effective)
    )
    unsupported = any(
        fragment.reason is RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION
        for fragment in rejected
    )
    next_number = current.revision + 1
    if unsupported:
        status = ClarificationSessionStatus.STOPPED
        stop_reason = ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION
        prompt = None
    elif not blocker_ids:
        status = ClarificationSessionStatus.READY
        stop_reason = None
        prompt = None
    elif (
        _consecutive_no_progress(session, effective, blocker_ids)
        >= session.limits.max_consecutive_no_progress
    ):
        status = ClarificationSessionStatus.STOPPED
        stop_reason = ClarificationStopReason.NO_PROGRESS_LIMIT
        prompt = None
    elif next_number >= session.limits.max_answer_turns:
        status = ClarificationSessionStatus.STOPPED
        stop_reason = ClarificationStopReason.ANSWER_TURN_LIMIT
        prompt = None
    else:
        status = ClarificationSessionStatus.AWAITING_ANSWER
        stop_reason = None
        requirements = collect_blocking_requirements(effective)
        issues = derive_clarification_issues(requirements, rejected_fragments=rejected)
        try:
            prompt = _build_prompt(
                effective,
                requirements=requirements,
                revision=next_number,
                composer=composer,
                issues=issues,
            )
        except ClarificationPromptCompositionFailedError:
            return ClarificationCompositionPending(
                session=session,
                pending=PendingPromptTransition(
                    session_id=session.session_id,
                    base_revision=current.revision,
                    revision=next_number,
                    answer_turn=answer_turn,
                    effective_request=effective,
                    outcome=ResolutionOutcome(
                        accepted_amendments=accepted, rejected_fragments=rejected
                    ),
                    requirements=requirements,
                    issues=issues,
                    composition_key=_composition_key(
                        base_revision=current.revision,
                        requirements=requirements,
                        issues=issues,
                    ),
                ),
            )
        assert prompt is not None
    next_revision = ClarificationSessionRevision(
        revision=next_number,
        effective_request=effective,
        answer_turn=answer_turn,
        outcome=ResolutionOutcome(accepted_amendments=accepted, rejected_fragments=rejected),
        prompt=prompt,
        status=status,
        stop_reason=stop_reason,
    )
    next_session = ClarificationSession(
        session_id=session.session_id,
        initial_result=session.initial_result,
        limits=session.limits,
        revisions=session.revisions + (next_revision,),
    )
    return ClarificationTransition(session=next_session, revision=next_revision)


def retry_prompt_composition(
    session: ClarificationSession,
    pending: PendingPromptTransition,
    composer: ClarificationPromptComposer,
) -> ClarificationTransition | ClarificationCompositionPending:
    """Complete a previously reduced answer without invoking its receiver again."""

    current = session.current_revision
    if pending.session_id != session.session_id or pending.base_revision != current.revision:
        raise ClarificationCommandError(
            "pending prompt transition does not match the current session"
        )
    if current.status is not ClarificationSessionStatus.AWAITING_ANSWER:
        raise ClarificationCommandError(
            "only an awaiting-answer session can retry prompt composition"
        )
    if current.prompt is None or pending.answer_turn.prompt_id != current.prompt.prompt_id:
        raise ClarificationCommandError(
            "pending prompt transition does not match the pending prompt"
        )
    expected_key = _composition_key(
        base_revision=pending.base_revision,
        requirements=pending.requirements,
        issues=pending.issues,
    )
    if pending.composition_key != expected_key:
        raise ClarificationCommandError("pending prompt transition has an invalid composition key")
    try:
        prompt = _build_prompt(
            pending.effective_request,
            requirements=pending.requirements,
            revision=pending.revision,
            composer=composer,
            issues=pending.issues,
        )
    except ClarificationPromptCompositionFailedError:
        return ClarificationCompositionPending(session=session, pending=pending)
    assert prompt is not None
    revision = ClarificationSessionRevision(
        revision=pending.revision,
        effective_request=pending.effective_request,
        answer_turn=pending.answer_turn,
        outcome=pending.outcome,
        prompt=prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    next_session = ClarificationSession(
        session_id=session.session_id,
        initial_result=session.initial_result,
        limits=session.limits,
        revisions=session.revisions + (revision,),
    )
    return ClarificationTransition(session=next_session, revision=revision)


__all__ = [
    "ClarificationCommandError",
    "ClarificationCompositionPending",
    "ClarificationPromptCompositionFailedError",
    "ClarificationTransition",
    "apply_clarification_answer",
    "retry_prompt_composition",
    "start_clarification",
]
