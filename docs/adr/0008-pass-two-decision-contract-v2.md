# 0008: Use bounded local-handle decisions for Pass 2

- Status: Approved

## Context

ADR 0007 hid calendar values from Pass 2, but its catalog identifiers still embedded canonical
offsets and semantic details.  Pass 2 also constructed a flat graph whose window-composition and
duration-interval semantics were implicit.  In particular, a holiday-weekend range plus "Thursday
as well" and an approximate duration could not independently entail the representative result.

## Decision

Pass 2 receives only a temporal transcript, short request-local handles (`e0`, `a0`, `r0`), narrow
relation candidates, and date-free anchor kinds/targets.  It does not receive canonical IDs,
offsets, claim labels, direct-relation hints, resolved dates, the full request, or calendar context.
The adapter generates Structured Output handle enums from each supplied catalog where possible.

Pass 2 emits one bounded decision per atomic evidence claim.  Deterministic assembly restores
canonical evidence/anchor/reference identities, graph-node IDs, and evidence spans. It inserts a
direct anchor target only when literal anchor evidence stands alone; relative wording such as
"after New Year" and "weekend after Labor Day" remains relation-only. Semantic relations may
reference an earlier decision output by handle and edge.

The executable composition vocabulary is `base`, `intersect`, `union`, `extend_start`, `extend_end`,
`exclude`, and `alternative`.  Duration relations always reference the whole departure interval;
normalization remains deterministic.  Unsupported or ambiguous evidence uses only the bounded
reasons `ambiguous_reference`, `unsupported_relation`, `multiple_plausible_scopes`, or
`insufficient_context`.

## Consequences

- The model no longer copies long wire IDs or authors canonical graph structure.
- The canonical graph is sufficient to reproduce the representative Labor Day windows without
  rereading prose or pass-one labels.
- `exclude` is explicit; the current single contiguous `DateWindow` rejects interior holes rather
  than silently widening them.  A future non-contiguous output contract needs a separate decision.
- Historical flat-wire evals are not comparable to Contract v2 model results.

## Verification

Offline tests cover local-handle payload non-leakage (including repair), schema enums, transcript-local
conformance spans, conservative direct-anchor assembly, derived decision references, whole-interval
duration propagation, and the intersect-empty conflict.
No live model or provider evaluation is part of this ADR.
