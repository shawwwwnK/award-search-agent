# ADR 0019: LLM-proposed endpoint airports with bounded catalog validation

> Current-status note (2026-09-21): ADR 0023 records the owner's adoption of this selector as the
> official source for exactly resolved geographic endpoints. Explicit and uniquely resolved named
> airports remain direct catalog singletons. Independent semantic qualification remains unclaimed.

## Context

Milestone 1 provides a local, versioned catalog of geographic entities and
accepted airport identities. Its manifest explicitly declares no airport
serving relationships, airport groups, routes, schedules, or provider results.
The existing Milestone 0 JSON fixture remains the deterministic planner test
boundary. A city, country, or region therefore cannot yet be expanded by a
worldwide reviewed airport-serving graph.

The product needs to evaluate whether a model can propose useful exploratory
endpoint airports for an already-resolved location without promoting its
proposal into geographic fact. SQLite can validate only retained identity and
limited metadata, not whether an airport commonly serves a city or whether a
set is optimal.

## Options

1. Build a global curated serving-relationship graph before any selector
   evaluation.
2. Make the model's returned IATA list directly authoritative.
3. Let a model propose a bounded list for an established entity, validate only
   catalog-supported facts deterministically, and record the evidence and
   policy decision.

Choose option 3 for Milestone 2A.

## Decision

The workflow is:

```text
resolved canonical entity
  -> deterministic category and cap policy
  -> structured model proposal
  -> catalog identity / facility / supported-scope validation
  -> immutable model-generated selection record
  -> deterministic planning replay
```

Location category is projected after exact resolution from the canonical
entity and catalog taxonomy. It does not alter `LocationRef`, clarification,
or `EffectiveRequest`, and the selector cannot choose a broader category to
obtain a larger cap. City is capped at 2, country and admin1/admin2 at 4,
continent at 8, and an otherwise unclassified geographic region receives an
explicit broad-cap fallback of 8 rather than an error.

The approved v1 exceptions are the following canonical `(entity_id,
category)` cap records:

| Canonical entity | Display name | Category | Default | Approved cap |
| --- | --- | --- | ---: | ---: |
| `geonames:5391959` | San Francisco | `city_metropolitan` | 2 | 3 |
| `geonames:5128581` | New York City | `city_metropolitan` | 2 | 3 |
| `geonames:2643743` | London | `city_metropolitan` | 2 | 5 |
| `geonames:5368361` | Los Angeles | `city_metropolitan` | 2 | 5 |
| `geonames:6252001` | United States | `country` | 4 | 10 |
| `geonames:1814991` | China | `country` | 4 | 6 |
| `geonames:1269750` | India | `country` | 4 | 6 |

The active policy configuration has SHA-256
`a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256`.

These are empirical product-policy decisions based on pretrained geographic
and aviation knowledge. City/metropolitan exceptions address practical
multi-airport metro markets; country exceptions provide additional useful
international-gateway coverage for large countries. They are not
catalog-verified city-serving geography, a serving-relationship graph, or an
airport-membership list. An override changes only a maximum count: it does
not prescribe membership, create a whitelist, or require the selector to
fill the cap. Country exceptions do not claim that selected airports serve
one city and do not impose one-airport-per-region coverage. No regional
exceptions are approved.

An explicit airport remains itself and does not invoke this selector. Model
output is a strict structured proposal with either individual IATA codes or an
`insufficient_knowledge` outcome. The adapter uses Responses structured
output with `store=False`. It does not retry, replenish rejected candidates,
or write generated relationships into SQLite.

Validation records separate facts and judgments:

- identity is `catalog_verified` only for an accepted record in this snapshot;
- facility acceptance means the record passed this release's retained
  large/medium and scheduled-service input filter, not a current-service
  assertion;
- country membership is verified or contradicted only where the catalog can
  establish it; regional membership is otherwise unavailable;
- city distance is a permissive 200 km consistency policy, not city-serving
  verification; a candidate outside it is rejected by selection policy;
- city-serving remains model-proposed and priority remains model-selected;
- acceptance for exploratory search is an explicit policy decision.

A selection record binds resolved entity/category, cap policy, distance policy,
proposal and candidate outcomes, accepted set, model/adapter/prompt/schema
identities, and catalog receipt. Replay means deterministic planning from the
same immutable records and identities. A new model call may differ; catalog
validation does not restore model determinism. The old legacy `PlanIdentity`
continues to protect the Milestone 0 fixture; selector replay carries its
separate selection-replay receipt.

## Consequences

- This enables a measurable selector experiment without claiming a reviewed
  serving graph or airport whitelist.
- A valid IATA, proximity, or later provider result cannot prove city-serving
  suitability. Semantic errors and omissions remain evaluation concerns.
- Per-location selection caps do not override the planner's request-wide work
  budget. Actual accepted origin and destination endpoint counts multiply
  into endpoint pairs, subject to the planner's maximum of 25 pairs: `5 x 5`
  is exactly 25 and `6 x 4` is 24. The US maximum makes `10 x 4` 40,
  `10 x 5` 50, and `10 x 6` 60, each over budget; a ten-airport maximum is
  therefore not an authorization to schedule every possible endpoint pair.
  Endpoint sets are deduplicated separately; an over-budget request returns
  the visible `endpoint_pair_budget_exceeded` failure rather than silently
  truncating or narrowing the selections. Larger accepted sets also consume
  endpoint-search work items and reduce optional path-exploration headroom.
- No route discovery, repositioning gateway selection, provider execution,
  RAG, or generated-fact persistence is admitted.

## Evaluation

The diagnostic harness in `award_agent.evaluation.airport_selector_live`
compares the original-simple and refined prompt arms on the same model and
structured schema. It runs three bounded trials per disclosed development case
by default, captures opt-in private all-call traces, and emits a redacted
public artifact containing selection/validation outcomes, usage, latency,
trace reconciliation, and configuration identities. It has no price card, so
cost is explicitly `not_estimated_no_versioned_price_card` rather than a
remembered estimate.

Private traces retain raw model-facing input, raw provider response, and
provider-error detail. The public artifact omits those raw values but may
include validated proposed and accepted IATA codes so the human review can
assess the actual endpoint decision.

Human evaluation uses must-consider alternatives, acceptable envelopes, and
unacceptable choices. It separately reviews invalid identities caught,
inappropriate identity-valid survivors, omissions, weak extras, cap behavior,
and useful geographic coverage. It does not use the proposing model as its own
judge and does not treat a public development result as adoption qualification.

The seven overrides above are approved policy, not evidence that larger caps
improve coverage. The v2 active-policy diagnostic predates the US maximum of
10 and is historical US=6 evidence only; it does not validate US=10. The
active v3 diagnostic records model behavior under US=10 but does not qualify
that cap. Future human and holdout evaluation must assess whether the larger
maxima improve useful coverage while remaining within the visible planner
budget; that decision remains pending.

## Revisit trigger

Revisit if live evidence shows systematic semantic errors/omissions, if a
reviewed geographic membership source becomes necessary, if future evidence
supports adding or changing a named cap override, or if production needs
reuse. A future cache must be
explicitly versioned by canonical entity, category, cap policy, prompt/schema,
model configuration, and catalog snapshot; a cached answer remains
model-generated and never becomes a reviewed geographic fact.
