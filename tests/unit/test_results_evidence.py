"""Independent source-backed outcomes through the public Results seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from award_agent.providers.contracts import RawField, content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    DeclaredClaim,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    prepare_results,
    replay_results,
    run_results,
)
from award_agent.results.adapter import OpenAIResultsWriter
from award_agent.results.contracts import CheckFinding

SOURCE = Path("evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json")
JOURNEY = "f7d024bb65a87fe25bd14e71dbbf51c35f0a1995e3e9cc22fa112e677ed7eab9"


@pytest.fixture(scope="module")
def source() -> SolutionProjection:
    return SolutionProjection.model_validate_json(SOURCE.read_bytes())


@pytest.fixture(scope="module")
def settings() -> ResultsConfig:
    return ResultsConfig(model="offline-test", max_output_tokens=10000, timeout_seconds=20,
                         context_limit_tokens=10000000, prompt_overhead_tokens=100)


class Writer:
    def __init__(self, *drafts: ResultsDocument) -> None:
        self.drafts = drafts
        self.calls = 0

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple[CheckFinding, ...] = (),
               previous_document: ResultsDocument | None = None) -> ResultsDocument:
        draft = self.drafts[min(self.calls, len(self.drafts) - 1)]
        self.calls += 1
        return draft


def document(source: SolutionProjection, settings: ResultsConfig,
             claims: tuple[DeclaredClaim, ...] = (), journey: str = JOURNEY) -> ResultsDocument:
    slots = prepare_results(source, settings).slots[f"journey:{journey}"]
    # A deterministic fixture writer chooses all slots. Expected values below come from
    # frozen upstream evidence, never from these generated slot strings.
    return ResultsDocument(selection=ResultsSelection(journey_ids=(journey,)), parts=(
        ResultsPart(scope="shared", markdown="Coverage {{fact:coverage}}; "
                    "search {{fact:provider_status}}; benchmark {{fact:benchmark_status}}.\n\n"),
        ResultsPart(scope="journey", reference_id=journey,
                    markdown="\n".join(f"{key}: {{{{fact:{key}}}}}" for key in slots) + "\n\n" +
                    "\n".join(claim.text for claim in claims), claims=claims),
    ))


def test_frozen_exact_variant_values_program_cabin_scope_and_date_line(
    source: SolutionProjection, settings: ResultsConfig,
) -> None:
    artifact = run_results(source, settings, Writer(document(source, settings)))
    assert artifact.validation_outcome == "clean"
    visible = artifact.rendered_markdown
    assert "65000" in visible
    assert "11320 CAD" in visible
    assert "minor" in visible
    assert "196 USD" in visible
    assert "1790 minutes" in visible
    assert "380 minutes at SIN" in visible
    assert "aeroplan" in visible
    assert "BR, UA" in visible
    assert "economy" in visible
    assert "unknown" in visible  # unreported cash cabin and quote scope remain unknown
    assert "2026" in visible and "23:45:00" in visible and "19:35:00" in visible
    assert "America/Los" in visible and "Asia/Bangkok" in visible
    assert "2026" in visible and "05:47:43" in visible  # component observation times
    assert replay_results(ResultsArtifact.model_validate_json(artifact.model_dump_json())) == visible


@pytest.mark.parametrize(("kind", "proposition", "expected"), [
    ("cabin", "journey_business", "failed"),
    ("cabin", "all_legs_business", "insufficient_evidence"),
    ("connection_protection", "protected_connection", "failed"),
    ("price_scope", "party_total", "insufficient_evidence"),
    ("eligibility", "no_unresolved_requirements", "failed"),
    ("other", "personal_redeemability", "unchecked"),
])
def test_five_family_outcomes_keep_absent_evidence_distinct(
    source: SolutionProjection, settings: ResultsConfig,
    kind: str, proposition: str, expected: str,
) -> None:
    claim = DeclaredClaim.model_validate({"claim_id": "claim", "kind": kind,
        "proposition": proposition, "scope_ids": (JOURNEY,), "text": "A declared assertion."})
    artifact = run_results(source, settings, Writer(document(source, settings, (claim,))))
    finding = next(f for f in artifact.attempts[0].findings
                   if f.code.startswith("claim:"))
    assert finding.outcome == expected
    assert artifact.delivery_outcome == "delivered"
    if expected in {"unchecked", "insufficient_evidence"}:
        assert artifact.validation_outcome == "clean"
        assert len(artifact.attempts) == 1


def test_worsening_correction_keeps_initial_but_tie_prefers_correction(
    source: SolutionProjection, settings: ResultsConfig,
) -> None:
    first = DeclaredClaim(claim_id="cabin", kind="cabin", proposition="journey_business",
                          scope_ids=(JOURNEY,), text="Business award cabin.")
    second = DeclaredClaim(claim_id="protection", kind="connection_protection",
                           proposition="protected_connection", scope_ids=(JOURNEY,),
                           text="Protected transfer.")
    initial = document(source, settings, (first,))
    worse = document(source, settings, (first, second))
    artifact = run_results(source, settings, Writer(initial, worse))
    assert artifact.selected_attempt == 0
    assert "Business award cabin" in artifact.rendered_markdown
    assert "Protected transfer" not in artifact.rendered_markdown
    tied = run_results(source, settings, Writer(initial, initial))
    assert tied.selected_attempt == 1
    assert tied.selection_reason == "correction_tie"


def test_observed_zero_fees_and_missing_fees_are_distinct(
    source: SolutionProjection, settings: ResultsConfig,
) -> None:
    alt = next(a for a in source.view.alternatives if a.candidate_id == JOURNEY)
    for raw, expected in ((RawField(state="value", value=0), "0 CAD"),
                          (RawField(state="absent"), "unknown CAD")):
        components = tuple(c.model_copy(update={"taxes_fees": raw})
                           if c.observation_id == alt.award_observation_id else c
                           for c in source.view.components)
        view = source.view.model_copy(update={"components": components})
        receipt = source.receipt.model_copy(update={"view_digest": content_digest(view)})
        synthetic = SolutionProjection(view=view, receipt=receipt)
        artifact = run_results(synthetic, settings, Writer(document(synthetic, settings)))
        assert expected in artifact.rendered_markdown


def test_replay_detects_rendered_byte_corruption(source: SolutionProjection,
                                                settings: ResultsConfig) -> None:
    artifact = run_results(source, settings, Writer(document(source, settings)))
    corrupted = artifact.model_copy(update={"rendered_markdown": "changed"})
    with pytest.raises(ValueError, match="replay exactly"):
        replay_results(corrupted)


@pytest.mark.parametrize("kind", ["cabin", "price_scope"])
def test_known_contradiction_is_failed_even_when_other_evidence_is_missing(
    source: SolutionProjection, settings: ResultsConfig, kind: str,
) -> None:
    alternative = next(a for a in source.view.alternatives if a.candidate_id == JOURNEY)
    award = next(c for c in source.view.components
                 if c.observation_id == alternative.award_observation_id)
    if kind == "cabin":
        # One reported economy leg contradicts all-legs-business despite another unknown leg.
        legs = (award.legs[0].model_copy(update={"cabin": RawField(state="value", value="economy")}),
                *award.legs[1:])
        updated = award.model_copy(update={"legs": legs})
        proposition = "all_legs_business"
    else:
        # A per-traveler award is not a party total even if cash quote scope is unknown.
        updated = award.model_copy(update={"price_scope": "per_traveler"})
        proposition = "party_total"
    view = source.view.model_copy(update={"components": tuple(
        updated if c.observation_id == award.observation_id else c for c in source.view.components)})
    synthetic = SolutionProjection(view=view, receipt=source.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    claim = DeclaredClaim.model_validate({"claim_id": "contradiction", "kind": kind,
        "proposition": proposition, "scope_ids": (JOURNEY,),
        "text": "This claim has a known contradiction."})
    artifact = run_results(synthetic, settings, Writer(document(synthetic, settings, (claim,))))
    finding = next(f for f in artifact.attempts[0].findings if f.code.startswith("claim:"))
    assert finding.outcome == "failed"


@pytest.mark.parametrize("proposition", ["fastest", "cheapest"])
def test_comparisons_use_supplied_reference_and_complete_pool(
    source: SolutionProjection, settings: ResultsConfig, proposition: str,
) -> None:
    journey = next(a.candidate_id for a in source.view.alternatives
                   if a.candidate_id in source.view.comparison_pool_ids
                   and a.elapsed_microseconds == source.view.time_reference_microseconds)
    claim = DeclaredClaim(claim_id="comparison", kind="comparison", proposition=proposition,
                          scope_ids=source.view.comparison_pool_ids, text="A scoped comparison.")
    artifact = run_results(source, settings, Writer(document(source, settings, (claim,), journey)))
    finding = next(f for f in artifact.attempts[0].findings if f.code.startswith("claim:"))
    assert finding.outcome == ("supported" if proposition == "fastest" else "insufficient_evidence")


@pytest.mark.parametrize(("cash_cabin", "proposition", "expected"), [
    ("economy", "all_legs_business", "failed"),
    (None, "all_legs_business", "insufficient_evidence"),
    ("economy", "all_award_legs_business", "supported"),
])
def test_all_leg_claims_keep_cash_cabin_separate_from_award_legs(
    source: SolutionProjection, settings: ResultsConfig,
    cash_cabin: str | None, proposition: str, expected: str,
) -> None:
    alternative = next(a for a in source.view.alternatives if a.candidate_id == JOURNEY)
    components = []
    for component in source.view.components:
        if component.observation_id == alternative.award_observation_id:
            component = component.model_copy(update={"legs": tuple(
                leg.model_copy(update={"cabin": RawField(state="value", value="business")})
                for leg in component.legs)})
        elif component.observation_id == alternative.cash_observation_id:
            cabin = RawField(state="value", value=cash_cabin) if cash_cabin else RawField(state="absent")
            component = component.model_copy(update={"cabin": cabin})
        components.append(component)
    view = source.view.model_copy(update={"components": tuple(components)})
    synthetic = SolutionProjection(view=view, receipt=source.receipt.model_copy(
        update={"view_digest": content_digest(view)}))
    claim = DeclaredClaim(claim_id="all_legs", kind="cabin", proposition=proposition,
                          scope_ids=(JOURNEY,), text="A cabin assertion with exact evidence scope.")
    artifact = run_results(synthetic, settings, Writer(document(synthetic, settings, (claim,))))
    finding = next(f for f in artifact.attempts[0].findings if f.code.startswith("claim:"))
    assert finding.outcome == expected


@pytest.mark.parametrize("variant", ["clean", "annotated"])
def test_saved_artifact_replays_exact_bytes_without_writer(
    variant: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def never_author(*args: object, **kwargs: object) -> ResultsDocument:
        raise AssertionError("Replay must never invoke a writer")

    monkeypatch.setattr(OpenAIResultsWriter, "author", never_author)
    folder = Path("evidence/results-stage/m2")
    stem = f"sfo_to_bkk_positioning.{variant}"
    artifact = ResultsArtifact.model_validate_json((folder / f"{stem}.artifact.json").read_bytes())
    assert replay_results(artifact).encode("utf-8") == (folder / f"{stem}.md").read_bytes()
    assert artifact.validation_outcome == variant
    assert artifact.selected_attempt == 0
    assert len(artifact.attempts) == (1 if variant == "clean" else 2)
