from datetime import date

import pytest
from pydantic import ValidationError

from award_agent.domain import (
    CoarseIntentExtraction,
    MonthAnchor,
    RawRequest,
    RequestContext,
    TemporalAnchor,
    TemporalEvidenceClaim,
    TemporalPhrase,
    TemporalPhraseTarget,
    TemporalTarget,
)
from award_agent.intent.evidence import assign_stable_anchor_ids, ground_temporal_evidence
from award_agent.intent.model_views import (
    TemporalEvidenceCatalogEntry,
    TemporalInterpretationInput,
    build_temporal_interpretation_input,
)
from award_agent.intent.temporal import sanitize_temporal_extraction


def request(text: str) -> RawRequest:
    return RawRequest(
        text=text,
        context=RequestContext(reference_date=date(2026, 8, 30), timezone="Pacific/Auckland"),
    )


def extraction(anchor_id: str, *, reversed_order: bool = False) -> CoarseIntentExtraction:
    anchors: list[TemporalAnchor] = [
        MonthAnchor(
            kind="month",
            anchor_id=anchor_id,
            applies_to=TemporalTarget.DEPARTURE,
            raw_text="May",
            month=5,
        ),
        MonthAnchor(
            kind="month",
            anchor_id=f"{anchor_id}-return",
            applies_to=TemporalTarget.RETURN,
            raw_text="June",
            month=6,
        ),
    ]
    if reversed_order:
        anchors.reverse()
    return CoarseIntentExtraction(
        date_anchors=anchors,
        temporal_phrases=[
            TemporalPhrase(
                applies_to=TemporalPhraseTarget.DURATION,
                raw_text="about ten days",
                claim_ids=[
                    TemporalEvidenceClaim.DURATION,
                    TemporalEvidenceClaim.APPROXIMATE_DURATION,
                ],
            )
        ],
    )


def test_catalog_ids_offsets_claims_and_order_are_canonical() -> None:
    raw = request("Leave in May for about ten days and return in June.")
    coarse = sanitize_temporal_extraction(raw, extraction("model-a", reversed_order=True))
    evidence = ground_temporal_evidence(raw, coarse)
    stable = assign_stable_anchor_ids(raw, coarse)

    model_input = build_temporal_interpretation_input(raw.text, stable, evidence)

    assert [entry.evidence_id for entry in model_input.evidence_catalog] == [
        "request:9:12",
        "request:17:31",
        "request:46:50",
    ]
    assert [entry.source_order for entry in model_input.evidence_catalog] == [0, 1, 2]
    assert [
        (entry.source_start, entry.source_end, entry.text) for entry in model_input.evidence_catalog
    ] == [(9, 12, "May"), (17, 31, "about ten days"), (46, 50, "June")]
    assert model_input.evidence_catalog[1].claim_labels == [
        TemporalEvidenceClaim.APPROXIMATE_DURATION,
        TemporalEvidenceClaim.DURATION,
    ]
    assert [entry.anchor_id for entry in model_input.explicit_anchor_catalog] == [
        "anchor:month:departure:9:12",
        "anchor:month:return:46:50",
    ]
    assert [entry.key for entry in model_input.allowed_symbolic_references] == [
        "context:request_date",
        "anchor_ref:anchor:month:departure:9:12:start",
        "anchor_ref:anchor:month:departure:9:12:end",
        "anchor_ref:anchor:month:return:46:50:start",
        "anchor_ref:anchor:month:return:46:50:end",
        "request_field:departure:start",
        "request_field:departure:end",
        "request_field:return:start",
        "request_field:return:end",
    ]


def test_stable_anchor_ids_ignore_model_ids_and_model_output_order() -> None:
    raw = request("Leave in May for about ten days and return in June.")
    first = assign_stable_anchor_ids(
        raw,
        sanitize_temporal_extraction(raw, extraction("invented-one")),
    )
    second = assign_stable_anchor_ids(
        raw,
        sanitize_temporal_extraction(raw, extraction("different", reversed_order=True)),
    )

    assert [anchor.anchor_id for anchor in first.date_anchors] == [
        anchor.anchor_id for anchor in second.date_anchors
    ]


def test_catalog_rejects_offsets_that_do_not_match_transcript() -> None:
    with pytest.raises(ValidationError, match="offsets do not match transcript"):
        TemporalInterpretationInput(
            temporal_transcript="May",
            evidence_catalog=[
                TemporalEvidenceCatalogEntry(
                    evidence_id="request:0:3",
                    text="June",
                    claim_labels=[TemporalEvidenceClaim.DEPARTURE_ANCHOR],
                    source_order=0,
                    source_start=0,
                    source_end=3,
                )
            ],
        )
