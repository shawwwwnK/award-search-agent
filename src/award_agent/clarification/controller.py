"""Public, optimistic-concurrency controller for clarification sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast
from uuid import uuid4

from award_agent.clarification.blockers import (
    build_clarification_prompt,
    collect_blocking_requirements,
)
from award_agent.clarification.composer import (
    ClarificationPromptComposer,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreter,
    ClarificationAnswerInterpreterInput,
    interpret_answer,
)
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.projection import project_initial_request
from award_agent.clarification.reducer import apply_amendments
from award_agent.clarification.temporal import (
    AmbiguousClarificationTemporalAnswer,
    ClarificationTemporalNormalizationError,
    UnsupportedClarificationTemporalAnswer,
    recover_ordered_numeric_date_pair,
)
from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationError,
    ClarificationTemporalApproximationProjection,
    compile_temporal_approximation_selection,
    harvest_temporal_approximation_projection,
    unresolved_approximation_rejections,
)
from award_agent.clarification.temporal_templates import (
    ClarificationTemporalTemplateError,
    compile_temporal_template_selection,
    harvest_temporal_template_projection,
    target_for_template_candidate,
    unresolved_template_rejections,
)
from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    AnswerTurn,
    BlockingRequirement,
    ClarificationAnswerCommand,
    ClarificationPrompt,
    ClarificationSession,
    ClarificationSessionLimits,
    ClarificationSessionRevision,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateWindow,
    EffectiveRequest,
    LocationRef,
    MessageSpan,
    PromptCompositionSource,
    RejectedFragment,
    RejectedFragmentReason,
    RequestContext,
    RequestUnderstandingResult,
    ResolutionOutcome,
    TemporalAmendment,
    TemporalContribution,
    TemporalContributionKind,
    TemporalTemplateProvenance,
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


def _build_prompt(
    effective: EffectiveRequest,
    *,
    requirements: tuple[BlockingRequirement, ...],
    revision: int,
    composer: ClarificationPromptComposer | None,
    receiver_interpretation: ClarificationAnswerInterpretation | None = None,
    rejected_fragments: tuple[RejectedFragment, ...] = (),
) -> ClarificationPrompt | None:
    """Render the authoritative prompt without a second model round trip.

    The initial prompt is deterministic.  On later turns, presentation may
    reuse question items returned by the answer receiver only after the
    reducer has recomputed the exact remaining requirement IDs.  ``composer``
    remains an ignored compatibility parameter for callers from ADR 0012; it
    must never be invoked here.
    """

    if not requirements:
        return None
    issues = derive_clarification_issues(requirements, rejected_fragments=rejected_fragments)
    del composer
    expected_ids = tuple(requirement.requirement_id for requirement in requirements)
    if (
        receiver_interpretation is None
        or receiver_interpretation.next_question_requirement_ids != expected_ids
        or not receiver_interpretation.next_question_items
    ):
        return build_clarification_prompt(
            effective,
            revision=revision,
            issues=issues,
            composition_source=PromptCompositionSource.FALLBACK,
            fallback_code=(
                "receiver.no_usable_followup"
                if receiver_interpretation is not None
                else None
            ),
        )
    return build_clarification_prompt(
        effective,
        revision=revision,
        issues=issues,
        question_items=receiver_interpretation.next_question_items,
        composition_source=PromptCompositionSource.MODEL,
    )


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


def _is_cancel(text: str) -> bool:
    normalized = re.sub(r"[\s,.!?]+", " ", text.casefold().replace("’", "'")).strip()
    return (
        re.fullmatch(
            r"(?:please )?(?:cancel(?: this)?|stop(?: here)?|never ?mind|no(?: thanks| thank you)?|i (?:do not|don't) want to continue)",
            normalized,
        )
        is not None
    )


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
    return RejectedFragment(
        span=amendment.span,
        reason=reason,
        detail=str(error),
        requirement_ids=amendment.requirement_ids,
    )


def _validate_temporal_subset(
    amendments: tuple[TypedAmendment, ...],
    *,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    context: RequestContext,
    precompiled_amendment_ids: frozenset[str] = frozenset(),
) -> tuple[tuple[TypedAmendment, ...], tuple[RejectedFragment, ...]]:
    """Keep independent non-temporal siblings when one answer date is ambiguous."""

    from award_agent.clarification.temporal import normalize_temporal_amendment

    accepted: list[TypedAmendment] = []
    rejected: list[RejectedFragment] = []
    for amendment in amendments:
        if not isinstance(amendment, TemporalAmendment):
            accepted.append(amendment)
            continue
        if amendment.amendment_id in precompiled_amendment_ids:
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


def _recover_ordered_date_pair(
    interpretation: ClarificationAnswerInterpretation,
    *,
    message_id: str,
    text: str,
    requirements: tuple[BlockingRequirement, ...],
) -> ClarificationAnswerInterpretation:
    """Accept the closed literal pair grammar even if the receiver rejected it.

    The receiver is prompted to emit the two narrow amendments itself. This
    deterministic recovery protects the simple, fully-grounded case from a
    conservative model classification, without broadening any ambiguous date
    grammar.
    """

    if any(isinstance(item, TemporalAmendment) for item in interpretation.amendments):
        return interpretation
    recovered = recover_ordered_numeric_date_pair(
        message_id=message_id,
        text=text,
        requirements=requirements,
    )
    if not recovered:
        return interpretation
    recovered_requirement_ids = {
        requirement_id for amendment in recovered for requirement_id in amendment.requirement_ids
    }
    rejected = tuple(
        fragment
        for fragment in interpretation.rejected_fragments
        if not (
            set(fragment.requirement_ids) == recovered_requirement_ids
            and fragment.span.start <= recovered[0].span.start
            and fragment.span.end >= recovered[-1].span.end
        )
    )
    return interpretation.model_copy(
        update={
            "amendments": interpretation.amendments + recovered,
            "rejected_fragments": rejected,
        }
    )


def _exclude_registry_covered_legacy_temporal_amendments(
    amendments: tuple[TypedAmendment, ...],
    *,
    interpretation: object,
) -> tuple[tuple[TypedAmendment, ...], tuple[RejectedFragment, ...]]:
    """Route registered surface grammar exclusively through the registry.

    The model may still use the legacy temporal amendment shape for facts that
    the registry does not harvest (exact dates, named months, durations).  It
    must not get two competing ways to process a registered relative phrase.
    """

    from award_agent.clarification.interpreter import ClarificationAnswerInterpretation

    assert isinstance(interpretation, ClarificationAnswerInterpretation)
    ranges = tuple(
        (item.span.start, item.span.end)
        for item in interpretation.temporal_template_selection.selected
    ) + tuple(
        (item.span.start, item.span.end)
        for item in interpretation.temporal_template_selection.unresolved
    )
    accepting_ranges = tuple(
        (item.span.start, item.span.end)
        for item in interpretation.temporal_approximation_selection.selected
    ) + tuple(
        (item.span.start, item.span.end)
        for item in interpretation.temporal_approximation_selection.unresolved
    )
    accepted: list[TypedAmendment] = []
    rejected: list[RejectedFragment] = []
    for amendment in amendments:
        if isinstance(amendment, TemporalAmendment) and any(
            amendment.span.start < end and start < amendment.span.end for start, end in accepting_ranges
        ):
            # The accepting registry owns these words. It emits one canonical
            # rejection only if it cannot safely classify them; the legacy
            # shape must not create a second, conflicting rejection.
            continue
        if isinstance(amendment, TemporalAmendment) and any(
            amendment.span.start < end and start < amendment.span.end for start, end in ranges
        ):
            rejected.append(
                RejectedFragment(
                    span=amendment.span,
                    reason=RejectedFragmentReason.INVALID,
                    detail=(
                        "registered temporal wording must be classified through the approved "
                        "template registry"
                    ),
                    requirement_ids=amendment.requirement_ids,
                )
            )
        else:
            accepted.append(amendment)
    return tuple(accepted), tuple(rejected)


def _overlaps(left: MessageSpan, right: MessageSpan) -> bool:
    return left.start < right.end and right.start < left.end


def _registry_rejected_fragment(
    *,
    span: MessageSpan,
    requirement_ids: tuple[str, ...],
    classification: Literal["ambiguous", "unsupported"],
    reason_code: str,
) -> RejectedFragment:
    """Translate a closed registry result into the shared issue source."""

    reason = (
        RejectedFragmentReason.AMBIGUOUS
        if classification == "ambiguous"
        else RejectedFragmentReason.INVALID
    )
    return RejectedFragment(
        span=span,
        reason=reason,
        detail="temporal wording needs clarification",
        requirement_ids=requirement_ids,
        reason_code=reason_code,
    )


def _reconcile_temporal_registries(interpretation: object) -> tuple[RejectedFragment, ...]:
    """Give overlapping temporal surface text one authoritative outcome.

    The accepting registry is newer policy.  An accepted approximation masks a
    v1 unresolved classification over the same words; an accepting unresolved
    span is likewise the sole canonical rejection.  Two positive, overlapping
    registry selections would be competing semantic authority and fail closed.
    """

    from award_agent.clarification.interpreter import ClarificationAnswerInterpretation

    assert isinstance(interpretation, ClarificationAnswerInterpretation)
    old = interpretation.temporal_template_selection
    accepting = interpretation.temporal_approximation_selection
    if any(
        _overlaps(left.span, right.span)
        for left in old.selected
        for right in accepting.selected + accepting.unresolved
    ):
        raise ClarificationCommandError("overlapping temporal registries selected incompatible outcomes")
    accepting_spans = tuple(item.span for item in accepting.selected) + tuple(
        item.span for item in accepting.unresolved
    )
    return tuple(
        _registry_rejected_fragment(
            span=span,
            requirement_ids=requirement_ids,
            classification=classification,
            reason_code=reason_code,
        )
        for span, requirement_ids, classification, reason_code in unresolved_template_rejections(old)
        if not any(_overlaps(span, accepting_span) for accepting_span in accepting_spans)
    )


def _selected_approximation_amendments(
    interpretation: object,
    *,
    projection: object,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    context: RequestContext,
) -> tuple[tuple[TemporalAmendment, ...], dict[str, tuple[TemporalContribution, ...]]]:
    """Compile ADR 0012's accepting registry into reducer-owned facts."""

    from award_agent.clarification.interpreter import ClarificationAnswerInterpretation

    assert isinstance(interpretation, ClarificationAnswerInterpretation)
    assert isinstance(projection, ClarificationTemporalApproximationProjection)
    try:
        facts = compile_temporal_approximation_selection(
            projection,
            interpretation.temporal_approximation_selection,
            context=context,
            text=answer_text,
            requirements=requirements,
        )
    except ClarificationTemporalApproximationError as exc:
        # A malformed selection is never a success-shaped response.
        raise ClarificationCommandError("temporal approximation compilation failed") from exc

    amendments: list[TemporalAmendment] = []
    compiled: dict[str, tuple[TemporalContribution, ...]] = {}
    for fact in facts:
        amendment_id = f"{fact.candidate.span.message_id}:approximation:{fact.candidate.candidate_id}"
        amendment = TemporalAmendment(
            amendment_id=amendment_id,
            target=cast(
                "Literal[AmendmentTarget.DEPARTURE, AmendmentTarget.RETURN_OR_DURATION]",
                fact.candidate.target,
            ),
            requirement_ids=(fact.candidate.requirement_id,) if fact.candidate.requirement_id else (),
            span=fact.candidate.span,
            is_correction=fact.candidate.is_correction,
            temporal_text=fact.candidate.span.text,
        )
        if fact.duration is not None:
            kind = TemporalContributionKind.DURATION
            contribution = TemporalContribution(
                contribution_id=f"answer:{amendment_id}:{kind.value}", kind=kind,
                source=AnswerMessageSource(span=fact.candidate.span), raw_text=fact.duration.raw_text,
                amendment_id=amendment_id, interpreted_duration=fact.duration,
                interpretation_provenance=fact.provenance,
            )
        else:
            assert fact.window is not None
            kind = (
                TemporalContributionKind.DEPARTURE_WINDOW
                if fact.candidate.target is AmendmentTarget.DEPARTURE
                else TemporalContributionKind.RETURN_WINDOW
            )
            contribution = TemporalContribution(
                contribution_id=f"answer:{amendment_id}:{kind.value}", kind=kind,
                source=AnswerMessageSource(span=fact.candidate.span), raw_text=fact.window.raw_text,
                amendment_id=amendment_id, date_window=fact.window,
                interpretation_provenance=fact.provenance,
            )
        compiled[amendment_id] = (contribution,)
        amendments.append(amendment)
    return tuple(amendments), compiled


def _selected_template_amendments(
    interpretation: object,
    *,
    projection: object,
    answer_text: str,
    requirements: tuple[BlockingRequirement, ...],
    context: RequestContext,
) -> tuple[tuple[TemporalAmendment, ...], dict[str, tuple[TemporalContribution, ...]]]:
    """Materialize opaque model selections into reducer-owned answer facts."""

    from award_agent.clarification.interpreter import ClarificationAnswerInterpretation
    from award_agent.clarification.temporal_templates import ClarificationTemporalTemplateProjection

    assert isinstance(interpretation, ClarificationAnswerInterpretation)
    assert isinstance(projection, ClarificationTemporalTemplateProjection)
    try:
        facts = compile_temporal_template_selection(
            projection,
            interpretation.temporal_template_selection,
            context=context,
            text=answer_text,
            requirements=requirements,
            additional_classified_spans=tuple(
                item.span
                for item in (
                    interpretation.temporal_approximation_selection.selected
                    + interpretation.temporal_approximation_selection.unresolved
                    + interpretation.rejected_fragments
                )
            ),
        )
    except ClarificationTemporalTemplateError as exc:
        # The interpreter contract has already checked membership and closure.
        # A failure here is a deterministic registry/compiler defect, never a
        # success-shaped answer reduction.
        raise ClarificationCommandError("temporal template compilation failed") from exc

    amendments: list[TemporalAmendment] = []
    compiled: dict[str, tuple[TemporalContribution, ...]] = {}
    for fact in facts:
        target = target_for_template_candidate(fact.candidate, requirements)
        amendment_id = f"{fact.candidate.span.message_id}:template:{fact.candidate.candidate_id}"
        amendment = TemporalAmendment(
            amendment_id=amendment_id,
            target=target,
            requirement_ids=(fact.candidate.requirement_id,),
            span=fact.candidate.span,
            temporal_text=fact.candidate.span.text,
        )
        kind = (
            TemporalContributionKind.DEPARTURE_WINDOW
            if target.value == "departure"
            else TemporalContributionKind.RETURN_WINDOW
        )
        compiled[amendment_id] = (
            TemporalContribution(
                contribution_id=f"answer:{amendment_id}:{kind.value}",
                kind=kind,
                source=AnswerMessageSource(span=fact.candidate.span),
                raw_text=fact.window.raw_text,
                amendment_id=amendment_id,
                date_window=fact.window,
                template_provenance=TemporalTemplateProvenance(
                    template_id=fact.template_id,
                    registry_version=projection.registry_version,
                    candidate_id=fact.candidate.candidate_id,
                    dependency_candidate_ids=fact.candidate.dependency_candidate_ids,
                ),
            ),
        )
        amendments.append(amendment)
    return tuple(amendments), compiled


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
                    requirement_ids=amendment.requirement_ids,
                )
            )
        elif amendment.is_correction and not _is_supported_correction(amendment, effective):
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

    template_projection = harvest_temporal_template_projection(
        message_id=command.message_id,
        text=command.text,
        requirements=current.prompt.requirements,
    )
    approximation_projection = harvest_temporal_approximation_projection(
        message_id=command.message_id,
        text=command.text,
        requirements=current.prompt.requirements,
    )
    interpretation = interpret_answer(
        interpreter,
        ClarificationAnswerInterpreterInput(
            message_id=command.message_id,
            text=command.text,
            requirements=current.prompt.requirements,
            temporal_template_projection=template_projection,
            temporal_approximation_projection=approximation_projection,
        ),
    )
    interpretation = _recover_ordered_date_pair(
        interpretation,
        message_id=command.message_id,
        text=command.text,
        requirements=current.prompt.requirements,
    )
    template_amendments, compiled_temporal_contributions = _selected_template_amendments(
        interpretation,
        projection=template_projection,
        answer_text=command.text,
        requirements=current.prompt.requirements,
        context=current.effective_request.context,
    )
    approximation_amendments, compiled_approximation_contributions = (
        _selected_approximation_amendments(
            interpretation,
            projection=approximation_projection,
            answer_text=command.text,
            requirements=current.prompt.requirements,
            context=current.effective_request.context,
        )
    )
    non_registry_amendments, registry_rejections = (
        _exclude_registry_covered_legacy_temporal_amendments(
            interpretation.amendments, interpretation=interpretation
        )
    )
    scoped, scope_rejections = _filter_corrections_and_collisions(
        non_registry_amendments + template_amendments + approximation_amendments,
        effective=current.effective_request,
    )
    accepted, temporal_rejections = _validate_temporal_subset(
        scoped,
        answer_text=command.text,
        requirements=current.prompt.requirements,
        context=current.effective_request.context,
        precompiled_amendment_ids=frozenset(
            compiled_temporal_contributions | compiled_approximation_contributions
        ),
    )
    effective = apply_amendments(
        current.effective_request,
        accepted,
        answer_text=command.text,
        requirements=current.prompt.requirements,
        compiled_temporal_contributions=(
            compiled_temporal_contributions | compiled_approximation_contributions
        ),
    )
    rejected = (
        interpretation.rejected_fragments
        + _reconcile_temporal_registries(interpretation)
        + tuple(
            _registry_rejected_fragment(
                span=span,
                requirement_ids=requirement_ids,
                classification=classification,
                reason_code=reason_code,
            )
            for span, requirement_ids, classification, reason_code in unresolved_approximation_rejections(
                interpretation.temporal_approximation_selection
            )
        )
        + registry_rejections
        + scope_rejections
        + temporal_rejections
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
        prompt = _build_prompt(
            effective,
            requirements=requirements,
            revision=next_number,
            composer=composer,
            receiver_interpretation=interpretation,
            rejected_fragments=rejected,
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


__all__ = [
    "ClarificationCommandError",
    "ClarificationTransition",
    "apply_clarification_answer",
    "start_clarification",
]
