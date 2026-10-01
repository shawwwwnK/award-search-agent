# Ranking M1 closeout

Date: 2026-09-30. Status: **owner-complete for the declared matching/validation boundary**.

## Owner decision and accepted boundary

The owner explicitly instructed “Close M1” after reviewing the evidence-based closeout
recommendation for the new `sfo_to_bkk_positioning` saved search. Ranking M1 is owner-qualified
and closed for its typed, deterministic, replayable `MatchedJourneySet` boundary.

M1 consumes the frozen request, compiled plan, and provider result. It validates intact award
itineraries and combinations with at most one plan-authorized cash access or egress component,
retains every scoped pairing and distinct observed variant, and records admitted, conditional,
rejected, and research-lead outcomes with provenance and validation reasons. Direct cash remains
a separate benchmark. The accepted boundary uses matching policy m1-v2 and the current
award-only cabin interpretation for separately booked cash positioning; cash cabin evidence
remains visible. A broader cash-cabin requirement would require an explicit policy revision.

## Evidence and verification

The [design record](2026-09-25-ranking-stage-design.md) requires a validated dependency-backed
access **or** egress case, variant accounting, boundary tests, and preserved evidence. The
[implementation log](../build-log/2026-09-25-ranking-m1-matching.md) records independent review
and tests for elapsed-time/local-date boundaries, DST/date-line handling, requirement failures,
unknown prices, provenance, attachment integrity, direct-cash exclusion, and fanout.

The [live evidence run](../build-log/2026-09-27-ranking-m1-live-evidence-run.md) supplies the
previously missing positive case: five admitted award-cash egress journeys joining the aeroplan
SFO→TPE→SIN award to SIN→BKK cash positioning, with resolved permission and 230–535-minute
transfers. Its 123 scoped pairs comprise 5 admitted, 59 conditional, 58 rejected, and 1 research
lead. All compatible variants are retained. The three [saved matching outputs](../../evidence/ranking-stage/m1/README.md)
account for 975 mixed pairs across partial provider executions.

On 2026-09-30, the three current M1 test modules passed **35 tests**. All three saved matching
outputs were independently regenerated through the offline CLI and compared byte-for-byte
with their saved artifacts. These current measurements supersede neither historical test
counts nor the original execution records; they record the closeout verification performed.
See the [closeout build log](../build-log/2026-09-30-ranking-m1-closeout.md).

## Limits and next boundary

Turkish seat/traveler unknowns keep origin-side options conditional. Unreported award-leg
cabins remain visible under the accepted journey-level m1-v2 rule. Prices remain incomplete,
and admission does not establish bookability, current availability, provider reliability,
airline minimum connection times, or broad market coverage. Same-local-date cash acquisition
does not establish next-day search coverage.

M2 has no approved weights or implementation; the model-driven Output Stage remains unopened.
Full-workflow usefulness remains unqualified. D15's wider cash-on-both-ends/general assembly
and D18's expanded acquisition dates remain parked in [DEFERRED.md](../../DEFERRED.md).
