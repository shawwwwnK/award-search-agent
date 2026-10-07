"""Rendered Markdown regressions for the public Results delivery boundary."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

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
    run_results,
)


@pytest.fixture(scope="module")
def projection() -> SolutionProjection:
    path = Path("evidence/ranking-stage/m2/solutions/sfo_to_bkk_positioning.json")
    return SolutionProjection.model_validate(json.loads(path.read_text()))


@pytest.fixture(scope="module")
def config() -> ResultsConfig:
    return ResultsConfig(model="offline-markdown-test", max_output_tokens=10000,
                         timeout_seconds=20, context_limit_tokens=10_000_000,
                         prompt_overhead_tokens=100)


class FakeWriter:
    def __init__(self, document: ResultsDocument) -> None:
        self.document = document
        self.calls = 0

    def author(self, prepared: PreparedResultsInput, config: ResultsConfig,
               feedback: tuple = (), previous_document: ResultsDocument | None = None,
               ) -> ResultsDocument:
        self.calls += 1
        return self.document


class TreeParser(HTMLParser):
    """Keep enough structure to assert visible text's table-cell association."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.cells: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.headers: list[str] = []
        self.column_counts: list[int] = []
        self.text_ancestors: list[tuple[str, str]] = []
        self._row_columns = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack.append(tag)
        if tag in {"td", "th"}:
            self.current = {"tag": tag, "text": "", "ancestors": " ".join(self.stack)}
            self._row_columns += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.current is not None:
            if tag == "th":
                self.headers.append(self.current["text"])
            self.cells.append(self.current)
            self.current = None
        if tag == "tr":
            self.column_counts.append(self._row_columns)
            self._row_columns = 0
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            del self.stack[index:]

    def handle_data(self, data: str) -> None:
        self.text_ancestors.append((data, " ".join(self.stack)))
        if self.current is not None:
            self.current["text"] += data


def _rendered_html(markdown: str) -> str:
    return cast(str, MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown))


def _journeys(projection: SolutionProjection) -> tuple[str, str]:
    ids = tuple(item.candidate_id for item in projection.view.alternatives
                if item.status in {"admitted", "conditional"})
    assert len(ids) >= 2
    return ids[0], ids[1]


def _shared_part() -> ResultsPart:
    return ResultsPart(scope="shared", markdown=(
        "Coverage {{fact:coverage}}. Provider {{fact:provider_status}}. "
        "Benchmark {{fact:benchmark_status}}.\n\n"))


def _fact_stream(projection: SolutionProjection, config: ResultsConfig,
                 journey_id: str) -> str:
    slots = prepare_results(projection, config).slots[f"journey:{journey_id}"]
    return "; ".join(f"{key}: {{{{fact:{key}}}}}" for key in slots)


def _failed_protection_claim(journey_id: str) -> DeclaredClaim:
    return DeclaredClaim(claim_id="connection-protection", kind="connection_protection",
                         proposition="protected_connection", scope_ids=(journey_id,),
                         text="This connection is protected.")


def _artifact(projection: SolutionProjection, config: ResultsConfig,
              parts: tuple[ResultsPart, ...], journey_ids: tuple[str, ...]) -> ResultsArtifact:
    document = ResultsDocument(selection=ResultsSelection(journey_ids=journey_ids), parts=parts)
    return run_results(projection, config, FakeWriter(document))


def test_failed_notice_stays_in_its_cell_when_journeys_share_one_row(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    first, second = _journeys(projection)
    claim = _failed_protection_claim(first)
    parts = (
        _shared_part(),
        ResultsPart(scope="shared", markdown=(
            "| Option | Journey details |\n| --- | --- |\n")),
        ResultsPart(scope="journey", reference_id=first, claims=(claim,), markdown=(
            f"| A: {claim.text}; {_fact_stream(projection, config, first)} |")),
        ResultsPart(scope="journey", reference_id=second, markdown=(
            f" B: a clean alternative; {_fact_stream(projection, config, second)} |\n")),
    )
    artifact = _artifact(projection, config, parts, (first, second))
    assert artifact.validation_outcome == "annotated"

    parser = TreeParser()
    parser.feed(_rendered_html(artifact.rendered_markdown))
    assert parser.headers == ["Option", "Journey details"]
    assert parser.column_counts == [2, 2]
    first_cell = next(cell["text"] for cell in parser.cells if "A: This connection" in cell["text"])
    second_cell = next(cell["text"] for cell in parser.cells if "B: a clean alternative" in cell["text"])
    assert "Validation:" in first_cell
    assert "Validation:" not in second_cell


def test_open_authored_fence_cannot_hide_validation_notice(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey, _ = _journeys(projection)
    claim = _failed_protection_claim(journey)
    part = ResultsPart(scope="journey", reference_id=journey, claims=(claim,), markdown=(
        claim.text + "\n```text\n" + _fact_stream(projection, config, journey)))
    artifact = _artifact(projection, config, (_shared_part(), part), (journey,))
    html = _rendered_html(artifact.rendered_markdown)
    parser = TreeParser()
    parser.feed(html)
    notice = next(ancestors for data, ancestors in parser.text_ancestors if "Validation:" in data)
    assert "pre" not in notice.split()
    assert "code" not in notice.split()


def test_split_table_row_keeps_facts_and_notice_together(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey, _ = _journeys(projection)
    claim = _failed_protection_claim(journey)
    parts = (
        _shared_part(),
        ResultsPart(scope="shared", markdown="| Claim and source facts |\n| --- |\n"),
        ResultsPart(scope="journey", reference_id=journey, claims=(claim,), markdown=(
            "| " + claim.text + " {{fact:journey_id}")),
        ResultsPart(scope="journey", reference_id=journey, markdown=(
            " {{fact:route}} {{fact:points}} {{fact:fees}} " +
            _fact_stream(projection, config, journey) + " |\n")),
    )
    artifact = _artifact(projection, config, parts, (journey,))
    parser = TreeParser()
    parser.feed(_rendered_html(artifact.rendered_markdown))
    row = next(cell["text"] for cell in parser.cells if "This connection is protected" in cell["text"])
    assert "Validation:" in row
    assert journey in row
    assert "65000" in row


def test_escaped_source_pipe_preserves_table_columns_and_valid_prose_controls(
    projection: SolutionProjection, config: ResultsConfig,
) -> None:
    journey, _ = _journeys(projection)
    slots = prepare_results(projection, config).slots[f"journey:{journey}"]
    prose = ResultsPart(scope="journey", reference_id=journey, markdown=(
        "A useful summary names {{fact:journey_id}} and {{fact:route}}.\n\n"
        "| Label | Details |\n| --- | --- |\n"
        "| Result | {{fact:points}} points; source text with escaped pipe \\| intact |\n"
        + _fact_stream(projection, config, journey) + "\n"))
    # All source-backed journey disclosures remain visible, and the answer can mix prose and tables.
    assert "journey_id" in slots and "route" in slots and "points" in slots
    artifact = _artifact(projection, config, (_shared_part(), prose), (journey,))
    parser = TreeParser()
    parser.feed(_rendered_html(artifact.rendered_markdown))
    assert len(parser.column_counts) >= 2
    assert all(columns == 2 for columns in parser.column_counts)
    assert "Result" in " ".join(cell["text"] for cell in parser.cells)
    assert "source text with escaped pipe | intact" in " ".join(
        cell["text"] for cell in parser.cells)
    assert "A useful summary" in _rendered_html(artifact.rendered_markdown)
