# 2026-09-15: Milestone 1A catalog publication implementation

## Work recorded

Implemented the offline Milestone 1A publication library in
`award_agent.catalog`. It consumes the prepared local compact bundle only and
publishes an immutable SQLite release plus canonical JSON manifest through a
staging directory and atomic rename. It does not alter the Milestone 0 JSON
knowledge snapshot, planner, airport groups, route evidence, providers, or
request state.

## Implemented boundary

- Pydantic contracts validate a typed owner-supplied source date, actual local
  timezone-validator identity, bundle/output receipts, release manifest, and
  every supported compact-bundle row type; compact-file headers and manifest
  output receipts are validated before creating a staging directory.
- The SQLite schema stores source artifacts and records, taxonomies, GeoNames
  entities and alias evidence, administrative corroboration, OurAirports
  country/region metadata, GeoNames airport candidates/IATA evidence, accepted
  airports and official-name aliases, reconciliation outcomes, and compact
  quarantine receipts.
- Operational IDs are source-native: `geonames:<geoname_id>` and
  `ourairports:<ourairports_id>`. IATA is unique airport metadata, not airport
  identity.
- IATA reconciliation accepts exactly one non-historic, non-expired candidate
  with matching country and valid IANA timezone, and verifies the reverse
  candidate-to-current-IATA cardinality across retained endpoints. Missing,
  ambiguous, country-conflicting, reverse-cardinality-conflicting, blank or
  invalid-timezone evidence is quarantined; candidate/cross-reference,
  duplicate IATA, invalid administrative corroboration, dangling country/region,
  and other structural corruption rejects publication.
- Source records retain the verbatim compact-source `source_record_id` and a
  separate compact-row identity. The manifest binds catalog schema/logical
  digest, SQLite byte digest, compact input bundle and source-file receipts,
  fixed code-derived rule receipts, explicit source-date/actual timezone
  validator context, entity/taxonomy and endpoint coverage denominators, and a
  comprehensive quarantine digest.
- Validation opens only SQLite read-only and checks the manifest database
  digest, foreign keys, integrity, and logical content digest. No active
  snapshot pointer is created.

## Verification recorded

Synthetic offline tests cover successful immutable publication, exact official
airport-name evidence, strict country conflict and ambiguity quarantine,
same-candidate duplicate evidence, historic/expired evidence, blank and invalid
timezones, candidate-to-multiple-IATA quarantine, candidate/cross-reference
structural rejection, duplicate endpoint IATA and false administrative
corroboration rejection, manifest/database tampering, immutable no-overwrite,
receipt failure before release creation, verbatim source identity, and
reorder-invariant logical catalog digest.

Commands run:

```text
.venv/bin/pytest -q tests/unit/test_catalog_publication.py
.venv/bin/ruff check src/award_agent/catalog tests/unit/test_catalog_publication.py
.venv/bin/ruff format --check src/award_agent/catalog tests/unit/test_catalog_publication.py
```

At the recorded remediation point, the focused publication plus Milestone 0
planning/source-preparation suite passed with 104 tests. The complete offline
suite passed with 390 tests and 99 explicitly historical skips; Ruff, mypy, and
the whitespace diff check passed.

## Follow-up real-bundle compatibility check

Final review found two pre-publication compatibility issues before a full
release was attempted. The publication bundle contract now preserves and
validates the prepared bundle's `filters`, `purpose`, `record_counts`, and
`limitations` alongside the output/source-file receipts. Base-alias source
lineage now requires exact agreement with the referenced entity's verbatim
source record rather than assuming `allCountries`; this supports the prepared
bundle's `countryInfo`, `admin1CodesASCII`, and `admin2Codes` entity records.

The ignored real bundle completed receipt and header preflight successfully:
`m1-current-travel-identity`, 279,800 entities, four filter sections, and four
declared limitations. This check did not ingest or publish the full catalog and
needed no `PublicationContext`. The follow-up focused publication plus Milestone
0 suite passed with 106 tests.

## Final structural hardening

The publication gate now also rejects an endpoint whose declared region does
not use or resolve to its declared country; validates current-alias language
tags (including the bundle's explicit `abbr` convention); enforces IATA
cross-reference identifier/country/flag formats and exact administrative
corroboration; and rejects a manifest whose database filename differs from the
fixed catalog filename. The timezone-validator receipt now hashes the actual
local zoneinfo tree contents (with package version where available), rather
than only the names of timezone search paths.

Adversarial tests cover each of those failures and a zoneinfo-content digest
change. A no-publication real-bundle structural pass checked all 279,800
entities, base-alias source lineage, 1,442,567 current-alias language/filter
records, 3,987 regions, 3,244 endpoint region-country relationships, and
51,458 administrative corroboration records. No real catalog release was
created.

## Final preparation-contract parity

Current-alias language admission now exactly mirrors the source-preparation
predicate: `abbr`, or a two/three-letter ISO-like base with zero or more
two-to-eight-character subtags. Regression cases reject `en-x` and an
overlong subtag while accepting uppercase base tags and `abbr`. The importer
also now verifies a one-to-one administrative corroboration record for every
and only retained GeoNames admin1/admin2 entity. Missing, unexpected,
mismatched, duplicate, or false corroboration evidence rejects publication.

The no-publication real-bundle parity pass confirmed all 51,458 retained
admin1/admin2 entities have exactly one corroboration record. Focused catalog
tests passed 24 cases; the full offline suite passed with 400 tests and 99
historical skips.

## Published full-release candidate (2026-09-15)

The owner declared `2026-09-14` as the source/as-of date for the prepared
`m1-current-travel-identity` bundle. The full ignored local bundle was then
published without network or model access to:

```text
data/search_planning/catalogs/m1a-06b28b323dc70ef5/
```

The release is intentionally ignored rather than checked into Git. It contains
`catalog.sqlite` (1,360,375,808 bytes; SHA-256
`c56908c36cf518cf6ef9caa33648f773190ca4c283721f4e834fe2b2654264f2`) and
`manifest.json`. The validated logical content SHA-256 is
`24224f2904bcc72c3cfb0d4f7cfacb595b30bb130fb02f1e0ccb2dc1178b1c64`; the
prepared-bundle manifest SHA-256 is
`66d14b23f296543449ad0e46a3343047623c746e34869b28044830a0088f281e`.

The publication captured the actual local timezone validator as
`system-zoneinfo;zoneinfo_tree_sha256=caa07a4c343fe762bf9d02feee5a50cfafdf7fa443a00154ecef564b0257abba`.
This is an observed runtime receipt, not a claim that the owner selected a
separate validator implementation.

Validated catalog counts:

- 279,800 entities: 252 countries, 224,462 cities, and 55,086 regions across
  six explicit GeoNames taxonomies.
- 1,782,867 entity-alias evidence records.
- 3,244 retained OurAirports endpoint inputs; 3,209 accepted reconciled
  airports and airport aliases.
- 23,574 GeoNames airport candidates, 3,230 IATA evidence records, 51,458
  administrative corroboration records, and 249 country/3,987 region metadata
  records.

The reconciliation quarantine has 35 explicit outcomes: 30
`iata_no_eligible_geonames_candidate` and five `iata_country_conflict`.
Coverage remains exactly geographic and airport-identity facts only: no
airport-serving relationships, reviewed airport groups, routes, schedules,
providers, or booking claims. The manifest records the source bundle's four
stated limitations, including that a municipality, keyword, coordinate, or
distance never creates a serving relationship.

The release was validated read-only with manifest/database receipt binding,
foreign-key/integrity checks, and full canonical logical-content recomputation.

Commands run:

```text
PYTHONPATH=src .venv/bin/python -c '<publish_catalog(... source_date=2026-09-14)>'
PYTHONPATH=src .venv/bin/python -c '<validate_release(...) and inspect_release(...)>'
.venv/bin/pytest -q tests/unit/test_catalog_publication.py  # 24 passed
.venv/bin/pytest -q                                  # 400 passed, 99 skipped
```

## Owner review and gate decision (2026-09-15)

The owner approved the release source date, manifest/receipt evidence, declared
coverage, and catalog counts. The owner reviewed the 35 reconciliation
quarantines and accepted them as non-important places that may remain
quarantined. The owner chose local-only retention for now and deferred any
deployment-time hosting discussion.

This completes Milestone 1A and admits Milestone 1B: read-only catalog serving
and planner-boundary compatibility. It does not admit directed connectivity,
provider execution, airport-group expansion beyond the existing fixtures, or
deployment work.

## Owner conclusions / next cut

Owner-approved next cut: Milestone 1B read-only catalog serving and
planner-boundary compatibility.

## Milestone 1B implementation evidence (2026-09-15)

Implemented the selected-release, read-only catalog-serving boundary without
altering the Milestone 0 JSON fixture path. `CatalogKnowledgeRepository`
first runs the existing complete release validator, then opens only
`catalog.sqlite` with SQLite `mode=ro` and `PRAGMA query_only=ON`. It has no
release discovery, raw-bundle input, write method, network/model behavior,
airport-group policy, or route data.

The shared structural repository seam now permits the existing JSON
`KnowledgeRepository` and the catalog repository to feed one planner. The
planner requires exactly one of `snapshot=` or `repository=`. Catalog-backed
plans carry a distinct `CatalogKnowledgeReceipt` with the release/schema/source
date, logical catalog hash, manifest/database/source-bundle hashes, and source
artifact receipts. Catalog query evidence remains source-record IDs; unknown
evidence is rejected and freshness is pinned to the accepted release source
date rather than the wall clock.

Catalog entity, exact alias, explicit IATA, airport metadata, taxonomy, and
source-lineage queries have deterministic ordering. The inspection surface also
has a typed exact lookup result that distinguishes `resolved`, `not_found`,
`kind_mismatch`, `taxonomy_mismatch`, `ambiguous`, and `missing_metadata`.
`--taxonomy` on `award-catalog-inspect` is a named-region taxonomy-scoped alias
query, rather than a bare taxonomy-existence check. Catalog geographic facts
have no selection policies, relations, or routes, so a resolved city/country/
region reaches the existing explicit `MISSING_SELECTION_POLICY` result rather
than inventing airport service. The new `award-catalog-inspect` CLI only opens
the same validated read-only repository for manifest/receipt, alias, entity,
airport, taxonomy, and source-record inspection.

Focused tests use a tiny generated publication fixture, not the ignored 1.36
GB owner-reviewed artifact. They cover exact country/city/region/airport
retrieval, provenance, pinned-current/unknown evidence handling, database
write rejection, catalog receipt binding, explicit-airport planning, no-group
planning failure, snapshot/repository exclusivity, inspector behavior, and
tampered-manifest rejection. Follow-up adversarial coverage also confirms that
catalog serving never preloads all source-record keys and that an airport whose
published country has zero or multiple catalog country entities becomes an
explicit missing-airport-evidence result rather than a fabricated or arbitrary
country identifier. A valid projected airport includes its uniquely selected
country entity's source-record evidence.

Commands run during implementation:

```text
.venv/bin/python -m pytest tests/unit/test_catalog_serving.py \
  tests/unit/test_search_planning_grounding.py \
  tests/unit/test_search_planning_endpoint.py \
  tests/unit/test_catalog_publication.py -q  # 90 passed
.venv/bin/python -m mypy src/award_agent/search_planning \
  src/award_agent/cli/catalog_inspect.py tests/unit/test_catalog_serving.py
.venv/bin/python -m ruff check src/award_agent/search_planning \
  src/award_agent/cli/catalog_inspect.py tests/unit/test_catalog_serving.py
PYTHONPATH=src .venv/bin/python -m award_agent.cli.catalog_inspect \
  data/search_planning/catalogs/m1a-06b28b323dc70ef5 --airport SFO
.venv/bin/python -m pytest -q  # 406 passed, 99 skipped
.venv/bin/python -m ruff format --check \
  src/award_agent/search_planning/knowledge.py \
  src/award_agent/search_planning/contracts.py \
  src/award_agent/search_planning/locations.py \
  src/award_agent/search_planning/planner.py \
  src/award_agent/search_planning/__init__.py \
  src/award_agent/cli/catalog_inspect.py \
  tests/unit/test_catalog_serving.py
git diff --check
```

The final inspection command validated and queried the owner-reviewed full
local release: `SFO` resolved to `ourairports:3878`, with its accepted
OurAirports endpoint, GeoNames airport-candidate, and GeoNames IATA-evidence
source-record receipts. It reported the release/manifest/database/logical and
source-bundle digests recorded above. The installed entry point is named
`award-catalog-inspect`; this development checkout invoked the module directly
because its existing virtual environment pre-dates the new package script.

Owner interpretation and the Milestone 1 review/next-cut decision remain
pending. This implementation does not claim route, schedule, provider, or
airport-group coverage.

## Retention correction and Milestone 1B closeout (2026-09-16)

The owner corrected the earlier compact-data retention judgment: row eligibility remains
unchanged, but every original column for every retained source row must remain available. The
replacement local bundle therefore stores immutable source schemas and ordered raw payload values;
the SQLite catalog exposes them through read-only source-record inspection. `municipality` and
`keywords` are retained for inspection only and do not become aliases, selection policy, airport
groups, route data, or planner evidence.

The initial lossless publication exposed an unindexed raw-evidence lookup. A matching
`(source_schema_name, source_record_id)` index was added before derived evidence loading and the
nonessential artifact index was deferred until after bulk load. The validated replacement release
is `data/search_planning/catalogs/m1a-3cb7981519612945`.

Independent final qualification recorded: release digest/manifest validation, SQLite integrity and
foreign-key checks, 1,810,402 retained raw records with schema-length agreement, 3,244 retained
OurAirports rows with zero full-payload mismatches, and explicit New York City no-airport-expansion
behavior. Focused catalog/preparation/serving tests passed 36 tests; planner grounding/endpoint/
path tests passed 87 tests. The prior incomplete and column-dropping local artifacts plus expanded
raw downloads were removed after validation; the compact bundle and validated catalog remain.

On 2026-09-16, the owner approved and closed Milestone 1B. This closeout does not authorize
Milestone 2 connectivity, providers, route inference, or airport-group expansion.
