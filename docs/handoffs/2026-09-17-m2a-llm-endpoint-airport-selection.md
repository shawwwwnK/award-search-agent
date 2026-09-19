# Milestone 2A: LLM endpoint-airport selection design

## Scope

M2A adds a narrow selector seam after a location has already been resolved.
It is not a reparse of the request, an alteration of intent/clarification
granularity, or a change to `EffectiveRequest`. It does not add provider
execution, routes, schedules, award availability, a global serving graph, RAG,
repositioning gateways, or persistence of model output into the catalog.

The released M1 catalog is read-only. Its factual limitation is material:
identity and retained admission metadata can be checked, but city-serving,
regional membership (outside country), and search priority cannot be inferred
from it.

## Integration boundary

`context_for_resolved_location` creates a post-resolution
`ResolvedEntityContext` using a canonical entity plus catalog taxonomy. The
selector adapter receives that context, deterministic cap, and no raw request
text. The adapter returns `AirportSelectionProposal`; deterministic validation
creates `AirportSelectionRecord`; `plan_searches_from_airport_selection_records`
replays only supplied immutable records and does not call a model.

The selection record is intentionally a separate receipt from the legacy
Milestone 0 `PlanIdentity`. This preserves M0 golden artifacts while binding
M2A replays to record digests, cap/distance policy identities, catalog snapshot,
model, adapter, prompt version, and Structured Output schema hash.

## Policy v1

| Category | Default maximum | Classification source |
| --- | ---: | --- |
| city / metropolitan | 2 | canonical entity kind |
| sub-country region | 4 | admin1/admin2 catalog taxonomy |
| country | 4 | canonical entity kind |
| international region | 8 | continent catalog taxonomy |
| otherwise unspecified geographic region | 8 | explicit broad fallback |

Caps are maxima, not targets. The active policy digest is
`a3b493cc8c271e78217d99dcc89bcfa7eb8089bb7310a6f2489ae5d9cd915256`.
Seven owner-approved canonical overrides are active: San Francisco and New
York City at 3, London and Los Angeles at 5, United States at 10, and China
and India at 6. City/metro exceptions allow more practical metro-serving endpoint
candidates; country exceptions allow more useful international-gateway
candidates. They do not prescribe airport membership, assert city-serving
facts, or require cap fill. The separate override mechanism continues to avoid
any selector architecture change for future approved policy revisions.

The v2 active-policy casebook/artifact is historical evidence for the former
US cap of 6. It does not validate the current US cap of 10. The active
`development_cases_v3.yaml` diagnostic has completed and remains diagnostic
evidence only; independent human semantic review, holdout evidence, and an
adoption decision are still pending.

## Validation outcomes

| Question | M2A treatment |
| --- | --- |
| Structured response is well formed | strict Pydantic Responses output; invalid adapter result is an explicit error |
| More candidates than cap / duplicate | preserve each proposal outcome; reject excess or duplicate; do not refill |
| IATA in selected catalog snapshot | catalog verified or absent from snapshot; absence is not proof of fabrication |
| Eligible retained facility | accepted under snapshot input filter, otherwise unavailable/rejected; no present-service claim |
| Country scope | verified or contradicted from country codes where supported |
| Admin/international region scope | unavailable until reviewed membership evidence exists |
| City relationship | model-proposed; 200 km coordinate policy only catches gross inconsistency |
| Priority / omissions | model-selected and evaluated by humans |

An insufficient-knowledge response is a successful model contract outcome with
an empty accepted set, not a false claim that no airport exists. A partial
usable result is retained as such. Contradictions, over-cap results, duplicates,
and absent snapshot identity are recorded individually. No unlimited repair
loop is allowed.

## Deferred production cache

No cache is implemented in M2A. If needed in production, its lookup key must
include canonical entity identity, resolved category, cap-policy version and
digest, prompt/version/schema, full model configuration, and catalog snapshot
identity. It must retain proposal/validation provenance and label a hit as a
reused model-generated answer, never as reviewed geographic evidence.
