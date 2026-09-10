"""Deterministic offline qualification for ADR 0011 clarification sessions.

The checked-in YAML is intentionally synthetic: it contains only fixture labels,
short answer text, and declarative typed-amendment instructions.  A local
scripted interpreter turns those instructions into the public answer-interpreter
contract, so every trajectory still executes the public continuation controller
and its normal grounding, temporal, reducer, replay, and freshness checks.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, cast

import yaml

import award_agent.clarification.controller as controller_module
import award_agent.clarification.reducer as reducer_module
from award_agent.clarification.blockers import collect_blocking_requirements
from award_agent.clarification.controller import (
    ClarificationCommandError,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.clarification.interpreter import (
    ClarificationAnswerInterpretation,
    ClarificationAnswerInterpreterInput,
    ClarificationInterpretationError,
)
from award_agent.clarification.temporal_templates import ClarificationTemporalTemplateSelection
from award_agent.domain import (
    AmendmentTarget,
    ClarificationAction,
    ClarificationAnswerCommand,
    ClarificationDecision,
    ClarificationSession,
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
    TypedAmendment,
    UnknownField,
    UnknownReason,
)

DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES = Path("evals/clarification/cases_v1.yaml")
DEFAULT_FIXTURE_REFERENCE_DATE = date(2026, 9, 8)


class ClarificationContinuationFixtureError(ValueError):
    """The public, offline continuation fixture is malformed or unsafe."""


@dataclass(frozen=True)
class PreparedClarificationContinuationCase:
    identifier: str
    payload: Mapping[str, Any]


def _projection_fingerprint(projection: Mapping[str, Any]) -> str:
    """Stable oracle fingerprint for a redacted, complete session projection."""

    encoded = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _load(path: Path) -> tuple[Mapping[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        loaded = yaml.safe_load(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise ClarificationContinuationFixtureError(f"unable to load continuation fixture {path}") from exc
    if not isinstance(loaded, Mapping):
        raise ClarificationContinuationFixtureError("continuation fixture root must be a mapping")
    return loaded, raw


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ClarificationContinuationFixtureError(f"{label} must be a non-empty string")
    return value


def _validate_accepted_payload_oracle(item: Mapping[str, Any]) -> None:
    """Require a target-specific normalized typed payload in every oracle."""

    target = item["target"]
    payload = item["payload"]
    assert isinstance(payload, Mapping)
    if target in {AmendmentTarget.ORIGIN.value, AmendmentTarget.DESTINATION.value}:
        if set(payload) != {"locations"} or not isinstance(payload["locations"], list) or not payload["locations"]:
            raise ClarificationContinuationFixtureError("location acceptance payload must contain non-empty locations")
        for location in payload["locations"]:
            if not isinstance(location, Mapping) or set(location) != {"kind", "value"}:
                raise ClarificationContinuationFixtureError("location acceptance payload must use kind and value")
            _require_string(location["kind"], "accepted location kind")
            _require_string(location["value"], "accepted location value")
        return
    if target == AmendmentTarget.TRAVELERS.value:
        if set(payload) != {"travelers"} or not isinstance(payload["travelers"], int) or payload["travelers"] < 1:
            raise ClarificationContinuationFixtureError("traveler acceptance payload must contain a positive travelers value")
        return
    if target in {
        AmendmentTarget.DEPARTURE.value,
        AmendmentTarget.RETURN_OR_DURATION.value,
        AmendmentTarget.CONFLICTING_DATES.value,
    }:
        if set(payload) != {"temporal_text"}:
            raise ClarificationContinuationFixtureError("temporal acceptance payload must contain temporal_text")
        _require_string(payload["temporal_text"], "accepted temporal text")
        return
    raise ClarificationContinuationFixtureError(f"unsupported accepted amendment target {target!r}")


def _validate_template_provenance_oracle(item: Mapping[str, Any]) -> None:
    """Require an exact registry provenance oracle for template amendments."""

    is_template = item.get("template_candidate") is not None
    provenance = item.get("provenance")
    if not is_template:
        if provenance is not None:
            raise ClarificationContinuationFixtureError(
                "legacy amendment oracle cannot declare template provenance"
            )
        return
    _require_string(item["template_candidate"], "template candidate")
    if not isinstance(provenance, Mapping):
        raise ClarificationContinuationFixtureError(
            "template amendment oracle needs provenance"
        )
    required = {"template_id", "registry_version", "candidate_id", "dependency_candidate_ids"}
    if set(provenance) != required:
        raise ClarificationContinuationFixtureError(
            "template provenance oracle must contain exact registry fields"
        )
    _require_string(provenance["template_id"], "template provenance template_id")
    _require_string(provenance["registry_version"], "template provenance registry_version")
    _require_string(provenance["candidate_id"], "template provenance candidate_id")
    dependencies = provenance["dependency_candidate_ids"]
    if not isinstance(dependencies, list) or not all(
        isinstance(candidate_id, str) and candidate_id for candidate_id in dependencies
    ):
        raise ClarificationContinuationFixtureError(
            "template provenance dependency_candidate_ids must be a list of strings"
        )
    if provenance["candidate_id"] in dependencies or len(dependencies) != len(set(dependencies)):
        raise ClarificationContinuationFixtureError(
            "template provenance dependencies must be unique and exclude the candidate"
        )


def _privacy_violations(value: object, *, path: str = "fixture") -> list[str]:
    """Keep the public corpus synthetic and free of accidental raw payloads."""

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


def preflight_clarification_continuation_cases(
    fixture_path: Path = DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES,
) -> tuple[PreparedClarificationContinuationCase, ...]:
    """Validate closed, redacted fixture shape before any controller execution."""

    payload, _ = _load(fixture_path)
    if payload.get("contract_version") != "v1":
        raise ClarificationContinuationFixtureError("continuation fixture contract_version must be v1")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 16:
        raise ClarificationContinuationFixtureError("continuation fixture needs at least 16 scenarios")
    violations = _privacy_violations(payload)
    if violations:
        raise ClarificationContinuationFixtureError(
            f"continuation fixture fails privacy lint at {sorted(violations)!r}"
        )
    prepared: list[PreparedClarificationContinuationCase] = []
    identifiers: set[str] = set()
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, Mapping):
            raise ClarificationContinuationFixtureError(f"scenarios[{index}] must be a mapping")
        identifier = _require_string(scenario.get("id"), f"scenarios[{index}].id")
        if identifier in identifiers:
            raise ClarificationContinuationFixtureError(f"duplicate continuation scenario {identifier!r}")
        identifiers.add(identifier)
        if not isinstance(scenario.get("initial_unknowns"), list):
            raise ClarificationContinuationFixtureError(f"scenario {identifier!r} needs initial_unknowns")
        projection_fingerprint = scenario.get("final_projection_sha256")
        if not isinstance(projection_fingerprint, str) or len(projection_fingerprint) != 64:
            raise ClarificationContinuationFixtureError(
                f"scenario {identifier!r} needs a 64-character final_projection_sha256 oracle"
            )
        try:
            int(projection_fingerprint, 16)
        except ValueError as exc:
            raise ClarificationContinuationFixtureError(
                f"scenario {identifier!r} final_projection_sha256 must be hexadecimal"
            ) from exc
        turns = scenario.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ClarificationContinuationFixtureError(f"scenario {identifier!r} needs turns")
        for turn_index, turn in enumerate(turns):
            if not isinstance(turn, Mapping):
                raise ClarificationContinuationFixtureError(
                    f"scenario {identifier!r} turn {turn_index} must be a mapping"
                )
            _require_string(turn.get("kind", "answer"), f"scenario {identifier!r} turn kind")
            _require_string(turn.get("text"), f"scenario {identifier!r} turn text")
            expect = turn.get("expect")
            if not isinstance(expect, Mapping):
                raise ClarificationContinuationFixtureError(
                    f"scenario {identifier!r} turn {turn_index} needs expect"
                )
            if "error" in expect:
                if set(expect) != {"error"}:
                    raise ClarificationContinuationFixtureError(
                        f"error oracle for {identifier!r} turn {turn_index} must assert only error"
                    )
            else:
                required_oracle_keys = {"status", "blockers"}
                missing = required_oracle_keys - set(expect)
                if missing:
                    raise ClarificationContinuationFixtureError(
                        f"scenario {identifier!r} turn {turn_index} misses oracle keys {sorted(missing)!r}"
                    )
                if not isinstance(expect["blockers"], list):
                    raise ClarificationContinuationFixtureError("blocker oracle must be an ordered list")
                if "fields" in expect and not isinstance(expect["fields"], Mapping):
                    raise ClarificationContinuationFixtureError("effective field oracle must be a mapping")
                kind = turn.get("kind", "answer")
                if kind not in {"replay", "replay_different_text"}:
                    accepted = expect.get("accepted")
                    if not isinstance(accepted, list):
                        raise ClarificationContinuationFixtureError(
                            f"scenario {identifier!r} turn {turn_index} needs an explicit accepted oracle"
                        )
                    for accepted_index, item in enumerate(accepted):
                        if not isinstance(item, Mapping):
                            raise ClarificationContinuationFixtureError("accepted amendment oracle item must be a mapping")
                        required_accepted_keys = {"ordinal", "target", "requirements", "is_correction", "payload"}
                        missing_accepted_keys = required_accepted_keys - set(item)
                        if missing_accepted_keys:
                            raise ClarificationContinuationFixtureError(
                                "accepted amendment oracle misses "
                                f"{sorted(missing_accepted_keys)!r} at {identifier!r} turn {turn_index} item {accepted_index}"
                            )
                        if not isinstance(item["ordinal"], int) or item["ordinal"] < 1:
                            raise ClarificationContinuationFixtureError("accepted amendment ordinal must be a positive integer")
                        _require_string(item["target"], "accepted amendment target")
                        if not isinstance(item["requirements"], list) or not all(
                            isinstance(requirement, str) for requirement in item["requirements"]
                        ):
                            raise ClarificationContinuationFixtureError("accepted amendment requirements must be strings")
                        if not isinstance(item["is_correction"], bool):
                            raise ClarificationContinuationFixtureError("accepted amendment is_correction must be boolean")
                        if not isinstance(item["payload"], Mapping):
                            raise ClarificationContinuationFixtureError("accepted amendment payload must be a mapping")
                        _validate_accepted_payload_oracle(item)
                        _validate_template_provenance_oracle(item)
        prepared.append(PreparedClarificationContinuationCase(identifier, scenario))
    return tuple(prepared)


def _span(message_id: str, text: str, fragment: str) -> MessageSpan:
    start = text.find(fragment)
    if start < 0:
        raise ClarificationContinuationFixtureError(
            f"scripted amendment fragment {fragment!r} is not in answer text"
        )
    return MessageSpan(message_id=message_id, start=start, end=start + len(fragment), text=fragment)


class _ScriptedInterpreter:
    def __init__(self, turn: Mapping[str, Any]) -> None:
        self._turn = turn
        self.calls = 0

    def interpret(self, input: ClarificationAnswerInterpreterInput) -> ClarificationAnswerInterpretation:
        self.calls += 1
        fault = self._turn.get("fault")
        if fault == "interpreter":
            raise RuntimeError("scripted interpreter failure")
        amendments: list[TypedAmendment] = []
        for ordinal, instruction in enumerate(self._turn.get("amendments", []), start=1):
            if not isinstance(instruction, Mapping):
                raise ClarificationContinuationFixtureError("amendment instruction must be a mapping")
            target = AmendmentTarget(_require_string(instruction.get("target"), "amendment.target"))
            fragment = _require_string(instruction.get("fragment"), "amendment.fragment")
            span = _span(input.message_id, input.text, fragment)
            if fault == "grounding":
                span = MessageSpan(message_id=input.message_id, start=0, end=1, text="!")
            amendment_id = f"{input.message_id}:a{ordinal}"
            correction = bool(instruction.get("correction", False))
            requirement_ids = tuple(instruction.get("requirements", ()))
            if target in {AmendmentTarget.ORIGIN, AmendmentTarget.DESTINATION}:
                location_kind = LocationKind(instruction.get("location_kind", "airport"))
                value = _require_string(instruction.get("value"), "amendment.value")
                amendments.append(
                    LocationAmendment(
                        amendment_id=amendment_id,
                        target=target,
                        requirement_ids=requirement_ids,
                        span=span,
                        is_correction=correction,
                        locations=(LocationRef(kind=location_kind, value=value, raw_text=fragment),),
                    )
                )
            elif target is AmendmentTarget.TRAVELERS:
                amendments.append(
                    TravelersAmendment(
                        amendment_id=amendment_id,
                        target=target,
                        requirement_ids=requirement_ids,
                        span=span,
                        is_correction=correction,
                        travelers=int(instruction["travelers"]),
                    )
                )
            else:
                amendments.append(
                    TemporalAmendment(
                        amendment_id=amendment_id,
                        target=target,
                        requirement_ids=requirement_ids,
                        span=span,
                        is_correction=correction,
                        temporal_text=fragment,
                    )
                )
        rejected: list[RejectedFragment] = []
        for fragment in self._turn.get("rejected", []):
            if not isinstance(fragment, Mapping):
                raise ClarificationContinuationFixtureError("rejected instruction must be a mapping")
            rejected.append(
                RejectedFragment(
                    span=_span(input.message_id, input.text, _require_string(fragment.get("fragment"), "rejected.fragment")),
                    reason=RejectedFragmentReason(_require_string(fragment.get("reason"), "rejected.reason")),
                    detail=_require_string(fragment.get("detail", "scripted rejection"), "rejected.detail"),
                )
                )
        selection_payload = self._turn.get("template_selection")
        expected_templates = self._turn.get("expect", {}).get("accepted", ())
        if selection_payload is None and any(
            isinstance(item, Mapping) and item.get("template_candidate") is not None
            for item in expected_templates
        ):
            raise ClarificationContinuationFixtureError(
                "template_selection is required for a scripted template acceptance"
            )
        if selection_payload is None:
            return ClarificationAnswerInterpretation(
                amendments=tuple(amendments),
                rejected_fragments=tuple(rejected),
                temporal_template_selection=ClarificationTemporalTemplateSelection(complete=True),
            )
        if not isinstance(selection_payload, Mapping):
            raise ClarificationContinuationFixtureError("template_selection must be a mapping")
        selected = selection_payload.get("selected", ())
        unresolved = selection_payload.get("unresolved", ())
        if not isinstance(selected, list) or not all(isinstance(item, Mapping) for item in selected):
            raise ClarificationContinuationFixtureError(
                "template_selection.selected must be a list of handle/fragment mappings"
            )
        if not isinstance(unresolved, list) or not all(isinstance(item, Mapping) for item in unresolved):
            raise ClarificationContinuationFixtureError(
                "template_selection.unresolved must be a list of fragment mappings"
            )
        from award_agent.clarification.temporal_templates import (
            ClarificationTemporalTemplateBinding,
            ClarificationTemporalTemplateUnresolved,
        )
        return ClarificationAnswerInterpretation(
            amendments=tuple(amendments),
            rejected_fragments=tuple(rejected),
            temporal_template_selection=ClarificationTemporalTemplateSelection(
                selected=tuple(
                    ClarificationTemporalTemplateBinding(
                        template_handle=_require_string(item.get("handle"), "template_selection.selected.handle"),
                        span=_span(input.message_id, input.text, _require_string(item.get("fragment"), "template_selection.selected.fragment")),
                        weekday=(
                            _require_string(item.get("weekday"), "template_selection.selected.weekday")
                            if item.get("weekday") is not None
                            else None
                        ),
                    )
                    for item in selected
                ),
                unresolved=tuple(
                    ClarificationTemporalTemplateUnresolved(
                        span=_span(input.message_id, input.text, _require_string(item.get("fragment"), "template_selection.unresolved.fragment")),
                        requirement_ids=tuple(
                            _require_string(value, "template_selection.unresolved.requirement_ids item")
                            for value in item.get("requirement_ids", ())
                        ),
                        reason=cast(
                            "Literal['ambiguous', 'unsupported']",
                            _require_string(
                                item.get("reason", "unsupported"),
                                "template_selection.unresolved.reason",
                            ),
                        ),
                    )
                    for item in unresolved
                ),
                complete=True,
            ),
        )


def _initial(case: Mapping[str, Any]) -> RequestUnderstandingResult:
    unknowns = [
        UnknownField(field=_require_string(field, "initial_unknowns item"), reason=UnknownReason.MISSING, detail="fixture unknown")
        for field in case["initial_unknowns"]
    ]
    reference_date = date.fromisoformat(str(case.get("reference_date", DEFAULT_FIXTURE_REFERENCE_DATE)))
    context = RequestContext(reference_date=reference_date, timezone="America/Los_Angeles")
    origin = case.get("initial_origin")
    destination = case.get("initial_destination")
    departure = case.get("initial_departure")
    duration_days = case.get("initial_duration_days")
    departure_window = (
        DateWindow(start=date.fromisoformat(str(departure)), end=date.fromisoformat(str(departure)),
                   precision=DateWindowPrecision.EXACT, raw_text="fixture date")
        if departure else None
    )
    duration = (
        InterpretedDuration(raw_text="fixture duration", minimum_days=int(duration_days), maximum_days=int(duration_days))
        if duration_days else None
    )
    parsed = ParsedRequest(
        raw_text="Synthetic offline clarification fixture.", context=context,
        travelers=case.get("initial_travelers"),
        origins=[LocationRef(kind=LocationKind.AIRPORT, value=str(origin), raw_text=str(origin))] if origin else [],
        destinations=[LocationRef(kind=LocationKind.AIRPORT, value=str(destination), raw_text=str(destination))] if destination else [],
        departure_expression=None, return_expression=None,
        return_window=None, duration=None, cabins=[], search_modes=[], date_flexibility=[],
        repositioning_allowed=None, hard_constraints=[], unknowns=unknowns,
        conflicts=[
            Conflict(code=_require_string(code, "initial_conflicts item"), fields=["dates"], detail="fixture conflict")
            for code in case.get("initial_conflicts", [])
        ],
        departure_window=departure_window,
        date_resolution=DateResolutionProposal(interpreted_duration=duration) if duration else None,
    )
    return RequestUnderstandingResult(
        parsed_request=parsed,
        clarification=ClarificationDecision(action=ClarificationAction.ASK, field="origin", question="Synthetic."),
    )


def _field_summary(session: ClarificationSession) -> dict[str, object]:
    effective = session.effective_request
    return {
        "origin": effective.origins[0].value if effective.origins else None,
        "destination": effective.destinations[0].value if effective.destinations else None,
        "travelers": effective.travelers,
        "departure": effective.departure_window.start.isoformat() if effective.departure_window else None,
        "return": effective.return_window.start.isoformat() if effective.return_window else None,
        "duration_days": effective.interpreted_duration.minimum_days if effective.interpreted_duration else None,
    }


def _semantic_projection(session: ClarificationSession) -> dict[str, object]:
    """Effective-request comparison that intentionally excludes turn provenance."""

    summary = _projection_summary(session)
    return {
        key: summary[key]
        for key in (
            "travelers", "origins", "destinations", "departure_window", "return_window",
            "interpreted_duration", "unknowns", "conflicts",
        )
    }


def _blockers(session: ClarificationSession) -> list[str]:
    prompt = session.current_revision.prompt
    return [] if prompt is None else [item.requirement_id for item in prompt.requirements]


def _projection_summary(session: ClarificationSession) -> dict[str, Any]:
    """Redacted, complete semantic projection used by every trajectory record."""

    effective = session.effective_request
    def window(value: DateWindow | None) -> dict[str, str] | None:
        if value is None:
            return None
        return {"start": value.start.isoformat(), "end": value.end.isoformat(), "precision": value.precision.value}
    return {
        "context": {"reference_date": effective.context.reference_date.isoformat(), "timezone": effective.context.timezone},
        "travelers": effective.travelers,
        "origins": [{"kind": item.kind.value, "value": item.value} for item in effective.origins],
        "destinations": [{"kind": item.kind.value, "value": item.value} for item in effective.destinations],
        "departure_window": window(effective.departure_window),
        "return_window": window(effective.return_window),
        "interpreted_duration": None if effective.interpreted_duration is None else {
            "minimum_days": effective.interpreted_duration.minimum_days,
            "maximum_days": effective.interpreted_duration.maximum_days,
        },
        "unknowns": [{"field": item.field, "reason": item.reason.value} for item in effective.unknowns],
        "conflicts": [{"code": item.code, "fields": list(item.fields)} for item in effective.conflicts],
        "field_provenance": [
            {
                "field": item.field.value,
                "source": item.source.kind,
                "amendment_id": item.amendment_id,
                "message_id": item.source.span.message_id if hasattr(item.source, "span") else None,
            }
            for item in effective.field_provenance
        ],
        "temporal_contributions": [
            {
                "kind": item.kind.value,
                "source": item.source.kind,
                "amendment_id": item.amendment_id,
                "window": window(item.date_window),
                "duration": None if item.interpreted_duration is None else {
                    "minimum_days": item.interpreted_duration.minimum_days,
                    "maximum_days": item.interpreted_duration.maximum_days,
                },
            }
            for item in effective.temporal_contributions
        ],
    }


def _prompt_coverage_check(session: ClarificationSession) -> dict[str, Any]:
    """Check only prompt membership and deterministic requirement ordering."""

    revision = session.current_revision
    expected = [item.requirement_id for item in collect_blocking_requirements(session.effective_request)]
    actual = _blockers(session)
    if revision.status.value == "awaiting_answer":
        return {"expected": expected, "actual": actual, "passed": actual == expected}
    return {"expected": [], "actual": actual, "passed": not actual}


def _normalized_amendment_payload(amendment: TypedAmendment) -> dict[str, Any]:
    """Expose only target-specific typed values; spans are validated separately."""

    if isinstance(amendment, LocationAmendment):
        return {
            "locations": [
                {"kind": location.kind.value, "value": location.value}
                for location in amendment.locations
            ]
        }
    if isinstance(amendment, TravelersAmendment):
        return {"travelers": amendment.travelers}
    if isinstance(amendment, TemporalAmendment):
        return {"temporal_text": amendment.temporal_text}
    raise AssertionError(f"unsupported accepted amendment type {type(amendment)!r}")


def _typed_acceptance_failures(
    turn: Mapping[str, Any], session: ClarificationSession, *, message_id: str
) -> tuple[list[str], list[dict[str, Any]], list[dict[str, Any]], int]:
    """Compare a separately declared exact accepted-amendment oracle.

    The scripted proposal is deliberately *not* used to construct expected
    acceptance.  A proposal may be rejected during temporal normalization or
    conflict reduction, so treating every proposal as the oracle would make
    the metric circular.
    """

    outcome = session.current_revision.outcome
    actual: list[dict[str, Any]] = []
    if outcome is not None:
        contributions = {
            item.amendment_id: item.template_provenance
            for item in session.current_revision.effective_request.temporal_contributions
            if item.amendment_id is not None and item.template_provenance is not None
        }
        for item in outcome.accepted_amendments:
            row: dict[str, Any] = {
                "id": item.amendment_id,
                "target": item.target.value,
                "requirements": list(item.requirement_ids),
                "is_correction": item.is_correction,
                "payload": _normalized_amendment_payload(item),
            }
            provenance = contributions.get(item.amendment_id)
            if provenance is not None:
                row["provenance"] = provenance.model_dump(mode="json")
            actual.append(row)
    declared = turn.get("expect", {}).get("accepted", [])
    expected: list[dict[str, Any]] = []
    for item in declared:
        row = {
            "id": (
                f"{message_id}:template:{item['template_candidate']}"
                if item.get("template_candidate") is not None
                else f"{message_id}:a{item['ordinal']}"
            ),
            "target": item["target"],
            "requirements": list(item["requirements"]),
            "is_correction": item["is_correction"],
            "payload": dict(item["payload"]),
        }
        if item.get("template_candidate") is not None:
            row["provenance"] = dict(item["provenance"])
        expected.append(row)
    matched = sum(item in expected for item in actual)
    grounding_failures = [] if outcome is None else [
        f"accepted amendment {item.amendment_id!r} is not grounded in answer message {message_id!r}"
        for item in outcome.accepted_amendments
        if item.span.message_id != message_id
    ]
    if actual != expected:
        return grounding_failures + [f"accepted amendments expected {expected!r}, got {actual!r}"], expected, actual, matched
    return grounding_failures, expected, actual, matched


def _check(expect: Mapping[str, Any], session: ClarificationSession, *, error: str | None, replayed: bool) -> list[str]:
    failures: list[str] = []
    if "error" in expect:
        if error != expect["error"]:
            failures.append(f"error expected {expect['error']!r}, got {error!r}")
        return failures
    if error is not None:
        return [f"unexpected error {error!r}"]
    if "status" in expect and session.status.value != expect["status"]:
        failures.append(f"status expected {expect['status']!r}, got {session.status.value!r}")
    if "stop_reason" in expect:
        actual = session.current_revision.stop_reason
        if (actual.value if actual else None) != expect["stop_reason"]:
            failures.append("stop reason mismatch")
    if "blockers" in expect and _blockers(session) != expect["blockers"]:
        failures.append(f"blockers expected {expect['blockers']!r}, got {_blockers(session)!r}")
    if "replayed" in expect and replayed is not bool(expect["replayed"]):
        failures.append("replay result mismatch")
    outcome = session.current_revision.outcome
    if "accepted_count" in expect and (len(outcome.accepted_amendments) if outcome else 0) != expect["accepted_count"]:
        failures.append("accepted amendment count mismatch")
    if "rejected_reasons" in expect:
        actual_reasons = [item.reason.value for item in outcome.rejected_fragments] if outcome else []
        if actual_reasons != expect["rejected_reasons"]:
            failures.append(f"rejected reasons expected {expect['rejected_reasons']!r}, got {actual_reasons!r}")
    for key, value in expect.get("fields", {}).items():
        if _field_summary(session).get(key) != value:
            failures.append(f"field {key!r} expected {value!r}, got {_field_summary(session).get(key)!r}")
    return failures


def _replace_fixture_dependency(module: Any, attribute: str, replacement: Any) -> None:
    """Scoped fault injection for controller failure fixtures only."""

    setattr(module, attribute, replacement)


def run_clarification_continuation_eval(
    fixture_path: Path = DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES,
) -> dict[str, Any]:
    """Run every public trajectory using only deterministic scripted fixtures."""

    cases = preflight_clarification_continuation_cases(fixture_path)
    _, raw = _load(fixture_path)
    records: list[dict[str, Any]] = []
    final_projections: dict[str, dict[str, object]] = {}
    for case in cases:
        session = start_clarification(_initial(case.payload), session_id=f"fixture-{case.identifier}")
        initial_snapshot = deepcopy(session.initial_result.model_dump(mode="python"))
        previous_command: ClarificationAnswerCommand | None = None
        for index, turn in enumerate(case.payload["turns"], start=1):
            assert isinstance(turn, Mapping)
            kind = turn.get("kind", "answer")
            expect = turn["expect"]
            assert isinstance(expect, Mapping)
            current = session.current_revision
            prompt_id = current.prompt.prompt_id if current.prompt else "terminal"
            revision = current.revision
            message_id = f"{case.identifier}-m{index}"
            text = str(turn["text"])
            if kind == "replay":
                if previous_command is None:
                    raise ClarificationContinuationFixtureError("replay needs a prior command")
                command = previous_command
            elif kind == "replay_different_text":
                if previous_command is None:
                    raise ClarificationContinuationFixtureError("replay_different_text needs a prior command")
                command = previous_command.model_copy(update={"text": text})
            else:
                if kind == "stale":
                    revision += 1
                elif kind == "wrong_prompt":
                    prompt_id = "wrong-prompt"
                command = ClarificationAnswerCommand(
                    session_id=session.session_id, expected_revision=max(0, revision),
                    prompt_id=prompt_id, message_id=message_id, text=text,
                )
            interpreter = _ScriptedInterpreter(turn)
            before_revision = session.current_revision.revision
            before_session_snapshot = deepcopy(session.model_dump(mode="python"))
            before_projection = _projection_summary(session)
            before_blockers = _blockers(session)
            error: str | None = None
            replayed = False
            original_reducer = controller_module.apply_amendments
            original_normalizer = reducer_module.normalize_temporal_amendment
            fault = turn.get("fault")
            if fault == "reducer":
                _replace_fixture_dependency(
                    controller_module,
                    "apply_amendments",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("scripted reducer failure")),
                )
            elif fault == "temporal_normalizer":
                _replace_fixture_dependency(
                    reducer_module,
                    "normalize_temporal_amendment",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("scripted temporal failure")),
                )
            try:
                transition = apply_clarification_answer(session, command, interpreter)
                session = transition.session
                replayed = transition.replayed
                if kind != "replay":
                    previous_command = command
            except ClarificationCommandError:
                error = "command_error"
            except (ClarificationInterpretationError, RuntimeError):
                error = "system_error"
            finally:
                _replace_fixture_dependency(controller_module, "apply_amendments", original_reducer)
                _replace_fixture_dependency(
                    reducer_module, "normalize_temporal_amendment", original_normalizer
                )
            failures = _check(expect, session, error=error, replayed=replayed)
            prompt_coverage = _prompt_coverage_check(session)
            if not prompt_coverage["passed"]:
                failures.append("prompt does not exactly cover ordered blockers")
            expected_accepted: list[dict[str, object]] | None = None
            actual_accepted: list[dict[str, object]] | None = None
            accepted_matches = 0
            if error is None and not replayed:
                (
                    acceptance_failures,
                    expected_accepted,
                    actual_accepted,
                    accepted_matches,
                ) = _typed_acceptance_failures(turn, session, message_id=message_id)
                failures.extend(acceptance_failures)
            # Explicit error fixtures must leave the ledger unchanged.
            if error is not None and session.current_revision.revision != before_revision:
                failures.append("failed command mutated the session ledger")
            if session.initial_result.model_dump(mode="python") != initial_snapshot:
                failures.append("initial snapshot mutated")
            if before_session_snapshot != session.model_dump(mode="python") and replayed:
                failures.append("replay mutated session state")
            if error is not None and before_session_snapshot != session.model_dump(mode="python"):
                failures.append("failed command mutated any session state")
            if error is None and not replayed and session.current_revision.revision != before_revision + 1:
                failures.append("processed answer did not create exactly one revision")
            if session.status.value == "awaiting_answer":
                prompt = session.current_revision.prompt
                if prompt is None or prompt.revision != session.current_revision.revision:
                    failures.append("awaiting revision lacks its own prompt")
                elif prompt.prompt_id != f"prompt-{session.current_revision.revision}":
                    failures.append("prompt ID does not match deterministic revision policy")
            expected_calls = 0 if kind in {"replay", "replay_different_text", "stale", "wrong_prompt", "terminal"} or text.casefold() == "cancel" else 1
            if interpreter.calls != expected_calls:
                failures.append(f"interpreter calls expected {expected_calls}, got {interpreter.calls}")
            after_projection = _projection_summary(session)
            outcome = session.current_revision.outcome
            accepted_requirement_ids = [] if outcome is None else [
                requirement_id
                for amendment in outcome.accepted_amendments
                for requirement_id in amendment.requirement_ids
            ]
            records.append({
                "scenario": case.identifier, "turn": index, "status": "passed" if not failures else "failed",
                "checks": {"passed": not failures, "failures": failures}, "error": error,
                "controller_calls": interpreter.calls, "revision": session.current_revision.revision,
                "before_blockers": before_blockers, "blockers": _blockers(session),
                "prompt_coverage": prompt_coverage,
                "accepted_requirement_ids": accepted_requirement_ids,
                "accepted_oracle": (
                    None
                    if expected_accepted is None or actual_accepted is None
                    else {
                        "expected": expected_accepted,
                        "actual": actual_accepted,
                        "matched": accepted_matches,
                        "exact": expected_accepted == actual_accepted,
                    }
                ),
                "projection": after_projection, "projection_changed": before_projection != after_projection,
                "final_status": session.status.value, "stop_reason": (
                    session.current_revision.stop_reason.value if session.current_revision.stop_reason else None
                ),
            })
        final_projection = _projection_summary(session)
        expected_projection_fingerprint = case.payload["final_projection_sha256"]
        actual_projection_fingerprint = _projection_fingerprint(final_projection)
        final_projections[case.identifier] = _semantic_projection(session)
        if actual_projection_fingerprint != expected_projection_fingerprint:
            final_record = records[-1]
            final_record["checks"]["passed"] = False
            final_record["checks"]["failures"].append(
                "final projection fingerprint expected "
                f"{expected_projection_fingerprint!r}, got {actual_projection_fingerprint!r}"
            )
            final_record["status"] = "failed"
    artifact_privacy_violations = _privacy_violations(records, path="artifact.records")
    if artifact_privacy_violations:
        raise AssertionError(f"redacted evaluator artifact leaks fixture content: {artifact_privacy_violations!r}")
    failed_records = [record for record in records if record["status"] == "failed"]
    stop_reasons = Counter(str(record["stop_reason"]) for record in records if record["stop_reason"])
    coverage_runs = sum(record["prompt_coverage"]["passed"] for record in records)
    prompt_coverage = {
        "runs": len(records), "passed": coverage_runs,
        "rate": coverage_runs / len(records) if records else 0.0,
    }
    resolved = [
        set(record["before_blockers"]) - set(record["blockers"])
        for record in records if record["error"] is None
    ]
    resolved_total = sum(len(item) for item in resolved)
    accepted_requirement_ids = [
        requirement_id
        for record in records if record["error"] is None
        for requirement_id in record["accepted_requirement_ids"]
    ]
    accepted_oracles = [
        record["accepted_oracle"]
        for record in records
        if record["accepted_oracle"] is not None
    ]
    expected_accepted_total = sum(len(oracle["expected"]) for oracle in accepted_oracles)
    actual_accepted_total = sum(len(oracle["actual"]) for oracle in accepted_oracles)
    matched_accepted_total = sum(int(oracle["matched"]) for oracle in accepted_oracles)
    template_expected: Counter[str] = Counter()
    template_actual: Counter[str] = Counter()
    template_matched: Counter[str] = Counter()
    target_template_expected: Counter[tuple[str, str]] = Counter()
    target_template_actual: Counter[tuple[str, str]] = Counter()
    target_template_matched: Counter[tuple[str, str]] = Counter()
    for oracle in accepted_oracles:
        expected_by_id = {item["id"]: item for item in oracle["expected"]}
        actual_by_id = {item["id"]: item for item in oracle["actual"]}
        for item in expected_by_id.values():
            provenance = item.get("provenance")
            if isinstance(provenance, Mapping):
                template_expected[str(provenance["template_id"])] += 1
                target_template_expected[(str(item["target"]), str(provenance["template_id"]))] += 1
        for item in actual_by_id.values():
            provenance = item.get("provenance")
            if isinstance(provenance, Mapping):
                template_actual[str(provenance["template_id"])] += 1
                if item == expected_by_id.get(item["id"]):
                    template_matched[str(provenance["template_id"])] += 1
                    target_template_matched[(str(item["target"]), str(provenance["template_id"]))] += 1
                target_template_actual[(str(item["target"]), str(provenance["template_id"]))] += 1
    template_ids = sorted(set(template_expected) | set(template_actual))
    template_coverage = {
        "expected": sum(template_expected.values()),
        "actual": sum(template_actual.values()),
        "matched": sum(template_matched.values()),
        "per_template": {
            template_id: {
                "expected": template_expected[template_id],
                "actual": template_actual[template_id],
                "matched": template_matched[template_id],
                "exact": (
                    template_expected[template_id] == template_actual[template_id]
                    == template_matched[template_id]
                ),
            }
            for template_id in template_ids
        },
        "per_target_template": {
            f"{target}:{template_id}": {
                "target": target,
                "template_id": template_id,
                "expected": target_template_expected[(target, template_id)],
                "actual": target_template_actual[(target, template_id)],
                "matched": target_template_matched[(target, template_id)],
                "exact": (
                    target_template_expected[(target, template_id)]
                    == target_template_actual[(target, template_id)]
                    == target_template_matched[(target, template_id)]
                ),
            }
            for target, template_id in sorted(
                set(target_template_expected) | set(target_template_actual)
            )
        },
        "exact": (
            template_expected == template_actual == template_matched
            and bool(template_expected)
        ),
    }
    correctly_linked_resolutions = sum(
        requirement_id in (set(record["before_blockers"]) - set(record["blockers"]))
        for record in records if record["error"] is None
        for requirement_id in record["accepted_requirement_ids"]
    )
    ready_by_scenario: dict[str, int | None] = {}
    for case in cases:
        scenario_records = [record for record in records if record["scenario"] == case.identifier]
        ready = next((int(record["turn"]) for record in scenario_records if record["final_status"] == "ready"), None)
        ready_by_scenario[case.identifier] = ready
    equivalent_groups: dict[str, list[str]] = {}
    for case in cases:
        group = case.payload.get("equivalence_group")
        if isinstance(group, str):
            equivalent_groups.setdefault(group, []).append(case.identifier)
    equivalence_failures = {
        group: identifiers
        for group, identifiers in equivalent_groups.items()
        if len({repr(final_projections[identifier]) for identifier in identifiers}) != 1
    }
    if equivalence_failures:
        failed_records.append({"scenario": "equivalence", "status": "failed"})
    scenario_groups: dict[str, dict[str, int]] = {}
    for case in cases:
        group = case.payload.get("coverage_group")
        if not isinstance(group, str):
            continue
        group_records = [record for record in records if record["scenario"] == case.identifier]
        summary = scenario_groups.setdefault(
            group, {"scenarios": 0, "turns": 0, "passed": 0, "failed": 0}
        )
        summary["scenarios"] += 1
        summary["turns"] += len(group_records)
        summary["passed"] += sum(record["status"] == "passed" for record in group_records)
        summary["failed"] += sum(record["status"] == "failed" for record in group_records)
    return {
        "schema_version": "clarification_continuation_eval_v1",
        "fixture": {"path": str(fixture_path), "sha256": sha256(raw).hexdigest(), "redacted": True},
        "records": records,
        "summary": {
            "scenarios": len(cases), "turns": len(records), "passed": len(records) - len(failed_records),
            "failed": len(failed_records), "errors": sum(record["error"] is not None for record in records),
            "stop_reasons": dict(sorted(stop_reasons.items())),
            "prompt_coverage": prompt_coverage,
            "requirement_resolution": {
                "resolved_requirements": resolved_total,
                "linked_amendments": len(accepted_requirement_ids),
                "precision": (
                    correctly_linked_resolutions / len(accepted_requirement_ids)
                    if accepted_requirement_ids else 1.0
                ),
                "recall": (
                    correctly_linked_resolutions / resolved_total if resolved_total else 1.0
                ),
            },
            "accepted_amendment_correctness": {
                "expected": expected_accepted_total,
                "actual": actual_accepted_total,
                "matched": matched_accepted_total,
                "precision": (
                    matched_accepted_total / actual_accepted_total if actual_accepted_total else 1.0
                ),
                "recall": (
                    matched_accepted_total / expected_accepted_total if expected_accepted_total else 1.0
                ),
                "definition": (
                    "separately declared fixture oracle exact typed amendment identity, target, requirement links, "
                    "correction flag, and normalized target-specific payload equality"
                ),
            },
            "template_coverage": template_coverage,
            "scenario_groups": scenario_groups,
            "convergence": {
                "ready_sessions": sum(value is not None for value in ready_by_scenario.values()),
                "turns_to_ready": ready_by_scenario,
            },
            "equivalent_outcomes": {
                "groups": equivalent_groups,
                "passed": not equivalence_failures,
                "failures": equivalence_failures,
            },
            "instrumentation": {
                "controller_calls": sum(int(record["controller_calls"]) for record in records),
                "latency_seconds": 0.0,
                "tokens": 0,
                "errors": sum(record["error"] is not None for record in records),
            },
            "privacy_audit": {"passed": True, "violations": []},
            "exact_gate": {"passed": not failed_records, "required_rate": 1.0},
        },
    }


__all__ = [
    "DEFAULT_CLARIFICATION_CONTINUATION_FIXTURES",
    "ClarificationContinuationFixtureError",
    "preflight_clarification_continuation_cases",
    "run_clarification_continuation_eval",
]
