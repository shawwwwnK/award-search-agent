# 2026-09-22: Provider Stage implementation

> Artifact-location update (2026-09-23): the owner requested one current reusable corpus.
> Start at [saved searches](../../evidence/provider-stage/saved-searches/README.md).
> Dated campaign paths and v1/v2 standalone configurations below are historical identifiers;
> superseded files were removed, while retained current captures were consolidated.
> The canonical index records migration provenance. Original execution measurements remain valid.

Status: local implementation and offline verification complete; live-stage acceptance incomplete.

## Authorized scope

The owner requested implementation of the revised
[Provider Stage handoff](../handoffs/2026-09-21-award-first-provider-results-plan.md),
with delegated implementation and independent review, and authorized bounded provider calls.
The deliverable is a typed, replayable `ProviderResultSet`; journey assembly, ranking,
value calculations, recommendations, and upstream request changes remain outside this work.

## Work and evidence

- Read the active handoff, ADR 0022, project state, deferred-work register, relevant workbook
  product/provider sections, M2C contracts, and prior provider feasibility evidence.
- Preserved the owner's existing uncommitted boundary/documentation changes.
- Assigned architecture/contracts, adapters/evidence, deterministic execution, and trace-derived
  capture work to separate agents with nonoverlapping implementation ownership.
- Started the existing offline test suite before integrating Provider Stage changes.

## Implementation

- `src/award_agent/providers/contracts.py`: immutable request, capability, policy, raw-field,
  observation, transport, coverage, and result contracts with identity/resource reconciliation.
- `execution.py`: complete M2C graph projection; mandatory awards, endpoint cash samples,
  progressive supplemental bundles, evidence-gated positioning, and fresh attachment validation.
- `seats_aero.py`, `gfly.py`, `transport.py`, `evidence.py`, and `timezones.py`: injectable
  bounded transports, provider parsing, sanitized immutable evidence, conservative scope findings,
  and connection-airport timezone lookup tied to the same catalog receipt as the plan.
- `replay.py` and `cli/provider_results.py`: exact-acquisition replay, recording, separate
  caller authority, explicit live mode, executable version check, and preserved tape on failure.
- `scripts/provider_stage_capture.py` and `evidence/provider-stage/`: preregistered bounded
  captures and current-compiler replay of artificial upstream trace inputs.

## Verification to date

- `.venv/bin/pytest -q`: **467 passed, 99 skipped**, 579.85 seconds. This baseline suite was
  collected before the new Provider Stage tests were added; the new tests are run separately.
- `.venv/bin/pytest -q tests/unit/test_provider_*.py`: **56 passed** in 1.32 seconds after
  final integration and review corrections.
- `.venv/bin/ruff check src/award_agent/providers src/award_agent/cli/provider_results.py
  tests/unit/test_provider_*.py`: passed.
- `.venv/bin/mypy src/award_agent/providers src/award_agent/cli/provider_results.py
  tests/unit/test_provider_*.py --follow-imports=silent`: passed, 18 files. This is a scoped
  Provider Stage gate; it does not claim whole-repository mypy is clean.
- `.venv/bin/python -m award_agent.cli.provider_results --help` and `git diff --check` passed.
- The CLI replay test consumed six real captured cash observations, made zero provider calls,
  and retained explicit omission receipts for every disabled award logical query. This does not
  satisfy the combined award/cash live gate.

## Independent review and corrections

The architecture agent reviewed the independently implemented adapters and executor. Corrections
included preserving partial-page status, charging failed-call elapsed time, rejecting stale handoffs
before each fetch, reserving multi-query bundle capacity, validating observation/transport/coverage
attribution, checking attachment against the full original graph, preserving tax units and unknown
seat evidence, retaining retrieval identity in deduplication, and validating replay limits/cursors.
Credential-echo redaction and catalog-bound connection timezones received targeted tests.

Resource elapsed time measures captured provider-call time, not all compiler/parser wall time.
One response may overrun the remaining row/byte/time budget; it remains captured and is marked
partial, and further calls stop. HTTP per-read timeout plus elapsed checks is finite but is not a
strict composed end-to-end wall-clock deadline.

The final parent integration also rejects observations whose backend/version differs from the
bound capability, preserves typed upstream deferred constraints and query validation obligations,
and verifies the live executable version. The independent reviewer reported no remaining code
blocker for the declared singleton development boundary; see the
[review](../reviews/2026-09-23-provider-stage-implementation-review.md).

## Capture and integrated replay evidence

The preregistered campaign made **22 Seats.aero calls** within its original 30-call ceiling,
capturing 793,220 sanitized bytes over 8.463 active call seconds. Two of those calls repeated the
same page because the capture runner initially omitted `skip`; it detected the duplication and
stopped. The corrected five-page stream contained 20+20+20+20+13 rows, matching the single-page
93-row response without duplicate IDs. The 2 × 2 rectangle matched the full payloads of its four
singleton streams for three returned rows. Runtime continues to use singleton requests.

Qatar inline trip objects had no segments; bounded Get Trips supplied complete segments for the
same business trip IDs. The development policy therefore chooses summary plus at most two detail
calls. Qatar's raw zero taxes and positive seat numbers remain preserved, while normalized fees
and seat adequacy remain unknown under the source's documented limitations.

The cash campaign made **three live calls**: two successful responses (six and four itineraries)
and one structured upstream `SCHEMA_DRIFT`. It stopped without retries or later cash calls. The
[capture record](../provider-feasibility/2026-09-22-provider-capabilities.md) explains local
pre-network failures, the declared ceilings, source contracts, and every unattempted contrast.

The final joint replay summary (historical; see the [current corpus](../../evidence/provider-stage/saved-searches/README.md))
records **four award summaries and four cash observations**, two replayed transport calls,
and **25 coverage units: three completed, 22 omitted**. It used the current mixed-intent trace,
one captured search per provider, and an explicit zero-detail budget. It made no live call.
The artifact includes its caller bundle, exact tape, and typed result. The earlier joint-replay
directory is an explicitly superseded intermediate development artifact.
Re-running the final CLI replay into a temporary directory reproduced the saved result byte for
byte, with the expected partial exit code 1 and zero live calls.

All five saved trace inputs were deterministically recompiled with the current compiler, with
unchanged mandatory airport/date/cabin/traveler signatures; their original legacy exports and
the migration mapping remain recorded. No model call was made. The independent graph audit
covered every logical/use/relationship/dependency under limited and progressive budgets for
Japan, India, and exact-airport traces.

Final evidence checks: both capture scripts passed Python compilation; `git diff --check` passed;
120 changed/untracked files were checked against configured credential values with zero matches.
No credentials were added to files. A discovery-agent search did expose an existing OpenAI key
in tool output; the owner was informed and advised to rotate it. That incident is separate from
the credential-free checked-in evidence.

## Remaining acceptance gates and limits

- The exact fresh, combined two-provider live executor task is **unmet**. Combining live-origin
  captures in replay is not a substitute for that claim. The cash schema-drift stop remains in
  force for this session; the Japan/domestic/traveler/date-line/sparse cash contrasts were not run.
- Account-specific remaining quota was not observed. The explicit, adjustable
  `data/provider_capabilities/provider-stage-development-v1.json` values are conservative
  development choices supported by capture sizes/work, not measured account ceilings.
- The rectangle experiment passed for its sampled case, but runtime batching is deliberately
  disabled. Singletons avoid attributing a returned pair to unrelated logical queries.
- No provider reliability, bookability, owner stage qualification, journey assembly, ranking,
  redemption value, or recommendation claim follows from this work.

The owner-authorized local implementation is complete for this declared boundary. Provider Stage
is not marked owner-complete while the live gate and remaining capture evidence are open.

## Owner interpretation

<!-- Owner: record your interpretation and the next cut after reviewing implementation evidence. -->

## 2026-09-23 follow-up disposition

The owner explicitly reopened the gfly investigation and requested completion of the cash
contrasts and fresh combined live/replay gate. Those engineering gates now pass. A reproduced
empty-price parser failure received a reviewed, versioned local compatibility fix; all five
remaining contrasts succeeded; the combined live task returned four award and four priced cash
observations with byte-identical offline replay. The full graph has three completed and 22
explicitly budget-omitted coverage units. The earlier stop and unmet-gate statements above are
historical, preserved for traceability. See the
[follow-up record](2026-09-23-gfly-investigation-and-live-gates.md) for exact receipts, limits,
verification, and remaining unknowns. Owner stage acceptance was unclaimed at this
follow-up point. The owner subsequently accepted the declared Provider Stage boundary on
2026-09-23; see the [closeout](../handoffs/2026-09-23-provider-stage-closeout.md).
