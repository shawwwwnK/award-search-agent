# 0006: Model temporal relations; evaluate calendar windows deterministically

- Status: Approved

> Refined by ADR 0007: pass two receives date-free evidence, anchor, and symbolic-reference catalogs
> rather than resolved anchors or broad domain objects, and its wire schema uses fixed per-relation
> collections.

## Context

ADR 0003 made the second model pass responsible for proposing direct date ranges after deterministic
anchor enrichment. The `return_weekend_after_departure` evaluation met that ADR's revisit trigger:
the model consistently preserved and understood “the weekend afterwards,” but proposed three
different incorrect return ranges. Textual grounding proved that the wording existed in the request;
it could not prove that the proposed calendar dates conformed to the interpreted relation.

Phrase-specific calendar regexes would reproduce the same boundary problem for relative weekends,
weekdays, offsets, durations, month portions, and directional boundaries. Prompt changes alone would
leave model-proposed arithmetic authoritative.

## Options

1. Keep direct model-proposed windows and expand prompt examples.
2. Add phrase-specific deterministic corrections after direct model proposals.
3. Make the second pass emit a small typed semantic temporal-relation graph, validate it, and
   evaluate all calendar dates deterministically.

## Decision

Choose option 3.

The second pass emits a Pydantic discriminated union covering anchor windows, relative weekends,
relative weekdays, relative offsets, durations, month portions, unbounded boundaries, and explicit
unresolved relations. References point either to an enriched `anchor_id` or to the start/end edge of
a request field.

The model owns semantic classification, target selection, linguistic reference resolution,
direction, ordinal, weekday, unit, ambiguity preservation, and verbatim evidence. Deterministic code
owns schema and evidence validation, kind-specific anchor evidence validation, reference checks,
dependency ordering, cycle detection, holiday-window policy, weekend/weekday/offset/duration
arithmetic, exact window construction, conflict detection, and clarification policy.

`DateResolutionProposal` remains as a deterministically generated trace/result shape for evaluator
and artifact compatibility. It is no longer accepted from the model and is not an authoritative
model output. `TemporalResolver.resolve_dates` retains its narrow interface name during migration,
but its return contract is now `TemporalRelationGraph`.

Unbounded constraints remain unbounded. A duration attached to an unbounded departure may be
interpreted, but it cannot generate return dates until departure is bounded. Explicit return
relations take precedence over duration-derived return construction; deterministic conflict logic
reports a mismatch when their possible windows do not overlap.

## Relationship to earlier decisions

This ADR supersedes ADR 0003 only where ADR 0003 assigns direct range proposal authority to the
second model pass. It preserves the approved two-pass workflow, deterministic anchor enrichment,
holiday product policies, grounding, conflicts, clarification, and the broader ADR 0001 boundary.

## Consequences

- Calendar arithmetic is reproducible and exhaustively testable offline.
- Semantic interpretation can be evaluated independently from final date arithmetic.
- Missing anchors, unresolvable request-field references, cycles, ungrounded evidence, and
  kind/evidence mismatches fail explicitly.
- The internal graph uses discriminated unions. The model-facing Structured Outputs wire contract
  is necessarily flatter and nullable because the selected API/model rejects Pydantic-generated
  `oneOf`; deterministic adapter conversion restores the typed internal invariants immediately.
- Recorded direct-range pass-2 fixtures and external fake resolvers must migrate to relation graphs.
- Historical live artifacts remain valid evidence of the old workflow but are not comparable as
  relation-level outputs.

## Evaluation

Component evaluation checks typed relation kinds, targets, references, direction, ordinal, weekday,
unit, and ambiguity preservation without requiring one exact phrase segmentation. Deterministic
unit tests own calendar arithmetic. End-to-end cases check final windows, conflicts, unknowns, and
clarification.

No live model evaluation was authorized for this change.

## Revisit trigger

Revisit if the graph cannot represent a recurring temporal relation without phrase-specific
calendar logic, if Structured Output reliability is unacceptable, or if multiple simultaneous
constraints require an explicit intersection/alternative operator beyond the current window union.

Approved by the project owner through the explicit implementation direction on 2026-09-01.
