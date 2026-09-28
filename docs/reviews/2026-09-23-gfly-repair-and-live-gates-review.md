# Independent review: gfly repair and remaining live gates

> Artifact-location update (2026-09-23): the owner requested one current reusable corpus.
> Start at [saved searches](../../evidence/provider-stage/saved-searches/README.md).
> Dated campaign paths and v1/v2 standalone configurations below are historical identifiers;
> superseded files were removed, while retained current captures were consolidated.
> The canonical index records migration provenance. Original execution measurements remain valid.

Date: 2026-09-23. Disposition: **no remaining engineering blocker found for the
requested repair, cash contrasts, and fresh combined live-task gates.** This is
an independent AI engineering review, not owner acceptance or provider qualification.

## Scope and evidence

Reviewed the repository compatibility launcher, adapter/CLI integration, diagnostic
wrapper, preregistered v2 campaign runner, sanitized responses and receipts,
controlled contrast replay, and combined live result/tape/replay under
`evidence/provider-stage/2026-09-23-cash-validation-v2/`.

The review made no provider calls and changed no implementation. The full private
upstream HTML was neither printed nor added to the repository. Its digest and
the minimized parser-read fixture preserve the diagnostic link.

## Reproduced defect and bounded repair

The new same-query diagnostic failed at fast-flights 3.1.0 `parser.py:77`:
the eighth of eight returned itinerary rows had an empty inner price vector.
The original parser indexed its second element and lost the whole response.
The earlier historical error contained no upstream payload, so identical historical
row-level causation remains unproved.

`scripts/gfly_compat.py` verifies the reviewed installed source hashes and performs
one anchored in-process parser change. Only an empty price vector becomes `None`.
It retains the itinerary, emits JSON `null`, and preserves unrelated malformed
shape failures. It does not use a numeric sentinel, discard rows, alter installed
packages, change backend, or bypass the normal throttle. The effective version is
`0.3.0+award-search-unpriced-v1`; base versions and compatibility/source hashes
remain separately recorded and bound to the campaign and capability.

Independent offline verification passed:

- `pytest -q tests/unit/test_gfly_compat.py tests/unit/test_provider_adapters.py
  tests/unit/test_provider_results_cli.py`: **20 passed**.
- Scoped Ruff for the compatibility launcher, adapter, CLI, and compatibility tests:
  passed.
- A separate minimized-fixture → patched upstream parser → gfly normalizer →
  production adapter check retained all eight observations with prices
  `535, 566, 570, 670, 697, 773, 1156, null`. The null observation retained
  `cash_price_unknown`; all price scopes stayed unknown and all derived chronology
  checks passed. Zero and unrelated malformed price shapes have regression coverage.

The single same-query post-fix call was a separately preregistered validation after
a reproduced and reviewed repair. It was not an automatic retry of an unexplained
failure. The original failed diagnostic remains immutable and counted.

## Capture and replay results

The v2 amendment accounts for **eight cash acquisitions**: failed diagnostic,
post-fix validation, five contrasts, and the combined live task. It consumed
**42,802 raw command-output bytes** and **51.900709 active command seconds**, below
the registered 2,000,000-byte/300-second ceilings. These byte counts differ from
pretty-printed sanitized file sizes. Active command time includes throttle waiting;
it is not a pure network-latency measurement.

The post-fix response retained eight itineraries, including one unpriced itinerary
and two itineraries with at least two stops. The five previously unattempted
contrasts returned Japan 5, domestic one adult 29, domestic two adults 29,
date-line 4, and non-US 6 observations. No contrast remained unattempted.

The controlled replay includes the failed diagnostic and six successful captures:
seven typed acquisitions, **81 observations, 80 priced and one null-priced**.
All 81 retain unknown price scope and have catalog-derived, non-reversed chronology.
The four LAX–SYD observations retain their actual later local arrival dates.
The domestic one/two-adult responses have 29 matching itinerary signatures with
different displayed amounts; this does not prove price scope or traveler adequacy.
The nominal sparse/non-US case returned six rows and is not evidence of an empty
or intrinsically sparse provider market.

The controlled contrast `ProviderResultSet` deliberately uses an explicitly
synthetic execution binding. It verifies acquisition, normalization, field unknowns,
and typed evidence reconciliation. It is not a fresh M2C compiler execution or an
attachable result for one actual user request. Source trace names and endpoint IDs
remain in the parsed-page record. The separate combined task supplies the actual
frozen-plan execution and attachment evidence.

## Fresh combined executor gate

The actual live CLI ran the unchanged `mixed_award_cash_eligible` current trace:
SFO–BKK, October 5, 2026, one traveler. Independent comparison confirmed that its
complete compiled plan and effective request equal the frozen trace artifacts.

- Seats.aero: one request/attempt/page, three raw rows, four normalized award
  observations, zero detail calls, 6,687 bytes, 0.264046 active seconds.
- gfly: one request/attempt/page, four rows and four priced USD cash observations,
  2,575 bytes, 1.246527 active seconds.
- Coverage: all **25 units** retained; **3 completed and 22 omitted**. Omission
  reasons are 18 supplemental budget/activation, 3 resource-budget exhaustion,
  and 1 absence of observed-award activation.

The partial result and exit code 1 are truthful consequences of the declared
one-award/one-cash budget. They are not a failed live gate or complete graph
coverage claim. Independent `validate_result_attachment` passed against the original
plan, caller authority, capabilities, and policy. Every execution coverage unit has
exactly one receipt, and every omitted unit has an explicit reason.

The saved live result and offline replay result are byte-for-byte equal. Both tapes
validate against the typed replay contract. Manifest, bundle, capability, source,
receipt/body, summary, and replay-artifact hashes checked in this review matched;
installed base parser/backend hashes also remain unchanged.

## Remaining limits

Owner stage acceptance and account-specific remaining allowance are not established
by this review. Provider reliability, bookability, returned cabin/traveler adequacy,
general upstream parser stability, exhaustive market coverage, ranking, mixed-journey
assembly, and recommendations remain unclaimed. Runtime rectangle batching remains
disabled. No deeper architectural escalation is recommended.
