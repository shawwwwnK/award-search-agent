"""Public, optimistic-concurrency controller for clarification sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from award_agent.clarification.blockers import (
    build_clarification_prompt,
    collect_blocking_requirements,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpreter,
    ClarificationAnswerInterpreterInput,
    interpret_answer,
)
from award_agent.clarification.projection import project_initial_request
from award_agent.clarification.reducer import apply_amendments
from award_agent.clarification.temporal import (
    AmbiguousClarificationTemporalAnswer,
    ClarificationTemporalNormalizationError,
    UnsupportedClarificationTemporalAnswer,
)
from award_agent.domain import (
    AnswerTurn,
    BlockingRequirement,
    ClarificationAnswerCommand,
    ClarificationSession,
    ClarificationSessionLimits,
    ClarificationSessionRevision,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateWindow,
    EffectiveRequest,
    LocationRef,
    MessageSpan,
    RejectedFragment,
    RejectedFragmentReason,
    RequestContext,
    RequestUnderstandingResult,
    ResolutionOutcome,
    TemporalAmendment,
    TypedAmendment,
)


class ClarificationCommandError(ValueError):
    """A caller command cannot be applied to this session state."""


@dataclass(frozen=True)
class ClarificationTransition:
    """The recorded state transition and its resulting immutable session view."""

    session: ClarificationSession
    revision: ClarificationSessionRevision
    replayed: bool = False


def start_clarification(
    initial_result: RequestUnderstandingResult,
    *,
    session_id: str | None = None,
    limits: ClarificationSessionLimits | None = None,
) -> ClarificationSession:
    """Create an additive session without modifying the frozen initial result."""

    effective = project_initial_request(initial_result.parsed_request)
    prompt = build_clarification_prompt(effective, revision=0)
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


def _is_cancel(text: str) -> bool:
    normalized = re.sub(r"[\s,.!?]+", " ", text.casefold().replace("’", "'")).strip()
    return re.fullmatch(
        r"(?:please )?(?:cancel(?: this)?|stop(?: here)?|never ?mind|no(?: thanks| thank you)?|i (?:do not|don't) want to continue)",
        normalized,
    ) is not None


def _rejected_temporal_fragment(
    amendment: TemporalAmendment,
    error: Exception,
) -> RejectedFragment:
    if isinstance(error, AmbiguousClarificationTemporalAnswer):
        reason = RejectedFragmentReason.AMBIGUOUS
    elif isinstance(error, UnsupportedClarificationTemporalAnswer):
        reason = RejectedFragmentReason.INVALID
    else:
        reason = RejectedFragmentReason.INVALID
    return RejectedFragment(span=amendment.span, reason=reason, detail=str(error))


def _validate_temporal_subset(
    amendments: tuple[TypedAmendment, ...],
    *,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    context: RequestContext,
) -> tuple[tuple[TypedAmendment, ...], tuple[RejectedFragment, ...]]:
    """Keep independent non-temporal siblings when one answer date is ambiguous."""

    from award_agent.clarification.temporal import normalize_temporal_amendment

    accepted: list[TypedAmendment] = []
    rejected: list[RejectedFragment] = []
    for amendment in amendments:
        if not isinstance(amendment, TemporalAmendment):
            accepted.append(amendment)
            continue
        try:
            normalize_temporal_amendment(
                amendment,
                answer_text=answer_text,
                requirements=requirements,
                context=context,
            )
        except (
            AmbiguousClarificationTemporalAnswer,
            ClarificationTemporalNormalizationError,
            UnsupportedClarificationTemporalAnswer,
        ) as exc:
            rejected.append(_rejected_temporal_fragment(amendment, exc))
        else:
            accepted.append(amendment)
    return tuple(accepted), tuple(rejected)


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
    """Reject unsupported corrections and non-independent same-field writes."""

    counts: dict[str, int] = {}
    for amendment in amendments:
        field = _amendment_field(amendment)
        if field is not None:
            counts[field] = counts.get(field, 0) + 1
    accepted: list[TypedAmendment] = []
    rejected: list[RejectedFragment] = []
    for amendment in amendments:
        field = _amendment_field(amendment)
        if field is not None and counts[field] > 1:
            rejected.append(
                RejectedFragment(
                    span=amendment.span,
                    reason=RejectedFragmentReason.AMBIGUOUS,
                    detail="multiple amendments in one answer target the same field",
                )
            )
        elif amendment.is_correction and not _is_supported_correction(amendment, effective):
            rejected.append(
                RejectedFragment(
                    span=amendment.span,
                    reason=RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION,
                    detail="a correction can revise only an already-resolved supported field",
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
    if _semantic_effective_fingerprint(effective) != _semantic_effective_fingerprint(
        session.effective_request
    ) or blocker_ids != current_blockers:
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
            requirement.requirement_id for requirement in collect_blocking_requirements(revision.effective_request)
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
) -> ClarificationTransition:
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
        raise ClarificationCommandError("answer command prompt ID does not match the pending prompt")

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
    if _is_cancel(command.text):
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

    interpretation = interpret_answer(
        interpreter,
        ClarificationAnswerInterpreterInput(
            message_id=command.message_id,
            text=command.text,
            requirements=current.prompt.requirements,
        ),
    )
    scoped, scope_rejections = _filter_corrections_and_collisions(
        interpretation.amendments,
        effective=current.effective_request,
    )
    accepted, temporal_rejections = _validate_temporal_subset(
        scoped,
        answer_text=command.text,
        requirements=current.prompt.requirements,
        context=current.effective_request.context,
    )
    effective = apply_amendments(
        current.effective_request,
        accepted,
        answer_text=command.text,
        requirements=current.prompt.requirements,
    )
    rejected = interpretation.rejected_fragments + scope_rejections + temporal_rejections
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
    elif _consecutive_no_progress(session, effective, blocker_ids) >= session.limits.max_consecutive_no_progress:
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
        prompt = build_clarification_prompt(effective, revision=next_number)
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


__all__ = [
    "ClarificationCommandError",
    "ClarificationTransition",
    "apply_clarification_answer",
    "start_clarification",
]
