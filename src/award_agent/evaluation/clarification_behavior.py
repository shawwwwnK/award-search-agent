"""Property-based offline behavioral evaluation for accepting clarification.

Unlike the frozen v1 conformance corpus, v2 records acceptable actions and
semantic properties. It drives the public controller through a scripted
single-call receiver seam while keeping safety invariants exact.
"""

from __future__ import annotations

import json
import re
from calendar import monthrange
from collections import Counter, defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from award_agent.clarification.blockers import collect_blocking_requirements
from award_agent.clarification.controller import apply_clarification_answer, start_clarification
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
)
from award_agent.clarification.temporal_approximations import (
    ClarificationTemporalApproximationBinding,
    ClarificationTemporalApproximationSelection,
    ClarificationTemporalApproximationUnresolved,
)
from award_agent.clarification.temporal_templates import (
    ClarificationTemporalTemplateSelection,
    ClarificationTemporalTemplateUnresolved,
)
from award_agent.domain import (
    AmendmentTarget,
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
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
    RequestContext,
    RequestUnderstandingResult,
    TravelersAmendment,
    TypedAmendment,
    UnknownField,
    UnknownReason,
)

DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES = Path("evals/clarification/cases_v2.yaml")
EVALUATOR_VERSION = "clarification_behavior_eval_v2.1"
SCRIPTED_ADAPTER_VERSION = "clarification_behavior_scripted_adapter_v1"
_CLASSES = {
    "reasonably_resolvable", "safely_assumable", "ambiguous", "conflict", "nonanswer", "correction"
}
_FIELDS = {"origin", "destination", "travelers", "departure", "return_or_duration"}
_STATUSES = {"ready", "awaiting_answer", "stopped"}
_SEMANTIC_ACTIONS = {
    "ready", "awaiting_answer", "stopped", "accept_with_visible_assumption",
    "correction_applied", "targeted_follow_up",
}
_PROPERTY_KEYS = {"departure_window", "duration_days"}
_FORBIDDEN = {"generic_repeat"}


class ClarificationBehaviorFixtureError(ValueError):
    """A behavioral v2 fixture cannot safely be executed."""


def _privacy_violations(value: object, *, path: str = "fixture") -> list[str]:
    violations: list[str] = []
    forbidden_keys = {"raw_model_payload", "credentials", "api_key", "authorization"}
    forbidden_text = ("@", "bearer ", "sk-", "http://", "https://")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in forbidden_keys:
                violations.append(f"{path}.{key}")
            violations.extend(_privacy_violations(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            violations.extend(_privacy_violations(item, path=f"{path}[{index}]"))
    elif isinstance(value, str) and any(token in value.casefold() for token in forbidden_text):
        violations.append(path)
    return violations


def _initial(case: Mapping[str, Any]) -> RequestUnderstandingResult:
    """Build v2's synthetic snapshot without coupling to the v1 evaluator."""

    unknowns = [
        UnknownField(field=_string(field, "initial_unknowns item"), reason=UnknownReason.MISSING, detail="fixture unknown")
        for field in case["initial_unknowns"]
    ]
    context = RequestContext(
        reference_date=date.fromisoformat(str(case.get("reference_date", "2026-09-10"))),
        timezone="America/Los_Angeles",
    )
    departure_value = case.get("initial_departure")
    duration_days = case.get("initial_duration_days")
    departure = (
        DateWindow(start=date.fromisoformat(str(departure_value)), end=date.fromisoformat(str(departure_value)), precision=DateWindowPrecision.EXACT, raw_text="fixture date")
        if departure_value else None
    )
    duration = (
        InterpretedDuration(raw_text="fixture duration", minimum_days=int(duration_days), maximum_days=int(duration_days))
        if duration_days else None
    )
    origin, destination = case.get("initial_origin"), case.get("initial_destination")
    parsed = ParsedRequest(
        raw_text="Synthetic behavioral clarification fixture.", context=context, travelers=case.get("initial_travelers"),
        origins=[LocationRef(kind=LocationKind.AIRPORT, value=str(origin), raw_text=str(origin))] if origin else [],
        destinations=[LocationRef(kind=LocationKind.COUNTRY, value=str(destination), raw_text=str(destination))] if destination else [],
        departure_expression=None, return_expression=None, departure_window=departure, return_window=None,
        duration=None, cabins=[], search_modes=[], date_flexibility=[], repositioning_allowed=None,
        hard_constraints=[], unknowns=unknowns,
        conflicts=[Conflict(code=str(code), fields=["dates"], detail="fixture conflict") for code in case.get("initial_conflicts", [])],
        date_resolution=DateResolutionProposal(interpreted_duration=duration) if duration else DateResolutionProposal(),
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(action=ClarificationAction.ASK, field="origin", question="fixture"),
    )


@dataclass(frozen=True)
class PreparedClarificationBehaviorCase:
    identifier: str
    payload: Mapping[str, Any]


def _load(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationBehaviorFixtureError(f"unable to load behavioral fixture {path}") from exc
    if not isinstance(payload, Mapping):
        raise ClarificationBehaviorFixtureError("behavioral fixture root must be a mapping")
    return payload, raw


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ClarificationBehaviorFixtureError(f"{label} must be a non-empty string")
    return value


def preflight_clarification_behavior_cases(
    fixture_path: Path = DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES,
) -> tuple[PreparedClarificationBehaviorCase, ...]:
    payload, _ = _load(fixture_path)
    if payload.get("contract_version") != "v2":
        raise ClarificationBehaviorFixtureError("behavioral fixture contract_version must be v2")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 8:
        raise ClarificationBehaviorFixtureError("behavioral fixture needs at least eight scenarios")
    if _privacy_violations(payload):
        raise ClarificationBehaviorFixtureError("behavioral fixture fails privacy lint")
    seen: set[str] = set()
    classes: set[str] = set()
    pairs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise ClarificationBehaviorFixtureError("behavioral scenario must be a mapping")
        identifier = _string(scenario.get("id"), "scenario.id")
        if identifier in seen:
            raise ClarificationBehaviorFixtureError(f"duplicate behavioral scenario {identifier!r}")
        seen.add(identifier)
        answer_class = _string(scenario.get("answer_class"), "scenario.answer_class")
        if answer_class not in _CLASSES:
            raise ClarificationBehaviorFixtureError("scenario answer_class is unsupported")
        classes.add(answer_class)
        if "force_generic_followup" in scenario and not isinstance(scenario["force_generic_followup"], bool):
            raise ClarificationBehaviorFixtureError("force_generic_followup must be boolean")
        if not isinstance(scenario.get("initial_unknowns"), list) or not all(
            isinstance(value, str) and value in _FIELDS for value in scenario.get("initial_unknowns", ())
        ):
            raise ClarificationBehaviorFixtureError("scenario initial_unknowns must be a list")
        if scenario.get("pair_id") is not None:
            pair_id = _string(scenario["pair_id"], "scenario.pair_id")
            role = _string(scenario.get("pair_role"), "scenario.pair_role")
            if role not in {"accept", "ask"}:
                raise ClarificationBehaviorFixtureError("pair_role must be accept or ask")
            pairs[pair_id].append((role, answer_class))
        turns = scenario.get("turns")
        if not isinstance(turns, list) or len(turns) != 1:
            raise ClarificationBehaviorFixtureError("behavioral v2 scenarios require exactly one turn")
        for turn in turns:
            if not isinstance(turn, Mapping) or not isinstance(turn.get("oracle"), Mapping):
                raise ClarificationBehaviorFixtureError("behavioral turn needs an oracle")
            oracle = turn["oracle"]
            for key in (
                "must_resolve", "must_remain_blocked", "protected_fields", "permitted_statuses",
                "permitted_semantic_actions", "forbidden",
            ):
                if not isinstance(oracle.get(key), list):
                    raise ClarificationBehaviorFixtureError(f"behavioral oracle needs {key}")
            if not all(isinstance(value, str) and value in _FIELDS | {"conflict:return_before_departure"} for key in ("must_resolve", "must_remain_blocked", "protected_fields") for value in oracle[key]):
                raise ClarificationBehaviorFixtureError("behavioral oracle has an unsupported field link")
            if not all(isinstance(value, str) and value in _STATUSES for value in oracle["permitted_statuses"]):
                raise ClarificationBehaviorFixtureError("behavioral oracle has an unsupported status")
            if not all(isinstance(value, str) and value in _SEMANTIC_ACTIONS for value in oracle["permitted_semantic_actions"]):
                raise ClarificationBehaviorFixtureError("behavioral oracle has an unsupported semantic action")
            if not all(isinstance(value, str) and value in _FORBIDDEN for value in oracle["forbidden"]):
                raise ClarificationBehaviorFixtureError("behavioral oracle has an unsupported forbidden outcome")
            if not isinstance(oracle.get("properties"), Mapping) or not isinstance(oracle.get("disclosure_required"), bool) or not isinstance(oracle.get("question_required"), bool):
                raise ClarificationBehaviorFixtureError("behavioral oracle properties/disclosure_required are invalid")
            if set(oracle["properties"]) - _PROPERTY_KEYS:
                raise ClarificationBehaviorFixtureError("behavioral oracle has an unknown property")
            window = oracle["properties"].get("departure_window")
            if window is not None and (
                not isinstance(window, Mapping)
                or set(window) != {"year", "month", "start_day", "end_day"}
                or not all(
                    isinstance(window[key], int) and not isinstance(window[key], bool)
                    if key in {"year", "month"}
                    else isinstance(window[key], list) and len(window[key]) == 2
                    and all(isinstance(day, int) and not isinstance(day, bool) for day in window[key])
                    for key in window
                )
            ):
                raise ClarificationBehaviorFixtureError("departure_window property must use bounded envelope fields")
            if window is not None and (
                not 1 <= window["month"] <= 12
                or not 1 <= window["start_day"][0] <= window["start_day"][1] <= 31
                or not 1 <= window["end_day"][0] <= window["end_day"][1] <= 31
                or window["start_day"][0] > window["end_day"][1]
                or window["end_day"][1] > monthrange(window["year"], window["month"])[1]
            ):
                raise ClarificationBehaviorFixtureError("departure_window envelope is invalid")
            duration = oracle["properties"].get("duration_days")
            if duration is not None and (not isinstance(duration, list) or len(duration) != 2 or not all(isinstance(value, int) for value in duration)):
                raise ClarificationBehaviorFixtureError("duration_days property must be a two-integer envelope")
            if duration is not None and (duration[0] < 1 or duration[0] > duration[1]):
                raise ClarificationBehaviorFixtureError("duration_days envelope is invalid")
            if "valid_siblings" in oracle and (
                not isinstance(oracle["valid_siblings"], list)
                or not all(isinstance(value, str) and value in _FIELDS for value in oracle["valid_siblings"])
                or not set(oracle["valid_siblings"]).issubset(oracle["must_resolve"])
            ):
                raise ClarificationBehaviorFixtureError("valid_siblings must be supported must_resolve fields")
            for script_key in ("amendments", "approximations", "approximations_unresolved"):
                if script_key in turn and not isinstance(turn[script_key], list):
                    raise ClarificationBehaviorFixtureError(f"{script_key} must be a list")
            for amendment in turn.get("amendments", ()):
                if not isinstance(amendment, Mapping):
                    raise ClarificationBehaviorFixtureError("amendment script must be a mapping")
                target = _string(amendment.get("target"), "amendment.target")
                if target not in {"origin", "destination", "travelers"}:
                    raise ClarificationBehaviorFixtureError("v2 direct amendment target is unsupported")
                _string(amendment.get("fragment"), "amendment.fragment")
                if not isinstance(amendment.get("requirements"), list):
                    raise ClarificationBehaviorFixtureError("amendment requirements must be a list")
                if target in {"origin", "destination"}:
                    _string(amendment.get("value"), "amendment.value")
                elif not isinstance(amendment.get("travelers"), int):
                    raise ClarificationBehaviorFixtureError("traveler amendment needs an integer")
            for approximation in turn.get("approximations", ()):
                if not isinstance(approximation, Mapping):
                    raise ClarificationBehaviorFixtureError("approximation script must be a mapping")
                if _string(approximation.get("handle"), "approximation.handle") not in {"a1", "a2", "a3", "a4", "a5"}:
                    raise ClarificationBehaviorFixtureError("approximation handle is unsupported")
                _string(approximation.get("fragment"), "approximation.fragment")
                if approximation.get("handle") in {"a1", "a2", "a3"}:
                    if approximation.get("month_reference") not in {"named_month", "next_month"}:
                        raise ClarificationBehaviorFixtureError("month approximation needs a closed month_reference slot")
                    if approximation.get("month_reference") == "named_month":
                        _string(approximation.get("month_name"), "approximation.month_name")
                elif approximation.get("month_reference") is not None or approximation.get("month_name") is not None:
                    raise ClarificationBehaviorFixtureError("week approximation cannot include month slots")
            for unresolved in turn.get("approximations_unresolved", ()):
                if isinstance(unresolved, str):
                    continue
                if not isinstance(unresolved, Mapping):
                    raise ClarificationBehaviorFixtureError("unresolved approximation must be a fragment or mapping")
                _string(unresolved.get("fragment"), "unresolved.fragment")
                requirements = unresolved.get("requirements")
                if not isinstance(requirements, list) or not requirements:
                    raise ClarificationBehaviorFixtureError("unresolved approximation needs requirement links")
                if not all(isinstance(item, str) and item in {"departure", "return_or_duration"} for item in requirements):
                    raise ClarificationBehaviorFixtureError("unresolved approximation links unsupported requirement")
    if classes != _CLASSES:
        raise ClarificationBehaviorFixtureError("behavioral fixture must cover every answer class")
    if not pairs or any(
        len(items) != 2
        or {role for role, _ in items} != {"accept", "ask"}
        or any(role == "accept" and answer_class not in {"reasonably_resolvable", "safely_assumable"} for role, answer_class in items)
        or any(role == "ask" and answer_class not in {"ambiguous", "conflict"} for role, answer_class in items)
        for items in pairs.values()
    ):
        raise ClarificationBehaviorFixtureError("each pair_id must contain exactly one compatible accept and ask scenario")
    return tuple(PreparedClarificationBehaviorCase(str(item["id"]), item) for item in scenarios)


def _span(message_id: str, text: str, fragment: str) -> MessageSpan:
    start = text.casefold().find(fragment.casefold())
    if start < 0:
        raise ClarificationBehaviorFixtureError(f"script fragment {fragment!r} is not grounded in answer")
    return MessageSpan(message_id=message_id, start=start, end=start + len(fragment), text=text[start:start + len(fragment)])


class _ScriptedInterpreter:
    def __init__(self, turn: Mapping[str, Any], *, force_generic_followup: bool = False) -> None:
        self.turn = turn
        self.force_generic_followup = force_generic_followup

    def interpret(self, input: ClarificationAnswerInterpreterInput) -> ClarificationAnswerInterpretation:
        amendments: list[TypedAmendment] = []
        for ordinal, item in enumerate(self.turn.get("amendments", ()), start=1):
            if not isinstance(item, Mapping):
                raise ClarificationBehaviorFixtureError("amendment script must be a mapping")
            target = AmendmentTarget(_string(item.get("target"), "amendment.target"))
            span = _span(input.message_id, input.text, _string(item.get("fragment"), "amendment.fragment"))
            requirement_ids = tuple(item.get("requirements", ()))
            if target in {AmendmentTarget.ORIGIN, AmendmentTarget.DESTINATION}:
                value = _string(item.get("value"), "amendment.value")
                amendments.append(LocationAmendment(
                    amendment_id=f"{input.message_id}:a{ordinal}", target=target, requirement_ids=requirement_ids,
                    span=span, locations=(LocationRef(kind=LocationKind.AIRPORT, value=value, raw_text=value),),
                ))
            elif target is AmendmentTarget.TRAVELERS:
                amendments.append(TravelersAmendment(
                    amendment_id=f"{input.message_id}:a{ordinal}", target=target, requirement_ids=requirement_ids,
                    span=span, travelers=int(item["travelers"]),
                ))
            else:
                raise ClarificationBehaviorFixtureError("v2 scripts support only location/traveler direct amendments")
        selected = []
        for item in self.turn.get("approximations", ()):
            if not isinstance(item, Mapping):
                raise ClarificationBehaviorFixtureError("approximation script must be a mapping")
            selected.append(ClarificationTemporalApproximationBinding(
                approximation_handle=_string(item.get("handle"), "approximation.handle"),
                span=_span(input.message_id, input.text, _string(item.get("fragment"), "approximation.fragment")),
                month_reference=item.get("month_reference"), month_name=item.get("month_name"),
                is_correction=bool(item.get("correction", False)),
            ))
        unresolved_items: list[ClarificationTemporalApproximationUnresolved] = []
        for raw in self.turn.get("approximations_unresolved", ()):
            if isinstance(raw, str):
                fragment, requirement_ids = raw, tuple(
                    requirement.requirement_id for requirement in input.requirements
                    if requirement.requirement_id in {"departure", "return_or_duration"}
                )
            elif isinstance(raw, Mapping):
                fragment = _string(raw.get("fragment"), "unresolved.fragment")
                requirement_ids = tuple(raw["requirements"])
            else:
                raise ClarificationBehaviorFixtureError("unresolved approximation must be a fragment or mapping")
            unresolved_items.append(ClarificationTemporalApproximationUnresolved(
                span=_span(input.message_id, input.text, fragment),
                requirement_ids=requirement_ids,
                reason="ambiguous",
            ))
        # v1 still requires complete classification of the overlapping
        # ``next month`` cue. The accepting registry reconciliation owns it.
        old_unresolved = tuple(ClarificationTemporalTemplateUnresolved(
            span=_span(input.message_id, input.text, match.group(0)),
            requirement_ids=tuple(requirement.requirement_id for requirement in input.requirements if requirement.requirement_id in {"departure", "return_or_duration"}),
            reason="unsupported",
        ) for match in re.finditer(r"\bnext\s+month\b", input.text, re.IGNORECASE))
        oracle = self.turn["oracle"]
        assert isinstance(oracle, Mapping)
        remaining = set(oracle["must_remain_blocked"])
        next_requirement_ids = tuple(
            requirement.requirement_id
            for requirement in input.requirements
            if requirement.requirement_id in remaining
        )
        unresolved_fragments = [
            _string(item.get("fragment"), "unresolved.fragment")
            for item in self.turn.get("approximations_unresolved", ())
            if isinstance(item, Mapping)
        ]
        phrase = unresolved_fragments[0] if unresolved_fragments else input.text
        next_question_items = tuple(
            f"What should I use for {requirement_id.replace('_', ' ')}?"
            if self.force_generic_followup
            else f'When you said “{phrase},” what should I use for {requirement_id.replace("_", " ")}?'
            for requirement_id in next_requirement_ids
        )
        return ClarificationAnswerInterpretation(  # type: ignore[call-arg]  # Historical v2 adapter.
            amendments=tuple(amendments),
            next_question_requirement_ids=next_requirement_ids,
            next_question_items=next_question_items,
            temporal_template_selection=ClarificationTemporalTemplateSelection(unresolved=old_unresolved, complete=True),
            temporal_approximation_selection=ClarificationTemporalApproximationSelection(
                selected=tuple(selected), unresolved=tuple(unresolved_items), complete=True
            ),
        )


def _prompt_blockers(session: Any) -> list[str]:
    prompt = session.current_revision.prompt
    return [] if prompt is None else [item.requirement_id for item in prompt.requirements]


def _authoritative_blockers(session: Any) -> list[str]:
    """Read blockers from reduced state, never from composed prompt text."""

    return [item.requirement_id for item in collect_blocking_requirements(session.effective_request)]


def _fields(session: Any) -> dict[str, Any]:
    effective = session.effective_request
    return {
        "origin": effective.origins[0].value if effective.origins else None,
        "destination": effective.destinations[0].value if effective.destinations else None,
        "travelers": effective.travelers,
        "departure": None if effective.departure_window is None else [effective.departure_window.start.isoformat(), effective.departure_window.end.isoformat()],
        "return_or_duration": None if effective.interpreted_duration is None else [effective.interpreted_duration.minimum_days, effective.interpreted_duration.maximum_days],
    }


def _property_failures(session: Any, properties: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    effective = session.effective_request
    window_property = properties.get("departure_window")
    if window_property is not None:
        assert isinstance(window_property, Mapping)
        window = effective.departure_window
        if window is None:
            failures.append("departure portion was not resolved")
        elif (
            window.start.year != window_property["year"]
            or window.start.month != window_property["month"]
            or not window_property["start_day"][0] <= window.start.day <= window_property["start_day"][1]
            or not window_property["end_day"][0] <= window.end.day <= window_property["end_day"][1]
            or window.end < window.start
        ):
            failures.append("departure window is outside the acceptable bounded envelope")
    duration = properties.get("duration_days")
    if duration is not None and (
        not isinstance(duration, list)
        or effective.interpreted_duration is None
        or not (
            duration[0] <= effective.interpreted_duration.minimum_days
            <= effective.interpreted_duration.maximum_days <= duration[1]
        )
    ):
        failures.append("duration property was not satisfied")
    return failures


def run_clarification_behavior_eval(
    fixture_path: Path = DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES,
) -> dict[str, Any]:
    """Execute v2 property oracles and report safety separately from helpfulness."""

    cases = preflight_clarification_behavior_cases(fixture_path)
    _, raw = _load(fixture_path)
    records: list[dict[str, Any]] = []
    equivalence: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for case in cases:
        session = start_clarification(_initial(case.payload), session_id=f"behavior-{case.identifier}")
        initial_snapshot = deepcopy(session.initial_result.model_dump(mode="json"))
        for turn_index, turn in enumerate(case.payload["turns"], start=1):
            assert isinstance(turn, Mapping)
            oracle = turn["oracle"]
            assert isinstance(oracle, Mapping)
            before = _fields(session)
            before_blockers = _authoritative_blockers(session)
            prompt = session.current_revision.prompt
            assert prompt is not None
            command = ClarificationAnswerCommand(
                session_id=session.session_id, expected_revision=session.current_revision.revision,
                prompt_id=prompt.prompt_id, message_id=f"{case.identifier}:answer:{turn_index}", text=_string(turn.get("text"), "turn.text"),
            )
            error: str | None = None
            try:
                transition = apply_clarification_answer(
                    session,
                    command,
                    _ScriptedInterpreter(
                        turn,
                        force_generic_followup=bool(case.payload.get("force_generic_followup", False)),
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - evaluator reports boundary errors as safety failures.
                error = type(exc).__name__
            else:
                session = transition.session
            after = _fields(session)
            blockers = _authoritative_blockers(session)
            prompt_blockers = _prompt_blockers(session)
            resolved = [item for item in oracle["must_resolve"] if item in before_blockers and item not in blockers]
            protected_failures = [field for field in oracle["protected_fields"] if before.get(field) != after.get(field)]
            safety_failures = []
            if error is not None:
                safety_failures.append(f"system error: {error}")
            if session.initial_result.model_dump(mode="json") != initial_snapshot:
                safety_failures.append("initial snapshot mutated")
            if protected_failures:
                safety_failures.append(f"protected fields changed: {protected_failures!r}")
            if any(requirement not in blockers for requirement in oracle["must_remain_blocked"]):
                safety_failures.append("required blocker was silently cleared")
            # Composition is untrusted presentation: only its ordered links
            # are checked against the state-derived blocker collector.
            if session.status.value == "awaiting_answer":
                if prompt_blockers != blockers:
                    safety_failures.append("prompt requirement coverage failed")
            elif session.status.value == "ready" and blockers:
                safety_failures.append("ready state retains authoritative blockers")
            if any(
                contribution.date_window is not None
                and contribution.date_window.end < contribution.date_window.start
                for contribution in session.effective_request.temporal_contributions
            ):
                safety_failures.append("unbounded or invalid temporal contribution")
            disclosure_present = any(
                item.interpretation_provenance is not None
                and item.interpretation_provenance.assumption_disclosure is not None
                for item in session.effective_request.temporal_contributions
            )
            if oracle["disclosure_required"] and not disclosure_present:
                safety_failures.append("accepted approximation has no visible disclosure")
            behavioral_failures = []
            property_failures = _property_failures(session, oracle["properties"])
            behavioral_failures.extend(property_failures)
            all_must_resolve = not (set(oracle["must_resolve"]) - set(resolved))
            remaining_required = set(oracle["must_remain_blocked"]).issubset(blockers)
            prompt_message = session.current_revision.prompt.message if session.current_revision.prompt else ""
            issues = session.current_revision.prompt.issues if session.current_revision.prompt else ()
            question_required = bool(oracle["question_required"])
            targeted_question = bool(issues) and all(
                issue.span is None or issue.span.text in prompt_message for issue in issues
            )
            # This is an observable semantic outcome, deliberately distinct
            # from the controller's mechanical session status.
            semantic_action = session.status.value
            if question_required and targeted_question:
                semantic_action = "targeted_follow_up"
            elif case.payload["answer_class"] == "correction" and after.get("departure") != before.get("departure"):
                semantic_action = "correction_applied"
            elif disclosure_present and all_must_resolve and not blockers:
                semantic_action = "accept_with_visible_assumption"
            status_permitted = session.status.value in oracle["permitted_statuses"]
            semantic_action_permitted = semantic_action in oracle["permitted_semantic_actions"]
            if not status_permitted:
                behavioral_failures.append(f"status {session.status.value!r} is not permitted")
            if not semantic_action_permitted:
                behavioral_failures.append(f"action {semantic_action!r} is not permitted")
            if case.payload["answer_class"] in {"reasonably_resolvable", "safely_assumable"} and not all_must_resolve:
                behavioral_failures.append("false blocking")
            if question_required and not targeted_question:
                behavioral_failures.append("targeted question missing")
            if (
                "generic_repeat" in oracle["forbidden"]
                and issues
                and any(issue.span is not None for issue in issues)
                and not targeted_question
            ):
                behavioral_failures.append("generic repeat")
            if case.payload["answer_class"] in {"ambiguous", "conflict"} and not remaining_required:
                behavioral_failures.append("incorrect acceptance")
            unnecessary = (
                case.payload["answer_class"] in {"reasonably_resolvable", "safely_assumable"}
                and not oracle["must_remain_blocked"]
                and all_must_resolve
                and not property_failures
                and status_permitted and semantic_action_permitted
                and session.status.value == "awaiting_answer"
            )
            requested_siblings = list(oracle.get("valid_siblings", ()))
            sibling_retained = [field for field in requested_siblings if field not in blockers and after.get(field) is not None]
            if len(sibling_retained) != len(requested_siblings):
                behavioral_failures.append("valid sibling lost")
            records.append({
                "scenario": case.identifier, "turn": turn_index, "answer_class": case.payload["answer_class"],
                "semantic_family": case.payload["answer_class"],
                "safety_failures": safety_failures, "behavioral_failures": behavioral_failures,
                "status": session.status.value, "observed_status": session.status.value,
                "before_blockers": before_blockers, "blockers": blockers, "prompt_blockers": prompt_blockers,
                "resolved": resolved, "semantic_action": semantic_action, "turns_to_ready": turn_index if session.status.value == "ready" else None,
                "question_required": question_required, "targeted_question": targeted_question,
                "disclosure_required": bool(oracle["disclosure_required"]), "disclosure_present": disclosure_present,
                "expected_resolutions": len(oracle["must_resolve"]), "property_failures": property_failures,
                "all_must_resolve": all_must_resolve, "remaining_required": remaining_required,
                "status_permitted": status_permitted, "semantic_action_permitted": semantic_action_permitted,
                "unnecessary_clarification": unnecessary,
                "valid_siblings": requested_siblings, "sibling_retained": sibling_retained,
                "pair_id": case.payload.get("pair_id"), "pair_role": case.payload.get("pair_role"),
                "error": error, "stop_reason": session.current_revision.stop_reason,
            })
        group = case.payload.get("equivalence_group")
        if isinstance(group, str):
            equivalence[group].append((case.identifier, _fields(session)))
    safety_failed = [record for record in records if record["safety_failures"]]
    reasonable = [record for record in records if record["answer_class"] in {"reasonably_resolvable", "safely_assumable"}]
    false_blocks = sum("false blocking" in record["behavioral_failures"] for record in reasonable)
    ambiguous = [record for record in records if record["answer_class"] in {"ambiguous", "conflict"}]
    incorrect = sum("incorrect acceptance" in record["behavioral_failures"] for record in ambiguous)
    def compatible(values: list[tuple[str, Any]]) -> bool:
        rows = [value for _, value in values]
        first = rows[0]
        return all(
            item["origin"] == first["origin"]
            and item["destination"] == first["destination"]
            and item["travelers"] == first["travelers"]
            and item["return_or_duration"] == first["return_or_duration"]
            and item["departure"] is not None
            and first["departure"] is not None
            and max(item["departure"][0], first["departure"][0]) <= min(item["departure"][1], first["departure"][1])
            for item in rows[1:]
        )

    equivalence_failures = {
        group: [identifier for identifier, _ in values]
        for group, values in equivalence.items()
        if not compatible(values)
    }
    pair_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if isinstance(case.payload.get("pair_id"), str):
            pair_records[case.payload["pair_id"]].extend(
                record for record in records if record["scenario"] == case.identifier
            )
    pair_failures = {
        pair_id: [record["scenario"] for record in pair]
        for pair_id, pair in pair_records.items()
        if any(
            (record["pair_role"] == "accept" and (
                not record["all_must_resolve"]
                or record["status"] != "ready"
                or "false blocking" in record["behavioral_failures"]
            ))
            or (record["pair_role"] == "ask" and (
                not record["remaining_required"]
                or not record["targeted_question"]
                or "incorrect acceptance" in record["behavioral_failures"]
            ))
            for record in pair
        )
    }
    holdout = "holdout" in fixture_path.parts
    family_counts = Counter(record["answer_class"] for record in records)
    semantic_family_counts = Counter(record["semantic_family"] for record in records)
    sibling_records = [record for record in records if record["valid_siblings"]]
    slice_metrics = {
        answer_class: {
            "turns": len(items),
            "exact_safety_failures": sum(bool(item["safety_failures"]) for item in items),
            "behavioral_failures": sum(bool(item["behavioral_failures"]) for item in items),
            "false_blocking": sum("false blocking" in item["behavioral_failures"] for item in items),
            "incorrect_acceptance": sum("incorrect acceptance" in item["behavioral_failures"] for item in items),
        }
        for answer_class in sorted(semantic_family_counts)
        for items in [[item for item in records if item["semantic_family"] == answer_class]]
    }
    artifact = {
        "schema_version": "clarification_behavior_eval_v2",
        "fixture": ({"sha256": sha256(raw).hexdigest(), "private_holdout": True, "family_counts": dict(sorted(family_counts.items()))} if holdout else {"path": str(fixture_path), "sha256": sha256(raw).hexdigest(), "redacted": True}),
        **({} if holdout else {"records": records}),
        "summary": {
            "exact_safety_gate": {"passed": not safety_failed, "failed": len(safety_failed), "required_rate": 1.0},
            "behavioral": {
                "false_blocking": {"count": false_blocks, "denominator": len(reasonable), "rate": false_blocks / len(reasonable) if reasonable else 0.0},
                "incorrect_acceptance": {"count": incorrect, "denominator": len(ambiguous), "rate": incorrect / len(ambiguous) if ambiguous else 0.0},
                "unnecessary_clarification": {
                    "count": sum(record["unnecessary_clarification"] for record in reasonable),
                    "denominator": len(reasonable),
                },
                "turns_to_ready": (
                    {"ready_sessions": sum(record["turns_to_ready"] is not None for record in records), "mean": (sum(record["turns_to_ready"] for record in records if record["turns_to_ready"] is not None) / sum(record["turns_to_ready"] is not None for record in records) if any(record["turns_to_ready"] is not None for record in records) else None)}
                    if holdout
                    else {record["scenario"]: record["turns_to_ready"] for record in records if record["turns_to_ready"] is not None}
                ),
                "assumption_disclosure": {"required": sum(record["disclosure_required"] for record in records), "missing": sum(record["disclosure_required"] and not record["disclosure_present"] for record in records)},
                "materially_incorrect_assumption": {"count": sum(record["disclosure_required"] and bool(record["property_failures"]) for record in records), "denominator": sum(record["disclosure_required"] for record in records)},
                "valid_sibling_retention": {
                    "retained": sum(len(record["sibling_retained"]) for record in sibling_records),
                    "expected": sum(len(record["valid_siblings"]) for record in sibling_records),
                    "scenarios": len(sibling_records),
                },
                "targeted_question": {
                    "required": sum(record["question_required"] for record in records),
                    "targeted": sum(record["question_required"] and record["targeted_question"] for record in records),
                    "generic_repeats": sum("generic repeat" in record["behavioral_failures"] for record in records),
                },
                "generic_repeat_rate": sum("generic repeat" in record["behavioral_failures"] for record in records) / sum(record["question_required"] for record in records) if any(record["question_required"] for record in records) else 0.0,
                "paraphrase_consistency": ({"passed": not equivalence_failures, "failure_count": len(equivalence_failures)} if holdout else {"passed": not equivalence_failures, "failures": equivalence_failures}),
                "paired_accept_ask": ({"passed": not pair_failures, "failure_count": len(pair_failures)} if holdout else {"passed": not pair_failures, "failures": pair_failures}),
            },
            "metadata": {
                "mode": "offline_scripted", "evaluator_version": EVALUATOR_VERSION,
                "adapter_version": SCRIPTED_ADAPTER_VERSION,
                "pool": "private_holdout" if holdout else "development",
                "scenario_distribution": dict(sorted(family_counts.items())),
                "semantic_family_distribution": dict(sorted(semantic_family_counts.items())),
                "semantic_family_slice_metrics": slice_metrics,
                "errors": sum(record["error"] is not None for record in records),
                "stop_reasons": dict(sorted(Counter(
                    str(record["stop_reason"].value if hasattr(record["stop_reason"], "value") else record["stop_reason"])
                    for record in records if record["stop_reason"] is not None
                ).items())),
                "variance": {"kind": "deterministic_single_run", "value": 0.0},
            },
            "instrumentation": {"controller_calls": len(records), "tokens": 0, "latency_seconds": 0.0, "errors": sum(record["error"] is not None for record in records)},
        },
    }
    if holdout:
        encoded = json.dumps(artifact, sort_keys=True)
        forbidden = [str(fixture_path), *(case.identifier for case in cases)]
        if any(token in encoded for token in forbidden) or "records" in artifact:
            raise AssertionError("private holdout artifact leaks fixture identifiers, path, or records")
    return artifact


__all__ = [
    "DEFAULT_CLARIFICATION_BEHAVIOR_FIXTURES", "ClarificationBehaviorFixtureError",
    "preflight_clarification_behavior_cases", "run_clarification_behavior_eval",
]
