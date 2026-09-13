"""Bounded live evaluation of the active one-way award clarification workflow.

The checked-in v1 fixture was a two-case operational smoke. The active v2
fixture is a fixed development corpus: its public artifact contains only typed
outcomes and boolean oracle results, while model-facing text remains in a
gitignored all-call sidecar.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml

from award_agent.clarification.controller import (
    ClarificationTransition,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.openai_composer import (
    OpenAIClarificationComposerConfig,
    OpenAIClarificationPromptComposer,
)
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpreterConfig,
)
from award_agent.domain import ClarificationAnswerCommand, RawRequest, RequestContext
from award_agent.intent.holidays import NagerHolidayProvider
from award_agent.intent.openai_interpreter import (
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    semantic_intent_adapter_contract_metadata,
)
from award_agent.intent.workflow import understand_request
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES = Path("evals/clarification/one_way_award_live_cases_v2.yaml")
DEFAULT_ONE_WAY_AWARD_LIVE_TRACE_DIR = Path("evals/clarification/traces-one-way-live")
_FIXTURE_CONTRACT_VERSION = "one_way_award_live_v2"
_FIXED_SCENARIO_IDS = frozenset(
    {
        "initial_one_way_ready",
        "missing_departure_is_resolved",
        "all_four_one_way_blockers_completed_in_three_turns",
        "return_only_answer_stops_with_scope_notice",
        "duration_only_answer_stops_with_scope_notice",
        "departure_and_return_stops_without_partial_mutation",
        "ambiguous_departure_retains_blocker",
        "unresolved_departure_retains_blocker",
        "cancellation_stops_session",
        "no_progress_stops_after_limit",
        "cash_only_initial_request_is_unsupported",
        "award_and_cash_initial_request_remains_award_eligible",
    }
)


class OneWayAwardLiveFixtureError(ValueError):
    """The checked-in live corpus does not match the active contract."""


def _semantic_contract_metadata() -> dict[str, str]:
    return semantic_intent_adapter_contract_metadata()


def _is_pending_initial_result(result: object) -> bool:
    outcome = getattr(result, "outcome", None)
    return getattr(outcome, "value", outcome) == "pending_retryable"


def _fixture_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _required_mapping(value: object, *, label: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise OneWayAwardLiveFixtureError(f"{label} has an invalid shape")
    return value


def _validate_turn_oracle(value: object, *, label: str) -> Mapping[str, Any]:
    expected = _required_mapping(
        value,
        label=label,
        keys={
            "status",
            "stop_reason",
            "blockers",
            "scope_notice_codes",
            "departure_state",
            "effective_request_unchanged",
        },
    )
    if expected["status"] not in {"ready", "awaiting_answer", "stopped"}:
        raise OneWayAwardLiveFixtureError(f"{label} has an invalid status")
    if expected["stop_reason"] is not None and not isinstance(expected["stop_reason"], str):
        raise OneWayAwardLiveFixtureError(f"{label} has an invalid stop reason")
    if not all(isinstance(expected[key], list) for key in ("blockers", "scope_notice_codes")):
        raise OneWayAwardLiveFixtureError(f"{label} has invalid list oracles")
    if not all(
        isinstance(item, str) and item
        for key in ("blockers", "scope_notice_codes")
        for item in expected[key]
    ):
        raise OneWayAwardLiveFixtureError(f"{label} has invalid list values")
    if expected["departure_state"] not in {"present", "absent", "unchanged"}:
        raise OneWayAwardLiveFixtureError(f"{label} has an invalid departure-state oracle")
    if not isinstance(expected["effective_request_unchanged"], bool):
        raise OneWayAwardLiveFixtureError(f"{label} has an invalid non-mutation oracle")
    return expected


def _load(path: Path) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    try:
        payload = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise OneWayAwardLiveFixtureError("unable to load one-way live fixture") from exc
    if not isinstance(payload, Mapping) or set(payload) != {
        "contract_version",
        "frozen",
        "scenarios",
    }:
        raise OneWayAwardLiveFixtureError("live fixture has an invalid top-level shape")
    scenarios = payload["scenarios"]
    if payload["contract_version"] != _FIXTURE_CONTRACT_VERSION or payload["frozen"] is not True:
        raise OneWayAwardLiveFixtureError(
            "live fixture must be a frozen one_way_award_live_v2 corpus"
        )
    if not isinstance(scenarios, list) or len(scenarios) != len(_FIXED_SCENARIO_IDS):
        raise OneWayAwardLiveFixtureError("live fixture has an invalid fixed scenario count")

    prepared: list[Mapping[str, Any]] = []
    identifiers: set[str] = set()
    for item in scenarios:
        if not isinstance(item, Mapping):
            raise OneWayAwardLiveFixtureError("live scenario must be a mapping")
        allowed = {"id", "input", "context", "expected", "answers"}
        if not set(item).issubset(allowed) or not {"id", "input", "context", "expected"}.issubset(
            item
        ):
            raise OneWayAwardLiveFixtureError("live scenario has an invalid shape")
        identifier = item["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise OneWayAwardLiveFixtureError("live scenarios require unique non-empty string IDs")
        if not isinstance(item["input"], str) or not item["input"].strip():
            raise OneWayAwardLiveFixtureError("live scenarios require a non-empty input")
        context = _required_mapping(
            item["context"],
            label=f"scenario {identifier!r} context",
            keys={"reference_date", "timezone"},
        )
        if not isinstance(context["reference_date"], str) or not isinstance(
            context["timezone"], str
        ):
            raise OneWayAwardLiveFixtureError("live scenario context values must be strings")
        try:
            date.fromisoformat(context["reference_date"])
        except ValueError as exc:
            raise OneWayAwardLiveFixtureError(
                "live scenario has an invalid reference date"
            ) from exc

        expected = _required_mapping(
            item["expected"],
            label=f"scenario {identifier!r} expected",
            keys={"initial", "turns", "composer_call_count"},
        )
        initial = _required_mapping(
            expected["initial"],
            label=f"scenario {identifier!r} initial oracle",
            keys={"action", "field", "unsupported_codes"},
        )
        if initial["action"] not in {"none", "ask", "unsupported"}:
            raise OneWayAwardLiveFixtureError("live scenario has an invalid initial action")
        if initial["field"] is not None and not isinstance(initial["field"], str):
            raise OneWayAwardLiveFixtureError("live scenario has an invalid initial field")
        if not isinstance(initial["unsupported_codes"], list) or not all(
            isinstance(code, str) and code for code in initial["unsupported_codes"]
        ):
            raise OneWayAwardLiveFixtureError("live scenario has invalid unsupported-code oracles")
        if not isinstance(expected["turns"], list) or not isinstance(
            expected["composer_call_count"], int
        ):
            raise OneWayAwardLiveFixtureError("live scenario has invalid turn or composer oracles")
        if expected["composer_call_count"] < 0:
            raise OneWayAwardLiveFixtureError("live scenario has a negative composer-call oracle")
        for turn_index, turn in enumerate(expected["turns"], start=1):
            _validate_turn_oracle(turn, label=f"scenario {identifier!r} turn {turn_index}")

        answers = item.get("answers", [])
        if not isinstance(answers, list) or not all(
            isinstance(answer, str) and answer.strip() for answer in answers
        ):
            raise OneWayAwardLiveFixtureError("live scenario answers must be non-empty strings")
        if len(answers) != len(expected["turns"]):
            raise OneWayAwardLiveFixtureError("live scenario answers and turn oracles must align")
        if initial["action"] == "ask":
            if not answers:
                raise OneWayAwardLiveFixtureError("asking scenarios require answer turns")
        elif answers:
            raise OneWayAwardLiveFixtureError("non-asking scenarios cannot have answer turns")
        identifiers.add(identifier)
        prepared.append(item)

    if identifiers != _FIXED_SCENARIO_IDS:
        raise OneWayAwardLiveFixtureError(
            "live fixture scenario IDs drifted from the fixed v2 corpus"
        )
    return prepared, {
        "path": str(path),
        "contract_version": _FIXTURE_CONTRACT_VERSION,
        "sha256": _fixture_sha256(path),
        "scenario_count": len(prepared),
    }


def preflight_one_way_award_live_cases(
    fixture_path: Path = DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES,
) -> tuple[Mapping[str, Any], ...]:
    """Validate the immutable active corpus before a paid live run."""

    scenarios, _metadata = _load(fixture_path)
    return tuple(scenarios)


def _drain(adapter: Any) -> tuple[dict[str, int] | None, list[dict[str, Any]]]:
    return adapter.take_usage(), adapter.take_call_traces()


def _blockers(session: Any) -> list[str]:
    prompt = session.current_revision.prompt
    return [] if prompt is None else [item.requirement_id for item in prompt.requirements]


def _scope_notice_codes(revision: Any) -> list[str]:
    outcome = revision.outcome
    return [] if outcome is None else [notice.code for notice in outcome.scope_notices]


def _departure_state(before: Any, after: Any, expected: str) -> bool:
    before_value = before.departure_window
    after_value = after.departure_window
    if expected == "present":
        return after_value is not None
    if expected == "absent":
        return after_value is None
    assert expected == "unchanged"
    return bool(after_value == before_value)


def _turn_record(
    transition: Any,
    *,
    before_effective: Any,
    expected: Mapping[str, Any],
    index: int,
) -> tuple[dict[str, Any], Any | None]:
    if not isinstance(transition, ClarificationTransition):
        # A pending model interpretation is a semantic non-pass, not an evaluator
        # crash. It retains no new revision and must never be confused with a stop.
        record = {
            "turn": index,
            "status": "pending",
            "stop_reason": None,
            "blockers": [],
            "scope_notice_codes": [],
            "checks": {
                "status": False,
                "stop_reason": expected["stop_reason"] is None,
                "blockers": False,
                "scope_notice_codes": expected["scope_notice_codes"] == [],
                "departure_state": _departure_state(
                    before_effective, before_effective, expected["departure_state"]
                ),
                "effective_request_unchanged": expected["effective_request_unchanged"] is True,
                "one_way_state": not hasattr(before_effective, "return_window")
                and not hasattr(before_effective, "interpreted_duration"),
            },
        }
        return record, None

    revision = transition.revision
    after_effective = revision.effective_request
    actual_status = revision.status.value
    actual_stop_reason = None if revision.stop_reason is None else revision.stop_reason.value
    actual_blockers = _blockers(transition.session)
    actual_scope_codes = _scope_notice_codes(revision)
    record = {
        "turn": index,
        "status": actual_status,
        "stop_reason": actual_stop_reason,
        "blockers": actual_blockers,
        "scope_notice_codes": actual_scope_codes,
        "checks": {
            "status": actual_status == expected["status"],
            "stop_reason": actual_stop_reason == expected["stop_reason"],
            "blockers": actual_blockers == expected["blockers"],
            "scope_notice_codes": actual_scope_codes == expected["scope_notice_codes"],
            "departure_state": _departure_state(
                before_effective, after_effective, expected["departure_state"]
            ),
            "effective_request_unchanged": (after_effective == before_effective)
            is expected["effective_request_unchanged"],
            "one_way_state": not hasattr(after_effective, "return_window")
            and not hasattr(after_effective, "interpreted_duration"),
        },
    }
    return record, transition.session


def run_one_way_award_live_eval(
    *,
    model: str = "gpt-5.6-luna",
    composer_model: str | None = None,
    interpreter_model: str | None = None,
    trials: int = 1,
    fixture_path: Path = DEFAULT_ONE_WAY_AWARD_LIVE_FIXTURES,
    trace_dir: Path = DEFAULT_ONE_WAY_AWARD_LIVE_TRACE_DIR,
) -> dict[str, Any]:
    """Run the fixed v2 corpus with no public request or answer text."""

    if trials < 1:
        raise ValueError("trials must be positive")
    scenarios, fixture = _load(fixture_path)
    semantic_contract = _semantic_contract_metadata()
    composer_model = composer_model or model
    interpreter_model = interpreter_model or model
    generated_at = datetime.now(UTC).isoformat()
    run_trace_dir = (
        trace_dir / f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    records: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        for scenario in scenarios:
            started = perf_counter()
            semantic_intent = OpenAISemanticIntentInterpreter(
                OpenAISemanticIntentConfig(model=model), capture_llm_io=True
            )
            composer = OpenAIClarificationPromptComposer(
                OpenAIClarificationComposerConfig(model=composer_model), capture_llm_io=True
            )
            interpreter = OpenAIClarificationAnswerInterpreter(
                OpenAIClarificationInterpreterConfig(model=interpreter_model), capture_llm_io=True
            )
            calls: list[dict[str, Any]] = []
            record: dict[str, Any] = {"id": scenario["id"], "trial": trial}
            composer_usage: dict[str, int] | None = None
            try:
                context = scenario["context"]
                result = understand_request(
                    RawRequest(
                        text=str(scenario["input"]),
                        context=RequestContext(
                            reference_date=date.fromisoformat(str(context["reference_date"])),
                            timezone=str(context["timezone"]),
                        ),
                    ),
                    semantic_intent,
                    NagerHolidayProvider(),
                )
                expected = scenario["expected"]
                initial_expected = expected["initial"]
                pending_initial = _is_pending_initial_result(result)
                initial: dict[str, Any]
                if pending_initial:
                    initial = {
                        "action": None,
                        "field": None,
                        "outcome": "pending_retryable",
                        "unsupported_codes": [],
                    }
                    initial_checks = {
                        "action": False,
                        "field": False,
                        "unsupported_codes": False,
                        "not_pending": False,
                        "pending_is_state_free": result.parsed_request is None
                        and result.clarification is None,
                    }
                else:
                    parsed = result.parsed_request
                    clarification = result.clarification
                    if parsed is None or clarification is None:
                        raise TypeError("completed initial result is missing request state")
                    initial = {
                        "action": clarification.action.value,
                        "field": clarification.field,
                        "outcome": "completed",
                        "unsupported_codes": [
                            item.code.value for item in parsed.unsupported_request_parts
                        ],
                    }
                    initial_checks = {
                        "action": initial["action"] == initial_expected["action"],
                        "field": initial["field"] == initial_expected["field"],
                        "unsupported_codes": initial["unsupported_codes"]
                        == initial_expected["unsupported_codes"],
                        "not_pending": True,
                    }
                turn_records: list[dict[str, Any]] = []
                session: Any | None = None
                answers = scenario.get("answers", [])
                if answers and not pending_initial and initial["action"] == "ask":
                    session = start_clarification(
                        result, session_id=f"live-{scenario['id']}-{trial}", composer=composer
                    )
                    for index, (answer, turn_expected) in enumerate(
                        zip(answers, expected["turns"], strict=True), start=1
                    ):
                        prompt = session.current_revision.prompt
                        if prompt is None:
                            turn_records.append(
                                {
                                    "turn": index,
                                    "status": "not_asked",
                                    "stop_reason": None,
                                    "blockers": [],
                                    "scope_notice_codes": [],
                                    "checks": {"status": False},
                                }
                            )
                            break
                        before_effective = session.current_revision.effective_request
                        transition = apply_clarification_answer(
                            session,
                            ClarificationAnswerCommand(
                                session_id=session.session_id,
                                expected_revision=session.current_revision.revision,
                                prompt_id=prompt.prompt_id,
                                message_id=f"{scenario['id']}-{trial}-answer-{index}",
                                text=str(answer),
                            ),
                            interpreter,
                            composer=composer,
                        )
                        turn_record, next_session = _turn_record(
                            transition,
                            before_effective=before_effective,
                            expected=turn_expected,
                            index=index,
                        )
                        turn_records.append(turn_record)
                        if next_session is None:
                            break
                        session = next_session

                # An unexpected initial action must fail every expected answer turn,
                # rather than turning the evaluation into a false initial-only pass.
                while len(turn_records) < len(expected["turns"]):
                    index = len(turn_records) + 1
                    turn_records.append(
                        {
                            "turn": index,
                            "status": "not_run",
                            "stop_reason": None,
                            "blockers": [],
                            "scope_notice_codes": [],
                            "checks": {"status": False},
                        }
                    )
                turn_checks = [all(turn["checks"].values()) for turn in turn_records]
                record.update(
                    {
                        "initial": initial,
                        "turns": turn_records,
                        "checks": {
                            "initial": all(initial_checks.values()),
                            "turns": all(turn_checks),
                            # Filled after adapter draining so the oracle is based on
                            # recorded attempts, not public result text.
                            "composer_call_count": False,
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001 - classify and continue a bounded live run.
                # Provider/model exception content can echo customer text. Keep it only
                # in the private all-call sidecar, never in this public artifact.
                record.update({"status": "error", "error_type": type(exc).__name__})
            for adapter in (semantic_intent, composer, interpreter):
                usage, adapter_calls = _drain(adapter)
                if adapter is composer:
                    composer_usage = usage
                calls.extend(adapter_calls)
            if "checks" in record:
                expected_composer_calls = scenario["expected"]["composer_call_count"]
                actual_composer_calls = 0 if composer_usage is None else composer_usage["calls"]
                record["composer_call_count"] = actual_composer_calls
                record["checks"]["composer_call_count"] = (
                    actual_composer_calls == expected_composer_calls
                )
                record["status"] = "passed" if all(record["checks"].values()) else "failed"
            record["call_count"] = len(calls)
            record["semantic_contract"] = semantic_contract
            record["latency_seconds"] = round(perf_counter() - started, 3)
            # Public JSON deliberately contains no scenario input or answer text. The
            # all-call trace is locally written under a gitignored directory.
            trace_path = write_eval_llm_trace(
                run_trace_dir, scenario=scenario, record=record, calls=calls
            )
            record["private_trace"] = {"path": str(trace_path), "calls": len(calls)}
            records.append(record)
    errors = sum(item["status"] == "error" for item in records)
    passed = sum(item["status"] == "passed" for item in records)
    return {
        "schema_version": "one_way_award_live_eval_v2",
        "generated_at": generated_at,
        "request_scope": "one_way_award_v1",
        "models": {
            "semantic_intent": model,
            "composer": composer_model,
            "interpreter": interpreter_model,
        },
        "semantic_contract": semantic_contract,
        "fixture": fixture,
        "trials": trials,
        "records": records,
        "summary": {
            "runs": len(records),
            "passed": passed,
            "failed": sum(item["status"] == "failed" for item in records),
            "errors": errors,
            "mechanically_completed": errors == 0,
        },
    }
