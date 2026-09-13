"""Public, optimistic-concurrency controller for clarification sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError

from award_agent.clarification.blockers import (
    build_clarification_prompt,
    collect_blocking_requirements,
)
from award_agent.clarification.calendar_plan import (
    CalendarCalculationError,
    CalendarCalculationProposal,
    CalendarCalculationReceipt,
    CalendarProposalTarget,
    evaluate_calendar_proposals,
)
from award_agent.clarification.composer import (
    ClarificationPromptComposer,
    ClarificationPromptComposerInput,
    compose_prompt,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpreter,
    ClarificationAnswerInterpreterInput,
    ClarificationCalendarProposalIssue,
    ClarificationDiscourseAct,
    ClarificationInterpretationError,
    ClarificationInterpretationUnavailable,
    ClarificationOneWayScopeNotice,
    ClarificationRepairBudget,
    ClarificationSemanticFact,
    validate_answer_interpretation,
)
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.projection import project_initial_request
from award_agent.clarification.reducer import apply_amendments
from award_agent.clarification.semantic import (
    SemanticOperation,
    SemanticTarget,
)
from award_agent.domain import (
    AmendmentTarget,
    AnswerTurn,
    BlockingRequirement,
    ClarificationAction,
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
    RequestContext,
    RequestUnderstandingOutcome,
    RequestUnderstandingResult,
    ResolutionOutcome,
    ScopeNotice,
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


@dataclass(frozen=True)
class ClarificationInterpretationPending:
    """A non-mutating, retryable receiver result for unavailable semantics."""

    session: ClarificationSession
    code: str
    detail: str
    repair_attempted: bool
    answer_turn: AnswerTurn | None = None
    effective_request: EffectiveRequest | None = None
    outcome: ResolutionOutcome | None = None
    requirements: tuple[BlockingRequirement, ...] = ()
    issues: tuple[ClarificationIssue, ...] = ()


@dataclass(frozen=True)
class _AuthorizedSemanticFact:
    """A semantic fact after deterministic session-scope authorization.

    The receiver supplies no operation or requirement links.  This local form
    is the only place where a semantic target becomes a reducer amendment.
    """

    fact: ClarificationSemanticFact
    operation: SemanticOperation
    requirement_ids: tuple[str, ...]


_TARGET_REQUIREMENT_KIND = {
    SemanticTarget.ORIGIN: "origin",
    SemanticTarget.DESTINATION: "destination",
    SemanticTarget.TRAVELERS: "travelers",
    SemanticTarget.DEPARTURE_WINDOW: "departure",
}


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

    if initial_result.outcome is RequestUnderstandingOutcome.PENDING_RETRYABLE:
        raise ClarificationCommandError(
            "cannot start clarification from a pending request-understanding outcome"
        )
    assert initial_result.parsed_request is not None
    assert initial_result.clarification is not None

    effective = project_initial_request(initial_result.parsed_request)
    if initial_result.clarification.action is ClarificationAction.UNSUPPORTED:
        # The initial workflow already made a structured, grounded scope
        # decision.  Continuation must preserve that explicit user-facing
        # response rather than projecting the outbound fields into a
        # misleading ready session.
        revision = ClarificationSessionRevision(
            revision=0,
            effective_request=effective,
            status=ClarificationSessionStatus.STOPPED,
            stop_reason=ClarificationStopReason.UNSUPPORTED_REQUEST_SCOPE,
            terminal_message=initial_result.clarification.question,
        )
        return ClarificationSession(
            session_id=session_id or f"clarification-{uuid4().hex}",
            initial_result=initial_result,
            limits=limits or ClarificationSessionLimits(),
            revisions=(revision,),
        )
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
    return tuple(targets)


def _one_way_scope_notices(
    notices: tuple[ClarificationOneWayScopeNotice, ...],
) -> tuple[ScopeNotice, ...]:
    """Materialize policy-owned copy from receiver-owned scope classifications."""

    return tuple(ScopeNotice(span=notice.span) for notice in notices)


def _authorize_semantic_facts(
    facts: tuple[ClarificationSemanticFact, ...],
    *,
    requirements: tuple[BlockingRequirement, ...],
    effective: EffectiveRequest,
) -> tuple[tuple[_AuthorizedSemanticFact, ...], tuple[RejectedFragment, ...]]:
    """Bind model semantics to the current session without reading answer text.

    A target with one compatible active requirement is necessarily a ``set``.
    Only a target that is already resolved and explicitly correction-eligible
    becomes a ``replace``.  All other model facts are independently retained
    as a rejected proposal so a bad sibling cannot erase a usable one.
    """

    correction_eligible = set(_correction_eligible_targets(effective))
    authorized: list[_AuthorizedSemanticFact] = []
    rejected: list[RejectedFragment] = []
    for fact in facts:
        expected_kind = _TARGET_REQUIREMENT_KIND[fact.target]
        compatible = tuple(
            requirement.requirement_id
            for requirement in requirements
            if requirement.kind.value == expected_kind
        )
        if len(compatible) == 1:
            authorized.append(
                _AuthorizedSemanticFact(
                    fact=fact,
                    operation=SemanticOperation.SET,
                    requirement_ids=compatible,
                )
            )
        elif not compatible and fact.target in correction_eligible:
            authorized.append(
                _AuthorizedSemanticFact(
                    fact=fact,
                    operation=SemanticOperation.REPLACE,
                    requirement_ids=(),
                )
            )
        else:
            rejected.append(
                RejectedFragment(
                    span=fact.span,
                    # A target emitted by the receiver is a proposal, not an
                    # attempted user-level request revision.  Reject it
                    # independently so a valid sibling can still resolve the
                    # active blocker; its presence must not terminally stop
                    # the turn.
                    reason=RejectedFragmentReason.INVALID,
                    detail=(
                        "receiver target is neither an active compatible requirement "
                        "nor an eligible resolved correction"
                    ),
                    reason_code="receiver.target_not_authorized",
                )
            )
    return tuple(authorized), tuple(rejected)


def _materialize_semantic_facts(
    facts: tuple[_AuthorizedSemanticFact, ...],
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
    prior_receipts: dict[str, CalendarCalculationReceipt] = {}
    rejected: list[RejectedFragment] = []
    pending_temporal: list[_AuthorizedSemanticFact] = []
    for authorized_fact in facts:
        fact = authorized_fact.fact
        correction = authorized_fact.operation is SemanticOperation.REPLACE
        amendment: TypedAmendment
        if fact.target in {SemanticTarget.ORIGIN, SemanticTarget.DESTINATION}:
            assert fact.location_kind is not None and fact.location_value is not None
            amendment = LocationAmendment(
                amendment_id=fact.fact_id,
                target=AmendmentTarget.ORIGIN
                if fact.target is SemanticTarget.ORIGIN
                else AmendmentTarget.DESTINATION,
                requirement_ids=authorized_fact.requirement_ids,
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
                requirement_ids=authorized_fact.requirement_ids,
                span=fact.span,
                is_correction=correction,
                travelers=fact.travelers,
            )
        else:
            pending_temporal.append(authorized_fact)
            continue
        amendments.append(amendment)
    # A plan edge may point to a fact emitted later in the same answer.  Retry
    # only facts whose typed anchors can become available; an independent bad
    # sibling never blocks a valid component.
    while pending_temporal:
        deferred: list[_AuthorizedSemanticFact] = []
        progressed = False
        for authorized_fact in pending_temporal:
            try:
                amendment, receipt = _materialize_calendar_fact(
                    authorized_fact, context=effective.context, prior_receipts=prior_receipts
                )
            except (CalendarCalculationError, ValidationError):
                deferred.append(authorized_fact)
                continue
            amendments.append(amendment)
            compiled[receipt.fact_id] = (receipt.contribution,)
            prior_receipts[receipt.fact_id] = receipt
            progressed = True
        if not progressed:
            rejected.extend(
                RejectedFragment(
                    span=item.fact.span,
                    reason=RejectedFragmentReason.AMBIGUOUS,
                    detail="receiver calendar proposal could not be evaluated safely",
                    requirement_ids=item.requirement_ids,
                    reason_code="receiver.calendar_plan_compile",
                )
                for item in deferred
            )
            break
        pending_temporal = deferred
    return tuple(amendments), compiled, tuple(rejected)


def _materialize_calendar_fact(
    authorized_fact: _AuthorizedSemanticFact,
    *,
    context: RequestContext,
    prior_receipts: dict[str, CalendarCalculationReceipt],
) -> tuple[TemporalAmendment, CalendarCalculationReceipt]:
    fact = authorized_fact.fact
    assert fact.calendar_operation is not None
    amendment = TemporalAmendment(
        amendment_id=fact.fact_id,
        target=AmendmentTarget.DEPARTURE,
        requirement_ids=authorized_fact.requirement_ids,
        span=fact.span,
        is_correction=authorized_fact.operation is SemanticOperation.REPLACE,
        temporal_text=fact.span.text,
    )
    (receipt,) = evaluate_calendar_proposals(
        proposals=(
            CalendarCalculationProposal(
                fact_id=fact.fact_id,
                target=CalendarProposalTarget(fact.target.value),
                evidence=fact.span,
                operation=fact.calendar_operation,
            ),
        ),
        context=context,
        prior_receipts=prior_receipts,
    )
    return amendment, receipt


def _repair_calendar_failures(
    *,
    interpreter: ClarificationAnswerInterpreter,
    receiver_input: ClarificationAnswerInterpreterInput,
    authorized_facts: tuple[_AuthorizedSemanticFact, ...],
    compilation_rejections: tuple[RejectedFragment, ...],
    effective: EffectiveRequest,
    requirements: tuple[BlockingRequirement, ...],
    repair_budget_consumed: bool,
) -> tuple[
    tuple[TypedAmendment, ...],
    dict[str, tuple[TemporalContribution, ...]],
    tuple[RejectedFragment, ...],
    ClarificationInterpretationUnavailable | None,
]:
    """Ask the same model once to repair only calendar facts its evaluator rejected.

    This remains a semantic/model operation: local code merely supplies typed
    validation path information and accepts the repaired fact through the
    identical grounding and authorization gates.  An unavailable repair leaves
    the original rejected proposal explicit and cannot erase valid siblings.
    """

    rejected_spans = {
        (item.span.message_id, item.span.start, item.span.end)
        for item in compilation_rejections
        if item.reason_code == "receiver.calendar_plan_compile"
    }
    failed = tuple(
        item.fact
        for item in authorized_facts
        if (item.fact.span.message_id, item.fact.span.start, item.fact.span.end) in rejected_spans
        and item.fact.calendar_operation is not None
    )
    if not failed:
        return (), {}, compilation_rejections, None
    if repair_budget_consumed:
        return (
            (),
            {},
            compilation_rejections,
            ClarificationInterpretationUnavailable(
                code="receiver_repair_budget_exhausted",
                detail="The clarification receiver already used its one repair attempt.",
                repair_attempted=True,
            ),
        )
    repair = getattr(interpreter, "repair_calendar_proposals", None)
    if not callable(repair):
        return (
            (),
            {},
            compilation_rejections,
            ClarificationInterpretationUnavailable(
                code="receiver_repair_unavailable",
                detail="The clarification receiver cannot repair its calendar proposal.",
                repair_attempted=False,
            ),
        )
    issues = tuple(
        ClarificationCalendarProposalIssue(
            fact_id=fact.fact_id,
            code="calendar_plan_evaluation_failed",
            path=("facts", fact.fact_id, "calendar_operation"),
            detail="The typed calendar proposal could not be evaluated safely.",
        )
        for fact in failed
    )
    repaired = repair(receiver_input, facts=failed, issues=issues)
    if isinstance(repaired, ClarificationInterpretationUnavailable):
        return (), {}, compilation_rejections, repaired
    repaired = validate_answer_interpretation(receiver_input, repaired)
    assert not isinstance(repaired, ClarificationInterpretationUnavailable)
    repaired_authorized, repair_authorization_rejections = _authorize_semantic_facts(
        repaired.facts, requirements=requirements, effective=effective
    )
    repaired_amendments, repaired_compiled, repaired_rejections = _materialize_semantic_facts(
        repaired_authorized, effective=effective
    )
    repaired_ids = {amendment.amendment_id for amendment in repaired_amendments}
    remaining = tuple(
        item
        for item in compilation_rejections
        if item.span is None
        or not any(
            fact.fact_id in repaired_ids
            and (fact.span.message_id, fact.span.start, fact.span.end)
            == (item.span.message_id, item.span.start, item.span.end)
            for fact in failed
        )
    )
    return (
        repaired_amendments,
        repaired_compiled,
        remaining + repair_authorization_rejections + repaired_rejections,
        None,
    )


def _adapter_repair_budget_consumed(interpreter: object) -> bool:
    """Read the explicit optional budget capability without adapter duck typing."""
    return (
        interpreter.repair_budget_consumed()
        if isinstance(interpreter, ClarificationRepairBudget)
        else False
    )


def _amendment_field(amendment: TypedAmendment) -> str | None:
    return {
        "origin": "origin",
        "destination": "destination",
        "travelers": "travelers",
        "departure": "departure",
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

    return (
        effective.travelers,
        locations(effective.origins),
        locations(effective.destinations),
        window(effective.departure_window),
        tuple(item.value for item in effective.cabins),
        tuple(item.value for item in effective.search_modes),
        effective.repositioning_allowed,
        effective.hard_constraints,
        tuple(
            (
                item.kind.value,
                window(item.date_window),
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
) -> ClarificationTransition | ClarificationCompositionPending | ClarificationInterpretationPending:
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
    receiver_input = ClarificationAnswerInterpreterInput(
        message_id=command.message_id,
        text=command.text,
        ordered_requirements=current.prompt.requirements,
        correction_eligible_targets=_correction_eligible_targets(current.effective_request),
    )
    repair_consumed = False
    interpretation = interpreter.interpret(receiver_input)
    if isinstance(interpretation, ClarificationInterpretationUnavailable):
        return ClarificationInterpretationPending(
            session=session,
            code=interpretation.code,
            detail=interpretation.detail,
            repair_attempted=interpretation.repair_attempted,
        )
    try:
        interpretation = validate_answer_interpretation(receiver_input, interpretation)
    except ClarificationInterpretationError:
        repair = getattr(interpreter, "repair_interpretation", None)
        if not callable(repair):
            return ClarificationInterpretationPending(
                session=session,
                code="receiver_grounding_invalid",
                detail="The clarification receiver returned invalid answer grounding.",
                repair_attempted=False,
            )
        grounding_issues = tuple(
            ClarificationCalendarProposalIssue(
                fact_id=fact.fact_id,
                code="answer_grounding_failed",
                path=("facts", fact.fact_id, "span"),
                detail="Ground the fact in the exact answer text.",
            )
            for fact in interpretation.facts
        )
        repaired = repair(receiver_input, facts=interpretation.facts, issues=grounding_issues)
        repair_consumed = True
        if isinstance(repaired, ClarificationInterpretationUnavailable):
            return ClarificationInterpretationPending(
                session=session,
                code=repaired.code,
                detail=repaired.detail,
                repair_attempted=True,
            )
        try:
            interpretation = validate_answer_interpretation(receiver_input, repaired)
        except ClarificationInterpretationError:
            return ClarificationInterpretationPending(
                session=session,
                code="receiver_repair_grounding_invalid",
                detail="The clarification receiver returned invalid repaired grounding.",
                repair_attempted=True,
            )
    assert not isinstance(interpretation, ClarificationInterpretationUnavailable)
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

    scope_notices = _one_way_scope_notices(interpretation.one_way_scope_notices)
    if scope_notices:
        # A structured return/duration classification is outside this release,
        # not a partially fulfillable one-way answer. Preserve its exact span
        # and policy-owned response, but never accept sibling facts or invoke
        # the prompt composer for a scope-terminated turn.
        next_revision = ClarificationSessionRevision(
            revision=current.revision + 1,
            effective_request=current.effective_request,
            answer_turn=answer_turn,
            outcome=ResolutionOutcome(scope_notices=scope_notices),
            status=ClarificationSessionStatus.STOPPED,
            stop_reason=ClarificationStopReason.UNSUPPORTED_REQUEST_SCOPE,
            terminal_message=scope_notices[0].message,
        )
        next_session = ClarificationSession(
            session_id=session.session_id,
            initial_result=session.initial_result,
            limits=session.limits,
            revisions=session.revisions + (next_revision,),
        )
        return ClarificationTransition(session=next_session, revision=next_revision)
    authorized_facts, authorization_rejections = _authorize_semantic_facts(
        interpretation.facts,
        requirements=current.prompt.requirements,
        effective=current.effective_request,
    )
    materialized, compiled_temporal_contributions, compilation_rejections = (
        _materialize_semantic_facts(authorized_facts, effective=current.effective_request)
    )
    (
        repaired_amendments,
        repaired_compiled,
        compilation_rejections,
        repair_unavailable,
    ) = _repair_calendar_failures(
        interpreter=interpreter,
        receiver_input=receiver_input,
        authorized_facts=authorized_facts,
        compilation_rejections=compilation_rejections,
        effective=current.effective_request,
        requirements=current.prompt.requirements,
        repair_budget_consumed=repair_consumed or _adapter_repair_budget_consumed(interpreter),
    )
    materialized += repaired_amendments
    compiled_temporal_contributions.update(repaired_compiled)
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
                requirement_ids=tuple(
                    requirement.requirement_id
                    for requirement in current.prompt.requirements
                    if item.target is not None
                    and requirement.kind.value == _TARGET_REQUIREMENT_KIND[item.target]
                ),
                reason_code=f"receiver.{item.reason}",
            )
            for item in interpretation.unresolved_fragments
        )
        + compilation_rejections
        + authorization_rejections
        + scope_rejections
    )
    if repair_unavailable is not None:
        pending_requirements = collect_blocking_requirements(effective)
        pending_issues = derive_clarification_issues(
            pending_requirements, rejected_fragments=rejected
        )
        return ClarificationInterpretationPending(
            session=session,
            code=repair_unavailable.code,
            detail=repair_unavailable.detail,
            repair_attempted=True,
            answer_turn=answer_turn,
            effective_request=effective,
            outcome=ResolutionOutcome(
                accepted_amendments=accepted,
                rejected_fragments=rejected,
                scope_notices=scope_notices,
            ),
            requirements=pending_requirements,
            issues=pending_issues,
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
                        accepted_amendments=accepted,
                        rejected_fragments=rejected,
                        scope_notices=scope_notices,
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
        outcome=ResolutionOutcome(
            accepted_amendments=accepted,
            rejected_fragments=rejected,
            scope_notices=scope_notices,
        ),
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
    "ClarificationInterpretationPending",
    "ClarificationPromptCompositionFailedError",
    "ClarificationTransition",
    "apply_clarification_answer",
    "retry_prompt_composition",
    "start_clarification",
]
