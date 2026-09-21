# 2026-09-19: Milestone 2C deterministic search-strategy compiler

> **Historical implementation record.** On 2026-09-20 the owner approved a provider-neutral
> correction that removed capability binding and the provisional 31/24/128/4,000 allocation
> controls. The measurements below remain accurate for the original implementation and diagnostics,
> but their budget outcomes are not the active compiler contract. See the
> [revision build log](2026-09-20-m2c-provider-neutral-revision.md) and
> [ADR 0021 amendment](../adr/0021-deterministic-search-strategy-compilation.md#2026-09-20-amendment-provider-neutral-compilation-and-structural-safety).

## Authorization and boundary

The owner authorized Milestone 2C implementation after reviewing the detailed
[plan](../handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md). The owner explicitly chose
an in-place replacement: there is one current compiler contract and no V1 compatibility path.
Milestone 2A remains diagnostic-only and Milestone 2B remains closed.

The implemented stage is a deterministic, provider-neutral compiler. It consumes a frozen
`EffectiveRequest`, an explicit endpoint source, the authentic replayable 2B discovery record, the
catalog, capability evidence, and versioned policies. It makes no additional model call and no
travel-provider call. The integrated live diagnostic calls only the request-understanding, endpoint
selection, and gateway-proposal models; it does not call Seats.aero or another inventory provider.

## Implementation

The in-place `plan_searches` boundary now produces a `CompiledSearchPlan` with:

- complete mandatory selected-origin × selected-destination coverage or a typed overflow failure;
- origin access, destination access, and typed scoped-hub supplemental hypotheses;
- one semantic logical-query ledger with many-to-many strategy provenance;
- original-window and bounded later-component date derivations with query-origin timezones;
- explicit positioning, separate-ticket, complete-journey, and deferred-constraint obligations;
- deterministic balanced allocation under the selected 31/100/24/128/4,000 limits;
- exact endpoint, catalog, policy, capability, gateway-replay, and compilation bindings; and
- relationship dispositions and recomputable budget/coverage receipts.

The active route-topology/manual-cash planner branches and old 25/40/1,400 limits were retired. The
compiler does not create route-evidenced `ExplicitPathHypothesis` records from unverified 2B
hypotheses. Provider request batching remains a downstream projection from pair-level logical
coverage.

The execution handoff now checks session/revision, the effective-request digest, and a trusted
caller-computed compilation-binding digest. A changed catalog, capability, policy, endpoint source,
or gateway record therefore makes a plan stale before provider execution.

## Independent architecture review and fixes

The first independent review found that the initial implementation accepted several internally
rehashable forgeries and lost provenance in nontrivial hub scopes. The compiler and contracts were
corrected before stage evidence was accepted:

- all plan/query/strategy/use/support/derivation/dependency and compilation-binding identities use
  recursive canonical JSON with explicit identity versions;
- logical-query identity excludes provenance and precision metadata while retaining complete search
  semantics;
- plan validation independently recomputes mandatory coverage, query endpoints, component date
  rules, graph completeness, positioning dependencies, obligations, budgets, reuse, and dispositions;
- original accepted 2B scope indices and exact original-pair access relationships are retained;
- mixed direct/geographic endpoint sources preserve per-projection source identity;
- generated cabin filters are capability-checked; and
- an M2A or reviewed mapping record cannot choose among ambiguous catalog entities. Independent
  grounding or clarification must first produce one canonical entity.

The final stable architecture probe compiled a synthetic access-plus-hub plan and rejected six
rehashed semantic attacks, including a forged hub component endpoint, missing bundle use,
removed dependencies, capability drift, an extra admitted disposition, and an exceeded successful
budget. No core blocker remained in that review.

## Offline verification

The implementation gate recorded:

```text
113 passed
```

for the focused integration set, and:

```text
483 passed, 99 skipped
```

for the full repository test run. Scoped Ruff and mypy checks for the replacement compiler,
contracts, handoff, evaluator, and migrated tests passed. `git diff --check` also passed at the
implementation boundary.

These results establish deterministic mechanical behavior for the declared fixtures. They do not
qualify M2A semantics, 2B candidate usefulness, provider compatibility, returned itineraries, or
traveler-facing recommendations.

## Model-only integrated diagnostic

Before the full casebook, an intentionally partial live smoke wrote an uncommitted private artifact
at `/tmp/search-planning-live-smoke.json`. Its one `united_states_to_japan` trial reserved five
model calls, attempted four, completed once, and recorded no error. It bound two M2A projections;
M2B returned `success_nonempty` with 40 accepted relationships; M2C returned `REDUCED_COVERAGE`
with all 40 mandatory pairs complete, 24 admitted supplements, 16 budget omissions, 50 unique
queries, and 162 query-date-days. Reloaded same-record replay was equal and the execution handoff
was `CURRENT`. `mechanically_completed=false` reflects the intentional partial smoke
(`full_run=false`), not a failed trajectory. No provider call was made.

The [two-trial first full run](../../evals/search_planning_live/baseline/2026-09-19-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v1-2-trials.json)
used six declared trajectories and a maximum of 56 model calls. It
recorded 12 case-trials, 40 attempted calls, 10 completed trajectories, two errors, 12/12 trace
reconciliations, and eight same-record deterministic replays. Both errors were the Paris city case.
The catalog independently grounded “Paris” as ambiguous; the supplied endpoint-selection record was
correctly refused as disambiguation authority. This was a transparent input/evidence failure, not a
compiler fallback and not a provider failure. The run was therefore not mechanically complete.

The case was corrected to use unambiguous Lyon while preserving the intended city-to-country and
explicit positioning-refusal coverage. The corrected run is a new diagnostic rather than a rewrite
of the Paris evidence.

The [corrected Lyon run](../../evals/search_planning_live/baseline/2026-09-19-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v1-lyon-fix-2-trials.json)
completed all 12 case-trials with 56 planned and 40 attempted model calls, zero errors, 12/12 trace
reconciliations, and 10 equal same-record replays after reload with `CURRENT` handoffs. Its two
cash-only trials stopped upstream as expected. The public redaction scan found zero sensitive paths,
and the run was mechanically complete. The 40 private call records reported 63,589 input tokens,
23,697 output tokens, and 87,286 total tokens. Model-call latency totaled 190.279 seconds and
averaged 4.757 seconds; full-trajectory latency totaled 324.521 seconds and averaged 27.043 seconds.
SFO–NRT planned one mandatory pair in each trial;
United States–Japan preserved all 40 mandatory pairs and admitted 24 supplements with reduced
coverage in each trial; Lyon–France used the 2B policy skip and produced mandatory-only plans with
eight pairs each; United States–India preserved all 60 mandatory pairs and admitted 24 supplements
with reduced coverage in each trial. The clarified United States–Japan case preserved 40 mandatory
pairs in both trials: trial one admitted 24 supplements and omitted 28, while trial two admitted 10
and omitted none.

No provider call, provider payload, provider response, availability result, fare, or itinerary was
produced in either diagnostic. Independent human semantic qualification is not claimed.

## Resulting stage status

Milestone 2C runtime compilation is implemented and offline verified for its declared evidence and
policy boundary. The model-only integrated diagnostic is supporting development evidence; it does
not adopt M2A, reopen 2B, qualify the involved models, or establish provider/product coverage.
Provider execution, result validation, incomplete-component labeling, and any owner-facing shortlist
remain downstream work.
