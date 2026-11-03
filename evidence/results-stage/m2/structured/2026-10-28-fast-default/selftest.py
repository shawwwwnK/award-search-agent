"""Offline call-capture and budget sanity check; no API client is constructed."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import freeze
import ledger
import run as run_module
from run import RecordingMeasurer, RecordingWriter
from run import _invoke_results_profile, _profile_kwargs, run as run_experiment


def _offline_live_summary_control() -> None:
    """Exercise _run_live persistence/replay with captured artifacts and fake clients."""
    from types import SimpleNamespace

    from award_agent.results.default import DEFAULT_RESULTS_PROFILE
    from award_agent.results.focused import parse_focused_artifact

    fixture_dir = run_module.HERE / "runs/confirm-v27-default-1-admitted"
    artifact = parse_focused_artifact((fixture_dir / "artifact.json").read_bytes())
    case = "admitted"
    source_path = run_module.SOURCE / case / "artifact.json"
    config_path = run_module.SOURCE / case / "config.json"
    campaign = ledger.campaign()

    owned_clients = []

    class FakeOwnedClient:
        def __init__(self, *, max_retries: int, timeout: float) -> None:
            assert max_retries == 0 and timeout == campaign["timeout_seconds"]
            self.closed = False
            owned_clients.append(self)

        def __enter__(self) -> "FakeOwnedClient":
            return self

        def __exit__(self, *_exc: object) -> None:
            self.closed = True

    class SavedMeasurer:
        def __init__(self, receipts: list[object]) -> None:
            self.receipts = iter(receipts)

        def measure(self, _request: object, _config: object) -> object:
            return next(self.receipts)

    class SavedWriter:
        def __init__(self, passes: list[object]) -> None:
            self.passes = iter(passes)
            self.pending = None

        def author(self, _request: object, _config: object, _settings: object) -> str:
            item = next(self.passes)
            self.pending = item.writer_receipt
            assert isinstance(item.raw_wire, str)
            return item.raw_wire

        def take_receipt(self) -> object:
            receipt, self.pending = self.pending, None
            return receipt

    original = {
        "here": run_module.HERE,
        "snapshot_paths": run_module.snapshot_paths,
        "invoke": run_module._invoke_results_profile,
        "openai": run_module.OpenAI,
        "campaign": ledger.CAMPAIGN,
        "calls": ledger.CALLS,
    }
    import award_agent.results.adapter as adapter_module
    import award_agent.results.interactive_adapter as interactive_module
    original_measurer = adapter_module.OpenAIResultsInputMeasurer
    original_writer = interactive_module.OpenAIInteractiveResultsWriter
    try:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            harness_dir = root / "harness"
            harness_dir.mkdir()
            calls_dir = root / "calls"
            calls_dir.mkdir()
            campaign_path = root / "campaign.json"
            campaign_path.write_text(json.dumps(campaign), encoding="utf-8")
            run_module.HERE = harness_dir
            ledger.CAMPAIGN = campaign_path
            ledger.CALLS = calls_dir
            run_module.OpenAI = FakeOwnedClient
            run_module.snapshot_paths = lambda _case: [
                Path(run_module.__file__).resolve(), Path(__file__).resolve(),
                source_path, config_path, run_module.DEFAULT_CONFIG]
            adapter_module.OpenAIResultsInputMeasurer = lambda client: SimpleNamespace(
                _client=client)
            interactive_module.OpenAIInteractiveResultsWriter = lambda client: SimpleNamespace(
                _client=client)

            def invoke_saved(projection: object, config: object, writer: object,
                             measurer: object, profile: str) -> object:
                assert profile == DEFAULT_RESULTS_PROFILE
                assert writer.delegate._client is measurer.delegate._client
                count_passes = [item for item in artifact.passes
                                if item.input_token_receipt is not None]
                writer_passes = [item for item in artifact.passes if item.writer_called]
                assert len(count_passes) == len(writer_passes) == 2
                measurer.delegate = SavedMeasurer(
                    [item.input_token_receipt for item in count_passes])
                writer.delegate = SavedWriter(writer_passes)
                for item in artifact.passes:
                    if item.input_token_receipt is not None:
                        measurer.measure(item.request, config)
                    if item.writer_called:
                        settings = (artifact.selector_settings if item.phase == "selection" else
                                    artifact.composer_settings)
                        writer.author(item.request, config, settings)
                        assert writer.take_receipt() == item.writer_receipt
                return artifact

            run_module._invoke_results_profile = invoke_saved
            summary = run_module._run_live(
                case, "offline-summary-route", DEFAULT_RESULTS_PROFILE,
                source_path, config_path, None, False)
            saved_dir = harness_dir / "runs/offline-summary-route"
            saved_summary = ledger.read_json(saved_dir / "summary.json")
            assert summary == saved_summary
            assert (summary["count_calls"], summary["generation_calls"],
                    summary["live_calls"]) == (2, 2, 4)
            assert all((saved_dir / f"pass-{index:02d}" / "count-request.json").exists()
                       for index in (1, 2))
            assert all((saved_dir / f"pass-{index:02d}" / "generation-request.json").exists()
                       for index in (1, 2))
            assert ledger.read_json(saved_dir / "verification-receipt.json")["passed"] is True
            assert not (saved_dir / "run-error.json").exists()
            assert len(owned_clients) == 1 and owned_clients[0].closed is True
    finally:
        run_module.HERE = original["here"]
        run_module.snapshot_paths = original["snapshot_paths"]
        run_module._invoke_results_profile = original["invoke"]
        run_module.OpenAI = original["openai"]
        ledger.CAMPAIGN = original["campaign"]
        ledger.CALLS = original["calls"]
        adapter_module.OpenAIResultsInputMeasurer = original_measurer
        interactive_module.OpenAIInteractiveResultsWriter = original_writer


def main() -> int:
    from award_agent.providers.contracts import content_digest
    from award_agent.results.contracts import InputTokenReceipt, ResultsConfig, WriterReceipt
    from award_agent.results.default import DEFAULT_RESULTS_PROFILE
    from award_agent.results.interactive_contracts import InteractiveSettings

    # Keep live campaign routing on the public default API while explicit
    # historical profiles continue to call the focused runner directly.
    route_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def public_default(*args: object, **kwargs: object) -> str:
        route_calls.append(("default", args, kwargs))
        return "public-default"

    def focused(*args: object, **kwargs: object) -> str:
        route_calls.append(("focused", args, kwargs))
        return "focused-explicit"

    route_args = (object(), object(), object(), object())
    assert _invoke_results_profile(*route_args, DEFAULT_RESULTS_PROFILE,
                                   default_runner=public_default,
                                   focused_runner=focused) == "public-default"
    assert route_calls == [("default", route_args, {})]
    route_calls.clear()
    explicit_profile = "focused-v6" if DEFAULT_RESULTS_PROFILE != "focused-v6" else "focused-v5"
    assert _invoke_results_profile(*route_args, explicit_profile,
                                   default_runner=public_default,
                                   focused_runner=focused) == "focused-explicit"
    assert route_calls == [("focused", route_args, _profile_kwargs(explicit_profile))]

    class FakeOpenAIClient:
        def __init__(self, *, max_retries: int, timeout: float) -> None:
            assert max_retries == 0 and timeout == 12.5
            self.closed = False

        def __enter__(self) -> "FakeOpenAIClient":
            return self

        def __exit__(self, *_exc: object) -> None:
            self.closed = True

    original_openai = run_module.OpenAI
    run_module.OpenAI = FakeOpenAIClient
    client_seen: list[FakeOpenAIClient] = []
    try:
        result = run_module._with_openai_client(12.5, lambda client: (
            client_seen.append(client) or ("completed" if not client.closed else "closed")))
    finally:
        run_module.OpenAI = original_openai
    assert result == "completed" and len(client_seen) == 1
    assert client_seen[0].closed is True
    _offline_live_summary_control()

    request: dict[str, object] = {"model": "gpt-6-luna", "input": "fixture"}
    offline = run_experiment("admitted", "diagnostic-dry-run", profile="focused-v6",
                             recovery_diagnostic=True)
    assert offline["live_calls"] == 0 and offline["recovery_diagnostic"] is True
    v11 = run_experiment("admitted", "v11-diagnostic-dry-run", profile="focused-v11",
                         recovery_diagnostic=True)
    assert v11["live_calls"] == 0 and v11["recovery_diagnostic"] is True
    v12 = run_experiment("admitted", "v12-diagnostic-dry-run", profile="focused-v12",
                         recovery_diagnostic=True)
    assert v12["live_calls"] == 0 and v12["recovery_diagnostic"] is True
    v13 = run_experiment("admitted", "v13-diagnostic-dry-run", profile="focused-v13",
                         recovery_diagnostic=True)
    assert v13["live_calls"] == 0 and v13["recovery_diagnostic"] is True
    v14 = run_experiment("admitted", "v14-diagnostic-dry-run", profile="focused-v14",
                         recovery_diagnostic=True)
    assert v14["live_calls"] == 0 and v14["recovery_diagnostic"] is True
    v15 = run_experiment("admitted", "v15-diagnostic-dry-run", profile="focused-v15",
                         recovery_diagnostic=True)
    assert v15["live_calls"] == 0 and v15["recovery_diagnostic"] is True
    v19 = run_experiment("admitted", "v19-diagnostic-dry-run", profile="focused-v19",
                         recovery_diagnostic=True)
    assert v19["live_calls"] == 0 and v19["recovery_diagnostic"] is True
    v20 = run_experiment("admitted", "v20-diagnostic-dry-run", profile="focused-v20",
                         recovery_diagnostic=True)
    assert v20["live_calls"] == 0 and v20["recovery_diagnostic"] is True
    v21 = run_experiment("admitted", "v21-diagnostic-dry-run", profile="focused-v21",
                         recovery_diagnostic=True)
    assert v21["live_calls"] == 0 and v21["recovery_diagnostic"] is True
    v22 = run_experiment("admitted", "v22-diagnostic-dry-run", profile="focused-v22",
                         recovery_diagnostic=True)
    assert v22["live_calls"] == 0 and v22["recovery_diagnostic"] is True
    v23 = run_experiment("conditional", "v23-diagnostic-dry-run", profile="focused-v23",
                         recovery_diagnostic=True)
    assert v23["live_calls"] == 0 and v23["recovery_diagnostic"] is True
    v24 = run_experiment("incomplete", "v24-diagnostic-dry-run", profile="focused-v24",
                         recovery_diagnostic=True)
    assert v24["live_calls"] == 0 and v24["recovery_diagnostic"] is True
    v25 = run_experiment("incomplete", "v25-diagnostic-dry-run", profile="focused-v25",
                         recovery_diagnostic=True)
    assert v25["live_calls"] == 0 and v25["recovery_diagnostic"] is True
    v26 = run_experiment("incomplete", "v26-diagnostic-dry-run", profile="focused-v26",
                         recovery_diagnostic=True)
    assert v26["live_calls"] == 0 and v26["recovery_diagnostic"] is True
    v27 = run_experiment("incomplete", "v27-diagnostic-dry-run", profile="focused-v27",
                         recovery_diagnostic=True)
    assert v27["live_calls"] == 0 and v27["recovery_diagnostic"] is True
    v28 = run_experiment("incomplete", "v28-diagnostic-dry-run", profile="focused-v28",
                         recovery_diagnostic=True)
    assert v28["live_calls"] == 0 and v28["recovery_diagnostic"] is True
    v29 = run_experiment("incomplete", "v29-diagnostic-dry-run", profile="focused-v29",
                         recovery_diagnostic=True)
    assert v29["live_calls"] == 0 and v29["recovery_diagnostic"] is True
    v30 = run_experiment("incomplete", "v30-diagnostic-dry-run", profile="focused-v30",
                         recovery_diagnostic=True)
    assert v30["live_calls"] == 0 and v30["recovery_diagnostic"] is True
    for profile in ("focused-v3", "focused-v8", "focused-v9", "focused-v10"):
        try:
            run_experiment("admitted", f"invalid-{profile}-diagnostic", profile=profile,
                           recovery_diagnostic=True)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{profile} diagnostic was permitted")
    try:
        run_experiment("admitted", "invalid-frozen-diagnostic", profile="focused-v11",
                       recovery_diagnostic=True, manifest=Path("confirmation.json"))
    except ValueError:
        pass
    else:
        raise AssertionError("frozen diagnostic was permitted")
    original_remaining = ledger.remaining
    try:
        ledger.remaining = lambda _kind, _campaign=None: 999
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence_path = root / "scout-evidence.json"
            evidence_path.write_text(json.dumps({
                "source_only": True,
                "mapping": [{"run": "scout-fixture", "pass_index": 1,
                             "request_sha256": "fixture-digest"}],
            }), encoding="utf-8")
            manifest_path = root / "manifest.json"
            freeze.freeze(manifest_path, profile="focused-v23", repeat=1,
                          prefix="v23-offline-manifest",
                          scout_source_evidence=evidence_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            embedded = manifest["scout_source_evidence"]
            canonical = json.dumps(embedded["document"], ensure_ascii=False,
                                   sort_keys=True, separators=(",", ":")).encode("utf-8")
            assert embedded["sha256"] == hashlib.sha256(
                evidence_path.read_bytes()).hexdigest()
            assert embedded["canonical_sha256"] == hashlib.sha256(canonical).hexdigest()
            assert embedded["document"]["source_only"] is True
            assert "not part of the V23 confirmation cohort" in embedded["use"]
            assert all(row["profile"] == "focused-v23" for row in manifest["runs"])
            v28_manifest_path = root / "v28-manifest.json"
            freeze.freeze(v28_manifest_path, profile="focused-v28", repeat=1,
                          prefix="v28-offline-manifest")
            v28_manifest = json.loads(v28_manifest_path.read_text(encoding="utf-8"))
            assert all(row["profile"] == "focused-v28" for row in v28_manifest["runs"])
            v29_manifest_path = root / "v29-manifest.json"
            freeze.freeze(v29_manifest_path, profile="focused-v29", repeat=1,
                          prefix="v29-offline-manifest")
            v29_manifest = json.loads(v29_manifest_path.read_text(encoding="utf-8"))
            assert all(row["profile"] == "focused-v29" for row in v29_manifest["runs"])
            v30_manifest_path = root / "v30-manifest.json"
            freeze.freeze(v30_manifest_path, profile="focused-v30", repeat=1,
                          prefix="v30-offline-manifest")
            v30_manifest = json.loads(v30_manifest_path.read_text(encoding="utf-8"))
            assert all(row["profile"] == "focused-v30" for row in v30_manifest["runs"])
    finally:
        ledger.remaining = original_remaining
    config = ResultsConfig.model_validate_json(
        (Path(__file__).resolve().parent.parent /
         "2026-10-25-cost-experiments/luna-retest/round-1/admitted/config.json").read_bytes())
    settings = InteractiveSettings(reasoning_effort="low", service_tier="fast")

    class FakeMeasurer:
        def measure(self, value: dict[str, object], _config: ResultsConfig) -> InputTokenReceipt:
            return InputTokenReceipt(request_digest=content_digest(value), input_tokens=10,
                                     raw_response={"object": "response.input_tokens", "input_tokens": 10})

    class FakeWriter:
        def author(self, _value: dict[str, object], _config: ResultsConfig,
                   _settings: InteractiveSettings) -> str:
            return '{"blocks": []}'

        def take_receipt(self) -> WriterReceipt:
            return WriterReceipt(status="completed", usage={"input_tokens": 10},
                raw_response='{"status":"completed","service_tier":"priority",'
                             '"usage":{"input_tokens":10,"output_tokens":3}}')

    original_calls = ledger.CALLS
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ledger.CALLS = root / "calls"
            campaign = ledger.campaign()
            run = root / "run"
            count = RecordingMeasurer(FakeMeasurer(), run, campaign)
            writer = RecordingWriter(FakeWriter(), run, campaign)
            assert count.measure(request, config).input_tokens == 10
            assert writer.author(request, config, settings) == '{"blocks": []}'
            assert writer.take_receipt().status == "completed"
            assert writer.take_receipt() is None
            assert len(list(ledger.CALLS.glob("count-*.json"))) == 1
            assert len(list(ledger.CALLS.glob("generation-*.json"))) == 1
            assert ledger.read_json(run / "pass-01" / "generation-request.json")[
                "service_tier"] == "fast"
            assert ledger.read_json(run / "pass-01" / "generation-timing.json")[
                "returned_service_tier"] == "priority"
            ledger.require_headroom(campaign)
            ledger.reserve("count", campaign, run="run", label="pass-02", digest="fixture")
            ledger.reserve("count", campaign, run="run", label="pass-03", digest="fixture")
            try:
                ledger.reserve("count", campaign, run="run", label="pass-04", digest="fixture")
            except ValueError as exc:
                assert "attempt limit" in str(exc)
            else:
                raise AssertionError("fourth count reservation was permitted")
    finally:
        ledger.CALLS = original_calls
    print("offline capture and budget sanity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
