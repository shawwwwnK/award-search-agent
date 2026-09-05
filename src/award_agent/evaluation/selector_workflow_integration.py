"""Test-only end-to-end evaluation of the optional temporal selector path.

This is deliberately separate from the ready-corpus evaluator.  The production grammar has no
selector groups, so this module injects the existing private manual ambiguity catalogs through a
guarded ``compiler_select_v1`` workflow hook.  Pass 1 and holiday resolution are static; the
selector is the only boundary a live run may exercise.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml
from pydantic import ValidationError

from award_agent.domain import (
    CabinClass,
    CoarseIntentExtraction,
    LocationKind,
    LocationRef,
    RequestUnderstandingResult,
    SearchMode,
    TemporalRelationGraph,
)
from award_agent.evaluation.frozen_selector_cases import (
    FrozenSelectorCase,
    frozen_selector_case_registry,
)
from award_agent.evaluation.frozen_selector_eval import (
    DEFAULT_FROZEN_SELECTOR_FIXTURES,
    StaticFrozenHolidayProvider,
    preflight_frozen_selector_cases,
)
from award_agent.intent.extractor import TemporalCandidateSelector
from award_agent.intent.model_views import (
    CoarseExtractionInput,
    CoarseExtractionRepairInput,
    NonTemporalExtractionInput,
    NonTemporalIntentExtraction,
    StructuredValidationErrorView,
    TemporalInterpretationInput,
    TemporalResolutionResult,
    TemporalSelectorInput,
    TemporalSelectorOutput,
)
from award_agent.intent.openai_extractor import (
    OpenAIExtractorConfig,
    OpenAIIntentExtractor,
    TemporalSelectionError,
)
from award_agent.intent.temporal_selector import TemporalSelectorValidationError
from award_agent.intent.workflow import understand_request

DEFAULT_SELECTOR_WORKFLOW_MANIFEST = Path("evals/selector/workflow_integration_cases_v1.yaml")


class SelectorWorkflowFixtureError(ValueError):
    """The public integration manifest is inconsistent with the private case registry."""


@runtime_checkable
class _CaptureSelector(Protocol):
    def reset_capture(self) -> None: ...

    def take_usage(self) -> dict[str, int] | None: ...


class _StaticNonTemporalExtractor:
    """A complete, non-live Pass 1 fixture so temporal clarification remains observable."""

    def extract_non_temporal(
        self, _model_input: NonTemporalExtractionInput
    ) -> NonTemporalIntentExtraction:
        return NonTemporalIntentExtraction(
            travelers=1,
            origins=[LocationRef(kind=LocationKind.CITY, value="Origin", raw_text="Origin")],
            destinations=[
                LocationRef(kind=LocationKind.CITY, value="Destination", raw_text="Destination")
            ],
            cabins=[CabinClass.ECONOMY],
            search_modes=[SearchMode.AWARD],
        )

    def extract(self, _model_input: CoarseExtractionInput) -> CoarseIntentExtraction:
        raise AssertionError("selector workflow integration must not call legacy Pass 1")

    def repair_extract(self, _model_input: CoarseExtractionRepairInput) -> CoarseIntentExtraction:
        raise AssertionError("selector workflow integration must not repair legacy Pass 1")


class _ResolverMustNotRun:
    """Fail closed if an integration run leaks into the legacy temporal resolver."""

    def resolve_dates(self, _model_input: TemporalInterpretationInput) -> TemporalResolutionResult:
        raise AssertionError("selector workflow integration must not call the temporal resolver")

    def repair_dates(
        self,
        _model_input: TemporalInterpretationInput,
        _rejected_output: TemporalRelationGraph,
        _validation_errors: list[StructuredValidationErrorView],
    ) -> TemporalRelationGraph:
        raise AssertionError("selector workflow integration must not repair the temporal resolver")


SelectorFactory = Callable[[str], TemporalCandidateSelector]


@dataclass(frozen=True)
class _ManifestCase:
    identifier: str
    category: str
    pair: str


@dataclass(frozen=True)
class _PreparedIntegrationCases:
    cases: tuple[FrozenSelectorCase, ...]
    frozen_fixture_contract_version: str
    frozen_fixture_path: Path
    frozen_fixture_sha256: str


@dataclass(frozen=True)
class _WorkflowOracle:
    """Private exact workflow outcome expected after the private selector oracle is restored."""

    relation_kinds: tuple[str, ...]
    departure: tuple[date, date, str, str] | None
    return_window: tuple[date, date, str, str] | None
    unresolved: tuple[tuple[str, str, str], ...]
    conflicts: tuple[tuple[str, tuple[str, ...], str], ...]
    clarification: tuple[str, str | None, str | None, str]


_ASK_RETURN = (
    "ask",
    "return_or_duration",
    "When should you return, or how long should the trip be?",
    "return_or_duration is required to define a bounded flight search.",
)
_ASK_DEPARTURE = (
    "ask",
    "departure",
    "What departure date or date range should I use?",
    "departure is required to define a bounded flight search.",
)
_NO_CLARIFICATION = (
    "none",
    None,
    None,
    "The request contains enough hard constraints for later search planning.",
)

# These are intentionally local test oracles, not fixture data: serializing them would disclose
# resolved calendar values and expected workflow outputs to the selector study artifact.
_WORKFLOW_ORACLES: Mapping[str, _WorkflowOracle] = {
    "target": _WorkflowOracle(
        ("anchor_window",),
        (date(2026, 10, 5), date(2026, 10, 5), "exact", "October 5"),
        None,
        (),
        (),
        _ASK_RETURN,
    ),
    "reference": _WorkflowOracle(
        ("relative_weekend",),
        (date(2026, 12, 5), date(2026, 12, 6), "window", "two weekends after Thanksgiving"),
        None,
        (),
        (),
        _ASK_RETURN,
    ),
    "composition": _WorkflowOracle(
        ("anchor_window", "relative_weekday"),
        (date(2026, 9, 3), date(2026, 9, 7), "window", "Labor Day weekend; Thursday as well"),
        None,
        (),
        (),
        _ASK_RETURN,
    ),
    "scope": _WorkflowOracle(
        ("unbounded_boundary",),
        None,
        None,
        (
            (
                "departure",
                "after New Year",
                "The semantic boundary is unbounded and does not define a finite window.",
            ),
        ),
        (),
        _ASK_DEPARTURE,
    ),
    "dependency": _WorkflowOracle(
        ("anchor_window", "relative_weekend"),
        (date(2026, 10, 5), date(2026, 10, 5), "exact", "October 5"),
        (date(2026, 10, 10), date(2026, 10, 11), "window", "the weekend afterwards"),
        (),
        (),
        _NO_CLARIFICATION,
    ),
    "unsupported": _WorkflowOracle(
        ("unresolved",),
        None,
        None,
        (("departure", "next spring", "manual frozen ambiguity unresolved alternative"),),
        (),
        _ASK_DEPARTURE,
    ),
}


def _load_manifest(path: Path) -> tuple[_ManifestCase, ...]:
    try:
        payload = yaml.safe_load(path.read_bytes())
    except OSError as exc:
        raise SelectorWorkflowFixtureError(f"cannot read selector workflow manifest: {path}") from exc
    except yaml.YAMLError as exc:
        raise SelectorWorkflowFixtureError(f"cannot parse selector workflow manifest: {path}") from exc
    if not isinstance(payload, Mapping) or set(payload) != {"contract_version", "scenarios"}:
        raise SelectorWorkflowFixtureError(
            "selector workflow manifest must contain only contract_version and scenarios"
        )
    if payload["contract_version"] != "v1" or not isinstance(payload["scenarios"], list):
        raise SelectorWorkflowFixtureError("selector workflow manifest must use contract_version v1")
    cases: list[_ManifestCase] = []
    seen: set[str] = set()
    for item in payload["scenarios"]:
        if not isinstance(item, Mapping) or set(item) != {"id", "category", "pair"}:
            raise SelectorWorkflowFixtureError(
                "each selector workflow scenario must contain only id, category, and pair"
            )
        values = tuple(item[key] for key in ("id", "category", "pair"))
        if not all(isinstance(value, str) and value for value in values) or values[0] in seen:
            raise SelectorWorkflowFixtureError("selector workflow scenario labels must be unique non-empty strings")
        seen.add(values[0])
        cases.append(_ManifestCase(*values))

    registry = frozen_selector_case_registry()
    if {case.identifier for case in cases} != set(registry):
        raise SelectorWorkflowFixtureError("selector workflow manifest must exactly cover frozen cases")
    for case in cases:
        private = registry[case.identifier]
        if (case.category, case.pair) != (private.category, private.pair):
            raise SelectorWorkflowFixtureError(
                f"selector workflow manifest labels drifted for {case.identifier!r}"
            )
    return tuple(cases)


def _preflight_selector_workflow_cases(
    manifest_path: Path = DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
) -> _PreparedIntegrationCases:
    """Resolve manifest cases only after frozen-v2 projection preflight succeeds."""

    # This does more than check the private registry: it proves that every catalog used here
    # still projects exactly to the checked-in public v2 selector fixture.
    frozen_cases = preflight_frozen_selector_cases(DEFAULT_FROZEN_SELECTOR_FIXTURES)
    registry = {item.fixture.identifier: item.fixture for item in frozen_cases}
    contract_versions = {item.contract_version for item in frozen_cases}
    if contract_versions != {"v2"}:
        raise SelectorWorkflowFixtureError("selector workflow integration requires frozen v2 fixtures")
    frozen_bytes = DEFAULT_FROZEN_SELECTOR_FIXTURES.read_bytes()
    return _PreparedIntegrationCases(
        cases=tuple(registry[item.identifier] for item in _load_manifest(manifest_path)),
        frozen_fixture_contract_version="v2",
        frozen_fixture_path=DEFAULT_FROZEN_SELECTOR_FIXTURES,
        frozen_fixture_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
    )


def preflight_selector_workflow_cases(
    manifest_path: Path = DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
) -> tuple[FrozenSelectorCase, ...]:
    """Public test helper returning the v2-preflighted private integration catalogs."""

    return _preflight_selector_workflow_cases(manifest_path).cases


def _take_usage(selector: TemporalCandidateSelector) -> dict[str, int] | None:
    if isinstance(selector, _CaptureSelector):
        return selector.take_usage()
    return None


def _reset_capture(selector: TemporalCandidateSelector) -> None:
    if isinstance(selector, _CaptureSelector):
        selector.reset_capture()


def _selector_error_code(exc: BaseException) -> str:
    if isinstance(exc, ValidationError):
        return "selector_parse_failed"
    if isinstance(exc, TemporalSelectionError) and (
        "no parsed" in str(exc) or "unexpected" in str(exc)
    ):
        return "selector_parse_failed"
    if isinstance(exc, TemporalSelectorValidationError):
        return "selector_selection_validation_failed"
    return "selector_or_workflow_failed"


def _workflow_fingerprint(result: RequestUnderstandingResult) -> str:
    """Retain only an opaque proof for forward/reverse equality; never emit workflow dates."""

    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _oracle_selector_output(case: FrozenSelectorCase, model_input: TemporalSelectorInput) -> set[str]:
    """Translate the private oracle to opaque public handles for in-memory evaluation only."""

    oracle = set(case.oracle_candidates)
    return {
        public for public, private in model_input._candidate_handles.items() if private in oracle
    }


def _window_value(
    window: Any,
) -> tuple[date, date, str, str] | None:
    if window is None:
        return None
    return (window.start, window.end, window.precision.value, window.raw_text)


def _workflow_oracle_matches(case: FrozenSelectorCase, result: RequestUnderstandingResult) -> bool:
    """Score the exact private end-to-end outcome without copying it into the artifact."""

    expected = _WORKFLOW_ORACLES.get(case.pair)
    if expected is None:
        raise SelectorWorkflowFixtureError(
            f"selector workflow case {case.identifier!r} has no private workflow oracle"
        )
    parsed = result.parsed_request
    relations = parsed.temporal_relations
    if relations is None or parsed.date_resolution is None:
        return False
    unresolved = tuple(
        (item.field, item.raw_text, item.reason) for item in parsed.date_resolution.unresolved
    )
    conflicts = tuple(
        (item.code, tuple(item.fields), item.detail) for item in parsed.conflicts
    )
    clarification = (
        result.clarification.action.value,
        result.clarification.field,
        result.clarification.question,
        result.clarification.reason or "",
    )
    return (
        tuple(constraint.kind for constraint in relations.constraints) == expected.relation_kinds
        and _window_value(parsed.departure_window) == expected.departure
        and _window_value(parsed.return_window) == expected.return_window
        and unresolved == expected.unresolved
        and conflicts == expected.conflicts
        and clarification == expected.clarification
    )


def _run_case(
    case: FrozenSelectorCase,
    selector: TemporalCandidateSelector,
) -> tuple[dict[str, Any], RequestUnderstandingResult | None]:
    """Run exactly one selector-backed workflow without serializing private catalog state."""

    started = time.perf_counter()
    record: dict[str, Any] = {
        "case": {"id": case.identifier, "category": case.category, "pair": case.pair},
        "oracle": {"selector_matched": False, "workflow_matched": False},
        "selector": {"attempted": False, "public_output": None},
        "workflow": {"completed": False, "pass_one_repairs": 0, "pass_two_repairs": 0},
    }
    # Capture the selector's public output separately before the workflow crosses restoration.
    # This makes one call explicit and prevents an accidental retry from hiding in a workflow
    # wrapper.  The workflow receives a single-use selector proxy below.
    try:
        selector_input_holder: list[TemporalSelectorInput] = []

        class _SingleUseSelector:
            def select_candidates(self, model_input: TemporalSelectorInput) -> TemporalSelectorOutput:
                if selector_input_holder:
                    raise AssertionError("selector workflow integration made more than one selector call")
                selector_input_holder.append(model_input)
                record["selector"]["attempted"] = True
                output = selector.select_candidates(model_input)
                if not isinstance(output, TemporalSelectorOutput):
                    output = TemporalSelectorOutput.model_validate(output)
                record["selector"]["public_output"] = output.selected_candidates
                record["oracle"]["selector_matched"] = (
                    set(output.selected_candidates) == _oracle_selector_output(case, model_input)
                )
                return output

        result = understand_request(
            case.request,
            _StaticNonTemporalExtractor(),
            _ResolverMustNotRun(),
            StaticFrozenHolidayProvider(),
            temporal_strategy="compiler_select_v1",
            temporal_selector=_SingleUseSelector(),
            evaluation_temporal_catalog=case.catalog,
        )
        if len(selector_input_holder) != 1:
            raise AssertionError("selector workflow integration did not make exactly one selector call")
        if result.repair_trace is None:
            raise AssertionError("selector workflow integration did not retain a repair trace")
        record["workflow"] = {
            "completed": True,
            "pass_one_repairs": int(result.repair_trace.pass_one.repair_ran),
            "pass_two_repairs": int(result.repair_trace.pass_two.repair_ran),
            "output_sha256": _workflow_fingerprint(result),
        }
        record["oracle"]["workflow_matched"] = _workflow_oracle_matches(case, result)
        record["status"] = (
            "passed"
            if record["oracle"]["selector_matched"] and record["oracle"]["workflow_matched"]
            else "failed"
        )
        return record, result
    except Exception as exc:  # noqa: BLE001 - preserve independent E2E cases after one failure
        record["status"] = "error"
        record["error_code"] = _selector_error_code(exc)
        return record, None
    finally:
        record["usage"] = _take_usage(selector)
        record["latency_seconds"] = round(time.perf_counter() - started, 3)


def _summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    completed = [item for item in records if item["workflow"]["completed"]]
    return {
        "runs": len(records),
        "completed": len(completed),
        "errors": len(records) - len(completed),
        "selector_oracle_matches": sum(
            bool(item["oracle"]["selector_matched"]) for item in records
        ),
        "workflow_oracle_matches": sum(
            bool(item["oracle"]["workflow_matched"]) for item in records
        ),
        "zero_repairs": all(
            item["workflow"]["pass_one_repairs"] == 0
            and item["workflow"]["pass_two_repairs"] == 0
            for item in records
        ),
        "selector_attempts": sum(bool(item["selector"]["attempted"]) for item in records),
        "latency_seconds": {
            "total": round(sum(float(item["latency_seconds"]) for item in records), 3),
            "mean": round(
                sum(float(item["latency_seconds"]) for item in records) / len(records), 3
            )
            if records
            else 0.0,
        },
    }


def _attach_pair_checks(
    records: list[dict[str, Any]], results: Mapping[str, RequestUnderstandingResult | None]
) -> None:
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_pair[str(record["case"]["pair"])].append(record)
    for pair, paired in by_pair.items():
        if len(paired) != 2:
            raise SelectorWorkflowFixtureError(f"selector workflow pair {pair!r} must have two variants")
        identifiers = [str(item["case"]["id"]) for item in paired]
        first, second = (results[identifier] for identifier in identifiers)
        equal = first is not None and second is not None and first.model_dump(mode="json") == second.model_dump(mode="json")
        for item in paired:
            item["workflow"]["paired_output_match"] = equal


def _default_selector_factory(model: str) -> TemporalCandidateSelector:
    return OpenAIIntentExtractor(config=OpenAIExtractorConfig(model=model))


def run_selector_workflow_integration_eval(
    *,
    selector_model: str,
    manifest_path: Path = DEFAULT_SELECTOR_WORKFLOW_MANIFEST,
    trials: int = 1,
    selector_factory: SelectorFactory | None = None,
) -> dict[str, Any]:
    """Exercise the selected model through selector restoration and the real compiler workflow."""

    if not selector_model:
        raise ValueError("selector_model must be an explicit non-empty model ID")
    if trials < 1:
        raise ValueError("trials must be positive")
    prepared = _preflight_selector_workflow_cases(manifest_path)
    cases = prepared.cases
    selector = (selector_factory or _default_selector_factory)(selector_model)
    records: list[dict[str, Any]] = []
    for trial in range(1, trials + 1):
        results: dict[str, RequestUnderstandingResult | None] = {}
        trial_records: list[dict[str, Any]] = []
        for case in cases:
            _reset_capture(selector)
            record, result = _run_case(case, selector)
            record["trial"] = trial
            trial_records.append(record)
            results[case.identifier] = result
        _attach_pair_checks(trial_records, results)
        records.extend(trial_records)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation": "selector_workflow_integration_test_only",
        "manifest": {
            "path": str(manifest_path),
            "sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
        "frozen_selector_fixture": {
            "path": str(prepared.frozen_fixture_path),
            "sha256": prepared.frozen_fixture_sha256,
            "contract_version": prepared.frozen_fixture_contract_version,
        },
        "selector_model": selector_model,
        "scenario_count": len(cases),
        "trials": trials,
        "summary": _summary(records),
        "results": records,
    }
