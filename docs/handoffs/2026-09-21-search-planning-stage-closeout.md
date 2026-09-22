# Search-planning stage closeout

- Status: Owner-complete
- Date: 2026-09-21
- Boundary: `EffectiveRequest -> CompiledSearchPlan`

## Owner decision

The owner marked the search-planning stage complete after monitoring the builds and reviewing the
results. Milestones 1, 2A, 2B, and 2C are implemented and owner-qualified for their declared
planning boundaries. Milestone 0 is retired and has no executable compatibility path.

## Completed boundary

The stage accepts a frozen, supported one-way award `EffectiveRequest`; uses the reviewed local
catalog; preserves explicit or uniquely named airports as direct singletons; uses adopted M2A
model-proposed records for exactly resolved geographic endpoints; consumes bounded M2B gateway
hypotheses; and deterministically emits a provider-neutral `CompiledSearchPlan` with replay,
identity, provenance, obligations, and structural-budget evidence.

M2C makes no model or provider call. The stage neither reparses the request nor mutates upstream
session state. The official geographic endpoint source is M2A replay; its selections retain
model-proposed provenance rather than becoming catalog facts. M2B candidates remain unverified
search hypotheses rather than route or connectivity facts.

## Evidence and qualification boundary

The completed milestones are owner-monitored, owner-reviewed, and owner-qualified for their
declared planning scopes. This closeout does not claim independent external or holdout
corroboration, provider execution or availability, schedule or route verification, a valid or
bookable itinerary, product behavior, ranking, or recommendation quality.

The supporting records remain:

- ADRs 0018, 0019, 0020, 0021, and 0023;
- the M1 catalog publication and serving evidence;
- the M2A active-policy diagnostic and deterministic validation tests;
- the M2B prompt-v6/casebook-v3 diagnostic and closeout;
- the M2C implementation and provider-neutral revision records; and
- the 2026-09-21 M2A adoption/M0 retirement implementation record.

## Downstream handoff

The next stage is provider/result execution under ADR 0022. It consumes the frozen
`CompiledSearchPlan` and owns provider capability acceptance, request projection, execution budgets,
source-attributed observations, empty/partial/error behavior, result validation, and later ranking
or recommendation claims. Those are downstream responsibilities, not unfinished search-planning
work.

Reopen search planning only for a demonstrated planning-boundary defect or an explicit owner
decision. Provider limitations or empty provider results do not by themselves invalidate this
stage's completed provider-neutral contract.
