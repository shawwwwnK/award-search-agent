# Search-planning milestone roadmap

- Status: Active planning record
- Date: 2026-09-13
- Scope: The search-planning stage after the completed fixture-qualified boundary

## Purpose and authority

This document gives later agents one current roadmap for the search-planning
stage. It supersedes the earlier *work ordering* in the 2026-09-12 planning
handoff where they differ. It does not change the frozen one-way request
boundary, authorize provider execution, or make an operational coverage claim.

The implemented planner boundary remains:

```text
ClarificationSession(ready).effective_request -> SearchPlan
```

The planner consumes immutable `EffectiveRequest` values and immutable local
knowledge snapshots. It must not reparse conversation text, alter request or
session state, reinterpret temporal contributions, call an award or cash
provider, or claim cash-search coverage.

## Milestone 0 — fixture-qualified planning boundary (complete)

### Achievement

The repository has a deterministic, planning-only `EffectiveRequest ->
SearchPlan` compiler qualified for its declared checked-in seed fixture. The
seed demonstrates Japan and New York City group selection, explicit SFO
preservation, typed grounding failures, synthetic route topology, deterministic
ordering, bounded planning, and stale-plan handoff.

### Existing components

- `search_planning.knowledge`: validated local snapshot and deterministic
  repository retrieval.
- `search_planning.locations`: narrow alias grounding and singleton/group
  airport selection.
- `search_planning.planner`: endpoint probes, bounded optional paths, planning
  receipts, and provider-neutral award search items.
- `search_planning.handoff`: caller-side stale-session/request check.
- `data/search_planning/v1/`: the fixture-only seed and reviewed Cached Search
  capability record.
- `award-search-planning-eval`: ten-case offline fixture gate.

### Boundary

This is not evidence of operational geographic, route, schedule, inventory,
provider, or booking coverage. The default seed has no operational topology;
unit-test route edges are explicitly synthetic.

## Milestone 1 — geographic and airport-data foundation (active next cut)

### Objective

Import GeoNames and OurAirports source data into a deterministic, offline
geographic/airport catalog and serve it through the existing knowledge
repository boundary. Establish enough source-linked metadata and retrieval
behavior for a later reviewed airport-group layer, without attempting provider
execution or route connectivity.

This milestone includes region resolution. A resolved region must identify its
named taxonomy; geographic regions, administrative regions, and future
product-defined travel regions must not share an implicit meaning.

### Required outcomes

1. **GeoNames import.** Import the selected GeoNames geographic inputs into
   canonical geographic entities, narrow aliases, source identifiers, and
   source-supported administrative/geographic relationships. Use the current
   source format and license documentation during implementation; no importer
   may depend on a live GeoNames lookup at runtime.
2. **OurAirports import.** Import the selected OurAirports country, region, and
   airport inputs into canonical airport records and source cross-references.
   Preserve IATA data where present, physical country/administrative metadata,
   and source record identity. Do not treat a municipality or keyword alone as
   proof that an airport serves a city.
3. **Deterministic reconciliation.** Reconcile compatible source facts through
   explicit, versioned matching rules. Missing timezones, duplicate/conflicting
   IATA codes, invalid records, and uncertain cross-source matches are reported
   and withheld from publication rather than guessed or silently repaired.
4. **Offline serving.** Extend the existing `KnowledgeSnapshot` /
   `KnowledgeRepository` interface as needed so location lookup by narrow
   alias, explicit IATA lookup, airport metadata lookup, and region lookup are
   deterministic, stable under record reordering, and network/model-free.
5. **Coverage and evidence.** Publish a coverage manifest and source receipt
   sufficient to say what source inputs and entity kinds are represented. It
   must distinguish catalog recognition from reviewed airport-group coverage
   and later route coverage.
6. **Validation and inspection.** Add publication validation and a small
   library-first inspection surface; a thin CLI may inspect a snapshot, alias,
   entity, region taxonomy, airport, or source lineage. This is inspection only,
   not a search-provider CLI.

### Explicit non-goals

- Directed route evidence, schedule applicability, transfer feasibility, or
  O -> H -> D expansion.
- Award/cash provider requests, payloads, responses, prices, availability,
  ranking, or booking claims.
- A new semantic interpretation pass over the conversation.
- Automatic serving relationships based only on distance, name similarity,
  popularity, municipality, or population.
- Prematurely committing a durable storage/retention policy for large raw
  source artifacts. The owner has put that policy decision on hold until data
  is available for inspection. Imports still require declared, versioned local
  inputs and must record enough receipt data to identify what was used.

### Airport groups

The implementation must preserve the existing fact/policy separation and make
room for review-authored airport groups. The Japan, New York City, and explicit
SFO examples remain valid planner fixtures and product examples. Broader group
curation is intentionally iterative: it is not a prerequisite to importing and
serving the GeoNames/OurAirports catalog.

### Initial acceptance criteria

- GeoNames and OurAirports inputs can be imported and their published records
  retrieved offline through the repository interface.
- Country, city, airport, and region lookup returns one resolved entity, a
  stable ambiguity, a not-found result, a kind/taxonomy mismatch, or explicit
  missing evidence; it never fuzzy-guesses.
- Explicit SFO remains a singleton only when its airport metadata is present.
- A resolved geographic entity without a reviewed group remains explicit; it
  does not invent nearby airports.
- Invalid source records and invalid/dangling relationships cannot be
  published.
- Source record reordering produces equivalent canonical publication and
  lookup results.
- Retrieval neither mutates `EffectiveRequest` nor needs network/model access.

### Milestone 1 decision gate

Proceed to connectivity only after the imported catalog, taxonomy treatment,
provenance model, retrieval behavior, and declared catalog/group coverage are
reviewed. The raw-artifact retention decision remains intentionally open unless
the available source data demonstrates that it must be decided to reproduce or
review the publication.

## Milestone 2 — grounded connectivity and source comparison

### Objective

Add reviewed, directed physical route evidence that lets the existing planner
derive bounded O -> H -> D hypotheses from a published snapshot rather than
synthetic test edges.

### Components

- Compare a narrow set of official airline/airport sources and one accessible
  route or schedule API before selecting an integration.
- Evaluate coverage, update behavior, origin/destination-market versus physical
  nonstop-leg meaning, operating/marketing carrier distinctions, direction,
  seasonal/suspended service, date applicability, schedule horizon, cost,
  access, redistribution rights, and snapshot reproducibility.
- Extend directed-edge evidence only where needed for those source facts;
  preserve raw/source receipts and applicability disclosure.
- Feed reviewed edges into the existing bounded path-discovery seam while
  preserving endpoint-market probes as required coverage.
- Add offline tests proving no reverse-edge inference and no conversion of
  topology evidence into schedule, transfer, availability, or booking claims.

### Decision gate

Advance only if a selected source can provide retainable, reviewable, directed,
date-qualified evidence for explicitly declared markets. Missing evidence means
unsupported by the snapshot, never proof that a flight does not exist.

## Milestone 3 — reviewed strategy documents and RAG-assisted authoring

### Objective

Use a small, permission-aware corpus to assist human authors in proposing and
reviewing strategy claims. RAG remains separate from authoritative geographic
identity, route facts, and deterministic plan compilation.

### Components

- Selected document corpus with retention/permission, version, date, passage,
  attribution, and canonical-entity linkage records.
- Claim/strategy proposals that distinguish factual claims, advice, and
  historical observations, and preserve conditions and citations.
- Human review before publication; retrieval/model output is untrusted and
  cannot publish a route fact or strategy silently.
- Controlled comparison of structured-only, structured-plus-lexical, and
  structured-plus-hybrid retrieval on useful grounded alternatives, conditions,
  citation support, cost, and latency.

### Decision gate

Proceed only if the experiment improves reviewed knowledge authoring or
explanation without weakening provenance or allowing retrieval to invent
physical connectivity.

## Milestone 4 — evidence-driven coverage expansion

### Objective

Expand catalog, group, connectivity, and strategy coverage from documented
unsupported requests and evaluation gaps through explicit snapshot releases.

### Components

- Gap taxonomy: identity, taxonomy, airport metadata, group policy,
  relationship evidence, topology, strategy knowledge, or freshness.
- Controlled lifecycle: identify gap -> acquire/review -> validate -> publish
  new snapshot -> explicitly replan.
- Snapshot diffs, regression cases, review ownership, rollback, and refresh
  monitoring when demonstrated needs justify them.
- Separate provider observations from authoritative catalog/topology knowledge
  and disclose their incomplete or biased coverage.

### Decision gate

Introduce heavier indexing, storage, refresh automation, or review
infrastructure only when measured catalog size, refresh cost, or review volume
shows that structured snapshots and offline validation are no longer adequate.

## Documentation map

- This document is the current milestone order and scope.
- `docs/handoffs/2026-09-12-search-planning-design.md` remains the implemented
  Milestone 0 design and fixture qualification record.
- `docs/project-state.md` and `docs/workboard.md` summarize this active cut.
- Any durable choice of region taxonomy, source reconciliation authority, or
  raw-artifact retention model should receive a focused ADR after owner review.
