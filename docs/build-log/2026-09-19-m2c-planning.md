# 2026-09-19: Milestone 2C planning opened

## Authorization and boundary

The owner explicitly opened Milestone 2C planning and requested an implementation-ready
handoff grounded in the architecture review and current code. The owner excluded runtime
implementation and live model/provider calls. A subsequent instruction emphasized parent
orchestration and substantive subagent work.

The [plan](../handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md) contains recommendations,
not approved runtime changes. Milestone 2A remains diagnostic-only; 2B remains owner-closed.
The external workbook was read for product goals and was not edited.

## Work and ownership

- A planner investigator traced current contracts, policy defaults, endpoint-selection integration,
  handoff checks, and tests.
- A gateway investigator traced replay, source relationship identity, access dependencies,
  failure dispositions, advisories, resource use, and diagnostic coverage.
- An architect resolved the proposed contract and compiler algorithms against those findings.
- An implementer drafted the detailed documentation handoff, without runtime changes.
- A separate architect reviewed the draft for contract gaps and contradictory examples; findings
  included access-relationship identity, budget-policy precedence, and replay-artifact prerequisites.
- The parent read the source-of-truth documents and relevant code, challenged and integrated
  findings, updated planning status, and verified the documentation.

The repository already contained modified and untracked review/planning documents when this
session began. Those changes were preserved. This session changes only the new plan, this log,
and narrow planning-status/disposition entries in `AGENTS.md`, `docs/project-state.md`,
`docs/workboard.md`, the milestone roadmap, and `DEFERRED.md`.

## Observed evidence

- Existing `SearchPlan` requires exactly one endpoint award item per probe; physical path items
  require directed route evidence and structural direct-flight filters. It cannot accept new
  unverified gateway components without a distinct contract.
- Existing v1 repositioning behavior is deliberately `enabled_not_consumed_v1`. Suppression
  after explicit refusal is a proposed policy change, not a correction to an implementation bug.
- Existing gateway replay checks the full proposal and bound identities, but the new compiler
  must additionally bind those inputs to its frozen request and endpoint-selection records.
- Hub relationship identity is a typed reference pair. Its original-endpoint support comes
  from those particular references, not the union of every reference in the scope.
- Replay eagerly materializes finite scope products before compiler admission. Output caps
  cannot be described as bounds on that earlier work. No saturation performance measurement
  was performed in this session.
- The final v6 development diagnostic did not exercise access references inside hub scopes;
  the plan therefore requires synthetic offline coverage. Prior evidence remains historical
  evidence for its declared boundary, not 2C qualification.
- The parent challenged a proposed retry pass for budget-omitted bundles. For admitted query set
  `A` and candidate bundle `B`, admission requires `cost(A union B) <= cap`; `A` only grows and
  unique-query/date costs are nonnegative. A failed budget test cannot later pass. The architect
  accepted the correction and removed reconsideration, retaining single-pass atomic admission.
- `git ls-files evals/gateway_discovery` confirmed that the public casebooks and diagnostic summaries
  are tracked, while full immutable records are local ignored trace sidecars. The plan distinguishes
  local original-record replay from newly prepared portable fixtures; redaction or reconstruction
  must not be represented as preserving an original record's digest.

## Commands and verification

Repository inspection used `rg`, `cat`, and `sed`; initial state was recorded with
`git status --short`. The parent ran:

```sh
.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_gateway_discovery.py tests/unit/test_airport_selection_foundation.py
```

Result: **107 passed in 1.09s**. This is current baseline regression evidence, not evidence
that proposed 2C behavior exists. No live model/provider calls were run. Future commands and
acceptance criteria in the handoff are explicitly prospective.

Final documentation validation:

- `git diff --check` passed.
- A local Markdown-target check across the plan, log, and five planning-status/register files
  resolved **77 links with no missing targets**.
- The new plan/log have no trailing whitespace. The required A–F sections and concrete
  query-use, derivation, dependency, binding, allocation, and offline-mode contracts are present.
- The parent resolved the final review findings: explicit single-pass round-robin pseudocode;
  stable use/derivation/dependency IDs; unknown separate-ticket tolerance; actual endpoint-source
  records and compiler inputs; and neutral reviewed-selection projections. The later owner decision
  permits an explicit reviewed-mapping enum in the replacement contract.
- A bounded architect follow-up confirmed the neutral projection and combined catalog repository
  protocol fix. All required agent reports were collected and the identified contract gaps were
  resolved in the handoff. Owner policy decisions remain explicitly open.

No runtime source, tests, prompts, catalog, provider integration, or historical evidence was changed.
The future 2C test/evaluation commands were specified, not run or claimed passing.

## Owner conclusions and next cut

Recorded owner decision: open planning, preserve all-selected-endpoint coverage with explicit
overflow, and stop before runtime implementation or live calls.

Acceptance/rejection of the plan's remaining contract/policy defaults: **not yet recorded**. The
owner delegated the numerical compiler-limit decision; the recorded 31/100/24/128/4,000 values
are selected for implementation planning but remain unqualified until the specified offline tests.
The owner also explicitly declined V1 compatibility. The plan now calls for one in-place replacement
of the current plan, policy, handoff, callers, and current fixtures; historical evidence remains
preserved, while obsolete runtime paths and compatibility adapters are not retained.
Permission to implement: **not yet given in this session**.
Provider pilot opening and final next cut: **owner decision pending**.

## Follow-up: Cached Search list batching

The owner pointed out the saved provider documentation's origin/destination list parameters and
requested subagent investigation and parent design reconsideration. Two investigators checked the
saved provider contract and existing planner/tests; an architect challenged the design. All were
read-only. The parent integrated [Section G](../handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md#g-cached-search-batching-reconsideration)
into the existing plan rather than creating another competing handoff.

Findings and recommended changes:

- Saved docs support multiple airports on both sides, but provide no numerical airport cap or
  explicit per-pair completion guarantee. The saved live spike was singleton-only.
- Pair-level logical coverage never required pair-at-a-time HTTP calls. Specify an exact grouped
  request projection with pair-to-query provenance and separate execution cohorts.
- The owner delegated the compiler-limit decision to the parent/architect. Two independent architecture
  passes converged on 31 input days, 100 mandatory pairs, 24 supplemental relationships, 128 total
  unique logical queries, and 4,000 query-date-days. The plan records the derivation and overflow
  cases. These are compiler guardrails, not provider limits. The later in-place replacement decision
  retires the old 25/40/1,400 active limits rather than preserving them behind a second entry point.
- Batch count is nonmonotonic as pairs are added, so it cannot replace additive logical query/date
  costs inside the existing allocator. Keep execution pages/attempts/results separately budgeted.
- Retain per-query dates/timezones and validation, exact sparse-pair coverage, and honest partial
  batch outcomes. Add a catalog-pinned airport directory to the replacement plan boundary.

The parent ran a standalone Python grouping demonstration, with exact-pair/no-overlap assertions:
six compatible pairs formed one modeled batch; three sparse pairs formed two; a synthetic 6×6 set
formed one; completing a 2×2 rectangle reduced two batches to one. The architect independently
checked related cases. These are analytical grouping results under declared compatibility assumptions,
not runtime implementation, an evaluation of the compiler, or provider measurements.

Only the plan, its project-state pointer, and this log changed in this follow-up. No new runtime
tests, live calls, policy adoption, provider integration, or external workbook edits occurred.
Follow-up documentation verification: `git diff --check` passed; 28 local Markdown targets across
the three touched documents resolved, with no trailing whitespace in those documents.

## Follow-up: in-place planner replacement

The owner explicitly rejected V1 compatibility because the repository is development-only and has
no deployed or external planner consumer. A bounded architect review inspected the active planner,
contracts, policy, handoff, evaluator, selector integration, and affected tests. It agreed that a
parallel V1/V2 architecture would preserve unused machinery rather than a real dependency.

The plan now specifies one current `CompiledSearchPlan`, one evolved `plan_searches` boundary, one
current `PlanningPolicy`, and one handoff validator. Implementation should migrate all in-repository
callers and current fixtures, retire obsolete route-expansion and old limit paths, and classify old
assertions as retained, revised, or retired. Historical reports and upstream 2A/2B evidence remain
unchanged; semantic invariants such as complete mandatory coverage, evidence replay, deterministic
identity, and the route-evidenced meaning of `ExplicitPathHypothesis` remain protected.

This was a planning/documentation correction only. No runtime source, tests, fixtures, live calls,
provider integration, or external workbook content changed. The architect reported no need for
further escalation; exact dead-code deletion breadth should be determined during implementation by
repository reference searches.

Post-correction documentation verification: `git diff --check` passed; contract assertions confirmed
one plan, one entry point, one policy, the selected limits, and absence of stale V2/byte-compatibility
claims; 30 local Markdown targets across the updated plan/status records resolved with no missing
files. Runtime tests were not rerun because this correction changed documentation only.
