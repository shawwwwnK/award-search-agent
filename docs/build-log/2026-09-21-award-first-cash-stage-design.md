# 2026-09-21: Award-first cash stage design

## Work requested

The owner asked how the newly demonstrated `gfly` cash-search path should change the project and
then selected the next-stage direction:

- retain an award-first default;
- acquire direct origin -> destination cash results as a brief value anchor outside the ranked
  recommendations;
- use cash observations for positioning/access or short self-transfer components around an award
  itinerary; and
- adjust the next provider/result stage accordingly.

## Work completed

- Recorded the accepted architecture boundary in ADR 0022.
- Added the `gfly` and alternative-project feasibility intake, including the single isolated live
  smoke and its evidence limits.
- Added the provider/result/shortlist handoff with provider execution, normalization, bounded
  mixed-candidate assembly, ranking, failure, evaluation, and non-goal boundaries.
- Updated the active milestone roadmap, workboard, project state, deferred-work dispositions, ADR
  index, and repository instructions to point at the newly approved stage goal.
- Preserved the active runtime and completed M2C contract unchanged. No provider adapter, cash
  query, result schema, ranking code, or live workflow behavior was implemented.

## Evidence used

- Current project state, workboard, ADRs 0016 and 0021, the active milestone roadmap, the future
  stage-goal review, the deferred register, and relevant product/ranking sections of the external
  workbook.
- Read-only investigation of `gfly`, `fast-flights`, Webwright, and `google-flights-mcp`.
- One isolated `gfly 0.3.0` live query recorded in the provider-feasibility intake. No additional
  provider or model calls were made during this documentation update.

## Verification

- `git diff --check`: passed.
- Local Markdown-link target check across the changed documentation: 129 links checked, zero
  missing targets.
- Application tests were not required for this documentation-only change.

## Owner conclusions

The owner selected the award-first asymmetric policy described above. Pure-cash observations are a
brief comparison anchor, not ranked recommendations. Cash becomes rankable only as a validated
component of an award-led journey. The stage goal is approved; implementation has not started.

## Next cut

Implement the provider stage only after its capability contracts, budgets, fixtures, and exact provider/result
claims are reviewed. Start offline and replay-first; authorize the bounded live task separately.
