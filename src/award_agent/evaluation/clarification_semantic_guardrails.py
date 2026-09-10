"""Deterministic ADR 0014 conformance gate over typed fake model outputs.

This is intentionally not a language-understanding benchmark: evidence text
is opaque and fake receiver outputs supply all semantics.  It protects the
other side of the boundary—validation, compilation, reduction and rendering.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from award_agent.clarification.composer import (
    ClarificationCompositionError,
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
    compose_prompt,
)
from award_agent.clarification.controller import (
    ClarificationCommandError,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
    ClarificationSemanticFact,
    ClarificationUnresolvedFragment,
    interpret_answer,
    validate_answer_interpretation,
)
from award_agent.clarification.issues import derive_clarification_issues
from award_agent.clarification.semantic import (
    SemanticOperation,
    SemanticTarget,
    SemanticTemporalCompileError,
    TemporalAstKind,
    TemporalSemanticAst,
    compile_temporal_ast,
)
from award_agent.domain import (
    BlockingRequirement,
    BlockingRequirementKind,
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    DateWindow,
    DateWindowPrecision,
    EffectiveField,
    LocationKind,
    LocationRef,
    MessageSpan,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingResult,
    UnknownField,
    UnknownReason,
)

GUARDRAIL_EVALUATOR_VERSION = "clarification_semantic_guardrails_v2"
DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES = Path(
    "evals/clarification/semantic_guardrails_v1.yaml"
)

_CONTINUATION_SOURCES = ("controller.py", "interpreter.py", "semantic.py", "reducer.py")
_FORBIDDEN_MODULE_PREFIXES = (
    "award_agent.clarification.temporal",
    "award_agent.clarification.temporal_templates",
    "award_agent.clarification.temporal_approximations",
)
_FORBIDDEN_CALLS = {
    "normalize_temporal_amendment",
    "harvest_temporal_template_projection",
    "harvest_temporal_approximation_projection",
    "recover_ordered_numeric_date_pair",
}
_FORBIDDEN_TEXT_METHODS = {
    "casefold",
    "lower",
    "upper",
    "split",
    "strip",
    "replace",
    "startswith",
    "endswith",
    "find",
    "index",
    "partition",
    "rpartition",
    "match",
    "search",
    "fullmatch",
}
_REQUIRED_FAMILIES = frozenset(
    {
        "schema_span_grounding",
        "authority_and_state",
        "temporal_compilation",
        "accepting_provenance",
        "reduction_and_session",
        "composer_and_privacy",
        "static_boundary",
    }
)


@dataclass(frozen=True)
class ParserBoundaryViolation:
    path: str
    line: int
    detail: str


class ClarificationSemanticGuardrailError(AssertionError):
    """A deterministic ADR 0014 conformance invariant did not hold."""


class _TypedReceiver:
    def __init__(self, result: ClarificationAnswerInterpretation) -> None:
        self.result = result
        self.inputs: list[ClarificationAnswerInterpreterInput] = []

    def interpret(
        self, input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation:
        self.inputs.append(input)
        return self.result


class _TypedComposer:
    def __init__(self, *, error: Exception | None = None, invalid: str | None = None) -> None:
        self.error, self.invalid = error, invalid
        self.inputs: list[ClarificationPromptComposerInput] = []

    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
        self.inputs.append(input)
        if self.error is not None:
            raise self.error
        items = tuple(
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
        if self.invalid == "reversed":
            items = tuple(reversed(items))
        elif self.invalid == "unlinked" and items:
            items = (items[0].model_copy(update={"issue_ids": ("unlinked",)}), *items[1:])
        return ClarificationPromptComposition(question_items=items)


def _span(message_id: str, text: str) -> MessageSpan:
    return MessageSpan(message_id=message_id, start=0, end=len(text), text=text)


def _requirement(
    identifier: str, kind: BlockingRequirementKind, field: EffectiveField | None
) -> BlockingRequirement:
    return BlockingRequirement(requirement_id=identifier, kind=kind, field=field)


def _assert_raises(expected: type[Exception], callable_: Callable[[], object]) -> None:
    try:
        callable_()
    except expected:
        return
    except Exception as exc:
        raise ClarificationSemanticGuardrailError(
            f"expected {expected.__name__}, got {type(exc).__name__}: {exc}"
        ) from exc
    raise ClarificationSemanticGuardrailError(f"expected {expected.__name__} was accepted")


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def find_raw_answer_semantic_parser_violations(
    sources: Mapping[str, str],
) -> tuple[ParserBoundaryViolation, ...]:
    """Structurally reject retired parser seams and phrase-processing hooks."""
    violations: list[ParserBoundaryViolation] = []
    for path, source in sources.items():
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:  # pragma: no cover
            violations.append(
                ParserBoundaryViolation(path, exc.lineno or 0, "source does not parse")
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "re" or module.startswith(_FORBIDDEN_MODULE_PREFIXES):
                    violations.append(
                        ParserBoundaryViolation(
                            path, node.lineno, f"forbidden semantic import: {module}"
                        )
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "re" or alias.name.startswith(_FORBIDDEN_MODULE_PREFIXES):
                        violations.append(
                            ParserBoundaryViolation(
                                path, node.lineno, f"forbidden semantic import: {alias.name}"
                            )
                        )
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                if name in _FORBIDDEN_CALLS:
                    violations.append(
                        ParserBoundaryViolation(
                            path, node.lineno, f"forbidden semantic call: {name}"
                        )
                    )
                elif name in _FORBIDDEN_TEXT_METHODS:
                    violations.append(
                        ParserBoundaryViolation(
                            path, node.lineno, f"forbidden answer-text operation: {name}"
                        )
                    )
    return tuple(violations)


def audit_continuation_raw_answer_boundary(
    source_root: Path = Path("src/award_agent/clarification"),
) -> tuple[ParserBoundaryViolation, ...]:
    return find_raw_answer_semantic_parser_violations(
        {name: (source_root / name).read_text() for name in _CONTINUATION_SOURCES}
    )


def _input(text: str = "opaque-answer") -> ClarificationAnswerInterpreterInput:
    return ClarificationAnswerInterpreterInput(
        message_id="guardrail-answer",
        text=text,
        ordered_requirements=(
            _requirement("departure", BlockingRequirementKind.DEPARTURE, EffectiveField.DEPARTURE),
            _requirement(
                "return_or_duration",
                BlockingRequirementKind.RETURN_OR_DURATION,
                EffectiveField.RETURN_OR_DURATION,
            ),
        ),
        correction_eligible_targets=(SemanticTarget.DEPARTURE_WINDOW,),
    )


def _duration_fact(
    message_id: str,
    text: str,
    *,
    identifier: str = "duration",
    operation: SemanticOperation = SemanticOperation.SET,
    requirement_ids: tuple[str, ...] = ("return_or_duration",),
    approximate: bool = True,
) -> ClarificationSemanticFact:
    return ClarificationSemanticFact(
        fact_id=identifier,
        span=_span(message_id, text),
        operation=operation,
        target=SemanticTarget.DURATION,
        requirement_ids=requirement_ids,
        temporal=TemporalSemanticAst(
            kind=TemporalAstKind.DURATION, quantity=12, unit="day", approximate=approximate
        ),
    )


def _schema_span_grounding() -> None:
    input = _input()
    fact = _duration_fact(input.message_id, input.text)
    assert interpret_answer(
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(fact,))), input
    ) == ClarificationAnswerInterpretation(facts=(fact,))
    _assert_raises(
        ValidationError,
        lambda: ClarificationSemanticFact(
            fact_id="bad-shape",
            span=_span(input.message_id, input.text),
            operation=SemanticOperation.SET,
            target=SemanticTarget.DURATION,
            requirement_ids=("return_or_duration",),
            location_kind=LocationKind.AIRPORT,
            location_value="SFO",
        ),
    )
    for span in (
        MessageSpan(message_id="other", start=0, end=len(input.text), text=input.text),
        MessageSpan(message_id=input.message_id, start=0, end=1, text="x"),
        MessageSpan(
            message_id=input.message_id, start=0, end=len(input.text) + 1, text=input.text + "x"
        ),
    ):
        bad = fact.model_copy(update={"span": span})
        _assert_raises(
            ClarificationInterpretationError,
            lambda bad=bad: validate_answer_interpretation(
                input, ClarificationAnswerInterpretation(facts=(bad,))
            ),
        )
    fragment = ClarificationUnresolvedFragment(
        span=MessageSpan(message_id=input.message_id, start=0, end=1, text="x"), reason="ambiguous"
    )
    _assert_raises(
        ClarificationInterpretationError,
        lambda: validate_answer_interpretation(
            input, ClarificationAnswerInterpretation(unresolved_fragments=(fragment,))
        ),
    )


def _set_replace_authorization() -> None:
    input = _input()
    fact = _duration_fact(input.message_id, input.text)
    validate_answer_interpretation(input, ClarificationAnswerInterpretation(facts=(fact,)))
    _assert_raises(
        ClarificationInterpretationError,
        lambda: validate_answer_interpretation(
            input,
            ClarificationAnswerInterpretation(
                facts=(fact.model_copy(update={"requirement_ids": ()}),)
            ),
        ),
    )
    _assert_raises(
        ClarificationInterpretationError,
        lambda: validate_answer_interpretation(
            input,
            ClarificationAnswerInterpretation(
                facts=(fact.model_copy(update={"requirement_ids": ("departure",)}),)
            ),
        ),
    )
    correction = ClarificationSemanticFact(
        fact_id="dep",
        span=_span(input.message_id, input.text),
        operation=SemanticOperation.REPLACE,
        target=SemanticTarget.DEPARTURE_WINDOW,
        temporal=TemporalSemanticAst(kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"),
    )
    validate_answer_interpretation(input, ClarificationAnswerInterpretation(facts=(correction,)))
    _assert_raises(
        ClarificationInterpretationError,
        lambda: validate_answer_interpretation(
            input,
            ClarificationAnswerInterpretation(
                facts=(
                    fact.model_copy(
                        update={"operation": SemanticOperation.REPLACE, "requirement_ids": ()}
                    ),
                )
            ),
        ),
    )
    _assert_raises(
        ClarificationInterpretationError,
        lambda: validate_answer_interpretation(
            input,
            ClarificationAnswerInterpretation(
                facts=(correction.model_copy(update={"requirement_ids": ("return_or_duration",)}),)
            ),
        ),
    )


def _temporal_calendar_ranges_dependencies() -> None:
    context = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")
    exact = compile_temporal_ast(
        amendment_id="exact",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, month=1, day=3),
        span=_span("exact", "opaque-exact"),
        context=context,
    ).contribution
    assert exact.date_window is not None and exact.date_window.start == date(2027, 1, 3)
    for portion, bounds in {
        "early": (1, 10),
        "mid": (11, 20),
        "late": (21, 31),
        "whole": (1, 31),
    }.items():
        window = compile_temporal_ast(
            amendment_id=portion,
            target=SemanticTarget.DEPARTURE_WINDOW,
            ast=TemporalSemanticAst(kind=TemporalAstKind.MONTH_PORTION, month=10, portion=portion),
            span=_span("calendar", "opaque-calendar"),
            context=context,
        ).contribution.date_window
        assert (
            window is not None
            and (window.start.day, window.end.day) == bounds
            and window.start <= window.end
        )
    leap = compile_temporal_ast(
        amendment_id="leap",
        target=SemanticTarget.RETURN_WINDOW,
        ast=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, year=2028, month=2, day=29),
        span=_span("leap", "opaque-leap"),
        context=context,
    ).contribution
    assert leap.date_window is not None and leap.date_window.start == date(2028, 2, 29)
    cross_year = compile_temporal_ast(
        amendment_id="range",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DATE_RANGE, month=12, day=29, end_month=1, end_day=3
        ),
        span=_span("range", "opaque-range"),
        context=context,
    ).contribution
    assert cross_year.date_window is not None and (
        cross_year.date_window.start,
        cross_year.date_window.end,
    ) == (date(2026, 12, 29), date(2027, 1, 3))
    _assert_raises(
        SemanticTemporalCompileError,
        lambda: compile_temporal_ast(
            amendment_id="wrong",
            target=SemanticTarget.DURATION,
            ast=TemporalSemanticAst(kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"),
            span=_span("wrong", "opaque-wrong"),
            context=context,
        ),
    )
    _assert_raises(
        SemanticTemporalCompileError,
        lambda: compile_temporal_ast(
            amendment_id="bad-date",
            target=SemanticTarget.DEPARTURE_WINDOW,
            ast=TemporalSemanticAst(kind=TemporalAstKind.CALENDAR_DATE, year=2026, month=2, day=29),
            span=_span("bad", "opaque-bad"),
            context=context,
        ),
    )
    duration = compile_temporal_ast(
        amendment_id="week",
        target=SemanticTarget.DURATION,
        ast=TemporalSemanticAst(kind=TemporalAstKind.DURATION, quantity=2, unit="week"),
        span=_span("week", "opaque-week"),
        context=context,
    ).contribution
    assert duration.interpreted_duration is not None and (
        duration.interpreted_duration.minimum_days,
        duration.interpreted_duration.maximum_days,
    ) == (14, 14)
    relative = TemporalSemanticAst(
        kind=TemporalAstKind.RELATIVE_TO_PRIOR_FACT,
        anchor_fact_id="departure",
        relation="after",
        quantity=12,
        unit="day",
    )
    _assert_raises(
        SemanticTemporalCompileError,
        lambda: compile_temporal_ast(
            amendment_id="return",
            target=SemanticTarget.RETURN_WINDOW,
            ast=relative,
            span=_span("return", "opaque-return"),
            context=context,
        ),
    )
    departure = compile_temporal_ast(
        amendment_id="departure",
        target=SemanticTarget.DEPARTURE_WINDOW,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DATE_RANGE, month=10, day=11, end_month=10, end_day=20
        ),
        span=_span("departure", "opaque-departure"),
        context=context,
    )
    returned = compile_temporal_ast(
        amendment_id="return",
        target=SemanticTarget.RETURN_WINDOW,
        ast=relative,
        span=_span("return", "opaque-return"),
        context=context,
        prior_compiled_facts={"departure": departure},
    ).contribution
    assert returned.date_window is not None and (
        returned.date_window.start,
        returned.date_window.end,
    ) == (date(2026, 10, 23), date(2026, 11, 1))


def _fuzzy_assumption_disclosure() -> None:
    context = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")
    fuzzy = compile_temporal_ast(
        amendment_id="fuzzy",
        target=SemanticTarget.DURATION,
        ast=TemporalSemanticAst(
            kind=TemporalAstKind.DURATION, quantity=12, unit="day", approximate=True
        ),
        span=_span("fuzzy", "opaque-fuzzy"),
        context=context,
    ).contribution
    assert fuzzy.interpreted_duration is not None and (
        fuzzy.interpreted_duration.minimum_days,
        fuzzy.interpreted_duration.maximum_days,
    ) == (11, 13)
    assert fuzzy.interpretation_provenance is not None
    assert fuzzy.interpretation_provenance.assumption_disclosure is not None
    assert fuzzy.interpretation_provenance.assumption_disclosure.message.strip()
    exact = compile_temporal_ast(
        amendment_id="not-fuzzy",
        target=SemanticTarget.DURATION,
        ast=TemporalSemanticAst(kind=TemporalAstKind.DURATION, quantity=12, unit="day"),
        span=_span("exact", "opaque-exact"),
        context=context,
    ).contribution
    assert (
        exact.interpretation_provenance is None
        or exact.interpretation_provenance.assumption_disclosure is None
    )


def _initial(*, unknowns: tuple[str, ...] = ("return_or_duration",)) -> RequestUnderstandingResult:
    parsed = ParsedRequest(
        raw_text="frozen-initial-snapshot",
        context=RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles"),
        travelers=1,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.COUNTRY, value="England", raw_text="England")],
        departure_expression=None,
        return_expression=None,
        departure_window=DateWindow(
            start=date(2026, 10, 11),
            end=date(2026, 10, 20),
            precision=DateWindowPrecision.WINDOW,
            raw_text="initial-window",
        ),
        return_window=None,
        duration=None,
        cabins=[],
        search_modes=[],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=["preserve-me"],
        unknowns=[
            UnknownField(field=item, reason=UnknownReason.MISSING, detail="required")
            for item in unknowns
        ],
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK, field="return_or_duration", question="unused"
        ),
    )


def _command(session: Any, message_id: str, text: str) -> ClarificationAnswerCommand:
    prompt = session.current_revision.prompt
    assert prompt is not None
    return ClarificationAnswerCommand(
        session_id=session.session_id,
        expected_revision=session.current_revision.revision,
        prompt_id=prompt.prompt_id,
        message_id=message_id,
        text=text,
    )


def _fact(
    message_id: str,
    text: str,
    *,
    identifier: str,
    target: SemanticTarget,
    operation: SemanticOperation,
    requirement_ids: tuple[str, ...] = (),
    temporal: TemporalSemanticAst,
) -> ClarificationSemanticFact:
    return ClarificationSemanticFact(
        fact_id=identifier,
        span=_span(message_id, text),
        operation=operation,
        target=target,
        requirement_ids=requirement_ids,
        temporal=temporal,
    )


def _conflicts_siblings_atomicity() -> None:
    session = start_clarification(_initial(), session_id="conflict", composer=_TypedComposer())
    text = "opaque-conflict"
    return_fact = _fact(
        "conflict-message",
        text,
        identifier="return-before",
        target=SemanticTarget.RETURN_WINDOW,
        operation=SemanticOperation.SET,
        requirement_ids=("return_or_duration",),
        temporal=TemporalSemanticAst(
            kind=TemporalAstKind.CALENDAR_DATE, year=2026, month=10, day=1
        ),
    )
    conflict = apply_clarification_answer(
        session,
        _command(session, "conflict-message", text),
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(return_fact,))),
        _TypedComposer(),
    )
    assert conflict.revision.status.value == "awaiting_answer"
    assert {item.code for item in conflict.revision.effective_request.conflicts} == {
        "return_before_departure"
    }
    assert (
        conflict.revision.prompt is not None
        and conflict.revision.prompt.requirements[0].requirement_id
        == "conflict:return_before_departure"
    )
    sibling = start_clarification(
        _initial(unknowns=("return_or_duration", "travelers")),
        session_id="siblings",
        composer=_TypedComposer(),
    )
    good_text = "opaque-siblings"
    departure = _fact(
        "siblings-message",
        good_text,
        identifier="dep",
        target=SemanticTarget.DEPARTURE_WINDOW,
        operation=SemanticOperation.REPLACE,
        temporal=TemporalSemanticAst(kind=TemporalAstKind.MONTH_PORTION, month=10, portion="mid"),
    )
    duration = _duration_fact("siblings-message", good_text, identifier="duration")
    applied = apply_clarification_answer(
        sibling,
        _command(sibling, "siblings-message", good_text),
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(departure, duration))),
        _TypedComposer(),
    )
    assert {item.amendment_id for item in applied.revision.outcome.accepted_amendments} == {
        "dep",
        "duration",
    }
    assert applied.revision.effective_request.hard_constraints == ("preserve-me",)
    atomic = start_clarification(_initial(), session_id="atomic", composer=_TypedComposer())
    bad_text = "opaque-atomic"
    good = _duration_fact("atomic-message", bad_text, identifier="good")
    bad = _fact(
        "atomic-message",
        bad_text,
        identifier="bad",
        target=SemanticTarget.RETURN_WINDOW,
        operation=SemanticOperation.SET,
        requirement_ids=("return_or_duration",),
        temporal=TemporalSemanticAst(kind=TemporalAstKind.DURATION, quantity=2, unit="day"),
    )
    retained = apply_clarification_answer(
        atomic,
        _command(atomic, "atomic-message", bad_text),
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(good, bad))),
        _TypedComposer(),
    )
    assert {item.amendment_id for item in retained.revision.outcome.accepted_amendments} == {"good"}
    assert (
        retained.revision.outcome.rejected_fragments[0].reason_code == "receiver.semantic_compile"
    )


def _revisions_concurrency_idempotency_ready_policy() -> None:
    session = start_clarification(_initial(), session_id="replay", composer=_TypedComposer())
    original = session.model_copy(deep=True)
    command = _command(session, "replay-message", "opaque-ready")
    fact = _duration_fact("replay-message", command.text)
    transitioned = apply_clarification_answer(
        session,
        command,
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(fact,))),
        _TypedComposer(),
    )
    assert session == original and transitioned.revision.status.value == "ready"
    replay = apply_clarification_answer(
        transitioned.session,
        command,
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(fact,))),
        _TypedComposer(),
    )
    assert replay.replayed and replay.session == transitioned.session
    _assert_raises(
        ClarificationCommandError,
        lambda: apply_clarification_answer(
            transitioned.session,
            command.model_copy(update={"text": "opaque-changed"}),
            _TypedReceiver(ClarificationAnswerInterpretation()),
            _TypedComposer(),
        ),
    )
    _assert_raises(
        ClarificationCommandError,
        lambda: apply_clarification_answer(
            transitioned.session,
            command.model_copy(update={"message_id": "stale"}),
            _TypedReceiver(ClarificationAnswerInterpretation()),
            _TypedComposer(),
        ),
    )
    no_progress = start_clarification(
        _initial(), session_id="no-progress", composer=_TypedComposer()
    )
    first = apply_clarification_answer(
        no_progress,
        _command(no_progress, "np-1", "opaque-np-1"),
        _TypedReceiver(ClarificationAnswerInterpretation()),
        _TypedComposer(),
    )
    assert first.revision.status.value == "awaiting_answer"
    second = apply_clarification_answer(
        first.session,
        _command(first.session, "np-2", "opaque-np-2"),
        _TypedReceiver(ClarificationAnswerInterpretation()),
        _TypedComposer(),
    )
    assert (
        second.revision.status.value == "stopped"
        and second.revision.stop_reason is not None
        and second.revision.stop_reason.value == "no_progress_limit"
    )


def _composer_coverage_linkage_failure_redaction() -> None:
    requirements = (
        _requirement("departure", BlockingRequirementKind.DEPARTURE, EffectiveField.DEPARTURE),
        _requirement("travelers", BlockingRequirementKind.TRAVELERS, EffectiveField.TRAVELERS),
    )
    input = ClarificationPromptComposerInput(
        requirements=requirements, issues=derive_clarification_issues(requirements)
    )
    assert tuple(
        item.requirement_id for item in compose_prompt(_TypedComposer(), input).question_items
    ) == ("departure", "travelers")
    _assert_raises(
        ClarificationCompositionError,
        lambda: compose_prompt(_TypedComposer(invalid="reversed"), input),
    )
    _assert_raises(
        ClarificationCompositionError,
        lambda: compose_prompt(_TypedComposer(invalid="unlinked"), input),
    )
    projected = json.dumps(input.model_input(), sort_keys=True)
    for forbidden in (
        "effective_request",
        "session_id",
        "message_id",
        "reference_date",
        "timezone",
        "raw_text",
        "field_provenance",
    ):
        assert forbidden not in projected
    session = start_clarification(
        _initial(unknowns=("return_or_duration", "travelers")),
        session_id="composer-failure",
        composer=_TypedComposer(),
    )
    command = _command(session, "composer-message", "opaque-composer")
    fact = _duration_fact("composer-message", command.text)
    pending = apply_clarification_answer(
        session,
        command,
        _TypedReceiver(ClarificationAnswerInterpretation(facts=(fact,))),
        _TypedComposer(error=RuntimeError("opaque outage")),
    )
    from award_agent.clarification.controller import (
        ClarificationCompositionPending,
        retry_prompt_composition,
    )

    assert isinstance(pending, ClarificationCompositionPending)
    assert (
        len(session.revisions) == 1 and session.current_revision.status.value == "awaiting_answer"
    )
    completed = retry_prompt_composition(session, pending.pending, _TypedComposer())
    assert completed.revision.status.value == "awaiting_answer"


_CHECKS: dict[str, Callable[[], None]] = {
    "schema_and_span_grounding": _schema_span_grounding,
    "set_replace_authorization": _set_replace_authorization,
    "temporal_calendar_ranges_and_dependencies": _temporal_calendar_ranges_dependencies,
    "fuzzy_assumption_disclosure": _fuzzy_assumption_disclosure,
    "conflict_preservation_sibling_atomicity": _conflicts_siblings_atomicity,
    "immutable_revisions_concurrency_idempotency_ready_policy": _revisions_concurrency_idempotency_ready_policy,
    "composer_coverage_linkage_failure_and_redaction": _composer_coverage_linkage_failure_redaction,
}


def preflight_clarification_semantic_guardrail_cases(
    fixture_path: Path = DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES,
) -> tuple[Mapping[str, Any], ...]:
    try:
        payload = yaml.safe_load(fixture_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationSemanticGuardrailError(
            "unable to load semantic guardrail fixtures"
        ) from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("contract_version") != GUARDRAIL_EVALUATOR_VERSION
    ):
        raise ClarificationSemanticGuardrailError(
            "semantic guardrail fixture contract version is invalid"
        )
    if payload.get("corpus") != "disclosed_development":
        raise ClarificationSemanticGuardrailError(
            "semantic guardrail fixtures must be disclosed development data"
        )
    holdout = payload.get("owner_held_holdout")
    if (
        not isinstance(holdout, Mapping)
        or holdout.get("status") != "inaccessible_to_implementation"
    ):
        raise ClarificationSemanticGuardrailError(
            "fixture must explicitly declare the inaccessible owner-held holdout"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ClarificationSemanticGuardrailError("semantic guardrail fixtures need a cases list")
    ids: set[str] = set()
    families: set[str] = set()
    checks: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            raise ClarificationSemanticGuardrailError("semantic guardrail case must be a mapping")
        identifier, family, check, evidence, expected = (
            case.get("id"),
            case.get("family"),
            case.get("check"),
            case.get("evidence"),
            case.get("expected"),
        )
        if not all(
            isinstance(value, str) and value
            for value in (identifier, family, check, evidence, expected)
        ):
            raise ClarificationSemanticGuardrailError(
                "semantic guardrail case fields must be non-empty strings"
            )
        if not evidence.startswith("opaque-"):
            raise ClarificationSemanticGuardrailError(
                "semantic guardrail evidence must remain opaque"
            )
        if identifier in ids:
            raise ClarificationSemanticGuardrailError("semantic guardrail case IDs must be unique")
        ids.add(identifier)
        families.add(family)
        checks.add(check)
    if families != _REQUIRED_FAMILIES:
        raise ClarificationSemanticGuardrailError(
            "semantic guardrail cases miss or add required safety families"
        )
    expected_checks = {"static_no_raw_answer_parser", *_CHECKS}
    if checks != expected_checks:
        raise ClarificationSemanticGuardrailError(
            "semantic guardrail cases must exactly index every hard check"
        )
    return tuple(cases)


def run_offline_clarification_semantic_guardrails(
    source_root: Path = Path("src/award_agent/clarification"),
    fixture_path: Path = DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES,
) -> dict[str, Any]:
    cases = preflight_clarification_semantic_guardrail_cases(fixture_path)
    checks: dict[str, Callable[[], None]] = {
        "static_no_raw_answer_parser": lambda: _assert_no_parser(source_root),
        **_CHECKS,
    }
    records: list[dict[str, str]] = []
    for case in cases:
        identifier = str(case["check"])
        try:
            checks[identifier]()
        except Exception as exc:  # noqa: BLE001
            records.append(
                {
                    "id": identifier,
                    "case_id": str(case["id"]),
                    "status": "failed",
                    "detail": str(exc),
                }
            )
        else:
            records.append(
                {"id": identifier, "case_id": str(case["id"]), "status": "passed", "detail": ""}
            )
    return {
        "schema_version": GUARDRAIL_EVALUATOR_VERSION,
        "fixture": {"corpus": "disclosed_development", "case_count": len(cases), "redacted": True},
        "owner_held_holdout": {
            "status": "not_executed",
            "reason": "inaccessible_to_implementation",
        },
        "passed": all(item["status"] == "passed" for item in records),
        "checks": records,
    }


def _assert_no_parser(source_root: Path) -> None:
    violations = audit_continuation_raw_answer_boundary(source_root)
    if violations:
        raise ClarificationSemanticGuardrailError(
            "; ".join(f"{item.path}:{item.line}: {item.detail}" for item in violations)
        )


__all__ = [
    "DEFAULT_CLARIFICATION_SEMANTIC_GUARDRAIL_FIXTURES",
    "GUARDRAIL_EVALUATOR_VERSION",
    "ClarificationSemanticGuardrailError",
    "ParserBoundaryViolation",
    "audit_continuation_raw_answer_boundary",
    "find_raw_answer_semantic_parser_violations",
    "preflight_clarification_semantic_guardrail_cases",
    "run_offline_clarification_semantic_guardrails",
]
