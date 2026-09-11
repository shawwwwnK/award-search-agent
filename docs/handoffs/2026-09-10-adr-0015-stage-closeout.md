# Stage Takeaways: ADR 0015 clarification proposal diagnostic

## 1. Stage Context

This stage tested the ADR 0015 continuation boundary: a model reads a clarification answer and
authors grounded, generic calendar-calculation proposals; deterministic code validates, evaluates,
and reduces those proposals into session state. It began after a prior provider-schema rejection
and ends with a completed public development matrix. The stage did not qualify the boundary and
does not start search planning or provider integration.

## 2. Final Design Explanation

The receiver alone interprets raw answer language. It emits typed, grounded facts or unresolved
fragments; deterministic code enforces evidence, authorization, calendar arithmetic, conflicts,
and immutable state reduction. Invalid proposals receive one shared model-owned repair, then become
visible, non-mutating pending state. OpenAI uses a flat wire representation that is structurally
translated into the provider-independent proposal contract; it never adds a deterministic answer
parser. Provider schema rejection is preflight pending, distinct from a receiver failure.

## 3. Starting Point and Design Evolution

- **Generic proposal boundary (final design).** ADR 0015 replaced phrase-oriented temporal
  representations with generic calendar calculations so deterministic code would not grow
  answer-language heuristics. This is the current contract.
- **Flat OpenAI adapter (final design).** The first public v3 diagnostic failed before inference
  because the provider rejected a `oneOf` schema. The adapter was flattened and hardened; later
  diagnostics reached structured inference without preflight rejection.
- **Public three-trial diagnostic (stage evidence).** The disclosed eight-scenario corpus ran for
  three Luna/Luna trials. It verified provider/trace operation but exposed behavioral and scoring
  gaps. It is not a qualification corpus.

## 4. Key Learnings

### Learning: A valid typed proposal can still be an unsafe interpretation

**Observation.** In all three `bare_return_endpoint` trials, the receiver proposed a return fact
without retaining the unresolved endpoint ambiguity. The deterministic reducer correctly applied
that authorized proposal, producing the unsafe visible result.

**Evidence.** Three-trial public artifact and private trace review.

**Carry-forward.** The receiver must preserve ambiguity before it reaches deterministic reduction;
adding a deterministic endpoint heuristic would violate ADR 0015.

### Learning: Whole-proposal rejection protects safety but can lose valid siblings

**Observation.** Duplicate semantic targets made alternatives invalid. One repair repeated the
shape, producing non-mutating pending. Where valid origin, traveler, and duration facts shared the
proposal, they were not retained.

**Evidence.** `explicit_date_alternatives` failed in 3/3 trials and
`valid_siblings_with_ambiguous_departure` in 2/3.

**Limitations / uncertainty.** The evidence identifies the trade-off but does not decide whether
the proposal contract or atomic-reduction policy should change. That needs architecture review if
the stage reopens.

### Learning: Outcome scoring needs to distinguish safe re-asking from unsafe acceptance

**Observation.** The fuzzy-month case re-asked safely without accepting an approximation, but the
evaluator reported missing disclosure. A correctly formed conflict prompt was also classified as
the wrong action because its blocker changed shape.

**Carry-forward.** Fix the evaluator before using its safety count as a product conclusion; retain
the raw artifact and trace audit rather than rewriting their historical record.

## 5. Cross-Cutting Synthesis

The flat adapter and observability path are operationally sound: 63/63 calls reached structured,
captured, reconciled outcomes. The remaining uncertainty is behavioral: model-authored proposals
need to preserve ambiguity and independent facts, while the evaluator must report those outcomes
without conflating them with scoring artifacts.

## 6. Open Questions

- Should alternatives have a first-class safe proposal representation, or can receiver contract
  guidance reliably emit unresolved-only outcomes?
- Can independent valid facts be retained after a malformed sibling while preserving ADR 0015's
  safety and revision invariants?
- What is the intended action taxonomy when a resolved fact creates a targeted conflict blocker?

## 7. Implications for the Next Stage

ADR 0015 work is closed until explicitly reopened. Preserve the no-raw-text-parsing boundary, the
flat adapter, private trace handling, and redacted public artifacts. Any future reopening should
first address the documented endpoint safety failure, sibling-loss decision, and evaluator defects;
it must not label the current public pilot as qualification.

## Appendix: Evidence Index

| Topic | Source |
| --- | --- |
| ADR 0015 design | `docs/adr/0015-generic-model-authored-clarification-calendar-proposals.md` |
| Acceptance policy | `docs/evaluation/clarification-acceptance-evaluation-protocol.md` |
| Three-trial artifact | `evals/clarification/baseline/2026-09-10-gpt-5.6-luna-v3-development-diagnostic-3-trials-a86bb59.json` |
| Prior rerun handover | `docs/handoffs/2026-09-10-adr-0015-v3-live-rerun-handover.md` |
| Session evidence | `docs/build-log/2026-09-10-adr-0014-semantic-redesign.md` |
