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

## Owner-review input still required

The prepared ignored bundle does not itself provide an authoritative source
capture/as-of date or a selected timezone-validator identity. The publication
API requires those values in `PublicationContext` and no release was generated
from the full local bundle with invented values. The next release run must use
owner-declared values, then record its actual manifest, counts, reconciliation
and quarantine observations separately.

## Owner conclusions / next cut

<!-- Owner review of a full local release, artifact retention, and 1B admission goes here. -->
