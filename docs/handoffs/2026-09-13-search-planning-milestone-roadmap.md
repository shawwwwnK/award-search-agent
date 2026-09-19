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

## Milestone 1 — geographic and airport-data foundation (complete)

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
   deterministic, stable under record reordering, and network/model-free. The
   operational catalog artifact is SQLite with a JSON receipt/manifest under
   ADR 0018; the current small JSON seed remains a fixture contract.
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

### Milestone 1A — SQLite catalog publication

#### Objective

Convert the prepared local `m1-current-travel-identity` GeoNames/OurAirports
bundle into a validated, versioned SQLite catalog and JSON manifest, without
changing live planner behavior. This is the publication half of Milestone 1,
as selected by ADR 0018.

#### Dependencies and fixed boundaries

- Consume only the locally prepared source bundle and its receipt manifest;
  acquisition, live source lookup, model use, and provider calls are out of
  scope.
- SQLite is the embedded operational catalog and JSON is the human-readable
  receipt/coverage artifact. Pydantic validates import, publication, manifest,
  and query-boundary contracts; it is not the full-catalog runtime store.
- Preserve the current small JSON `KnowledgeSnapshot` and its reviewed seed
  groups as the Milestone 0 fixture contract.
- Do not author new airport groups, infer airport-city service, add routes, or
  reparse `EffectiveRequest`.

#### Components

- A versioned publication schema for entities, aliases, named taxonomies,
  source records/provenance, airports, retained administrative metadata, IATA
  reconciliation evidence, and necessary quarantine/coverage records.
- A deterministic local importer that constructs a temporary SQLite database,
  validates it, produces a canonical JSON manifest, and atomically publishes a
  complete snapshot only on success.
- Explicit reconciliation and invalid-record rules. In particular, missing or
  conflicting identifiers/timezones must be quarantined or block publication,
  never repaired by name, municipality, coordinate, or distance guessing.
- Publication inspection and validation functions. A CLI is optional at this
  increment; the library-level validator and manifest are required.

#### Decisions still to resolve with the owner before implementation

1. The exact snapshot directory and release-retention policy, including which
   generated manifest/database artifacts are tracked versus locally generated.
2. The final SQLite table/index shape and schema-version/migration policy.
3. The precise one-to-one GeoNames/OurAirports IATA and timezone reconciliation
   rules, including publication treatment for zero, multiple, stale, or
   country-conflicting candidate evidence.
4. Whether quarantine records live inside the catalog, adjacent to it, or only
   in the manifest; their inspection behavior must remain explicit either way.

#### Acceptance criteria

- The same compact input bundle and declared rules produce equivalent canonical
  catalog content and manifest receipts despite source-record reordering.
- The published database has foreign-key/integrity checks, exact alias indexes,
  deterministic query ordering, and a manifest SHA-256 binding.
- Manifest coverage distinguishes recognized catalog entity kinds/taxonomies,
  airport metadata, reviewed airport groups, and route coverage.
- Invalid, dangling, duplicate, or uncertain records are visible as quarantine
  outcomes or reject publication; no partial database replaces a working
  snapshot.
- Publication runs offline and does not modify `EffectiveRequest`, invoke a
  model, call providers, or claim city-airport serving relationships.

#### Decision gate

Proceed to 1B only when the owner has reviewed a successfully validated
catalog/manifest, its reconciliation and quarantine report, and the declared
snapshot/retention treatment.

### Milestone 1B — read-only catalog serving and planner integration

#### Objective

Serve a selected published catalog through the existing deterministic
location/planner boundary, while preserving the Milestone 0 JSON fixture path
and its reviewed airport-group policies.

#### Dependencies and fixed boundaries

- Requires a reviewed Milestone 1A catalog and manifest.
- Runtime opens one selected SQLite catalog read-only and verifies the
  corresponding manifest before retrieval.
- `EffectiveRequest` remains immutable and is not reparsed. Lookup remains
  narrow exact alias/identifier resolution; it has no network, model, route,
  cash-search, or award-provider dependency.
- A resolved entity without a reviewed group remains an explicit outcome. The
  catalog must not create a group, nearby-airport expansion, or positioning
  journey.

#### Components

- A catalog-backed repository implementation or adapter at the existing
  `KnowledgeRepository`/location-resolution seam, with typed query results and
  evidence receipts.
- Read-only lookup for exact aliases, explicit IATA, entities, named region
  taxonomies, airport metadata, and source lineage.
- Stable ambiguity/not-found/kind-mismatch/taxonomy-mismatch/missing-metadata
  outcomes, with deterministic ordering and evidence rather than a bare code.
- A small inspection surface for catalog, manifest, entity, alias, airport,
  taxonomy, and provenance checks. It must inspect only; it cannot run search
  providers.
- Compatibility tests proving the existing JSON seed and its Japan, New York
  City, and explicit SFO fixture behavior remain available.

#### Acceptance criteria

- Read-only lookup returns the same canonical result after source-record
  reordering and never writes the SQLite catalog.
- Country, city, airport, and named-region lookup preserves ambiguity and
  reports no-group/missing-metadata cases explicitly.
- Explicit SFO remains a singleton only when its selected catalog metadata is
  available; no fallback airport is invented.
- Retrieved evidence identifies the published snapshot, manifest/policy, and
  supporting source records.
- Existing planning tests continue to pass, and catalog lookup tests require no
  network or model access.

#### Decision gate

Milestone 1 is ready for its owner review only after the catalog artifact,
retrieval behavior, declared catalog/group coverage, and inspection/evaluation
results are reviewed. Milestone 2 connectivity remains a separate decision.

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

## Milestone 2 — endpoint and gateway strategy planning

### Objective

Build the operational planning coverage that maps a supported requested
geography to bounded airport sets, identifies useful candidate gateway
airports, and compiles direct plus supplemental award-search strategies. The
objective is to avoid limiting award search to the original O -> D market when
a separate award search from a reachable gateway could be useful.

This milestone does not assume that a directed-route catalog is the mechanism
for gateway discovery. Reviewed connectivity facts, curated gateway policies,
and other permitted local evidence are candidates to evaluate. The award-search
and result stage remains responsible for returned itinerary topology, award
availability, and itinerary validation.

### Milestone 2A — endpoint airport grounding (implemented; adoption gate open)


#### Objective

For an explicit airport, city, area, country, named region, or other supported
location kind, resolve the requested endpoint to a bounded, reviewed airport
set or an explicit coverage outcome. The existing Milestone 1 catalog provides
airport identity and geographic facts; this increment adds neither guessed
airport service nor an implicit claim that every airport in a geography is a
suitable search endpoint.

#### Components

- Declare a narrow initial geography/airport coverage set and the supported
  location kinds within it.
- Define location-kind-specific retrieval and airport-selection strategies.
  Explicit airports remain singleton lookups; city, area, country, and named
  region handling may each use distinct reviewed relationships and policies.
- Keep factual geographic-to-airport relationships separate from the ordered,
  capped policy that selects airports for search.
- Return stable resolved, ambiguous, unsupported, and missing-evidence
  outcomes with inspectable snapshot provenance. Do not substitute nearby,
  similarly named, or popular airports.
- Qualify ordering, caps, provenance, and no-guess behavior offline while
  preserving the Milestone 0 JSON fixture path.

#### Decision gate

Advance when the declared initial locations can each produce their reviewed
airport set or a truthful typed coverage outcome, with no fuzzy expansion or
silent airport-service inference.

### Milestone 2B — gateway-airport discovery (implemented; semantic review open)

#### Objective

Given selected departure and destination airport sets, provide a bounded,
deterministic, explainable set of candidate connection/gateway airports that
could make a supplemental award-search strategy useful.

The owner approved ADR 0020 on 2026-09-18. This version uses a reviewed global
planning-market policy, one grouped structured model proposal when generation
is required, deterministic catalog/reference/relationship validation, and an
immutable result. Opening and implementing it do not satisfy the still-open M2A
adoption gate; reviewed fixtures or supplied selection records may support the
interface without promoting model output into fact.

#### Components

- Apply the versioned planning-market policy with explicit airport-override,
  country-assignment, and mapping-gap provenance. Skip only when every original
  endpoint is known and the combined market union contains exactly one market.
- Make exactly one grouped structured model call for every other valid input,
  including inputs with an unknown endpoint market. Supply the mapping gap as
  explicit context rather than treating it as shared or cross-market evidence.
- Validate catalog identity and retained-facility eligibility, pool bounds,
  references, applicability, duplicates, self-reference, and dependency
  integrity without claiming connectivity.
- Preserve a model/policy candidate-market disagreement as a nonfatal advisory
  observation for 2C. It does not reject an otherwise valid candidate or scope.
- Return explicit policy-skip, successful-empty, successful-nonempty, partial,
  rejected-all, generation-failure, and system-validation-failure dispositions,
  with market-coverage status recorded independently.

#### Implementation and review status

The approved policy, one-call grouped generator, relationship-aware validator,
immutable replay record, and disclosed casebook-v3 development casebook are
implemented. Casebook v3 preserves the eight v2 scenarios and adds 15
catalog-pinned scenarios, for 23 cases: two policy skips and 21 generation
cases. The prompt-v5/casebook-v2 and first prompt-v5/casebook-v3 diagnostics
are historical evidence. The final prompt-v6/casebook-v3 two-trial live
evaluation completed its bounded 42 calls and remains open only for
owner/human semantic review. Access gateways may be
materially complementary for already-strong endpoints only when they provide
specific incremental value; size, proximity, shared market, or diversity alone
is insufficient. The independent 2 origin-access, 2 destination-access, and 5
hub maxima do not impose an intermediate-market diversity quota. Offline checks
and trace reconciliation are complete. The v6 artifact records 46 case-trials,
42/42 calls, 82 candidates, 43 scopes, and 400 accepted relationships; one PNH
catalog-absence rejection and three market-mismatch advisories were retained.
The artifact/privacy audit and independent AI semantic review passed for owner
human review, not human qualification. No prompt-v7 or deterministic
semantic-rejection change is currently recommended; 2C relationship/search-work
budgeting remains mandatory. 2B is not automatically qualified or adopted as a
2C input source.

#### Decision gate

Advance when the approved mechanism yields useful, bounded, reviewable gateway
candidates beyond endpoint-only searching and its relationship scopes and
coverage limitations pass offline and human semantic review.

### Milestone 2C — search-strategy compilation

#### Objective

Compile selected endpoint airport sets and optional gateway candidates into a
provider-neutral `SearchPlan` that retains direct endpoint-market award searches
and adds bounded supplemental award-search strategies.

#### Components

- Preserve an O -> D endpoint-market probe as required coverage for every
  selected endpoint combination.
- Define which supplemental award-search items each gateway candidate enables.
  Where a strategy needs positioning from O to a gateway, represent it
  explicitly rather than silently treating it as an award result.
- Apply deterministic planning budgets, canonical ordering, and semantic
  deduplication across direct and supplemental strategies.
- Budget compiled relationships/search items rather than raw candidate count;
  record any budget omission without relabeling an accepted 2B candidate
  invalid.
- Carry candidate/selection provenance and coverage disclosures into plan
  receipts without changing request understanding or calling a provider.
- Add offline tests proving direct coverage remains present, strategy output is
  bounded and stable, and supplemental strategies never become claims of a
  scheduled, feasible, protected, available, or bookable itinerary.

#### Decision gate

Milestone 2 is ready for owner review when the declared coverage can progress
end-to-end from supported geography through selected endpoint airports to
mandatory direct and optional supplemental award-search strategies, with
bounded work, provenance, and truthful coverage outcomes. It must not call a
provider or claim a returned itinerary, award seat, or bookable journey.

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
