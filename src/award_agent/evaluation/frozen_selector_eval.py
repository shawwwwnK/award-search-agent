"""Frozen, selector-only evaluation independent of the request-understanding runner.

This evaluator intentionally does not invoke runtime model boundaries, the request workflow, or a live
holiday provider.  It starts from public date-free selector projections, restores selections into
the private manual catalog, then validates and compiles them with fixed holiday dates.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import product
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml
from pydantic import ValidationError

from award_agent.domain import Holiday
from award_agent.evaluation.frozen_selector_cases import (
    FrozenSelectorCase,
    frozen_selector_case_registry,
)
from award_agent.intent.extractor import TemporalCandidateSelector
from award_agent.intent.model_views import TemporalSelectorInput, TemporalSelectorOutput
from award_agent.intent.openai_extractor import (
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    TemporalSelectionError,
)
from award_agent.intent.temporal_compiler import compile_temporal_candidates
from award_agent.intent.temporal_selector import (
    build_temporal_selector_input,
    plan_temporal_selection,
    restore_selector_output,
    unresolved_selection,
)

DEFAULT_FROZEN_SELECTOR_FIXTURES = Path("evals/selector/frozen_cases_v2.yaml")
LEGACY_FROZEN_SELECTOR_FIXTURES = Path("evals/selector/frozen_cases.yaml")

# These are the acceptance thresholds recorded in the compiler-selector handoff.  They are
# deliberately data rather than CLI policy so each saved study says exactly what it was judged
# against.
SELECTOR_QUALITY_GATE_THRESHOLDS: Mapping[str, float] = {
    "parse_rate": 1.0,
    "membership_rate": 1.0,
    "compiler_completion_rate": 1.0,
    "semantic_accuracy_rate": 0.95,
    "target_accuracy_rate": 0.90,
    "reference_accuracy_rate": 0.90,
    "composition_accuracy_rate": 0.90,
    "scope_accuracy_rate": 0.90,
    "unsupported_to_unresolved_accuracy_rate": 1.0,
    "repair_attempts": 0.0,
}


class FrozenSelectorFixtureError(ValueError):
    """The checked-in public fixture no longer matches its private catalog."""


@runtime_checkable
class _CaptureSelector(Protocol):
    def reset_capture(self) -> None: ...

    def take_usage(self) -> dict[str, int] | None: ...


@dataclass(frozen=True)
class PreparedFrozenSelectorCase:
    """A private catalog paired with its exact checked-in public input."""

    fixture: FrozenSelectorCase
    model_input: TemporalSelectorInput
    contract_version: str


@dataclass(frozen=True)
class LoadedFrozenSelectorFixtures:
    """Checked-in public fixture rows plus immutable study identity metadata."""

    contract_version: str
    scenarios: tuple[dict[str, Any], ...]
    path: Path
    sha256: str


class StaticFrozenHolidayProvider:
    """Small offline calendar fixture for compiler completion checks."""

    _DATES: Mapping[tuple[Holiday, int], date] = {
        (Holiday.LABOR_DAY, 2026): date(2026, 9, 7),
        (Holiday.THANKSGIVING, 2026): date(2026, 11, 26),
        (Holiday.NEW_YEARS_DAY, 2026): date(2026, 1, 1),
        (Holiday.NEW_YEARS_DAY, 2027): date(2027, 1, 1),
    }

    def holiday_date(self, holiday: Holiday, year: int) -> date:
        try:
            return self._DATES[(holiday, year)]
        except KeyError as exc:
            raise AssertionError(
                f"frozen selector fixture requested unstubbed holiday {holiday.value} {year}"
            ) from exc


SelectorFactory = Callable[[str], TemporalCandidateSelector]


def _public_projection(model_input: TemporalSelectorInput) -> dict[str, Any]:
    """Get the serializable boundary payload, excluding Pydantic private restoration maps."""

    return model_input.model_dump(mode="json")


def _load_public_fixtures(path: Path) -> LoadedFrozenSelectorFixtures:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FrozenSelectorFixtureError(f"cannot read frozen selector fixtures: {path}") from exc
    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise FrozenSelectorFixtureError(f"cannot parse frozen selector fixtures: {path}") from exc
    if not isinstance(payload, Mapping):
        raise FrozenSelectorFixtureError("frozen selector fixture must be a mapping")
    if set(payload) == {"scenarios"}:
        # Historical study inputs did not carry explicit contract metadata.  Keep them usable for
        # regression/preflight without silently treating them as the current study contract.
        contract_version = "v1"
    elif set(payload) == {"contract_version", "scenarios"} and payload["contract_version"] == "v2":
        contract_version = "v2"
    else:
        raise FrozenSelectorFixtureError(
            "frozen selector fixture must be legacy scenarios-only v1 or tagged v2"
        )
    scenarios = payload.get("scenarios") if isinstance(payload, Mapping) else None
    if not isinstance(scenarios, list):
        raise FrozenSelectorFixtureError("frozen selector fixture must contain a scenarios list")
    expected_keys = {"id", "category", "pair", "public_input"}
    seen: set[str] = set()
    checked: list[dict[str, Any]] = []
    for item in scenarios:
        if not isinstance(item, Mapping) or set(item) != expected_keys:
            raise FrozenSelectorFixtureError(
                "every frozen selector scenario must contain only id, category, pair, and public_input"
            )
        identifier = item["id"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise FrozenSelectorFixtureError("frozen selector scenario ids must be unique non-empty strings")
        if not all(isinstance(item[field], str) and item[field] for field in ("category", "pair")):
            raise FrozenSelectorFixtureError(f"frozen selector scenario {identifier!r} has invalid labels")
        if not isinstance(item["public_input"], Mapping):
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {identifier!r} must include a public input object"
            )
        try:
            TemporalSelectorInput.model_validate(item["public_input"])
        except ValueError as exc:
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {identifier!r} has invalid public input"
            ) from exc
        seen.add(identifier)
        checked.append(dict(item))
    return LoadedFrozenSelectorFixtures(
        contract_version=contract_version,
        scenarios=tuple(checked),
        path=path,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def _selected_handles(
    prepared: PreparedFrozenSelectorCase,
    selected_from_selector: Sequence[str],
) -> tuple[str, ...]:
    plan = plan_temporal_selection(prepared.fixture.catalog)
    restored = restore_selector_output(
        prepared.model_input,
        TemporalSelectorOutput(selected_candidates=list(selected_from_selector)),
    )
    return (*plan.auto_selected, *restored)


def _semantic_fingerprint(case: FrozenSelectorCase, selected: Sequence[str]) -> str:
    """Canonical compiled semantics used only by private fixture/discriminator checks."""

    compiled = compile_temporal_candidates(
        case.request,
        case.catalog,
        selected,
        holiday_provider=StaticFrozenHolidayProvider(),
    )
    return json.dumps(compiled.graph.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _valid_selection_fingerprints(prepared: PreparedFrozenSelectorCase) -> set[str]:
    """Enumerate the tiny finite choice space to prove the fixture has a discriminator."""

    plan = plan_temporal_selection(prepared.fixture.catalog)
    groups = prepared.model_input.candidate_groups
    public_choices = [tuple(candidate.handle for candidate in group.candidates) for group in groups]
    fingerprints: set[str] = set()
    for output in product(*public_choices):
        try:
            selected = _selected_handles(prepared, output)
            fingerprints.add(_semantic_fingerprint(prepared.fixture, selected))
        except (ValueError, AssertionError):
            # A dependency-incompatible choice remains useful as a selection validation case,
            # but it cannot prove compiler-semantic discrimination by itself.
            continue
    if not plan.selector_groups:
        raise FrozenSelectorFixtureError(
            f"frozen selector scenario {prepared.fixture.identifier!r} has no selector group"
        )
    return fingerprints


def _lint_discriminators(prepared: Sequence[PreparedFrozenSelectorCase]) -> None:
    """Reject duplicate/easy fixtures before any model is called.

    Every fixture must have more than one valid compiled semantic outcome.  Forward/reversed
    counterparts must share their oracle semantics while placing each oracle choice at a different
    public candidate position, preventing a fixed-position answer from passing the study.
    """

    pairs: dict[str, list[PreparedFrozenSelectorCase]] = defaultdict(list)
    for item in prepared:
        plan = plan_temporal_selection(item.fixture.catalog)
        expected = (*plan.auto_selected, *item.fixture.oracle_candidates)
        if _semantic_fingerprint(item.fixture, expected) not in _valid_selection_fingerprints(item):
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {item.fixture.identifier!r} oracle does not compile"
            )
        if len(_valid_selection_fingerprints(item)) < 2:
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {item.fixture.identifier!r} has no semantic discriminator"
            )
        pairs[item.fixture.pair].append(item)

    for pair, variants in pairs.items():
        if len(variants) != 2:
            raise FrozenSelectorFixtureError(f"frozen selector pair {pair!r} must have two order variants")
        fingerprints: list[str] = []
        positions: list[tuple[int, ...]] = []
        for item in variants:
            plan = plan_temporal_selection(item.fixture.catalog)
            expected = (*plan.auto_selected, *item.fixture.oracle_candidates)
            fingerprints.append(_semantic_fingerprint(item.fixture, expected))
            oracle = set(item.fixture.oracle_candidates)
            positions.append(
                tuple(
                    index
                    for group in item.model_input.candidate_groups
                    for index, candidate in enumerate(group.candidates)
                    if item.model_input._candidate_handles[candidate.handle] in oracle
                )
            )
        if fingerprints[0] != fingerprints[1]:
            raise FrozenSelectorFixtureError(
                f"frozen selector pair {pair!r} order variants have different oracle semantics"
            )
        if positions[0] == positions[1]:
            raise FrozenSelectorFixtureError(
                f"frozen selector pair {pair!r} does not balance oracle candidate positions"
            )


def _normalized_candidate_semantics(candidate: Any) -> tuple[Any, ...]:
    """Compare only selector-visible semantics, independent of opaque candidate/slot numbering."""

    return (
        candidate.summary,
        candidate.interpretation_kind,
        candidate.relation_ordinal,
        candidate.target,
        candidate.covers,
        tuple((use.anchor, use.mode) for use in candidate.anchor_uses),
        candidate.composition,
        # ``requires``/``produces`` are intentionally reduced to role shape. pN labels change
        # under candidate ordering and do not by themselves convey an interpretation.
        len(candidate.requires),
        len(candidate.produces),
        candidate.composition_operand is not None,
    )


def _oracle_public_semantics(prepared: PreparedFrozenSelectorCase) -> tuple[tuple[Any, ...], ...]:
    oracle = set(prepared.fixture.oracle_candidates)
    return tuple(
        _normalized_candidate_semantics(candidate)
        for group in prepared.model_input.candidate_groups
        for candidate in group.candidates
        if prepared.model_input._candidate_handles[candidate.handle] in oracle
    )


def _lint_v2_self_sufficiency(prepared: Sequence[PreparedFrozenSelectorCase]) -> None:
    """Reject v2 fixtures whose public view cannot identify its private oracle safely.

    This is deliberately a public-contract lint: it must not inspect candidate relation enums,
    resolved dates, or private oracle identities to prove a distinction.  Private identities are
    used only to locate the already-published oracle candidate for the cross-order comparison.
    """

    pairs: dict[str, list[PreparedFrozenSelectorCase]] = defaultdict(list)
    for item in prepared:
        if item.contract_version != "v2":
            raise FrozenSelectorFixtureError("v2 self-sufficiency lint received a non-v2 fixture")
        evidence = {entry.handle: entry for entry in item.model_input.ordered_evidence}
        for group in item.model_input.candidate_groups:
            normalized = [_normalized_candidate_semantics(candidate) for candidate in group.candidates]
            if len(normalized) != len(set(normalized)):
                raise FrozenSelectorFixtureError(
                    f"frozen selector scenario {item.fixture.identifier!r} has duplicate public candidate semantics"
                )
            varying_targets = {
                candidate.target
                for candidate in group.candidates
                if candidate.interpretation_kind != "unresolved"
            }
            if len(varying_targets) > 1:
                cues = {
                    evidence[handle].endpoint_cue
                    for candidate in group.candidates
                    for handle in candidate.covers
                    if evidence[handle].endpoint_cue in {"departure", "return"}
                }
                if not cues:
                    raise FrozenSelectorFixtureError(
                        f"frozen selector scenario {item.fixture.identifier!r} has target alternatives without an explicit endpoint cue"
                    )
                oracle_targets = {
                    candidate.target
                    for candidate in group.candidates
                    if item.model_input._candidate_handles[candidate.handle]
                    in item.fixture.oracle_candidates
                }
                if not oracle_targets <= cues:
                    raise FrozenSelectorFixtureError(
                        f"frozen selector scenario {item.fixture.identifier!r} oracle target conflicts with its explicit endpoint cue"
                    )
        pairs[item.fixture.pair].append(item)

    for pair, variants in pairs.items():
        semantic_identities = {_oracle_public_semantics(item) for item in variants}
        if len(semantic_identities) != 1:
            raise FrozenSelectorFixtureError(
                f"frozen selector pair {pair!r} does not retain one normalized public oracle identity"
            )


def _preflight_loaded_frozen_selector_cases(
    loaded: LoadedFrozenSelectorFixtures,
) -> tuple[PreparedFrozenSelectorCase, ...]:
    """Reconstruct private catalogs and assert a loaded fixture's exact public projection."""

    registry = frozen_selector_case_registry()
    fixture_ids = {str(item["id"]) for item in loaded.scenarios}
    if fixture_ids != set(registry):
        missing = sorted(set(registry) - fixture_ids)
        extra = sorted(fixture_ids - set(registry))
        raise FrozenSelectorFixtureError(
            f"frozen selector fixture registry mismatch; missing={missing!r} extra={extra!r}"
        )
    prepared: list[PreparedFrozenSelectorCase] = []
    for row in loaded.scenarios:
        identifier = str(row["id"])
        fixture = registry[identifier]
        if row["category"] != fixture.category or row["pair"] != fixture.pair:
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {identifier!r} does not match private labels"
            )
        model_input = build_temporal_selector_input(
            fixture.catalog,
            plan_temporal_selection(fixture.catalog),
            contract_version=loaded.contract_version,  # type: ignore[arg-type]
        )
        if _public_projection(model_input) != row["public_input"]:
            raise FrozenSelectorFixtureError(
                f"frozen selector scenario {identifier!r} public projection drifted; regenerate and review YAML"
            )
        prepared.append(PreparedFrozenSelectorCase(fixture, model_input, loaded.contract_version))
    _lint_discriminators(prepared)
    if loaded.contract_version == "v2":
        _lint_v2_self_sufficiency(prepared)
    return tuple(prepared)


def preflight_frozen_selector_cases(
    fixtures_path: Path = DEFAULT_FROZEN_SELECTOR_FIXTURES,
) -> tuple[PreparedFrozenSelectorCase, ...]:
    """Reconstruct private catalogs and assert their public projections exactly match YAML."""

    return _preflight_loaded_frozen_selector_cases(_load_public_fixtures(fixtures_path))


def _default_selector_factory(model: str) -> TemporalCandidateSelector:
    return OpenAIIntentExtractor(config=OpenAIExtractorConfig(model=model))


def _take_usage(selector: TemporalCandidateSelector) -> dict[str, int] | None:
    if isinstance(selector, _CaptureSelector):
        return selector.take_usage()
    return None


def _reset_capture(selector: TemporalCandidateSelector) -> None:
    if isinstance(selector, _CaptureSelector):
        selector.reset_capture()


def _usage_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    usage_records = [item["usage"] for item in results if isinstance(item.get("usage"), Mapping)]
    attempts = sum(bool(item.get("selector_call_attempted")) for item in results)
    keys = (
        "calls",
        "captured_calls",
        "missing_calls",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    )
    return {
        # An attempted selector invocation remains a call even if the SDK raised before it
        # returned usage, or returned a response with no usage object.
        "selector_call_attempts": attempts,
        "sdk_usage_captured_attempts": len(usage_records),
        "sdk_usage_missing_attempts": attempts - len(usage_records),
        **{key: sum(int(record.get(key, 0)) for record in usage_records) for key in keys},
    }


def _metric(runs: Sequence[Mapping[str, Any]], key: str) -> dict[str, float | int]:
    applicable = [run for run in runs if run.get(key) is not None]
    passed = sum(bool(run.get(key)) for run in applicable)
    return {
        "runs": len(applicable),
        "passed": passed,
        "rate": passed / len(applicable) if applicable else 0.0,
    }


def _gate_check(
    *,
    actual: float,
    threshold: float,
    comparison: str = "at_least",
) -> dict[str, float | bool | str]:
    if comparison == "at_most":
        passed = actual <= threshold
    else:
        passed = actual >= threshold
    return {
        "actual": actual,
        "threshold": threshold,
        "comparison": comparison,
        "passed": passed,
    }


def _quality_gate_for_arm(arm: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a model arm against the live-selector handoff gate.

    The no-selector control intentionally has no model output to qualify, so it is included in
    the artifact for comparison but cannot pass or fail the enablement gate.
    """

    if arm == "none":
        return {
            "eligible": False,
            "passed": None,
            "reason": "no_selector_control_is_not_gate_eligible",
            "checks": {},
        }

    category_accuracy = summary["per_class_accuracy"]
    checks = {
        "parse": _gate_check(
            actual=summary["parse"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["parse_rate"],
        ),
        "membership": _gate_check(
            actual=summary["membership"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["membership_rate"],
        ),
        "compiler_completion": _gate_check(
            actual=summary["validation_compiler_completion"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["compiler_completion_rate"],
        ),
        "semantic_accuracy": _gate_check(
            actual=summary["semantic_accuracy"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["semantic_accuracy_rate"],
        ),
        "target_accuracy": _gate_check(
            actual=category_accuracy["target"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["target_accuracy_rate"],
        ),
        "reference_accuracy": _gate_check(
            actual=category_accuracy["reference"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["reference_accuracy_rate"],
        ),
        "composition_accuracy": _gate_check(
            actual=category_accuracy["composition"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["composition_accuracy_rate"],
        ),
        "scope_accuracy": _gate_check(
            actual=category_accuracy["scope"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["scope_accuracy_rate"],
        ),
        "unsupported_to_unresolved_accuracy": _gate_check(
            actual=summary["unsupported_to_unresolved_accuracy"]["rate"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS[
                "unsupported_to_unresolved_accuracy_rate"
            ],
        ),
        "repairs": _gate_check(
            actual=summary["repairs"]["attempts"],
            threshold=SELECTOR_QUALITY_GATE_THRESHOLDS["repair_attempts"],
            comparison="at_most",
        ),
    }
    return {
        "eligible": True,
        "passed": all(bool(check["passed"]) for check in checks.values()),
        "checks": checks,
    }


def _summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    successful = [run for run in results if run.get("status") != "error"]
    by_category: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    # Selector errors are semantically incorrect outcomes, so retain them in accuracy
    # denominators.  ``None`` remains the explicit N/A marker for metrics such as parse_valid
    # (used by the no-selector arm), and _metric excludes only those values.
    for run in results:
        by_category[str(run["category"])].append(run)
    category_accuracy = {
        category: _metric(runs, "semantic_correct") for category, runs in sorted(by_category.items())
    }
    unsupported = by_category.get("unsupported", [])
    return {
        "runs": len(results),
        "completed": len(successful),
        "errors": len(results) - len(successful),
        "parse": _metric(results, "parse_valid"),
        "membership": _metric(results, "membership_valid"),
        "validation_compiler_completion": _metric(results, "compiler_completed"),
        "semantic_accuracy": _metric(results, "semantic_correct"),
        "per_class_accuracy": category_accuracy,
        "unsupported_to_unresolved_accuracy": _metric(unsupported, "semantic_correct"),
        "repairs": {"attempts": 0, "successes": 0, "zero_repairs": True},
        "latency_seconds": {
            "total": round(sum(float(run["latency_seconds"]) for run in results), 3),
            "mean": round(
                sum(float(run["latency_seconds"]) for run in results) / len(results), 3
            )
            if results
            else 0.0,
        },
        "usage": _usage_summary(results),
    }


def _selector_failure_code(exc: BaseException) -> str:
    """Classify selector-boundary failures without retaining exception text in artifacts."""

    if isinstance(exc, ValidationError):
        return "selector_parse_failed"
    # The adapter deliberately has public, fixed messages for these post-response failures.
    # Treat parsed-output absence/type mismatch as parse failure, distinct from a failed SDK
    # call.  Do not propagate the message: a different selector implementation could include
    # private catalog details in it.
    if isinstance(exc, TemporalSelectionError) and (
        "no parsed" in str(exc) or "unexpected" in str(exc)
    ):
        return "selector_parse_failed"
    return "selector_call_failed"


def _record_public_error(record: dict[str, Any], *, stage: str, code: str) -> None:
    """Store a stable public classification, never an exception's potentially private text."""

    record.update(
        {
            "status": "error",
            "error_stage": stage,
            "error_code": code,
        }
    )


def _run_one(
    prepared: PreparedFrozenSelectorCase,
    arm: str,
    selector: TemporalCandidateSelector | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    record: dict[str, Any] = {
        "id": prepared.fixture.identifier,
        "category": prepared.fixture.category,
        "pair": prepared.fixture.pair,
        "arm": arm,
        "repairs": 0,
        "parse_valid": None,
        "membership_valid": False,
        "compiler_completed": False,
        "semantic_correct": False,
        "selector_call_attempted": False,
    }
    if selector is None:
        selected_public = [
            public
            for public, private in prepared.model_input._candidate_handles.items()
            if private
            in unresolved_selection(
                prepared.fixture.catalog, plan_temporal_selection(prepared.fixture.catalog)
            )
        ]
    else:
        # A model-arm failure is a failed parse outcome, not an N/A control result.  Record the
        # attempt before crossing the selector boundary because SDK usage can be absent on either
        # a client failure or a response without usage metadata.
        record["parse_valid"] = False
        record["selector_call_attempted"] = True
        try:
            response = selector.select_candidates(prepared.model_input)
            if not isinstance(response, TemporalSelectorOutput):
                response = TemporalSelectorOutput.model_validate(response)
            selected_public = response.selected_candidates
            record["parse_valid"] = True
        except Exception as exc:  # noqa: BLE001 - preserve other study records after one bad call
            _record_public_error(
                record,
                stage="selector",
                code=_selector_failure_code(exc),
            )
            selected_public = []

    if record.get("status") != "error":
        try:
            selected = _selected_handles(prepared, selected_public)
            record["membership_valid"] = True
        except Exception:  # noqa: BLE001 - validation errors can contain restored private handles
            _record_public_error(
                record,
                stage="selection_validation",
                code="selector_selection_validation_failed",
            )

    if record.get("status") != "error":
        try:
            compile_temporal_candidates(
                prepared.fixture.request,
                prepared.fixture.catalog,
                selected,
                holiday_provider=StaticFrozenHolidayProvider(),
            )
            record["compiler_completed"] = True
            record["semantic_correct"] = set(selected) == {
                *plan_temporal_selection(prepared.fixture.catalog).auto_selected,
                *prepared.fixture.oracle_candidates,
            }
            record["status"] = "passed" if record["semantic_correct"] else "failed"
            # Only the public opaque handles returned by a schema-valid selector are retained.
            record["selected_candidates"] = selected_public
        except Exception:  # noqa: BLE001 - compiler errors can name private candidates and slots
            _record_public_error(
                record,
                stage="compiler",
                code="selector_compiler_failed",
            )

    if selector is not None:
        record["usage"] = _take_usage(selector)
    else:
        record["usage"] = None
    record["latency_seconds"] = round(time.perf_counter() - started, 3)
    return record


def run_frozen_selector_eval(
    *,
    mini_model: str,
    luna_model: str,
    fixtures_path: Path = DEFAULT_FROZEN_SELECTOR_FIXTURES,
    trials: int = 1,
    selector_factory: SelectorFactory | None = None,
) -> dict[str, Any]:
    """Run None/Mini/Luna selector arms against frozen date-free projections.

    ``mini_model`` and ``luna_model`` are deliberately explicit caller inputs; this code assigns
    neither product names nor model IDs.  The ``none`` arm sends no model request and selects the
    conservative unresolved choice for every selector group.
    """

    if not mini_model or not luna_model:
        raise ValueError("mini_model and luna_model must both be explicit non-empty model IDs")
    if trials < 1:
        raise ValueError("trials must be positive")
    loaded_fixtures = _load_public_fixtures(fixtures_path)
    prepared = _preflight_loaded_frozen_selector_cases(loaded_fixtures)
    factory = selector_factory or _default_selector_factory
    model_arms: tuple[tuple[str, str | None], ...] = (
        ("none", None),
        ("mini", mini_model),
        ("luna", luna_model),
    )
    selectors = {
        arm: None if model is None else factory(model)
        for arm, model in model_arms
    }
    results: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        for arm, _model in model_arms:
            selector = selectors[arm]
            for item in prepared:
                if selector is not None:
                    _reset_capture(selector)
                record = _run_one(item, arm, selector)
                record["trial"] = trial
                results.append(record)
    arm_results = {
        arm: _summary([record for record in results if record["arm"] == arm])
        for arm, _model in model_arms
    }
    quality_gate = {
        "thresholds": dict(SELECTOR_QUALITY_GATE_THRESHOLDS),
        "arms": {
            arm: _quality_gate_for_arm(arm, arm_results[arm]) for arm, _model in model_arms
        },
    }
    return {
        "schema_version": 2,
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation": "frozen_temporal_selector_only",
        "fixtures_path": str(fixtures_path),
        "fixture": {
            "contract_version": loaded_fixtures.contract_version,
            "path": str(loaded_fixtures.path),
            "sha256": loaded_fixtures.sha256,
        },
        "scenario_count": len(prepared),
        "trials": trials,
        "arms": {
            "none": {"model": None, "selector_calls": 0},
            "mini": {"model": mini_model},
            "luna": {"model": luna_model},
        },
        "summary": {
            "arms": arm_results,
            "repairs": {"attempts": 0, "zero_repairs": True},
            "quality_gate": quality_gate,
        },
        "results": results,
    }
