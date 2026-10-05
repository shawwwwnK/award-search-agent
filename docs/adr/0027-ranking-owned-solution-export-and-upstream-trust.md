# ADR 0027: Ranking-owned factual export and trusted upstream Results input

- Status: Accepted; export implemented and owner-closed with Ranking; Results M2 open
- Decision date: 2026-10-04
- Recorded: 2026-10-04 (backfill of decisions earlier this date)

## Context

Results M1 originally owned reusable factual preparation. Review also proposed an additional
upstream requirement verifier. The owner settled both issues: verified same-project upstream
output is trusted, and reusable factual preparation belongs in Ranking M2. Sources are the
[export contract](../handoffs/2026-10-04-ranking-m2-solution-export.md),
[project state](../project-state.md), and [Results opening](../handoffs/2026-10-04-results-m2-opening.md).

## Options

Recorded alternatives were Results-owned factual projection versus Ranking-owned reusable export,
and duplicate upstream requirement verification versus faithful transformation of trusted upstream
output. The owner chose Ranking ownership and upstream trust. An equivalent second Results brief
transformation is therefore unnecessary.

## Decision

Ranking produces a compact factored `SolutionView` plus internal `ProjectionReceipt` from
`RankedJourneySet`. Keep projection separate from style arithmetic and the ranked derivation
validator. Reuse existing matching conclusions, features, styles, comparisons, policy and FX
values; do not recompute upstream decisions. Ranking never imports Results.

Preserve every distinct complete admitted/conditional alternative and its exact component/source
linkage, status, conditions, costs/scopes, booking obligations, reported evidence and observations.
Factor repeated facts without candidate aliasing or a new equivalence policy. Preserve request
context, separate direct cash, incomplete/rejected/research material, planning rationale and actual
provider coverage, with complete source dispositions in the receipt. Avoid wholesale raw provider
fields that may contain booking tokens.

Results consumes `SolutionView` directly and keeps the receipt internal. It adds presentation
grouping/handles, selections, factual slots, disclosure obligations, prompt/schema preparation,
model authorship and rendering validation. It verifies faithful transformation and visible
presentation of trusted facts, without an additional matching requirement verifier or upstream
policy recomputation. Upstream validation and Results' own transformation checks remain required
at their respective boundaries.

## Consequences

The former Results M1 allocation is superseded: reusable projection is absorbed into Ranking M2,
while authoring preparation stays in Results M2. Existing Results M2/M3 names remain for continuity.
This export extends Ranking's scope with separate evidence; earlier qualification retains its
original boundary. Trust is for verified same-project input, not arbitrary external artifacts.

Complete factual retention can still produce large model inputs. Factoring does not establish
context fit. Local schedule displays are frozen, but the host timezone database release is not
pinned, so cross-host regeneration equality remains unqualified.

## Evaluation

The [export build log](../build-log/2026-10-04-ranking-m2-solution-export.md) records 28 export tests,
62 existing Ranking tests, scoped lint/type checks and three exact saved-export replays.
The [evidence index](../../evidence/ranking-stage/m2/solutions/README.md) records all 992 candidate
and 427 eligible-alternative dispositions. These are recorded earlier-session results, not reruns
by this ADR backfill. Preservation checks derive expected facts independently from trusted inputs,
covering exact variants, conditions, price/cabin/timing evidence, comparisons and coverage.
Results context fit, runtime, live bookability and full traveler-task benefit remain unqualified.

## Revisit trigger

Revisit ownership/trust when an external or unverified input boundary is introduced, export
preservation fails, or a new consumer requires different reusable facts. Resolve authoring context
fit with measurements of complete prompt/schema input without silently dropping alternatives.
