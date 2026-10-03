# 2026-10-01: Ranking M2 solution-style investigation

## Owner direction

The owner explicitly opened M2 for collaborative design. They clarified that precise ranking
is not the main purpose: deterministic criteria should organize solutions for the later LLM
Output Stage. They preferred solution styles to overall-attractiveness tiers and requested an
orchestrated investigation of the saved searches. Specific style rules, thresholds, score
weights, representative selection, and an output contract remained unapproved at the end of
the initial investigation. The subsequent owner decisions are recorded in the amendment below.

This refines the emphasis of the September 25 Ranking Stage design record; it does not reopen
M1, expand provider acquisition, or open the Output Stage. The workbook is unchanged.

## Investigation and verification

- Two investigator agents independently examined disjoint saved-run scopes: `mixed_access`
  plus `exact_business`, and `sfo_to_bkk_positioning`. An architect independently reviewed
  categorization, comparison, evidence-status, and family-preservation policy without repeating
  the numeric inventory. The parent integrated their reports; all agents were completed and closed.
- Read the project state, deferred register, Ranking Stage design and M1 closeout, relevant
  workbook sections, provider/matching contracts, saved-search index, and saved M1 outputs.
- Agent commands used read-only `jq` joins/grouping/elapsed calculations and `rg` record lookup.
- A parent `PYTHONPATH=src .venv/bin/python -c ...` audit validated all three saved outputs with
  `MatchedJourneySet.model_validate_json`, validated their linked `ProviderResultSet`s, and
  confirmed embedded provider results equal the linked source results.
- The three outputs retain 992 journeys, including 975 mixed pairs: 22 admitted, 405
  conditional, 564 rejected, and one research lead. All provider results have partial coverage.
- `.venv/bin/pytest -q tests/unit/test_ranking_m1_corpus.py`: **4 passed in 1.67 seconds**.
- No live provider/model calls, runtime changes, saved-artifact changes, or new scoring code.

## Observed examples

`mixed_access` has 17 admitted award-only Aeroplan economy journeys, all with one connection,
plus 240 conditional cash-access variants across six Turkish award families. Award-only does
not mean nonstop. Candidate `1b2e10eb` via TPE takes 19h05 and reports 65,000 points and CAD
115.70 fees; candidate `72c36a4e` via KIX takes 38h45 and reports the same points and CAD 91.20
fees. These illustrate time versus reported fee amount, not a supported all-in cost comparison.
Award price scope is unknown. Access variants include economy and business awards, with
unresolved traveler/seat and positioning evidence.

`exact_business` has no admitted journeys and 106 conditional cash-access candidates across
three award families. All use a Turkish business award via IST after SFO-LAX cash access;
requested two-person adequacy remains unconfirmed. Within one family, `c2181073` reports a
USD 487 cash amount with 4h27 at LAX, while `1e2322f9` reports USD 645 with 2h21. Unknown
party scope and award fees prohibit an all-in cheapest label.

`sfo_to_bkk_positioning` has five admitted egress variants in one family, sharing Aeroplan
SFO-TPE-SIN economy observation `2e93cc515d`, reported 65,000 points, and CAD 113.20 fees.
All add a same-local-date, reported-nonstop SIN-BKK cash component:

| Candidate prefix | Observed USD cash quote | SIN transfer | Whole journey |
| --- | ---: | ---: | ---: |
| `89c654f542` | 290 | 3h50 | 27h30 |
| `238e369c9b` | 284 | 5h35 | 29h15 |
| `f7d024bb65` | 196 | 6h20 | 29h50 |
| `82c597b5e7` | 284 | 6h35 | 30h15 |
| `662b5c4c95` | 196 | 8h55 | 32h25 |

All five retain partial prices and unknown price scopes. The same run has 59 conditional
access variants across three Turkish families. Their traveler/seat unknowns must not become
admitted merely because a duration is competitive. Eight direct-cash observations remain
separate benchmarks. A connecting cash observation without timed internal legs remains a
research lead, not a complete solution.

Repeated cash observations across query provenance occur in the September 25 runs. A later
presentation grouping policy may avoid visually repeated choices, but must retain all source
IDs, actual schedule variants, family/support identities, and original matching accounting.
No new deduplication policy was adopted here.

## Recommendations for owner review, not approved policy

- Use factual structural collections: award-only, positioning before the award, and positioning
  after the award. Add overlapping preference styles rather than forcing one exclusive winner.
- Initial useful styles are shorter observed whole journeys, no separate positioning, and
  more separate-ticket transfer time. The latter is a buffer fact, not a safety guarantee.
- Within an award family, expose cash variants with their actual duration, transfer, and quoted
  price tradeoffs. Do not combine different variants' best attributes into a fictional offer.
- Cost-saving styles require supported numeric amounts, currencies, units, and traveler scope;
  raw lower quotes in this corpus can be shown descriptively but do not establish lower total
  outlay. Points comparisons additionally require the same program and compatible scope.
- Keep admitted and conditional views distinct; preserve research/rejected accounting and
  direct cash outside solution collections. Compare only within declared request/date/cabin
  cohorts and evidence status; saved runs are not competing alternatives for one request.
- A deterministic feature/rule view may serve M2 without a weighted score. Avoid "best overall"
  or "balanced" until an explicit tradeoff policy exists. Exact extrema, tolerances, and
  absolute style thresholds remain owner decisions, not inferred from this small corpus.

## Owner interpretation and next cut

Pending owner review of the proposed styles and their membership rules. No implementation or
qualification follows from this investigation. Wider topology (D15), expanded acquisition
dates (D18), and full-workflow usefulness remain outside this cut; no register disposition changed.

## Subsequent owner decisions and contract drafting

The owner adopted integrated complete-journey time/cost/premium styles, removed simplicity,
selected inclusive 120% time and 200% cost thresholds, and approved 100 points = USD 1,
USD 150 per-traveler unknown-tax estimates, versioned currency conversion, and a complete-
cost reference with provisional unknown-cost possibilities. Admitted and conditional journeys
share the comparison pool while retaining their M1 status. Premium economy is an add-on;
two or more full styles earn highlights. Preserve all variants for later LLM presentation,
with pure cash separately presented as a baseline. These decisions supersede the initial
recommendations above, including separate status pools and same-program-only valuation.

At the owner's approval to record the policy and draft the contract, added
`docs/handoffs/2026-10-01-ranking-m2-styles-contract.md` and updated `AGENTS.md`,
`docs/project-state.md`, the original Ranking Stage design, `DEFERRED.md`, and this log.
The draft separates approved product policy from proposed schemas, arithmetic/completeness
mechanics, provisional-highlight treatment, and acceptance tests. No runtime, tests, workbook,
or saved JSON artifacts changed. No exchange-rate values or qualification evidence were invented.

Validation: `git diff --check` passed. A `.venv/bin/python -c ...` documentation check passed
newline/trailing-whitespace checks for all six touched documents and resolved 129 local links.
No runtime tests were rerun for this documentation-only step; the earlier four corpus-test passes
remain the investigation evidence, not tests of an implemented M2. Runtime implementation,
conversion-snapshot selection, and owner review/qualification remain the next required work;
the owner has not requested implementation during this drafting step.

## Subsequent implementation disposition

The owner subsequently requested orchestrated implementation, review, saved-search verification,
and iteration. M2 is now locally implemented with final independent review and saved projections;
see the [implementation evidence](2026-10-01-ranking-m2-implementation.md). This supersedes the
drafting step's no-implementation status, not its historical measurements. Unknown price scope
still prevents a sufficiently complete reference in all three saved requests. Owner qualification
and Output Stage opening remain unclaimed.
