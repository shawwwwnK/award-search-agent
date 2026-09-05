# 0009: Compile temporal candidates deterministically

- Status: Accepted

## Context

ADRs 0007 and 0008 limited what the two temporal model passes could see and moved calendar
arithmetic out of the model. Their sequential Pass 2 contract still asked a model to author a
flat relation wire. Schema-valid sentinel values and semantically incorrect relation graphs made
that conversion the dominant reliability failure. A stronger model improved completion but did
not remove that structural risk.

The retained offline probe showed that the existing canonical graph evaluator produces the
approved outcomes for the first six failing scenarios when it receives correct relations.

## Decision

For the new compiler path, deterministic code scans `RawRequest.text` directly and creates a
local temporal candidate catalog. It owns literal anchors, quantities, duration modifiers,
endpoint cues, supported relative/composition wording, and unsupported wording. Pass-one temporal
anchors and phrases are diagnostic-only on this path and cannot alter scanner facts.

Candidates have local IDs, exclusive groups, coverage and dependency metadata, and mandatory
scoped anchor use:

- `direct_window` may create a bounded endpoint window;
- `reference_only` may be used only as a relation reference; and
- `unresolved_support` preserves literal support without authoring a window.

The compiler validates candidate membership, exclusivity, coverage, dependency closure,
same-target composition, anchor scope/kind/target compatibility, and cycles. It directly builds
the existing `TemporalRelationGraph`; it does not call the Contract-v2 model-wire converter or
the model-catalog conformance layer. Existing deterministic enrichment, graph validation,
calendar evaluation, conflict detection, and clarification continue to own their respective
responsibilities.

`CompiledTemporalIntent` is the internal temporal hand-off on this path. It retains the canonical
graph, resolved anchors, proposal, windows, literal duration, and unresolved semantics. Its
proposal is the compatibility input to existing final assembly.

`compiler_select_v1` is opt-in and currently invokes no temporal model: it auto-selects only
groups with one safe interpretation. `two_pass` remains the default rollback path. An optional
selector may receive only ordered local evidence, local anchors, candidate groups, summaries, and
dependencies and return selected local candidate IDs. It must not receive reference date, timezone,
resolved dates, provider data, canonical IDs, source offsets, or expected outputs.

## Consequences

- The production migration path no longer depends on model-authored temporal relations for fully
  auto-compilable requests.
- `Labor Day weekend` can use a direct anchor window while `after New Year` uses the same literal
  only as a reference and `first week of June` uses June only as unresolved support.
- A relative return weekend is compiled against `departure:end`, not a coincidentally equivalent
  holiday date.
- The initial six-scenario cut has been extended through the sixteen ready corpus scenarios in a
  table-driven offline oracle gate. Unsupported and ambiguous language remains explicit rather
  than widened.
- The compiler carries a strict unbounded endpoint bound for phrases such as "back before July
  8" so chronology conflicts can be detected without fabricating a return window.
- A model-facing selector adapter now submits only the date-free opaque projection and accepts
  only `TemporalSelectorOutput` in one call without repair. Frozen ambiguity evaluation and its
  selector-quality matrix remain required before a live selector is enabled.
- The frozen evaluator rebuilds private manual catalogs, verifies exact checked-in public
  projections, and compiles restored selections with fixed offline holiday dates. Paired
  candidate-order variants cover target, reference, composition, scope, dependency closure, and
  unsupported-to-unresolved choices. This is evaluation infrastructure, not a live-selector result
  or an authorization to enable a selector.
- Compiler-route Pass 1 is a separate strict non-temporal boundary. It has no temporal fields,
  repair path, or legacy extraction fallback; scanner/compiler facts are merged only after
  compilation into the compatibility extraction used by final assembly. The rollback two-pass
  prompt, schema, and repair contract remain unchanged.
- The ready-corpus evaluator exposes the compiler arm as `compiler_select_v1`. It constructs only
  its non-temporal Pass 1 adapter and, when explicitly configured, a separately modeled selector;
  it passes no live Pass 2 resolver. Schema-v5 artifacts keep legacy totals while recording
  payload-free stage telemetry and stable selector failure classifications. This wiring is not an
  authorization to run a live study or enable the selector.

## Relationship to earlier decisions

This ADR supersedes only the sequential/model-authored temporal-decision portions of ADRs 0007
and 0008 for `compiler_select_v1`. Their minimum-disclosure requirements and deterministic
calendar ownership remain in force. `two_pass` remains governed by ADRs 0007 and 0008 as the
rollback strategy.

## Verification

Focused offline tests use all sixteen exact ready-case requests and their corpus reference
contexts with a fake holiday provider. They assert scanner candidates, oracle local IDs,
canonical graph kinds, evaluated windows, clarification-relevant output, anchor scope,
raw-text independence from malformed Pass-1 temporal output, unsupported first-week/season
preservation, known duration with an unbounded departure, candidate selection validation, and no
temporal-resolver call for the fully auto-compiled route. Runner coverage additionally verifies
strategy-specific adapter construction, independent selector model use, telemetry under
`--no-trace`, redacted selector failures, and unchanged two-pass totals. No live model or provider
evaluation is recorded by this ADR.
