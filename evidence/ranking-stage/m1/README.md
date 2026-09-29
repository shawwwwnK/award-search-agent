# Ranking M1 saved matching results

These are deterministic local development outputs from the three [plan-linked Provider Stage
runs](../../provider-stage/saved-searches/README.md). Each `MatchedJourneySet` embeds its frozen
request, compiled plan, full provider result, validation reasons, and pairing receipts. It
preserves the provider's partial coverage and unknown fields. No provider or model call was
made to create these files. All three outputs use matching policy `m1-v2`; the two September 25
outputs were regenerated unchanged in distribution when only the cabin rule moved from m1-v1
to m1-v2 (see the build log).

| Input run | Output | Admitted | Conditional | Rejected | Research leads | Scoped mixed pairs |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `mixed_access` | [JSON](mixed_access.json) | 17 (all direct award) | 240 | 216 | 0 | 456 |
| `exact_business` | [JSON](exact_business.json) | 0 | 106 | 290 | 0 | 396 |
| `sfo_to_bkk_positioning` | [JSON](sfo_to_bkk_positioning.json) | 5 (all award-cash egress) | 59 | 58 | 1 | 123 |

The `sfo_to_bkk_positioning` run is the first live admitted mixed journeys: its five
`award_cash_egress` candidates join the two-seat aeroplan SFO→TPE→SIN economy award to
SIN→BKK cash positioning whose provider-returned party echo is recorded as returned-traveler
evidence, under a positioning dependency with resolved permission. Each admitted journey passes
the two-hour and same-or-next-local-day transfer rules, confirms travelers, seats, and the
requested cabin at journey level, and still records honest unknowns: per-leg award cabins are
unreported (accepted at journey level under the owner's m1-v2 decision), price scope is
incomplete, and admission is not a booking or availability guarantee.

Under m1-v2 (owner decision, 2026-09-27), a confirmed, matching journey-level award cabin is
accepted when the provider does not report per-leg cabins; the unreported legs stay visible as
non-blocking `cabin`-dimension reasons. A leg that does report a cabin outside the requested
set still rejects the journey. Mixed options that pass route and schedule checks otherwise remain
**conditional** when returned traveler, seat, or positioning-permission evidence is unresolved,
and become **research leads** when the timing structure itself is missing. Direct cash
benchmarks are retained separately and never become award-led journeys. Source duplicates remain
distinct observations and candidate variants.

Rebuild a result from the repository root with the offline command, choosing a new output path:

```sh
PYTHONPATH=src .venv/bin/python -m award_agent.cli.ranking_match \
  --bundle evidence/provider-stage/saved-searches/runs/sfo_to_bkk_positioning/bundle.json \
  --result evidence/provider-stage/saved-searches/runs/sfo_to_bkk_positioning/result.json \
  --output /private/tmp/sfo-to-bkk-positioning-m1.json
```

The saved output SHA-256 digests are:

- `mixed_access.json`: `074229e8bf20615e2bfeb2f96cbbc33e8716265dc4adf6f266317240f2dfa5b0`
- `exact_business.json`: `adb56166c6c1d63b568ff32482130c882d3af36825fee3e16bf523be562b2b58`
- `sfo_to_bkk_positioning.json`: `7e4f2501f41fe724aee6724a9e5060670c7afdd2f1f02a5bf49f0b542e260c50`

The cash egress and next-day boundary tests use synthetic fixtures; the saved live runs cover
access positioning (September 25) and destination-side egress positioning (September 27). M1
does not rank these candidates or produce user-facing recommendations.
