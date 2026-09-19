# Search-planning stage boundary: retrieval-backed plan design

## Status and cut line

The project owner opened this planning-only stage on 2026-09-10, paused it on 2026-09-11 for the
ADR 0016 one-way award-request recut, and explicitly reopened it on 2026-09-12. Its input is a
ready outbound-only `ClarificationSession` projection and its output is a deterministic
`SearchPlan`:

```text
ClarificationSession(ready).effective_request -> SearchPlan
```

The implemented design and fixture-qualification record is
[`2026-09-12-search-planning-design.md`](2026-09-12-search-planning-design.md). It is the durable
design record for the declared local seed boundary. The planner implementation is fixture-qualified;
provider execution remains a later separately scoped stage after the 2B/2C
planning increments.

ADR 0020 narrowly supersedes this brief's connection-candidate source requirement for Milestone
2B. Its grouped model-originated candidates are catalog-validated, unverified supplemental-search
hypotheses and do not satisfy or use the legacy route-backed `ExplicitPathHypothesis` contract.
The requirement that every physical connection/path component bind versioned route evidence remains
in force for that legacy topology contract. Milestone 2C must keep those concepts distinct.

The plan is a collection of expected Seats.aero request items. This stage ends before any
Seats.aero API call. It does **not** add a provider adapter, provider-result contracts,
normalization, ranking, recommendations, booking, persistence, deployment, or production UI.

ADR 0015 remains closed. The ADR 0016/0017 request-understanding and clarification boundaries are
frozen for this stage. The upstream one-way live matrix has remaining behavioral evidence gaps;
the owner's reopening is an authorization to begin this planning-only stage, not a claim that those
gaps are qualified or an authorization to change the upstream boundary. Do not use this stage to
alter clarification semantics, the active one-way request boundary, or the no-raw-text-parsing
continuation boundary.

## Why planning is its own stage

`EffectiveRequest` deliberately retains locations as `LocationRef` candidates. Other than an
explicit model-classified airport code, those values are not stable airport identifiers. Seats.aero
expects airport lists. Planning also needs grounded knowledge to decide whether a trip merits
connection-search legs; for example, a request from SFO to BKK may call for direct and selected
two-leg searches via plausible intermediate airports. Neither transformation may be an untraceable
model guess.

The stage therefore establishes two retrieval-backed planning capabilities:

1. **Location resolution:** city, region, country, and airport candidates become stable geographic
   entities and declared airport sets under a versioned data source and policy.
2. **Connection discovery:** grounded route/network data produces eligible intermediate airports
   and separate search legs under explicit limits and provenance.

The final design has not yet been selected. The owner will obtain and review an external high-level
design before implementation. This brief records the required questions and non-negotiable
boundaries for that review.

## Required input boundary

The planner accepts only a ready `EffectiveRequest`; it must reject incomplete or conflicting
requests rather than reimplementing clarification. Relevant fields are:

- `origins` and `destinations`: one or more `LocationRef` values with `kind`, normalized-candidate
  `value`, and verbatim `raw_text`;
- `departure_window` only; return windows and trip durations are unsupported in the active
  one-way contract and cannot be introduced into planning state;
- `travelers`, `cabins`, `search_modes`, and `repositioning_allowed` when supported by the plan;
- `hard_constraints`, temporal contributions, and field provenance for traceability only unless a
  separately approved planning policy makes a constraint executable.

The owner approved that planning policy on 2026-09-12. Product admission retains origin,
destination, traveler, bounded-window, award, and no-conflict requirements. A separate versioned
Seats.aero Cached-Search capability contract determines resolved airport-list executability and
which future typed hard requirements become provider-filter obligations. Other current free-text
hard constraints remain explicit deferred post-search validation obligations; a typed upstream
constraint contract is a later separate cut.

The planner must not reinterpret raw user text, silently add hard constraints, mutate the
`EffectiveRequest`, or call a provider.

## Required output boundary

The future `SearchPlan` contract must make all search intent inspectable before execution. At a
minimum it should record:

- plan version and deterministic planning-policy version;
- source `EffectiveRequest`/session revision identity and relevant field provenance;
- location-resolution records, including data-source version, selected entities, airport sets, and
  any unresolved or ambiguous candidates;
- connection-discovery records, including source/version, eligibility rationale, and limits used;
- ordered expected search items, each with an item ID, route/leg type, origin airport set,
  destination airport set, date window, cabin/mode constraints that the provider supports, and
  provenance links to the plan decisions;
- explicit plan warnings, exclusions, or a typed `unplannable` outcome when safe planning is not
  possible.

The output is not an API payload and does not assert inventory exists. The next stage will map
these items to Seats.aero request payloads and record execution outcomes.

## Design questions for review

1. What authoritative or sufficiently grounded data sources can resolve locations and route
   connectivity, and what are their freshness, licensing, offline-fixture, and failure policies?
2. Which stable geographic entities and airport-expansion rules should be introduced? In particular,
   how should metro areas, regions, countries, and user-provided airport codes differ?
3. What route/network evidence is sufficient to propose a connection airport? Must each candidate
   support both route legs, and how are seasonality or incomplete schedule data represented?
4. What deterministic limits bound combinatorial growth: maximum airport sets, connection airports,
   legs, date windows, and total expected search items?
5. How should direct options and connection options be represented so later execution can preserve
   provenance and avoid implying that independently searched legs form a bookable itinerary?
6. Which `EffectiveRequest` fields are executable planning inputs now, and which remain explicit
   unsupported constraints rather than silently ignored?
7. What offline corpus and deterministic properties prove that the plan is grounded, bounded,
   reproducible, and non-mutating?

## Acceptance criteria for the eventual implementation

- Identical ready input plus identical versioned retrieval fixtures yields byte-equivalent planning
  decisions and ordered search items.
- Every airport and connection candidate links to a versioned retrieval record and policy decision.
- Ambiguous, unsupported, or unavailable location/route evidence yields an explicit typed outcome;
  it never becomes a guessed airport or route.
- Direct and connection search items are bounded and deduplicated deterministically.
- The planner preserves source request provenance and does not modify the session or effective
  request.
- Tests run solely on local fixtures. No provider or live retrieval call is permitted in the test
  suite.
- The stage has no Seats.aero network client or provider-response parsing code.

## Deferred follow-on stages

1. Translate approved `SearchPlan` items into Seats.aero cached-search API requests and handle
   provider failures.
2. Normalize and validate provider results with freshness and source provenance.
3. Pair or otherwise reason over independent legs, rank candidates, and explain recommendations.
