# 2026-09-12: Search-planning design review

## Work attempted

Prepared a design-only, implementation-ready plan for the active
ClarificationSession(ready).effective_request -> SearchPlan stage. The design records the planning
boundary, repository findings, deterministic architecture, reviewed knowledge snapshot, typed
outcomes, constraint/date/budget policy, offline evaluation, and incremental implementation sequence.

## Evidence inspected

- EffectiveRequest, ClarificationSession, projection, reducer, readiness, location-preservation,
  and initial semantic workflow contracts.
- Active one-way ADRs, the search-planning boundary brief, provider-intake evidence, active
  fixtures/tests, and relevant workbook background.
- Four independent read-only reviews: upstream contract, fixtures/constraints, knowledge/provider
  evidence, and architecture.

## Files changed

- docs/handoffs/2026-09-12-search-planning-design.md
- docs/handoffs/2026-09-10-search-plan-design-stage.md
- docs/workboard.md

## Observed design gaps retained for owner review

- Upstream READY permits optional unknowns, while a literal no-unknown planner gate would reject
  valid ready sessions.
- hard_constraints is arbitrary text with no canonical vocabulary or per-constraint provenance.
- No source-backed operational airport/group/route snapshot exists yet.
- The existing date contract does not establish an airport-local planning convention.

## Capability review and owner policy closure

Three independent read-only reviews inspected the local Seats.aero reference, the active request
contract, fixtures, and the design. They established Cached Search as the v1 capability target:
only its origin and destination airport lists are provider-required; dates and cabin are optional;
it has no traveler/seat-count filter. Product admission therefore remains unchanged (origin,
destination, travelers, bounded outbound window, award mode, and no conflicts), while resolved
airport lists form the separate provider-executability check. Travelers carry as a later
result-validation obligation.

The reviewed provider-filter enum is limited to cabin availability, direct-flight availability,
carrier involvement, redemption-program membership, and minimum reported cabin-distance
percentage. The current arbitrary `hard_constraints` values cannot safely populate it, so all such
text remains deferred verbatim until a separately scoped typed upstream contract exists. The first
actual component uses origin-local dates and later components use the explicit start - 1 / end + 2
exploratory envelope.

The local cached-search page declares `updatedAt: 2025-04-23`, despite a 2026-09-08 repository
documentation capture. Known ambiguities—date inclusivity/timezone, carrier match strength,
multiple-cabin semantics, and a singular/plural cabin inconsistency—are recorded for later adapter
acceptance checks. No provider call occurred.

## Post-design completion map

Added a durable checklist to the design record separating: planner implementation and offline
qualification; initial declared knowledge coverage; the longer-lived curated knowledge-base
expansion; typed upstream constraint work needed before hard requirements can influence provider
filters; and later provider-execution work that remains outside planning. This corrects the
potentially misleading implication that a small initial knowledge snapshot or deferred free-text
constraints is the endpoint of a broadly useful planning product.

## Deep architecture review follow-up

An independent deep architecture review found the boundary sound but identified implementation-ready
contract gaps. The design now distinguishes user requirements from planner-structural filters,
including a direct-flight summary prefilter plus mandatory trip validation for explicit physical
components. It separates evidence-backed location-to-airport relations from product airport
selection policy; names the absence of an operational airport/topology source; adds deterministic
snapshot retrieval interfaces; moves EffectiveRequest digest computation into the planner; records
field-level provenance limits; repairs payment-pattern, outcome, and budget semantics; and marks
the 31-day input window as a provisional owner policy. The review ran 15 focused existing contract
tests successfully, made no provider/network calls, and changed no production code.

## Verification

- Documentation-only session: no production code, provider client, test, dataset, dependency, or
  live provider call was added.
- An independent architecture review ran five focused existing contract/scope/airport-preservation
  tests successfully; two historical temporal-compiler tests were skipped by their current-suite
  markers. These were inspection checks, not search-planning implementation qualification.
- git diff --check — passed.

## Implemented offline qualification and caller handoff

Implemented the five planned offline search-planning increments. The deterministic planner now
has a reviewed local seed snapshot, Cached-Search capability record, endpoint and explicit-path
planning, temporal/budget/payment obligations, canonical plan identity, and a pure caller-side
stale-plan check. No provider adapter, request payload, network call, response parser, or cash
search was added.

Added `evals/search_planning/cases_v1.json` and the `award-search-planning-eval` command. The
strict JSON corpus contains ten fixture-only cases covering Japan and NYC groups, explicit SFO,
unsupported/ambiguous/missing-policy/stale knowledge, a visibly synthetic directed path, country
arrival without invented onward travel, cabin/traveler/deferred-constraint obligations,
repositioning receipt, cash-first annotations, budget exhaustion, and reordered-record canonical
output. Each case records a canonical complete-result SHA-256; the corpus preflight verifies its
declared default snapshot and capability identities.

Objective verification completed on 2026-09-12:

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.search_planning_eval` — 10/10 exact gate.
- `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_search_planning_evaluation.py` — 4 passed.
- Ruff and mypy for the planner, evaluator, handoff, CLI, and focused test scope — passed.

This is fixture qualification for declared local coverage only. Operational route/topology evidence,
broader curated knowledge coverage, typed upstream constraints, provider semantic acceptance, and
provider execution remain separately scoped work.

## Final qualification-gate hardening

The fixture-only golden gate now pins canonical SHA-256 values for the default knowledge snapshot,
Cached-Search capability record/version, and default planning policy. Preflight verifies those
records plus the resolved repository-local Cached-Search reference bytes against the capability
record's source SHA-256; a fixture-controlled source path cannot escape the checkout. The public
artifact emits the input identities and hashes. Its executable coverage matrix maps every required
end-to-end behavior tag to named case IDs, rejects missing categories and self-referential canonical
peers, and distinguishes its fixture coverage from focused unit-only adversarial checks.

`PlanHandoffCheck` now derives and validates both `status` and serialized `executable` from its
identity fields, with session/revision staleness taking precedence over a request-digest mismatch.
Tests reject forged status and executable values, malformed corpus pins, unsafe capability paths,
and altered source hashes. No provider client, credential, network call, response parser, or cash
search was added.

Objective verification completed on 2026-09-12:

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.search_planning_eval` — 10/10 exact gate.
- `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_search_planning_evaluation.py` — 12 passed.
- `PYTHONPATH=src .venv/bin/pytest -q` — 372 passed, 99 skipped. The previously reported 364
  passing count predated the eight final-gate tests added here.
- `PYTHONPATH=src .venv/bin/ruff check .` — passed repository-wide.
- Scoped mypy over the final-gate planner/evaluator/handoff/test files — passed.
- `PYTHONPATH=src .venv/bin/mypy src tests` — 266 errors in unrelated pre-existing
  intent/clarification source and test files; the scoped final-gate files have no mypy errors.

## Final truthfulness hardening

Added the tenth fixture-only golden case, `optional_path_budget_omission`, and the matching
`optional_path_budget_degradation` coverage tag. It sets the optional path-candidate exploration
budget to zero and asserts `ReducedCoverage` while retaining all three required endpoint probes
and all six budget receipts, including an observed and allowed path-candidate count of zero. The
case pins result SHA-256 `e34d8953cafc96288d43627aa4c58c871d5eb80dfb346e6c4ab581a15ee06337`.

Updated the design, stage brief, workboard, and project-state wording to identify the planner as
implemented and fixture-qualified for declared local coverage. Historical design-only wording
remains historical; provider execution is explicitly the next separately scoped stage.

Objective verification completed on 2026-09-12:

- `PYTHONPATH=src .venv/bin/python -m award_agent.cli.search_planning_eval` — 10/10 exact gate.
- Focused search-planning tests — 100 passed.
- `PYTHONPATH=src .venv/bin/pytest -q` — 373 passed, 99 skipped.
- `PYTHONPATH=src .venv/bin/ruff check .` — passed.
- Scoped mypy over planner/evaluator/CLI/handoff/search-planning tests — passed.
- `git diff --check` — passed.
