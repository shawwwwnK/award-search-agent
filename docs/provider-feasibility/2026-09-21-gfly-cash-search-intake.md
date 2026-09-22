# 2026-09-21: `gfly` cash-search feasibility intake

## Scope

This read-only investigation assessed whether `gfly` and three related projects could provide
lightweight cash-fare observations without a paid subscription. It did not add a provider adapter,
change runtime behavior, or qualify cash search for product use.

Repositories reviewed:

- <https://github.com/rnwolfe/gfly>
- <https://github.com/AWeirdDev/flights>
- <https://github.com/microsoft/Webwright>
- <https://github.com/HaroldLeo/google-flights-mcp>

## Conclusion

`gfly` is the preferred first experimental integration surface. Its default backend requires no API
key or LLM call and wraps `fast-flights` with a versioned JSON envelope, persistent throttling, and
structured blocked, rate-limited, schema-drift, empty, and retryable outcomes. It does not remove
the underlying risk: the data comes from an undocumented reverse-engineered Google Flights path.

`fast-flights` is the underlying lower-level library and remains a possible fallback if direct
library control becomes necessary. `google-flights-mcp` adds unnecessary MCP coupling, pins an older
`fast-flights` generation, and exposes weaker itinerary/provenance semantics. Webwright is useful
for browser exploration or authoring a standalone fallback script, but its browser and model loop
is not the lightweight provider boundary sought here.

## Pinned evidence

The inspected `gfly` repository commit was
`43b1aa4bbe5b442cc7fd3a7c285c940bb39561db`; PyPI version `0.3.0` was the tested package. The
isolated environment used Python 3.12, `fast-flights 3.1.0`, and `airportsdata 20260905`.

Exactly one credential-free live command was executed, with no proxy, retry, CAPTCHA handling, or
throttle bypass:

```text
gfly search SFO LAX --depart 2026-10-20 --stops nonstop --sort price --limit 3 --json
```

The command returned schema version `1`, backend `google`, 29 total itineraries, and three displayed
USD 59 nonstop results from Southwest, United, and Delta. The complete isolated install-and-query
command took 10.1 seconds. This establishes a working live path at one point in time; it does not
establish price accuracy, completeness, availability, bookability, or sustained reliability.

The attempted upstream offline test run exceeded the investigation timebox and was interrupted. It
must not be recorded as passing.

## Capability relevant to the next stage

The JSON surface can supply the owner's minimum cash-observation need: origin, destination,
departure and arrival, duration, stops, airlines, displayed price, and currency. The free backend
does not reliably supply booking tokens, flight numbers, or a bookability guarantee. Those fields
are not required for the approved cash benchmark, but price scope, traveler semantics, cabin
treatment, local-time semantics, and incomplete-result behavior still require acceptance fixtures.

The default persistent throttle is 12 seconds across processes. A date range is effectively one
search per day. Consequently, cash work must have a provider-specific progressive budget and must
not mirror all compiled award query-date-days.

## Risk boundary

Do not disable the throttle, rotate proxies, solve CAPTCHAs, use abuse-exemption mechanisms, or
create automatic retry storms. Stop cash execution on blocking or schema drift. Use remains local,
personal-scale, read-only, and experimental unless a later decision establishes a broader permitted
boundary.

## Decision link

[ADR 0022](../adr/0022-award-first-cash-observations.md) uses this feasibility evidence to open a
narrow award-first cash benchmark and positioning design. It does not adopt `gfly` as a qualified
provider or change the active runtime.
