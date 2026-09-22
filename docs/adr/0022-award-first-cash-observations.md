# ADR 0022: Award-first cash observations and positioning components

Date: 2026-09-21. Status: accepted for the next-stage design; runtime implementation pending.

## Context

The original product goal is an award-search assistant that reduces the work of comparing award
and cash choices. ADR 0016 deliberately made the active request boundary one-way and award-only
because no sufficiently accessible cash source had been demonstrated. Cash-only intent therefore
stops upstream, and mixed award-and-cash intent currently proceeds only for its award portion.

On 2026-09-21, a read-only feasibility investigation identified `gfly` as a lightweight candidate
for indicative Google Flights observations without an API key or subscription. One isolated
credential-free SFO -> LAX query returned structured route, time, airline, stop, price, and currency
data. This proves a narrow live path, not sustained reliability, price completeness, bookability,
or permission for broad automated use. The default backend depends on the reverse-engineered
`fast-flights` interface and can be blocked or broken by upstream changes.

The owner does not require an official booking link or an official verification claim. Route,
time, and displayed price observations are sufficient for value anchoring and recommendation work
when their source, retrieval time, scope, and limitations remain explicit.

## Options

1. Keep all cash work manual and leave D05 parked until after the award-only core is complete.
2. Make cash and award symmetric product modes and rank complete cash itineraries alongside award
   itineraries by default.
3. Keep the product award-first, add a bounded direct cash benchmark outside the ranked award
   shortlist, and allow cash access or egress observations to become ranked only inside a validated
   award-led journey.

Choose option 3.

## Decision

### Product boundary

The default supported workflow remains a one-way award-search workflow. A cash-only user request
remains unsupported in the active product boundary. Return dates and trip durations remain subject
to ADR 0016's separate-one-way guidance.

The next provider/result stage adds two cash roles to every eligible award workflow, subject to its
own execution budget:

1. **Direct cash benchmark.** Search only selected original origin -> destination endpoint pairs.
   Present a small, source-attributed cash summary near the final recommendations to anchor the
   apparent value of award options. Pure-cash itineraries are not members of the ranked award
   shortlist and cannot displace award candidates.
2. **Cash positioning component.** Search an origin -> origin-access-gateway component or a
   destination-access-gateway -> destination component when an observed award itinerary makes that
   research relevant. A cash component may enter the ranked shortlist only as part of a validated
   award-led journey.

This is a product execution policy, not an inference that the user requested a cash-only product.
An explicit award-and-cash request and an ordinary supported award request use the same default
award-first comparison behavior. The existing intent contract need not invent a new hard user
constraint to authorize the bounded benchmark.

### Planning and execution boundary

Milestone 2C remains provider-neutral and unchanged. `LogicalAwardQuery` remains award-only. A new
downstream execution planner owns provider capability, provider-specific requests, activation,
resource budgets, and scheduled-versus-omitted receipts.

The execution planner may derive:

- award-provider requests from compiled logical award queries;
- direct cash benchmark queries from M2C mandatory endpoint probes and requested dates; and
- cash positioning queries only from an explicit M2C positioning dependency plus the relevant
  access strategy and observed award itinerary.

It must not mirror every award query or every supplemental date-day into `gfly`. Cash execution has
an independent finite query, attempt, elapsed-time, and result budget. A provider block, rate limit,
schema drift, or malformed response stops further cash execution rather than triggering evasion,
proxy rotation, CAPTCHA handling, or an unbounded retry loop.

### Observation and candidate boundary

Cash output is an indicative provider observation, not a verified fare or bookable itinerary.
Every normalized observation retains its exact query, provider/backend and version, retrieval time,
currency, traveler-price scope, raw or sanitized evidence digest, and validation results.

The first ranked candidate classes are:

- an intact provider-returned award itinerary; and
- a validated two-component journey containing one primary award itinerary plus at most one cash
  access or egress itinerary.

A direct cash benchmark is displayed separately. An incomplete access result remains a research
lead. Arbitrary award/cash hub substitution, more than two provider-returned components,
airport-changing ground transfers, and automatic general journey assembly remain outside the first
slice.

A mixed candidate requires deterministic validation of airport continuity, timezone-aware
chronology, original departure compliance, a versioned self-transfer buffer, traveler count,
requested cabin treatment, and explicit separate-ticket and unresolved baggage/check-in/terminal
obligations. Component prices are never presented as a protected through-ticket price.

### Ranking and explanation

Ranking remains award-led. Feasibility and hard constraints precede preference scoring. The system
keeps points, award taxes/fees, and cash outlay as separate dimensions unless the user supplies or
accepts a valuation policy. A cash benchmark may support an explicitly labeled redemption-value
calculation only when route, date, cabin, traveler count, and price scope are sufficiently
comparable.

Deterministic code owns normalization, arithmetic, validation, candidate admission, and score
features. A model may explain already checked records but cannot promote a cash benchmark or
incomplete positioning lead into a ranked award recommendation.

## Consequences

- The provider/result/output pilot becomes a two-source award-first slice rather than a single
  award-provider adapter exercise.
- D05 opens only for direct cash benchmarks and award-supporting positioning. General cash search
  and a cash-only product remain parked.
- D15 opens only for the bounded cash-access/award and award/cash-egress topologies above. General
  hub/component assembly remains parked.
- Provider availability does not become catalog or route truth, and successful downstream results
  do not qualify M2A or reopen M2B.
- The active runtime continues to enforce ADR 0016 until this decision is implemented and tested.

## Evaluation

The next stage must include:

- accepted award and cash capability contracts;
- offline fixtures for success, empty, partial, blocked/rate-limited, timeout, malformed, and schema
  drift outcomes where applicable;
- exact scheduled, attempted, completed, failed, and omitted accounting for both providers;
- cash price-scope, currency, traveler, local-time, and cabin tests;
- direct-cash-summary tests proving those results never enter the ranked award list;
- cash-first access and award-first egress chronology, date-line, buffer, discontinuity, and
  separate-ticket cases;
- a bounded live owner-relevant one-way scenario that reaches award observations, a direct cash
  anchor, and—when evidence permits—one mixed positioning candidate; and
- comparison with the owner's current workflow, including remaining manual checks.

The narrow `gfly` smoke is feasibility evidence only and does not satisfy these gates.

## Revisit trigger

Revisit the asymmetric treatment if users need a cash-only product, if direct cash alternatives
prove important enough to enter the main ranking, if observed tasks justify broader mixed-mode hub
assembly, or if `gfly` reliability or use constraints make it unsuitable. Any broader topology or
ranking change requires new evidence and a versioned policy decision.
