# Ranking M2 currency snapshot

`fx-2026-09-29.json` is an explicit, replayable USD/CAD conversion input, not a live currency
lookup. Its `source_digest` is the SHA-256 of `fx-source-2026-09-29.json`, the captured dated
[Bank of Canada response](https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?start_date=2026-09-29&end_date=2026-09-29).

The official observation is 1 USD = 1.4188 CAD. The snapshot's CAD-to-USD rate is its reciprocal
at 28 decimal digits of precision; USD has an identity rate of 1. The September 30 query returned
no observations; the most recent returned observation was September 29. This records an actual
source date, not an invented October 1 rate.

Only USD and CAD are supplied. Unsupported currencies remain explicit normalization gaps,
not parity conversions. Unknown quote scope remains unknown even when a currency rate exists.
Runtime must use the supplied snapshot without a network refresh. Tests may use clearly labeled
synthetic snapshots; they are not market-rate evidence.
