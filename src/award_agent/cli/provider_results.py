"""Explicit local plan, offline replay, and bounded live Provider Stage command."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import TypedDict

from pydantic import Field

from award_agent.domain import EffectiveRequest
from award_agent.providers.contracts import ExecutionPolicy, ProviderCapability
from award_agent.providers.replay import RecordingAdapter, ReplayAdapter, ReplayTape
from award_agent.search_planning.compilation_contracts import CompiledSearchPlan
from award_agent.search_planning.contracts import PlanningContractModel


class ProviderInputBundle(PlanningContractModel):
    """Caller authority is explicit and separate from the materialized plan."""

    plan: CompiledSearchPlan
    current_session_id: str = Field(min_length=1)
    current_revision: int = Field(ge=0)
    current_effective_request: EffectiveRequest
    expected_compilation_binding_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    policy: ExecutionPolicy
    award_capability: ProviderCapability
    cash_capability: ProviderCapability


class ExecutionOptions(TypedDict):
    run_id: str
    current_session_id: str
    current_revision: int
    current_effective_request: EffectiveRequest
    expected_compilation_binding_digest: str
    policy: ExecutionPolicy
    award_capability: ProviderCapability
    cash_capability: ProviderCapability


def _write_new(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(rendered + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("plan", "replay", "live"), default="plan")
    parser.add_argument("--tape", type=Path, help="Required acquisition tape for offline replay.")
    parser.add_argument("--record-tape", type=Path, help="Save the live acquisition tape.")
    parser.add_argument("--evidence-root", type=Path, default=Path("evidence/provider-stage/runtime"))
    parser.add_argument("--gfly-executable", default="gfly")
    parser.add_argument("--gfly-wrapper", type=Path,
                        help="Repo-owned compatibility launcher, run with --gfly-executable Python.")
    parser.add_argument("--catalog", type=Path, help="Matching catalog release for connection-airport timezones.")
    args = parser.parse_args(argv)
    if args.output.exists() or (args.record_tape and args.record_tape.exists()):
        parser.error("output and recording paths must be new; existing evidence is immutable")
    if args.mode == "replay" and args.tape is None:
        parser.error("offline replay requires --tape")
    if args.mode == "live" and args.record_tape is None:
        parser.error("live execution requires --record-tape for replayable evidence")

    from award_agent.providers.execution import (
        build_execution_plan,
        execute_provider_plan,
        validate_result_attachment,
    )

    bundle = ProviderInputBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
    options: ExecutionOptions = {
        "run_id": bundle.run_id,
        "current_session_id": bundle.current_session_id,
        "current_revision": bundle.current_revision,
        "current_effective_request": bundle.current_effective_request,
        "expected_compilation_binding_digest": bundle.expected_compilation_binding_digest,
        "policy": bundle.policy,
        "award_capability": bundle.award_capability,
        "cash_capability": bundle.cash_capability,
    }
    if args.mode == "plan":
        execution_plan = build_execution_plan(bundle.plan, **options)
        _write_new(args.output, execution_plan.model_dump_json(indent=2))
        print(json.dumps({"mode": "plan", "queries": len(execution_plan.queries),
                          "coverage_units": len(execution_plan.coverage_units)}))
        return 0

    from award_agent.providers.gfly import GflyAdapter
    from award_agent.providers.seats_aero import SeatsAeroAdapter
    from award_agent.providers.transport import SubprocessTransport

    api_key = os.environ.get("SEATS_AERO_API_KEY", "")
    if args.mode == "live":
        if not bundle.award_capability.reviewed or not bundle.cash_capability.reviewed:
            parser.error("live execution requires reviewed, evidence-bound provider capabilities")
        if not api_key:
            parser.error("set SEATS_AERO_API_KEY in the environment for live execution")
        expected_cash_version = (
            "0.3.0+award-search-unpriced-party-echo-v2" if args.gfly_wrapper is not None
            else "0.3.0"
        )
        if bundle.award_capability.version != "cached-search-v1" or (
            bundle.cash_capability.version != expected_cash_version
        ):
            parser.error("live adapter versions must match the reviewed capability and launcher")
        if args.gfly_wrapper is not None and args.gfly_wrapper.resolve() != (
            Path(__file__).resolve().parents[3] / "scripts/gfly_compat.py"
        ).resolve():
            parser.error("live compatibility launcher must be this repository's reviewed script")
        if (bundle.award_capability.backend, bundle.award_capability.operation) != (
            "partnerapi", "cached_search"
        ) or (bundle.cash_capability.backend, bundle.cash_capability.operation) != (
            "google", "search"
        ):
            parser.error("capability backend/operation must match the implemented adapters")
        version = SubprocessTransport().run(
            [args.gfly_executable, *([str(args.gfly_wrapper)] if args.gfly_wrapper else []),
             "version", "--json"],
            timeout_seconds=5, max_response_bytes=4096,
        )
        if version.exit_code != 0 or json.loads(version.stdout).get("version") != expected_cash_version:
            parser.error("gfly command does not match reviewed capability version")
    award_parser = SeatsAeroAdapter(
        api_key=api_key or "offline-unused", evidence_root=args.evidence_root,
        provider_version=bundle.award_capability.version,
    )
    cash_parser = GflyAdapter(
        evidence_root=args.evidence_root, executable=args.gfly_executable,
        wrapper=str(args.gfly_wrapper) if args.gfly_wrapper is not None else None,
        provider_version=bundle.cash_capability.version,
    )
    if args.mode == "replay":
        tape = ReplayTape.model_validate_json(args.tape.read_text(encoding="utf-8"))
        award: ReplayAdapter | RecordingAdapter = ReplayAdapter(award_parser, tape)
        cash: ReplayAdapter | RecordingAdapter = ReplayAdapter(cash_parser, tape)
    else:
        award = RecordingAdapter(award_parser)
        cash = RecordingAdapter(cash_parser)
    def current_authority() -> tuple[str, int, EffectiveRequest, str]:
        current = ProviderInputBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
        return (current.current_session_id, current.current_revision,
                current.current_effective_request, current.expected_compilation_binding_digest)

    try:
        with ExitStack() as stack:
            repository = None
            if args.catalog is not None:
                from award_agent.search_planning.knowledge import CatalogKnowledgeRepository

                repository = stack.enter_context(CatalogKnowledgeRepository(args.catalog))
            result = execute_provider_plan(
                bundle.plan, award_adapter=award, cash_adapter=cash,
                current_authority=current_authority, timezone_repository=repository, **options,
            )
    finally:
        if args.mode == "live":
            assert isinstance(award, RecordingAdapter) and isinstance(cash, RecordingAdapter)
            tape = ReplayTape(entries=tuple(award.entries + cash.entries))
            _write_new(args.record_tape, tape.model_dump_json(indent=2))
    # A stale artifact may be saved as a diagnostic; it is never accepted for attachment.
    if result.status != "stale":
        current = ProviderInputBundle.model_validate_json(args.bundle.read_text(encoding="utf-8"))
        result = validate_result_attachment(
            current.plan, result, current_session_id=current.current_session_id,
            current_revision=current.current_revision,
            current_effective_request=current.current_effective_request,
            expected_compilation_binding_digest=current.expected_compilation_binding_digest,
            policy=current.policy, award_capability=current.award_capability,
            cash_capability=current.cash_capability,
        )
    _write_new(args.output, result.model_dump_json(indent=2))
    print(json.dumps({"mode": args.mode, "status": result.status,
                      "observations": len(result.observations),
                      "transport_calls": len(result.transport_receipts),
                      "coverage_units": len(result.coverage)}))
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
