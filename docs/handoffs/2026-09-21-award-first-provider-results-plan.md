# Provider Stage: execution and structured results

Date: 2026-09-21. Revised: 2026-09-23. Status: **owner-complete for the declared ProviderResultSet boundary on 2026-09-23.**

The [Provider Stage closeout](2026-09-23-provider-stage-closeout.md) records the accepted
boundary, evidence, and remaining limits.

Implementation and verification evidence is tracked in the
[2026-09-22 build log](../build-log/2026-09-22-provider-stage-implementation.md) and
[2026-09-23 follow-up](../build-log/2026-09-23-gfly-investigation-and-live-gates.md).

## Objective and boundary

Consume the current frozen `EffectiveRequest` and complete `CompiledSearchPlan`; execute bounded
Seats.aero award and `gfly` cash searches; capture, parse, normalize, and conservatively deduplicate
the results into a typed, replayable `ProviderResultSet` that a later ranking and output generation
stage can use directly.

```text
frozen EffectiveRequest + current CompiledSearchPlan
    -> capability-aware ProviderExecutionPlan and deterministic activation
    -> Seats.aero and gfly requests with captured responses
    -> source-attributed parsed and normalized observations
    -> conservative deduplication, validation findings, and coverage receipts
    -> typed replayable ProviderResultSet
    -> later ranking and output generation stage
```

The `ProviderResultSet` binds request, plan, provider capability, execution policy, and run
identities. It retains award availability summaries and, where details support them, provider-returned
itineraries; direct endpoint cash observations and relevant access/egress cash observations; distinct
offers and raw/sanitized evidence references; exact transport-to-logical-query/strategy attribution;
field-level unknowns; validation findings; and scheduled, attempted, completed, empty, partial,
failed, omitted, and coverage state. An absent pair in an interrupted page stream is not an empty
result. Stale request or plan identity prevents execution and attachment.

This stage does not modify request/session state, M2C identity, or the full compiled graph. It does
not reinterpret free text, infer provider routes or bookability, assemble mixed journeys, rank,
calculate redemption value, explain options, or generate user-facing recommendations. The later
stage owns intact-award candidate admission, bounded cash-access/award and award/cash-egress
assembly, ranking, direct-cash presentation, and output generation under ADR 0022's award-first
product policy. ADR 0016 still governs the active runtime.

## Capability, budgeting, and activation

Accept a reviewed Seats.aero operation and pinned `gfly` behavior with request, response, freshness,
error, and evidence semantics before implementation. Keep provider capabilities and resource limits
downstream from M2C. The M2C 100 selected-origin × destination-pair guard is structural, not a
provider budget. Its retired 31-day, 24-relationship, 128-query, and 4,000 query-date-day limits
must not return as execution admission rules.

Define adjustable, separate award and cash budgets for requests, attempts, pages, detail calls,
returned rows, bytes, and elapsed time. Choose numerical values from representative captures and
owner account limits rather than inheriting planning limits. Preserve the entire M2C graph and
account for every unexecuted logical unit. A simple list-prefix cut is not an execution policy.

Run mandatory endpoint award work first, then a bounded direct endpoint cash sample, then fair
progressive supplemental award work. Deterministic selection uses shared-query reuse, marginal
endpoint/strategy coverage, completion of atomic strategy bundles, provider cost, and fair rotation
across endpoint pairs. Relevant cash access or egress queries may activate only when an observed
award result and an existing M2C positioning dependency justify them. `repositioning_allowed=false`
excludes dependent positioning work. No model chooses provider actions. Hard stops cover stale
handoff, exhausted budget, provider block/rate limit, and schema drift; failures produce explicit
partial/omitted receipts. Do not evade blocking or retry without bound.

Seats.aero accepts multiple origins and destinations per request, so exact airport rectangles can
save calls. A rectangle is eligible only if every cross-product pair is authorized by the compiled
work and shares compatible dates, filters, cabin, and activation scope. Gate batching on a complete
2 × 2-versus-four-singletons acceptance experiment that checks attribution and pair coverage; the
provider does not promise that an unreturned pair was exhaustively evaluated. Capture all pages to
claim a completed stream; track duplicate IDs across pages. Compare inline `include_trips` with
summary plus bounded `Get Trips` before fixing detail retrieval. Keep availability summaries and
complete itineraries as separate evidence levels.

`gfly` remains one pair/date per acquisition in the first slice. Its local `--limit` truncates
displayed results after fetching and is not an upstream work budget. Capture the complete response
once per selected pair/date, with no automatic retry on blocking or schema drift. Direct cash
queries derive from original endpoint probes; do not mirror every award query-date-day into cash.

## Observation contract

Record source/backend/version, exact query and logical uses, airport sequence, local times and
catalog-derived timezone instants, carriers, duration/stops where supplied, requested traveler and
cabin scope, retrieval time, immutable sanitized evidence digest, and raw field state. Award records
retain program, points, taxes/fees, cabin, and seats independently. Cash records retain amount,
currency, and per-traveler/party/unknown price scope. A requested traveler count or cabin is not
proof of returned scope; zero, absent, null, and unknown stay distinct. In particular, Qatar
Seats.aero results may omit taxes/fees and seat evidence; never convert absence to zero.

Deduplicate exact transport repeats conservatively while preserving distinct programs, cabins,
points, fees, seats, price scopes, observation times, and evidence. Validation checks parseability,
chronology, airport attribution, request scope, and supported fields, and records unresolved facts.
It does not turn a multi-component search hypothesis into a validated journey.

## Pre-implementation capture campaign

Use actual airports and dates from active Intent-to-Search-Plan end-to-end traces to select common
cases, then add controlled provider edge cases. Predeclare the queries, fixed provider versions,
limits, stop conditions, and expected evidence before calls. Preserve complete sanitized responses,
metadata, pagination, errors, and per-call receipts as immutable replay fixtures; avoid deliberate
blocking. Live captures are development evidence, not provider qualification.

The core trace-derived set includes `ready_exact_airports` (SFO–BKK, exact outbound date, business,
two travelers), `mixed_award_cash_eligible` (SFO–BKK, exact outbound date), `ready_whole_month`
(SFO–BKK, May 2027), and the high-fanout `united_states_to_japan` planning trace. Use the actual
compiled airport sets, dates, and logical uses from each saved trace for Seats.aero; project
corresponding selected endpoint pair/dates into `gfly` under its separate budget. These cases cover
ordinary exact searches, mixed intent, a wide date window, and multiple selected airports. Record
which trace supplied every capture so convenient hand-picked pairs cannot replace the actual
upstream distribution.

Add a Qatar-source/DOH branch from `united_states_to_india`: JFK–DOH on May 12–14, 2027 and
DOH–BOM on May 11–16, 2027, business, source `qatar`. Capture the provider's actual tax and seat
field states, including absent/unknown values. Do not label these as confirmed flights or assume
that Seats.aero will return inventory on those dates.

For Seats.aero, also compare a complete compatible 2 × 2 rectangle with four singletons; test a
dense multi-airport/multi-day paginated search, an apparently absent batched pair against a
singleton, detail retrieval modes, program differences, missing taxes/seats/trips, and date-line or
window-boundary behavior. For `gfly`, add a small independent contrast set for dense domestic,
international/date-line, one-versus-two travelers, complex connection, and sparse/non-US behavior
after the trace-derived captures. One full JSON capture per pair/date, default backend and throttle,
fixed currency, and no automatic retry. Use synthetic offline fixtures for failures that should
not be induced live.

## Completion evidence and sequence

1. Record reviewed provider capability contracts and representative immutable sanitized success,
   empty/partial, failure, pagination, and schema-drift fixtures for both adapters as applicable.
2. Offline tests prove request mapping, rectangle safety, pagination accounting, attribution,
   normalization, conservative deduplication, price scope, timezones, traveler/cabin treatment,
   stale-identity blocking, and finite resource/coverage accounting.
3. Replay the trace-derived and edge-case fixture campaign through the typed `ProviderResultSet`;
   independently review whether every executed and omitted M2C logical unit is accounted for.
4. Run a bounded owner-relevant live task that reaches award observations and a direct cash
   observation, with truthful empty/partial behavior and explicit unsupported evidence. Compare
   provider effort, coverage, and data quality with the planned budget. One task is development
   evidence, not broad provider reliability or product qualification.

First capture and review representative responses; choose budget numbers and detail strategy from
that evidence; implement adapters and deterministic scheduling behind fake transports; then run
offline and bounded live gates. Ranking/output usefulness and a positive actionable recommendation
are completion gates for the later stage and overall workflow, not this `ProviderResultSet` stage.
