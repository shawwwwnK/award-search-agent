"""Focused Step-1 contracts for additive clarification sessions."""

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from award_agent.clarification import project_initial_request
from award_agent.domain import (
    AmendmentTarget,
    AnswerMessageSource,
    AnswerTurn,
    AssumptionDisclosure,
    BlockingRequirement,
    BlockingRequirementKind,
    ClarificationAction,
    ClarificationDecision,
    ClarificationIssue,
    ClarificationIssueKind,
    ClarificationPrompt,
    ClarificationSession,
    ClarificationSessionRevision,
    ClarificationSessionStatus,
    ClarificationStopReason,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    EffectiveRequest,
    FieldProvenance,
    InitialSnapshotSource,
    InterpretedDuration,
    LocationAmendment,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    PromptCompositionSource,
    RejectedFragment,
    RejectedFragmentReason,
    RequestContext,
    RequestUnderstandingResult,
    ResolutionOutcome,
    TemporalAmendment,
    TemporalAnswerInterpretationProvenance,
    TemporalContribution,
    TemporalContributionKind,
    TemporalTemplateProvenance,
    TravelersAmendment,
    TypedAmendment,
    UnknownField,
    UnknownReason,
)


def _parsed_request() -> ParsedRequest:
    return ParsedRequest(
        raw_text="Two travelers from SFO to Tokyo October 6 through October 16.",
        context=RequestContext(reference_date=date(2026, 9, 8), timezone="America/Los_Angeles"),
        travelers=2,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        return_expression=None,
        departure_window=DateWindow(
            start=date(2026, 10, 6),
            end=date(2026, 10, 6),
            precision=DateWindowPrecision.EXACT,
            raw_text="October 6",
        ),
        return_window=DateWindow(
            start=date(2026, 10, 16),
            end=date(2026, 10, 16),
            precision=DateWindowPrecision.EXACT,
            raw_text="October 16",
        ),
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[],
        conflicts=[],
        date_resolution=DateResolutionProposal(
            interpreted_duration=InterpretedDuration(
                raw_text="10 days", minimum_days=10, maximum_days=10
            )
        ),
    )


def _parsed_request_missing_origin_and_travelers() -> ParsedRequest:
    parsed = _parsed_request()
    parsed.origins = []
    parsed.travelers = None
    parsed.unknowns = [
        UnknownField(
            field="origin",
            reason=UnknownReason.MISSING,
            detail="No departure location was stated.",
        ),
        UnknownField(
            field="travelers",
            reason=UnknownReason.MISSING,
            detail="The number of travelers was not stated.",
        ),
    ]
    return parsed


def test_initial_projection_is_additive_and_does_not_mutate_frozen_initial_snapshot() -> None:
    parsed = _parsed_request()
    before = parsed.model_dump(mode="python")

    effective = project_initial_request(parsed)

    assert parsed.model_dump(mode="python") == before
    assert parsed.date_resolution is not None
    assert effective.departure_window == parsed.departure_window
    assert effective.interpreted_duration == parsed.date_resolution.interpreted_duration
    assert [item.contribution_id for item in effective.temporal_contributions] == [
        "initial:departure_window",
        "initial:return_window",
        "initial:duration",
    ]
    assert {item.field for item in effective.field_provenance} == {
        EffectiveField.ORIGIN,
        EffectiveField.DESTINATION,
        EffectiveField.DEPARTURE,
        EffectiveField.RETURN_OR_DURATION,
        EffectiveField.TRAVELERS,
    }

    parsed.origins[0].value = "LAX"
    assert effective.origins[0].value == "SFO"


def test_projection_retains_valid_frozen_v1_empty_raw_text() -> None:
    parsed = _parsed_request()
    parsed.raw_text = ""
    assert parsed.departure_window is not None
    parsed.departure_window.raw_text = ""

    effective = project_initial_request(parsed)

    assert effective.raw_text == ""
    assert effective.temporal_contributions[0].raw_text == ""


def test_message_span_and_typed_amendments_require_turn_grounding_and_scope() -> None:
    span = MessageSpan(message_id="message-1", start=4, end=7, text="SFO")

    with pytest.raises(ValidationError, match="greater than start"):
        MessageSpan(message_id="message-1", start=4, end=4, text="SFO")
    with pytest.raises(ValidationError, match="require a requirement link"):
        LocationAmendment(
            amendment_id="amendment-1",
            target=AmendmentTarget.ORIGIN,
            span=span,
            locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
        )

    amendment: TypedAmendment = TypeAdapter(TypedAmendment).validate_python(
        {
            "amendment_id": "amendment-2",
            "target": "travelers",
            "requirement_ids": ["travelers"],
            "span": span.model_dump(mode="python"),
            "travelers": 2,
        }
    )
    correction = TemporalAmendment(
        amendment_id="amendment-3",
        target=AmendmentTarget.DEPARTURE,
        span=span,
        is_correction=True,
        temporal_text="October 6",
    )

    assert isinstance(amendment, TravelersAmendment)
    assert correction.requirement_ids == ()


def test_revision_ledger_is_contiguous_and_session_exposes_current_projection() -> None:
    parsed = _parsed_request()
    effective = project_initial_request(parsed)
    revision = ClarificationSessionRevision(
        revision=0,
        effective_request=effective,
        status=ClarificationSessionStatus.READY,
    )
    initial_result = RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.NONE,
            reason="Initial snapshot remains frozen.",
        ),
    )
    session = ClarificationSession(
        session_id="session-1",
        initial_result=initial_result,
        revisions=(revision,),
    )

    assert session.current_revision == revision
    assert session.current_revision is not revision
    assert session.effective_request == effective
    initial_result.parsed_request.origins[0].value = "LAX"
    revision.effective_request.origins[0].value = "JFK"
    assert session.initial_result.parsed_request.origins[0].value == "SFO"
    assert session.effective_request.origins[0].value == "SFO"
    skipped_revision = ClarificationSessionRevision(
        revision=2,
        effective_request=effective,
        prompt=ClarificationPrompt(
            prompt_id="prompt-2",
            revision=2,
            requirements=(
                BlockingRequirement(
                    requirement_id="origin",
                    kind=BlockingRequirementKind.ORIGIN,
                    field=EffectiveField.ORIGIN,
                ),
            ),
            message="This placeholder is unreachable because the ledger has a revision gap.",
        ),
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    with pytest.raises(ValidationError, match="contiguous"):
        ClarificationSession(
            session_id="session-2",
            initial_result=session.initial_result,
            revisions=(revision, skipped_revision),
        )


def test_initial_revision_must_be_the_exact_projection_of_the_initial_snapshot() -> None:
    parsed = _parsed_request()
    effective = project_initial_request(parsed)
    mismatched_revision = ClarificationSessionRevision(
        revision=0,
        effective_request=effective.model_copy(update={"travelers": 3}),
        status=ClarificationSessionStatus.READY,
    )

    with pytest.raises(ValidationError, match="must match the initial snapshot"):
        ClarificationSession(
            session_id="session-mismatch",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(mismatched_revision,),
        )


def test_accepted_amendments_and_effective_provenance_are_retained_and_linked() -> None:
    parsed = _parsed_request_missing_origin_and_travelers()
    initial_effective = project_initial_request(parsed)
    initial_prompt = ClarificationPrompt(
        prompt_id="prompt-0",
        revision=0,
        requirements=(
            BlockingRequirement(
                requirement_id="origin",
                kind=BlockingRequirementKind.ORIGIN,
                field=EffectiveField.ORIGIN,
            ),
            BlockingRequirement(
                requirement_id="travelers",
                kind=BlockingRequirementKind.TRAVELERS,
                field=EffectiveField.TRAVELERS,
            ),
        ),
        message="Please confirm your request.",
    )
    initial_revision = ClarificationSessionRevision(
        revision=0,
        effective_request=initial_effective,
        prompt=initial_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    message = MessageSpan(message_id="answer-1", start=0, end=12, text="three people")
    amendment = TravelersAmendment(
        amendment_id="amendment-1",
        target=AmendmentTarget.TRAVELERS,
        span=message,
        requirement_ids=("travelers",),
        travelers=3,
    )
    amended_provenance = (
        *(
            FieldProvenance(
                field=item.field,
                source=(
                    AnswerMessageSource(span=message)
                    if item.field is EffectiveField.TRAVELERS
                    else item.source
                ),
                amendment_id="amendment-1" if item.field is EffectiveField.TRAVELERS else None,
            )
            for item in initial_effective.field_provenance
        ),
        FieldProvenance(
            field=EffectiveField.TRAVELERS,
            source=AnswerMessageSource(span=message),
            amendment_id="amendment-1",
        ),
    )
    amended_effective = initial_effective.model_copy(
        update={
            "travelers": 3,
            "field_provenance": amended_provenance,
            "unknowns": tuple(
                item for item in initial_effective.unknowns if item.field != "travelers"
            ),
        }
    )
    outcome = ResolutionOutcome(accepted_amendments=(amendment,))
    second_prompt = ClarificationPrompt(
        prompt_id="prompt-1",
        revision=1,
        requirements=(
            BlockingRequirement(
                requirement_id="origin",
                kind=BlockingRequirementKind.ORIGIN,
                field=EffectiveField.ORIGIN,
            ),
        ),
        message="Where are you departing from?",
    )
    answer_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=1,
            expected_revision=0,
            prompt_id="prompt-0",
            message=message,
        ),
        outcome=outcome,
        prompt=second_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    session = ClarificationSession(
        session_id="session-amendment",
        initial_result=RequestUnderstandingResult(
            parsed_request=parsed,
            clarification=ClarificationDecision(
                action=ClarificationAction.NONE,
                reason="Initial snapshot remains frozen.",
            ),
        ),
        revisions=(initial_revision, answer_revision),
    )

    assert session.current_revision.outcome is not None
    assert session.current_revision.outcome.accepted_amendments == (amendment,)
    assert session.current_revision.outcome.accepted_amendment_ids == ("amendment-1",)

    mismatched_message = MessageSpan(message_id="answer-1", start=0, end=5, text="three")
    mismatched_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=1,
            expected_revision=0,
            prompt_id="prompt-0",
            message=message,
        ),
        outcome=ResolutionOutcome(
            accepted_amendments=(amendment.model_copy(update={"span": mismatched_message}),)
        ),
        prompt=second_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    with pytest.raises(ValidationError, match="span must match"):
        ClarificationSession(
            session_id="session-mismatched-provenance",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(initial_revision, mismatched_revision),
        )

    awaiting_revision = ClarificationSessionRevision(
        revision=1,
        effective_request=amended_effective,
        answer_turn=answer_revision.answer_turn,
        outcome=outcome,
        prompt=second_prompt,
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    duplicate_message_revision = ClarificationSessionRevision(
        revision=2,
        effective_request=amended_effective,
        answer_turn=AnswerTurn(
            turn_number=2,
            expected_revision=1,
            prompt_id="prompt-1",
            message=message,
        ),
        outcome=ResolutionOutcome(),
        status=ClarificationSessionStatus.STOPPED,
        stop_reason=ClarificationStopReason.NO_PROGRESS_LIMIT,
    )
    with pytest.raises(ValidationError, match="message IDs must be unique"):
        ClarificationSession(
            session_id="session-duplicate-message",
            initial_result=RequestUnderstandingResult(
                parsed_request=parsed,
                clarification=ClarificationDecision(
                    action=ClarificationAction.NONE,
                    reason="Initial snapshot remains frozen.",
                ),
            ),
            revisions=(initial_revision, awaiting_revision, duplicate_message_revision),
        )


def test_new_contracts_do_not_widen_the_frozen_parsed_request_schema() -> None:
    parsed_properties = ParsedRequest.model_json_schema()["properties"]

    assert "effective_request" not in parsed_properties
    assert "revisions" not in parsed_properties
    assert "message_id" not in parsed_properties
    assert InitialSnapshotSource(field=EffectiveField.ORIGIN).kind == "initial_snapshot"


def test_adr_0012_contract_defaults_load_an_old_prompt_and_session_payload() -> None:
    prompt = ClarificationPrompt.model_validate(
        {
            "prompt_id": "prompt-0",
            "revision": 0,
            "requirements": [],
            "message": "Please confirm your request.",
        }
    )
    rejected = RejectedFragment.model_validate(
        {
            "span": {"message_id": "answer-1", "start": 0, "end": 3, "text": "SFO"},
            "reason": "invalid",
            "detail": "historic payload without v2 issue metadata",
        }
    )

    assert prompt.issues == ()
    assert prompt.composition_source is PromptCompositionSource.FALLBACK
    assert prompt.fallback_code is None
    assert rejected.requirement_ids == ()
    assert rejected.reason_code is None


def test_interpretation_provenance_retains_visible_assumption_without_new_semantics() -> None:
    provenance = TemporalAnswerInterpretationProvenance(
        policy_version="clarification-fuzzy-v1",
        interpretation_id="month_portion:early",
        candidate_ids=("candidate-early",),
        assumption_disclosure=AssumptionDisclosure(
            disclosure_id="assumption-1",
            message="I’ll use October 1–10 for early October.",
        ),
    )
    contribution = TemporalContribution(
        contribution_id="answer:1:departure",
        kind=TemporalContributionKind.DEPARTURE_WINDOW,
        source=AnswerMessageSource(
            span=MessageSpan(message_id="answer-1", start=0, end=13, text="early October")
        ),
        amendment_id="amendment-1",
        date_window=DateWindow(
            start=date(2026, 10, 1),
            end=date(2026, 10, 10),
            precision=DateWindowPrecision.WINDOW,
            raw_text="early October",
        ),
        interpretation_provenance=provenance,
    )

    assert contribution.interpretation_provenance is not None
    assert contribution.interpretation_provenance.policy_version == "clarification-fuzzy-v1"
    assert contribution.interpretation_provenance.assumption_disclosure is not None
    with pytest.raises(ValidationError, match="candidate IDs must be unique"):
        TemporalAnswerInterpretationProvenance(
            policy_version="clarification-fuzzy-v1",
            interpretation_id="month_portion:early",
            candidate_ids=("candidate-early", "candidate-early"),
        )
    with pytest.raises(ValidationError, match="requires an answer-message source"):
        TemporalContribution(
            contribution_id="initial:departure",
            kind=TemporalContributionKind.DEPARTURE_WINDOW,
            source=InitialSnapshotSource(field=EffectiveField.DEPARTURE),
            date_window=contribution.date_window,
            interpretation_provenance=provenance,
        )
    with pytest.raises(ValidationError, match="mutually exclusive"):
        TemporalContribution(
            contribution_id="answer:1:template-and-interpretation",
            kind=TemporalContributionKind.DEPARTURE_WINDOW,
            source=contribution.source,
            amendment_id="amendment-1",
            date_window=contribution.date_window,
            template_provenance=TemporalTemplateProvenance(
                template_id="this_weekend",
                registry_version="clarification-temporal-templates-v2",
                candidate_id="candidate-template",
            ),
            interpretation_provenance=provenance,
        )
    duplicate_disclosure = TemporalContribution(
        contribution_id="answer:1:return",
        kind=TemporalContributionKind.RETURN_WINDOW,
        source=AnswerMessageSource(
            span=MessageSpan(message_id="answer-1", start=14, end=24, text="for a week")
        ),
        amendment_id="amendment-2",
        date_window=DateWindow(
            start=date(2026, 10, 8),
            end=date(2026, 10, 17),
            precision=DateWindowPrecision.WINDOW,
            raw_text="for a week",
        ),
        interpretation_provenance=provenance,
    )
    with pytest.raises(ValidationError, match="assumption disclosure IDs must be unique"):
        EffectiveRequest(
            context=RequestContext(
                reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"
            ),
            temporal_contributions=(contribution, duplicate_disclosure),
        )


def test_prompt_issues_and_rejection_links_fail_closed_and_remain_defensive() -> None:
    requirement = BlockingRequirement(
        requirement_id="departure",
        kind=BlockingRequirementKind.DEPARTURE,
        field=EffectiveField.DEPARTURE,
    )
    issue = ClarificationIssue(
        issue_id="issue-departure",
        requirement_id="departure",
        kind=ClarificationIssueKind.AMBIGUOUS,
        reason="The answer used an unbounded relative phrase.",
        span=MessageSpan(message_id="answer-1", start=0, end=16, text="early next month"),
        reason_code="temporal.relative_unbounded",
    )
    prompt = ClarificationPrompt(
        prompt_id="prompt-1",
        revision=1,
        requirements=(requirement,),
        issues=(issue,),
        composition_source=PromptCompositionSource.FALLBACK,
        fallback_code="composer.unavailable",
        message="What date range should I use for ‘early next month’?",
    )

    assert prompt.issues[0].span is not None
    with pytest.raises(ValidationError, match="frozen"):
        prompt.issues[0].reason = "mutated copy"
    with pytest.raises(ValidationError, match="reason_code"):
        ClarificationIssue.model_validate(
            {
                "issue_id": "issue-no-code",
                "requirement_id": "departure",
                "kind": "missing",
                "reason": "Missing departure timing.",
            }
        )
    with pytest.raises(ValidationError, match="exactly link active requirements"):
        ClarificationPrompt(
            prompt_id="prompt-1",
            revision=1,
            requirements=(requirement,),
            issues=(
                ClarificationIssue(
                    issue_id="issue-travelers",
                    requirement_id="travelers",
                    kind=ClarificationIssueKind.MISSING,
                    reason="Missing traveler count.",
                    reason_code="requirement.missing",
                ),
            ),
            message="How many travelers?",
        )
    with pytest.raises(ValidationError, match="unique"):
        RejectedFragment(
            span=MessageSpan(message_id="answer-1", start=0, end=3, text="SFO"),
            reason=RejectedFragmentReason.INVALID,
            detail="invalid",
            requirement_ids=("origin", "origin"),
        )


def test_prompt_issue_kinds_cover_active_requirements_without_one_issue_limit() -> None:
    departure = BlockingRequirement(
        requirement_id="departure",
        kind=BlockingRequirementKind.DEPARTURE,
        field=EffectiveField.DEPARTURE,
    )
    conflict = BlockingRequirement(
        requirement_id="conflict:dates",
        kind=BlockingRequirementKind.CONFLICT,
        conflict_code="dates",
    )
    prompt = ClarificationPrompt(
        prompt_id="prompt-1",
        revision=1,
        requirements=(departure, conflict),
        issues=(
            ClarificationIssue(
                issue_id="issue-departure-missing",
                requirement_id="departure",
                kind=ClarificationIssueKind.MISSING,
                reason="No departure was supplied.",
                reason_code="requirement.missing",
            ),
            ClarificationIssue(
                issue_id="issue-departure-unsupported",
                requirement_id="departure",
                kind=ClarificationIssueKind.UNSUPPORTED,
                reason="The supplied expression is not supported.",
                reason_code="temporal.unsupported",
            ),
            ClarificationIssue(
                issue_id="issue-conflict",
                requirement_id="conflict:dates",
                kind=ClarificationIssueKind.CONFLICT,
                reason="The dates conflict.",
                reason_code="dates.conflict",
            ),
        ),
        message="Please clarify the dates.",
    )

    assert [item.issue_id for item in prompt.issues] == [
        "issue-departure-missing",
        "issue-departure-unsupported",
        "issue-conflict",
    ]
    with pytest.raises(ValidationError, match="field requirements cannot use conflict"):
        ClarificationPrompt(
            prompt_id="prompt-1",
            revision=1,
            requirements=(departure,),
            issues=(
                ClarificationIssue(
                    issue_id="bad-field-issue",
                    requirement_id="departure",
                    kind=ClarificationIssueKind.CONFLICT,
                    reason="Not valid for a field blocker.",
                    reason_code="invalid",
                ),
            ),
            message="Please clarify.",
        )


def test_revision_issue_and_rejection_spans_must_exactly_match_answer_text() -> None:
    effective = project_initial_request(_parsed_request())
    answer = MessageSpan(message_id="answer-1", start=0, end=18, text="early next month")
    requirement = BlockingRequirement(
        requirement_id="departure",
        kind=BlockingRequirementKind.DEPARTURE,
        field=EffectiveField.DEPARTURE,
    )
    issue = ClarificationIssue(
        issue_id="issue-departure",
        requirement_id="departure",
        kind=ClarificationIssueKind.AMBIGUOUS,
        reason="The phrase needs a bounded range.",
        reason_code="temporal.unbounded",
        span=MessageSpan(message_id="answer-1", start=0, end=5, text="later"),
    )
    with pytest.raises(ValidationError, match="prompt issue span text must exactly match"):
        ClarificationSessionRevision(
            revision=1,
            effective_request=effective,
            answer_turn=AnswerTurn(
                turn_number=1,
                expected_revision=0,
                prompt_id="prompt-0",
                message=answer,
            ),
            outcome=ResolutionOutcome(),
            prompt=ClarificationPrompt(
                prompt_id="prompt-1",
                revision=1,
                requirements=(requirement,),
                issues=(issue,),
                message="What date range should I use?",
            ),
            status=ClarificationSessionStatus.AWAITING_ANSWER,
        )
    with pytest.raises(ValidationError, match="rejected fragment span text must exactly match"):
        ClarificationSessionRevision(
            revision=1,
            effective_request=effective,
            answer_turn=AnswerTurn(
                turn_number=1,
                expected_revision=0,
                prompt_id="prompt-0",
                message=answer,
            ),
            outcome=ResolutionOutcome(
                rejected_fragments=(
                    RejectedFragment(
                        span=MessageSpan(message_id="answer-1", start=0, end=5, text="later"),
                        reason=RejectedFragmentReason.INVALID,
                        detail="Not grounded.",
                    ),
                )
            ),
            status=ClarificationSessionStatus.STOPPED,
            stop_reason=ClarificationStopReason.NO_PROGRESS_LIMIT,
        )
    with pytest.raises(ValidationError, match="initial prompt issues cannot cite answer spans"):
        ClarificationSessionRevision(
            revision=0,
            effective_request=effective,
            prompt=ClarificationPrompt(
                prompt_id="prompt-0",
                revision=0,
                requirements=(requirement,),
                issues=(issue,),
                message="What date range should I use?",
            ),
            status=ClarificationSessionStatus.AWAITING_ANSWER,
        )


def test_session_rejects_fragment_links_outside_the_answered_prompt() -> None:
    parsed = _parsed_request_missing_origin_and_travelers()
    effective = project_initial_request(parsed)
    initial_result = RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.NONE,
            reason="Initial snapshot remains frozen.",
        ),
    )
    initial = ClarificationSessionRevision(
        revision=0,
        effective_request=effective,
        prompt=ClarificationPrompt(
            prompt_id="prompt-0",
            revision=0,
            requirements=(
                BlockingRequirement(
                    requirement_id="origin",
                    kind=BlockingRequirementKind.ORIGIN,
                    field=EffectiveField.ORIGIN,
                ),
                BlockingRequirement(
                    requirement_id="travelers",
                    kind=BlockingRequirementKind.TRAVELERS,
                    field=EffectiveField.TRAVELERS,
                ),
            ),
            message="Please confirm your request.",
        ),
        status=ClarificationSessionStatus.AWAITING_ANSWER,
    )
    message = MessageSpan(message_id="answer-1", start=0, end=2, text="no")
    answer = ClarificationSessionRevision(
        revision=1,
        effective_request=effective,
        answer_turn=AnswerTurn(
            turn_number=1,
            expected_revision=0,
            prompt_id="prompt-0",
            message=message,
        ),
        outcome=ResolutionOutcome(
            rejected_fragments=(
                RejectedFragment(
                    span=message,
                    reason=RejectedFragmentReason.OUT_OF_SCOPE,
                    detail="This did not answer an active requirement.",
                    requirement_ids=("departure",),
                ),
            )
        ),
        status=ClarificationSessionStatus.STOPPED,
        stop_reason=ClarificationStopReason.NO_PROGRESS_LIMIT,
    )

    with pytest.raises(ValidationError, match="must be active in the prior prompt"):
        ClarificationSession(
            session_id="session-invalid-rejection-link",
            initial_result=initial_result,
            revisions=(initial, answer),
        )
