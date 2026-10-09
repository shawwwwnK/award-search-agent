"""Offline checks for the local end-to-end harness boundary."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import (
    ClarificationSession,
    ClarificationSessionStatus,
    DateWindow,
    DateWindowPrecision,
    EffectiveRequest,
    LocationKind,
    LocationRef,
    RequestContext,
    SearchMode,
)
from award_agent.harness import pipeline
from award_agent.harness.pipeline import (
    HarnessSettings,
    ProviderRun,
    RankingRun,
    acquire_and_rank,
    author,
    plan_session,
    rank,
    run_from_ready,
)
from award_agent.providers.replay import ReplayTape
from award_agent.results.contracts import ResultsArtifact, ResultsConfig, ResultsDocument
from award_agent.search_planning.airport_selector import (
    AirportSelectionProposal,
    AirportSelectionProposalOutcome,
)
from award_agent.search_planning.gateway_generator import GatewayCandidateProposal

ROOT = Path(__file__).resolve().parents[2]
SAVED = ROOT / "evidence/provider-stage/saved-searches/runs/sfo_to_bkk_positioning"
RESULTS = ROOT / "evidence/results-stage/m2"


def _session(destination_kind: LocationKind = LocationKind.AIRPORT,
             named_origin: bool = False) -> ClarificationSession:
    destination = "NRT" if destination_kind is LocationKind.AIRPORT else "Japan"
    origin = "San Francisco International Airport" if named_origin else "SFO"
    request = EffectiveRequest(
        raw_text="offline harness planning fixture",
        context=RequestContext(reference_date=date(2026, 9, 19), timezone="America/Los_Angeles"),
        travelers=2,
        origins=(LocationRef(kind=LocationKind.AIRPORT, value=origin, raw_text=origin),),
        destinations=(LocationRef(kind=destination_kind, value=destination, raw_text=destination),),
        departure_window=DateWindow(start=date(2026, 11, 2), end=date(2026, 11, 4),
                                    precision=DateWindowPrecision.WINDOW, raw_text="November 2-4"),
        search_modes=(SearchMode.AWARD,),
    )
    return cast(ClarificationSession, SimpleNamespace(
        status=ClarificationSessionStatus.READY, session_id="harness-test",
        current_revision=SimpleNamespace(revision=0), effective_request=request))


class _Gateway:
    def __init__(self, _config: object) -> None:
        pass

    def propose(self, _model_input: object) -> GatewayCandidateProposal:
        return GatewayCandidateProposal.model_validate({
            "endpoint_market_assessments": [], "origin_access_gateways": [],
            "destination_access_gateways": [], "intermediate_hubs": []})


class _Selector:
    def __init__(self, _config: object) -> None:
        pass

    def propose(self, _model_input: object) -> AirportSelectionProposal:
        return AirportSelectionProposal(
            outcome=AirportSelectionProposalOutcome.PROPOSED,
            airport_iata_codes=("NRT",))


def test_planning_requires_ready_session_before_model_or_catalog() -> None:
    session = cast(ClarificationSession, SimpleNamespace(
        status=ClarificationSessionStatus.AWAITING_ANSWER))
    with pytest.raises(ValueError, match="ready clarification session"):
        plan_session(session, HarnessSettings(catalog_path=Path("missing")))


@pytest.mark.parametrize("destination_kind,named_origin", [
    (LocationKind.AIRPORT, False), (LocationKind.COUNTRY, False),
    (LocationKind.AIRPORT, True),
])
def test_planning_compiles_direct_and_m2a_endpoints_offline(
    monkeypatch: pytest.MonkeyPatch, destination_kind: LocationKind, named_origin: bool,
) -> None:
    monkeypatch.setattr(pipeline, "OpenAIGatewayGenerator", _Gateway)
    monkeypatch.setattr(pipeline, "OpenAIAirportSelector", _Selector)
    session = _session(destination_kind, named_origin)
    planned = plan_session(session, HarnessSettings())
    assert planned.bundle is not None
    assert planned.result.plan is not None
    assert planned.bundle.current_effective_request == session.effective_request
    assert planned.bundle.plan.identity.session_id == session.session_id
    assert planned.bundle.plan.identity.revision == 0
    if destination_kind is LocationKind.COUNTRY:
        assert planned.planning_input.endpoint_source.source_kind == "m2a_replay"
    else:
        assert planned.planning_input.endpoint_source.source_kind == "direct_grounding"


def test_provider_config_preflight_precedes_model_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(pipeline, "OpenAIGatewayGenerator", lambda *_: pytest.fail("model called"))
    bad_settings = HarnessSettings(provider_settings_path=tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        plan_session(_session(), bad_settings)


def test_live_provider_preflight_uses_selected_reviewed_interpreter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = ProviderInputBundle.model_validate_json((SAVED / "bundle.json").read_bytes())
    selected = Path("/private/tmp/gfly-live-py312/bin/python")
    settings = HarnessSettings(gfly_executable=selected)
    commands: list[list[str]] = []

    def fake_run(_transport: object, command: list[str], **_kwargs: object) -> SimpleNamespace:
        commands.append(command)
        return SimpleNamespace(exit_code=0, stdout=(
            '{"version":"0.3.0+award-search-unpriced-party-echo-v2"}'))

    monkeypatch.setenv("SEATS_AERO_API_KEY", "fixture-key")
    monkeypatch.setattr(pipeline.SubprocessTransport, "run", fake_run)
    key, wrapper = pipeline._live_preflight(bundle, settings)
    assert key == "fixture-key"
    assert commands == [[str(selected), str(wrapper), "version", "--json"]]


def test_run_from_ready_yields_stages_and_stops_on_no_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    settings = HarnessSettings()
    config = ResultsConfig.model_validate_json((RESULTS / "offline-config.json").read_bytes())
    bundle = ProviderInputBundle.model_validate_json((SAVED / "bundle.json").read_bytes())
    calls: list[str] = []
    planning = SimpleNamespace(bundle=bundle)
    provider = SimpleNamespace(result=SimpleNamespace(status="completed"))
    ranking = SimpleNamespace(projection=object())
    def stage(name: str, value: object) -> object:
        calls.append(name)
        return value

    monkeypatch.setattr(pipeline, "plan_session", lambda *_: stage("plan", planning))
    monkeypatch.setattr(pipeline, "acquire", lambda *_: stage("acquire", provider))
    monkeypatch.setattr(pipeline, "rank", lambda *_: stage("rank", ranking))
    monkeypatch.setattr(pipeline, "author", lambda *_: stage("author", object()))
    assert [name for name, _ in run_from_ready(session, settings, config)] == [
        "planning", "providers", "ranking", "results"]
    assert calls == ["plan", "acquire", "rank", "author"]
    planning.bundle = None
    calls.clear()
    assert [name for name, _ in run_from_ready(session, settings, config)] == ["planning"]
    assert calls == ["plan"]


def test_provider_replay_ranking_results_and_binding_rejection() -> None:
    bundle = ProviderInputBundle.model_validate_json((SAVED / "bundle.json").read_bytes())
    tape = ReplayTape.model_validate_json((SAVED / "tape.json").read_bytes())
    settings = HarnessSettings()
    stages = dict(acquire_and_rank(bundle, settings, tape))
    provider = cast(ProviderRun, stages["providers"])
    ranking = cast(RankingRun, stages["ranking"])
    assert provider.result.status in {"completed", "partial"}
    assert provider.tape == tape
    assert ranking.projection.view.alternatives
    config = ResultsConfig.model_validate_json((RESULTS / "offline-config.json").read_bytes())
    draft = ResultsDocument.model_validate_json(
        (RESULTS / "sfo_to_bkk_positioning.annotated.initial.draft.json").read_bytes())
    correction = ResultsDocument.model_validate_json(
        (RESULTS / "sfo_to_bkk_positioning.annotated.correction.draft.json").read_bytes())
    artifact = author(ranking.projection, config, draft, correction)
    assert isinstance(artifact, ResultsArtifact)
    assert artifact.delivery_outcome == "delivered"

    stale_bundle = bundle.model_copy(update={"current_revision": bundle.current_revision + 1})
    with pytest.raises(ValueError):
        rank(stale_bundle, provider.result, settings)
