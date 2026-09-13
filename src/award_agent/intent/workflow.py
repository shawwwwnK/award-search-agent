"""One-call semantic initial-intent workflow.

No request-text temporal scanner, candidate catalogue, or selector is imported
by this live path. The receiver reads language; this module grounds quoted
facts and evaluates typed calendar calculations only.
"""

from __future__ import annotations

import re

from award_agent.domain import (
    Ambiguity,
    CalendarOperationReceipt,
    CoarseIntentExtraction,
    Conflict,
    DateWindow,
    GroundedTemporalEvidence,
    LocationRef,
    OneWayDateResolutionProposal,
    ParsedRequest,
    ProposedDateWindow,
    RawRequest,
    RequestUnderstandingOutcome,
    RequestUnderstandingResult,
    SearchMode,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    UnknownField,
    UnknownReason,
    UnresolvedTemporalConstraint,
    UnsupportedRequestPart,
    UnsupportedRequestPartCode,
)
from award_agent.intent.calendar_plan import (
    IntentCalendarOperationalError,
    departure_windows,
    evaluate_departure_calendar_plan,
)
from award_agent.intent.clarification import decide_clarification
from award_agent.intent.evidence import resolve_source_quote
from award_agent.intent.holidays import HolidayDateProvider
from award_agent.intent.locations import preserve_explicit_airport_codes
from award_agent.intent.openai_interpreter import (
    OpenAISemanticIntentError,
    OpenAISemanticIntentRepresentationError,
    WireIntentProposal,
)
from award_agent.intent.semantic import (
    SemanticFact,
    SemanticFactTarget,
    SemanticIntentInput,
    SemanticIntentInterpreter,
    SemanticIntentProposal,
    SemanticTemporalFact,
    SemanticTemporalTarget,
    SemanticUnresolved,
    SemanticValidationIssue,
)


class _SemanticComponentError(ValueError):
    """Attach a deterministic component identity to a repairable failure."""

    def __init__(self, component_id: str | None, error: BaseException) -> None:
        super().__init__(str(error))
        self.component_id = component_id


def _evidence(
    request: RawRequest, quote: str, occurrence: int | None, claim: TemporalEvidenceClaim
) -> GroundedTemporalEvidence:
    span = resolve_source_quote(
        request.text, quote, claim_id=claim.value, occurrence_index=occurrence
    )
    return GroundedTemporalEvidence(
        evidence_id=f"request:{span.start}:{span.end}", claim_ids=[claim], span=span
    )


def _extraction(request: RawRequest, proposal: SemanticIntentProposal) -> CoarseIntentExtraction:
    origins, destinations, cabins, modes, constraints, ambiguities = [], [], [], [], [], []
    travelers = repositioning = None
    for fact in proposal.facts:
        # Validate every receiver assertion against immutable source text.
        try:
            _evidence(request, fact.quote, fact.occurrence_index, TemporalEvidenceClaim.UNSPECIFIED)
        except Exception as error:
            raise _SemanticComponentError(fact.component_id, error) from error
        if fact.target is SemanticFactTarget.ORIGIN:
            assert fact.location_kind is not None and fact.location_value is not None
            origins.append(
                LocationRef(kind=fact.location_kind, value=fact.location_value, raw_text=fact.quote)
            )
        elif fact.target is SemanticFactTarget.DESTINATION:
            assert fact.location_kind is not None and fact.location_value is not None
            destinations.append(
                LocationRef(kind=fact.location_kind, value=fact.location_value, raw_text=fact.quote)
            )
        elif fact.target is SemanticFactTarget.TRAVELERS:
            if travelers is not None and travelers != fact.travelers:
                ambiguities.append(
                    Ambiguity(
                        field="travelers",
                        detail="The request states conflicting traveler counts.",
                        raw_text=fact.quote,
                    )
                )
            travelers = fact.travelers
        elif fact.target is SemanticFactTarget.CABIN:
            assert fact.cabin is not None
            cabins.append(fact.cabin)
        elif fact.target is SemanticFactTarget.SEARCH_MODE:
            assert fact.search_mode is not None
            modes.append(fact.search_mode)
        elif fact.target is SemanticFactTarget.REPOSITIONING:
            if repositioning is not None and repositioning != fact.repositioning_allowed:
                ambiguities.append(
                    Ambiguity(
                        field="repositioning_allowed",
                        detail="The request states conflicting repositioning preferences.",
                        raw_text=fact.quote,
                    )
                )
            repositioning = fact.repositioning_allowed
        else:
            assert fact.hard_constraint is not None
            constraints.append(fact.hard_constraint)
    for item in proposal.unresolved:
        try:
            _evidence(request, item.quote, item.occurrence_index, TemporalEvidenceClaim.UNSPECIFIED)
        except Exception as error:
            raise _SemanticComponentError(item.component_id, error) from error
        if item.field in {"origin", "destination", "travelers", "departure", "cabin"}:
            ambiguities.append(Ambiguity(field=item.field, detail=item.reason, raw_text=item.quote))
    return CoarseIntentExtraction(
        travelers=travelers,
        origins=origins,
        destinations=destinations,
        cabins=list(dict.fromkeys(cabins)),
        search_modes=list(dict.fromkeys(modes)) or [SearchMode.AWARD],
        repositioning_allowed=repositioning,
        hard_constraints=constraints,
        ambiguities=ambiguities,
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text=item.quote,
                claim_ids=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
                occurrence_index=item.occurrence_index,
            )
            for item in proposal.temporal_facts
            if item.target is SemanticTemporalTarget.DEPARTURE
        ],
    )


def _scope_parts(
    request: RawRequest, proposal: SemanticIntentProposal, modes: list[SearchMode]
) -> list[UnsupportedRequestPart]:
    unsupported = [
        item
        for item in proposal.temporal_facts
        if item.target in {SemanticTemporalTarget.RETURN, SemanticTemporalTarget.DURATION}
    ]
    notices = list(proposal.scope_notices)
    result = []
    # Scope notices are grounded first and independently; no malformed
    # outbound calculation is allowed to hide an explicit separate-leg request.
    notice_evidence = []
    valid_notices = []
    for item in notices:
        try:
            notice_evidence.append(
                _evidence(
                    request,
                    item.quote,
                    item.occurrence_index,
                    TemporalEvidenceClaim.RETURN_PERIOD
                    if item.kind.value == "return"
                    else TemporalEvidenceClaim.DURATION,
                )
            )
            valid_notices.append(item)
        except Exception:  # noqa: BLE001, S112 - invalid sibling cannot hide scope notice
            continue
    notices = valid_notices
    valid_unsupported = []
    evidence = []
    for unsupported_item in unsupported:
        try:
            evidence.append(_evidence(request, unsupported_item.quote, unsupported_item.occurrence_index, TemporalEvidenceClaim.RETURN_PERIOD if unsupported_item.target is SemanticTemporalTarget.RETURN else TemporalEvidenceClaim.DURATION))
            valid_unsupported.append(unsupported_item)
        except Exception:  # noqa: BLE001, S112 - invalid sibling cannot hide scope notice
            continue
    if valid_unsupported:
        result.append(
            UnsupportedRequestPart(
                code=UnsupportedRequestPartCode.RETURN_OR_DURATION_NOT_SUPPORTED,
                detail="Return dates and trip durations require a separate one-way request.",
                raw_text=valid_unsupported[0].quote,
                evidence=[*notice_evidence, *evidence],
            )
        )
    elif notices:
        result.append(
            UnsupportedRequestPart(
                code=UnsupportedRequestPartCode.RETURN_OR_DURATION_NOT_SUPPORTED,
                detail="Return dates and trip durations require a separate one-way request.",
                raw_text=notices[0].quote,
                evidence=notice_evidence,
            )
        )
    if SearchMode.CASH in modes and SearchMode.AWARD not in modes:
        cash_evidence = [
            _evidence(
                request,
                fact.quote,
                fact.occurrence_index,
                TemporalEvidenceClaim.UNSPECIFIED,
            )
            for fact in proposal.facts
            if fact.target is SemanticFactTarget.SEARCH_MODE and fact.search_mode is SearchMode.CASH
        ]
        result.append(
            UnsupportedRequestPart(
                code=UnsupportedRequestPartCode.CASH_ONLY_NOT_SUPPORTED,
                detail="Cash-only search is outside the active award-search workflow.",
                evidence=cash_evidence,
            )
        )
    return result


def _scope_modes(request: RawRequest, proposal: SemanticIntentProposal) -> list[SearchMode]:
    """Read and ground only the facts needed for award/cash policy."""
    modes: list[SearchMode] = []
    for fact in proposal.facts:
        if fact.target is SemanticFactTarget.SEARCH_MODE:
            try:
                _evidence(request, fact.quote, fact.occurrence_index, TemporalEvidenceClaim.UNSPECIFIED)
            except Exception:  # noqa: BLE001, S112 - invalid mode cannot hide scope notice
                # Scope policy is computed from independently grounded modes.
                # An invalid mode can be repaired/degraded later but cannot
                # conceal a grounded return/duration notice.
                continue
            assert fact.search_mode is not None
            modes.append(fact.search_mode)
    return list(dict.fromkeys(modes)) or [SearchMode.AWARD]


def _scope_safe_projection(
    request: RawRequest, proposal: SemanticIntentProposal
) -> SemanticIntentProposal:
    """Drop only invalid active siblings after a scope notice is grounded."""
    facts: list[SemanticFact] = []
    for fact in proposal.facts:
        try:
            _evidence(request, fact.quote, fact.occurrence_index, TemporalEvidenceClaim.UNSPECIFIED)
        except Exception:  # noqa: BLE001, S112 - invalid sibling cannot erase scope result
            continue
        facts.append(fact)
    temporal_facts: list[SemanticTemporalFact] = []
    for temporal_fact in proposal.temporal_facts:
        if temporal_fact.target is not SemanticTemporalTarget.DEPARTURE:
            continue
        try:
            _evidence(
                request,
                temporal_fact.quote,
                temporal_fact.occurrence_index,
                TemporalEvidenceClaim.DEPARTURE_PERIOD,
            )
        except Exception:  # noqa: BLE001, S112 - invalid sibling cannot erase scope result
            continue
        temporal_facts.append(temporal_fact)
    unresolved: list[SemanticUnresolved] = []
    for item in proposal.unresolved:
        try:
            _evidence(request, item.quote, item.occurrence_index, TemporalEvidenceClaim.UNSPECIFIED)
        except Exception:  # noqa: BLE001, S112 - invalid sibling cannot erase scope result
            continue
        unresolved.append(item)
    return proposal.model_copy(
        update={
            "facts": tuple(facts),
            "temporal_facts": tuple(temporal_facts),
            "unresolved": tuple(unresolved),
        }
    )


def _scope_safe_outbound_projection(proposal: SemanticIntentProposal) -> SemanticIntentProposal:
    """Remove invalid active outbound years without affecting scope notices."""
    valid: list[SemanticTemporalFact] = []
    for fact in proposal.temporal_facts:
        if fact.target is not SemanticTemporalTarget.DEPARTURE:
            continue
        try:
            _validate_year_quote(fact)
        except _SemanticComponentError:
            continue
        valid.append(fact)
    return proposal.model_copy(update={"temporal_facts": tuple(valid)})


def _validate_year_quote(fact: SemanticTemporalFact) -> None:
    for value in (fact.start_year, fact.end_year, fact.period_year, fact.anchor_year):
        if value is not None and re.search(rf"(?<![0-9]){value}(?![0-9])", fact.quote) is None:
            raise _SemanticComponentError(
                fact.component_id or fact.fact_id,
                ValueError("explicit calendar year is not grounded by its quote"),
            )


def _validate_year_quotes(proposal: SemanticIntentProposal) -> None:
    for fact in proposal.temporal_facts:
        _validate_year_quote(fact)


def _require_operation_recheck(proposal: SemanticIntentProposal) -> None:
    """Request the single model repair from typed receiver state only."""
    item = next(
        (
            candidate
            for candidate in proposal.unresolved
            if candidate.field == "departure" and candidate.operation_recheck
        ),
        None,
    )
    if item is not None:
        raise _SemanticComponentError(
            item.component_id,
            ValueError("receiver requested a supported calendar-operation recheck"),
        )


def _issue(error: BaseException, path: str) -> SemanticValidationIssue:
    component_id = error.component_id if isinstance(error, _SemanticComponentError) else None
    return SemanticValidationIssue(
        code="semantic_proposal_validation_failed",
        path=("components", component_id) if component_id else (path,),
        detail=str(error)[:500],
    )


def _unknowns(
    extraction: CoarseIntentExtraction,
    departure: DateWindow | None,
    unresolved: tuple[SemanticTemporalFact, ...],
    pending: str | None,
) -> list[UnknownField]:
    values = []
    if not extraction.origins:
        values.append(
            UnknownField(
                field="origin",
                reason=UnknownReason.MISSING,
                detail="No departure location was stated.",
            )
        )
    if not extraction.destinations:
        values.append(
            UnknownField(
                field="destination",
                reason=UnknownReason.MISSING,
                detail="No destination was stated.",
            )
        )
    if extraction.travelers is None:
        values.append(
            UnknownField(
                field="travelers",
                reason=UnknownReason.MISSING,
                detail="The number of travelers was not stated.",
            )
        )
    if departure is None:
        item = next(iter(unresolved), None)
        values.append(
            UnknownField(
                field="departure",
                reason=UnknownReason.UNRESOLVED if item or pending else UnknownReason.MISSING,
                detail=getattr(item, "reason", None)
                or pending
                or "No bounded departure timing was stated.",
                raw_text=getattr(item, "quote", None),
            )
        )
    if not extraction.cabins:
        values.append(
            UnknownField(
                field="cabin",
                reason=UnknownReason.MISSING,
                detail="No cabin preference was stated.",
            )
        )
    values.extend(
        UnknownField(
            field=item.field,
            reason=UnknownReason.AMBIGUOUS,
            detail=item.detail,
            raw_text=item.raw_text,
        )
        for item in extraction.ambiguities
    )
    return values


def _conflicts(
    windows: tuple[DateWindow, ...], evidence: list[GroundedTemporalEvidence]
) -> list[Conflict]:
    if len(windows) > 1 and min(item.end for item in windows) < max(item.start for item in windows):
        return [
            Conflict(
                code="departure_constraints_conflict",
                fields=["departure"],
                detail="The departure-date constraints do not overlap.",
                evidence_by_alternative={"departure": evidence},
            )
        ]
    return []


def _compile(
    request: RawRequest,
    proposal: SemanticIntentProposal,
    holiday_provider: HolidayDateProvider | None,
) -> tuple[
    CoarseIntentExtraction,
    DateWindow | None,
    tuple[SemanticTemporalFact, ...],
    tuple[DateWindow, ...],
]:
    extraction = _extraction(request, proposal)
    departure, unresolved = evaluate_departure_calendar_plan(
        proposal.temporal_facts, request.context, holiday_provider
    )
    return (
        extraction,
        departure,
        unresolved,
        departure_windows(proposal.temporal_facts, request.context, holiday_provider),
    )


def understand_request(
    request: RawRequest,
    interpreter: SemanticIntentInterpreter,
    holiday_provider: HolidayDateProvider | None = None,
) -> RequestUnderstandingResult:
    """One semantic read plus at most one component-preserving proposal repair.

    Contract/operational failures become a normal safe clarification state;
    ordinary user wording never escapes here as an exception.
    """
    # Blank input is a deterministic missing-information result, not a model
    # call or an operational failure.
    if not request.text.strip():
        extraction = CoarseIntentExtraction(search_modes=[SearchMode.AWARD])
        parsed = _parsed(request, SemanticIntentProposal(), extraction, None, (), (), [])
        return RequestUnderstandingResult(
            parsed_request=parsed, clarification=decide_clarification(parsed)
        )

    input = SemanticIntentInput(request_text=request.text)
    proposal = SemanticIntentProposal()
    repair_consumed = False
    # Transport/schema preflight errors are operational, so retrying semantic
    # content is both futile and contrary to the one-repair budget.
    try:
        proposal = interpreter.interpret(input)
        if not isinstance(proposal, SemanticIntentProposal):
            raise OpenAISemanticIntentRepresentationError(
                WireIntentProposal(),
                (
                    SemanticValidationIssue(
                        code="semantic_interpreter_output_wrong_type",
                        path=("provider_output",),
                        detail="semantic interpreter returned a non-proposal output",
                    ),
                ),
            )
    except OpenAISemanticIntentRepresentationError as error:
        # A structured response was produced but could not cross the
        # provider-wire boundary.  This is semantic representation work, not
        # an operational outage, and receives the one bounded repair call.
        repair_wire = getattr(interpreter, "repair_wire", None)
        initial_partial = error.partial or proposal
        if not callable(repair_wire):
            # Provider-independent interpreters may expose the original
            # internal repair contract but no provider-specific wire method.
            repair = getattr(interpreter, "repair", None)
            if not callable(repair):
                return _degraded(request, initial_partial, holiday_provider)
            try:
                repair_consumed = True
                proposal = repair(input, proposal=initial_partial, errors=error.errors)
                if not isinstance(proposal, SemanticIntentProposal):
                    raise TypeError("semantic repair returned an unexpected output type")
            except Exception:  # noqa: BLE001 - exhausted generic repair degrades safely
                return _degraded(request, initial_partial, holiday_provider)
        else:
            try:
                repair_consumed = True
                proposal = repair_wire(input, wire=error.wire, errors=error.errors)
                if not isinstance(proposal, SemanticIntentProposal):
                    raise TypeError("semantic wire repair returned an unexpected output type")
            except OpenAISemanticIntentRepresentationError as repair_error:
                return _degraded(request, repair_error.partial or initial_partial, holiday_provider)
            except OpenAISemanticIntentError as operational_error:
                return _pending(request, initial_partial, str(operational_error))
            except Exception:  # noqa: BLE001 - semantic repair exhaustion degrades safely
                return _degraded(request, initial_partial, holiday_provider)
    except Exception as error:  # noqa: BLE001 - adapter/transport failure is operational
        return _pending(request, proposal, f"{type(error).__name__}: {error}")

    try:
        # Scope policy is intentionally staged before all unrelated semantic
        # calculation validation. A stated return must be visible even if a
        # separate outbound plan was malformed.
        scope_modes = _scope_modes(request, proposal)
        scope_parts = _scope_parts(request, proposal, scope_modes)
        if scope_parts:
            sibling_proposal = _scope_safe_outbound_projection(
                _scope_safe_projection(request, proposal)
            )
            try:
                extraction, departure, unresolved, windows = _compile(
                    request, sibling_proposal, holiday_provider
                )
            except IntentCalendarOperationalError:
                return _pending(request, proposal, "holiday provider unavailable")
            except Exception:  # noqa: BLE001 - malformed unrelated calculation cannot hide scope
                extraction, departure, unresolved, windows = (
                    _extraction(request, sibling_proposal),
                    None,
                    (),
                    (),
                )
            extraction = preserve_explicit_airport_codes(request, extraction)
            parsed = _parsed(
                request, sibling_proposal, extraction, departure, unresolved, windows, scope_parts
            )
            return RequestUnderstandingResult(
                parsed_request=parsed, clarification=decide_clarification(parsed)
            )
        _require_operation_recheck(proposal)
        _validate_year_quotes(proposal)
        extraction, departure, unresolved, windows = _compile(request, proposal, holiday_provider)
        extraction = preserve_explicit_airport_codes(request, extraction)
        parsed = _parsed(request, proposal, extraction, departure, unresolved, windows, [])
        return RequestUnderstandingResult(
            parsed_request=parsed, clarification=decide_clarification(parsed)
        )
    except IntentCalendarOperationalError as error:
        return _pending(request, proposal, str(error))
    except Exception as error:  # noqa: BLE001 - grounding/DTO/calendar faults get one semantic repair
        repair = getattr(interpreter, "repair", None)
        if callable(repair) and not repair_consumed:
            try:
                repair_consumed = True
                proposal = repair(input, proposal=proposal, errors=(_issue(error, "proposal"),))
                if not isinstance(proposal, SemanticIntentProposal):
                    raise TypeError("semantic repair returned an unexpected output type")
                scope_modes = _scope_modes(request, proposal)
                scope_parts = _scope_parts(request, proposal, scope_modes)
                if scope_parts:
                    sibling_proposal = _scope_safe_outbound_projection(
                        _scope_safe_projection(request, proposal)
                    )
                    try:
                        extraction, departure, unresolved, windows = _compile(
                            request, sibling_proposal, holiday_provider
                        )
                    except IntentCalendarOperationalError:
                        return _pending(request, proposal, "holiday provider unavailable")
                    except Exception:  # noqa: BLE001 - malformed unrelated calculation cannot hide scope
                        extraction, departure, unresolved, windows = (
                            _extraction(request, sibling_proposal),
                            None,
                            (),
                            (),
                        )
                    extraction = preserve_explicit_airport_codes(request, extraction)
                    parsed = _parsed(
                        request,
                        sibling_proposal,
                        extraction,
                        departure,
                        unresolved,
                        windows,
                        scope_parts,
                    )
                    return RequestUnderstandingResult(
                        parsed_request=parsed, clarification=decide_clarification(parsed)
                    )
                _validate_year_quotes(proposal)
                extraction, departure, unresolved, windows = _compile(
                    request, proposal, holiday_provider
                )
                extraction = preserve_explicit_airport_codes(request, extraction)
                parsed = _parsed(request, proposal, extraction, departure, unresolved, windows, [])
                return RequestUnderstandingResult(
                    parsed_request=parsed, clarification=decide_clarification(parsed)
                )
            except IntentCalendarOperationalError as operational_error:
                return _pending(request, proposal, str(operational_error))
            except OpenAISemanticIntentError as operational_error:
                return _pending(request, proposal, str(operational_error))
            except Exception as repair_error:  # noqa: BLE001 - semantic defects degrade safely
                return _degraded(
                    request,
                    _without_rejected_components(proposal, (_issue(repair_error, "proposal"),)),
                    holiday_provider,
                )
        else:
            return _degraded(
                request,
                _without_rejected_components(proposal, (_issue(error, "proposal"),)),
                holiday_provider,
            )


def _pending(
    request: RawRequest, proposal: SemanticIntentProposal, _detail: str
) -> RequestUnderstandingResult:
    """A typed non-mutating operational/model outcome, never fake user ambiguity."""
    return RequestUnderstandingResult(
        outcome=RequestUnderstandingOutcome.PENDING_RETRYABLE,
        # Do not surface a model quote, provider response, or validation text
        # as customer-facing request state. Diagnostics belong in call traces.
        pending_detail="Interpretation is temporarily unavailable; please try again.",
    )


def _degraded(
    request: RawRequest,
    proposal: SemanticIntentProposal,
    holiday_provider: HolidayDateProvider | None,
) -> RequestUnderstandingResult:
    """Turn exhausted semantic defects into a completed clarification.

    This reducer only keeps independently groundable components.  It never
    reads raw wording for meaning; a rejected calendar component simply leaves
    the deterministic departure blocker in place.  Genuine holiday-provider
    outages stay operational pending.
    """
    safe = _scope_safe_projection(request, proposal)
    valid_temporal: list[SemanticTemporalFact] = []
    for item in safe.temporal_facts:
        try:
            evaluate_departure_calendar_plan((item,), request.context, holiday_provider)
        except IntentCalendarOperationalError:
            return _pending(request, safe, "holiday provider unavailable")
        except Exception:  # noqa: BLE001, S112 - retain independently valid temporal siblings
            continue
        valid_temporal.append(item)
    safe = safe.model_copy(update={"temporal_facts": tuple(valid_temporal)})
    try:
        extraction = _extraction(request, safe)
    except Exception:  # noqa: BLE001 - degradation must remain a completed user outcome
        # Every fact here was independently source-grounded above; retain the
        # valid collection shape rather than exposing a model failure.
        extraction = CoarseIntentExtraction(search_modes=[SearchMode.AWARD])
    extraction = preserve_explicit_airport_codes(request, extraction)
    modes = _scope_modes(request, safe)
    scope_parts = _scope_parts(request, safe, modes)
    try:
        departure, unresolved = evaluate_departure_calendar_plan(
            safe.temporal_facts, request.context, holiday_provider
        )
        windows = departure_windows(safe.temporal_facts, request.context, holiday_provider)
    except IntentCalendarOperationalError:
        return _pending(request, safe, "holiday provider unavailable")
    except Exception:  # noqa: BLE001 - invalid calendar sibling leaves clarification blocker
        departure, unresolved, windows = None, (), ()
    parsed = _parsed(request, safe, extraction, departure, unresolved, windows, scope_parts)
    return RequestUnderstandingResult(parsed_request=parsed, clarification=decide_clarification(parsed))


def _without_rejected_components(
    proposal: SemanticIntentProposal, errors: tuple[SemanticValidationIssue, ...]
) -> SemanticIntentProposal:
    """Drop only typed rejected IDs before a completed clarification fallback."""
    rejected = {
        item.path[-1]
        for item in errors
        if len(item.path) >= 2 and item.path[-2] == "components"
    }
    if not rejected:
        return proposal
    return proposal.model_copy(
        update={
            "facts": tuple(
                item
                for item in proposal.facts
                if (item.component_id or "") not in rejected
            ),
            "temporal_facts": tuple(
                item
                for item in proposal.temporal_facts
                if (item.component_id or item.fact_id) not in rejected
            ),
            "unresolved": tuple(
                item
                for item in proposal.unresolved
                if (item.component_id or "") not in rejected
            ),
            "scope_notices": tuple(
                item
                for item in proposal.scope_notices
                if (item.component_id or "") not in rejected
            ),
        }
    )


def _parsed(
    request: RawRequest,
    proposal: SemanticIntentProposal,
    extraction: CoarseIntentExtraction,
    departure: DateWindow | None,
    unresolved: tuple[SemanticTemporalFact, ...],
    windows: tuple[DateWindow, ...],
    scope_parts: list[UnsupportedRequestPart],
) -> ParsedRequest:
    evidence = [
        _evidence(
            request, item.quote, item.occurrence_index, TemporalEvidenceClaim.DEPARTURE_PERIOD
        )
        for item in proposal.temporal_facts
        if item.target is SemanticTemporalTarget.DEPARTURE
    ]
    receipts = []
    for fact in proposal.temporal_facts:
        if (
            fact.target is not SemanticTemporalTarget.DEPARTURE
            or fact.operation.value == "unresolved"
        ):
            continue
        matching_window = next((item for item in windows if item.raw_text == fact.quote), None)
        matching_evidence = next((item for item in evidence if item.span.text == fact.quote), None)
        if matching_window is not None and matching_evidence is not None:
            receipts.append(
                CalendarOperationReceipt(
                    fact_id=fact.fact_id,
                    operation=fact.operation.value,
                    date_window=matching_window,
                    evidence=matching_evidence,
                )
            )
    return ParsedRequest(
        raw_text=request.text,
        context=request.context,
        travelers=extraction.travelers,
        origins=extraction.origins,
        destinations=extraction.destinations,
        departure_expression=None,
        departure_window=departure,
        cabins=extraction.cabins,
        search_modes=extraction.search_modes,
        date_flexibility=[],
        repositioning_allowed=extraction.repositioning_allowed,
        hard_constraints=extraction.hard_constraints,
        unknowns=_unknowns(extraction, departure, unresolved, None),
        conflicts=_conflicts(windows, evidence),
        unsupported_request_parts=scope_parts,
        temporal_extraction=extraction,
        temporal_evidence=evidence,
        temporal_relations=TemporalRelationGraph(),
        date_resolution=OneWayDateResolutionProposal(
            departure=(
                ProposedDateWindow(
                    start=departure.start,
                    end=departure.end,
                    supporting_text=[departure.raw_text],
                    interpretation="model-authored generic calendar calculation",
                )
                if departure
                else None
            ),
            unresolved=[
                UnresolvedTemporalConstraint(
                    field="departure",
                    raw_text=item.quote,
                    reason=item.reason or "Unresolved departure timing.",
                )
                for item in unresolved
            ],
        ),
        calendar_receipts=receipts,
    )
