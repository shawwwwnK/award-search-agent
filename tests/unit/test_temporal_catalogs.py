from datetime import date

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


def test_catalog_uses_short_model_handles_and_keeps_canonical_mappings_private() -> None:
    raw = request("Leave in May for about ten days and return in June.")
    coarse = sanitize_temporal_extraction(raw, extraction("model-a", reversed_order=True))
    evidence = ground_temporal_evidence(raw, coarse)
    stable = assign_stable_anchor_ids(raw, coarse)

    model_input = build_temporal_interpretation_input(raw.text, stable, evidence)

    payload = model_input.model_dump(mode="json")
    assert [entry["handle"] for entry in payload["evidence_catalog"]] == ["e0", "e1", "e2"]
    assert [entry["handle"] for entry in payload["explicit_anchor_catalog"]] == ["a0", "a1"]
    assert payload["allowed_symbolic_references"][0]["handle"] == "r0"
    assert "request:" not in str(payload)
    assert "source_start" not in str(payload)


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


def test_catalog_does_not_expose_offsets() -> None:
    catalog = TemporalInterpretationInput(
        temporal_transcript="June",
        evidence_catalog=[
            TemporalEvidenceCatalogEntry(
                handle="e0",
                text="June",
                allowed_targets=["unspecified"],
                allowed_relation_kinds=["unresolved"],
            )
        ],
    )
    assert "source_start" not in str(catalog.model_dump(mode="json"))
