# Ranking Stage: design opening

Date: 2026-09-25. Status: **M1 locally implemented and independently reviewed; owner qualification pending; no M2 scoring weights approved**.

## Owner goal and stage boundary

The owner described the workflow they now perform with an award-search tool, Google Flights, and
a spreadsheet. For a requested trip such as SFO to Tokyo, they compare award results across the
selected original and access airports, identify promising award itineraries, search cash flights
that could position them to or from those itineraries, and manually align schedules, prices, and
flight details. Ranking Stage should perform the mechanical matching, time validation, combination,
and first deterministic ordering. A later **Output Stage** will use an LLM to explain and present
the checked results. It must not be responsible for deciding connection feasibility or promoting
an incomplete observation into a validated journey.

The owner opened Ranking Stage with two milestones:

1. **M1 — result matching:** assemble and validate intact award itineraries and supported
   award-led cash-positioning combinations; retain all meaningful alternatives and their evidence.
2. **M2 — ranking:** calculate transparent deterministic features, group comparable alternatives,
   and give them an initial heuristic order with a reproducible score breakdown.

The stage consumes the frozen `EffectiveRequest`, `CompiledSearchPlan`, and `ProviderResultSet`
without changing search planning. It should retain exact input/policy identities and provenance.
The current accepted candidate topology in [ADR 0022](../adr/0022-award-first-cash-observations.md)
is an intact provider-returned award itinerary, cash access plus one award itinerary, or one award
itinerary plus cash egress. Direct cash is a separate benchmark. The owner wants eventual cash
access on both ends, but chose **one cash component now**; the wider topology is parked in
[D15](../../DEFERRED.md).

## Proposed M1 mechanism

- Anchor on the **provider-returned award itinerary**, which may itself contain several flight
  legs. Do not choose an individual long-haul segment and reconstruct the provider itinerary.
- Use the compiled planning dependencies and physical query roles to identify eligible cash
  access/egress observations. Enumerate every compatible award/cash pairing within that scope.
  A cash query's activating award observation remains provenance; a result may be reused for
  another compatible award itinerary under the same dependency after full validation.
- Check exact airport continuity, timezone-aware chronology, the first departure against the
  original outbound window, traveler/cabin and other supported hard requirements, and the
  separate-ticket boundary. At the award/cash boundary, the onward flight must depart at least
  **two elapsed hours** after the arriving flight and, in the transfer airport's local calendar,
  on **the same date or the following date**. This replaces the earlier two-night proposal.
  UTC instants determine elapsed time; local dates determine the calendar-day rule.
- Classify each combination as admitted, rejected with reasons, or conditional/unresolved because
  evidence is missing. Unknown cash price scope or traveler evidence must **not make an otherwise
  useful schedule match disappear**. Nor may an unknown hard requirement be marked satisfied.
  Keep separate route/time, requirement, price-completeness, and booking-obligation assessments.
- Keep each distinct cash flight as a distinct candidate. Merge only affirmative exact duplicates
  and retain all source evidence. Group candidates sharing an award offer as an option family;
  for example, three SFO–LAX cash flights feeding the same LAX–HND award remain three variants.
- Keep award summaries without enough trip detail, incomplete positioning observations, rejected
  combinations, direct-cash benchmarks, and provider coverage/omission receipts visible in the
  result contract, outside the admitted complete-journey list.

Suggested output: `MatchedJourneySet` with input/policy digests, component and candidate IDs,
topology, complete validation receipts, exact planning dependency and positioning reason,
provider evidence, direct-cash observations, research leads, rejected cases, and coverage.

## Proposed M2 mechanism

Feasibility and hard-constraint checks precede preference scoring. Features should include whole-
journey elapsed time, internal connections, the additional separate-ticket connection, layover
time and local-date offset, points/program, award taxes and fees, cash positioning amount, and evidence
completeness. Keep all candidate variants and expose each feature and score contribution.

The owner accepted the recommended direction of **comparable groups with a transparent heuristic
order within each group**. Exact weights, normalizers, tie-breaks, and handling of conditional
options remain to be specified against owner-reviewed examples. Points, award fees, and cash outlay
stay distinct unless a valuation policy is accepted; unknown price or party scope cannot become a
zero or an invented total. The stage may provide a clearly labeled partial cost breakdown when
all-in monetary cost is not supportable. Stable option-family grouping should preserve different
cash times/prices and different award redemption offers.

Suggested output: `RankedJourneySet` that adds versioned features, score components, comparable
groups, deterministic ordering and tie-breaks, option-family/variant references, and all M1
validation, planning rationale, evidence, unknowns, and coverage needed by Output Stage.

## Current provider evidence and limits

`ProviderObservation` has typed endpoint airports, optional timezone-aware instants, itinerary
legs, four-state price/traveler fields, findings, evidence, and query attribution. An
`award_summary` need not have flight times; an `award_itinerary` still needs checked continuous
timed legs for admission. Current `gfly` observations have endpoint times but generally lack
normalized per-leg times, returned traveler/cabin proof, and known price scope. Query-requested
travelers/cabin are not proof of provider-returned adequacy. See
[provider contracts](../../src/award_agent/providers/contracts.py) and
[cash adapter](../../src/award_agent/providers/gfly.py).

The current saved corpus contains two bounded live executions from frozen search-planning inputs.
Both include a timed LAX→BKK award itinerary, SFO→LAX positioning cash observations authorized
by the same plan, and a separate direct-cash benchmark. These are component evidence for M1;
no complete journey has yet passed M1 validation.

### Saved-record M1 case plan

| Saved material | Use in M1 | Limit |
| --- | --- | --- |
| [Mixed access result](../../evidence/provider-stage/saved-searches/runs/mixed_access/result.json) and [bundle](../../evidence/provider-stage/saved-searches/runs/mixed_access/bundle.json) | Positive same-plan access-component case, direct-cash exclusion, variant enumeration, and exact coverage accounting | 23 timed award itineraries, including six LAX→BKK; 76 SFO→LAX cash observations; 212 untimed award summaries and four direct-cash observations. Provider evidence alone does not validate combinations. |
| [Exact business result](../../evidence/provider-stage/saved-searches/runs/exact_business/result.json) and [bundle](../../evidence/provider-stage/saved-searches/runs/exact_business/bundle.json) | Two-traveler business-request case, distinct cash variants, and unresolved requirement treatment | Six timed LAX→BKK awards, 66 SFO→LAX cash observations, six direct cash observations. Returned seat and cash traveler/price scope evidence is incomplete. |
| [Five frozen plans](../../evidence/provider-stage/saved-searches/trace-inputs/) | Verify award-query, endpoint-cash projection, and positioning-dependency rules across actual search-planning outputs | Only the two plans above have current live ProviderResultSets. Plans alone do not imply provider coverage. |
| [Adapter regression fixtures](../../tests/fixtures/providers/README.md) | Exercise specific parsing edge cases independently of M1 journey qualification | Component fixtures are not current saved searches and must not be joined across requests. |

The owner supplied SFO–Tokyo as a description of their manual workflow, not a requested test
fixture. No saved record should be relabeled as a valid mixed journey by combining unrelated
dates, requests, or planning dependencies. After corpus-backed negative and component cases,
record the exact missing positive case and obtain it through a bounded saved search when needed;
until then, M1 mixed-journey qualification is unclaimed.

The [saved-search index](../../evidence/provider-stage/saved-searches/index.json) binds each
result to its frozen plan, request, acquisition tape, and captured bodies. The old standalone
contrast collection was retired on 2026-09-25. The two current runs supply the previously missing
same-plan components. Their partial coverage and unknown fields remain explicit; no M1 matching
or admission claim follows from merely observing both components.

Current positioning acquisition samples cash access on the award departure's local date and cash
egress on the award arrival's local date. The owner chose to **keep same-day acquisition for now**.
M1 may validate an observed next-calendar-day connection, but the stage must not claim comprehensive
next-day positioning-search coverage. Expanding to earlier or later cash search dates is parked in
[D18](../../DEFERRED.md) and requires its own bounded policy and coverage evidence.

## Remaining design decisions and implementation policy

1. M1 validates strictly positive internal layovers for provider-returned legs and keeps the
   separate-ticket two-hour and same/next-local-date rule only at the award/cash boundary. It
   records elapsed transfer minutes and the local-day offset. No airline minimum connection
   time is inferred for internal legs.
2. M1 treats a schedule-complete pairing with unresolved traveler, cabin, positioning permission,
   or retained hard-requirement evidence as **conditional**. Missing route/timing structure is
   a research lead; affirmative hard or schedule failure is rejected. Neither conditional nor
   admitted status claims bookability. Cabin scope for separately booked cash positioning remains
   an explicit owner policy question; the implementation provisionally checks requested cabin
   across the award itinerary and preserves cash cabin evidence.
3. Choose M2 feature scales, weights, comparable-group keys, treatment of incomplete prices,
   and deterministic tie-breaks from reviewed example journeys. Cross-program point valuation
   requires a separate accepted policy.
4. The M1 implementation uses a versioned 100,000-pair structural guard and records all
   in-scope cross-product pairings by support/dependency. It fails explicitly if the guard would
   be exceeded; it does not truncate to a shortlist. Distinct observed cash variants remain
   separate, including source duplicates, pending a future affirmative dedup policy.

## Evidence to close each milestone

M1 should first replay the saved-record cases above. Closing mixed matching also needs a
validated dependency-backed access or egress case plus all compatible variants; exact
119/120/121-minute transfer boundaries; same-day, next-day, and two-days-later departures;
date-line, DST, airport,
original-departure, traveler/cabin, unknown-price, and duplicate cases. It must prove provenance,
complete combination accounting, direct-cash exclusion, and no fabricated cost or booking claim.

M2 should show reproducible ordering and score breakdowns, stable ties, sensitivity to isolated
time/connection/cost changes, unknown-cost handling, no unsupported cross-program arithmetic,
preserved variants, and owner-reviewed tradeoff examples. A later full-workflow usefulness claim
still requires comparison against the owner's manual workflow; stage engineering tests alone do
not establish product value.

This is a design record of the owner's 2026-09-25 direction and the proposed contract shape.
Unsettled choices above are not silently approved policies.
