# Provider Stage independent implementation review

Date: 2026-09-23. Review scope: downstream provider contracts, adapters, resource execution,
evidence, replay, CLI, and graph attribution. This is an engineering review, not owner acceptance
or provider/product qualification.

## Implemented boundary

The implementation keeps request/session and M2C planning state unchanged. The new executor
uses caller-owned freshness authority before acquisition and before attachment. It gives every
logical query, mandatory use, supplemental use, relationship, positioning dependency, and
downstream cash query an explicit coverage receipt. Serialized observations must reference their
physical query and a captured transport; resource totals must reproduce those receipts. A call
recorded after exhausted resource limits fails validation.
Successful coverage must also reconcile to successful terminal transport streams; changing a
failed receipt into a success label cannot create an attachable result. Original typed result
validation obligations and deferred-constraint IDs/text/query bindings survive into the result
without reinterpretation or an invented claim of enforcement.

The reviewer examined `providers/contracts.py`, `execution.py`, `seats_aero.py`, `gfly.py`,
`transport.py`, `evidence.py`, `timezones.py`, `replay.py`, and `cli/provider_results.py`.
The reviewer implemented contracts and their tests, then independently inspected the other
implementation owners' work. This is not an independent review of the reviewer's own contracts;
the parent agent retains integration and acceptance responsibility.

## Findings resolved during review

- Partial/malformed pages could be promoted to complete streams. Execution now preserves failure
  and partial outcomes and does not claim that interrupted or unknown pair coverage is empty.
- Positioning used an arbitrary preceding date for access and the award departure date for egress.
  Activation now uses observed itinerary endpoint dates and checks the original outbound window
  for access research. It does not claim connection feasibility or assemble a journey.
- First-member pagination could consume the known minimum call capacity for the other member of
  an admitted strategy bundle. The executor now reserves a first request/attempt/page for each
  remaining member; unsuccessful completion remains explicit.
- Mandatory selection initially used sorted query hashes. It now chooses marginal endpoint
  coverage, shared-strategy reuse, fair endpoint counts, and date cost deterministically. Direct
  cash sampling rotates across those endpoint probes before taking another sample per probe.
- Duplicate observations within one page could fail result serialization. In-page and cross-page
  provider IDs are accounted for; normalized exact-repeat IDs are deduplicated sequentially.
- Failed transports recorded zero elapsed time. Failures now retain measured elapsed time;
  malformed and overlarge responses retain bounded sanitized context and explicit truncation.
- Returned cabin, seat, and physical-component scope needed validation findings. Adapters now
  retain mismatches/unknowns, observed retrieval times, and typed tax units. Requested scope is
  separate from returned evidence.
- Cash acquisition needed a pinned executable check. The live CLI performs a bounded local
  version preflight, binds the parser implementation identity, and preserves the recording tape
  even if later execution fails.
- Replay needed the recorded acquisition limits and cursor to reproduce genuine timeout/byte
  overruns without inventing a response or falling through to a live provider.
- Intermediate-airport timezones were limited to M2C's airport directory. The catalog-bound lazy
  resolver now supports returned connection airports while preserving unknown catalog lookups.
- Evidence now removes an echoed configured Seats.aero credential even when it appears under an
  ordinary provider message field.

## Independent graph audit

`tests/unit/test_provider_review.py` runs six bounded fake-transport cases using the current saved
Japan, India, and exact-airport traces. Each trace runs under both a three-award-request budget and
a progressive budget of its mandatory query count plus five. Cash has its own three-call budget.

The Japan graph contains 47 logical queries, 40 mandatory uses, 24 supplemental uses, and 12
relationships. India contains 84 logical queries, 60 mandatory uses, 144 supplemental uses, and 72
relationships. These high-fanout traces have no positioning dependencies; the exact-airport trace
adds that audit dimension. The tests independently enumerate original graph IDs, check each
executed and omitted unit, verify shared-query attribution and partial relationship accounting,
check resource ceilings and ordering, and prove unchanged plans, JSON reload, and attachment
validation. All six pass. Scoped Ruff and mypy pass.

## Live capture evidence reviewed

In the v4 2 × 2 experiment, the rectangle returned three LAX–HND rows. The four singleton streams
returned the same three rows and no rows for the other three pairs. All streams reported
`hasMore=false`; the combined singleton rows match both IDs and complete payloads. This supports
the declared comparison, not a general guarantee that an absent batched pair was exhaustively
searched. Runtime batching must stay disabled until the implementation enforces exact pair-level
authorization and attribution.

The v4 Qatar captures returned two JFK–DOH records with five reported business seats and six
DOH–BOM records with four. They supplied numeric zero business taxes, USD currency, and empty trip
arrays. These are not absent field values and are not proof of zero payable taxes. The summary
adapter was corrected to preserve the raw zero and empty-array states while retaining unresolved
Qatar tax meaning. The v4 exact inline-trip search was empty and could not support a nonvacuous
detail-mode comparison.

The v6 follow-up supplies that comparison. Inline expansion contains two business trip IDs but
zero physical segments. Two Get Trips calls return seven trips across cabins; the two business
IDs match inline exactly and each contains one physical segment. Inline used 7,755 sanitized
bytes; the two Get Trips bodies total 11,463 bytes in addition to summary acquisition. This
supports summary search plus bounded Get Trips for complete-itinerary evidence in the reviewed
development slice. It does not establish broad source or cabin coverage. The same campaign
completed five month-search pages of 20, 20, 20, 20, and 13 records, with 93 unique IDs and an
explicit terminal `hasMore=false`.

The reviewed executor enumerates one detail opportunity per observed parent-query/availability
ID, combines its source summary observations, and rotates across parent queries. All opportunities
receive receipts, including those omitted by the independent detail-call allowance. Detail calls
also consume general award requests, attempts, rows, bytes, and elapsed resources, but do not
consume search-page counters. Mandatory summary acquisition precedes its details and direct cash;
supplemental detail work uses the remaining award allowance. Attachment reconstructs the same
opportunities from source summaries and rejects changed detail activation or graph attribution.

The proposed development policy is internally consistent: 12 distinct award requests, 24
attempts, 22 search pages, two detail calls, 1,000 rows, 4 MiB, and 90 active-call seconds; cash
has its own three requests/attempts/pages, 250 rows, 2 MiB, and 90 seconds. These are conservative
engineering limits informed by the captures, not measurements of the owner's remaining account
quota. Singleton execution remains the default. The capability record's explicit quota and
qualification caveats must remain visible.

The cash campaign's schema-drift stop remains binding. Combining previously captured live cash
and award responses through replay proves integrated replay over live-origin evidence. It does
not prove a fresh two-provider live executor run after that stop.
The saved joint replay contains four award and four cash observations with three completed and
19 omitted coverage units. The unattempted cash contrast cases and a fresh combined live executor
run remain unmet campaign/gate items; neither is silently substituted by the replay. No further
cash call is justified merely to complete those claims after the recorded schema-drift stop.

## Remaining limits

This review does not establish account-limit acceptance, provider reliability, broad coverage,
bookability, or stage owner qualification. The reviewed numerical limits and detail strategy are
development choices supported only by the stated captures. HTTP timeouts are finite but a late read can exceed a remaining elapsed allowance;
overruns stop later calls and remain visible. No strict end-to-end deadline including local
parsing is claimed. Mixed-journey assembly, ranking, value, and recommendations remain outside
Provider Stage. No deeper architecture escalation is recommended.
