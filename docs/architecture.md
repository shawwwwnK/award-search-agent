# Architecture Overview

## Eventual workflow

`Raw request -> Parse request -> Clarify constraints -> Plan searches -> Run provider tools -> Normalize and validate -> Rank candidates -> Explain recommendations`

## Current request-understanding boundary

The current slice stops after request interpretation and clarification selection. It uses strict
non-temporal Pass 1 plus a date-free opaque temporal selector. Deterministic code scans temporal
wording, builds and validates candidate catalogs, resolves holiday anchors, restores only selected
local candidates, compiles the canonical relation graph, evaluates calendar windows, and applies
conflict and clarification policy. Sequential model-authored temporal resolution is retired by ADR
0010.

This boundary is complete and frozen. Luna is the configured model for both model boundaries in
the qualified implementation: non-temporal Pass 1 and the opaque temporal selector. Sequential
two-pass resolution is retired from the live code path. The final qualification record is the
three-trial selector-only run with 47/48 passes (97.92%), zero errors, and one documented
clarification miss. Further intent changes require an explicit owner decision to reopen this
slice.

## Responsibility table

| Responsibility | Current owner | Reason |
| --- | --- | --- |
| Coarse semantic extraction | first model pass | Natural-language interpretation is the core semantic task. |
| Ambiguity identification | model | Ambiguity detection depends on language understanding and uncertainty recognition. |
| Explicit airport-code preservation | deterministic code | A model-classified verbatim IATA code is already a stable downstream identifier. |
| Holiday calendar dates | `HolidayDateProvider` | Nager.Holidays API v4 supplies U.S. federal-holiday anchors. |
| Temporal candidate selection | selector model | It may select only deterministic, opaque local candidates, including explicit unresolved choices. |
| Temporal relation construction | deterministic compiler | Candidate relations, targets, references, and composition are pre-authored and validated before compilation. |
| Calendar evaluation | deterministic code | Holiday windows, weekends, weekdays, offsets, month portions, durations, and final ranges must be reproducible. |
| Dependency/reference validation | deterministic code | Anchor existence, request-field ordering, and cycles are exact graph invariants. |
| Schema validation | deterministic code | Contract enforcement should not depend on model behavior. |
| Evidence span resolution | deterministic code | Quotes must match the immutable request exactly; offsets and ambiguity handling must be reproducible. |
| Evidence, anchor, and symbolic-reference catalogs | deterministic code | Stable IDs and allowed membership form the trust boundary between model passes. |
| Claim/evidence sufficiency evaluation | deterministic code | Allowed envelopes and required fragments are fixture-defined correctness rules. |
| Conflict detection | deterministic code | Contradiction checks need explicit, auditable rules. |
| Clarification selection | deterministic policy | Asking at most one focused question should follow stable policy. |
| Point balances and spending budgets | deferred | Excluded from MVP extraction, parsed output, and clarification policy. |
| Search planning | deferred | Outside the current milestone. |
| Travel-provider calls | deferred | Outside the current milestone. |
| Ranking | deferred | Outside the current milestone. |
| Final explanation | deferred | Outside the current milestone. |

## Current request-understanding diagram

```mermaid
flowchart LR
    A["RawRequest + RequestContext"]
    B["NonTemporalExtractionInput: request text only"]
    C["Pass 1: non-temporal fields only"]
    D["Deterministic temporal scan + candidate catalog"]
    E["Date-free opaque selector projection"]
    F["Selector: candidate handles only"]
    J["Private calendar / holiday enrichment"]
    I["Restore + compile + deterministic calendar evaluation"]
    G["ClarificationPolicy"]
    H["ParsedRequest + ClarificationDecision + provenance"]

    A --> B --> C
    A --> D --> E --> F --> I
    A --> J
    C --> H
    J --> I --> G --> H
```

The `RawRequest` context remains inside deterministic orchestration. Neither model boundary sees a
concrete reference date, timezone, resolved anchor boundary, holiday-provider metadata, or inferred
calendar value. The selector sees only supplied local evidence, anchors, candidates, and production
handles. `next month` remains a symbolic whole-calendar-period relation until deterministic
evaluation; `next spring` remains unresolved because no deterministic season policy is approved.

The holiday lookup is only exercised for holiday anchors. Exact-date and month anchors do not call
Nager.Holidays. API failures and invalid responses surface as explicit errors; there is no
hand-coded success fallback. Unit tests inject fake model passes and a fake provider and do not
require network access.

The retained `DateResolutionProposal` in `ParsedRequest` is generated after deterministic graph
evaluation for trace and historical scorer compatibility. The authoritative internal semantic
contract is `TemporalRelationGraph`; no model response authors it.

This diagram describes the completed, frozen request-understanding slice. Downstream search
planning begins after `ClarificationDecision` and is outside this implementation boundary.
