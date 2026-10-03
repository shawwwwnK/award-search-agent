# Results Stage opening

Date: 2026-10-02. Status: **owner-opened for design; detailed contract unsettled**.

## Owner instruction and terminology

The owner instructed: “Now we're opening the results stage”. This record uses Results Stage
for the downstream user-facing presentation/explanation stage previously called Output Stage.
Opening the stage does not approve a detailed design or establish implementation or qualification.

## Inherited boundary

Start from the frozen `RankedJourneySet` produced by the closed Ranking Stage, including its
attached matching/provider evidence. The existing M2 contract permits model-selected presentation
breadth and explanation while preserving deterministic memberships, actual journey variants,
conditional requirements, and observed versus estimated versus unavailable costs.

Keep direct cash as a separate baseline. Retain source attribution, retrieval times, coverage
limits, and separate-ticket obligations. Rejected records and research leads cannot be promoted
to validated solutions. Presentation choices must not change upstream request state, matching
policy, provider observations, or style assignments.

All three saved requests lack a complete cost reference because price scope is unknown. Do not
present those results as definitively cost-focused or invent complete totals. Personal
redeemability, transfer feasibility, live bookability, and full-workflow usefulness remain
unclaimed. D06, wider D15 topologies, and D18 acquisition expansion retain their parked status.

Sources: [Ranking closeout](2026-10-02-ranking-stage-closeout.md),
[M2 contract](2026-10-01-ranking-m2-styles-contract.md),
[ADR 0022](../adr/0022-award-first-cash-observations.md), and
[deferred register](../../DEFERRED.md).

## Proposed first design cut — not owner-approved policy

Define an evidence-linked output contract before implementing generation. A narrow model interface
could select and explain candidate IDs, with deterministic rendering of dates, cabins, amounts,
status, and source references. Validation should reject unsupported references and claims rather
than return a success-shaped fallback.

Use the three saved M2 requests for initial replay walkthroughs, then test empty, partial,
conditional-only, missing-cost-reference, and model-failure outcomes. Saved evidence is sufficient
for initial design work; no new provider run is required merely to open the stage.

## Decisions still to settle

- Presentation breadth and how styles, highlights, award families, and cash variants appear.
- The model's selection/explanation authority and how claims are checked against source evidence.
- The user-facing artifact and typed contract, including source access and freshness labels.
- Empty/partial/error behavior and treatment of research material.
- Evaluation rubric, bounded live-model diagnostic, and owner acceptance evidence. Engineering
  completion and any claim of full-workflow usefulness need separate evidence.

The next cut is the Results Stage contract and a saved-result walkthrough. No runtime code,
model/provider calls, deployment, or workbook changes were made during this opening session.
