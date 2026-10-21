"""Freeze and replay source-bound, offline Results presentation examples.

No model or provider adapter is imported. Existing iterations are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, ResultsDocument, ResultsPart, ResultsSelection, run_results, replay_results


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "2026-10-08-golden-diagnostic" / "early-2027" / "runs"
CASES = {
    "admitted": SOURCE / "mixed_award_cash_eligible" / "continuation-3",
    "conditional": SOURCE / "typo_recognizable_date" / "continuation-3",
    "incomplete": SOURCE / "ready_whole_month",
}
VERSION = "results-artifact-v4"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        output.write(content)


def journey(label: str, candidate_id: str, conditional: bool) -> ResultsPart:
    opening = (
        "This itinerary needs a few checks before you can rely on it. "
        "The cash flight to Los Angeles and the award flight onward are separate tickets.\n\n"
        if conditional else
        "A complete award itinerary was found in these records.\n\n"
    )
    cash = (
        "**Separate cash flight:** {{fact:cash_route}}, {{fact:cash_departure}} to "
        "{{fact:cash_arrival}}; {{fact:cash}}. Reported cabin: {{fact:cash_cabin}}; "
        "leg cabins: {{fact:cash_leg_cabins}}. Quote scope: {{fact:cash_price_scope}}. "
        "Time between flights: {{fact:transfer}}. Observed {{fact:cash_observed_at}}.\n\n"
        if conditional else ""
    )
    tail = (
        "Please confirm the traveler count and whether separate positioning travel works for you. "
        "Baggage, check-in, terminal, transit, missed-connection arrangements and protection "
        "between the tickets have not been verified.\n\n"
        if conditional else
        "The itinerary-level cabin report does not confirm the cabin on each flight.\n\n"
    )
    markdown = (
        f"## Option {label}\n\n" + opening +
        "**Travel:** {{fact:route}}. Leave {{fact:departure}}; arrive {{fact:arrival}}. "
        "Total travel time: {{fact:elapsed}}. {{fact:status}}; {{fact:styles}}.\n\n"
        "**Award flight:** {{fact:award_route}}, {{fact:award_departure}} to "
        "{{fact:award_arrival}}. Book through {{fact:award_program}}; reported airlines: "
        "{{fact:award_carrier}}. Reported cabin: {{fact:award_cabin}}; flights: "
        "{{fact:award_leg_cabins}}. {{fact:points}} plus {{fact:fees}}. "
        "Quote scope: {{fact:award_price_scope}}; price information: "
        "{{fact:price_completeness}}. Observed {{fact:award_observed_at}}.\n\n"
        + cash +
        "**Before booking:** {{fact:booking_obligation}}. {{fact:requirements}} " + tail
    )
    return ResultsPart(scope="journey", reference_id=candidate_id,
                       identifier=f"Option {label}", markdown=markdown)


def benchmark(observation_id: str) -> ResultsPart:
    return ResultsPart(scope="benchmark", reference_id=observation_id,
        identifier="Cash comparison",
        markdown=(
            "## Cash comparison\n\n"
            "This is a separate direct cash quote, not an award option. "
            "{{fact:route}} on {{fact:carrier}}: leave {{fact:departure}}; "
            "arrive {{fact:arrival}}. Reported fare: {{fact:cash}}. "
            "The fare's traveler scope is {{fact:price_scope}}. "
            "Cabin: {{fact:cabin}}; flight cabins: {{fact:leg_cabins}}. "
            "Observed {{fact:observed_at}}; provider update: {{fact:provider_updated_at}}. "
            "{{fact:disposition}}.\n\n"
        ))


def incomplete(label: str, observation_id: str) -> ResultsPart:
    return ResultsPart(scope="incomplete", reference_id=observation_id,
        identifier=f"Lead {label}",
        markdown=(
            f"### Lead {label}\n\n"
            "{{fact:program}} reports {{fact:points}} points plus {{fact:fees}} "
            "for {{fact:route}}. Reported cabin: {{fact:cabin}}; individual flights: "
            "{{fact:leg_cabins}}. Quote scope: {{fact:price_scope}}. "
            "Departure and arrival times: {{fact:departure}}; {{fact:arrival}}. "
            "Observed {{fact:observed_at}}; provider update: {{fact:provider_updated_at}}. "
            "{{fact:disposition}}.\n\n"
        ))


def draft_for(case: str, original: dict) -> ResultsDocument:
    source_doc = original["attempts"][original["selected_attempt"]]["document"]
    selection = ResultsSelection.model_validate(source_doc["selection"])
    if case == "admitted":
        introduction = (
            "# Award flights from San Francisco to Bangkok\n\n"
            "Three award itineraries stood out for January 15, 2027. These are observed "
            "results, so confirm current availability and the final price before transferring "
            "points or booking. Some planned award-detail searches were not completed. "
            "{{fact:provider_status}}. {{fact:coverage}}.\n\n"
        )
    elif case == "conditional":
        introduction = (
            "# Ways to reach Bangkok from San Francisco\n\n"
            "These January 8, 2027 options combine a cash flight to Los Angeles with an award "
            "flight to Bangkok. Each needs confirmation before booking, including permission "
            "for separate positioning travel. Some planned searches were not completed. "
            "{{fact:provider_status}}. {{fact:coverage}}.\n\n"
        )
    else:
        introduction = (
            "# Bangkok award search for January 2027\n\n"
            "I can't recommend a complete award itinerary from these results yet. The direct "
            "award-detail search was not completed, and the search through Taipei was only "
            "partial. The leads below have no confirmed flight schedule or booking path. "
            "{{fact:complete_journey_count}} complete journeys; {{fact:provider_status}}. "
            "{{fact:coverage}}.\n\n"
        )
    parts = [ResultsPart(scope="shared", markdown=introduction)]
    if selection.journey_ids:
        parts.extend(journey(chr(65 + index), rid, case == "conditional")
                     for index, rid in enumerate(selection.journey_ids))
    if selection.benchmark_observation_id:
        parts.append(benchmark(selection.benchmark_observation_id))
    if selection.incomplete_observation_ids:
        parts.append(ResultsPart(scope="shared", markdown=(
            "## Award leads that need more detail\n\n"
            "These are award summaries only. Their dates, cabins and prices do not establish "
            "complete itineraries, confirmed seats or protection for a connection.\n\n")))
        parts.extend(incomplete(chr(65 + index), rid)
                     for index, rid in enumerate(selection.incomplete_observation_ids))
    return ResultsDocument(selection=selection, parts=tuple(parts))


class FrozenWriter:
    def __init__(self, document: ResultsDocument):
        self.document = document

    def author(self, prepared, config, feedback=(), previous_document=None):
        return self.document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration", help="New iteration directory, for example 001")
    parser.add_argument("--freeze-drafts", action="store_true",
                        help="Create missing hand-authored draft fixtures from these templates")
    args = parser.parse_args()
    iteration = ROOT / "offline" / args.iteration
    if iteration.exists() and any((iteration / case / "artifact.json").exists() for case in CASES):
        parser.error("iteration already has rendered evidence; use a new iteration name")
    config = ResultsConfig(model="offline-frozen-document", max_output_tokens=32768,
                           timeout_seconds=30, context_limit_tokens=100000000,
                           prompt_overhead_tokens=100)
    manifest = {"iteration": args.iteration, "render_version": VERSION,
                "method": "offline frozen ResultsDocument; no model or provider calls", "cases": {}}
    pending = []
    for case, source in CASES.items():
        source_artifact = source / "results-artifact.json"
        baseline = source / "answer.md"
        projection_file = source / "solutions.json"
        original = json.loads(source_artifact.read_text())
        fixture = iteration / case / "document.json"
        if args.freeze_drafts and not fixture.exists():
            write_new(fixture, draft_for(case, original).model_dump_json(indent=2) + "\n")
        document = ResultsDocument.model_validate_json(fixture.read_text())
        projection = SolutionProjection.model_validate_json(projection_file.read_text())
        artifact = run_results(projection, config, FrozenWriter(document), render_version=VERSION)
        if artifact.delivery_outcome != "delivered" or artifact.validation_outcome != "clean":
            codes = [f.code for attempt in artifact.attempts for f in attempt.findings
                     if f.outcome == "failed"]
            raise ValueError(f"{case}: {artifact.delivery_outcome}/{artifact.validation_outcome}: {codes}")
        if replay_results(artifact) != artifact.rendered_markdown:
            raise ValueError(f"{case}: replay mismatch")
        pending.append((iteration / case / "artifact.json", artifact.model_dump_json(indent=2) + "\n"))
        pending.append((iteration / case / "answer.md", artifact.rendered_markdown))
        manifest["cases"][case] = {
            "source": str(source.relative_to(ROOT.parent)),
            "source_projection_sha256": sha(projection_file),
            "source_artifact_sha256": sha(source_artifact),
            "baseline_answer_sha256": sha(baseline),
            "draft_sha256": sha(fixture),
            "selected_journeys": len(document.selection.journey_ids),
            "selected_incomplete_leads": len(document.selection.incomplete_observation_ids),
            "findings": {outcome: sum(f.outcome == outcome for a in artifact.attempts for f in a.findings)
                         for outcome in ("supported", "failed", "unchecked", "insufficient_evidence")},
            "validation_outcome": artifact.validation_outcome,
            "delivery_outcome": artifact.delivery_outcome,
            "rendered_digest": artifact.rendered_digest,
        }
    pending.append((iteration / "manifest.json", json.dumps(manifest, indent=2) + "\n"))
    for path, content in pending:
        write_new(path, content)
    print(json.dumps({case: details["findings"] for case, details in manifest["cases"].items()}, indent=2))


if __name__ == "__main__":
    main()
