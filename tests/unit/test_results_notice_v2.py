"""Versioned notice-placement regressions for public Results replay."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, cast

import pytest
from markdown_it import MarkdownIt

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
    render_results,
    replay_results,
    run_results,
)
from award_agent.results.core import INSTRUCTIONS

ROOT = Path(__file__).resolve().parents[2]
LEGACY_ARTIFACT = ROOT / "evidence/results-stage/m2/sfo_to_bkk_positioning.annotated.artifact.json"
LEGACY_MARKDOWN = ROOT / "evidence/results-stage/m2/sfo_to_bkk_positioning.annotated.md"


class FakeWriter:
    def __init__(self, document: ResultsDocument) -> None:
        self.document = document

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple = (), previous_document: ResultsDocument | None = None,
               ) -> ResultsDocument:
        del prepared, config, feedback, previous_document
        return self.document


class HeadingOrder(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, str]] = []
        self.active: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "h2"}:
            self.active = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self.active:
            self.active = None

    def handle_data(self, data: str) -> None:
        if self.active is not None and data.strip():
            self.tags.append((self.active, data.strip()))


@pytest.fixture(scope="module")
def projection() -> SolutionProjection:
    path = ROOT / "evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json"
    return SolutionProjection.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def config() -> ResultsConfig:
    return ResultsConfig(model="offline-notice-test", max_output_tokens=10000,
                         timeout_seconds=20, context_limit_tokens=10_000_000,
                         prompt_overhead_tokens=100)


def _document(projection: SolutionProjection) -> ResultsDocument:
    journey_id = next(item.candidate_id for item in projection.view.alternatives
                      if item.status in {"admitted", "conditional"})
    claim = DeclaredClaim(claim_id="connection-protection", kind="connection_protection",
                          proposition="protected_connection", scope_ids=(journey_id,),
                          text="This connection is protected.")
    return ResultsDocument(
        selection=ResultsSelection(journey_ids=(journey_id,)),
        parts=(
            ResultsPart(scope="journey", reference_id=journey_id,
                        markdown="This connection is protected.", claims=(claim,)),
            ResultsPart(scope="journey", reference_id=journey_id,
                        markdown="## Next part\n\nMore detail."),
        ),
    )


def test_v2_notice_stays_before_following_part_heading(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    artifact = run_results(projection, config, FakeWriter(_document(projection)),
                           render_version="results-artifact-v2")
    assert artifact.contract_version == "results-artifact-v2"
    rendered = artifact.rendered_markdown
    assert rendered.index("Validation:") < rendered.index("## Next part")
    assert "\n\n## Next part" in rendered

    html = cast(str, MarkdownIt("commonmark").render(rendered))
    parser = HeadingOrder()
    parser.feed(html)
    notice_index = next(i for i, (_, content) in enumerate(parser.tags)
                        if "Validation:" in content)
    heading_index = next(i for i, (tag, content) in enumerate(parser.tags)
                         if tag == "h2" and content == "Next part")
    assert notice_index < heading_index
    assert replay_results(artifact).encode("utf-8") == rendered.encode("utf-8")


def test_v1_artifact_replay_keeps_saved_bytes_and_explicit_v1_rendering(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    raw_artifact = LEGACY_ARTIFACT.read_bytes()
    saved = ResultsArtifact.model_validate_json(raw_artifact)
    assert saved.contract_version == "results-artifact-v1"
    assert replay_results(saved).encode("utf-8") == LEGACY_MARKDOWN.read_bytes()

    generated = run_results(projection, config, FakeWriter(_document(projection)),
                            render_version="results-artifact-v1")
    assert generated.contract_version == "results-artifact-v1"
    assert replay_results(generated).encode("utf-8") == generated.rendered_markdown.encode("utf-8")


def test_unknown_render_version_fails_before_authoring(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    document = _document(projection)
    unknown = cast("Literal['results-artifact-v1', 'results-artifact-v2', 'results-artifact-v3']",
                   "results-artifact-v4")
    with pytest.raises(ValueError, match="unsupported Results render version"):
        render_results(document, projection, render_version=unknown)
    with pytest.raises(ValueError, match="unsupported Results render version"):
        run_results(projection, config, FakeWriter(document), render_version=unknown)


def test_optional_guidance_is_replayed_and_none_preserves_default_instructions(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    assert prepare_results(projection, config, version="results-artifact-v2").instructions == INSTRUCTIONS

    guidance = "Keep each option's notice with its originating prose part."
    guided_config = config.model_copy(update={"authoring_guidance": guidance})
    prepared = prepare_results(projection, guided_config, version="results-artifact-v2")
    assert prepared.instructions == INSTRUCTIONS + "\n\n" + guidance

    artifact = run_results(projection, guided_config, FakeWriter(_document(projection)),
                           render_version="results-artifact-v2")
    reloaded = ResultsArtifact.model_validate_json(artifact.model_dump_json())
    assert reloaded.prepared.instructions == prepared.instructions
    assert replay_results(reloaded).encode("utf-8") == artifact.rendered_markdown.encode("utf-8")
