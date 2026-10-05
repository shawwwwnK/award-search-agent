# ADR 0025: Deterministic overlapping solution styles

- Status: Accepted; Ranking M2 implemented and owner-closed for its declared style boundary
- Decision date: 2026-10-01; stage closeout: 2026-10-02
- Recorded: 2026-10-04 (backfill of existing decisions; no new runtime policy)

## Context

The owner needs understandable tradeoffs among complete award-led journeys. Earlier M2 proposals
used comparable groups with a heuristic order; exact weights, valuation and treatment of conditional
options were unsettled. The [approved style contract](../handoffs/2026-10-01-ranking-m2-styles-contract.md)
replaced that proposal. [Stage closeout](../handoffs/2026-10-02-ranking-stage-closeout.md)
records acceptance and claim limits.

## Options

Recorded alternatives were the earlier group/order proposal and the selected overlapping
solution-style approach. Weighted overall ranking is not required. A simplicity style was removed;
routing and separate-ticket facts remain explanatory inputs. Separate status collections were
superseded by the approved unified admitted/conditional comparison pool.

## Decision

Deterministically style complete admitted and conditional pure-award or one-cash-component journeys
within one request. Preserve their original status and unresolved requirements without a status
penalty. Exclude rejected journeys and research leads from style membership and reference minima;
retain them in the artifact. Direct cash remains a separate baseline.

- Time-focused: whole-journey elapsed time at most 120% of the shortest eligible journey.
- Cost-focused: sufficiently complete per-traveler USD-equivalent heuristic cost at most 200%
  of the lowest sufficiently complete observed/estimated cost.
- Premium-focused: business/first award component under M1 cabin policy. Cash positioning may be
  economy. Premium economy is a labeled add-on, not full premium membership.

Use `award points / 100 + award taxes/fees + cash positioning fare` per traveler. The fixed
100-points-to-USD-1 valuation is a preference heuristic. Unknown award taxes use an explicitly
labeled USD 150 per-traveler estimate; observed zero stays zero. Use an explicit versioned FX
snapshot, preserving original currencies, units, scope and observations. Unknown price scope,
missing points or missing cash prices cannot become invented totals or zero terms.

A reference requires sufficient cost completeness. Retain provisional/undetermined cost
assessments when evidence is incomplete; no complete reference means no reliable threshold or
definitive cost membership. Two or more full styles yield highlights, not a best-overall claim.
Preserve every alternative and exact variant linkage; no shortlist cap is imposed by Ranking.

Deterministic code owns features, exact comparisons and reproducible assessments. Later Results
selection cannot change membership or combine different variants' cheapest/fastest facts.

## Consequences

This supersedes unsettled M2 ordering and valuation proposals in the
[September 25 design](../handoffs/2026-09-25-ranking-stage-design.md), and specifies ADR 0022's
allowance for an accepted valuation policy. M1 eligibility remains unchanged. Style overlap makes
tradeoffs explicit but cannot establish booking confidence or observed monetary value.

## Evaluation

The [implementation log](../build-log/2026-10-01-ranking-m2-implementation.md) and
[saved evidence](../../evidence/ranking-stage/m2/README.md) record offline verification and replay.
Tests exercise exact 120%/200% boundaries, ties, zero/missing distinctions, quote scope, estimates,
FX, premium evidence, highlights and variant preservation. All three saved requests lack a complete
cost reference; synthetic supported-scope fixtures verify mechanics, not live cost coverage.
The October 2 closeout covers the declared style boundary only. Historical evidence is not a new
verification run by this backfill.

## Revisit trigger

Revisit thresholds, valuation or style definitions when owner-reviewed tasks expose misleading
comparisons or important missing tradeoffs. Complete observed cost coverage and recommendation
usefulness require separate evidence; changing weights or estimates requires a versioned decision.
