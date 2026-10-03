"""Generate or verify replayable Ranking M2 corpus artifacts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

from award_agent.cli.ranking_styles import main as ranking_styles_main
from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.style_contracts import RankedJourneySet


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _run_cli(matched_path: Path, snapshot_path: Path, output_path: Path) -> bytes:
    with redirect_stdout(io.StringIO()):
        ranking_styles_main([
            "--matched", str(matched_path),
            "--fx-snapshot", str(snapshot_path),
            "--output", str(output_path),
        ])
    return output_path.read_bytes()


def _utc_instant(value: str | None) -> datetime | None:
    if value is None:
        return None
    instant = datetime.fromisoformat(value)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("raw provider and journey instants must include a timezone")
    return instant.astimezone(UTC)


def _raw_elapsed_microseconds(journey: dict[str, Any]) -> int | None:
    departure = journey.get("departure_instant")
    arrival = journey.get("arrival_instant")
    if departure is None or arrival is None:
        return None
    departure_utc = _utc_instant(departure)
    arrival_utc = _utc_instant(arrival)
    if departure_utc is None or arrival_utc is None:
        return None
    interval = arrival_utc - departure_utc
    microseconds = (
        (interval.days * 86400 + interval.seconds) * 1_000_000
        + interval.microseconds
    )
    if microseconds <= 0:
        return None
    return microseconds


def _decimal_ratio(numerator: int, denominator: int) -> Decimal:
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        return Decimal(numerator) / Decimal(denominator)


def _decimal_fraction(value: Fraction) -> Decimal:
    return _decimal_ratio(value.numerator, value.denominator)


def _elapsed_minutes(microseconds: int) -> Decimal:
    return _decimal_ratio(microseconds, 60_000_000)


def _provider_timing(
    observation: dict[str, Any], award: bool,
) -> tuple[datetime | None, datetime | None]:
    if award:
        legs = observation["legs"]
        if not legs:
            return None, None
        return (
            _utc_instant(legs[0].get("departure_instant")),
            _utc_instant(legs[-1].get("arrival_instant")),
        )
    return (
        _utc_instant(observation.get("departure_instant")),
        _utc_instant(observation.get("arrival_instant")),
    )


def _assert_source_timing(
    journey: dict[str, Any], raw_observations: dict[str, dict[str, Any]],
) -> None:
    award = raw_observations[journey["award_observation_id"]]
    award_start, award_end = _provider_timing(award, award=True)
    cash_id = journey["cash_observation_id"]
    cash = raw_observations[cash_id] if cash_id is not None else None
    cash_start, cash_end = _provider_timing(cash, award=False) if cash is not None else (None, None)
    topology = journey["topology"]
    expected_start = cash_start if topology == "cash_access_award" else award_start
    expected_end = cash_end if topology == "award_cash_egress" else award_end
    if (_utc_instant(journey.get("departure_instant")),
            _utc_instant(journey.get("arrival_instant"))) != (expected_start, expected_end):
        raise ValueError("matched journey endpoint instants differ from provider topology evidence")
    if cash is None:
        return

    expected_transfer_airport = (
        cash["destination"] if topology == "cash_access_award" else award["destination"]
    )
    if journey.get("transfer_airport") != expected_transfer_airport:
        raise ValueError("matched transfer airport differs from provider topology evidence")
    arriving = cash_end if topology == "cash_access_award" else award_end
    departing = award_start if topology == "cash_access_award" else cash_start
    expected_transfer_minutes = None
    if arriving is not None and departing is not None:
        interval = departing - arriving
        interval_microseconds = (
            (interval.days * 86400 + interval.seconds) * 1_000_000
            + interval.microseconds
        )
        if interval_microseconds >= 0:
            expected_transfer_minutes = interval_microseconds // 60_000_000
    if journey.get("transfer_minutes") != expected_transfer_minutes:
        raise ValueError("matched transfer duration differs from provider topology evidence")


def _assert_case_integrity(
    matched: MatchedJourneySet,
    raw_matched: dict[str, Any],
    ranked: RankedJourneySet,
) -> None:
    if ranked.matched != matched:
        raise ValueError("style output does not retain its exact matched journey attachment")
    raw_journeys = {journey["candidate_id"]: journey for journey in raw_matched["journeys"]}
    source_journeys = {journey.candidate_id: journey for journey in matched.journeys}
    features = {feature.candidate_id: feature for feature in ranked.features}
    if set(features) != set(source_journeys) or set(raw_journeys) != set(source_journeys):
        raise ValueError("style output candidate IDs differ from the matched source")
    observations = {
        observation.observation_id: observation
        for observation in matched.provider_result.observations
    }
    raw_observations = {
        observation["observation_id"]: observation
        for observation in raw_matched["provider_result"]["observations"]
    }
    if set(observations) != set(raw_observations):
        raise ValueError("parsed provider observation IDs differ from raw source IDs")

    eligible_durations: list[int] = []
    raw_elapsed_by_id: dict[str, int | None] = {}
    eligible_ids: set[str] = set()
    premium_ids: set[str] = set()
    premium_economy_ids: set[str] = set()
    excluded_ids: set[str] = set()
    for candidate_id, source_journey in source_journeys.items():
        raw_journey = raw_journeys[candidate_id]
        feature = features[candidate_id]
        _assert_source_timing(raw_journey, raw_observations)
        if (feature.option_family_id, feature.status) != (
            source_journey.option_family_id, source_journey.status
        ):
            raise ValueError("style output changed source status or option family")
        if (feature.award_observation_id, feature.cash_observation_id) != (
            source_journey.award_observation_id, source_journey.cash_observation_id
        ):
            raise ValueError("style output changed source observation IDs")

        elapsed = _raw_elapsed_microseconds(raw_journey)
        raw_elapsed_by_id[candidate_id] = elapsed
        expected_minutes = _elapsed_minutes(elapsed) if elapsed is not None else None
        if feature.elapsed_minutes != expected_minutes or (
            feature.elapsed_microseconds != elapsed
        ):
            raise ValueError("style duration differs from raw timezone-aware source instants")
        if source_journey.status in {"admitted", "conditional"}:
            if elapsed is None:
                raise ValueError("eligible source journey has no positive UTC duration")
            eligible_ids.add(candidate_id)
            eligible_durations.append(elapsed)
            raw_cabin = raw_observations[source_journey.award_observation_id]["cabin"]
            if raw_cabin.get("state") == "value" and raw_cabin.get("value") in {"business", "first"}:
                premium_ids.add(candidate_id)
            if raw_cabin.get("state") == "value" and raw_cabin.get("value") == "premium_economy":
                premium_economy_ids.add(candidate_id)
        else:
            excluded_ids.add(candidate_id)

    time_reference = min(eligible_durations) if eligible_durations else None
    expected_reference_minutes = (
        _elapsed_minutes(time_reference) if time_reference is not None else None
    )
    if (ranked.time_reference_microseconds, ranked.time_reference_minutes) != (
        time_reference, expected_reference_minutes
    ):
        raise ValueError("time reference differs from independently derived UTC durations")
    if time_reference is None:
        expected_time_ids: set[str] = set()
    else:
        exact_threshold = Fraction(time_reference) * Fraction(ranked.policy.time_factor)
        expected_time_ids = set()
        for candidate_id in eligible_ids:
            elapsed_microseconds = raw_elapsed_by_id[candidate_id]
            if elapsed_microseconds is not None and (
                Fraction(elapsed_microseconds) <= exact_threshold
            ):
                expected_time_ids.add(candidate_id)
    indexes = ranked.indexes
    if set(indexes.time) != expected_time_ids:
        raise ValueError("time style index differs from independently derived eligibility")
    if set(indexes.premium) != premium_ids:
        raise ValueError("premium index differs from raw award cabin evidence")
    if set(indexes.premium_economy_addons) != premium_economy_ids:
        raise ValueError("premium economy add-on index differs from raw cabin evidence")
    if set(indexes.excluded) != excluded_ids:
        raise ValueError("excluded index differs from source M1 statuses")
    member_indexes = (
        indexes.time,
        indexes.cost,
        indexes.premium,
        indexes.possible_cost,
        indexes.definite_highlights,
        indexes.possible_highlights,
    )
    if any(set(candidate_ids) & excluded_ids for candidate_ids in member_indexes):
        raise ValueError("an excluded M1 status appears in a style or highlight index")
    if ranked.comparison_pool_ids != tuple(sorted(eligible_ids)):
        raise ValueError("comparison pool contains a cross-input or excluded candidate")

    direct_cash_ids = set(matched.direct_cash_observation_ids)
    if ranked.matched.direct_cash_observation_ids != matched.direct_cash_observation_ids:
        raise ValueError("direct cash baseline IDs were not passed through")
    if not direct_cash_ids <= set(observations):
        raise ValueError("direct cash baseline references missing provider observations")


def _case_index(
    source_name: str,
    output_name: str,
    matched_content: bytes,
    output_content: bytes,
    ranked: RankedJourneySet,
) -> dict[str, object]:
    eligible_ids = set(ranked.comparison_pool_ids)
    eligible_features = [
        feature for feature in ranked.features if feature.candidate_id in eligible_ids
    ]
    cost_states = Counter(feature.cost.completeness for feature in ranked.features)
    eligible_cost_states = Counter(feature.cost.completeness for feature in eligible_features)
    component_states = Counter(
        component.state
        for feature in ranked.features
        for component in feature.cost.components
    )
    eligible_component_states = Counter(
        component.state
        for feature in eligible_features
        for component in feature.cost.components
    )
    status_split = Counter(feature.status for feature in ranked.features)
    indexes = ranked.indexes
    cost_assessment_states = Counter(
        assessment.state
        for assessment in ranked.assessments
        if assessment.style == "cost" and assessment.candidate_id in eligible_ids
    )
    estimated_candidates_all = [
        feature for feature in ranked.features
        if any(component.state == "estimated" for component in feature.cost.components)
    ]
    estimated_candidates_eligible = [
        feature for feature in eligible_features
        if any(component.state == "estimated" for component in feature.cost.components)
    ]
    time_reference_minutes = (
        _decimal_fraction(Fraction(ranked.time_reference_microseconds, 60_000_000))
        if ranked.time_reference_microseconds is not None else None
    )
    time_threshold_minutes = (
        _decimal_fraction(
            Fraction(ranked.time_reference_microseconds, 60_000_000)
            * Fraction(ranked.policy.time_factor)
        )
        if ranked.time_reference_microseconds is not None else None
    )
    cost_reference = (
        Fraction(ranked.cost_reference_numerator, ranked.cost_reference_denominator)
        if ranked.cost_reference_numerator is not None
        and ranked.cost_reference_denominator is not None else None
    )
    cost_threshold = (
        cost_reference * Fraction(ranked.policy.cost_factor)
        if cost_reference is not None else None
    )
    return {
        "source": source_name,
        "output": output_name,
        "input_sha256": _sha256(matched_content),
        "output_sha256": _sha256(output_content),
        "policy_digest": ranked.policy_digest,
        "fx_snapshot_digest": ranked.fx_snapshot_digest,
        "counts": {
            "journeys": len(ranked.features),
            "comparison_pool": len(ranked.comparison_pool_ids),
            "excluded": len(indexes.excluded),
            "time_members": len(indexes.time),
            "cost_members": len(indexes.cost),
            "premium_members": len(indexes.premium),
            "possible_cost_members": len(indexes.possible_cost),
            "premium_economy_addons": len(indexes.premium_economy_addons),
            "definite_highlights": len(indexes.definite_highlights),
            "possible_highlights": len(indexes.possible_highlights),
            "other_alternatives": len(indexes.other_alternatives),
            "cost_states_all_retained": dict(sorted(cost_states.items())),
            "cost_states_eligible": dict(sorted(eligible_cost_states.items())),
            "cost_component_states_all_retained": dict(sorted(component_states.items())),
            "cost_component_states_eligible": dict(sorted(eligible_component_states.items())),
            "eligible_cost_assessment_states": dict(sorted(cost_assessment_states.items())),
            "status_split": dict(sorted(status_split.items())),
            "estimated_cost_components_all_retained": component_states["estimated"],
            "estimated_cost_components_eligible": eligible_component_states["estimated"],
            "estimated_cost_candidates_all_retained": len(estimated_candidates_all),
            "estimated_cost_candidates_eligible": len(estimated_candidates_eligible),
        },
        "time_reference_minutes": str(time_reference_minutes) if time_reference_minutes is not None else None,
        "time_threshold_minutes": str(time_threshold_minutes) if time_threshold_minutes is not None else None,
        "cost_reference_usd": (
            str(_decimal_fraction(cost_reference)) if cost_reference is not None else None
        ),
        "cost_threshold_usd": (
            str(_decimal_fraction(cost_threshold)) if cost_threshold is not None else None
        ),
        "highlights": {
            "definite_ids": list(indexes.definite_highlights),
            "possible_ids": list(indexes.possible_highlights),
        },
    }


def _index_bytes(cases: list[dict[str, object]]) -> bytes:
    return (json.dumps({"contract_version": "ranking-style-corpus-v1", "cases": cases},
                       indent=2, sort_keys=True) + "\n").encode("utf-8")


def _input_files(matched_directory: Path) -> list[Path]:
    if not matched_directory.is_dir():
        raise ValueError("matched directory must exist")
    files = sorted(matched_directory.glob("*.json"), key=lambda path: path.name)
    if not files:
        raise ValueError("matched directory contains no JSON case inputs")
    return files


def _recheck_inputs(input_bytes: dict[Path, bytes], snapshot_path: Path, snapshot_bytes: bytes) -> None:
    if snapshot_path.read_bytes() != snapshot_bytes:
        raise ValueError("FX snapshot changed during corpus processing")
    for input_path, content in input_bytes.items():
        if input_path.read_bytes() != content:
            raise ValueError(f"matched input changed during corpus processing: {input_path}")


def _process_cases(
    matched_files: list[Path],
    snapshot_path: Path,
    artifact_directory: Path,
    verification: bool,
) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    snapshot_content = snapshot_path.read_bytes()
    input_bytes = {path: path.read_bytes() for path in matched_files}
    cases: list[dict[str, object]] = []
    output_bytes: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix="ranking-style-corpus-replay-") as replay_root:
        replay_directory = Path(replay_root)
        for matched_path in matched_files:
            matched_content = input_bytes[matched_path]
            matched = MatchedJourneySet.model_validate_json(matched_content)
            raw_matched = json.loads(matched_content)
            output_name = f"{matched_path.stem}.json"
            generated_path = artifact_directory / output_name
            if verification:
                generated_path = replay_directory / output_name
            generated_content = _run_cli(matched_path, snapshot_path, generated_path)
            ranked = RankedJourneySet.model_validate_json(generated_content)
            _assert_case_integrity(matched, raw_matched, ranked)

            replay_path = replay_directory / f"second-{output_name}"
            replay_content = _run_cli(matched_path, snapshot_path, replay_path)
            RankedJourneySet.model_validate_json(replay_content)
            if generated_content != replay_content:
                raise ValueError(f"second replay differs byte-for-byte for {matched_path.name}")
            output_bytes[output_name] = generated_content
            cases.append(_case_index(
                matched_path.name,
                output_name,
                matched_content,
                generated_content,
                ranked,
            ))
    _recheck_inputs(input_bytes, snapshot_path, snapshot_content)
    return cases, output_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched-dir", type=Path, default=Path("evidence/ranking-stage/m1"))
    parser.add_argument("--fx-snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify", action="store_true",
                        help="Recompute and compare artifacts in an existing output directory.")
    args = parser.parse_args(argv)

    matched_files = _input_files(args.matched_dir)
    output_directory = args.output_dir
    if args.verify:
        if output_directory.is_symlink() or not output_directory.is_dir():
            raise ValueError("verification output directory must be an existing real directory")
    else:
        if output_directory.exists() or output_directory.is_symlink():
            raise ValueError("output directory must be new")
        output_directory.parent.mkdir(parents=True, exist_ok=True)
        output_directory.mkdir()

    cases, output_bytes = _process_cases(
        matched_files, args.fx_snapshot, output_directory, args.verify
    )
    expected_index = _index_bytes(cases)
    if args.verify:
        expected_names = {"index.json", *output_bytes}
        actual_names = {path.name for path in output_directory.iterdir()}
        if actual_names != expected_names:
            raise ValueError("verification output directory has missing or unexpected artifacts")
        for output_name, content in output_bytes.items():
            if (output_directory / output_name).read_bytes() != content:
                raise ValueError(f"saved output differs from replay: {output_name}")
        if (output_directory / "index.json").read_bytes() != expected_index:
            raise ValueError("saved corpus index differs from recomputed evidence")
    else:
        for output_name, content in output_bytes.items():
            if (output_directory / output_name).read_bytes() != content:
                raise ValueError(f"generated output changed before indexing: {output_name}")
        with (output_directory / "index.json").open("xb") as stream:
            stream.write(expected_index)

    print(json.dumps({"output_dir": str(output_directory), "cases": len(cases)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
