"""Run one disclosed intent fixture through the local Results M2 pipeline.

Usage: .venv/bin/python evidence/end-to-end/2026-10-08-golden-diagnostic/run.py --case ID
Raw fixture requests, model IO and provider bodies are private under ignored runs/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from openai.resources.responses import Responses

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from award_agent.clarification import (
    OpenAIClarificationAnswerInterpreter,
    OpenAIClarificationComposerConfig,
    OpenAIClarificationInterpreterConfig,
    OpenAIClarificationPromptComposer,
    apply_clarification_answer,
    start_clarification,
)
from award_agent.cli.provider_results import ProviderInputBundle
from award_agent.domain import (
    ClarificationAnswerCommand,
    ClarificationSession,
    ClarificationSessionStatus,
    RawRequest,
    RequestContext,
    RequestUnderstandingOutcome,
    RequestUnderstandingResult,
)
from award_agent.harness.pipeline import (
    HarnessSettings,
    ProviderRun,
    acquire,
    author,
    plan_session,
    rank,
)
from award_agent.intent import (
    NagerHolidayProvider,
    OpenAISemanticIntentConfig,
    OpenAISemanticIntentInterpreter,
    understand_request,
)
from award_agent.providers.contracts import ExecutionPolicy, ProviderResultSet
from award_agent.providers.replay import ReplayTape
from award_agent.results import ResultsConfig, replay_results

HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "evals/intent/one_way_award_behavior_cases_v1.yaml"
RESULTS_CONFIG = ROOT / "evidence/results-stage/m2/2026-10-08-luna/declared.config.json"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def save_model(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.model_dump_json(indent=2) + "\n")


def repository_state() -> dict[str, Any]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    sources = [ROOT / name for name in (
        "src/award_agent/intent/workflow.py", "src/award_agent/harness/pipeline.py",
        "src/award_agent/providers/execution.py", "src/award_agent/ranking/matching.py",
        "src/award_agent/results/core.py", "src/award_agent/results/adapter.py",
    )]
    return {"git_head": head, "dirty_paths": status,
            "source_sha256": {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                              for path in sources if path.is_file()},
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


def apply_provider_profile(bundle: ProviderInputBundle, profile: str) -> ProviderInputBundle:
    # Derive either profile from the declared source, not the previous run's
    # modified policy. This makes both profile directions and same-policy resume
    # explicit and idempotent.
    policy = json.loads(HarnessSettings().provider_settings_path.read_text())["policy"]
    if profile == "compact":
        selected = json.loads((HERE / "provider-compact.json").read_text())
        for provider in ("award", "cash"):
            key = f"{provider}_budget"
            policy[key].update(selected[key])
        policy["direct_cash_samples"] = selected["direct_cash_samples"]
        policy["positioning_cash_samples"] = selected["positioning_cash_samples"]
        policy["version"] += "+e2e-compact-v1"
        policy["budget_evidence"].append("evidence/end-to-end/2026-10-08-golden-diagnostic/provider-compact.json")
    elif profile != "standard":
        raise ValueError(f"unknown provider profile {profile}")
    payload = bundle.model_dump(mode="json")
    payload["policy"] = ExecutionPolicy.model_validate(policy).model_dump(mode="json")
    return ProviderInputBundle.model_validate(payload)


def load_case(case_id: str, campaign: str = "original") -> dict[str, Any]:
    manifest_path = HERE / ("cases.json" if campaign == "original" else "cases-early-2027.json")
    manifest = json.loads(manifest_path.read_text())
    if case_id not in manifest["cases"]:
        raise ValueError(f"unknown case {case_id}; choose from {', '.join(manifest['cases'])}")
    fixture = next(item for item in yaml.safe_load(SOURCE.read_text())["scenarios"]
                   if item["id"] == case_id)
    adaptation = manifest["cases"][case_id]
    request = fixture["input"]
    if "input_replace" in adaptation:
        old, new = adaptation["input_replace"]["old"], adaptation["input_replace"]["new"]
        if request.count(old) != 1:
            raise ValueError(f"{case_id}: expected one source phrase {old!r}")
        request = request.replace(old, new)
    context = dict(fixture["context"])
    context.update(adaptation.get("context_override", {}))
    return {
        "campaign": campaign,
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "source_path": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(SOURCE.read_bytes()).hexdigest(),
        "source_fixture": fixture,
        "adaptation": adaptation,
        "executed_input": request,
        "executed_context": context,
        "oracle_applicability": "original fixture oracle applies only if input/context are unchanged",
    }


def dump_response(value: Any) -> Any:
    method = getattr(value, "model_dump", None)
    return method(mode="json") if callable(method) else value


def usage_of(value: Any) -> dict[str, int] | None:
    raw = getattr(value, "usage", None)
    if raw is None:
        return None
    data = dump_response(raw)
    if not isinstance(data, dict):
        return None
    details = data.get("input_tokens_details") or {}
    return {
        "input_tokens": int(data.get("input_tokens", 0)),
        "output_tokens": int(data.get("output_tokens", 0)),
        "total_tokens": int(data.get("total_tokens", 0)),
        "cached_input_tokens": int(details.get("cached_tokens", 0)),
    }


@contextmanager
def capture_calls(directory: Path, phase: list[str]) -> Iterator[list[dict[str, Any]]]:
    """Capture actual SDK request/response envelopes, including planning adapters.

    This local diagnostic wraps public SDK entry points and restores them on exit;
    no runtime module is modified. Client credentials live on ``self`` and are
    deliberately excluded from trace serialization.
    """
    entries: list[dict[str, Any]] = []
    sequence = [0]
    original_parse, original_create, original_post = Responses.parse, Responses.create, OpenAI.post

    def call(kind: str, original: Any, receiver: Any, args: tuple[Any, ...],
             kwargs: dict[str, Any]) -> Any:
        sequence[0] += 1
        index = sequence[0]
        request = {"args": [str(x) for x in args], "kwargs": {
            key: (getattr(value, "__name__", str(value)) if key == "text_format" else value)
            for key, value in kwargs.items() if key not in {"api_key", "headers", "extra_headers"}
        }}
        item: dict[str, Any] = {"sequence": index, "stage": phase[0], "kind": kind,
                                "request": request}
        started = time.perf_counter()
        try:
            response = original(receiver, *args, **kwargs)
            item["response"] = dump_response(response)
            item["usage"] = usage_of(response)
            return response
        except Exception as exc:
            item["error"] = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            item["latency_seconds"] = round(time.perf_counter() - started, 3)
            entries.append({key: item[key] for key in ("sequence", "stage", "kind", "latency_seconds",
                          "usage", "error") if key in item})
            write_json(directory / f"call-{index:03d}.json", item)
            write_json(directory / "index.json", entries)

    def parse(receiver: Any, *args: Any, **kwargs: Any) -> Any:
        return call("responses.parse", original_parse, receiver, args, kwargs)

    def create(receiver: Any, *args: Any, **kwargs: Any) -> Any:
        return call("responses.create", original_create, receiver, args, kwargs)

    def post(receiver: Any, *args: Any, **kwargs: Any) -> Any:
        if not args or args[0] != "/responses/input_tokens":
            return original_post(receiver, *args, **kwargs)
        return call("client.post", original_post, receiver, args, kwargs)

    Responses.parse, Responses.create, OpenAI.post = parse, create, post
    try:
        yield entries
    finally:
        Responses.parse, Responses.create, OpenAI.post = original_parse, original_create, original_post


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--campaign", choices=("original", "early-2027"), default="original")
    parser.add_argument("--preflight", action="store_true", help="Validate fixture and settings without live calls")
    parser.add_argument("--resume-from", type=Path,
                        help="Continue from saved intent/session/planning without repeating paid calls")
    parser.add_argument("--provider-profile", choices=("standard", "compact"), default="standard")
    args = parser.parse_args()
    case = load_case(args.case, args.campaign)
    config = ResultsConfig.model_validate_json(RESULTS_CONFIG.read_bytes())
    settings = HarnessSettings()
    for path in (settings.catalog_path, settings.provider_settings_path, settings.fx_path):
        if not path.exists():
            raise FileNotFoundError(path)
    if args.preflight:
        print(json.dumps({"case": args.case, "adaptation": case["adaptation"],
                          "models": {"intent": "gpt-5.6-luna", "planning": settings.selector_model,
                                     "gateway": settings.gateway_model, "results": config.model}}))
        return 0

    load_dotenv(ROOT / ".env")
    prior = args.resume_from.resolve() if args.resume_from else None
    if prior is not None and not (prior / "case.json").is_file():
        raise ValueError("resume source must contain case.json")
    if prior is not None:
        previous_case = json.loads((prior / "case.json").read_text())
        for key in ("source_sha256", "source_fixture", "executed_input", "executed_context"):
            if previous_case[key] != case[key]:
                raise ValueError(f"resume source {key} differs from current fixture")
    out = (HERE / "runs" / args.case if args.campaign == "original"
           else HERE / args.campaign / "runs" / args.case)
    if prior is not None:
        number = 1
        while (out / f"continuation-{number}").exists():
            number += 1
        out = out / f"continuation-{number}"
    elif out.exists() and (out / "summary.json").exists():
        raise FileExistsError(f"existing run at {out}; use --resume-from {out}")
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "case.json", case)
    write_json(out / "settings.json", {
        "harness": {key: str(value) for key, value in vars(settings).items()},
        "results_config_path": str(RESULTS_CONFIG.relative_to(ROOT)),
        "results_config_sha256": sha256(RESULTS_CONFIG.read_bytes()).hexdigest(),
        "provider_settings_sha256": sha256(settings.provider_settings_path.read_bytes()).hexdigest(),
        "fx_sha256": sha256(settings.fx_path.read_bytes()).hexdigest(),
        "catalog_path": str(settings.catalog_path),
        "repository_state": repository_state(),
    })
    summary: dict[str, Any] = {"case": args.case, "campaign": args.campaign,
                               "status": "running", "stages": {},
                               "trace_scope": "private local fixture/model/provider data",
                               "provider_profile": args.provider_profile,
                               "models": {"intent": "gpt-5.6-luna", "selector": settings.selector_model,
                                          "gateway": settings.gateway_model, "results": config.model}}
    if prior is not None:
        summary["resume_from"] = str(prior)
    write_json(out / "summary.json", summary)
    phase = ["intent"]
    started_total = time.perf_counter()
    try:
        with capture_calls(out / "model-calls", phase) as calls:
            print(f"{args.case}: intent", flush=True)
            if prior is not None:
                initial = RequestUnderstandingResult.model_validate_json((prior / "intent.json").read_bytes())
                shutil.copy2(prior / "intent.json", out / "intent.json")
                summary["stages"]["intent"] = {"reused_from": str(prior)}
            else:
                started = time.perf_counter()
                interpreter = OpenAISemanticIntentInterpreter(OpenAISemanticIntentConfig(
                    model="gpt-5.6-luna"), capture_llm_io=True)
                request = RawRequest(text=case["executed_input"], context=RequestContext(
                    reference_date=date.fromisoformat(case["executed_context"]["reference_date"]),
                    timezone=case["executed_context"]["timezone"]))
                initial = understand_request(request, interpreter, NagerHolidayProvider())
                save_model(out / "intent.json", initial)
                write_json(out / "intent-adapter-traces.json", interpreter.take_call_traces())
                summary["stages"]["intent"] = {"elapsed_seconds": round(time.perf_counter() - started, 3),
                                               "usage": interpreter.take_usage(), "outcome": initial.outcome.value}
                write_json(out / "summary.json", summary)
            if initial.outcome is RequestUnderstandingOutcome.PENDING_RETRYABLE:
                summary["status"] = "intent_pending"
                return 2
            if prior is not None and (prior / "session.json").is_file() or prior is not None and (prior / "provider-bundle.json").is_file():
                session = ClarificationSession.model_validate_json((prior / "session.json").read_bytes())
                summary["stages"]["clarification"] = {"reused_from": str(prior)}
            else:
                phase[0] = "clarification"
                clarification_started = time.perf_counter()
                composer = OpenAIClarificationPromptComposer(
                    OpenAIClarificationComposerConfig(model="gpt-5.6-luna"),
                    capture_llm_io=True,
                )
                session = start_clarification(initial, composer=composer)
                write_json(out / "composer-adapter-traces.json", composer.take_call_traces())
                summary["stages"]["clarification"] = {
                    "usage": composer.take_usage(), "session_status": session.status.value,
                    "elapsed_seconds": round(time.perf_counter() - clarification_started, 3),
                }
            save_model(out / "session.json", session)
            if prior is not None and session.status is ClarificationSessionStatus.AWAITING_ANSWER:
                answer = case["adaptation"].get("scripted_clarification")
                if not answer:
                    summary["status"] = "blocked_by_original_request"
                    return 2
                phase[0] = "clarification_answer"
                started = time.perf_counter()
                receiver = OpenAIClarificationAnswerInterpreter(
                    OpenAIClarificationInterpreterConfig(model="gpt-5.6-luna"),
                    capture_llm_io=True)
                composer = OpenAIClarificationPromptComposer(
                    OpenAIClarificationComposerConfig(model="gpt-5.6-luna"),
                    capture_llm_io=True)
                revision = session.current_revision
                assert revision.prompt is not None
                command = ClarificationAnswerCommand(
                    session_id=session.session_id, expected_revision=revision.revision,
                    prompt_id=revision.prompt.prompt_id,
                    message_id=f"diagnostic:{args.case}:answer:{revision.revision + 1}",
                    text=answer)
                write_json(out / "scripted-answer.json", {
                    "command": command.model_dump(mode="json"),
                    "provenance": case["adaptation"]["answer_source"]})
                transition = apply_clarification_answer(session, command, receiver, composer=composer)
                write_json(out / "clarification-receiver-traces.json", receiver.take_call_traces())
                write_json(out / "clarification-composer-traces.json", composer.take_call_traces())
                if not hasattr(transition, "session"):
                    summary["status"] = "clarification_pending"
                    return 2
                session = transition.session
                save_model(out / "session.json", session)
                summary["stages"]["clarification_answer"] = {
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "receiver_usage": receiver.take_usage(), "composer_usage": composer.take_usage(),
                    "status": session.status.value}
            summary["session_status"] = session.status.value
            write_json(out / "summary.json", summary)
            if session.status is not ClarificationSessionStatus.READY:
                summary["status"] = "blocked_by_original_request"
                return 2

            if prior is not None and (prior / "provider-bundle.json").is_file():
                bundle = ProviderInputBundle.model_validate_json((prior / "provider-bundle.json").read_bytes())
                shutil.copy2(prior / "planning-input.json", out / "planning-input.json")
                shutil.copy2(prior / "planning-result.json", out / "planning-result.json")
                save_model(out / "provider-bundle.json", bundle)
                summary["stages"]["planning"] = {"reused_from": str(prior)}
            else:
                phase[0] = "planning"
                print(f"{args.case}: planning", flush=True)
                started = time.perf_counter()
                planning = plan_session(session, settings)
                save_model(out / "planning-input.json", planning.planning_input)
                save_model(out / "planning-result.json", planning.result)
                bundle = planning.bundle
                if bundle is not None:
                    save_model(out / "provider-bundle.json", bundle)
                summary["stages"]["planning"] = {"elapsed_seconds": round(time.perf_counter() - started, 3),
                                                   "diagnostics": planning.diagnostics,
                                                   "outcome": planning.result.outcome.value}
                write_json(out / "summary.json", summary)
            if bundle is None:
                summary["status"] = "planning_without_plan"
                return 2
            bundle = apply_provider_profile(bundle, args.provider_profile)
            save_model(out / "provider-bundle.json", bundle)

            phase[0] = "providers"
            print(f"{args.case}: providers", flush=True)
            prior_bundle = (ProviderInputBundle.model_validate_json(
                (prior / "provider-bundle.json").read_bytes()) if prior is not None
                and (prior / "provider-bundle.json").is_file() else None)
            if prior is not None and prior_bundle is not None and prior_bundle.policy == bundle.policy and (
                prior / "provider-result.json").is_file() and (prior / "provider-tape.json").is_file():
                providers = ProviderRun(
                    result=ProviderResultSet.model_validate_json((prior / "provider-result.json").read_bytes()),
                    tape=ReplayTape.model_validate_json((prior / "provider-tape.json").read_bytes()),
                )
                shutil.copy2(prior / "provider-result.json", out / "provider-result.json")
                shutil.copy2(prior / "provider-tape.json", out / "provider-tape.json")
                if (prior / "provider-bodies").exists():
                    shutil.copytree(prior / "provider-bodies", out / "provider-bodies")
                summary["stages"]["providers"] = {"reused_from": str(prior),
                                                    "status": providers.result.status}
            else:
                started = time.perf_counter()
                providers = acquire(bundle, settings)
                save_model(out / "provider-result.json", providers.result)
                assert providers.tape is not None
                save_model(out / "provider-tape.json", providers.tape)
                for name, body in providers.evidence_files.items():
                    path = out / "provider-bodies" / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(body)
                summary["stages"]["providers"] = {"elapsed_seconds": round(time.perf_counter() - started, 3),
                                                    "status": providers.result.status,
                                                    "captured_pages": len(providers.tape.entries),
                                                    "body_files": len(providers.evidence_files)}
            write_json(out / "summary.json", summary)
            replay_started = time.perf_counter()
            try:
                replay = acquire(bundle, settings, ReplayTape.model_validate_json(
                    (out / "provider-tape.json").read_bytes()))
                save_model(out / "provider-replayed.json", replay.result)
                summary["provider_exact_replay"] = (
                    replay.result.model_dump(mode="json") == providers.result.model_dump(mode="json"))
            except Exception as exc:  # noqa: BLE001 - replay failure is evidence, not a live-stage failure.
                summary["provider_exact_replay"] = False
                summary["provider_replay_error"] = {"type": type(exc).__name__, "message": str(exc)}
            summary["provider_replay_seconds"] = round(time.perf_counter() - replay_started, 3)
            write_json(out / "summary.json", summary)

            phase[0] = "ranking"
            print(f"{args.case}: ranking", flush=True)
            started = time.perf_counter()
            ranking = rank(bundle, providers.result, settings)
            save_model(out / "matched.json", ranking.matched)
            save_model(out / "ranked.json", ranking.ranked)
            save_model(out / "solutions.json", ranking.projection)
            summary["stages"]["ranking"] = {"elapsed_seconds": round(time.perf_counter() - started, 3),
                                              "journeys": len(ranking.matched.journeys)}
            write_json(out / "summary.json", summary)

            phase[0] = "results"
            print(f"{args.case}: results", flush=True)
            started = time.perf_counter()
            result = author(ranking.projection, config)
            results_live_seconds = round(time.perf_counter() - started, 3)
            save_model(out / "results-artifact.json", result)
            replay_started = time.perf_counter()
            answer = replay_results(result)
            summary["results_exact_replay"] = answer == result.rendered_markdown
            (out / "answer.md").write_text(answer)
            summary["results_replay_seconds"] = round(time.perf_counter() - replay_started, 3)
            summary["stages"]["results"] = {"elapsed_seconds": results_live_seconds,
                                              "generation": result.generation_outcome,
                                              "validation": result.validation_outcome,
                                              "delivery": result.delivery_outcome,
                                              "attempts": len(result.attempts)}
            summary["status"] = ("finished" if result.delivery_outcome == "delivered"
                                 else "finished_no_delivery")
            return 0
    except KeyboardInterrupt:
        summary["status"] = "interrupted"
        summary["interrupted_stage"] = phase[0]
        return 130
    except Exception as exc:  # noqa: BLE001 - preserve the stage and partial evidence on any failure.
        summary["status"] = "error"
        summary["error"] = {"stage": phase[0], "type": type(exc).__name__, "message": str(exc),
                            "traceback": traceback.format_exc()}
        return 1
    finally:
        summary["elapsed_seconds"] = round(time.perf_counter() - started_total, 3)
        summary["live_pipeline_seconds"] = round(sum(
            float(stage.get("elapsed_seconds", 0)) for stage in summary["stages"].values()), 3)
        summary["model_calls"] = len(calls) if "calls" in locals() else 0
        summary["token_accounting"] = "See model-calls/index.json; missing usage is not zero. Input-token measurement calls are separate from generation."
        write_json(out / "summary.json", summary)
        print(json.dumps({"case": args.case, "status": summary["status"], "out": str(out),
                          "elapsed_seconds": summary["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
