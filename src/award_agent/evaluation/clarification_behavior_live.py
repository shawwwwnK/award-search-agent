"""Live, property-based ADR 0012 clarification qualification.

This runner deliberately checks behavioral envelopes rather than a prewritten
model answer. Exact state integrity remains a hard safety gate. Model payloads
and answer text are written only to private trace sidecars.
"""

from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol
from uuid import uuid4

import yaml

from award_agent.clarification.blockers import collect_blocking_requirements
from award_agent.clarification.composer import ClarificationPromptComposer
from award_agent.clarification.controller import (
    ClarificationCompositionPending,
    ClarificationInterpretationPending,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import ClarificationAnswerInterpreter
from award_agent.clarification.openai_composer import (
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
)
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpreterConfig,
)
from award_agent.domain import ClarificationAnswerCommand
from award_agent.evaluation.clarification_behavior import _initial, _privacy_violations
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_LIVE_BEHAVIOR_FIXTURES = Path("evals/clarification/live_cases_v3_development.yaml")
DEFAULT_LIVE_BEHAVIOR_TRACE_DIR = Path("evals/clarification/traces-behavior-v3")
EVALUATOR_VERSION = "clarification_behavior_live_eval_v3.0"

_FIELDS = {"origin", "destination", "travelers", "departure", "return_or_duration"}
_STATUSES = {"ready", "awaiting_answer", "stopped"}
_CLASSES = {
    "reasonably_resolvable",
    "safely_assumable",
    "ambiguous",
    "conflict",
    "correction",
    "nonanswer",
}
_PROPERTY_KEYS = {
    "departure_window",
    "return_window",
    "duration_days",
    "return_after_departure",
    "bounded_departure_window",
    "bounded_return_window",
}
_VALUE_KEYS = {"origin", "destination", "travelers", "departure", "return"}
_CONFLICT_IDS = {"conflict:return_before_departure"}
_V3_ACTIONS = {"resolve", "partial_resolve_and_ask", "ask", "stop", "pending_retryable"}
_V3_QUESTION_ISSUE_KINDS = {"missing", "ambiguous", "unsupported", "conflict"}
_V3_STATE_RELATIONS = {"ready_iff_no_blockers", "prompt_covers_remaining_blockers"}
_V3_FORBIDDEN_OUTCOMES = {
    "unsafe_ambiguity_acceptance",
    "protected_field_mutation",
    "unexpected_stop",
    "unnecessary_ask",
    "question_intent_mismatch",
    "disclosure_missing",
}
_V3_ORACLE_KEYS = {
    "expected_action",
    "must_resolve",
    "must_remain_blocked",
    "protected_fields",
    "forbidden_outcomes",
    "state_envelope",
    "question_intent",
    "disclosure",
    "properties",
    "values",
    "valid_siblings",
}
_V3_DEVELOPMENT_FAMILIES = {
    "clear_resolvable",
    "alternatives",
    "endpoint_ambiguity",
    "correction_sibling",
    "sibling_retention",
    "disclosed_approximation",
    "conflict",
}


class ClarificationBehaviorLiveFixtureError(ValueError):
    """A live behavioral fixture cannot be executed safely."""


class _Traceable(Protocol):
    def take_usage(self) -> dict[str, int] | None: ...

    def take_call_traces(self) -> list[dict[str, Any]]: ...


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ClarificationBehaviorLiveFixtureError(f"{label} must be a non-empty string")
    return value


def _strict_iso_date(value: object, label: str) -> None:
    if not isinstance(value, str):
        raise ClarificationBehaviorLiveFixtureError(f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ClarificationBehaviorLiveFixtureError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ClarificationBehaviorLiveFixtureError(f"{label} must be an exact ISO date")


def _valid_envelope(window: object) -> bool:
    if not isinstance(window, Mapping) or set(window) != {"year", "month", "start_day", "end_day"}:
        return False
    year, month = window["year"], window["month"]
    if (
        not isinstance(year, int)
        or isinstance(year, bool)
        or not isinstance(month, int)
        or isinstance(month, bool)
        or not 1 <= month <= 12
    ):
        return False
    maximum_day = monthrange(year, month)[1]
    ranges: list[list[int]] = []
    for key in ("start_day", "end_day"):
        value = window[key]
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(not isinstance(day, int) or isinstance(day, bool) for day in value)
            or not 1 <= value[0] <= value[1] <= maximum_day
        ):
            return False
        ranges.append(value)
    return ranges[0][0] <= ranges[1][0] and ranges[0][1] <= ranges[1][1]


def _validate_v3_oracle(oracle: Mapping[str, Any], answer_class: str) -> None:
    """Validate a behavior-first oracle without admitting internal model forms.

    The contract deliberately names only observable session state, prompt
    requirement/issue links, and visible assumption provenance.  It has no
    slot for receiver ASTs, proposal handles, or customer-facing copy.
    """

    if set(oracle) - _V3_ORACLE_KEYS:
        raise ClarificationBehaviorLiveFixtureError(
            "v3 oracle may contain only observable outcome and prompt-intent fields"
        )
    action = oracle.get("expected_action")
    if not isinstance(action, str) or action not in _V3_ACTIONS:
        raise ClarificationBehaviorLiveFixtureError("v3 oracle expected_action is unsupported")
    for key in ("must_resolve", "must_remain_blocked", "protected_fields"):
        values = oracle.get(key)
        if not isinstance(values, list) or not all(
            isinstance(value, str) and value in _FIELDS | _CONFLICT_IDS for value in values
        ) or len(values) != len(set(values)):
            raise ClarificationBehaviorLiveFixtureError(f"v3 oracle needs supported {key}")
    must_resolve = set(oracle["must_resolve"])
    must_remain = set(oracle["must_remain_blocked"])
    if must_resolve & must_remain:
        raise ClarificationBehaviorLiveFixtureError("v3 must_resolve and must_remain_blocked overlap")
    forbidden = oracle.get("forbidden_outcomes")
    if not isinstance(forbidden, list) or not all(
        isinstance(item, str) and item in _V3_FORBIDDEN_OUTCOMES for item in forbidden
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 oracle has unsupported forbidden_outcomes")
    if answer_class in {"ambiguous", "conflict"} and "unsafe_ambiguity_acceptance" not in forbidden:
        raise ClarificationBehaviorLiveFixtureError(
            "v3 ambiguous/conflict oracles must forbid unsafe_ambiguity_acceptance"
        )
    envelope = oracle.get("state_envelope")
    if not isinstance(envelope, Mapping):
        raise ClarificationBehaviorLiveFixtureError("v3 oracle needs state_envelope")
    statuses, relations = envelope.get("statuses"), envelope.get("relations")
    if (
        not isinstance(statuses, list)
        or not statuses
        or not all(isinstance(value, str) and value in _STATUSES for value in statuses)
        or not isinstance(relations, list)
        or not all(isinstance(value, str) and value in _V3_STATE_RELATIONS for value in relations)
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 state_envelope is invalid")
    action_status = {
        "resolve": {"ready"},
        "partial_resolve_and_ask": {"awaiting_answer"},
        "ask": {"awaiting_answer"},
        "stop": {"stopped"},
        "pending_retryable": {"awaiting_answer"},
    }[action]
    if not set(statuses).issubset(action_status):
        raise ClarificationBehaviorLiveFixtureError("v3 state_envelope conflicts with expected_action")
    if (
        (action == "resolve" and must_remain)
        or (action == "partial_resolve_and_ask" and (not must_resolve or not must_remain))
        or (action == "ask" and (must_resolve or not must_remain))
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 expected_action conflicts with blocker outcome")
    intent = oracle.get("question_intent")
    if not isinstance(intent, Mapping) or not isinstance(intent.get("required"), bool):
        raise ClarificationBehaviorLiveFixtureError("v3 oracle needs question_intent.required")
    requirement_ids, issue_kinds = intent.get("requirement_ids", []), intent.get("issue_kinds", [])
    if (
        not isinstance(requirement_ids, list)
        or not all(isinstance(item, str) and item in _FIELDS | _CONFLICT_IDS for item in requirement_ids)
        or not isinstance(issue_kinds, list)
        or not all(isinstance(item, str) and item in _V3_QUESTION_ISSUE_KINDS for item in issue_kinds)
        or (not intent["required"] and (requirement_ids or issue_kinds))
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 question_intent is invalid")
    if action in {"partial_resolve_and_ask", "ask"} and not intent["required"]:
        raise ClarificationBehaviorLiveFixtureError("v3 ask actions require question intent")
    disclosure = oracle.get("disclosure")
    if not isinstance(disclosure, Mapping) or not isinstance(disclosure.get("required"), bool):
        raise ClarificationBehaviorLiveFixtureError("v3 oracle needs disclosure.required")
    if not isinstance(oracle.get("properties", {}), Mapping) or set(oracle.get("properties", {})) - _PROPERTY_KEYS:
        raise ClarificationBehaviorLiveFixtureError("v3 oracle properties are invalid")
    for key in ("departure_window", "return_window"):
        if oracle.get("properties", {}).get(key) is not None and not _valid_envelope(
            oracle["properties"][key]
        ):
            raise ClarificationBehaviorLiveFixtureError(f"v3 {key} envelope is invalid")
    duration = oracle.get("properties", {}).get("duration_days")
    if duration is not None and (
        not isinstance(duration, list)
        or len(duration) != 2
        or not all(isinstance(day, int) and not isinstance(day, bool) for day in duration)
        or not 1 <= duration[0] <= duration[1]
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 duration_days envelope is invalid")
    for key in ("return_after_departure", "bounded_departure_window", "bounded_return_window"):
        if key in oracle.get("properties", {}) and not isinstance(oracle["properties"][key], bool):
            raise ClarificationBehaviorLiveFixtureError(f"v3 {key} must be boolean")
    if not isinstance(oracle.get("values", {}), Mapping) or set(oracle.get("values", {})) - _VALUE_KEYS:
        raise ClarificationBehaviorLiveFixtureError("v3 oracle values are unsupported")
    values = oracle.get("values", {})
    if any(
        not isinstance(values[key], str) or not values[key]
        for key in {"origin", "destination", "departure", "return"} & set(values)
    ) or (
        "travelers" in values
        and (
            not isinstance(values["travelers"], int)
            or isinstance(values["travelers"], bool)
            or values["travelers"] < 1
        )
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 oracle values have invalid types")
    for key in {"departure", "return"} & set(values):
        _strict_iso_date(values[key], f"v3 oracle.values.{key}")
    siblings = oracle.get("valid_siblings", [])
    if (
        not isinstance(siblings, list)
        or not all(isinstance(value, str) and value in _FIELDS for value in siblings)
        or not set(siblings).issubset(must_resolve)
    ):
        raise ClarificationBehaviorLiveFixtureError("v3 valid_siblings must be must_resolve fields")


def _load_v3_cases(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ClarificationBehaviorLiveFixtureError("v3 live behavioral qualification needs scenarios")
    if _privacy_violations(payload):
        raise ClarificationBehaviorLiveFixtureError("v3 live behavioral fixtures fail privacy lint")
    identifiers: set[str] = set()
    families: set[str] = set()
    prepared: list[Mapping[str, Any]] = []
    for item in scenarios:
        if not isinstance(item, Mapping):
            raise ClarificationBehaviorLiveFixtureError("v3 scenario must be a mapping")
        identifier = _string(item.get("id"), "scenario.id")
        if identifier in identifiers:
            raise ClarificationBehaviorLiveFixtureError("v3 scenario IDs must be unique")
        identifiers.add(identifier)
        families.add(_string(item.get("family"), "scenario.family"))
        answer_class = _string(item.get("answer_class"), "scenario.answer_class")
        if answer_class not in _CLASSES:
            raise ClarificationBehaviorLiveFixtureError("v3 answer_class is unsupported")
        unknowns = item.get("initial_unknowns")
        if not isinstance(unknowns, list) or not all(
            isinstance(value, str) and value in _FIELDS for value in unknowns
        ):
            raise ClarificationBehaviorLiveFixtureError("v3 initial_unknowns must contain supported fields")
        turns = item.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ClarificationBehaviorLiveFixtureError("v3 scenario needs turns")
        for turn in turns:
            if not isinstance(turn, Mapping) or not isinstance(turn.get("oracle"), Mapping):
                raise ClarificationBehaviorLiveFixtureError("v3 turn needs an oracle")
            _string(turn.get("text"), "turn.text")
            _validate_v3_oracle(turn["oracle"], answer_class)
        prepared.append(item)
    if payload.get("development_corpus") is True and not _V3_DEVELOPMENT_FAMILIES.issubset(families):
        raise ClarificationBehaviorLiveFixtureError(
            "v3 development corpus lacks required scenario families"
        )
    return tuple(prepared)


def _load_cases(path: Path) -> tuple[tuple[Mapping[str, Any], ...], bytes]:
    try:
        raw = path.read_bytes()
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationBehaviorLiveFixtureError("unable to load live behavioral fixtures") from exc
    if not isinstance(payload, Mapping):
        raise ClarificationBehaviorLiveFixtureError("live behavioral fixture root must be a mapping")
    if payload.get("contract_version") == "v3-live":
        return _load_v3_cases(payload), raw
    if payload.get("contract_version") != "v2-live":
        raise ClarificationBehaviorLiveFixtureError("live behavioral fixtures must use contract_version v2-live")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 16:
        raise ClarificationBehaviorLiveFixtureError("live behavioral qualification needs at least 16 scenarios")
    if _privacy_violations(payload):
        raise ClarificationBehaviorLiveFixtureError("live behavioral fixtures fail privacy lint")
    identifiers: set[str] = set()
    pairs: dict[str, list[tuple[str, str]]] = defaultdict(list)
    equivalence_groups: dict[str, int] = defaultdict(int)
    families: set[str] = set()
    prepared: list[Mapping[str, Any]] = []
    for item in scenarios:
        if not isinstance(item, Mapping):
            raise ClarificationBehaviorLiveFixtureError("live behavioral scenario must be a mapping")
        identifier = _string(item.get("id"), "scenario.id")
        if identifier in identifiers:
            raise ClarificationBehaviorLiveFixtureError("live behavioral scenario IDs must be unique")
        identifiers.add(identifier)
        families.add(_string(item.get("family"), "scenario.family"))
        if _string(item.get("answer_class"), "scenario.answer_class") not in _CLASSES:
            raise ClarificationBehaviorLiveFixtureError("live behavioral answer_class is unsupported")
        for key in ("initial_origin", "initial_destination"):
            if key in item:
                _string(item[key], f"scenario.{key}")
        if "initial_travelers" in item and (
            not isinstance(item["initial_travelers"], int)
            or isinstance(item["initial_travelers"], bool)
            or item["initial_travelers"] < 1
        ):
            raise ClarificationBehaviorLiveFixtureError("initial_travelers must be a positive integer")
        if "initial_departure" in item:
            _strict_iso_date(item["initial_departure"], "scenario.initial_departure")
        if "initial_duration_days" in item and (
            not isinstance(item["initial_duration_days"], int)
            or isinstance(item["initial_duration_days"], bool)
            or item["initial_duration_days"] < 1
        ):
            raise ClarificationBehaviorLiveFixtureError("initial_duration_days must be a positive integer")
        unknowns = item.get("initial_unknowns")
        if (
            not isinstance(unknowns, list)
            or not all(isinstance(value, str) and value in _FIELDS for value in unknowns)
            or len(unknowns) != len(set(unknowns))
        ):
            raise ClarificationBehaviorLiveFixtureError("initial_unknowns must contain supported fields")
        turns = item.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ClarificationBehaviorLiveFixtureError("live behavioral scenario needs turns")
        for turn in turns:
            if not isinstance(turn, Mapping) or not isinstance(turn.get("oracle"), Mapping):
                raise ClarificationBehaviorLiveFixtureError("live behavioral turn needs an oracle")
            _string(turn.get("text"), "turn.text")
            oracle = turn["oracle"]
            for key in ("must_resolve", "must_remain_blocked", "protected_fields", "permitted_statuses"):
                if not isinstance(oracle.get(key), list):
                    raise ClarificationBehaviorLiveFixtureError(f"live behavioral oracle needs {key}")
            if not all(
                isinstance(value, str)
                and value in _FIELDS | _CONFLICT_IDS
                for key in ("must_resolve", "must_remain_blocked", "protected_fields")
                for value in oracle[key]
            ):
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle has an unsupported field")
            siblings = oracle.get("valid_siblings", [])
            if (
                not isinstance(siblings, list)
                or not all(isinstance(value, str) and value in _FIELDS for value in siblings)
                or not set(siblings).issubset(oracle["must_resolve"])
            ):
                raise ClarificationBehaviorLiveFixtureError("valid_siblings must be a subset of must_resolve")
            if not all(value in _STATUSES for value in oracle["permitted_statuses"]):
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle has an unsupported status")
            if not isinstance(oracle.get("properties"), Mapping) or set(oracle["properties"]) - _PROPERTY_KEYS:
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle properties must be a mapping")
            departure_window = oracle["properties"].get("departure_window")
            if departure_window is not None and not _valid_envelope(departure_window):
                raise ClarificationBehaviorLiveFixtureError("departure_window envelope is invalid")
            duration_days = oracle["properties"].get("duration_days")
            if duration_days is not None and (
                not isinstance(duration_days, list)
                or len(duration_days) != 2
                or not all(isinstance(day, int) and not isinstance(day, bool) for day in duration_days)
                or not 1 <= duration_days[0] <= duration_days[1]
            ):
                raise ClarificationBehaviorLiveFixtureError("duration_days envelope is invalid")
            if not isinstance(oracle.get("values", {}), Mapping) or set(oracle.get("values", {})) - _VALUE_KEYS:
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle values are unsupported")
            values = oracle.get("values", {})
            if any(
                not isinstance(values[key], str) or not values[key]
                for key in {"origin", "destination", "departure", "return"} & set(values)
            ) or (
                "travelers" in values
                and (
                    not isinstance(values["travelers"], int)
                    or isinstance(values["travelers"], bool)
                    or values["travelers"] < 1
                )
            ):
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle values have invalid types")
            for key in {"departure", "return"} & set(values):
                _strict_iso_date(values[key], f"oracle.values.{key}")
            if not isinstance(oracle.get("disclosure_required"), bool) or not isinstance(
                oracle.get("question_required"), bool
            ):
                raise ClarificationBehaviorLiveFixtureError("live behavioral oracle flags must be booleans")
        if item.get("pair_id") is not None:
            role = _string(item.get("pair_role"), "pair_role")
            pairs[_string(item["pair_id"], "pair_id")].append((role, str(item["answer_class"])))
        if item.get("equivalence_group") is not None:
            equivalence_groups[_string(item["equivalence_group"], "equivalence_group")] += 1
        prepared.append(item)
    if {str(item["answer_class"]) for item in prepared} != _CLASSES:
        raise ClarificationBehaviorLiveFixtureError("live behavioral fixture must cover every answer class")
    if not {"accepting", "accepting_paraphrase", "paired_boundary", "partial_sibling", "targeted_composer", "correction", "no_progress", "conflict"}.issubset(families):
        raise ClarificationBehaviorLiveFixtureError("live behavioral fixture lacks required scenario families")
    if not pairs or any(
        len(items) != 2
        or {role for role, _ in items} != {"accept", "ask"}
        or any(role == "accept" and answer_class not in {"reasonably_resolvable", "safely_assumable"} for role, answer_class in items)
        or any(role == "ask" and answer_class not in {"ambiguous", "conflict"} for role, answer_class in items)
        for items in pairs.values()
    ):
        raise ClarificationBehaviorLiveFixtureError("each live behavioral pair requires accept and ask members")
    if any(count < 2 for count in equivalence_groups.values()):
        raise ClarificationBehaviorLiveFixtureError("each equivalence group needs at least two scenarios")
    return tuple(prepared), raw


def preflight_live_clarification_behavior_cases(
    fixture_path: Path = DEFAULT_LIVE_BEHAVIOR_FIXTURES,
) -> tuple[Mapping[str, Any], ...]:
    return _load_cases(fixture_path)[0]


def _blockers(session: Any) -> list[str]:
    return [item.requirement_id for item in collect_blocking_requirements(session.effective_request)]


def _field_values(session: Any) -> dict[str, object]:
    effective = session.effective_request
    window = lambda value: None if value is None else (value.start.isoformat(), value.end.isoformat())
    duration = effective.interpreted_duration
    return {
        "origin": tuple((item.kind.value, item.value) for item in effective.origins),
        "destination": tuple((item.kind.value, item.value) for item in effective.destinations),
        "travelers": effective.travelers,
        "departure": window(effective.departure_window),
        "return_or_duration": (
            window(effective.return_window),
            None if duration is None else (duration.minimum_days, duration.maximum_days),
        ),
    }


def _property_failures(session: Any, properties: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    window = properties.get("departure_window")
    actual = session.effective_request.departure_window
    if window is not None:
        if not isinstance(window, Mapping) or actual is None:
            failures.append("departure window missing")
        elif (
            actual.start.year != window.get("year")
            or actual.start.month != window.get("month")
            or not window.get("start_day", [99, 0])[0] <= actual.start.day <= window.get("start_day", [0, 0])[1]
            or not window.get("end_day", [99, 0])[0] <= actual.end.day <= window.get("end_day", [0, 0])[1]
        ):
            failures.append("departure window outside acceptable envelope")
    duration = properties.get("duration_days")
    actual_duration = session.effective_request.interpreted_duration
    if duration is not None and (
        not isinstance(duration, list)
        or actual_duration is None
        or not duration[0] <= actual_duration.minimum_days <= actual_duration.maximum_days <= duration[1]
    ):
        failures.append("duration outside acceptable envelope")
    return_window = properties.get("return_window")
    actual_return = session.effective_request.return_window
    if return_window is not None:
        if not isinstance(return_window, Mapping) or actual_return is None:
            failures.append("return window missing")
        elif (
            actual_return.start.year != return_window.get("year")
            or actual_return.start.month != return_window.get("month")
            or not return_window.get("start_day", [99, 0])[0]
            <= actual_return.start.day
            <= return_window.get("start_day", [0, 0])[1]
            or not return_window.get("end_day", [99, 0])[0]
            <= actual_return.end.day
            <= return_window.get("end_day", [0, 0])[1]
        ):
            failures.append("return window outside acceptable envelope")
    departure = session.effective_request.departure_window
    if properties.get("bounded_departure_window") and (
        departure is None or departure.end < departure.start
    ):
        failures.append("departure window is not bounded")
    if properties.get("bounded_return_window") and (
        actual_return is None or actual_return.end < actual_return.start
    ):
        failures.append("return window is not bounded")
    if properties.get("return_after_departure") and (
        departure is None or actual_return is None or actual_return.start < departure.end
    ):
        failures.append("return is not after departure")
    return failures


def _value_failures(session: Any, values: Mapping[str, Any]) -> list[str]:
    """Check exact values only where a live oracle explicitly requests them."""

    effective = session.effective_request
    actual: dict[str, object] = {
        "origin": effective.origins[0].value if len(effective.origins) == 1 else None,
        "destination": effective.destinations[0].value if len(effective.destinations) == 1 else None,
        "travelers": effective.travelers,
        "departure": (
            effective.departure_window.start.isoformat()
            if effective.departure_window is not None
            and effective.departure_window.start == effective.departure_window.end
            else None
        ),
        "return": (
            effective.return_window.start.isoformat()
            if effective.return_window is not None
            and effective.return_window.start == effective.return_window.end
            else None
        ),
    }
    return [f"exact value mismatch: {field}" for field, value in values.items() if actual[field] != value]


def _v3_observed_action(status: str, resolved: set[str], *, pending_retryable: bool = False) -> str:
    if pending_retryable:
        return "pending_retryable"
    if status == "stopped":
        return "stop"
    if status == "ready":
        return "resolve"
    return "partial_resolve_and_ask" if resolved else "ask"


def _v3_outcome_failures(
    *,
    oracle: Mapping[str, Any],
    answer_class: str,
    status: str,
    before_blockers: tuple[str, ...],
    blockers: tuple[str, ...],
    before_values: Mapping[str, object],
    after_values: Mapping[str, object],
    prompt_requirement_ids: tuple[str, ...] | None,
    prompt_issue_kinds: tuple[str, ...],
    prompt_message: str | None,
    disclosure_present: bool,
    pending_retryable: bool = False,
) -> tuple[str, list[str], list[str]]:
    """Score only observable outcomes; never receiver forms or prompt wording.

    The first returned list is an exact-safety failure list.  In particular,
    ambiguous/conflicting answers that clear a required blocker fail closed
    even if a fixture author accidentally omits a softer behavioral rule.
    """

    # Naturalness is human-reviewed separately.  Only typed prompt intent is
    # assessed here, never a literal generated question.
    del prompt_message
    safety: list[str] = []
    behavioral: list[str] = []
    blocker_set, before_blocker_set = set(blockers), set(before_blockers)
    resolved = before_blocker_set - blocker_set
    action = _v3_observed_action(status, resolved, pending_retryable=pending_retryable)
    must_resolve = set(oracle["must_resolve"])
    must_remain = set(oracle["must_remain_blocked"])
    forbidden = set(oracle["forbidden_outcomes"])
    events: set[str] = set()

    if must_resolve - resolved:
        behavioral.append("false blocking")
    if not must_remain.issubset(blocker_set):
        events.add("unsafe_ambiguity_acceptance")
        safety.append("required blocker silently cleared")
    if any(before_values.get(field) != after_values.get(field) for field in oracle["protected_fields"]):
        events.add("protected_field_mutation")
        safety.append("protected fields changed")
    if action != oracle["expected_action"]:
        behavioral.append("outcome action outside expected envelope")
        if action == "stop":
            events.add("unexpected_stop")
        if action == "ask" and oracle["expected_action"] in {"resolve", "partial_resolve_and_ask"}:
            events.add("unnecessary_ask")

    envelope = oracle["state_envelope"]
    if status not in envelope["statuses"]:
        behavioral.append("status outside permitted envelope")
    relations = set(envelope["relations"])
    if "ready_iff_no_blockers" in relations and (status == "ready") != (not blocker_set):
        safety.append("ready status does not exactly match blockers")
    if "prompt_covers_remaining_blockers" in relations:
        if status == "awaiting_answer":
            if prompt_requirement_ids != blockers:
                safety.append("prompt blocker coverage failed")
        elif prompt_requirement_ids is not None:
            safety.append("terminal state retained a prompt")

    intent = oracle["question_intent"]
    if intent["required"]:
        if prompt_requirement_ids is None:
            events.add("question_intent_mismatch")
            behavioral.append("question intent missing")
        else:
            if tuple(intent["requirement_ids"]) != prompt_requirement_ids or not set(
                intent["issue_kinds"]
            ).issubset(prompt_issue_kinds):
                events.add("question_intent_mismatch")
                behavioral.append("question intent mismatch")
    elif prompt_requirement_ids is not None and status != "awaiting_answer":
        events.add("question_intent_mismatch")

    if oracle["disclosure"]["required"] and not disclosure_present:
        events.add("disclosure_missing")
        safety.append("accepted approximation has no disclosure")
    if (
        answer_class in {"ambiguous", "conflict"}
        and not must_remain.issubset(blocker_set)
        and "unsafe ambiguity acceptance" not in safety
    ):
        safety.append("unsafe ambiguity acceptance")
    for event in sorted(events & forbidden):
        if event == "unsafe_ambiguity_acceptance":
            # The specific hard failure above is retained too; this stable
            # marker makes fixture-driven reports easy to aggregate.
            safety.append(f"forbidden outcome: {event}")
        else:
            behavioral.append(f"forbidden outcome: {event}")
    return action, safety, behavioral


def _v3_unnecessary_clarification(
    *, action: str, oracle: Mapping[str, Any], behavioral_failures: Sequence[str]
) -> bool:
    """Classify avoidable follow-ups from observable action and outcome codes.

    This intentionally does not inspect composed prose. A requested resolve
    or partial resolve that instead leaves the user in an asking state is an
    unnecessary clarification, as is any recorded false block or explicit
    forbidden unnecessary-ask outcome.
    """

    expected_action = oracle["expected_action"]
    followup_instead_of_resolution = (
        action in {"ask", "partial_resolve_and_ask"}
        and expected_action in {"resolve", "partial_resolve_and_ask"}
    )
    return followup_instead_of_resolution or any(
        failure in {"false blocking", "forbidden outcome: unnecessary_ask"}
        for failure in behavioral_failures
    )


def _targeted_assessment(session: Any) -> tuple[bool, str, bool]:
    """Assess question specificity without requiring a verbatim quotation.

    Prompt requirement/issue coverage remains deterministic.  Naturalness is
    a calibrated automated proxy: direct quotation, or a requirement-specific
    cue in a question, passes. Other validly-covered prompts are flagged for
    manual review rather than treated as an automatic safety failure.
    """

    prompt = session.current_revision.prompt
    if prompt is None:
        return False, "none", False
    spans = [issue.span.text.casefold() for issue in prompt.issues if issue.span is not None]
    if not spans:
        return False, prompt.composition_source.value, False
    message = prompt.message.casefold()
    quoted = any(span in message for span in spans)
    cues = {
        "origin": ("depart", "from", "airport", "where"),
        "destination": ("destination", "go", "where"),
        "departure": ("leave", "depart", "date", "range", "when"),
        "return_or_duration": ("return", "trip", "long", "duration", "week", "day"),
        "travelers": ("travel", "people", "passengers", "many"),
        "conflict": ("which", "conflict", "choose", "date"),
    }
    covered = all(
        any(cue in message for cue in cues[requirement.kind.value])
        for requirement in prompt.requirements
    )
    return quoted or covered, prompt.composition_source.value, not (quoted or covered)


def _usage(adapter: _Traceable) -> tuple[dict[str, int], list[dict[str, Any]]]:
    usage = adapter.take_usage() or {}
    normalized = {
        key: int(usage.get(key, 0))
        for key in ("calls", "captured_calls", "missing_calls", "input_tokens", "output_tokens", "total_tokens")
    }
    return normalized, adapter.take_call_traces()


def _drain_optional(adapter: object | None) -> tuple[dict[str, int], list[dict[str, Any]]]:
    if adapter is None:
        return ({key: 0 for key in ("calls", "captured_calls", "missing_calls", "input_tokens", "output_tokens", "total_tokens")}, [])
    return _usage(adapter)  # type: ignore[arg-type]


def _safe_drain(
    adapter: object | None, safety_failures: list[str]
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Drain diagnostic state without letting a broken adapter hide a session."""

    try:
        return _drain_optional(adapter)
    except Exception as exc:  # noqa: BLE001 - evidence collection is part of the safety boundary.
        safety_failures.append(f"trace drain error: {type(exc).__name__}")
        return (
            {
                key: 0
                for key in (
                    "calls",
                    "captured_calls",
                    "missing_calls",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                )
            },
            [],
        )


def _stage_summary(usage: Mapping[str, int], traces: Sequence[Mapping[str, Any]]) -> dict[str, object]:
    trace_count = len(traces)
    return {
        **usage,
        "trace_count": trace_count,
        "reconciled": (
            usage["calls"] == trace_count
            and usage["captured_calls"] == trace_count
            and usage["missing_calls"] == 0
        ),
        "latency_seconds": sum(
            float(trace.get("latency_seconds") or 0.0) for trace in traces
        ),
        "errors": sum(trace.get("error") is not None for trace in traces),
    }


def _repair_telemetry(
    traces: Sequence[Mapping[str, Any]],
    *,
    pending_retryable: int,
    pending_receiver: int,
    pending_composer: int,
) -> dict[str, int | float]:
    """Keep repair traces distinct from first-pass receiver telemetry.

    Adapters retain full calls in private sidecars.  The public artifact only
    exposes counts, errors, and latency by phase; a handled unavailable result
    is reported as pending rather than misclassified as a trace failure.
    """

    repair = [trace for trace in traces if trace.get("stage") == "interpreter_repair"]
    first_pass = [trace for trace in traces if trace.get("stage") == "interpreter"]
    repair_errors = sum(trace.get("error") is not None for trace in repair)
    repaired_workflow = int(bool(repair) and repair_errors == 0 and pending_retryable == 0)
    return {
        "first_pass_calls": len(first_pass),
        "repair_calls": len(repair),
        "repair_errors": repair_errors,
        "repaired_workflows": repaired_workflow,
        "repair_latency_seconds": sum(float(trace.get("latency_seconds") or 0.0) for trace in repair),
        "pending_retryable": pending_retryable,
        "pending_receiver": pending_receiver,
        "pending_composer": pending_composer,
    }


def _string_leaves(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, Mapping):
        return set().union(*(_string_leaves(item) for item in value.values())) if value else set()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return set().union(*(_string_leaves(item) for item in value)) if value else set()
    return set()


def run_live_clarification_behavior_eval(
    *,
    interpreter_model: str = "gpt-5.6-luna",
    composer_model: str = "gpt-5.6-luna",
    trials: int = 3,
    fixture_path: Path = DEFAULT_LIVE_BEHAVIOR_FIXTURES,
    trace_dir: Path = DEFAULT_LIVE_BEHAVIOR_TRACE_DIR,
    interpreter_factory: Callable[[str], ClarificationAnswerInterpreter] | None = None,
    composer_factory: Callable[[str], ClarificationPromptComposer] | None = None,
) -> dict[str, Any]:
    """Execute real model seams against property envelopes, never gold prose."""

    if trials < 1:
        raise ValueError("trials must be positive")
    cases, raw = _load_cases(fixture_path)
    fixture_payload = yaml.safe_load(raw)
    assert isinstance(fixture_payload, Mapping)
    is_v3 = fixture_payload["contract_version"] == "v3-live"
    make_interpreter = interpreter_factory or (
        lambda model: OpenAIClarificationAnswerInterpreter(
            OpenAIClarificationInterpreterConfig(model=model), capture_llm_io=True
        )
    )
    make_composer = composer_factory or (
        lambda model: OpenAIClarificationPromptComposer(
            OpenAIClarificationComposerConfig(model=model), capture_llm_io=True
        )
    )
    generated_at = datetime.now(UTC).isoformat()
    trace_run_dir = trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    records: list[dict[str, Any]] = []
    trace_count = 0
    for trial in range(1, trials + 1):
        for case in cases:
            identifier, family, answer_class = str(case["id"]), str(case["family"]), str(case["answer_class"])
            started = perf_counter()
            safety_failures: list[str] = []
            interpreter: ClarificationAnswerInterpreter | None = None
            composer: ClarificationPromptComposer | None = None
            session: Any | None = None
            initial_snapshot: object | None = None
            try:
                interpreter = make_interpreter(interpreter_model)
                composer = make_composer(composer_model)
                session = start_clarification(
                    _initial(case),
                    session_id=f"behavior-live-{identifier}-{trial}",
                    composer=composer,
                )
                initial_snapshot = deepcopy(session.initial_result.model_dump(mode="json"))
            except Exception as exc:  # noqa: BLE001 - construction/start failures are live safety events.
                safety_failures.append(f"system error: {type(exc).__name__}")
            behavioral_failures: list[str] = []
            property_failures: list[str] = []
            value_failures: list[str] = []
            turn_metrics: list[dict[str, object]] = []
            turns_ready: int | None = None
            question_required_count = targeted_question_count = 0
            manual_review_count = 0
            composition_sources: Counter[str] = Counter()
            valid_siblings_expected = valid_siblings_retained = 0
            pending_retryable_count = 0
            pending_receiver_count = 0
            pending_composer_count = 0
            if session is None or interpreter is None or composer is None:
                interpreter_usage, interpreter_traces = _safe_drain(interpreter, safety_failures)
                composer_usage, composer_traces = _safe_drain(composer, safety_failures)
                stages = {
                    "interpreter": _stage_summary(interpreter_usage, interpreter_traces),
                    "composer": _stage_summary(composer_usage, composer_traces),
                }
                repair_telemetry = _repair_telemetry(
                    interpreter_traces,
                    pending_retryable=0,
                    pending_receiver=0,
                    pending_composer=0,
                )
                if any(
                    not bool(stage["reconciled"]) or stage["errors"] != 0
                    for stage in stages.values()
                ):
                    safety_failures.append("model trace reconciliation failed")
                record: dict[str, Any] = {
                    "scenario": identifier,
                    "family": family,
                    "answer_class": answer_class,
                    "trial": trial,
                    "final_status": "construction_failed",
                    "stop_reason": None,
                    "safety_passed": False,
                    "behavioral_passed": False,
                    "safety_failures": safety_failures,
                    "behavioral_failures": ["construction failed"],
                    "property_failures": [],
                    "value_failures": [],
                    "turn_metrics": [],
                    "turns_to_ready": None,
                    "targeted_questions": {"required": 0, "targeted": 0},
                    "question_composition": {"sources": {}, "manual_review_required": 0},
                    "valid_siblings": {"expected": 0, "retained": 0},
                    "repair_telemetry": repair_telemetry,
                    "latency_seconds": perf_counter() - started,
                    "stages": stages,
                }
                write_eval_llm_trace(
                    trace_run_dir,
                    scenario={"id": identifier, "input": dict(case)},
                    record=record,
                    calls=[*interpreter_traces, *composer_traces],
                )
                trace_count += 1
                records.append(record)
                continue
            try:
                for ordinal, turn in enumerate(case["turns"], start=1):
                    assert isinstance(turn, Mapping)
                    oracle = turn["oracle"]
                    assert isinstance(oracle, Mapping)
                    if session.current_revision.prompt is None:
                        safety_failures.append("missing pending prompt")
                        break
                    before, before_blockers = _field_values(session), _blockers(session)
                    command = ClarificationAnswerCommand(
                        session_id=session.session_id,
                        expected_revision=session.current_revision.revision,
                        prompt_id=session.current_revision.prompt.prompt_id,
                        message_id=f"{identifier}:{trial}:{ordinal}",
                        text=str(turn["text"]),
                    )
                    try:
                        applied = apply_clarification_answer(
                            session, command, interpreter, composer=composer
                        )
                    except Exception as exc:  # noqa: BLE001 - report live boundary failures as safety failures.
                        safety_failures.append(f"system error: {type(exc).__name__}")
                        break
                    pending_retryable = isinstance(
                        applied, (ClarificationInterpretationPending, ClarificationCompositionPending)
                    )
                    if pending_retryable:
                        pending_retryable_count += 1
                        pending_receiver_count += int(
                            isinstance(applied, ClarificationInterpretationPending)
                        )
                        pending_composer_count += int(
                            isinstance(applied, ClarificationCompositionPending)
                        )
                    session = applied.session
                    after, blockers = _field_values(session), _blockers(session)
                    if is_v3:
                        prompt = session.current_revision.prompt
                        prompt_requirement_ids = (
                            tuple(item.requirement_id for item in prompt.requirements)
                            if prompt is not None
                            else None
                        )
                        prompt_issue_kinds = (
                            tuple(item.kind.value for item in prompt.issues) if prompt is not None else ()
                        )
                        disclosure = any(
                            contribution.interpretation_provenance is not None
                            and contribution.interpretation_provenance.assumption_disclosure is not None
                            for contribution in session.effective_request.temporal_contributions
                        )
                        action, turn_safety, turn_behavioral = _v3_outcome_failures(
                            oracle=oracle,
                            answer_class=answer_class,
                            status=session.status.value,
                            before_blockers=tuple(before_blockers),
                            blockers=tuple(blockers),
                            before_values=before,
                            after_values=after,
                            prompt_requirement_ids=prompt_requirement_ids,
                            prompt_issue_kinds=prompt_issue_kinds,
                            prompt_message=prompt.message if prompt is not None else None,
                            disclosure_present=disclosure,
                            pending_retryable=pending_retryable,
                        )
                        safety_failures.extend(turn_safety)
                        behavioral_failures.extend(turn_behavioral)
                        requires_question = bool(oracle["question_intent"]["required"])
                        question_required_count += int(requires_question)
                        targeted_question_count += int(
                            requires_question and "question intent mismatch" not in turn_behavioral
                            and "question intent missing" not in turn_behavioral
                        )
                        if prompt is not None:
                            composition_sources[prompt.composition_source.value] += 1
                        turn_property_failures = _property_failures(
                            session, oracle.get("properties", {})
                        )
                        turn_value_failures = _value_failures(session, oracle.get("values", {}))
                        property_failures.extend(turn_property_failures)
                        value_failures.extend(turn_value_failures)
                        unnecessary_clarification = _v3_unnecessary_clarification(
                            action=action,
                            oracle=oracle,
                            behavioral_failures=turn_behavioral,
                        )
                        turn_metrics.append(
                            {
                                "expected_action": oracle["expected_action"],
                                "observed_action": action,
                                "disclosure_required": bool(oracle["disclosure"]["required"]),
                                "disclosure_missing": bool(oracle["disclosure"]["required"])
                                and not disclosure,
                                "materially_incorrect_assumption": bool(
                                    oracle["disclosure"]["required"]
                                )
                                and bool(turn_property_failures or turn_value_failures),
                                "unnecessary_clarification": unnecessary_clarification,
                            }
                        )
                        siblings = list(oracle.get("valid_siblings", ()))
                        valid_siblings_expected += len(siblings)
                        valid_siblings_retained += sum(
                            field in (set(before_blockers) - set(blockers)) for field in siblings
                        )
                        if session.status.value == "ready" and turns_ready is None:
                            turns_ready = ordinal
                        continue
                    resolved = set(before_blockers) - set(blockers)
                    must_resolve = set(oracle["must_resolve"])
                    must_remain = set(oracle["must_remain_blocked"])
                    protected = [field for field in oracle["protected_fields"] if before.get(field) != after.get(field)]
                    if must_resolve - resolved:
                        behavioral_failures.append("false blocking")
                    if not must_remain.issubset(blockers):
                        safety_failures.append("required blocker silently cleared")
                        if answer_class in {"ambiguous", "conflict"}:
                            behavioral_failures.append("incorrect acceptance")
                    if protected:
                        safety_failures.append("protected fields changed")
                    if session.status.value not in oracle["permitted_statuses"]:
                        behavioral_failures.append("status outside permitted envelope")
                    if (session.status.value == "ready") != (not blockers):
                        safety_failures.append("ready status does not exactly match blockers")
                    if session.status.value == "awaiting_answer":
                        prompt = session.current_revision.prompt
                        assert prompt is not None
                        expected = _blockers(session)
                        actual = [item.requirement_id for item in prompt.requirements]
                        if actual != expected:
                            safety_failures.append("prompt blocker coverage failed")
                        targeted, composition_source, manual_review = _targeted_assessment(session)
                        composition_sources[composition_source] += 1
                        manual_review_count += int(manual_review)
                    else:
                        targeted = False
                    if bool(oracle["question_required"]):
                        question_required_count += 1
                        targeted_question_count += int(targeted)
                        if not targeted:
                            behavioral_failures.extend(("targeted question missing", "generic repeat"))
                    turn_property_failures = _property_failures(session, oracle["properties"])
                    turn_value_failures = _value_failures(session, oracle.get("values", {}))
                    property_failures.extend(turn_property_failures)
                    value_failures.extend(turn_value_failures)
                    disclosure = any(
                        contribution.interpretation_provenance is not None
                        and contribution.interpretation_provenance.assumption_disclosure is not None
                        for contribution in session.effective_request.temporal_contributions
                    )
                    if oracle["disclosure_required"] and not disclosure:
                        safety_failures.append("accepted approximation has no disclosure")
                    unnecessary_clarification = (
                        session.status.value == "awaiting_answer"
                        and not must_remain
                        and not (must_resolve - resolved)
                        and not turn_property_failures
                        and not turn_value_failures
                    )
                    if unnecessary_clarification:
                        behavioral_failures.append("unnecessary clarification")
                    turn_metrics.append(
                        {
                            "disclosure_required": bool(oracle["disclosure_required"]),
                            "disclosure_missing": bool(oracle["disclosure_required"]) and not disclosure,
                            "materially_incorrect_assumption": bool(oracle["disclosure_required"])
                            and bool(turn_property_failures or turn_value_failures),
                            "unnecessary_clarification": unnecessary_clarification,
                        }
                    )
                    siblings = list(oracle.get("valid_siblings", ()))
                    valid_siblings_expected += len(siblings)
                    valid_siblings_retained += sum(field in resolved for field in siblings)
                    if session.status.value == "ready" and turns_ready is None:
                        turns_ready = ordinal
                if session.initial_result.model_dump(mode="json") != initial_snapshot:
                    safety_failures.append("initial snapshot mutated")
                if any(
                    item.date_window is not None and item.date_window.end < item.date_window.start
                    for item in session.effective_request.temporal_contributions
                ):
                    safety_failures.append("invalid temporal contribution")
            except Exception as exc:  # noqa: BLE001 - a probe failure must still yield private evidence.
                safety_failures.append(f"evaluator error: {type(exc).__name__}")
            finally:
                interpreter_usage, interpreter_traces = _safe_drain(interpreter, safety_failures)
                composer_usage, composer_traces = _safe_drain(composer, safety_failures)
                stages = {
                    "interpreter": _stage_summary(interpreter_usage, interpreter_traces),
                    "composer": _stage_summary(composer_usage, composer_traces),
                }
                repair_telemetry = _repair_telemetry(
                    interpreter_traces,
                    pending_retryable=pending_retryable_count,
                    pending_receiver=pending_receiver_count,
                    pending_composer=pending_composer_count,
                )
                if any(not bool(stage["reconciled"]) for stage in stages.values()):
                    safety_failures.append("model trace reconciliation failed")
                interpreter_errors = stages["interpreter"]["errors"]
                composer_errors = stages["composer"]["errors"]
                assert isinstance(interpreter_errors, int) and isinstance(composer_errors, int)
                if interpreter_errors > pending_receiver_count or composer_errors > pending_composer_count:
                    safety_failures.append("unhandled model trace error")
                record = {
                    "scenario": identifier,
                    "family": family,
                    "answer_class": answer_class,
                    "trial": trial,
                    "final_status": session.status.value,
                    "stop_reason": session.current_revision.stop_reason.value if session.current_revision.stop_reason else None,
                    "safety_passed": not safety_failures,
                    "behavioral_passed": not behavioral_failures and not property_failures and not value_failures,
                    "safety_failures": safety_failures,
                    "behavioral_failures": behavioral_failures,
                    "property_failures": property_failures,
                    "value_failures": value_failures,
                    "turn_metrics": turn_metrics,
                    "turns_to_ready": turns_ready,
                    "targeted_questions": {"required": question_required_count, "targeted": targeted_question_count},
                    "question_composition": {
                        "sources": dict(composition_sources),
                        "manual_review_required": manual_review_count,
                    },
                    "valid_siblings": {"expected": valid_siblings_expected, "retained": valid_siblings_retained},
                    "repair_telemetry": repair_telemetry,
                    "latency_seconds": perf_counter() - started,
                    "stages": stages,
                }
                write_eval_llm_trace(
                    trace_run_dir,
                    scenario={"id": identifier, "input": dict(case)},
                    record=record,
                    calls=[*interpreter_traces, *composer_traces],
                )
                trace_count += 1
                records.append(record)
    if _privacy_violations(records, path="live_behavior.records"):
        raise AssertionError("public live behavioral artifact leaked private content")
    family_counts = Counter(str(record["family"]) for record in records)
    class_counts = Counter(str(record["answer_class"]) for record in records)
    reasonable = [record for record in records if record["answer_class"] in {"reasonably_resolvable", "safely_assumable"}]
    must_ask = [record for record in records if record["answer_class"] in {"ambiguous", "conflict"}]
    false_blocks = sum("false blocking" in record["behavioral_failures"] for record in reasonable)
    total_stage: dict[str, dict[str, float | int]] = {
        stage: {
            key: sum(int(record["stages"][stage][key]) for record in records)
            for key in (
                "calls",
                "captured_calls",
                "missing_calls",
                "trace_count",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "errors",
            )
        }
        for stage in ("interpreter", "composer")
    }
    for stage, stage_totals in total_stage.items():
        stage_totals["reconciled_sessions"] = sum(
            bool(record["stages"][stage]["reconciled"]) for record in records
        )
        stage_totals["unreconciled_sessions"] = len(records) - int(
            stage_totals["reconciled_sessions"]
        )
        stage_totals["latency_seconds"] = sum(
            float(record["stages"][stage]["latency_seconds"]) for record in records
        )
    pair_results: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    by_id = {str(case["id"]): case for case in cases}
    for record in records:
        pair_id = by_id[str(record["scenario"])].get("pair_id")
        if isinstance(pair_id, str):
            pair_results[(pair_id, int(record["trial"]))].append(record)
    pair_passed = bool(pair_results) and all(
        any(item["answer_class"] in {"reasonably_resolvable", "safely_assumable"} and item["behavioral_passed"] for item in items)
        and any(item["answer_class"] == "ambiguous" and item["behavioral_passed"] for item in items)
        for items in pair_results.values()
    )
    equivalence_results: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        group = by_id[str(record["scenario"])].get("equivalence_group")
        if isinstance(group, str):
            equivalence_results[(group, int(record["trial"]))].append(record)
    paraphrase_passed = bool(equivalence_results) and all(
        len(items) >= 2 and all(item["behavioral_passed"] for item in items)
        for items in equivalence_results.values()
    )
    question_required = sum(int(record["targeted_questions"]["required"]) for record in records)
    generic_repeats = sum(
        int(record["targeted_questions"]["targeted"])
        < int(record["targeted_questions"]["required"])
        for record in records
    )
    incorrect = sum(
        any(
            "unsafe ambiguity acceptance" in failure
            or "forbidden outcome: unsafe_ambiguity_acceptance" in failure
            for failure in record["safety_failures"]
        )
        for record in must_ask
    )
    disclosure_required = sum(
        bool(turn["disclosure_required"])
        for record in records
        for turn in record["turn_metrics"]
    )
    disclosure_missing = sum(
        bool(turn["disclosure_missing"])
        for record in records
        for turn in record["turn_metrics"]
    )
    material_incorrect = sum(
        bool(turn["materially_incorrect_assumption"])
        for record in records
        for turn in record["turn_metrics"]
    )
    unnecessary = sum(
        bool(turn["unnecessary_clarification"])
        for record in records
        for turn in record["turn_metrics"]
    )
    stop_reasons = Counter(
        str(record["stop_reason"]) for record in records if record["stop_reason"] is not None
    )
    trial_rates = {
        trial: sum(
            bool(record["behavioral_passed"])
            for record in records
            if int(record["trial"]) == trial
        )
        / len(cases)
        for trial in range(1, trials + 1)
    }
    mean_rate = sum(trial_rates.values()) / len(trial_rates)
    variance = sum((rate - mean_rate) ** 2 for rate in trial_rates.values()) / len(trial_rates)
    slice_metrics = {
        key: {
            "sessions": len(items),
            "safety_failures": sum(not bool(item["safety_passed"]) for item in items),
            "behavioral_failures": sum(not bool(item["behavioral_passed"]) for item in items),
            "false_blocking": sum("false blocking" in item["behavioral_failures"] for item in items),
            "incorrect_acceptance": sum(
                any(
                    "unsafe ambiguity acceptance" in failure
                    or "forbidden outcome: unsafe_ambiguity_acceptance" in failure
                    for failure in item["safety_failures"]
                )
                for item in items
            ),
        }
        for key, items in (
            {
                f"family:{key}": [record for record in records if record["family"] == key]
                for key in family_counts
            }
            | {
                f"class:{key}": [record for record in records if record["answer_class"] == key]
                for key in class_counts
            }
        ).items()
    }
    holdout = "holdout" in fixture_path.parts
    mode = "pilot" if trials == 1 else "qualification"
    pool = "private_holdout" if holdout else "public"
    system_errors = sum(
        sum(failure.startswith("system error:") for failure in record["safety_failures"])
        for record in records
    )
    evaluator_errors = sum(
        sum(
            failure.startswith(("evaluator error:", "trace drain error:"))
            for failure in record["safety_failures"]
        )
        for record in records
    )
    artifact = {
        "schema_version": (
            "clarification_behavior_live_eval_v3" if is_v3 else "clarification_behavior_live_eval_v2"
        ),
        "fixture": {"sha256": sha256(raw).hexdigest(), "redacted": True, "scenario_count": len(cases), "private_holdout": holdout},
        "models": {"interpreter": interpreter_model, "composer": composer_model},
        "trials": trials,
        "generated_at": generated_at,
        "llm_trace": ({"mode": "all_calls_private", "sidecars": trace_count} if holdout else {"mode": "all_calls_private", "directory": str(trace_run_dir), "sidecars": trace_count}),
        **({} if holdout else {"records": records}),
        "summary": {
            "exact_safety_gate": {"passed": not any(not record["safety_passed"] for record in records), "failed": sum(not record["safety_passed"] for record in records)},
            "behavioral": {
                "false_blocking": {"count": false_blocks, "denominator": len(reasonable), "rate": false_blocks / len(reasonable) if reasonable else None, "eligible": bool(reasonable)},
                "incorrect_acceptance": {"count": incorrect, "denominator": len(must_ask), "rate": incorrect / len(must_ask) if must_ask else None, "eligible": bool(must_ask)},
                "targeted_question": {"required": sum(record["targeted_questions"]["required"] for record in records), "targeted": sum(record["targeted_questions"]["targeted"] for record in records)},
                "valid_sibling_retention": {"expected": sum(record["valid_siblings"]["expected"] for record in records), "retained": sum(record["valid_siblings"]["retained"] for record in records)},
                "property_envelopes": {
                    "failed_records": sum(bool(record["property_failures"]) for record in records),
                    "failure_count": sum(len(record["property_failures"]) for record in records),
                },
                "assumption_disclosure": {"required": disclosure_required, "missing": disclosure_missing},
                "materially_incorrect_assumption": {"count": material_incorrect, "denominator": disclosure_required},
                "unnecessary_clarification": {"count": unnecessary, "denominator": len(reasonable)},
                "generic_repeat_rate": {"count": generic_repeats, "denominator": question_required, "rate": generic_repeats / question_required if question_required else None, "eligible": bool(question_required)},
                "turns_to_ready": {"ready_sessions": sum(record["turns_to_ready"] is not None for record in records), "mean": (sum(int(record["turns_to_ready"]) for record in records if record["turns_to_ready"] is not None) / sum(record["turns_to_ready"] is not None for record in records) if any(record["turns_to_ready"] is not None for record in records) else None)},
                "paired_accept_ask": {"passed": pair_passed, "pairs": len({key for key, _ in pair_results}), "trial_runs": len(pair_results)},
                "paraphrase_consistency": {"passed": paraphrase_passed, "trial_runs": len(equivalence_results)},
                "repair_transitions": {
                    "first_pass_calls": sum(record["repair_telemetry"]["first_pass_calls"] for record in records),
                    "repair_calls": sum(record["repair_telemetry"]["repair_calls"] for record in records),
                    "repaired_workflows": sum(
                        record["repair_telemetry"]["repaired_workflows"] for record in records
                    ),
                    "pending_retryable": sum(record["repair_telemetry"]["pending_retryable"] for record in records),
                    "pending_receiver": sum(record["repair_telemetry"]["pending_receiver"] for record in records),
                    "pending_composer": sum(record["repair_telemetry"]["pending_composer"] for record in records),
                },
            },
            "metadata": {"mode": mode, "pool": pool, "execution": "live_openai", "evaluator_version": EVALUATOR_VERSION, "adapter_versions": {"interpreter": "openai_clarification_interpreter_v2", "composer": "openai_clarification_composer_v1"}, "scenario_distribution": dict(sorted(family_counts.items())), "answer_class_distribution": dict(sorted(class_counts.items())), "slice_metrics": slice_metrics, "stop_reasons": dict(sorted(stop_reasons.items())), "trial_variance": {"rates": trial_rates, "mean": mean_rate, "variance": variance}, "errors": {"model": total_stage["interpreter"]["errors"] + total_stage["composer"]["errors"], "system": system_errors, "evaluator": evaluator_errors}},
            "instrumentation": {
                "stages": total_stage,
                "totals": {
                    **{
                        key: sum(int(total_stage[stage][key]) for stage in total_stage)
                        for key in ("calls", "captured_calls", "missing_calls", "trace_count", "input_tokens", "output_tokens", "total_tokens", "errors", "reconciled_sessions", "unreconciled_sessions")
                    },
                    "latency_seconds": sum(
                        float(total_stage[stage]["latency_seconds"]) for stage in total_stage
                    ),
                },
            },
        },
    }
    if holdout:
        public_strings = _string_leaves(artifact)
        forbidden = [str(fixture_path), *(str(case["id"]) for case in cases), *(str(turn["text"]) for case in cases for turn in case["turns"])]
        if "records" in artifact or any(item in public_strings for item in forbidden):
            raise AssertionError("private live holdout artifact leaked fixture path, identifiers, or answer text")
    return artifact


__all__ = [
    "DEFAULT_LIVE_BEHAVIOR_FIXTURES",
    "DEFAULT_LIVE_BEHAVIOR_TRACE_DIR",
    "ClarificationBehaviorLiveFixtureError",
    "preflight_live_clarification_behavior_cases",
    "run_live_clarification_behavior_eval",
]
