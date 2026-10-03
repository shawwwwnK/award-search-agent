"""Assign deterministic solution styles to an offline matched journey set."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.style_contracts import (
    CurrencyConversionSnapshot,
    RankingStylePolicy,
)
from award_agent.ranking.styles import assign_journey_styles


def _write_new_atomic(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(rendered)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_json_model[ModelType: BaseModel](
    path: Path, model: type[ModelType]
) -> tuple[ModelType, bytes]:
    content = path.read_bytes()
    instance = model.model_validate_json(content)
    return instance, content


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched", type=Path, required=True,
                        help="Frozen M1 MatchedJourneySet JSON.")
    parser.add_argument("--fx-snapshot", type=Path, required=True,
                        help="Versioned currency conversion snapshot JSON.")
    parser.add_argument("--policy", type=Path,
                        help="Ranking style policy JSON; defaults to the contract policy.")
    parser.add_argument("--output", type=Path, required=True,
                        help="New path for the styled journey set JSON.")
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output path must be new; existing evidence is immutable")

    matched, matched_content = _read_json_model(args.matched, MatchedJourneySet)
    snapshot, snapshot_content = _read_json_model(args.fx_snapshot, CurrencyConversionSnapshot)
    if args.policy is None:
        policy = RankingStylePolicy()
        policy_content = None
    else:
        policy, policy_content = _read_json_model(args.policy, RankingStylePolicy)

    styled = assign_journey_styles(matched, policy=policy, fx_snapshot=snapshot)

    if args.matched.read_bytes() != matched_content:
        raise ValueError("matched journey input changed during style assignment")
    if args.fx_snapshot.read_bytes() != snapshot_content:
        raise ValueError("FX snapshot changed during style assignment")
    if args.policy is not None and args.policy.read_bytes() != policy_content:
        raise ValueError("ranking style policy changed during style assignment")

    _write_new_atomic(args.output, styled.model_dump_json(indent=2))
    print(json.dumps({"output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
