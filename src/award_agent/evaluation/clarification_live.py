"""Redacted live qualification runner for the clarification-answer model seam."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from math import ceil
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import yaml

from award_agent.clarification.blockers import collect_blocking_requirements
from award_agent.clarification.controller import apply_clarification_answer, start_clarification
from award_agent.clarification.openai_interpreter import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationInterpretationError,
    OpenAIClarificationInterpreterConfig,
)
from award_agent.domain import ClarificationAnswerCommand
from award_agent.evaluation.clarification_continuation import (
    _field_summary,
    _initial,
    _privacy_violations,
)
from award_agent.observability.llm_trace import write_eval_llm_trace

DEFAULT_LIVE_CLARIFICATION_FIXTURES = Path("evals/clarification/live_cases_v1.yaml")
DEFAULT_LIVE_CLARIFICATION_TRACE_DIR = Path("evals/clarification/traces")


class ClarificationLiveFixtureError(ValueError):
    """A live synthetic trajectory is malformed or would leak private data."""


def _required_terminal_correct(session_count: int) -> int:
    """Return the minimum terminal successes for the 95% live gate."""

    return ceil(0.95 * session_count)


def _load_cases(path: Path) -> tuple[list[Mapping[str, Any]], bytes]:
    try:
        raw = path.read_bytes()
        payload = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationLiveFixtureError("unable to load live clarification fixtures") from exc
    if not isinstance(payload, Mapping) or payload.get("contract_version") != "v1":
        raise ClarificationLiveFixtureError("live clarification fixtures must use contract_version v1")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 12:
        raise ClarificationLiveFixtureError("live qualification needs at least 12 scenarios")
    if _privacy_violations(payload):
        raise ClarificationLiveFixtureError("live clarification fixtures fail privacy lint")
    prepared: list[Mapping[str, Any]] = []
    ids: set[str] = set()
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            raise ClarificationLiveFixtureError("live scenario must be a mapping")
        identifier = scenario.get("id")
        turns = scenario.get("turns")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ClarificationLiveFixtureError("live scenario IDs must be unique non-empty strings")
        if not isinstance(turns, list) or not turns:
            raise ClarificationLiveFixtureError("live scenarios need one or more turns")
        ids.add(identifier)
        prepared.append(scenario)
    if not any(item.get("blind_target") is True for item in prepared):
        raise ClarificationLiveFixtureError("live qualification needs at least one blind_target scenario")
    if not any(item.get("qualification_target") is True for item in prepared):
        raise ClarificationLiveFixtureError("live qualification needs at least one qualification_target scenario")
    return prepared, raw


def _blockers(session: Any) -> list[str]:
    prompt = session.current_revision.prompt
    return [] if prompt is None else [item.requirement_id for item in prompt.requirements]


def _check(expect: Mapping[str, Any], session: Any) -> tuple[bool, bool, bool]:
    status_ok = session.status.value == expect.get("status")
    blockers_ok = _blockers(session) == expect.get("blockers")
    stop = session.current_revision.stop_reason
    stop_ok = "stop_reason" not in expect or (stop.value if stop else None) == expect["stop_reason"]
    fields_ok = all(_field_summary(session).get(key) == value for key, value in expect.get("fields", {}).items())
    return status_ok and blockers_ok and stop_ok and fields_ok, blockers_ok, fields_ok


def _prompt_coverage(session: Any) -> bool:
    revision = session.current_revision
    expected = [item.requirement_id for item in collect_blocking_requirements(session.effective_request)]
    actual = _blockers(session)
    return actual == expected if revision.status.value == "awaiting_answer" else not actual


_RESOLUTION_FIELDS = {
    "origin": {"origin"},
    "destination": {"destination"},
    "travelers": {"travelers"},
    "departure": {"departure", "return"},
    "return_or_duration": {"return", "duration_days"},
}


def run_live_clarification_eval(
    *,
    model: str,
    trials: int = 3,
    fixture_path: Path = DEFAULT_LIVE_CLARIFICATION_FIXTURES,
    trace_dir: Path = DEFAULT_LIVE_CLARIFICATION_TRACE_DIR,
) -> dict[str, Any]:
    """Run 12+ synthetic trajectories with private all-call trace sidecars."""

    if trials < 1:
        raise ValueError("trials must be positive")
    cases, raw = _load_cases(fixture_path)
    records: list[dict[str, Any]] = []
    generated_at = datetime.now(UTC).isoformat()
    trace_run_dir = trace_dir / (
        f"run-{generated_at.replace(':', '').replace('+', '-')}-{uuid4().hex[:8]}"
    )
    trace_count = 0
    for trial in range(1, trials + 1):
        for scenario in cases:
            identifier = str(scenario["id"])
            session = start_clarification(_initial(scenario), session_id=f"live-{identifier}-{trial}")
            initial_snapshot = deepcopy(session.initial_result.model_dump(mode="python"))
            adapter = OpenAIClarificationAnswerInterpreter(
                OpenAIClarificationInterpreterConfig(model=model), capture_llm_io=True
            )
            run_started = perf_counter()
            system_error = False
            checks: list[bool] = []
            blocker_checks: list[bool] = []
            field_checks: list[bool] = []
            prompt_checks: list[bool] = []
            resolution_expected: list[str] = []
            resolution_linked: list[str] = []
            for turn_number, turn in enumerate(scenario["turns"], start=1):
                assert isinstance(turn, Mapping)
                current = session.current_revision
                if current.prompt is None:
                    system_error = True
                    break
                expected_before = _blockers(session)
                command = ClarificationAnswerCommand(
                    session_id=session.session_id,
                    expected_revision=current.revision,
                    prompt_id=current.prompt.prompt_id,
                    message_id=f"{identifier}-{trial}-{turn_number}",
                    text=str(turn["text"]),
                )
                before = _field_summary(session)
                try:
                    session = apply_clarification_answer(session, command, adapter).session
                except (OpenAIClarificationInterpretationError, ValueError):
                    system_error = True
                    break
                expect = turn["expect"]
                assert isinstance(expect, Mapping)
                check, blockers_ok, fields_ok = _check(expect, session)
                checks.append(check)
                blocker_checks.append(blockers_ok)
                field_checks.append(fields_ok)
                prompt_checks.append(_prompt_coverage(session))
                expected_after = list(expect.get("blockers", []))
                resolution_expected.extend(
                    requirement for requirement in expected_before if requirement not in expected_after
                )
                outcome = session.current_revision.outcome
                if outcome is not None:
                    resolution_linked.extend(
                        requirement
                        for amendment in outcome.accepted_amendments
                        for requirement in amendment.requirement_ids
                    )
                expected_fields = set(expect.get("fields", {}))
                expected_fields.update(
                    field
                    for requirement in expected_before
                    if requirement not in expected_after
                    for field in _RESOLUTION_FIELDS.get(requirement, set())
                )
                changed = {
                    key
                    for key, value in _field_summary(session).items()
                    if before.get(key) != value
                }
                # Any accepted amendment can cause deterministic temporal
                # projection to materialize a return date from a retained
                # departure/duration pair. It is derived state, not a model
                # mutation, and remains provenance-checked by the controller.
                if not changed.issubset(expected_fields | {"return"}):
                    system_error = True
                    break
                if session.status.value != "awaiting_answer" and turn_number != len(scenario["turns"]):
                    system_error = True
                    break
            usage = adapter.take_usage() or {
                "calls": 0,
                "captured_calls": 0,
                "missing_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
            final_expect = scenario["turns"][-1]["expect"]
            assert isinstance(final_expect, Mapping)
            terminal_ok, _, _ = _check(final_expect, session)
            terminal_ok = terminal_ok and session.status.value in {"ready", "stopped"} and not system_error
            record = {
                    "scenario": identifier,
                    "trial": trial,
                    "terminal_correct": terminal_ok,
                    "processed_turns": len(checks),
                    "turns_correct": sum(checks),
                    "turns_total": len(scenario["turns"]),
                    "exact_blockers": sum(blocker_checks),
                    "field_checks": sum(field_checks),
                    "prompt_coverage": sum(prompt_checks),
                    "resolution_expected": resolution_expected,
                    "resolution_linked": resolution_linked,
                    "system_error": system_error,
                    "initial_snapshot_unchanged": session.initial_result.model_dump(mode="python") == initial_snapshot,
                    "final_status": session.status.value,
                    "stop_reason": (
                        session.current_revision.stop_reason.value
                        if session.current_revision.stop_reason
                        else None
                    ),
                    "latency_seconds": perf_counter() - run_started,
                    "usage": usage,
                    "template_outcomes": [
                        {
                            "target": (
                                "departure"
                                if contribution.kind.value == "departure_window"
                                else "return_or_duration"
                            ),
                            "template_id": contribution.template_provenance.template_id,
                        }
                        for contribution in session.effective_request.temporal_contributions
                        if contribution.template_provenance is not None
                    ],
            }
            call_traces = adapter.take_call_traces()
            # Always write trace sidecars. They are private/gitignored and never
            # become part of the public redacted artifact.
            write_eval_llm_trace(
                trace_run_dir,
                scenario={"id": identifier},
                record=record,
                calls=call_traces,
            )
            trace_count += 1
            records.append(record)
    if _privacy_violations(records, path="live_artifact.records"):
        raise AssertionError("live artifact privacy lint failed")
    terminal_correct = sum(bool(record["terminal_correct"]) for record in records)
    blocker_total = sum(int(record["turns_total"]) for record in records)
    blockers_exact = sum(int(record["exact_blockers"]) for record in records)
    unauthorized = sum(not bool(record["initial_snapshot_unchanged"]) for record in records)
    system_errors = sum(bool(record["system_error"]) for record in records)
    stop_reasons = Counter(str(record["stop_reason"]) for record in records if record["stop_reason"])
    calls = sum(int(record["usage"]["calls"]) for record in records)
    expected_resolutions = [requirement for record in records for requirement in record["resolution_expected"]]
    linked_resolutions = [requirement for record in records for requirement in record["resolution_linked"]]
    matched_resolutions = sum(
        requirement in record["resolution_expected"]
        for record in records
        for requirement in record["resolution_linked"]
    )
    prompt_coverage_total = sum(int(record["processed_turns"]) for record in records)
    prompt_coverage_passed = sum(int(record["prompt_coverage"]) for record in records)
    required_terminal_correct = _required_terminal_correct(len(records))
    target_template: dict[tuple[str, str], dict[str, int]] = {}
    for record in records:
        template_outcomes = record["template_outcomes"]
        assert isinstance(template_outcomes, list)
        for item in template_outcomes:
            assert isinstance(item, Mapping)
            key = (str(item["target"]), str(item["template_id"]))
            metric = target_template.setdefault(key, {"seen": 0, "terminal_correct": 0})
            metric["seen"] += 1
            metric["terminal_correct"] += int(bool(record["terminal_correct"]))
    blind_trials = {
        str(scenario["id"]): [
            bool(record["terminal_correct"])
            for record in records
            if record["scenario"] == scenario["id"]
        ]
        for scenario in cases
        if scenario.get("blind_target") is True
    }
    blind_target_gate = {
        identifier: {"passed": all(outcomes) and len(outcomes) == trials, "passed_trials": sum(outcomes), "trials": len(outcomes)}
        for identifier, outcomes in blind_trials.items()
    }
    qualification_trials = {
        str(scenario["id"]): [
            bool(record["terminal_correct"])
            for record in records
            if record["scenario"] == scenario["id"]
        ]
        for scenario in cases
        if scenario.get("qualification_target") is True
    }
    qualification_target_gate = {
        identifier: {"passed": all(outcomes) and len(outcomes) == trials, "passed_trials": sum(outcomes), "trials": len(outcomes)}
        for identifier, outcomes in qualification_trials.items()
    }
    return {
        "schema_version": "clarification_live_eval_v1",
        "fixture": {"path": str(fixture_path), "sha256": sha256(raw).hexdigest(), "redacted": True},
        "model": model,
        "trials": trials,
        "generated_at": generated_at,
        "llm_trace": {
            "mode": "all_calls",
            "directory": str(trace_run_dir),
            "case_count": trace_count,
        },
        "records": records,
        "summary": {
            "sessions": len(records),
            "terminal_correct": terminal_correct,
            "exact_remaining_blockers": {"passed": blockers_exact, "total": blocker_total, "rate": blockers_exact / blocker_total},
            "unauthorized_mutations": unauthorized,
            "system_errors": system_errors,
            "prompt_coverage": {
                "passed": prompt_coverage_passed,
                "total": prompt_coverage_total,
                "rate": prompt_coverage_passed / prompt_coverage_total if prompt_coverage_total else 1.0,
            },
            "requirement_resolution": {
                "expected": len(expected_resolutions),
                "linked": len(linked_resolutions),
                "matched": matched_resolutions,
                "precision": matched_resolutions / len(linked_resolutions) if linked_resolutions else 1.0,
                "recall": matched_resolutions / len(expected_resolutions) if expected_resolutions else 1.0,
            },
            "per_target_template": {
                f"{target}:{template_id}": {
                    "target": target,
                    "template_id": template_id,
                    **metric,
                    "rate": metric["terminal_correct"] / metric["seen"] if metric["seen"] else 0.0,
                }
                for (target, template_id), metric in sorted(target_template.items())
            },
            "blind_target_gate": blind_target_gate,
            "qualification_target_gate": qualification_target_gate,
            "convergence": {
                "within_turn_budget": sum(
                    bool(record["terminal_correct"])
                    and int(record["processed_turns"]) <= 6
                    for record in records
                ),
                "sessions": len(records),
            },
            "stop_reasons": dict(sorted(stop_reasons.items())),
            "instrumentation": {
                "calls": calls,
                "latency_seconds": sum(float(record["latency_seconds"]) for record in records),
                "input_tokens": sum(int(record["usage"]["input_tokens"]) for record in records),
                "output_tokens": sum(int(record["usage"]["output_tokens"]) for record in records),
            },
            "live_gate": {
                "passed": len(records) >= 36
                and terminal_correct >= required_terminal_correct
                and blockers_exact / blocker_total >= 0.95
                and unauthorized == 0
                and system_errors == 0
                and all(item["passed"] for item in blind_target_gate.values())
                and all(item["passed"] for item in qualification_target_gate.values()),
                # No aggregate threshold may mask a blind-target miss.
                # Kept alongside the numeric gates for an explicit artifact audit.
                "blind_targets_passed": all(
                    item["passed"] for item in blind_target_gate.values()
                ),
                # The listed core selector trajectories must each be 3/3;
                # aggregate success cannot mask a targeted regression.
                "qualification_targets_passed": all(
                    item["passed"] for item in qualification_target_gate.values()
                ),
                "required_terminal_correct": required_terminal_correct,
                "required_exact_blocker_rate": 0.95,
            },
        },
    }


__all__ = [
    "DEFAULT_LIVE_CLARIFICATION_FIXTURES",
    "DEFAULT_LIVE_CLARIFICATION_TRACE_DIR",
    "ClarificationLiveFixtureError",
    "run_live_clarification_eval",
]
