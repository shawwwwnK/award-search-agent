# ADR 0023: Adopt M2A endpoint selection and retire Milestone 0 compatibility

- Status: Accepted
- Date: 2026-09-21

## Context

Milestone 2A implemented a bounded model proposal for endpoint airports after deterministic
resolution of a canonical geographic entity. Deterministic code validates catalog identity,
retained facility eligibility, supported country scope, city-distance consistency, cap policy, and
record integrity before Milestone 2C may replay the immutable selection record. The selector had
remained diagnostic-only pending a separate adoption decision and stronger semantic evidence.

The active system has since completed the Milestone 1 SQLite catalog, Milestone 2B gateway
discovery, and Milestone 2C deterministic strategy compiler. The older Milestone 0 JSON knowledge
snapshot, reviewed group-selection fallback, route/path contracts, and V1 corpus are no longer
active runtime dependencies. Retaining those executable compatibility paths now creates two
competing answers for geographic endpoint selection.

On 2026-09-21, the owner explicitly accepted and qualified the existing M2A policy as the official
endpoint-airport source, qualified the completed M1, M2B, and M2C boundaries after monitoring and
reviewing their builds and results, and authorized retirement of the remaining Milestone 0 implementation.

## Decision

### Official endpoint-source policy

The active endpoint boundary is:

```text
explicit IATA or uniquely resolved named airport
  -> direct catalog singleton

exactly resolved city, country, or region
  -> current M2A structured model proposal
  -> deterministic catalog, cap, distance, and scope validation
  -> immutable selection record
  -> deterministic M2C replay
```

An ambiguous, unresolved, unsupported, or missing geographic entity cannot invoke M2A. An empty or
fully rejected proposal cannot manufacture endpoint coverage. Explicit and uniquely resolved named
airports remain direct because M2A accepts geographic entities, not airport entities.

M2A is the only active source for geographic endpoint sets. The reviewed-mapping alternative and
the Milestone 0 automatic group-selection path are removed. Mixed requests remain supported:
explicit airport endpoints are grounded directly while geographic endpoints require one matching,
validated M2A record.

Adoption does not turn a proposal into catalog fact. Selection provenance remains model-proposed;
the record retains model, prompt, schema, policy, validation, and catalog identities. M2C remains
deterministic and makes no model call: orchestration obtains M2A records before compilation, and the
compiler only validates and replays them.

### Evidence and claim boundary

The owner monitored, reviewed, and qualified the completed M1, M2A, M2B, and M2C boundaries for
their declared local planning scope. M2A is both the official geographic endpoint source and
owner-qualified for that boundary. This does not fabricate or claim independent external human
review, preregistered holdout, or useful-coverage-versus-work corroboration; those may guide future
policy revision but are not prerequisites to the owner's qualification decision.

Selection provenance remains model-proposed rather than catalog fact. Downstream provider results
do not retroactively prove endpoint suitability. City-serving, regional suitability, airport
priority, routes, schedules, availability, bookability, itinerary quality, product behavior, and
recommendation quality remain outside these planning-boundary qualifications.

### Milestone 0 retirement

Remove the executable/test-only Milestone 0 surface:

- the JSON knowledge snapshot and its repository/loaders;
- automatic reviewed group selection and group-cap planning policy;
- legacy route, path, payment, manual-cash, and old search-item contracts with no current caller;
- the old V1 planning corpus and tests whose only purpose was JSON-seed compatibility; and
- current exports or documentation that present the retired path as available.

Historical ADRs, handoffs, build logs, and evaluation artifacts remain immutable evidence. They may
describe Milestone 0 or pre-adoption M2A accurately for their date; current-status documents point
to this ADR instead of rewriting those measurements.

The existing Seats.aero capability research is retained and relocated under provider-capability
ownership. It is provider evidence rather than an endpoint-selection compatibility path. The next
provider stage must explicitly accept or replace capability contracts before use.

## Consequences

- Geographic endpoint selection now has one active policy and one explicit provenance class.
- Explicit airports do not incur an unnecessary model call.
- M2A failure or abstention becomes a visible endpoint-selection failure rather than falling back
  to a reviewed seed group.
- Removing obsolete fields and alternatives changes active policy and plan identities. Current
  offline fixtures are repinned; prior live artifacts remain byte-identical historical evidence.
- The operational catalog remains read-only and does not acquire generated serving relationships.
- Provider execution, result normalization, ranking, and recommendation behavior are unchanged.

## Evaluation

Offline verification must cover:

- explicit IATA and uniquely resolved named-airport direct grounding;
- geographic endpoints requiring exactly one valid M2A record;
- mixed direct/geographic requests;
- missing, extra, stale, tampered, wrong-role, wrong-entity, empty, and rejected records;
- cap, country, distance, catalog, and immutable replay validation;
- complete mandatory coverage, same-record M2C replay, and current handoff; and
- absence of live references to the retired JSON snapshot, group fallback, reviewed mapping, and
  dead route/path contracts.

Tests remain offline and use fake model proposals or supplied immutable records. No live model or
travel-provider run is required to establish this structural adoption change.

## Supersession

This ADR supersedes:

- ADR 0018's requirement to preserve the Milestone 0 JSON repository as an active compatibility
  gate;
- ADR 0019's diagnostic-only and adoption-pending status; and
- ADR 0021's allowance for reviewed endpoint mappings and its statement that M2A is unadopted.

It does not supersede their historical evidence, catalog boundaries, deterministic validation, or
provider-neutral compiler decisions.

## Revisit trigger

Revisit the selector policy or caps when independent review, holdout results, or measured provider
work show systematic inappropriate endpoints, important omissions, excessive search multiplication,
or a better reviewed geographic source. Any replacement must preserve explicit provenance,
deterministic validation, bounded work, immutable replay, and visible failure.
