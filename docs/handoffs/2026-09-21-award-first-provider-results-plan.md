# Next provider stage: award-first observations and cash positioning

Date: 2026-09-21. Status: **stage goal approved; implementation not started.**

## Objective

Turn a frozen supported one-way award request and its provider-neutral compiled plan into a small,
traceable recommendation output containing:

- normalized award observations;
- a brief direct origin -> destination cash benchmark outside the ranked award list;
- ranked intact award itineraries; and
- when evidence permits, ranked award-led journeys with one validated cash access or egress
  component.

The stage should reduce the owner's manual provider-switching and spreadsheet work. It does not
promise comprehensive inventory, official fare verification, bookability, or a cash-only product.

## Governing decisions

- [ADR 0016](../adr/0016-one-way-award-request-boundary.md) continues to govern active upstream
  behavior until implementation changes are accepted.
- [ADR 0021](../adr/0021-deterministic-search-strategy-compilation.md) keeps M2C provider-neutral.
- [ADR 0022](../adr/0022-award-first-cash-observations.md) governs this stage's award-first cash
  roles, candidate admission, and ranking boundary.
- The [`gfly` intake](../provider-feasibility/2026-09-21-gfly-cash-search-intake.md) is feasibility
  evidence, not provider qualification.

## Stage boundary

```text
frozen EffectiveRequest + current CompiledSearchPlan
    -> capability-bound ProviderExecutionPlan
    -> award and cash ProviderObservations
    -> normalized ObservedItineraries
    -> intact award candidates + bounded mixed candidates
    -> ranked award recommendations + separate cash benchmark summary
```

This provider stage does not mutate request/session state, change M2C identity, reinterpret free-text constraints,
or convert provider observations into catalog or route facts.

M2C already supplies the complete provider-neutral search work; this stage does not add another
strategy compiler or trim that graph. Award execution maps its logical queries to the accepted
award provider. Direct cash benchmarks derive from the mandatory endpoint probes, while cash access
or egress resolves an existing M2C positioning dependency around a returned award itinerary.
These are provider-execution projections and observations, not new gateway proposals or M2C search
options.

## Work packages

### P1 — capability and execution contracts

Accept one reviewed Seats.aero operation for awards and pinned `gfly` behavior for cash. Define
provider-specific request, response, error, freshness, and evidence contracts before application
orchestration.

The execution plan records logical work separately from transport work and owns:

- provider and operation identity;
- scheduled, attempted, completed, empty, partial, failed, and omitted work;
- finite requests, attempts, pages/details, returned rows, bytes, and elapsed time;
- exact source-query attribution; and
- hard stops for stale handoff, cash blocking/rate limit, schema drift, and exhausted budgets.

Seats.aero may use exact rectangle-safe airport-list batching only after fixtures prove result
attribution and no unauthorized cross-product pairs. `gfly` cash queries remain individual airport
pair/date searches in the first slice.

### P2 — deterministic activation policy

Use separate award and cash budgets. The initial order is:

1. execute mandatory award endpoint work;
2. acquire a bounded direct cash benchmark over original selected endpoint pairs;
3. normalize and validate intact results;
4. activate award supplemental work under the accepted award-provider budget;
5. activate cash access or egress only when an observed award itinerary and a compiled access
   relationship make that component relevant; and
6. stop when the next action cannot improve a supported output within the remaining budget.

This is a deterministic controller. No new model call chooses provider work. Direct cash is never
run for hubs or used to create a cash-only alternative network. Cash positioning is limited to
`O -> G + G -> D award` and `O -> A award + A -> D`.

Unknown repositioning permission may authorize bounded read-only research but cannot make a mixed
candidate rankable. `repositioning_allowed=false` excludes dependent cash work. A true value does
not establish separate-ticket tolerance or connection feasibility.

### V — observation normalization and validation

Use a common itinerary core without erasing provider-specific meaning. Required common evidence
includes source, query, airport sequence, local times, timezone-normalized instants, duration,
stops, displayed carriers, traveler count/scope, observation/retrieval time, and raw/sanitized
evidence digest.

Cash observations retain amount, currency, and whether the amount is per traveler, party total, or
unknown. Award observations retain points, taxes/fees, program, cabin and seat evidence where
available. Missing and zero remain distinct.

An intact provider-returned itinerary can become a candidate after its applicable request checks.
A two-component mixed journey additionally requires:

- endpoint continuity and no unsupported airport change;
- timezone-aware chronology and a versioned self-transfer buffer;
- first-departure compliance with the original request;
- traveler and cabin treatment;
- separate-ticket labeling; and
- explicit unresolved baggage, check-in, terminal, visa, and protection obligations.

Failed validation produces a rejected candidate or research lead, never a success-shaped journey.

### U — award-first shortlist and cash anchor

The main ranked list contains intact award candidates and validated award-led mixed candidates. It
does not contain pure-cash itineraries.

The cash benchmark is a brief adjacent summary: representative direct cash observations, their
route/date/cabin/traveler comparison scope, retrieval time, and limitations. It may support a
clearly labeled redemption-value calculation only when the compared evidence is sufficiently
aligned and the valuation policy is explicit.

Ranking applies feasibility and hard requirements before transparent preference features such as
departure fit, cabin, duration, stops, points, award taxes/fees, cash positioning outlay,
self-transfer burden, and unresolved checks. Points are not silently converted to currency.

Explanation may use a model only over validated structured records. Templates are the initial
baseline. Every factual statement must trace to an observation or deterministic derivation.

## Explicit non-goals

- Cash-only request support or ranking pure-cash itineraries with award candidates.
- Round-trip pairing.
- Official fare verification, booking links, booking action, or availability guarantee.
- General award/cash hub substitution or more than two provider-returned components.
- Airport-changing ground transfers.
- Automatic points valuation, personal wallet/profile, transfer execution, RAG, persistence,
  deployment, monitoring, or product multi-agent orchestration.
- Reopening M2A, M2B, or the M2C compiler.

## Completion evidence

The stage is complete only when all of the following are true:

1. Provider capability records and immutable sanitized fixtures cover declared success and failure
   outcomes for both adapters.
2. Offline tests prove request mapping, rectangle safety where batching is used, exact attribution,
   normalization, deduplication, price scope, timezones, traveler/cabin treatment, and finite
   resource accounting.
3. Direct cash observations cannot enter the ranked award list by construction and test.
4. Mixed-candidate tests cover cash-first access, award-first egress, buffer failure, overnight and
   date-line chronology, airport discontinuity, unknown positioning, and unresolved self-transfer
   obligations.
5. Stale request/plan identity prevents execution or result attachment.
6. One bounded live owner-relevant task reaches award observations and a cash benchmark; if the
   evidence contains an eligible positioning case, it also exercises the mixed-candidate path.
7. The final output reports searched, omitted, empty, partial, and failed scope and is compared with
   the owner's current workflow for time, manual checks, and usefulness.
8. At least one supported award or award-led mixed option enables a concrete owner next action with
   less total effort than the current workaround. Honest empty/partial behavior is also required but
   is not a substitute for this positive capability evidence.

One successful live task is development evidence, not broad provider reliability or product
qualification.

## Implementation sequence

1. Freeze capability records, observation contracts, budgets, and replay fixtures.
2. Implement provider adapters and execution accounting behind fake transports.
3. Implement normalization and intact award-candidate validation.
4. Implement direct cash benchmark acquisition and non-ranking output.
5. Implement the bounded cash-access/award and award/cash-egress candidate assembler.
6. Add transparent ranking and explanation from validated records.
7. Run offline gates, a replayable owner preview, then the separately authorized bounded live task.

Do not begin with a broad live run or feed all compiled query-date-days into `gfly`.
