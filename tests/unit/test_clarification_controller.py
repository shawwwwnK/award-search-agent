"""Offline controller tests for additive clarification sessions."""

from datetime import date
from typing import Literal

import pytest

from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import (
    ClarificationCommandError,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import ClarificationAnswerInterpretation
from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationBinding,
    ClarificationTemporalApproximationSelection,
    ClarificationTemporalApproximationUnresolved,
)
from award_agent.clarification.temporal_templates import (
    ClarificationTemporalTemplateBinding,
    ClarificationTemporalTemplateSelection,
    ClarificationTemporalTemplateUnresolved,
)
from award_agent.domain import (
    AmendmentTarget,
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSession,
    ClarificationSessionLimits,
    ClarificationSessionStatus,
    ClarificationStopReason,
    Conflict,
    DateResolutionProposal,
    DateWindow,
    DateWindowPrecision,
    InterpretedDuration,
    LocationAmendment,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RejectedFragment,
    RejectedFragmentReason,
    RequestContext,
    RequestUnderstandingResult,
    TemporalAmendment,
    TravelersAmendment,
    UnknownField,
    UnknownReason,
)


class FakeInterpreter:
    def __init__(self, output: ClarificationAnswerInterpretation) -> None:
        self.output = output
        self.calls = 0

    def interpret(self, _input: object) -> ClarificationAnswerInterpretation:
        self.calls += 1
        return self.output


class FakeComposer:
    def __init__(self, *, fail: bool = False, invalid: bool = False) -> None:
        self.fail = fail
        self.invalid = invalid
        self.inputs: list[ClarificationPromptComposerInput] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.inputs.append(input)
        if self.fail:
            raise RuntimeError("offline")
        if self.invalid:
            return ClarificationPromptComposition(question_items=())
        return ClarificationPromptComposition(
            question_items=tuple(
                ClarificationQuestionItem(
                    requirement_id=requirement.requirement_id,
                    issue_ids=tuple(
                        issue.issue_id
                        for issue in input.issues
                        if issue.requirement_id == requirement.requirement_id
                    ),
                    question=f"Question for {requirement.requirement_id}?",
                )
                for requirement in input.requirements
            )
        )


def _template_selection(text: str, *items: tuple[str, str]) -> ClarificationTemporalTemplateSelection:
    return ClarificationTemporalTemplateSelection(
        selected=tuple(
            ClarificationTemporalTemplateBinding(
                template_handle=handle,
                span=_span(text, fragment),
                weekday=next(
                    (name for name in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
                    if name in fragment.casefold()),
                    None,
                ),
            )
            for handle, fragment in items
        ),
        complete=True,
    )


_CONTEXT = RequestContext(reference_date=date(2026, 9, 8), timezone="America/Los_Angeles")


def _initial(*, all_unknown: bool = True) -> RequestUnderstandingResult:
    unknowns = []
    if all_unknown:
        from award_agent.domain import UnknownField, UnknownReason

        unknowns = [
            UnknownField(field=field, reason=UnknownReason.MISSING, detail=f"{field} missing")
            for field in ("origin", "destination", "departure", "return_or_duration", "travelers")
        ]
    parsed = ParsedRequest(
        raw_text="Need a trip.",
        context=_CONTEXT,
        travelers=None,
        origins=[],
        destinations=[],
        departure_expression=None,
        return_expression=None,
        departure_window=None,
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=unknowns,
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK if all_unknown else ClarificationAction.NONE,
            field="origin" if all_unknown else None,
            question="Where from?" if all_unknown else None,
        ),
    )


def _span(text: str, value: str) -> MessageSpan:
    start = text.index(value)
    return MessageSpan(message_id="m1", start=start, end=start + len(value), text=value)


def _command(
    session: ClarificationSession,
    text: str,
    *,
    message_id: str = "m1",
    revision: int | None = None,
) -> ClarificationAnswerCommand:
    current = session.current_revision
    assert current.prompt is not None
    return ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=current.revision if revision is None else revision,
        prompt_id=current.prompt.prompt_id,
        message_id=message_id,
        text=text,
    )


def _reported_initial() -> RequestUnderstandingResult:
    parsed = ParsedRequest(
        raw_text="I want to go from LA to Tokyo for a 9-day trip.",
        context=_CONTEXT,
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="LA", raw_text="LA")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo")],
        departure_expression=None,
        return_expression=None,
        departure_window=None,
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[
            UnknownField(
                field="departure",
                reason=UnknownReason.MISSING,
                detail="departure missing",
            )
        ],
        conflicts=[],
        date_resolution=DateResolutionProposal(
            interpreted_duration=InterpretedDuration(
                raw_text="9-day trip", minimum_days=9, maximum_days=9
            )
        ),
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK,
            field="departure",
            question="When would you like to leave?",
        ),
    )


def _relative_temporal_initial() -> RequestUnderstandingResult:
    context = RequestContext(reference_date=date(2026, 9, 9), timezone="America/Los_Angeles")
    parsed = ParsedRequest(
        raw_text="I want to go to NYC from SF this weekend",
        context=context,
        travelers=1,
        origins=[LocationRef(kind=LocationKind.CITY, value="San Francisco", raw_text="SF")],
        destinations=[LocationRef(kind=LocationKind.CITY, value="New York City", raw_text="NYC")],
        departure_expression=None,
        return_expression=None,
        departure_window=None,
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[
            UnknownField(
                field="departure", reason=UnknownReason.MISSING, detail="departure missing"
            ),
            UnknownField(
                field="return_or_duration",
                reason=UnknownReason.MISSING,
                detail="return missing",
            ),
        ],
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK,
            field="departure",
            question="When would you like to leave?",
        ),
    )


def _temporal_amendment(
    text: str,
    quote: str,
    *,
    target: Literal[
        AmendmentTarget.DEPARTURE,
        AmendmentTarget.RETURN_OR_DURATION,
        AmendmentTarget.CONFLICTING_DATES,
    ],
    requirement_id: str,
) -> TemporalAmendment:
    return TemporalAmendment(
        amendment_id=f"{requirement_id}-relative",
        target=target,
        requirement_ids=(requirement_id,),
        span=_span(text, quote),
        temporal_text=quote,
    )


def test_all_blockers_can_be_resolved_atomically_and_ready() -> None:
    session = start_clarification(_initial(), session_id="s1")
    assert session.status is ClarificationSessionStatus.AWAITING_ANSWER
    prompt = session.current_revision.prompt
    assert prompt is not None
    assert [item.requirement_id for item in prompt.requirements] == [
        "origin",
        "destination",
        "departure",
        "return_or_duration",
        "travelers",
    ]
    text = "SFO to Tokyo, two travelers, depart October 6 and return October 16"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-1",
                    target=AmendmentTarget.ORIGIN,
                    requirement_ids=("origin",),
                    span=_span(text, "SFO"),
                    locations=(
                        LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),
                    ),
                ),
                LocationAmendment(
                    amendment_id="destination-1",
                    target=AmendmentTarget.DESTINATION,
                    requirement_ids=("destination",),
                    span=_span(text, "Tokyo"),
                    locations=(
                        LocationRef(kind=LocationKind.CITY, value="Tokyo", raw_text="Tokyo"),
                    ),
                ),
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
                TemporalAmendment(
                    amendment_id="departure-1",
                    target=AmendmentTarget.DEPARTURE,
                    requirement_ids=("departure",),
                    span=_span(text, "depart October 6"),
                    temporal_text="October 6",
                ),
                TemporalAmendment(
                    amendment_id="return-1",
                    target=AmendmentTarget.RETURN_OR_DURATION,
                    requirement_ids=("return_or_duration",),
                    span=_span(text, "return October 16"),
                    temporal_text="October 16",
                ),
            )
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), fake)

    assert transition.session.status is ClarificationSessionStatus.READY
    assert transition.revision.outcome is not None
    assert len(transition.revision.outcome.accepted_amendments) == 5
    assert transition.session.effective_request.travelers == 2
    assert transition.session.effective_request.departure_window == DateWindow(
        start=date(2026, 10, 6),
        end=date(2026, 10, 6),
        precision=DateWindowPrecision.EXACT,
        raw_text="October 6",
    )


def test_hedged_month_resolves_reported_departure_question_and_derives_return() -> None:
    session = start_clarification(_reported_initial(), session_id="reported")
    assert session.current_revision.prompt is not None
    assert [item.requirement_id for item in session.current_revision.prompt.requirements] == [
        "departure"
    ]
    text = "Maybe in October?"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TemporalAmendment(
                        amendment_id="departure-october",
                        target=AmendmentTarget.DEPARTURE,
                        requirement_ids=("departure",),
                        span=_span(text, text),
                        temporal_text=text,
                    ),
                )
            )
        ),
    )

    assert transition.session.status is ClarificationSessionStatus.READY
    assert transition.session.effective_request.departure_window == DateWindow(
        start=date(2026, 10, 1),
        end=date(2026, 10, 31),
        precision=DateWindowPrecision.MONTH,
        raw_text="October",
    )
    assert transition.session.effective_request.return_window == DateWindow(
        start=date(2026, 10, 10),
        end=date(2026, 11, 9),
        precision=DateWindowPrecision.DERIVED,
        raw_text="9-day trip",
    )


@pytest.mark.parametrize(
    ("text", "departure_quote", "return_quote", "expected_departure", "expected_return"),
    [
        (
            "1. This weekend\n2. On Monday",
            "1. This weekend",
            "2. On Monday",
            DateWindow(
                start=date(2026, 9, 12),
                end=date(2026, 9, 13),
                precision=DateWindowPrecision.WINDOW,
                raw_text="This weekend",
            ),
            DateWindow(
                start=date(2026, 9, 14),
                end=date(2026, 9, 14),
                precision=DateWindowPrecision.EXACT,
                raw_text="On Monday",
            ),
        ),
        (
            "Leave this friday and come back on Monday",
            "Leave this friday",
            "come back on Monday",
            DateWindow(
                start=date(2026, 9, 11),
                end=date(2026, 9, 11),
                precision=DateWindowPrecision.EXACT,
                raw_text="this friday",
            ),
            DateWindow(
                start=date(2026, 9, 14),
                end=date(2026, 9, 14),
                precision=DateWindowPrecision.EXACT,
                raw_text="on Monday",
            ),
        ),
    ],
)
def test_reported_relative_temporal_answers_resolve_without_no_progress_stop(
    text: str,
    departure_quote: str,
    return_quote: str,
    expected_departure: DateWindow,
    expected_return: DateWindow,
) -> None:
    session = start_clarification(_relative_temporal_initial(), session_id="relative-temporal")
    transition = apply_clarification_answer(
        session,
            _command(session, text),
            FakeInterpreter(
                ClarificationAnswerInterpretation(
                    temporal_template_selection=(
                        _template_selection(text, ("h2", "This weekend"), ("h5", "On Monday"))
                        if "weekend" in text
                        else _template_selection(text, ("h4", "this friday"), ("h5", "on Monday"))
                    )
                )
            ),
    )

    assert transition.session.status is ClarificationSessionStatus.READY
    assert transition.session.effective_request.departure_window == expected_departure
    assert transition.session.effective_request.return_window == expected_return


def test_template_selection_resolves_numbered_next_weekend_afterwards_and_singular_traveler() -> (
    None
):
    initial = _relative_temporal_initial()
    parsed = initial.parsed_request.model_copy(
        update={
            "travelers": None,
            "unknowns": initial.parsed_request.unknowns
            + [
                UnknownField(
                    field="travelers", reason=UnknownReason.MISSING, detail="travelers missing"
                )
            ],
        }
    )
    session = start_clarification(
        initial.model_copy(update={"parsed_request": parsed}), session_id="template-user-example"
    )
    text = "1. Next weekend\n2. The Wednesday afterwards\n3. Just myself"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TravelersAmendment(
                        amendment_id="traveler-alias",
                        target=AmendmentTarget.TRAVELERS,
                        requirement_ids=("travelers",),
                        span=_span(text, "Just myself"),
                        travelers=1,
                    ),
                ),
                temporal_template_selection=_template_selection(
                    text, ("h1", "Next weekend"), ("h6", "The Wednesday afterwards")
                ),
            )
        ),
    )

    effective = transition.session.effective_request
    assert effective.departure_window is not None
    assert (effective.departure_window.start, effective.departure_window.end) == (
        date(2026, 9, 19),
        date(2026, 9, 20),
    )
    assert effective.return_window is not None
    assert effective.return_window.start == effective.return_window.end == date(2026, 9, 23)
    assert effective.travelers == 1
    assert effective.temporal_contributions[1].template_provenance is not None
    assert effective.temporal_contributions[1].template_provenance.dependency_candidate_ids == (
        "c0",
    )


def test_registered_temporal_surface_cannot_also_use_legacy_normalization() -> None:
    session = start_clarification(_relative_temporal_initial(), session_id="registry-exclusive")
    text = "1. This weekend\n2. On Monday"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    _temporal_amendment(
                        text,
                        "1. This weekend",
                        target=AmendmentTarget.DEPARTURE,
                        requirement_id="departure",
                    ),
                ),
                temporal_template_selection=_template_selection(
                    text, ("h2", "This weekend"), ("h5", "On Monday")
                ),
            )
        ),
    )

    outcome = transition.revision.outcome
    assert outcome is not None
    assert [item.amendment_id for item in outcome.accepted_amendments] == [
        "m1:template:c0",
        "m1:template:c1",
    ]
    assert len(outcome.rejected_fragments) == 1
    assert "approved template registry" in outcome.rejected_fragments[0].detail
    assert len(transition.session.effective_request.temporal_contributions) == 2


def test_answer_interpreter_legacy_next_question_is_ignored_after_reduction() -> None:
    session = start_clarification(_initial(), session_id="next-question")
    text = "two travelers"
    accepted = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TravelersAmendment(
                        amendment_id="travelers-1",
                        target=AmendmentTarget.TRAVELERS,
                        requirement_ids=("travelers",),
                        span=_span(text, "two"),
                        travelers=2,
                    ),
                ),
                next_question="Thanks — where would you like to begin?",
                next_question_requirement_ids=(
                    "origin",
                    "destination",
                    "departure",
                    "return_or_duration",
                ),
            )
        ),
    )
    prompt = accepted.session.current_revision.prompt
    assert prompt is not None
    assert "Thanks — where would you like to begin?" not in prompt.message
    assert prompt.composition_source.value == "fallback"
    assert prompt.fallback_code == "receiver.no_usable_followup"


def test_receiver_followup_is_rendered_without_a_second_model_call() -> None:
    composer = FakeComposer()
    session = start_clarification(_initial(), session_id="receiver-followup", composer=composer)
    text = "two travelers"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TravelersAmendment(
                        amendment_id="travelers-1",
                        target=AmendmentTarget.TRAVELERS,
                        requirement_ids=("travelers",),
                        span=_span(text, "two"),
                        travelers=2,
                    ),
                ),
                next_question_requirement_ids=(
                    "origin",
                    "destination",
                    "departure",
                    "return_or_duration",
                ),
                next_question_items=(
                    "Where are you departing from?",
                    "Where would you like to go?",
                    "When would you like to leave?",
                    "When would you like to return?",
                ),
            )
        ),
        composer=composer,
    )

    prompt = transition.revision.prompt
    assert prompt is not None
    assert prompt.composition_source.value == "model"
    assert "Where are you departing from?" in prompt.message
    assert composer.inputs == []


def test_ordered_two_date_answer_resolves_both_pending_date_requirements() -> None:
    initial = _reported_initial().model_copy(
        update={
            "parsed_request": _reported_initial().parsed_request.model_copy(
                update={
                    "unknowns": [
                        UnknownField(
                            field="departure", reason=UnknownReason.MISSING, detail="departure missing"
                        ),
                        UnknownField(
                            field="return_or_duration",
                            reason=UnknownReason.MISSING,
                            detail="return missing",
                        ),
                    ],
                    "date_resolution": DateResolutionProposal(),
                }
            )
        }
    )
    session = start_clarification(initial, session_id="ordered-date-pair")
    text = "10/25 and 11/1"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    _temporal_amendment(
                        text, "10/25", target=AmendmentTarget.DEPARTURE, requirement_id="departure"
                    ),
                    _temporal_amendment(
                        text,
                        "11/1",
                        target=AmendmentTarget.RETURN_OR_DURATION,
                        requirement_id="return_or_duration",
                    ),
                )
            )
        ),
    )

    assert transition.revision.status is ClarificationSessionStatus.READY
    effective = transition.session.effective_request
    assert effective.departure_window is not None
    assert effective.departure_window.start == date(2026, 10, 25)
    assert effective.return_window is not None
    assert effective.return_window.start == date(2026, 11, 1)


def test_ordered_two_date_answer_recovers_from_the_receiver_rejecting_the_whole_pair() -> None:
    initial = _reported_initial().model_copy(
        update={
            "parsed_request": _reported_initial().parsed_request.model_copy(
                update={
                    "unknowns": [
                        UnknownField(field="departure", reason=UnknownReason.MISSING, detail="departure missing"),
                        UnknownField(
                            field="return_or_duration", reason=UnknownReason.MISSING, detail="return missing"
                        ),
                    ],
                    "date_resolution": DateResolutionProposal(),
                }
            )
        }
    )
    session = start_clarification(initial, session_id="recovered-ordered-date-pair")
    text = "10/25 and 11/1"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                rejected_fragments=(
                    RejectedFragment(
                        span=_span(text, text),
                        reason=RejectedFragmentReason.AMBIGUOUS,
                        detail="answer contains more than one date fact",
                        requirement_ids=("departure", "return_or_duration"),
                    ),
                )
            )
        ),
    )

    assert transition.revision.status is ClarificationSessionStatus.READY
    assert transition.revision.outcome is not None
    assert len(transition.revision.outcome.accepted_amendments) == 2
    assert transition.revision.outcome.rejected_fragments == ()


def test_second_prompt_call_is_not_made_and_fallback_keeps_semantic_transition() -> None:
    initial_composer = FakeComposer()
    session = start_clarification(
        _initial(), session_id="post-reduction-composer", composer=initial_composer
    )
    assert initial_composer.inputs == []
    assert session.current_revision.prompt is not None
    assert session.current_revision.prompt.composition_source.value == "fallback"

    text = "two travelers; early October"
    failed_composer = FakeComposer(fail=True)
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TravelersAmendment(
                        amendment_id="travelers-1",
                        target=AmendmentTarget.TRAVELERS,
                        requirement_ids=("travelers",),
                        span=_span(text, "two"),
                        travelers=2,
                    ),
                ),
                rejected_fragments=(
                    RejectedFragment(
                        span=_span(text, "early October"),
                        reason=RejectedFragmentReason.AMBIGUOUS,
                        detail="choose a bounded range",
                        requirement_ids=("departure",),
                    ),
                ),
            )
        ),
        composer=failed_composer,
    )

    revision = transition.revision
    assert revision.effective_request.travelers == 2
    assert revision.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert revision.prompt is not None
    assert revision.prompt.composition_source.value == "fallback"
    assert revision.prompt.fallback_code == "receiver.no_usable_followup"
    assert "early October" in revision.prompt.message
    assert failed_composer.inputs == []
    issue_by_requirement = {item.requirement_id: item for item in revision.prompt.issues}
    assert issue_by_requirement["departure"].span is not None
    assert issue_by_requirement["departure"].span.text == "early October"
    assert issue_by_requirement["origin"].span is None


def test_legacy_composer_is_not_called_for_ready_cancel_or_replay() -> None:
    ready_composer = FakeComposer()
    ready = start_clarification(_initial(all_unknown=False), composer=ready_composer)
    assert ready.status is ClarificationSessionStatus.READY
    assert ready_composer.inputs == []

    composer = FakeComposer()
    session = start_clarification(_initial(), session_id="composer-no-extra", composer=composer)
    assert composer.inputs == []
    cancelled = apply_clarification_answer(
        session,
        _command(session, "cancel"),
        FakeInterpreter(ClarificationAnswerInterpretation()),
        composer=composer,
    )
    assert cancelled.session.status is ClarificationSessionStatus.STOPPED
    assert composer.inputs == []

    interpreter = FakeInterpreter(ClarificationAnswerInterpretation())
    first = apply_clarification_answer(
        session, _command(session, "I don't know"), interpreter, composer=composer
    )
    assert composer.inputs == []
    replay = apply_clarification_answer(
        first.session,
        _command(first.session, "I don't know", revision=0),
        interpreter,
        composer=composer,
    )
    assert replay.replayed is True
    assert composer.inputs == []


def test_missing_receiver_followup_falls_back_after_preserving_reduced_state() -> None:
    composer = FakeComposer()
    session = start_clarification(_initial(), session_id="invalid-composition", composer=composer)
    text = "two travelers"

    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                amendments=(
                    TravelersAmendment(
                        amendment_id="travelers-1",
                        target=AmendmentTarget.TRAVELERS,
                        requirement_ids=("travelers",),
                        span=_span(text, "two"),
                        travelers=2,
                    ),
                )
            )
        ),
        composer=FakeComposer(invalid=True),
    )

    assert transition.session.effective_request.travelers == 2
    assert transition.revision.prompt is not None
    assert transition.revision.prompt.fallback_code == "receiver.no_usable_followup"


def test_registry_unresolved_ambiguity_links_the_active_temporal_blocker() -> None:
    session = start_clarification(_reported_initial(), session_id="registry-ambiguity")
    text = "this Friday"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                temporal_template_selection=ClarificationTemporalTemplateSelection(
                    unresolved=(
                        ClarificationTemporalTemplateUnresolved(
                            span=_span(text, text),
                            requirement_ids=("departure",),
                            reason="ambiguous",
                        ),
                    ),
                    complete=True,
                )
            )
        ),
    )

    outcome = transition.revision.outcome
    assert outcome is not None
    assert [(item.reason.value, item.requirement_ids, item.reason_code) for item in outcome.rejected_fragments] == [
        (
            "ambiguous",
            ("departure",),
            "clarification-temporal-templates-v2.unresolved.ambiguous",
        )
    ]
    prompt = transition.revision.prompt
    assert prompt is not None
    departure_issue = next(item for item in prompt.issues if item.requirement_id == "departure")
    assert departure_issue.span is not None and departure_issue.span.text == "this Friday"
    assert departure_issue.kind.value == "ambiguous"


def test_conflict_linked_rejection_stays_nonterminal_and_composes_conflict_issue() -> None:
    initial = _initial().model_copy(
        update={
            "parsed_request": _initial().parsed_request.model_copy(
                update={
                    "conflicts": [
                        Conflict(
                            code="return_before_departure",
                            fields=["departure"],
                            detail="conflict",
                        )
                    ],
                    "departure_window": DateWindow(
                        start=date(2026, 10, 10),
                        end=date(2026, 10, 10),
                        precision=DateWindowPrecision.EXACT,
                        raw_text="October 10",
                    ),
                    "return_window": DateWindow(
                        start=date(2026, 10, 1),
                        end=date(2026, 10, 1),
                        precision=DateWindowPrecision.EXACT,
                        raw_text="October 1",
                    ),
                }
            )
        }
    )
    composer = FakeComposer()
    session = start_clarification(initial, session_id="conflict-rejection", composer=composer)
    text = "Those dates conflict"
    transition = apply_clarification_answer(
        session,
        _command(session, text),
        FakeInterpreter(
            ClarificationAnswerInterpretation(
                rejected_fragments=(
                    RejectedFragment(
                        span=_span(text, text),
                        reason=RejectedFragmentReason.AMBIGUOUS,
                        detail="ambiguous conflict",
                        requirement_ids=("conflict:return_before_departure",),
                        reason_code="test.conflict.ambiguous",
                    ),
                )
            )
        ),
        composer=composer,
    )

    assert transition.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert transition.revision.prompt is not None
    issue = next(
        item
        for item in transition.revision.prompt.issues
        if item.requirement_id == "conflict:return_before_departure"
    )
    assert issue.kind.value == "conflict"
    assert issue.span is not None and issue.span.text == text


@pytest.mark.parametrize(
    ("terminal_kind", "expected_stop"),
    [
        ("unsupported", ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION),
        ("no_progress", ClarificationStopReason.NO_PROGRESS_LIMIT),
        ("turn_limit", ClarificationStopReason.ANSWER_TURN_LIMIT),
    ],
)
def test_terminal_answer_paths_do_not_call_composer(
    terminal_kind: str, expected_stop: ClarificationStopReason
) -> None:
    composer = FakeComposer()
    limits = ClarificationSessionLimits(max_answer_turns=1) if terminal_kind == "turn_limit" else None
    session = start_clarification(
        _initial(), session_id=f"terminal-{terminal_kind}", composer=composer, limits=limits
    )
    assert composer.inputs == []
    if terminal_kind == "unsupported":
        transition = apply_clarification_answer(
            session,
            _command(session, "actually add a constraint"),
            FakeInterpreter(
                ClarificationAnswerInterpretation(
                    rejected_fragments=(
                        RejectedFragment(
                            span=_span("actually add a constraint", "constraint"),
                            reason=RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION,
                            detail="unsupported",
                            requirement_ids=("origin",),
                        ),
                    )
                )
            ),
            composer=composer,
        )
    elif terminal_kind == "no_progress":
        first = apply_clarification_answer(
            session,
            _command(session, "I do not know"),
            FakeInterpreter(ClarificationAnswerInterpretation()),
            composer=composer,
        )
        assert composer.inputs == []
        transition = apply_clarification_answer(
            first.session,
            _command(first.session, "I still do not know", message_id="m2"),
            FakeInterpreter(ClarificationAnswerInterpretation()),
            composer=composer,
        )
    else:
        transition = apply_clarification_answer(
            session,
            _command(session, "I do not know"),
            FakeInterpreter(ClarificationAnswerInterpretation()),
            composer=composer,
        )

    assert transition.session.status is ClarificationSessionStatus.STOPPED
    assert transition.revision.stop_reason is expected_stop
    assert composer.inputs == []


def test_replay_precedes_freshness_and_message_reuse_with_new_text_fails() -> None:
    session = start_clarification(_initial(), session_id="s1")
    text = "two travelers"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
            )
        )
    )
    first = apply_clarification_answer(session, _command(session, text), fake)
    replay_command = _command(first.session, text, revision=0)
    replay = apply_clarification_answer(first.session, replay_command, fake)

    assert replay.replayed is True
    assert replay.revision.revision == 1
    assert replay.session.current_revision.revision == 1
    assert fake.calls == 1
    with pytest.raises(ClarificationCommandError, match="different text"):
        apply_clarification_answer(
            first.session, _command(first.session, "three travelers", revision=0), fake
        )


def test_cancel_does_not_call_interpreter_and_no_progress_stops_on_second_answer() -> None:
    session = start_clarification(_initial(), session_id="s1")
    fake = FakeInterpreter(ClarificationAnswerInterpretation())
    cancelled = apply_clarification_answer(session, _command(session, "cancel"), fake)
    assert cancelled.session.status is ClarificationSessionStatus.STOPPED
    assert cancelled.revision.stop_reason is ClarificationStopReason.CANCELLED
    assert fake.calls == 0

    session = start_clarification(_initial(), session_id="s2")
    first = apply_clarification_answer(session, _command(session, "I do not know"), fake)
    assert first.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    second = apply_clarification_answer(
        first.session, _command(first.session, "I still do not know", message_id="m2"), fake
    )
    assert second.session.status is ClarificationSessionStatus.STOPPED
    assert second.revision.stop_reason is ClarificationStopReason.NO_PROGRESS_LIMIT


def test_unsupported_revision_stops_without_discarding_valid_sibling() -> None:
    session = start_clarification(_initial(), session_id="s1")
    text = "two travelers and add first class"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="travelers-1",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
            ),
            rejected_fragments=(
                RejectedFragment(
                    span=_span(text, "first class"),
                    reason=RejectedFragmentReason.UNSUPPORTED_REQUEST_REVISION,
                    detail="cabin revision is deferred",
                ),
            ),
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), fake)

    assert transition.session.status is ClarificationSessionStatus.STOPPED
    assert transition.revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION
    assert transition.session.effective_request.travelers == 2


def test_correction_cannot_fill_an_unresolved_field_and_duplicate_field_writes_reask() -> None:
    session = start_clarification(_initial(), session_id="s1")
    correction_text = "Actually change the origin to SFO"
    correction = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin-correction",
                    target=AmendmentTarget.ORIGIN,
                    is_correction=True,
                    span=_span(correction_text, "Actually change the origin to SFO"),
                    locations=(
                        LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),
                    ),
                ),
            )
        )
    )
    stopped = apply_clarification_answer(session, _command(session, correction_text), correction)
    assert stopped.session.status is ClarificationSessionStatus.STOPPED
    assert stopped.revision.stop_reason is ClarificationStopReason.UNSUPPORTED_REQUEST_REVISION
    assert not stopped.session.effective_request.origins

    session = start_clarification(_initial(), session_id="s2")
    text = "two travelers or three travelers"
    duplicate = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                TravelersAmendment(
                    amendment_id="two",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "two"),
                    travelers=2,
                ),
                TravelersAmendment(
                    amendment_id="three",
                    target=AmendmentTarget.TRAVELERS,
                    requirement_ids=("travelers",),
                    span=_span(text, "three"),
                    travelers=3,
                ),
            )
        )
    )
    reasked = apply_clarification_answer(session, _command(session, text), duplicate)
    assert reasked.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert reasked.session.effective_request.travelers is None
    assert reasked.revision.outcome is not None
    assert [item.reason for item in reasked.revision.outcome.rejected_fragments] == [
        RejectedFragmentReason.AMBIGUOUS,
        RejectedFragmentReason.AMBIGUOUS,
    ]


def test_stale_wrong_prompt_and_terminal_commands_do_not_call_interpreter() -> None:
    session = start_clarification(_initial(), session_id="s1")
    fake = FakeInterpreter(ClarificationAnswerInterpretation())
    with pytest.raises(ClarificationCommandError, match="stale"):
        apply_clarification_answer(session, _command(session, "hello", revision=4), fake)
    current = session.current_revision
    assert current.prompt is not None
    wrong_prompt = ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=0,
        prompt_id="wrong",
        message_id="m1",
        text="hello",
    )
    with pytest.raises(ClarificationCommandError, match="prompt ID"):
        apply_clarification_answer(session, wrong_prompt, fake)
    stopped = apply_clarification_answer(session, _command(session, "Please cancel."), fake)
    terminal_command = ClarificationAnswerCommand(
        session_id=stopped.session.session_id,
        expected_revision=stopped.revision.revision,
        prompt_id="former-prompt",
        message_id="m2",
        text="hello",
    )
    with pytest.raises(ClarificationCommandError, match="terminal"):
        apply_clarification_answer(stopped.session, terminal_command, fake)
    assert fake.calls == 0


def test_accepting_numbered_temporal_answer_reaches_ready_with_visible_assumptions() -> None:
    """The owner-reported reasonable reply must not consume a no-progress turn."""

    initial = _initial()
    parsed = initial.parsed_request.model_copy(
        update={
            "destinations": [LocationRef(kind=LocationKind.COUNTRY, value="France", raw_text="France")],
            "unknowns": [item for item in initial.parsed_request.unknowns if item.field != "destination"],
            "context": RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
        }
    )
    session = start_clarification(initial.model_copy(update={"parsed_request": parsed}), session_id="accepting")
    text = "1. SFO\n2. Early next month\n3. For a week\n4. I'm solo traveling"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin", target=AmendmentTarget.ORIGIN, requirement_ids=("origin",),
                    span=_span(text, "1. SFO"),
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
                ),
                TravelersAmendment(
                    amendment_id="travelers", target=AmendmentTarget.TRAVELERS, requirement_ids=("travelers",),
                    span=_span(text, "4. I'm solo traveling"), travelers=1,
                ),
            ),
            # v1 classifies the overlapping relative cue as unresolved; the
            # accepting registry owns the span and suppresses that duplicate.
            temporal_template_selection=ClarificationTemporalTemplateSelection(
                unresolved=(
                    ClarificationTemporalTemplateUnresolved(
                        span=_span(text, "Early next month"), requirement_ids=("departure",)
                    ),
                ), complete=True,
            ),
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=(
                    ClarificationTemporalApproximationBinding(approximation_handle="a1", span=_span(text, "Early next month"), month_reference="next_month"),
                    ClarificationTemporalApproximationBinding(approximation_handle="a4", span=_span(text, "a week")),
                ), complete=True,
            ),
        )
    )
    transition = apply_clarification_answer(session, _command(session, text), fake)
    assert transition.session.status is ClarificationSessionStatus.READY
    effective = transition.session.effective_request
    assert effective.departure_window is not None
    assert (effective.departure_window.start, effective.departure_window.end) == (date(2026, 10, 1), date(2026, 10, 10))
    assert effective.interpreted_duration is not None
    assert (effective.interpreted_duration.minimum_days, effective.interpreted_duration.maximum_days) == (7, 7)
    outcome = transition.revision.outcome
    assert outcome is not None
    assert all("registered temporal wording" not in item.detail for item in outcome.rejected_fragments)
    assert all(item.interpretation_provenance is not None for item in effective.temporal_contributions)


def test_accepting_temporal_correction_replaces_the_stale_assumption() -> None:
    initial = _reported_initial()
    # Keep origin unresolved so a later correction is accepted while the
    # session remains conversationally active.
    parsed = initial.parsed_request.model_copy(
        update={
            "origins": [],
            "unknowns": [
                UnknownField(field="origin", reason=UnknownReason.MISSING, detail="origin missing"),
                *[item for item in initial.parsed_request.unknowns if item.field == "departure"],
            ],
            "context": RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
        }
    )
    session = start_clarification(initial.model_copy(update={"parsed_request": parsed}), session_id="correcting")
    first_text = "2. early next month"
    first = FakeInterpreter(
        ClarificationAnswerInterpretation(
            temporal_template_selection=ClarificationTemporalTemplateSelection(
                unresolved=(ClarificationTemporalTemplateUnresolved(
                    span=_span(first_text, "early next month"), requirement_ids=("departure",)
                ),), complete=True
            ),
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=(ClarificationTemporalApproximationBinding(approximation_handle="a1", span=_span(first_text, "early next month"), month_reference="next_month"),), complete=True
            ),
        )
    )
    after_first = apply_clarification_answer(session, _command(session, first_text), first).session
    assert after_first.effective_request.departure_window is not None
    correction_text = "Actually, leave late October"
    correction = FakeInterpreter(
        ClarificationAnswerInterpretation(
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                    selected=(ClarificationTemporalApproximationBinding(
                        approximation_handle="a3", span=_span(correction_text, "late October").model_copy(update={"message_id": "m2"}), month_reference="named_month", month_name="october", is_correction=True
                ),), complete=True
            )
        )
    )
    transition = apply_clarification_answer(after_first, _command(after_first, correction_text, message_id="m2"), correction)
    assert transition.session.effective_request.departure_window is not None
    assert transition.session.effective_request.departure_window.start == date(2026, 10, 21)
    assert len([
        item for item in transition.session.effective_request.temporal_contributions
        if item.kind.value == "departure_window"
    ]) == 1


def test_multi_turn_accepting_assumptions_coexist_with_message_scoped_provenance() -> None:
    session = start_clarification(_initial(), session_id="multi-assumptions")
    first_text = "1. SFO\n2. France\n3. early next month\n5. solo"
    first = FakeInterpreter(
        ClarificationAnswerInterpretation(
            amendments=(
                LocationAmendment(
                    amendment_id="origin", target=AmendmentTarget.ORIGIN, requirement_ids=("origin",),
                    span=_span(first_text, "1. SFO"),
                    locations=(LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO"),),
                ),
                LocationAmendment(
                    amendment_id="destination", target=AmendmentTarget.DESTINATION, requirement_ids=("destination",),
                    span=_span(first_text, "2. France"),
                    locations=(LocationRef(kind=LocationKind.COUNTRY, value="France", raw_text="France"),),
                ),
                TravelersAmendment(
                    amendment_id="travelers", target=AmendmentTarget.TRAVELERS, requirement_ids=("travelers",),
                    span=_span(first_text, "5. solo"), travelers=1,
                ),
            ),
            temporal_template_selection=ClarificationTemporalTemplateSelection(
                unresolved=(ClarificationTemporalTemplateUnresolved(
                    span=_span(first_text, "early next month"), requirement_ids=("departure",)
                ),), complete=True
            ),
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=(ClarificationTemporalApproximationBinding(
                    approximation_handle="a1", span=_span(first_text, "early next month"), month_reference="next_month"
                ),), complete=True
            ),
        )
    )
    after_first = apply_clarification_answer(session, _command(session, first_text), first).session
    assert after_first.status is ClarificationSessionStatus.AWAITING_ANSWER
    second_text = "a week"
    second = FakeInterpreter(
        ClarificationAnswerInterpretation(
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=(ClarificationTemporalApproximationBinding(
                    approximation_handle="a4",
                    span=_span(second_text, second_text).model_copy(update={"message_id": "m2"}),
                ),), complete=True
            )
        )
    )
    transition = apply_clarification_answer(
        after_first, _command(after_first, second_text, message_id="m2"), second
    )
    assert transition.session.status is ClarificationSessionStatus.READY
    contributions = transition.session.effective_request.temporal_contributions
    ids = [item.interpretation_provenance.candidate_ids[0] for item in contributions if item.interpretation_provenance]
    assert ids == ["m1:a0", "m2:a0"]


def test_unresolved_accepting_alternative_stays_blocked_without_duplicate_or_mutation() -> None:
    session = start_clarification(_reported_initial(), session_id="alternatives")
    text = "early next month or late October"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            temporal_template_selection=ClarificationTemporalTemplateSelection(
                unresolved=(ClarificationTemporalTemplateUnresolved(
                    span=_span(text, "early next month"), requirement_ids=("departure",), reason="ambiguous"
                ),),
                complete=True,
            ),
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                unresolved=(ClarificationTemporalApproximationUnresolved(
                    span=_span(text, text), requirement_ids=("departure",), reason="ambiguous"
                ),),
                complete=True,
            )
        )
    )
    transition = apply_clarification_answer(session, _command(session, text), fake)
    assert transition.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert transition.session.effective_request.departure_window is None
    assert transition.revision.outcome is not None
    assert len(transition.revision.outcome.rejected_fragments) == 1


def test_positive_accepting_selection_in_a_disjunction_downgrades_to_one_ambiguity() -> None:
    session = start_clarification(_reported_initial(), session_id="selected-alternative")
    text = "early next month or late October"
    fake = FakeInterpreter(
        ClarificationAnswerInterpretation(
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=(
                    ClarificationTemporalApproximationBinding(
                        approximation_handle="a1",
                        span=_span(text, "early next month"),
                        month_reference="next_month",
                    ),
                ),
                complete=True,
            )
        )
    )

    transition = apply_clarification_answer(session, _command(session, text), fake)

    assert transition.session.status is ClarificationSessionStatus.AWAITING_ANSWER
    assert transition.session.effective_request.departure_window is None
    assert transition.revision.outcome is not None
    rejected = transition.revision.outcome.rejected_fragments
    assert len(rejected) == 1
    assert rejected[0].reason is RejectedFragmentReason.AMBIGUOUS
    assert rejected[0].span.text == text
    assert rejected[0].requirement_ids == ("departure",)
