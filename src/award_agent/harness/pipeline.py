"""Thin local orchestration of the existing planning, provider, and output stages."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal, cast
from uuid import uuid4

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import ClarificationSession, ClarificationSessionStatus, LocationKind
from award_agent.providers.contracts import ExecutionPolicy, ProviderCapability, ProviderResultSet
from award_agent.providers.execution import execute_provider_plan, validate_result_attachment
from award_agent.providers.gfly import GflyAdapter
from award_agent.providers.replay import RecordingAdapter, ReplayAdapter, ReplayTape
from award_agent.providers.seats_aero import SeatsAeroAdapter
from award_agent.providers.transport import SubprocessTransport
from award_agent.ranking import assemble_matched_journeys
from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.project_solutions import project_solutions
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.ranking.style_contracts import (
    CurrencyConversionSnapshot,
    RankedJourneySet,
    RankingStylePolicy,
)
from award_agent.ranking.styles import assign_journey_styles
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIResultsWriter
from award_agent.results.contracts import (
    CheckFinding,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
)
from award_agent.results.core import run_results
from award_agent.search_planning.airport_selection_policy import (
    context_for_resolved_location,
    load_default_airport_selection_cap_policy,
)
from award_agent.search_planning.airport_selector import (
    REFINED_AIRPORT_SELECTOR_PROMPT,
    AirportSelectorModelInput,
    OpenAIAirportSelector,
    OpenAIAirportSelectorConfig,
    airport_selection_record_digest,
    validate_airport_selection_proposal,
)
from award_agent.search_planning.compilation_contracts import (
    CompiledSearchPlan,
    DirectGroundingSource,
    M2ASelectionRecordSource,
    SearchPlanningInput,
    SearchPlanningResult,
    SelectionRecordIdBinding,
)
from award_agent.search_planning.contracts import (
    LocationResolutionStatus,
    PlanningInputEnvelope,
    PlanningSource,
    ResolvedLocation,
    SelectedAirport,
)
from award_agent.search_planning.distance_consistency import CityAirportDistanceConsistency
from award_agent.search_planning.gateway_discovery import (
    GatewayDiscoveryGeneratorConfiguration,
    GatewayDiscoveryInput,
    discover_gateway_candidates,
    replay_gateway_discovery_result,
)
from award_agent.search_planning.gateway_generator import (
    DEFAULT_GATEWAY_GENERATOR_PROMPT,
    GATEWAY_GENERATOR_ADAPTER_VERSION,
    GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
    GatewayOutboundDateContext,
    OpenAIGatewayGenerator,
    OpenAIGatewayGeneratorConfig,
)
from award_agent.search_planning.knowledge import (
    CatalogKnowledgeRepository,
    normalize_location_alias,
)
from award_agent.search_planning.locations import ground_endpoint
from award_agent.search_planning.market_policy import load_default_planning_market_policy
from award_agent.search_planning.planner import effective_request_digest, plan_searches
from award_agent.search_planning.policy import PlanningPolicy


@dataclass(frozen=True)
class HarnessSettings:
    catalog_path: Path = Path("data/search_planning/catalogs/m1a-3cb7981519612945")
    selector_model: str = "gpt-5.6-luna"
    gateway_model: str = "gpt-5.6-luna"
    provider_settings_path: Path = Path("data/provider_capabilities/provider-stage-current.json")
    fx_path: Path = Path("data/ranking/m2/fx-2026-09-29.json")
    gfly_executable: Path = Path("/private/tmp/gfly-live-py312/bin/python")


@dataclass(frozen=True)
class PlanningRun:
    planning_input: SearchPlanningInput
    result: SearchPlanningResult
    bundle: ProviderInputBundle | None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderRun:
    result: ProviderResultSet
    tape: ReplayTape | None
    evidence_files: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class RankingRun:
    matched: MatchedJourneySet
    ranked: RankedJourneySet
    projection: SolutionProjection


def session_binding(session: ClarificationSession) -> tuple[str, int, str]:
    return (session.session_id, session.current_revision.revision,
            effective_request_digest(session.effective_request))


def _provider_settings(settings: HarnessSettings) -> tuple[ExecutionPolicy, ProviderCapability, ProviderCapability]:
    source = json.loads(settings.provider_settings_path.read_text())
    return (
        ExecutionPolicy.model_validate(source["policy"]),
        ProviderCapability.model_validate(source["award_capability"]),
        ProviderCapability.model_validate(source["cash_capability"]),
    )


def _bundle(plan: CompiledSearchPlan, session: ClarificationSession,
            provider_settings: tuple[ExecutionPolicy, ProviderCapability, ProviderCapability]
            ) -> ProviderInputBundle:
    policy, award_capability, cash_capability = provider_settings
    return ProviderInputBundle(
        plan=plan, current_session_id=session.session_id,
        current_revision=session.current_revision.revision,
        current_effective_request=session.effective_request,
        expected_compilation_binding_digest=plan.identity.compilation_binding_digest,
        run_id=f"harness:{uuid4().hex}",
        policy=policy,
        award_capability=award_capability,
        cash_capability=cash_capability,
    )


def plan_session(session: ClarificationSession, settings: HarnessSettings) -> PlanningRun:
    if session.status is not ClarificationSessionStatus.READY:
        raise ValueError(f"planning requires a ready clarification session; got {session.status.value}")
    provider_settings = _provider_settings(settings)
    started = perf_counter()
    request = session.effective_request
    cap_policy = load_default_airport_selection_cap_policy()
    planning_policy = PlanningPolicy()
    distance_policy = CityAirportDistanceConsistency(policy_version="city-airport-distance-consistency-v1")
    market_policy = load_default_planning_market_policy()
    selections = []
    bindings = []
    selector_calls = 0
    selector_tokens = 0
    selector_usage_missing = False
    endpoints: dict[str, list[SelectedAirport]] = {"origin": [], "destination": []}
    with CatalogKnowledgeRepository(settings.catalog_path) as repository:
        for role, locations in (("origin", request.origins), ("destination", request.destinations)):
            for location in locations:
                if location.kind is LocationKind.AIRPORT:
                    grounded = ground_endpoint(location, role, repository, planning_policy)
                    if grounded.selection is None:
                        raise ValueError(f"{role} airport {location.value} could not be grounded: {grounded.issues}")
                    endpoints[role].extend(grounded.selection.airports)
                    continue
                normalized = normalize_location_alias(location.value)
                candidates = repository.resolve_entities(location.kind, normalized)
                if len(candidates) != 1:
                    raise ValueError(f"{role} {location.value}: expected one catalog entity, found {len(candidates)}")
                entity = candidates[0]
                context = context_for_resolved_location(ResolvedLocation(
                    location=location, status=LocationResolutionStatus.RESOLVED,
                    normalized_alias=normalized, resolved_entity_id=entity.entity_id,
                    evidence_source_ids=entity.source_ids, candidate_ids=(entity.entity_id,)), repository)
                selector = OpenAIAirportSelector(OpenAIAirportSelectorConfig(
                    model=settings.selector_model, prompt=REFINED_AIRPORT_SELECTOR_PROMPT))
                proposal = selector.propose(AirportSelectorModelInput.from_context(
                    context, cap_policy.applicable_cap_for(context)))
                selector_calls += 1
                take_usage = getattr(selector, "take_usage", None)
                usage = take_usage() if callable(take_usage) else None
                if isinstance(usage, dict) and usage.get("missing_calls", 0) == 0:
                    selector_tokens += int(usage.get("total_tokens", 0))
                else:
                    selector_usage_missing = True
                record = validate_airport_selection_proposal(
                    role=cast(Literal["origin", "destination"], role), context=context, cap_policy=cap_policy,
                    distance_policy=distance_policy, proposal=proposal,
                    model=settings.selector_model,
                    prompt_version=REFINED_AIRPORT_SELECTOR_PROMPT.version,
                    repository=repository)
                if not record.accepted_airports:
                    raise ValueError(f"M2A selected no accepted {role} airports for {location.value}")
                selections.append(record)
                endpoints[role].extend(record.accepted_airports)
                bindings.append(SelectionRecordIdBinding(
                    upstream_record_id=f"m2a:{session.session_id}:{role}:{entity.entity_id}",
                    record_digest=airport_selection_record_digest(record)))
        window = request.departure_window
        assert window is not None
        gateway_input = GatewayDiscoveryInput(
            origin_endpoints=tuple(endpoints["origin"]),
            destination_endpoints=tuple(endpoints["destination"]),
            outbound_date=GatewayOutboundDateContext(
                start=window.start, end=window.end, timezone=request.context.timezone,
                effective_window_precision=window.precision.value),
            upstream_selection_record_ids=tuple(item.upstream_record_id for item in bindings),
            upstream_selection_record_digests=tuple(sorted(item.record_digest for item in bindings)))
        gateway = discover_gateway_candidates(
            discovery_input=gateway_input, policy=market_policy, repository=repository,
            generator_factory=lambda: OpenAIGatewayGenerator(
                OpenAIGatewayGeneratorConfig(model=settings.gateway_model)),
            generator_configuration=GatewayDiscoveryGeneratorConfiguration(
                model=settings.gateway_model,
                prompt_version=DEFAULT_GATEWAY_GENERATOR_PROMPT.version,
                response_schema_sha256=GATEWAY_GENERATOR_RESPONSE_SCHEMA_SHA256,
                adapter_version=GATEWAY_GENERATOR_ADAPTER_VERSION))
        replay_gateway_discovery_result(record=gateway, policy=market_policy, repository=repository)
        planning_input = SearchPlanningInput(
            envelope=PlanningInputEnvelope(source=PlanningSource(
                session_id=session.session_id, revision=session.current_revision.revision),
                effective_request=request),
            endpoint_source=M2ASelectionRecordSource(selection_records=tuple(selections))
            if selections else DirectGroundingSource(),
            upstream_selection_id_bindings=tuple(bindings), gateway_discovery_result=gateway)
        if selections:
            result = plan_searches(planning_input, repository=repository,
                policy=planning_policy, market_policy=market_policy,
                selection_cap_policy=cap_policy,
                selection_distance_policy=distance_policy)
        else:
            result = plan_searches(planning_input, repository=repository,
                policy=planning_policy, market_policy=market_policy)
    bundle = _bundle(result.plan, session, provider_settings) if result.plan else None
    gateway_usage = gateway.generator_invocation.usage if gateway.generator_invocation else None
    gateway_called = gateway.generation_status.value != "not_attempted"
    gateway_tokens = (
        gateway_usage.get("total_tokens", "unknown") if gateway_usage
        else ("unknown" if gateway_called else 0)
    )
    diagnostics = (
        f"m2a_selector_calls={selector_calls}",
        f"m2a_selector_total_tokens={selector_tokens if not selector_usage_missing else 'unknown'}",
        f"m2b_generator_calls={int(gateway_called)}",
        f"m2b_generator_total_tokens={gateway_tokens}",
        f"planning_elapsed_seconds={perf_counter() - started:.3f}",
        *(str(issue) for issue in result.issues),
    )
    return PlanningRun(planning_input, result, bundle, diagnostics)


def _live_preflight(bundle: ProviderInputBundle, settings: HarnessSettings) -> tuple[str, Path]:
    key = os.environ.get("SEATS_AERO_API_KEY", "")
    if not key:
        raise ValueError("set SEATS_AERO_API_KEY for live provider acquisition")
    wrapper = Path(__file__).resolve().parents[3] / "scripts/gfly_compat.py"
    if not wrapper.is_file():
        raise ValueError("reviewed gfly compatibility launcher is missing")
    if not bundle.award_capability.reviewed or not bundle.cash_capability.reviewed:
        raise ValueError("live acquisition requires reviewed provider capabilities")
    if (bundle.award_capability.version, bundle.award_capability.backend,
        bundle.award_capability.operation) != ("cached-search-v1", "partnerapi", "cached_search"):
        raise ValueError("award capability does not match the reviewed adapter")
    if (bundle.cash_capability.version, bundle.cash_capability.backend,
        bundle.cash_capability.operation) != (
            "0.3.0+award-search-unpriced-party-echo-v2", "google", "search"):
        raise ValueError("cash capability does not match the reviewed compatibility launcher")
    version = SubprocessTransport().run(
        [str(settings.gfly_executable), str(wrapper), "version", "--json"],
        timeout_seconds=5, max_response_bytes=4096)
    if version.exit_code != 0 or json.loads(version.stdout).get("version") != bundle.cash_capability.version:
        raise ValueError("gfly command does not match reviewed capability version")
    return key, wrapper


def acquire(bundle: ProviderInputBundle, settings: HarnessSettings,
            tape: ReplayTape | None = None) -> ProviderRun:
    key, wrapper = ("offline-unused", None) if tape is not None else _live_preflight(bundle, settings)
    with TemporaryDirectory(prefix="award-harness-") as temporary:
        evidence_root = Path(temporary)
        award_parser = SeatsAeroAdapter(
            api_key=key, evidence_root=evidence_root,
            provider_version=bundle.award_capability.version)
        cash_parser = GflyAdapter(
            evidence_root=evidence_root,
            executable=str(settings.gfly_executable) if wrapper else "gfly",
            wrapper=str(wrapper) if wrapper else None,
            provider_version=bundle.cash_capability.version)
        award = ReplayAdapter(award_parser, tape) if tape is not None else RecordingAdapter(award_parser)
        cash = ReplayAdapter(cash_parser, tape) if tape is not None else RecordingAdapter(cash_parser)
        with CatalogKnowledgeRepository(settings.catalog_path) as repository:
            result = execute_provider_plan(
                bundle.plan, award_adapter=award, cash_adapter=cash,
                timezone_repository=repository,
                run_id=bundle.run_id, current_session_id=bundle.current_session_id,
                current_revision=bundle.current_revision,
                current_effective_request=bundle.current_effective_request,
                expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
                policy=bundle.policy, award_capability=bundle.award_capability,
                cash_capability=bundle.cash_capability)
        if result.status != "stale":
            result = validate_result_attachment(bundle.plan, result,
                current_session_id=bundle.current_session_id,
                current_revision=bundle.current_revision,
                current_effective_request=bundle.current_effective_request,
                expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
                policy=bundle.policy, award_capability=bundle.award_capability,
                cash_capability=bundle.cash_capability)
        if tape is None:
            assert isinstance(award, RecordingAdapter) and isinstance(cash, RecordingAdapter)
            recorded = ReplayTape(entries=tuple(award.entries + cash.entries))
        else:
            recorded = tape
        files = {path.relative_to(evidence_root).as_posix(): path.read_bytes()
                 for path in evidence_root.rglob("*") if path.is_file()}
        return ProviderRun(result=result, tape=recorded, evidence_files=files)


def rank(bundle: ProviderInputBundle, result: ProviderResultSet,
         settings: HarnessSettings) -> RankingRun:
    matched = assemble_matched_journeys(bundle.plan, result,
        current_session_id=bundle.current_session_id,
        current_revision=bundle.current_revision,
        current_effective_request=bundle.current_effective_request,
        expected_compilation_binding_digest=bundle.expected_compilation_binding_digest,
        policy=bundle.policy, award_capability=bundle.award_capability,
        cash_capability=bundle.cash_capability)
    snapshot = CurrencyConversionSnapshot.model_validate_json(settings.fx_path.read_bytes())
    ranked = assign_journey_styles(matched, policy=RankingStylePolicy(), fx_snapshot=snapshot)
    return RankingRun(matched, ranked, project_solutions(ranked))


class _FrozenWriter:
    def __init__(self, draft: ResultsDocument, correction: ResultsDocument | None) -> None:
        self.draft, self.correction = draft, correction

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: ResultsDocument | None = None) -> ResultsDocument:
        return (self.correction or self.draft) if previous_document is not None else self.draft


def author(projection: SolutionProjection, config: ResultsConfig,
           draft: ResultsDocument | None = None,
           correction: ResultsDocument | None = None) -> ResultsArtifact:
    if correction is not None and draft is None:
        raise ValueError("a corrected document requires an initial draft")
    if draft is None:
        return run_results(projection, config, OpenAIResultsWriter(),
                           input_measurer=OpenAIResultsInputMeasurer())
    return run_results(projection, config, _FrozenWriter(draft, correction))


def acquire_and_rank(bundle: ProviderInputBundle, settings: HarnessSettings,
                     tape: ReplayTape | None = None
                     ) -> Iterator[tuple[Literal["providers", "ranking"], ProviderRun | RankingRun]]:
    """Yield each completed stage so a local UI can retain partial evidence."""
    providers = acquire(bundle, settings, tape)
    yield "providers", providers
    if providers.result.status == "stale":
        return
    yield "ranking", rank(bundle, providers.result, settings)


def run_from_ready(session: ClarificationSession, settings: HarnessSettings,
                   config: ResultsConfig
                   ) -> Iterator[tuple[Literal["planning", "providers", "ranking", "results"],
                                       PlanningRun | ProviderRun | RankingRun | ResultsArtifact]]:
    """Run the complete local workflow from an authoritative ready session."""
    planning = plan_session(session, settings)
    yield "planning", planning
    if planning.bundle is None:
        return
    providers = acquire(planning.bundle, settings)
    yield "providers", providers
    if providers.result.status == "stale":
        return
    ranking = rank(planning.bundle, providers.result, settings)
    yield "ranking", ranking
    yield "results", author(ranking.projection, config)
