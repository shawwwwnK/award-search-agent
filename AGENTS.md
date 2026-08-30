# AGENTS.md

## Project purpose

Build a narrow, measurable award-search workflow that converts vague travel requests into grounded, traceable recommendations.

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

Implement request understanding only:

`raw request -> ParsedRequest -> ClarificationDecision`

## Architecture boundaries

- The model may perform semantic extraction and identify ambiguity.
- Deterministic code must perform date arithmetic, schema validation, conflict checks, and clarification policy.
- Unknowns and conflicts must be preserved.
- Hard constraints must never be silently invented.
- The intent component must not expand cities into airports.
- The intent component must not call travel providers.
- Model-dependent behavior must sit behind a narrow interface.
- Tests must run without live model or provider access.

## Current non-goals

- Search planning
- Provider integrations
- Ranking
- RAG
- Web UI
- Authentication
- Persistence
- Multi-agent orchestration
- Deployment infrastructure

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