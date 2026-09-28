# 2026-09-23: gfly investigation and Provider Stage live gates

> Artifact-location update (2026-09-23): the owner requested one current reusable corpus.
> Start at [saved searches](../../evidence/provider-stage/saved-searches/README.md).
> Dated campaign paths and v1/v2 standalone configurations below are historical identifiers;
> superseded files were removed, while retained current captures were consolidated.
> The canonical index records migration provenance. Original execution measurements remain valid.

Status at the time of this engineering record: implementation, live gates, and independent
evidence review complete. The owner subsequently accepted Provider Stage on 2026-09-23; see
the [closeout](../handoffs/2026-09-23-provider-stage-closeout.md).

## Authorized work

The owner explicitly requested orchestration of the gfly investigation, completion of the
interrupted cash contrast captures, and one fresh combined live executor task. This reopens
bounded acquisition after the earlier campaign's recorded schema-drift stop. It does not erase
that stop, authorize unbounded retries, or qualify the stage on the owner's behalf.

Independent agents own offline diagnosis, the capture/executor harness, and critical review.
The parent integrates changes, controls live-call admission, and records the final disposition.

## Initial evidence

The earlier failed SFO–BKK May 15, 2027 capture saved a structured `SCHEMA_DRIFT` stderr with
`IndexError: list index out of range`; the response artifact contained empty stdout. It did not
save the upstream response or traceback, so it cannot establish the exact historical failing
offset. Installed gfly 0.3.0 and fast-flights 3.1.0 source hashes match their distribution RECORD
entries. No local parser patch was present. The gfly backend maps multiple upstream parsing
exceptions into the same failure code.

The new campaign will preregister exact requests, implementation hashes, finite call/byte/time
limits, and stop conditions before making a normally throttled diagnostic call. A successful
diagnostic cannot retrospectively establish the historical cause; a repeat failure must be
diagnosed offline before another call is justified.

## Results and verification

The first new live diagnostic reproduced `IndexError` in `fast_flights/parser.py:77`
on the same SFO–BKK May 15, 2027 query. Seven rows had prices; row eight had a valid
itinerary but `k[1][0] == []`. The upstream unchecked price index failed the entire
response. This establishes the new failure, not the unknowable exact historical offset.
The installed parser/backend remained unchanged and matched their distribution hashes.

The diagnostic receipt lives under `evidence/provider-stage/2026-09-23-cash-validation/`.
Private HTML (2,282,568 bytes) was retained only under `/private/tmp`; the checked-in
`tests/fixtures/providers/gfly_missing_price_minimized.json` contains only parser-read
fields and reproduces the failure. An offline substitution preserves all eight rows,
with prices `[535, 566, 570, 670, 697, 773, 1156, null]`.

The repository-owned `scripts/gfly_compat.py` verifies upstream versions and source
hashes, then changes only the observed empty price vector to `None` in memory. It keeps
normal gfly CLI, backend, and persistent throttle behavior; installed packages are not
modified. Effective version is `0.3.0+award-search-unpriced-v1`. Production CLI uses an
explicit pinned Python executable plus `--gfly-wrapper`; capability and observed
versions must match. Other malformed structures retain their failure behavior.

The initial manifest captured an earlier cash-harness digest while that harness was
being finalized. The diagnostic wrapper and exact diagnostic query were unchanged;
no continuation occurred under the mismatched manifest. The immutable v2 manifest
will import that one failed diagnostic and bind the finalized repair and harness
before further calls. It permits one post-fix validation, five remaining contrasts,
and one combined cash call: eight cash acquisitions total including the failure,
with a separate one-call Seats.aero allowance for the combined task.

The post-fix same-query call returned all eight rows, including the null-price row.
All five remaining contrast calls succeeded: Japan 5 itineraries, domestic one/two
travelers 29 each, LAX–SYD date-line 4, and DOH–BOM 6. The month capture contains two
itineraries with at least two stops, satisfying the complex-connection contrast without
another call. The typed controlled contrast replay preserves the failed diagnostic
and six successful responses: 81 cash observations, 80 priced, all price scopes unknown.
Its synthetic execution binding is explicitly labeled; it is evidence of contrast
normalization/accounting, not a claim that those contrasts form one real M2C request.

The final production CLI live task used the unchanged current mixed-intent trace,
SFO–BKK October 5, 2026, one traveler. One Seats.aero summary call returned three raw
rows and four normalized award observations; one cash call returned four priced cash
observations. Its typed result is truthfully `partial`: all 25 coverage units are
accounted for, three completed and 22 omitted under the deliberately small budget.
The offline CLI replay is byte-for-byte equal to the live result. Both CLI exit codes
are 1 because graph coverage is partial; the positive-observation/replay gate passed.

New-work totals are eight cash acquisitions (one failed diagnostic, seven successful),
42,802 response bytes and 51.901 active seconds, within eight calls / 2,000,000 bytes /
300 seconds. The combined award call used 6,687 bytes and 0.264 seconds. Including the
preceding campaign, development acquisition totals are 11 cash and 23 Seats.aero calls;
these are acquisition counts, not unique searches or reliability measurements.

All new evidence is under `evidence/provider-stage/2026-09-23-cash-validation-v2/`:
`manifest.json`, post-fix receipts, `gfly/`, `cash-run-summary.json`,
`cash-contrast-controlled-result.json`, `cash-contrast-replay-summary.json`, and the
combined bundle/tape/live result/replay result/receipt. Older failed manifests and
receipts remain immutable. `data/provider_capabilities/provider-stage-development-v2.json`
binds the reviewed compatibility behavior; v1 remains historical.

Verification: all 60 provider/compatibility tests passed in 1.73 seconds; scoped Ruff
passed; mypy passed for 10 runtime/CLI files. The repair reviewer independently ran
20 targeted tests and checked fixture -> patched parser -> normalized typed observations.
No model calls, package-file edits, automatic retries, proxy changes, or throttle bypass
were used. The local launcher requires the pinned `/private/tmp/gfly-live-py312` environment;
portable packaging and other upstream schema changes remain unqualified.

The requested engineering gates 1–3 are complete. Owner stage acceptance, provider
reliability/bookability qualification, and later ranking/output work are not inferred.

## Owner acceptance

On 2026-09-23, after reviewing the Provider Stage walkthrough and the saved combined
`ProviderResultSet` example, the owner explicitly said, “Ok I approve this stage. Mark this
stage finish.” The accepted scope is the typed, replayable `ProviderResultSet` boundary in
ADR 0022 and the revised handoff. This is owner stage completion, not provider qualification
or acceptance of ranking/output behavior. See the
[closeout](../handoffs/2026-09-23-provider-stage-closeout.md).


## Final integration review

The [independent final review](../reviews/2026-09-23-gfly-repair-and-live-gates-review.md)
reported no blockers. It verified source/bundle/receipt hashes, exact live/replay equality,
unchanged original request and plan, attachment validation, complete 25-unit coverage accounting,
and the separate synthetic contrast evidence. Parent revalidated frozen implementation hashes
and all three typed results without provider calls. Scoped script Ruff and `git diff --check`
passed. A final credential-value scan of 164 changed/untracked files found zero matches.
