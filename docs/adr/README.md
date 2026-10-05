# ADRs

An architecture decision record documents a consequential technical decision, the alternatives considered, and the reasons the project chose one path over another.

Create an ADR when a decision changes workflow boundaries, trust guarantees, evaluation strategy, state management, or another choice that will matter later when behavior is reviewed or revised. ADRs should capture consequential, defensible decisions rather than every library choice.

## Decision-record workflow

- At design opening and before changing a consequential boundary, inspect existing ADRs and
  decide whether to add a record or amend one. Triggers include stage ownership, input trust,
  model/code responsibility, eligibility/evidence policy, ranking/valuation, state and evaluation
  guarantees. Routine implementation details need no ADR.
- Record accepted decisions in the same session as their contract/implementation changes, before
  closeout or commit. A handoff, plan, build log or project-state entry does not replace an ADR.
- Use explicit status and dates. Proposed options remain proposed; accepted product policy must
  be distinguished from engineering proposals and implementation/qualification status. An ADR
  records authorization already given; it does not create another approval gate.
- For backfills, retain the original decision dates, add the recording date, and cite original
  sources. Do not invent alternatives, owner rationale or retrospective measurements. Label
  inferred tradeoffs as analysis rather than owner conclusions.
- Link affected contracts/current state to the ADR and update this index. State what earlier
  decision is superseded and its exact scope. Preserve historical evidence; use a dated amendment
  or a new superseding ADR for material changes instead of silently rewriting prior decisions.
- Session closeout records the ADR added/amended, or a brief reason none was needed. Reconcile
  conflicting current documents and update deferred entries only when their disposition changes.

Expected sections:

- Context
- Options
- Decision
- Consequences
- Evaluation
- Revisit trigger

## Index

- [0001: Request understanding is a typed workflow node](0001-request-understanding-boundary.md)
- [0002: Nager holiday date provider](0002-nager-holiday-date-provider.md)
- [0003: Two-pass temporal resolution](0003-two-pass-temporal-resolution.md)
- [0004: Location names are resolver candidates](0004-location-names-are-resolver-candidates.md)
- [0005: Claim-linked temporal evidence](0005-claim-linked-temporal-evidence.md)
- [0006: Typed temporal relation graph](0006-typed-temporal-relation-graph.md)
- [0007: Minimum-disclosure two-pass intent workflow](0007-minimum-disclosure-two-pass-intent-workflow.md)
- [0008: Pass-two decision contract v2](0008-pass-two-decision-contract-v2.md)
- [0009: Deterministic temporal candidate compiler](0009-deterministic-temporal-candidate-compiler.md)
- [0010: Selector-only temporal understanding](0010-selector-only-temporal-understanding.md)
- [0011: Iterative all-blockers clarification sessions](0011-iterative-clarification-sessions.md)
- [0012: Accepting clarification and behavioral evaluation](0012-accepting-clarification-and-behavioral-evaluation.md)
- [0013: Single-call clarification receiver](0013-single-call-clarification-receiver.md)
- [0014: LLM-owned clarification semantics and composition](0014-llm-owned-clarification-semantics-and-composition.md)
- [0015: Generic model-authored clarification calendar proposals](0015-generic-model-authored-clarification-calendar-proposals.md)
- [0016: One-way award request boundary](0016-one-way-award-request-boundary.md)
- [0017: LLM-owned initial intent semantics](0017-llm-owned-initial-intent-semantics.md)
- [0018: SQLite published geographic catalog with JSON receipts](0018-sqlite-geographic-catalog.md)
- [0019: LLM-proposed endpoint airports with bounded catalog validation](0019-llm-proposed-endpoint-airport-selection.md)
- [0020: Market-aware model-proposed gateway candidates](0020-market-aware-model-proposed-gateway-candidates.md)
- [0021: Deterministic search-strategy compilation](0021-deterministic-search-strategy-compilation.md)
- [0022: Award-first cash observations and positioning components](0022-award-first-cash-observations.md)

- [0023: Adopt M2A and retire Milestone 0 compatibility](0023-adopt-m2a-and-retire-m0-endpoint-selection.md)
- [0024: Deterministic award-led journey matching](0024-deterministic-award-led-journey-matching.md)
- [0025: Deterministic overlapping solution styles](0025-deterministic-overlapping-solution-styles.md)
- [0026: Model-authored Results structure with bound facts](0026-model-authored-results-with-bound-facts.md)
- [0027: Ranking-owned factual export and trusted upstream Results input](0027-ranking-owned-solution-export-and-upstream-trust.md)
