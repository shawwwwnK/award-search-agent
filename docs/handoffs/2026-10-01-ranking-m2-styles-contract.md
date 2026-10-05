# Ranking M2: solution styles and draft contract

Decision record: [ADR 0025](../adr/0025-deterministic-overlapping-solution-styles.md).

**Owner closeout, 2026-10-04:** Ranking Stage is closed including the completed factual-export
extension. Results M2 is owner-opened; see the [handoff](2026-10-04-results-m2-opening.md).

**Owner-approved extension, 2026-10-04:** Ranking M2 now also owns the
[compact factual solution export](2026-10-04-ranking-m2-solution-export.md) formerly proposed as
Results M1. This extension is separate from style calculation; it reuses existing assessments
and leaves the original completed boundary and saved ranked contract unchanged. Results retains
answer-specific formatting, selection, slots and disclosure validation.

Date: 2026-10-01. Status: **owner-approved product policy and locally implemented contract; Ranking Stage owner-closed 2026-10-02 for its declared solution-style boundary**.

## Purpose and unchanged boundaries

M2 deterministically organizes complete award-led solutions into overlapping styles for a later
model-driven Output Stage. A precise overall leaderboard is not the product goal. Weighted
multi-feature scoring is not required for this cut.

Consume the frozen [M1 `MatchedJourneySet`](../../src/award_agent/ranking/contracts.py), without
changing its request, plan, provider observations, candidate/family identities, validation, or
coverage. Pure-award journeys and journeys with one cash access or egress component are evaluated
together as complete origin-to-destination solutions. Cash on both ends and expanded acquisition
dates remain parked under [D15 and D18](../../DEFERRED.md). Pure cash remains a separate final-
presentation baseline, never a solution-style member. The Output Stage remains unopened.

This policy supersedes the unsettled M2 heuristic-order proposal in the
[September 25 design record](2026-09-25-ranking-stage-design.md) and the earlier recommendations
in the [style investigation](../build-log/2026-10-01-ranking-m2-style-investigation.md).
It does not reopen the [accepted M1 boundary](2026-09-30-ranking-m1-closeout.md).

## Owner-approved policy

### Eligibility and comparison pool

- Admitted and conditional complete journeys share one pool, with no status penalty or separate
  ranking/style collections. Original status and unresolved requirements remain explicit.
- Compare within one request/result across its allowed departure dates, requested cabins,
  supported endpoint alternatives, and pure-award/mixed topologies. Do not combine saved requests.
- Rejected journeys and research leads are retained but excluded from style assignment and
  reference minima. Untimed award summaries and unmatched observations remain research material.
- All style features describe the complete journey. Award-family grouping organizes alternatives
  but is not a separate leaderboard and does not determine membership.

### Styles

| Style | Membership policy |
| --- | --- |
| Time-focused | Whole-journey elapsed time is at most 120% of the shortest eligible journey in the pool. Include positioning flights and all waits. |
| Cost-focused | USD-equivalent heuristic cost is at most 200% of the lowest sufficiently complete observed/estimated cost in the pool. Preserve provisional treatment for incomplete costs. |
| Premium-cabin-focused | The award component reports business or first under the existing M1 cabin-evidence policy. Cash positioning may be economy. |

For this cut, the intact award component is the major component; do not infer a new longest-
segment requirement or change M1's per-leg cabin validation. Premium economy is retained in
a labeled add-on section of premium-focused output, not full premium membership. Cabin
unknowns cannot establish premium membership. Simplicity-focused is removed; routing,
connection, and separate-ticket facts remain available for explanation.

### Cost valuation and missing evidence

Use per-traveler USD-equivalent amounts:

`heuristic cost = award points / 100 + award taxes/fees + cash positioning fare`

The owner adopted 100 miles/points = USD 1 across programs for this rubric. This is a fixed
preference heuristic, not market value, cash payable, or a redemption-value guarantee. Retain
the original points/program and monetary fields alongside the derived amount.

- Normalize observed monetary currencies with a versioned USD conversion snapshot. Preserve
  original currency, amount, units, scope, conversion identity, and derived amount.
- When award taxes are unknown, use a clearly labeled USD 150 per-traveler estimate. This is
  the approved tax fallback, not an observed fee. Do not replace an observed zero with it.
- Evaluate known parts when other cost evidence is missing. Missing points, cash fare, and
  per-person/party scope must not become fabricated complete prices or silently supplied zeros.
- The reference minimum comes only from sufficiently complete observed/estimated costs.
  Incomplete candidates that may fall within twice that reference are flagged for validation,
  rather than treated as definitively cost-focused.
- If no sufficiently complete reference exists, preserve known-cost comparisons and provisional
  possibilities without claiming a reliable threshold or definitive cost membership.

### Overlap and presentation

Journeys with membership in two or more full styles enter multi-style highlights. This is not
a "best overall" or booking-confidence claim. Premium-economy add-ons do not count as full
premium membership. Preserve every source journey and actual cash variant, including alternatives
with no styles. Do not splice the lowest cost of one variant with another's shortest duration.

M2 imposes no shortlist cap. The later LLM may choose presentation breadth and balance based
on style quality, but cannot change deterministic memberships, hide conditional requirements,
promote research/rejected records, or turn estimated/partial costs into observed totals.
Pure cash is carried separately for a source-attributed baseline comparison.

## Implemented engineering contract

The [implemented schemas](../../src/award_agent/ranking/style_contracts.py) and
[deterministic projection](../../src/award_agent/ranking/styles.py) encode the approved policy.
Engineering mechanics below are implementation decisions, not invented additional owner product
conclusions. `RankedJourneySet` is a styled solution set rather than an overall score table.

| Record | Required content |
| --- | --- |
| Envelope | Contract/policy versions and digests; immutable M1 input or lossless attachment; request/plan/provider identities; conversion snapshot; comparison-pool receipt. |
| Journey features | Candidate/family/component references; unchanged M1 status; whole-journey UTC microseconds and displayed minutes; transfer/ticket facts; award cabin evidence; observed costs and scope. Original reasons/routing remain in the full source attachment. |
| Cost breakdown | Per-component observed, estimated, or unavailable state; raw source values and observation links; original units/currency/scope; exact rational normalized values and displayed per-traveler USD; known subtotal; missing parts; completeness and assumptions. |
| Style assessment | One record per candidate/style, with member, possible, not_member, or undetermined state; feature/reference values; exact threshold receipts and displays; reasons; validation needs. |
| Presentation indexes | Full style members; provisional cost possibilities; premium-economy add-ons; definite and possible multi-style highlights; other alternatives; preserved family/variant references. |
| Passthrough evidence | All rejected/research records, untimed/unmatched observations, direct-cash baseline, provider coverage, and original accounting. |

### Arithmetic, coherence, and completeness mechanics

Use finite, nonnegative numeric values. Exact rational arithmetic determines cost membership;
exact UTC microseconds determine time membership. Decimal displays use an owned precision-50,
half-even context, independent of caller rounding and traps. Normalize documented minor tax
units before conversion; current minor-unit support is explicit for USD/CAD (100 minor units
per major unit), with other minor scales left unsupported rather than guessed. For known per-traveler
scope, use the value directly; for known party
scope, divide by the positive requested traveler count. Unknown scope does not justify either
operation: retain the source quote and its limitation instead of inventing a basis.

A sufficiently complete heuristic cost requires normalized award points, observed or approved-
estimated award fees, and a normalized fare for an actually present cash component, all on the
same per-traveler basis. A pure-award topology has no cash term by construction. A mixed topology
with an unknown cash amount remains incomplete. Missing numeric inputs, unsupported units, or
missing conversion rates prevent completeness; they do not remove the candidate from other styles.
An invalid conversion snapshot should fail explicitly rather than silently refresh or use parity.

A supported nonnegative partial subtotal at or below the cost threshold can indicate possible
membership, but cannot confirm it. A supported subtotal above the threshold rules cost membership
out even before missing nonnegative terms are added. An unknown-scope quote is not a normalized
lower bound; carry it descriptively and explain any undetermined assessment. With no cost reference,
do not manufacture possible membership from an arbitrary number.

Check eligible whole-journey endpoints and transfer timing against attached award/cash component
evidence before deriving styles; reject incoherent M1 artifacts explicitly rather than trusting
a changed candidate timestamp or changing its original status. Bind the complete M1, policy,
FX snapshot, and derived content with digests and recompute assignments/indexes on validation.

Use inclusive threshold comparisons without early rounding. Preserve exact ties. If the supported
cost reference is zero, its doubled threshold is zero; an empty subtotal is unavailable, not a zero
cost. Derive elapsed duration from checked timezone-aware endpoint instants. Use stable IDs for
deterministic ties/serialization, not an undisclosed preference score.

Only definite full memberships count toward definite multi-style highlights. Retain a separate
possible-highlight index when provisional cost membership would raise a candidate to two styles;
the presentation must label that possibility and its missing evidence. No new source deduplication
or variant pruning occurs in this cut.

The selected [USD/CAD snapshot and source receipt](../../data/ranking/m2/README.md) use the dated
Bank of Canada September 29 observation. Snapshots remain explicit inputs, with no runtime refresh.
No source price-scope assumption is introduced. Material policy edge cases return to the owner.

## Implementation and acceptance checklist

1. Add versioned feature, cost, policy, style-assessment, and output contracts with attachment checks.
2. Implement deterministic normalization, reference minima, inclusive memberships, provisional
   assessments, add-on/highlight indexes, and stable serialization behind an explicit offline API/CLI.
3. Preserve all M1 evidence and accounting. The unchanged source status is distinct from style
   eligibility and cost completeness. Add no provider/model calls or Output Stage implementation.
4. Test exact 120%/200% boundaries, ties, zero versus missing, party/per-traveler/unknown scopes,
   tax estimates, currency/unit conversion, incomparable or malformed inputs, no complete cost
   reference, premium evidence/add-ons, two-style highlights, and actual-variant integrity.
5. Replay all three saved M1 outputs; verify source attachments, complete retention, reproducibility,
   and isolated time/cost changes. Use synthetic cost-scope fixtures where the corpus lacks evidence.
6. Review assignments and tradeoffs with the owner before claiming M2 qualification. Passing
   engineering tests alone does not establish full-workflow usefulness or recommendation quality.

Runtime contracts, normalization/assignment, offline CLI, corpus tooling, and tests are locally
implemented. See the [implementation/review log](../build-log/2026-10-01-ranking-m2-implementation.md)
and [saved outputs](../../evidence/ranking-stage/m2/README.md). All three unchanged saved requests
lack a complete cost reference; supported-price synthetic fixtures verify cost mechanics without
claiming live cost coverage. The owner closed Ranking Stage on 2026-10-02 for the declared M1
matching/validation and M2 solution-style boundaries; this does not claim observed-cost coverage,
provider reliability, bookability, or full-workflow usefulness. Later Output Stage work remains
unopened. No live travel-provider/model calls or M1 source changes are part of the implementation.
