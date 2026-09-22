# 0018: SQLite published geographic catalog with JSON receipts

> Current-status note (2026-09-21): ADR 0023 supersedes this ADR's requirement to preserve and
> test the Milestone 0 JSON repository as an active compatibility path. The SQLite catalog,
> publication, provenance, and read-only serving decisions remain active.

- Status: Accepted
- Date: 2026-09-15

## Context

Milestone 1 must import and serve GeoNames and OurAirports data through a
deterministic, offline geographic and airport-identity boundary. The prepared
local source bundle contains 279,800 geographic entities, 1,442,567 current
aliases, 23,574 GeoNames airport reconciliation candidates, and 3,244
OurAirports airport endpoints. The compact source bundle itself is 148 MiB on
disk.

The existing Milestone 0 fixture uses a small JSON `KnowledgeSnapshot` parsed
into Pydantic models. That is appropriate for reviewed fixture groups, but a
single Pydantic/JSON operational catalog would require parsing and retaining
the full entity and alias population before an exact lookup can occur. The
owner considers even the compact 148 MiB input size an unacceptable memory
baseline; parsed JSON objects and a Python alias index would materially exceed
it. No measurement of a published JSON artifact is claimed here.

Milestone 1 still needs human-readable source receipts, coverage declarations,
and small reviewed policy records. It must not add a service, runtime network
dependency, fuzzy lookup, provider behavior, route evidence, or airport-group
curation.

## Options

1. Publish the entire operational catalog as canonical JSON and instantiate it
   as a Pydantic `KnowledgeSnapshot`, adding an in-memory alias index.
2. Publish the operational geographic/airport catalog as a local SQLite
   database, with a JSON manifest for snapshot identity, receipts, coverage,
   and database digest. Retain JSON/Pydantic for small fixtures and reviewed
   policy records.
3. Move catalog lookup to an external database service or hosted search index.

Choose option 2.

## Decision

### Published artifact boundary

Each operational knowledge release will be a versioned local snapshot
directory containing:

```text
catalog.sqlite    # immutable geographic/airport catalog and exact indexes
manifest.json     # canonical snapshot receipt, coverage, sources, and digests
```

Small reviewed records, including the existing Milestone 0 seed fixture and
future airport-group policy, may remain JSON where that is clearer. Their
identities and digests must be included in the manifest when they participate
in an operational release.

The catalog is built in a temporary location, validated completely, and then
atomically published. Runtime opens the published database read-only. It does
not read raw source inputs, mutate a snapshot, use an LLM, or contact a
network service.

### SQLite responsibilities

SQLite stores normalized published records and exact lookup indexes for at
least:

- canonical entities and named region taxonomies;
- source records and entity/airport provenance links;
- canonical and accepted current aliases with their normalized key;
- OurAirports airports and retained administrative metadata;
- validated GeoNames IATA/timezone reconciliation evidence; and
- explicit quarantine/coverage publication metadata where it is required for
  inspection.

Every query that can yield multiple records must use an explicit deterministic
ordering. Alias normalization remains the existing narrow NFKC, case-folding,
and whitespace-normalization rule; SQLite full-text search, fuzzy matching,
distance matching, and name-based airport-service inference are out of scope.

### Pydantic and repository compatibility

Pydantic remains responsible for importer input validation, publication
validation, manifest contracts, and typed query results. It must not
materialize the entire operational catalog into a process-wide object graph.

The implementation will adapt the existing read-only
`KnowledgeRepository`/location-resolution boundary rather than introduce a
second planner. The current small JSON `KnowledgeSnapshot` remains the
Milestone 0 fixture contract. A catalog-backed repository must preserve the
same relevant deterministic lookup, ambiguity, evidence, and no-mutation
guarantees before the planner consumes an operational snapshot.

## Consequences

- Exact location and IATA lookup can use persistent local indexes without a
  148+ MiB in-memory catalog baseline.
- The manifest remains inspectable and diffable, while database contents need
  an inspection CLI or library surface rather than direct line-by-line review.
- Publication code must define schemas, migrations or schema-version handling,
  deterministic query ordering, database integrity checks, and database-file
  digest rules.
- Tests must exercise both the existing JSON fixture repository and the SQLite
  catalog repository at the common retrieval boundary.
- SQLite is an embedded file, not a new infrastructure service. There is no
  concurrent write path during planning and no automatic refresh during a
  planning attempt.
- This decision does not authorize a route catalog, provider integration,
  airport-group expansion, semantic parsing change, or a claim of geographic
  completeness.

## Evaluation

Before an operational catalog is accepted, demonstrate that:

- the importer produces a validated SQLite database and manifest from the
  declared compact source bundle without network/model access;
- the manifest binds the database SHA-256, schema version, source receipts,
  coverage statement, and applicable policy identities;
- narrow alias, IATA, entity, taxonomy, and source-lineage queries return
  typed deterministic results, including stable ambiguity and explicit
  not-found/unsupported outcomes;
- reordered source records produce equivalent canonical published content and
  lookup results;
- malformed, conflicting, or dangling records are quarantined or block
  publication rather than being repaired by a query-time guess;
- read-only lookup neither mutates `EffectiveRequest` nor writes to the
  published database; and
- the existing fixture-qualified planner continues to pass against its JSON
  seed while catalog-backed retrieval receives focused offline acceptance
  tests.

## Revisit trigger

Revisit this decision if measured operational use requires concurrent remote
writes, cross-process serving, materially richer retrieval than exact narrow
alias lookup, or if a compact validated JSON artifact demonstrably meets the
memory and startup budget. Any such change must preserve immutable snapshot
selection, receipts, provenance, and deterministic results.
