# Provider Stage implementation contract

Date: 2026-09-22. Implements the approved Provider Stage handoff; capture acceptance and owner
qualification remain separate evidence claims.

The frozen M2C graph is input evidence. `providers/contracts.py` owns downstream immutable models;
`execution.py` owns deterministic selection, activation, accounting, and fresh handoff checks;
`seats_aero.py` and `gfly.py` own request mapping and response interpretation; `transport.py` owns
bounded single attempts; `evidence.py` owns immutable sanitized capture storage. The existing
intent, clarification, and planning boundaries are unchanged.

## Adapter seam

`ProviderAdapter.fetch(query, *, cursor, timeout_seconds, max_bytes)` returns one
`CapturedResponse`. It never retries. A `ProviderQuery` specifies exact airport lists, inclusive
dates, filters, requested traveler/cabin scope, and the logical queries, uses, strategies, and
positioning evidence authorizing that acquisition. `fetch` saves the sanitized response before
returning its digest/reference. The query carries no credential. The adapter receives credentials
through its transport configuration and must exclude them from evidence and errors.

`ProviderAdapter.parse(query, capture, *, airport_timezones)` returns `ParsedProviderPage`:
observations, raw row count/IDs, pagination, outcome, and validation findings. The executor owns
pagination and duplicate-page accounting. A complete stream does not establish exhaustive coverage
of every pair in a multi-airport rectangle; `pair_coverage_exhaustive` defaults to false. Unknown
pairs in partial streams cannot produce empty receipts. Batching remains disabled until the
specific comparison evidence supports its capability flag.

`ProviderObservation` separates award summary, provider-returned award itinerary, and cash
itinerary evidence. `RawField` distinguishes absent, null, unknown, and value (including zero).
Requested cabin and travelers remain separate from returned evidence. The raw source value can
remain in `raw_fields` when interpretation marks a normalized field unknown. Catalog timezones
support local-to-instant conversion; missing/ambiguous/nonexistent local times produce findings.
Seats.aero documents airport-local clock values even when strings carry a `Z` suffix; parsing
must follow the accepted source semantics rather than treating that suffix as UTC evidence.

## Execution and replay

The execution binding contains run/session/revision, effective-request digest, compilation binding,
plan digest, and capability/policy digests. Caller authority must be checked before calls and
before attachment using `check_plan_handoff`; copying expected authority from the plan itself does
not establish freshness. Result attachment also checks its original plan and execution identities.

The coverage ledger includes every logical query, mandatory use, supplemental use, positioning
dependency, and accepted relationship disposition. Every unit receives exactly one final coverage
receipt. An inactive dependency remains explicitly omitted. The execution plan may grow only its
own downstream cash queries and coverage units when actual observations activate them; M2C stays
unchanged. Cash positioning requires an existing dependency and relevant observed award evidence;
it does not validate or assemble a journey. Explicit repositioning refusal excludes that work.

Separate award and cash budgets have no implicit numerical defaults. Every policy supplies a
version and its budget evidence. Resource usage means distinct attempted physical query IDs
(`requests`), physical calls (`attempts`), non-detail calls (`pages`), detail calls, returned raw
rows, bytes acquired, and elapsed call seconds. Failed attempts count. Receipt sums reproduce
usage. The current synchronous transport has finite per-call network/subprocess timeouts;
HTTP elapsed checks run between response reads, so one late read can exceed the remaining
elapsed allowance. Such overruns stop subsequent acquisition and remain explicit in receipts.
Parsing and local orchestration are not included in an end-to-end deadline claim. A provider
page can reveal more rows than the remaining row allowance; retain its full captured evidence,
stop further work, and mark any omitted normalization explicitly. The byte boundary must stop
reading safely and preserve a partial-evidence receipt rather than silently dropping a large body.

Mandatory award work precedes bounded endpoint cash sampling and progressive supplemental bundles.
Supplemental ordering must consider shared-query reuse, marginal coverage, bundle completion,
cost, and endpoint rotation. It is not a list-prefix truncation. All queries and uses excluded by
budgets, hard stops, or activation receive reasons. Provider blocks, rate limits, and schema drift
stop that provider; no retry, proxy rotation, or throttle bypass is allowed.

`ProviderResultSet` verifies coverage completeness and query/transport/observation references,
including provider identity, evidence provenance, and exact resource reconciliation. Exact-repeat
deduplication must preserve distinct observation times, queries/uses, programs, cabins, prices,
fees, seats, price scopes, and evidence. Transport receipts retain repeated provider IDs even when
the normalized exact repeat is represented once. Replay uses the saved response and the same
capability, policy, request, and plan; it never invokes a live transport.

## Acceptance evidence

Offline tests cover stale authority, request/filter mapping, safe rectangles, full and interrupted
pagination, attribution, field states, local dates/timezones, requested versus returned scope,
deduplication, activation, deterministic fairness, and independent finite budgets. Fixtures label
synthetic failures distinctly from live captures. The trace-derived and controlled-edge capture
campaign and the bounded owner-relevant live task remain mandatory completion gates. Successful
offline implementation alone does not establish provider qualification or close the stage.
