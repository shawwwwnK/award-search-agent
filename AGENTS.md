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

Milestone 2B gateway-airport discovery is implemented and in owner/human review before provider execution. The deterministic,
retrieval-backed outbound-only `EffectiveRequest -> SearchPlan` boundary is implemented and
fixture-qualified for its declared checked-in seed snapshot. Milestone 1 supplied the reviewed,
versioned local geographic/airport catalog. Milestone 2A implemented a bounded model-proposed
endpoint-airport selector and completed its active-policy diagnostic, but the selector remains
diagnostic-only pending independent human semantic review, holdout evidence, and an adoption
decision.

The current search-planning milestone order is recorded in
`docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md`. Milestone 2B implements the
market-aware gateway-candidate boundary: given selected departure and destination airport sets, apply
the approved versioned planning-market policy, skip only a fully known single-market request, and
otherwise make one grouped structured model proposal for bounded provider-neutral candidates.
Candidates are unverified search hypotheses, never route or connectivity facts. An unknown endpoint
market forces generation with an explicit mapping-gap receipt; a model/policy candidate-market
disagreement is advisory and passes to 2C rather than rejecting an otherwise valid candidate.
The prompt-v2 development diagnostic is mechanically complete, while independent human semantic
review and the owner's next-cut decision remain open. Completing 2B does not close or adopt 2A;
reviewed fixtures or supplied selection records may be used without promoting model output into
geographic fact. It stops before 2C search-strategy compilation, provider execution,
returned-itinerary claims, RAG, or persistence. See ADR 0020.

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

- Provider integrations
- Ranking
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
