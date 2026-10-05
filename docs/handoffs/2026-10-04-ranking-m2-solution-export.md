# Ranking M2 extension: compact factual solution export

Decision record: [ADR 0027](../adr/0027-ranking-owned-solution-export-and-upstream-trust.md).

Date: 2026-10-04. Status: **owner-closed with Ranking Stage; export implemented, offline verified and independently reviewed**.

The completed export API, CLI and saved evidence are documented in the
[build log](../build-log/2026-10-04-ranking-m2-solution-export.md) and
[evidence index](../../evidence/ranking-stage/m2/solutions/README.md). The final gates passed
28 new tests and 62 existing Ranking tests; all three exports replay exactly on the current
environment. The owner subsequently closed Ranking including this export and opened Results M2;
see the [handoff](2026-10-04-results-m2-opening.md). Results M2 remains unimplemented.

## Owner decision

The owner approved moving the reusable factual preparation from Results M1 into Ranking M2,
then requested documentation updates, implementation with subagents, and reviews. The owner
clarified: “Basically finish the ranking stage with this roped in”; **Results Stage M2 remains
the next step and is not implemented in this task**. Ranking owns
the compact factual export; Results owns authoring-specific preparation and the authored answer.
Earlier Results M1 plans are superseded for this allocation of responsibilities.

The completed M1 matching and M2 solution-style qualification remains evidence for its original
scope. This extension received its own implementation and preservation evidence, followed by the
owner's explicit stage-closeout instruction on 2026-10-04. No broader qualification is implied.

## Contract and dependency boundary

`RankedJourneySet -> project_solutions() -> factored solution view + source receipt -> Results`

Implement a pure projection in `src/award_agent/ranking/project_solutions.py`, with typed export
contracts in `projection_contracts.py`. Consume trusted upstream output and reuse existing
features, assessments, comparison references and policy/FX values. Do not recompute matching,
eligibility, style membership or cost arithmetic. Keep projection separate from `styles.py` and
the ranked artifact's derivation validator. The existing ranked contract and saved inputs remain
unchanged; the compact view is a new export.

The view is the factual portion of the later model input. Results consumes it directly and adds
authoring instructions/slots; it must not construct a second equivalent solution representation.
Ranking never imports Results. No additional workflow stage or generic mapping framework is needed.

## Ranking export responsibilities

- Factor repeated award/cash records and supplied conditions, retaining exact observation identity.
- Retain every distinct complete admitted/conditional alternative with exact component linkage,
  route/schedule, original status, conditions, booking obligations, price scope, cost completeness,
  styles and policy assumptions. Preserve zero versus unknown fees and reported cabin evidence.
- Preserve requested-versus-returned traveler/cabin evidence, observation freshness and reported
  mixed-cabin indicators with their observation scope. Export explicit typed factual fields;
  do not forward provider `raw_fields` wholesale (they can include booking tokens).
- Generate local schedule displays from aware instants and IANA timezone evidence. Raw provider
  local strings remain source-only; missing timezone is explicit. Freeze displays in the export
  without claiming an upstream-pinned timezone database version.
- Preserve request context, separate direct cash, incomplete/summary/unmatched observations,
  rejected conclusions, planning rationale and actual provider coverage.
- Carry existing comparison references and ties with their scope, without inventing cost minima.
- Provide source IDs/version bindings and complete original-record dispositions in the receipt.
- Retain every candidate identity in v1; no candidate aliasing or cross-observation deduplication.
  Factoring supplies compression without introducing a new equivalence policy.
- Keep original condition code/state/detail, including nonblocking obligations; comparison facts
  retain exact units/ratios and scope. Coverage preserves unit kind, stream/pair completeness and
  empty/partial/failed/omitted distinctions; overlapping kinds are not independent search counts.

## Results responsibilities

Presentation grouping and short handles, primary/alternate selection rules, human-readable slot
formatting, activated visible-disclosure obligations, prompt/schema serialization, model authorship,
substitution, visible-content validation and exact answer replay remain in Results. The old Results
M1 is absorbed into this Ranking extension plus the Results authoring milestone; the existing
Results M2/M3 names are retained for continuity. Fallback behavior, models and numerical live-call
budgets are settled during those milestones.

## Implementation and verification

1. Define the view/receipt contracts with explicit source associations and reusable existing types.
2. Implement stable pure projection and a saved-input export interface using immutable outputs.
3. Test projection separately from style arithmetic: expected facts come from trusted inputs,
   not the production projector. Cover exact variant linkage, conditions, quote scopes, missing/zero
   fees, cabin/timing evidence, comparisons, empty/partial/failed coverage and complete accounting.
4. Export all three saved Ranking M2 cases. Expect 257/106/64 eligible alternatives before any
   justified aliases; preserve all 992 original candidate dispositions and source observations.
   Reconstruct Aeroplan USD 196/29h50 and USD 290/27h30, and local/UTC schedules.
5. Measure complete export byte sizes and token counts only where supported; label estimates.
   The later authoring prompt/schema is not implemented or context-qualified by this export.
6. Run independent review, fix material findings, run focused lint/tests and saved replay checks,
   and record objective results in the build log and evidence index.

No model/provider calls are part of this extension. Results runtime remains unimplemented.
The measured compact views are 2,011,912 / 1,302,037 / 654,408 UTF-8 bytes; this does not establish
authoring context fit. Local displays are frozen in the output, but host timezone database release
is not pinned, so cross-host regeneration equality remains unqualified.
