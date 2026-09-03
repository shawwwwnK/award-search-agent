from datetime import date

import pytest

from award_agent.domain import (
    AnchorWindowConstraint,
    CoarseIntentExtraction,
    DecisionReference,
    Holiday,
    HolidayAnchor,
    MonthAnchor,
    RawRequest,
    RelativeWeekdayConstraint,
    RequestContext,
    TemporalComposition,
    TemporalDirection,
    TemporalEdge,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalRelationGraph,
    TemporalTarget,
    Weekday,
)
from award_agent.intent.conformance import validate_temporal_conformance
from award_agent.intent.evidence import (
    TemporalResolutionValidationError,
    assign_stable_anchor_ids,
    ground_temporal_evidence,
)
from award_agent.intent.model_views import (
    TemporalInterpretationInput,
    build_temporal_interpretation_input,
)
from award_agent.intent.openai_extractor import TemporalDecisionSetWire, TemporalDecisionWire
from award_agent.intent.temporal import (
    enrich_temporal_anchors,
    evaluate_temporal_relation_graph,
)


class LaborDayProvider:
    def holiday_date(self, holiday: Holiday, year: int) -> date:
        assert (holiday, year) == (Holiday.LABOR_DAY, 2026)
        return date(2026, 9, 7)


def _fixture() -> tuple[RawRequest, CoarseIntentExtraction, TemporalInterpretationInput]:
    request = RawRequest(
        text=(
            "Leave Labor Day weekend for about 10 days. We are flexible to leave Thursday as well."
        ),
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
    )
    extraction = CoarseIntentExtraction(
        date_anchors=[
            HolidayAnchor(
                kind="holiday",
                anchor_id="model-local",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="Labor Day",
                holiday=Holiday.LABOR_DAY,
            )
        ],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="Labor Day weekend",
                claim_ids=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="about 10 days",
                claim_ids=[TemporalEvidenceClaim.APPROXIMATE_DURATION],
            ),
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text="We are flexible to leave Thursday as well",
                claim_ids=[TemporalEvidenceClaim.ALTERNATE_DEPARTURE_DAY],
            ),
        ],
    )
    evidence = ground_temporal_evidence(request, extraction)
    extraction = assign_stable_anchor_ids(request, extraction)
    return (
        request,
        extraction,
        build_temporal_interpretation_input(request.text, extraction, evidence),
    )


def _decisions(
    *, weekday_combine: TemporalComposition = TemporalComposition.EXTEND_START
) -> TemporalDecisionSetWire:
    return TemporalDecisionSetWire(
        decisions=[
            TemporalDecisionWire(
                evidence="e1",
                relation_kind="anchor_window",
                target="departure",
                anchor="a0",
                window="holiday_weekend",
                combine=TemporalComposition.BASE,
            ),
            TemporalDecisionWire(
                evidence="e3",
                relation_kind="relative_weekday",
                target="departure",
                reference="e1",
                reference_kind="decision",
                reference_edge="start",
                direction="before",
                ordinal=1,
                weekday="thursday",
                combine=weekday_combine,
                combine_with_evidence="e1",
            ),
            TemporalDecisionWire(
                evidence="e2",
                relation_kind="duration",
                target="return",
                stated_minimum_quantity=10,
                stated_maximum_quantity=10,
                unit="day",
                modifier="approximate",
            ),
        ]
    )


def test_contract_v2_hides_canonical_ids_and_enforces_local_handle_enums() -> None:
    _, _, model_input = _fixture()
    payload = model_input.model_dump(mode="json")
    assert payload["temporal_transcript"] != (
        "Leave Labor Day weekend for about 10 days. We are flexible to leave Thursday as well."
    )
    assert [entry["handle"] for entry in payload["evidence_catalog"]] == ["e0", "e1", "e2", "e3"]
    weekday_entry = payload["evidence_catalog"][3]
    assert weekday_entry == {
        "handle": "e3",
        "text": "We are flexible to leave Thursday as well",
        "allowed_targets": ["departure"],
        "allowed_relation_kinds": [
            "anchor_window",
            "month_portion",
            "relative_calendar_period",
            "relative_weekend",
            "relative_weekday",
            "relative_offset",
            "unbounded_boundary",
            "unresolved",
        ],
    }
    assert "[e3] We are flexible to leave Thursday as well" in payload["temporal_transcript"]
    assert "request:" not in str(payload)
    assert "anchor:" not in str(payload)
    assert "source_start" not in str(payload)
    assert "claim_labels" not in str(payload)
    schema = TemporalDecisionSetWire.for_input(model_input).model_json_schema()
    assert schema["$defs"]["TemporalDecisionWireForInput"]["properties"]["evidence"]["enum"] == [
        "e0",
        "e1",
        "e2",
        "e3",
    ]


def test_decision_target_must_be_permitted_by_its_local_evidence_entry() -> None:
    _, _, model_input = _fixture()
    invalid = TemporalDecisionSetWire(
        decisions=[
            TemporalDecisionWire(
                evidence="e3",
                relation_kind="relative_weekday",
                target="return",
                reference="e1",
                reference_kind="decision",
                reference_edge="start",
                direction="before",
                ordinal=1,
                weekday="thursday",
            )
        ]
    )

    with pytest.raises(TemporalResolutionValidationError) as captured:
        invalid.to_domain(model_input)

    assert captured.value.details.error_code == "incompatible_evidence_target"


def test_representative_decisions_entail_windows_and_whole_interval_duration() -> None:
    request, extraction, model_input = _fixture()
    graph = _decisions().to_domain(model_input)
    validate_temporal_conformance(model_input, graph)
    proposal = evaluate_temporal_relation_graph(
        request, extraction, graph, enrich_temporal_anchors(request, extraction, LaborDayProvider())
    )
    assert proposal.departure is not None
    assert (proposal.departure.start, proposal.departure.end) == (
        date(2026, 9, 3),
        date(2026, 9, 7),
    )
    assert proposal.return_date is not None
    assert (proposal.return_date.start, proposal.return_date.end) == (
        date(2026, 9, 12),
        date(2026, 9, 18),
    )
    duration = next(item for item in graph.constraints if item.kind == "duration")
    assert duration.reference.scope.value == "whole_interval"
    assert duration.reference.edge is None


def test_intersect_instead_of_extend_start_is_an_explicit_empty_window_conflict() -> None:
    request, extraction, model_input = _fixture()
    graph = _decisions(weekday_combine=TemporalComposition.INTERSECT).to_domain(model_input)
    with pytest.raises(Exception, match="empty temporal window"):
        evaluate_temporal_relation_graph(
            request,
            extraction,
            graph,
            enrich_temporal_anchors(request, extraction, LaborDayProvider()),
        )


def test_decision_reference_reads_the_prior_composed_window_not_its_raw_candidate() -> None:
    request, extraction, model_input = _fixture()
    anchor_id = model_input._anchor_ids["a0"]
    graph = TemporalRelationGraph(
        constraints=[
            AnchorWindowConstraint(
                kind="anchor_window",
                constraint_id="relation:e1",
                combine=TemporalComposition.BASE,
                target=TemporalTarget.DEPARTURE,
                anchor_id=anchor_id,
                window="holiday_weekend",
                raw_text="Labor Day weekend",
            ),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                constraint_id="relation:e3",
                combine=TemporalComposition.EXTEND_START,
                combine_with="relation:e1",
                target=TemporalTarget.DEPARTURE,
                reference=DecisionReference(
                    kind="decision",
                    constraint_id="relation:e1",
                    edge=TemporalEdge.START,
                ),
                direction=TemporalDirection.BEFORE,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                raw_text="We are flexible to leave Thursday as well",
            ),
            RelativeWeekdayConstraint(
                kind="relative_weekday",
                constraint_id="relation:e4",
                combine=TemporalComposition.BASE,
                target=TemporalTarget.DEPARTURE,
                reference=DecisionReference(
                    kind="decision",
                    constraint_id="relation:e3",
                    edge=TemporalEdge.START,
                ),
                direction=TemporalDirection.BEFORE,
                ordinal=1,
                weekday=Weekday.THURSDAY,
                raw_text="Thursday as well",
            ),
        ]
    )

    proposal = evaluate_temporal_relation_graph(
        request,
        extraction,
        graph,
        enrich_temporal_anchors(request, extraction, LaborDayProvider()),
    )

    # e3 composes its raw September 3 weekday with e1's September 4--7 window, exposing a
    # September 3 start.  A reference to e3 therefore resolves to August 27, not September 3.
    assert proposal.departure is not None
    assert (proposal.departure.start, proposal.departure.end) == (
        date(2026, 8, 27),
        date(2026, 8, 27),
    )


def _anchor_only_input(
    text: str,
    anchor: HolidayAnchor | MonthAnchor,
    phrase: str,
) -> TemporalInterpretationInput:
    extraction = CoarseIntentExtraction(
        date_anchors=[anchor],
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DEPARTURE,
                raw_text=phrase,
                claim_ids=[TemporalEvidenceClaim.DEPARTURE_PERIOD],
            )
        ]
        if phrase != anchor.raw_text
        else [],
    )
    raw_request = RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 29), timezone="UTC"),
    )
    evidence = ground_temporal_evidence(raw_request, extraction)
    extraction = assign_stable_anchor_ids(raw_request, extraction)
    return build_temporal_interpretation_input(text, extraction, evidence)


def test_deterministic_assembly_inserts_a_plain_direct_literal_anchor() -> None:
    model_input = _anchor_only_input(
        "Travel in June.",
        MonthAnchor(
            kind="month",
            anchor_id="model-local",
            applies_to=TemporalTarget.DEPARTURE,
            raw_text="June",
            month=6,
        ),
        "June",
    )

    graph = TemporalDecisionSetWire().to_domain(model_input)

    assert [(constraint.kind, constraint.target) for constraint in graph.constraints] == [
        ("month_portion", TemporalTarget.DEPARTURE)
    ]


@pytest.mark.parametrize(
    ("text", "anchor", "phrase"),
    [
        (
            "Travel after New Year.",
            HolidayAnchor(
                kind="holiday",
                anchor_id="model-local",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="New Year",
                holiday=Holiday.NEW_YEARS_DAY,
            ),
            "after New Year",
        ),
        (
            "Travel the weekend after Labor Day.",
            HolidayAnchor(
                kind="holiday",
                anchor_id="model-local",
                applies_to=TemporalTarget.DEPARTURE,
                raw_text="Labor Day",
                holiday=Holiday.LABOR_DAY,
            ),
            "the weekend after Labor Day",
        ),
    ],
)
def test_relative_holiday_wording_does_not_insert_an_anchor_target_window(
    text: str,
    anchor: HolidayAnchor,
    phrase: str,
) -> None:
    model_input = _anchor_only_input(text, anchor, phrase)

    graph = TemporalDecisionSetWire().to_domain(model_input)

    assert graph.constraints == []
