# 2026-09-10 — ADR 0014 semantic clarification redesign

## Work attempted

- Added ADR 0014 and its acceptance-evaluation protocol.
- Replaced continuation raw-answer semantic recovery with a typed receiver contract and a
  deterministic symbolic-temporal compiler.
- Restored post-reduction LLM prompt composition and removed deterministic clarification-copy
  fallback from the active renderer.
- Added typed offline guardrail cases, static parser-boundary checks, and a paired Luna versus
  GPT-4o mini composer experiment harness.
- Added semantic-contract hardening for correction authorization, typed ranges/dependencies, and
  visible assumption disclosures.

## Evidence

- `pytest -q tests/unit` passed: 379 tests.
- Focused semantic/controller/guardrail tests and mypy checks passed during implementation.
- The architecture review identified live-qualification gaps in the initial experiment/gate design;
  those findings were used to strengthen the typed offline gate. No live OpenAI calls were made in
  this stage.

## Current limitations

- The paired composer harness is development infrastructure only until a preregistered,
  owner-held locked input set and blinded human quality review are available.
- The durable composer-only retry path needs a final architecture review before any live
  qualification or model-selection conclusion.

## Project-owner decisions

- _Placeholder: record any model-selection or latency decision after reviewed experimental
  evidence exists._
