# Results M2 revision code review

Review baseline: `af585b70ad17bb4135ede497c7b6a80935e138f4`, current work in
progress plus relevant new files. Requirements: ADR 0029 and the current plan's
U1–U3 with October 24 implementation details. Frontend U4–U6 and M3 acceptance
remain separate. Reviewers used independent native contexts; no external review
CLI or paid judge ran.

## Standards

No documented-standard violation was found. Two possible duplication smells were
raised as judgment calls:

- Run/replay selection scoring and reason logic: resolved by the small pure
  `choose_recoverable` helper used in generation and structured replay.
- Adapter receipt/error handling: retained as bounded intentional duplication for
  distinct document schemas and historical error messages. Both adapters share
  the one-request transport. The reviewer found no concrete divergence requiring
  a larger abstraction.

The Standards reviewer independently rechecked the selection helper and retained
adapter shape. No outstanding actionable Standards finding remains.

## Spec

Two confirmed findings were fixed before live generation:

- P1: a cabin claim could have an unrelated scope while receiving a supported
  finding; changing only that saved scope could replay unchanged. The structured
  checker now rejects mismatched scopes before proposition evaluation, including
  the exact full-pool requirement for supported comparison claims. Red-green
  controls cover journey, benchmark and lead scope association and replay mutation.
- P2: selecting a benchmark or lead without a corresponding reference block could
  yield clean output. Every selected reference kind now needs its exact block;
  unselected journey discussion remains allowed.

Independent original probes now produce explicit failed findings and scope-only
tampering raises during replay. Reviewer verification passed five selected
regressions (eight deselected) in 35.49 seconds, plus direct selection-outcome
controls. Implementer verification passed 29 structured/adapter/V5 tests in
89.59 seconds and the additional lead-scope control separately. No outstanding
finding remains in the reviewed scope.

## Earlier fact/currency integration review

The independent U1/U2 review and parent integration probes prompted these fixes:
converted benchmark/standalone money; retained mixed-cabin, stops and route detail;
complete summary-lead accounting; optional snapshot-bound FX acquisition receipts;
wrong-kind references carrying no unrelated component facts. The reviewer confirmed
all 378 incomplete-case award summaries occur exactly once, and FX receipt
serialization/replay preserves provenance. Three targeted tests and independent
probes passed after those changes.

Review is code and scoped behavior evidence. It does not establish live model
quality, arbitrary prose truth, traveler benefit, visual acceptance or M3 qualification.

## Versioned-facts follow-up

After live review exposed omitted known lead dates, the Spec reviewer independently
checked the nested v1/v2 fact-shape change. All three original round-one artifacts
retain exact saved JSON/digests, current components preserve source-known dates,
and version/component mismatches are rejected. No compatibility regression or
remaining finding was identified in that delta. Outer authoring schemas are unchanged.
