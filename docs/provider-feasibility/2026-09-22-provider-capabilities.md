# Provider capabilities and reusable saved-search coverage

Updated: 2026-09-25. Current development evidence; provider qualification is unclaimed.

## Start here

The single current collection is
[**evidence/provider-stage/saved-searches/**](../../evidence/provider-stage/saved-searches/README.md).
Its README and machine-readable index identify the saved queries, response files, receipts,
versions, coverage, provenance, and offline replay instructions. Superseded campaign folders have
been removed at the owner's request. Earlier execution history remains in the build logs;
those historical paths are not instructions for new development.

The active capability and budget configuration is
[`provider-stage-current.json`](../../data/provider_capabilities/provider-stage-current.json).
Each saved live execution has its original embedded policy/capability snapshots, preserved for
exact replay. These are saved execution identities, not alternative active configurations.

## Historical coverage and current replacement

The table and measurements below describe the 2026-09-23 evidence review. Its standalone
captures and combined result were retired from the active corpus on 2026-09-25. The
[current plan-linked corpus](../../evidence/provider-stage/saved-searches/README.md) contains
two live results with timed LAX→BKK awards and SFO→LAX positioning cash from their own frozen
plans; see the [refresh record](../build-log/2026-09-25-plan-linked-provider-corpus.md).

### 2026-09-23 saved coverage

| Area | Retained evidence | What it supports |
| --- | --- | --- |
| Exact award searches | SFO–BKK exact business and mixed-intent captures | Empty/success behavior and summary normalization |
| Award date windows | May SFO–BKK single response and corrected complete five-page stream | Pagination and equal 93-row coverage across retrieval modes |
| Multiple award airport pairs | Japan 2 × 2 rectangle and four singleton comparisons | Pair attribution and a sampled batching comparison; runtime batching stays disabled |
| Qatar source | JFK–DOH and DOH–BOM summaries, inline trips, bounded Get Trips | Detail-level distinction and tax/seat unknowns |
| Current cash behavior | Repaired SFO–BKK May sample, Japan, domestic one/two travelers, LAX–SYD, DOH–BOM | Missing price, multi-stop, traveler contrast, date-line, and non-US normalization |
| Actual combined execution | Current mixed-intent SFO–BKK October 5 request, live result and exact replay | Frozen-plan execution, attachment, and full accounting under a small budget |
| Planning inputs | Five current request/compiled-plan bundles | Reusable upstream inputs; not full live provider coverage of those plans |

The six current cash contrast captures contain 81 observations: 80 priced and one null-priced.
All retain unknown price scope. The month sample includes two itineraries with at least two stops.
The nominal sparse/non-US case returned six observations; its label does not establish a sparse
market. The combined task separately contains four award and four priced cash observations,
with three completed and 22 omitted coverage units. It is a partial result with exact replay.

## Seats.aero boundary

The [Cached Search reference](https://developers.seats.aero/reference/cached-search) describes
`GET /partnerapi/search`; the [Get Trips reference](https://developers.seats.aero/reference/get-trips)
describes `GET /partnerapi/trips/{availability-id}`. The accepted local adapter remains
`cached-search-v1` on `partnerapi`. Current retained captures remain applicable even though they
were acquired before the cash parser repair.

Runtime executes singleton airport pairs. The complete sampled rectangle comparison is retained,
but it does not establish exhaustive evaluation of absent pairs or enable runtime batching.
The corrected pagination stream follows validated cursor/skip information and retains fixed query
filters. Summary plus bounded Get Trips supplies complete segments where available; inline
Qatar trips in these captures do not contain complete segment detail.

Qatar's raw zero taxes and positive seat numbers remain preserved. They do not establish actual
fees or traveler adequacy under the [source limitations](https://developers.seats.aero/reference/concepts-copy).
Provider trip/segment times are treated as airport local and resolved using catalog timezones.
Account-specific remaining quota is unknown.

## gfly boundary

The current effective version is `0.3.0+award-search-unpriced-v1`, using gfly 0.3.0 and
fast-flights 3.1.0 with a reviewed repository-owned compatibility launcher. See the
[compatibility record](2026-09-23-gfly-compatibility.md) for source fingerprints and invocation.
Only the observed empty price vector is mapped to null; the itinerary survives, zero stays zero,
and unrelated malformed shapes still fail. Installed packages, Google backend, and persistent
throttle remain unchanged.

Each cash acquisition is one pair/date; `--limit 0` preserves complete local output and is not
an upstream work budget. Requested traveler/cabin values do not prove returned adequacy, and
amounts have unknown per-traveler/party scope. These are indicative observations, not bookability.

## Reuse and limits

Use the current collection's offline replay instructions. Normalized results preserve source identity,
query attribution, evidence hashes, field unknowns, and coverage/resource receipts. The old
combined result and controlled contrast were retired in the 2026-09-25 replacement; their
measurements above remain historical.

Failure regression fixtures remain under `tests/fixtures/providers`; they are not selectable
current saved searches. No new provider calls were made for consolidation. Ranking, mixed-journey
assembly, recommendations, owner stage acceptance, and broad provider reliability remain outside
these evidence claims.
