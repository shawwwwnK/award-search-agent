# 2026-09-08: Initial provider intake

## Scope

The active feasibility spike evaluates **Seats.aero** as the primary award-inventory candidate.
**SerpAPI Google Flights** is recorded as a later candidate for live cash-fare results. Neither is
an implemented application provider, and no live query was made in this intake.

## Credential handling

- Provider-key variable names are documented in `.env.example`; real values belong only in the
  ignored `.env` file.
- No credential is present in this record, the downloaded reference snapshot, or a tracked file.
- The local `.provider-docs/` directory is ignored. It contains public reference material only,
  not API responses or credentials.

## Local documentation snapshot

Downloaded 2026-09-08:

- Seats.aero's `llms.txt` index and all 19 linked `reference/*.md` pages under
  `.provider-docs/seats-aero/`.
- SerpAPI's Google Flights reference page under
  `.provider-docs/serpapi/google-flights-api.html`.

The upstream sources remain authoritative and may change:

- <https://developers.seats.aero/reference/getting-started-p>
- <https://serpapi.com/google-flights-api>

## Seats.aero: award-inventory candidate

| Check | Initial evidence | Status |
| --- | --- | --- |
| Intended role | Award availability and trip-level itinerary data. | In scope |
| Authentication | `Partner-Authorization` request header. | Documented |
| Relevant endpoints | Cached Search (`/partnerapi/search`), Bulk Availability, Get Trips, and Live Search. | Documented |
| Required planning inputs | Cached Search accepts origin/destination airport lists, date range, sources, cabins, and filters. | Documented |
| Candidate result fields | Availability summaries expose route, date, cabin availability, mileage cost, seats, carriers, directness, and timestamps; trip retrieval can add segments, times, stops, taxes, and flight numbers. | Documented, program-dependent |
| Permitted use | The official reference says Pro access is for non-commercial use and commercial use requires written agreement. | Must remain within personal/non-commercial scope |
| Quota | The owner reports a Pro allowance of 1,000 calls/day; the official reference describes Pro access as up to 1,000 calls/day. | Account-specific quota reading remains pending |
| Freshness and completeness | Cached and live searches are distinct. Individual programs may omit seat counts or trip data; the spike response contained an `UpdatedAt` field on every returned record. | Observed field presence only |
| Replay fixture | A sanitized success summary is in `evidence/provider-feasibility/2026-09-08-seats-aero-cached-search-success.json`. No provider error response has been captured. | Success captured; error path pending |

### Narrow live-spike result

One minimal cached-search request was made on 2026-09-08 for SFO to NRT over a three-day future
window with `take=10` and without `include_trips`. It returned HTTP 200 in 0.138 seconds and
22,505 bytes. The response had 10 availability records, the documented top-level pagination
fields, route information, cabin availability/cost/seat fields, and `UpdatedAt` on every returned
record. The complete response was discarded after the credential-free success summary was created.

The one-call result demonstrates authenticated access and a usable cached-search contract. It does
not establish comprehensive inventory coverage, booking availability, a freshness SLA, trip-level
detail, or provider error behavior.

## SerpAPI Google Flights: cash-fare candidate

| Check | Initial evidence | Status |
| --- | --- | --- |
| Intended role | Live cash-fare search through the Google Flights engine. | Deferred, in scope later |
| Endpoint | `https://serpapi.com/search?engine=google_flights` | Documented |
| Relevant planning inputs | Departure/arrival airport or location IDs, outbound/return dates, cabin, passengers, filters, and round-trip flow tokens. | Documented |
| Account quota | The owner reports the free plan allows 250 calls/month. | Account-specific live verification pending |
| Result caveat | The reference states default results may differ from the browser; `deep_search=true` can improve similarity at higher latency. | Documented |
| Fixture and rate-limit behavior | Not yet tested. | Pending |

No SerpAPI call should be used during the Seats.aero award-inventory spike. Its lower owner-reported
monthly quota warrants a separately budgeted cash-fare feasibility test later.

## Outcome

Seats.aero has passed the narrow access-and-response-shape spike and is suitable for the fixed
one-provider vertical-slice design. The later implementation must still add offline success and
failure fixtures, validate its narrower result contract, and surface provider failures explicitly.
