# ADR 0020: Market-aware model-proposed gateway candidates

## Context

Milestone 1 supplies a reviewed, versioned airport-identity catalog but no route,
schedule, airport-serving, or connectivity facts. Milestone 2A supplies a
diagnostic-only endpoint-airport proposal seam whose immutable records may be
provided to later experiments without adopting the selector or promoting its
output into geographic fact.

Milestone 2B needs bounded optional airport candidates after origin and
destination airport sets have already been selected. The candidates are useful
only as hypotheses for additional award-search work. They cannot establish a
scheduled route, feasible or protected connection, award seat, or bookable
itinerary.

The earlier 2B opening required a comparison of route, schedule, reviewed-local,
and curated sources before selecting a mechanism. The owner has instead selected
a grouped model-proposal mechanism for this version. A curated gateway database,
route database, runtime web-research call, or second judging model is not a
prerequisite.

## Options

1. Require reviewed connectivity evidence for every candidate before 2B can
   return it.
2. Let a model return authoritative candidates and market assignments without
   deterministic validation.
3. Use a small deterministic planning-market policy to decide when generation
   can be skipped, make one grouped structured model call otherwise, validate
   catalog facts and relationship integrity deterministically, and retain
   unresolved market disagreements for Milestone 2C.

Choose option 3.

## Decision

### Boundary

The workflow is:

```text
selected origin and destination airport sets
  -> deterministic airport-to-market classification
  -> deterministic skip-or-generate gate
  -> one grouped structured model proposal when required
  -> deterministic identity, bound, reference, and relationship validation
  -> immutable gateway-candidate selection record
```

Milestone 2B does not compile a `SearchPlan`, construct provider payloads, call
award-search providers, assemble itineraries, or verify connectivity,
feasibility, availability, or bookability. Milestone 2C may consume the record,
preserve mandatory endpoint coverage, and compile bounded optional searches.

### Planning-market policy

Planning markets are versioned product policy used only by the generation gate.
They are not an official aviation taxonomy or connectivity evidence. The owner
approved the initial global taxonomy, country/territory mapping, Hawaii and IPC
airport overrides, retention of Alaska in the United States market, the separate
Australia/New Zealand/Pacific Islands markets, and the recorded transcontinental
assignments.

The policy is separate from catalog geography and uses this precedence:

```text
exact airport-ID override
  -> guarded exception-region drift gap
  -> exact physical country/territory-code assignment
  -> explicit unknown mapping gap
```

It never rewrites an airport's physical catalog metadata and has no continent,
coordinate, timezone, sovereign-state, or fuzzy fallback. The guarded-region
step is not a region assignment rule: it ensures that a newly retained airport
in a reviewed exception region such as `US-HI` becomes an explicit gap instead
of silently inheriting the country default before its exact override is
reviewed. Policy serialization, catalog binding, and a canonical digest make
classification replayable.

### Generation gate

Empty or invalid endpoint sets are input errors. A same-market skip is permitted
only when both sides are nonempty, every original endpoint has a known policy
market, and the union of all origin and destination markets contains exactly one
market. Equality of multi-market side sets is not sufficient.

Every other valid input requires one grouped generation call. In particular, an
unknown endpoint market does not withhold generation. It is supplied to the
model as explicit unknown context, remains an inspectable mapping-gap receipt,
and makes a same-market skip impossible. Model reasoning about an unknown market
is a proposal, not a deterministic policy assignment.

Gate status and market-knowledge status remain separate:

- the gate records input error, single-known-market skip, or generation required;
- each airport classification records a known assignment or an unknown mapping
  gap with precedence provenance.

### Grouped proposal and validation

One structured response contains shared origin-access, destination-access, and
intermediate-hub pools with explicit applicability. Product caps, duplicate
handling, correct-side references, support restrictions, nonempty scopes,
self-reference rules, and dependency integrity are enforced in deterministic
code after schema parsing. Valid subsets remain eligible; rejected candidates or
scopes are recorded without refill, substitution, scope broadening, or an
automatic second model call.

The proposal may include the model's market assessment for an endpoint or
candidate. Deterministic code compares it with policy classification when one is
known, but a disagreement is advisory rather than a rejection. The immutable
record preserves both values and records one of `match`, `mismatch_advisory`,
`model_unspecified`, `policy_unknown`, `assessment_unrecognized` (an endpoint
assessment does not name an input), or `not_evaluated` (the candidate was not
eligible for policy comparison, such as invalid, duplicate, over-cap, or
lacking catalog identity or retained-facility metadata). Neither advisory status is a candidate-market mismatch
rejection: a market disagreement cannot by itself remove a candidate that
otherwise passes airport identity, retained-facility, cap, reference,
applicability, and dependency validation.

Milestone 2C owns search-plan consolidation for accepted candidates carrying
market gaps or advisory disagreements. It may use the known policy assignment
for deterministic budgeting while retaining the model claim and issue; it may
not silently rewrite either provenance record.

### Outcomes and replay

Market classification, gate disposition, and generation/validation disposition
are separate axes. Generation may be not attempted, empty, accepted, partially
accepted, rejected-all, failed operationally, or fail system-level validation.
Candidate-level rejections do not become a system-level validation failure.

The immutable record binds endpoint inputs and provenance, catalog receipt,
market-policy version and digest, classifications and gaps, gate decision,
prompt/schema/adapter/model configuration, the complete structured proposal,
candidate and scope decisions, accepted subsets, and explicit coverage
limitations. Replay revalidates the stored proposal against the bound identities
instead of trusting only its accepted subset.

### Relationship to Milestone 2A and existing topology contracts

This decision does not adopt Milestone 2A. Reviewed endpoint sets or supplied
immutable 2A records are both permitted inputs, and model-proposed endpoint
provenance remains visible.

The existing `ExplicitPathHypothesis` contract requires directed route-edge
evidence and exact physical components. A 2B model-originated candidate must not
be converted into that contract or presented as a route-backed path. A later 2C
contract must represent it as an optional supplemental-search hypothesis and
retain mandatory original endpoint probes.

## Consequences

- 2B can test useful global candidate generation without first constructing a
  curated gateway or route database.
- Known same-market requests avoid a model call; mapping gaps conservatively
  invoke the grouped generator rather than suppressing exploration.
- Catalog validation proves only retained identity and supported metadata.
- Market-policy disagreement remains inspectable and actionable downstream
  without unnecessarily discarding a potentially useful candidate.
- Optional-generation failure cannot erase mandatory endpoint coverage in 2C.
- A broader planning market intentionally suppresses more optional generation;
  taxonomy changes therefore require a new policy identity and review.

## Evaluation

Offline tests must cover policy loading and catalog binding, override precedence,
unknown mappings, all-known single-market skips, multi-market generation,
equal-but-multi-market side sets, and preservation of endpoint inputs. Generator
and validator tests must later cover grouped applicability, both hub-cap
branches, invalid identities, duplicates, self-reference, dependency pruning,
partial acceptance, advisory market disagreements, replay, and empty or failed
generation without live model access.

A separate bounded human-reviewed evaluation will judge usefulness, scope,
important omissions, weak extras, and uncertainty. Valid airport codes and
market agreement are not sufficient quality measures.

## Revisit trigger

Revisit the taxonomy when human evaluation shows that a market boundary
systematically suppresses useful exploration or creates unnecessary calls.
Revisit advisory mismatch handling if downstream consolidation cannot safely
resolve the preserved policy/model evidence. Revisit the source mechanism if
model hypotheses are not useful enough, if connectivity evidence becomes
necessary for the intended search contract, or if a maintainable reviewed
gateway or route source becomes available.
