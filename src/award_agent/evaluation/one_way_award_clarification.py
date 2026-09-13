"""Offline conformance evaluator for the active one-way clarification boundary.

The fixture deliberately drives the public controller with typed receiver output.
It checks that return/duration semantics become grounded scope notices rather than
return state, while ordinary outbound facts can still complete a session.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from award_agent.clarification.calendar_plan import CalendarDay, LiteralIntervalOperation
from award_agent.clarification.composer import (
    ClarificationPromptComposerInput,
    ClarificationPromptComposition,
    ClarificationQuestionItem,
)
from award_agent.clarification.controller import apply_clarification_answer, start_clarification
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationOneWayScopeKind,
    ClarificationOneWayScopeNotice,
    ClarificationSemanticFact,
)
from award_agent.clarification.semantic import SemanticTarget
from award_agent.domain import (
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    LocationKind,
    LocationRef,
    ParsedRequest,
    RequestContext,
    RequestUnderstandingResult,
    SearchMode,
    UnknownField,
    UnknownReason,
)

DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES = Path(
    "evals/clarification/one_way_award_cases_v1.yaml"
)


class OneWayAwardClarificationFixtureError(ValueError):
    """The active deterministic clarification fixture is malformed."""


@dataclass(frozen=True)
class _Case:
    identifier: str
    payload: Mapping[str, Any]


def _span(message_id: str, text: str, quote: str):
    start = text.index(quote)
    from award_agent.domain import MessageSpan

    return MessageSpan(message_id=message_id, start=start, end=start + len(quote), text=quote)


class _FixtureComposer:
    def compose(self, input: ClarificationPromptComposerInput) -> ClarificationPromptComposition:
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


class _FixtureReceiver:
    def __init__(self, case: Mapping[str, Any]) -> None:
        self.case = case

    def interpret(
        self, input: ClarificationAnswerInterpreterInput
    ) -> ClarificationAnswerInterpretation:
        facts: list[ClarificationSemanticFact] = []
        quote = self.case.get("departure_quote")
        if quote is not None:
            assert isinstance(quote, str)
            facts.append(
                ClarificationSemanticFact(
                    fact_id="departure",
                    span=_span(input.message_id, input.text, quote),
                    target=SemanticTarget.DEPARTURE_WINDOW,
                    calendar_operation=LiteralIntervalOperation(
                        start=CalendarDay(year=2026, month=10, day=5)
                    ),
                )
            )
        notices: list[ClarificationOneWayScopeNotice] = []
        scope_quote = self.case.get("scope_quote")
        if scope_quote is not None:
            assert isinstance(scope_quote, str)
            notices.append(
                ClarificationOneWayScopeNotice(
                    kind=ClarificationOneWayScopeKind.RETURN_OR_DURATION,
                    span=_span(input.message_id, input.text, scope_quote),
                )
            )
        return ClarificationAnswerInterpretation(
            facts=tuple(facts), one_way_scope_notices=tuple(notices)
        )


def preflight_one_way_award_clarification_cases(
    fixture_path: Path = DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES,
) -> tuple[_Case, ...]:
    try:
        payload = yaml.safe_load(fixture_path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise OneWayAwardClarificationFixtureError(
            "unable to load one-way clarification fixture"
        ) from exc
    if (
        not isinstance(payload, Mapping)
        or payload.get("contract_version") != "one_way_award_clarification_v1"
    ):
        raise OneWayAwardClarificationFixtureError(
            "fixture must use one_way_award_clarification_v1"
        )
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 2:
        raise OneWayAwardClarificationFixtureError("fixture requires at least two scenarios")
    prepared: list[_Case] = []
    identifiers: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise OneWayAwardClarificationFixtureError("scenario must be a mapping")
        identifier = scenario.get("id")
        expected = scenario.get("expected")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise OneWayAwardClarificationFixtureError(
                "scenario IDs must be unique non-empty strings"
            )
        if not isinstance(scenario.get("initial_unknowns"), list) or not isinstance(
            scenario.get("answer"), str
        ):
            raise OneWayAwardClarificationFixtureError("scenario needs initial_unknowns and answer")
        if not isinstance(expected, Mapping) or set(expected) != {
            "status",
            "blockers",
            "departure",
            "scope_notice",
            "prompt_scope_notice",
        }:
            raise OneWayAwardClarificationFixtureError(
                "scenario expected outcome has an invalid shape"
            )
        if expected["status"] not in {"ready", "awaiting_answer", "stopped"} or not isinstance(
            expected["blockers"], list
        ):
            raise OneWayAwardClarificationFixtureError(
                "scenario expected status or blockers is invalid"
            )
        if not all(
            isinstance(expected[key], bool) for key in ("scope_notice", "prompt_scope_notice")
        ):
            raise OneWayAwardClarificationFixtureError("scope notice oracles must be boolean")
        identifiers.add(identifier)
        prepared.append(_Case(identifier=identifier, payload=scenario))
    return tuple(prepared)


def _initial(unknowns: list[str]) -> RequestUnderstandingResult:
    context = RequestContext(reference_date=date(2026, 9, 10), timezone="America/Los_Angeles")
    parsed = ParsedRequest(
        raw_text="Synthetic one-way clarification fixture.",
        context=context,
        travelers=1,
        origins=[LocationRef(kind=LocationKind.AIRPORT, value="SFO", raw_text="SFO")],
        destinations=[LocationRef(kind=LocationKind.AIRPORT, value="BKK", raw_text="BKK")],
        departure_expression=None,
        departure_window=None,
        cabins=[],
        search_modes=[SearchMode.AWARD],
        date_flexibility=[],
        repositioning_allowed=None,
        hard_constraints=[],
        unknowns=[
            UnknownField(field=field, reason=UnknownReason.MISSING, detail="fixture")
            for field in unknowns
        ],
        conflicts=[],
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(
            action=ClarificationAction.ASK, field="departure", question="fixture"
        ),
    )


def _blockers(session: Any) -> list[str]:
    prompt = session.current_revision.prompt
    return [] if prompt is None else [item.requirement_id for item in prompt.requirements]


def run_offline_one_way_award_clarification_eval(
    fixture_path: Path = DEFAULT_ONE_WAY_AWARD_CLARIFICATION_FIXTURES,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for case in preflight_one_way_award_clarification_cases(fixture_path):
        session = start_clarification(
            _initial(list(case.payload["initial_unknowns"])),
            session_id=f"one-way-{case.identifier}",
            composer=_FixtureComposer(),
        )
        current = session.current_revision
        assert current.prompt is not None
        transition = apply_clarification_answer(
            session,
            ClarificationAnswerCommand(
                session_id=session.session_id,
                expected_revision=current.revision,
                prompt_id=current.prompt.prompt_id,
                message_id=f"{case.identifier}-answer",
                text=str(case.payload["answer"]),
            ),
            _FixtureReceiver(case.payload),
            composer=_FixtureComposer(),
        )
        expected = case.payload["expected"]
        revision = transition.revision
        outcome = revision.outcome
        prompt = revision.prompt
        departure = transition.session.effective_request.departure_window
        checks = {
            "status": revision.status.value == expected["status"],
            "blockers": _blockers(transition.session) == expected["blockers"],
            "departure": (None if departure is None else departure.start.isoformat())
            == expected["departure"],
            "scope_notice": bool(outcome and outcome.scope_notices) is expected["scope_notice"],
            "prompt_scope_notice": bool(prompt and prompt.scope_notices)
            is expected["prompt_scope_notice"],
            "no_return_state": not hasattr(transition.session.effective_request, "return_window")
            and not hasattr(transition.session.effective_request, "interpreted_duration"),
        }
        records.append({"id": case.identifier, "checks": checks, "passed": all(checks.values())})
    return {
        "schema_version": "one_way_award_clarification_eval_v1",
        "fixture": str(fixture_path),
        "records": records,
        "passed": all(item["passed"] for item in records),
    }
