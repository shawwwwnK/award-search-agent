# AGENTS.md

## Project purpose

Build a narrow, measurable award-search workflow that converts vague travel requests into grounded, traceable recommendations.

## Development-only status

This repository and every artifact it currently produces are local development
work. Nothing is deployed, published, or used by external users. Terms such as
"release," "snapshot," and "catalog" describe local versioned artifacts, not
a production rollout or externally consumed service.

Agents may therefore revise, rebuild, replace, or remove local development
artifacts when that is in scope for the owner's request; do not treat a local
artifact change as an operational-impact or deployment decision. For material
changes, preserve traceability through receipts, tests, project-state/build-log
updates, and explicit coverage claims. Do not invent production constraints or
require deployment-style approval merely because an artifact is versioned.

## Living project workbook

The ongoing project-design workbook lives outside this repository at:

`/Users/shawnkang/bots/workbook_formatted.md`

Consult relevant sections when a task depends on:

- product intent;
- workflow scope;
- project principles;
- agent boundaries;
- evaluation philosophy;
- unresolved design questions;
- previously recorded project decisions.

Rules for using the workbook:

- Do not modify it unless explicitly instructed.
- Do not treat blank sections as tasks to complete.
- Do not treat every idea in it as an implementation requirement.
- Read only the sections relevant to the current task when possible.
- Surface material conflicts with current repository documentation.
- More specific, newer repository decisions may intentionally refine older workbook thinking.

## Source-of-truth hierarchy

When instructions appear to conflict, use this hierarchy:

1. The user's current explicit instructions.
2. This repository's `AGENTS.md`.
3. `docs/project-state.md`.
4. Relevant ADRs and implementation contracts.
5. `/Users/shawnkang/bots/workbook_formatted.md`.
6. Older/general project notes.

If a conflict is significant or changes product behavior, report it rather than silently resolving it.

## Current milestone

The search-planning stage is owner-complete as of 2026-09-21. Milestones 1, 2A, 2B, and 2C are
implemented and owner-qualified for their declared planning boundaries, and Milestone 0 is retired.
Provider Stage under amended ADR 0022 is owner-complete as of 2026-09-23 for its declared
typed, replayable `ProviderResultSet` boundary. It consumes the frozen `CompiledSearchPlan`
and must not be described as additional search planning. Ranking Stage M1 matching was opened
and locally implemented on 2026-09-25, and owner-qualified and closed on 2026-09-30 for its
declared matching/validation boundary. See `docs/handoffs/2026-09-30-ranking-m1-closeout.md`. On 2026-09-27 the
owner adopted matching policy m1-v2 (journey-level award cabin accepted when legs are
unreported) and approved recording the gfly provider-returned party echo as returned-traveler
evidence; the 2026-09-27 positioning-permitted live run then produced the first five admitted
mixed journeys. M2 was opened for solution-style design on 2026-10-01; the owner approved
time/cost/premium styles, unified admitted/conditional comparison, explicit heuristic valuation,
and two-or-more-style highlights. Its approved policy and draft contract are in
`docs/handoffs/2026-10-01-ranking-m2-styles-contract.md`. The owner closed Ranking Stage on
2026-10-02 for its declared M1 matching/validation and M2 solution-style boundaries. This
closeout does not establish broader product or provider qualification. Unknown price scope
prevents a complete cost reference in all three saved requests. See
`docs/handoffs/2026-10-02-ranking-stage-closeout.md`,
`docs/build-log/2026-10-02-ranking-stage-closeout.md`,
`docs/build-log/2026-10-01-ranking-m2-implementation.md`, and
`evidence/ranking-stage/m2/README.md`. Weighted overall scoring is not required, and the
Results Stage (previously Output Stage) is owner-opened for design as of 2026-10-02.
See `docs/handoffs/2026-10-02-results-stage-opening.md`; its detailed output contract and
presentation policy remain unsettled, with no implementation or qualification claimed. The owner reaffirmed on
2026-10-04 that the LLM controls answer structure. The updated
`docs/handoffs/2026-10-02-results-stage-v1-design.md`, milestone/execution plans, and
`docs/handoffs/2026-10-03-results-stage-authored-template.md` replace the earlier code-assembled
answer proposal. Code fills factual slots and checks visible content without imposing layout.
The review is `docs/reviews/2026-10-04-results-stage-design-review.md`; engineering proposals
remain unimplemented, and no upstream stage is reopened.
See `docs/build-log/2026-09-25-ranking-m1-matching.md`,
`docs/build-log/2026-09-27-ranking-m1-live-evidence-run.md`, and the saved plan-linked
matching outputs under `evidence/ranking-stage/m1/`.

When scoping 2C or later stages, consult
`docs/reviews/2026-09-19-future-stage-goals.md` for the owner's requested advisory
synthesis of stage goals, evidence gates, and sequencing alternatives. Its recommendations
are not approved decisions and do not override the active roadmap or open a stage.

Milestone 2B gateway-airport discovery is owner-closed as of 2026-09-19. Milestone 2C deterministic
search-strategy compilation is implemented as an in-place replacement, with no V1 compatibility
path. See `docs/handoffs/2026-09-19-m2c-search-strategy-compilation-plan.md`, ADR 0021, and
`docs/build-log/2026-09-19-m2c-implementation.md`. The active 2026-09-20 provider-neutral revision is
recorded in `docs/build-log/2026-09-20-m2c-provider-neutral-revision.md`. The compiler makes no additional
model call and no travel-provider call; its integrated live diagnostic is model-only. Provider
execution and product/provider qualification remain outside the completed stage. The deterministic,
retrieval-backed outbound-only `EffectiveRequest -> CompiledSearchPlan` boundary is implemented and
offline verified for its declared catalog, replay, and policy evidence. Milestone 1 supplied the reviewed,
versioned local geographic/airport catalog. On 2026-09-21 the owner adopted and qualified Milestone 2A as the
official endpoint-airport source for exactly resolved geographic entities. Explicit and uniquely
resolved named airports remain direct catalog singletons; geographic endpoints use the bounded
model proposal, deterministic validation, immutable record, and M2C replay. The completed
search-planning milestones M1, M2A, M2B, and M2C are owner-monitored, owner-reviewed, and
owner-qualified for their declared boundaries. Independent external or holdout corroboration remains
unclaimed and may inform later policy revision. ADR 0023 retires
the executable Milestone 0 JSON/group compatibility path.

The completed search-planning milestone record is preserved in
`docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`. Milestone 2B implements the
market-aware gateway-candidate boundary: given selected departure and destination airport sets, apply
the approved versioned planning-market policy, skip only a fully known single-market request, and
otherwise make one grouped structured model proposal for bounded provider-neutral candidates.
Candidates are unverified search hypotheses, never route or connectivity facts. An unknown endpoint
market forces generation with an explicit mapping-gap receipt; a model/policy candidate-market
disagreement is advisory and passes to 2C rather than rejecting an otherwise valid candidate.
The prompt-v6/casebook-v3 development diagnostic is mechanically complete. The owner accepted the
implemented boundary and evidence record for its declared stage scope. The preceding prompt-v5/casebook-v3 run exposed
relationship multiplication; prompt-v6 adds relationship-level uncertainty/scope reconciliation and
same-scope candidate consolidation without changing the schema, adapter, catalog, policy, or
deterministic validator. Access gateways may be materially complementary alternatives even for
already-strong endpoints, but require specific incremental value rather than size, proximity, shared
market, or diversity alone. The pools are independently capped at 2 origin access, 2 destination
access, and 5 hubs (9 candidates total); no intermediate-market diversity quota applies. Closing 2B
does not close or adopt 2A;
reviewed fixtures or supplied selection records may be used without promoting model output into
geographic fact. The 2B boundary itself stops before strategy compilation and provider execution;
2C now consumes its replay record without changing those claims. See ADR 0020.

The final v6 diagnostic recorded 46 case-trials and 42/42 expected calls across two trials: 37
nonempty, 4 empty, 4 policy-skip, and 1 partial outcomes; 82 accepted candidates (22 origin access,
18 destination access, and 42 hubs), 43 scopes, and 400 accepted relationships. It recorded 186,549
tokens, one catalog-absence rejection for PNH, and three retained market-mismatch advisories. Artifact
integrity and independent AI semantic review passed for owner human review; this is not human semantic
qualification. Complete 2C relationship accounting remains mandatory; provider search-work and
execution budgeting belongs to the later provider stage. No prompt-v7 or
deterministic semantic-rejection change is currently recommended.

On 2026-09-21 the owner approved the next provider/result-stage goal. On 2026-09-22 the owner named
it Provider Stage and narrowed its boundary to a typed, replayable `ProviderResultSet`. It executes M2C's already
complete, untrimmed provider-neutral search graph rather than adding another planning milestone.
The workflow remains award-first: acquire a brief direct origin-to-destination cash benchmark
outside the ranked award recommendations, and allow one cash access or egress component to enter
ranking only inside a deterministically validated award-led journey in the later ranking/output stage. Provider Stage
executes bounded Seats.aero and `gfly` calls, captures, parses, normalizes, conservatively
deduplicates, and attributes observations with validation and coverage receipts. It does not
assemble mixed journeys, rank, calculate value, explain, or generate recommendations. The decision and implementation
boundary are in ADR 0022 and
`docs/handoffs/2026-09-21-award-first-provider-results-plan.md`. D05 and D15 are only partially
opened for narrow cash acquisition and later mixed assembly respectively; cash-only product scope, pure-cash ranking, general hub/component
assembly, round trips, and provider qualification remain outside it. Provider Stage implementation
started on 2026-09-22 behind a separate explicit CLI/API. The bounded cash contrasts and combined live/replay gate
passed on 2026-09-23 after a reviewed narrow gfly parser fix. The owner accepted the stage
on 2026-09-23 for its declared boundary after reviewing the output structure and combined
example. See `docs/handoffs/2026-09-23-provider-stage-closeout.md` and
`docs/build-log/2026-09-23-gfly-investigation-and-live-gates.md`.
ADR 0016 still governs upstream request/session behavior.
The canonical reusable Provider Stage corpus is `evidence/provider-stage/saved-searches/`;
start with its README and index. Historical campaign folders were removed on 2026-09-23 at the
owner's request. Use `data/provider_capabilities/provider-stage-current.json` for new work;
preserve embedded original settings when replaying saved executions. Saved planning inputs do
not imply that their entire graphs have live provider coverage.

Do not reopen 2B or treat the implemented 2C compiler as provider execution, availability, itinerary,
product, or recommendation qualification. M2A adoption and owner qualification are recorded in ADR 0023.
The 2B closeout is recorded in
`docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md`.

The upstream one-way award-only boundary in ADR 0016 is frozen for this stage:

- require origin, destination, bounded outbound departure timing, and travelers;
- preserve the existing outbound temporal mechanism and all provenance, grounding, validation, and
  immutable-state guarantees;
- treat recognized return dates and trip durations as explicit unsupported scope, with guidance to
  submit the return as a separate one-way request; and
- reject cash-only requests while permitting the award portion of mixed award-and-cash requests
  without claiming cash-search coverage.

The prior round-trip/cash-capable contracts, corpus, and qualification evidence are historical.
There is no live runtime workflow switch. The owner selected knowledge-base expansion as the next
cut on 2026-09-13. Preserve the remaining broad upstream behavioral-evidence gap as recorded, not
silently treated as qualification. See `docs/handoffs/2026-09-12-search-planning-design.md` for
the planner completion boundary and the knowledge-base completion map.

## Architecture boundaries

- The model may perform semantic extraction and identify ambiguity.
- Deterministic code must perform date arithmetic, schema validation, conflict checks, and clarification policy.
- Unknowns and conflicts must be preserved.
- Hard constraints must never be silently invented.
- Recognized return dates and trip durations must never become active one-way request/session state;
  they require explicit separate-one-way guidance.
- Cash-only intent must not produce a success-shaped ready result. Mixed award-and-cash intent must
  not imply that cash prices or cash search are available.
- A clarification answer must retain its turn-level provenance and must not silently overwrite
  unrelated hard constraints.
- Clarification prompts must enumerate all current blockers deterministically; one user answer may
  resolve any subset of them.
- An explicit, grounded correction to a supported already-resolved request field must be applied
  atomically and trigger full recomputation; new unsupported constraints remain explicit instead
  of being silently accepted.
- Do not introduce LangChain or LangGraph for this stage. Use explicit Python/Pydantic contracts
  and deterministic state reduction.
- The intent and clarification components must not expand cities into airports; the new planner
  may do so only from versioned retrieval evidence and explicit planning policy.
- The intent component must not call travel providers.
- Model-dependent behavior must sit behind a narrow interface.
- Tests must run without live model or provider access.

## Current non-goals

- Provider integrations outside the opened Provider Stage Seats.aero and `gfly` slice
- Weighted overall ranking; M2 solution styles are locally implemented
- RAG
- Production Web UI
- Authentication
- Persistence
- Multi-agent orchestration
- Deployment infrastructure

A local Streamlit interface is allowed only as an experimental validation harness: no persistence,
authentication, deployment, provider calls, or workflow logic in the UI layer.

## Development expectations

- Read `docs/project-state.md` before making substantial changes.
- Consult the workbook when product context is relevant.
- Read the relevant ADR before changing an architectural boundary.
- Add or update tests for behavior changes.
- Run tests before declaring work complete.
- Surface explicit errors rather than returning success-shaped fallbacks.
- Never commit credentials or private travel information.
- Do not fabricate measurements or evidence.
- Report files changed, commands run, tests run, assumptions, and remaining failures.

## Deferred-work register

`DEFERRED.md` in the repository root is the living register of intentionally
parked work and claim-specific prerequisites. Consult it when scoping a new
stage or closing a meaningful session. When work is newly deferred, reopened,
completed, or dropped, update the existing stable entry (or add one), its source,
revisit trigger, and required completion evidence. Keep recommendations distinct
from owner-approved decisions, and preserve a dated disposition history.

Do not automatically implement parked work or treat explicit non-goals as
future commitments. Required core work and safety/qualification prerequisites
must not be mislabeled optional cleanup. The register does not override the
source-of-truth hierarchy above.

## Build log

After a meaningful implementation or evaluation session, update the
relevant entry under `docs/build-log/`.

Codex should record objective development evidence such as:

- work attempted;
- files changed;
- commands and tests run;
- eval results;
- observed failures;
- trace observations;
- implementation it generated.

Do not invent project-owner conclusions.

Leave clearly marked placeholders, or preserve existing owner-written
content, for:

- architectural or product decisions;
- interpretation of what was learned;
- what the project owner changed or rejected;
- the final next cut line.

If the project owner has already stated those conclusions explicitly
during the task, Codex may record them accurately.
