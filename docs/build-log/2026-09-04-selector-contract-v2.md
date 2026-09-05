# 2026-09-04: Frozen selector contract v2

- Reworked only the public frozen-selector projection after the one-trial Mini/Luna study showed
  semantic selection failures despite complete parsing, restoration, and compilation.
- Added a date-free `endpoint_cue` derived solely from explicit local leave/depart/return/back
  tokens in the literal's sentence; no model target, reference date, timezone, offsets, or
  resolved calendar state is used.
- Added pre-authored public interpretation kinds, relation-relevant ordinals, and lossless safe
  candidate summaries. Anchor mode, production/composition operand, and unresolved semantics
  remain explicit while private candidate and slot identities remain opaque.
- Hardened the selector instruction around endpoint cues, anchor modes, dependency closure,
  composition, and unsupported seasonal wording. The boundary remains one call with no repair.
- Preserved `frozen_cases.yaml` as the historical v1 projection. Added
  `frozen_cases_v2.yaml` as the default checked-in v2 study input. The evaluator now records the
  fixture contract version, path, and SHA-256 in schema-v2 artifacts.
- Added v2 preflight checks for unique normalized public candidate semantics, endpoint-cue
  sufficiency when targets compete, and stable normalized oracle identity across each order pair.
  Private manual catalogs and oracles were not changed.

## Verification

- Focused selector/evaluator tests and static checks are recorded with this implementation.
- No live model, provider, ready-corpus, or selector-enabled compiler evaluation was run in this
  contract-update session.

## Owner decision pending

- Run the same explicit-model frozen study against the v2 fixture before reconsidering the
  selector activation gate.
