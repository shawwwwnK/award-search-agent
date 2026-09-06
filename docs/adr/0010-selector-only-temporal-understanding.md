# 0010: Retire sequential temporal resolution in favor of selector-only compilation

- Status: Accepted

## Context

The compiler/selector arm was evaluated against the ready corpus with Luna on both non-temporal
Pass 1 and selector. The traced post-fix run completed 44 of 48 trials (91.67%) with zero
transport, selector-boundary, repair, wire, or grounding failures. The remaining failures are
frozen semantic limitations documented in the 2026-09-05 handoff, not a reason to retain a
second model-authored temporal-relation path.

The old sequential implementation carried a model-authored Pass 2 wire, conformance layer, and
repair loops. It increased latency and failure surface without improving the validated cut.

## Decision

Request understanding is selector-only:

`raw request -> non-temporal Pass 1 -> deterministic temporal scan/candidate catalog -> Luna selector -> deterministic compiler -> ParsedRequest -> ClarificationDecision`

The workflow requires separately configured non-temporal and selector adapters before Pass 1
starts. The runtime always uses `supported_or_unresolved`; a selected unresolved candidate is an
explicit semantic result, never a fallback. There is no strategy switch, Pass 2 model, resolver,
repair loop, wire conversion, or conformance path in the live workflow or ready-corpus evaluator.

The private catalog injection used by selector workflow integration remains evaluation-only. It
is exact-request matched and uses the historical planner only because older frozen manual
catalogs intentionally omit unresolved choices for deterministic fixture groups. It cannot be
selected through runtime or CLI configuration.

## Consequences

- The production request-understanding path has two narrow model boundaries: non-temporal
  extraction and opaque candidate selection.
- Temporal facts, calendar arithmetic, validation, conflicts, and clarification remain
  deterministic.
- `two_pass` and its rollback path are retired rather than retained as runtime configuration.
- Historical two-pass artifacts and build logs remain evidence; they are not executable claims
  about the current architecture.
- New ready-evaluation artifacts use schema version 6 and report only Pass 1 and selector
  telemetry. Existing version-5 artifacts are intentionally not rewritten.

## Relationship to earlier decisions

This supersedes the sequential Pass-2 and rollback portions of ADRs 0003, 0007, 0008, and 0009.
Their privacy/minimum-disclosure principles and deterministic calendar ownership remain in force.

## Verification

Selector-only tests cover required-selector preflight, normal supported-or-unresolved selection,
opaque restoration, catalog validation, test-only injection isolation, separate adapter capture,
and schema-v6 evaluator telemetry. The frozen live result and remaining failures are preserved
in `docs/handoffs/2026-09-05-intent-freeze-handoff.md`.

## Final qualification record

Following the retirement proof and a trace-driven prompt-only repair, the project owner accepted
the selector-only request-understanding implementation as complete and frozen on 2026-09-06. The
qualification artifact is
`evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`:
47/48 records passed (97.92%) over three trials, with 90 calls, zero errors, zero Pass-1,
selector, grounding, semantic, or deterministic-output failures, and one clarification miss
where `repositioning_allowed` asked for `origin` rather than `departure`. The run's 48 all-call
trace sidecars remain private/local under `evals/intent/traces/` and are not committed as public
evidence.

This ADR is the current architecture decision. Historical two-pass comparisons and the earlier
44/48 and 40/48 selector-only milestones remain useful evidence but are not current quality or
runtime claims. No further intent changes are authorized without an explicit owner reopening.
