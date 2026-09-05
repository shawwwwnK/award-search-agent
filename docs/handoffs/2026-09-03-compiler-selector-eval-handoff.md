# Handoff: deterministic compiler to evaluation-ready selector workflow

## Stop point

This is the requested stop point after the production-slot architecture checkpoint. Do not treat
the branch as evaluation-ready: no live selector or compiler-select end-to-end model evaluation
has been run. The worktree is intentionally uncommitted and began clean at `d337c7c`; preserve
these session changes and do not reset or discard unrelated edits.

## Latest verification

Before this documentation-only handoff update:

- `.venv/bin/pytest -q` — `294 passed`.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy` — passed for 51 source files.
- `git diff --check` — passed.

The final production-slot architecture checkpoint also ran 70 focused selector/compiler/workflow
tests with Ruff and mypy clean. Re-run the full set after any source change.

## Completed state

### Compiler route

`compiler_select_v1` is opt-in; `two_pass` remains default. The route scans `RawRequest.text`,
builds scoped local candidates, validates selections, and directly creates the existing
`TemporalRelationGraph`. It does not use the model-authored Pass-2 flat wire/converter.

The table-driven gate in [test_temporal_compiler.py](../../tests/unit/test_temporal_compiler.py)
covers all sixteen `status: ready` corpus cases with exact raw request/context, fake holidays,
static non-temporal output, and a temporal resolver fake that fails if called. It asserts local
selections, canonical graph kinds, evaluated windows, and clarification-relevant result.

Supported policies include exact/month/holiday windows, key relative relations, durations, and
strict `back before` conflict bounds without invented return windows. First-week, seasons, and
non-contiguous dates remain unresolved. Day/week duration can be known with an unbounded
departure; month duration cannot exploit that relaxation. Anchor scope is mandatory and anchors
bind to their own clause.

### Local selector boundary

The local date-free selector projection exists but it is **not** an OpenAI adapter yet:

- [model_views.py](../../src/award_agent/intent/model_views.py): public
  `TemporalSelectorInput`/`TemporalSelectorOutput`.
- [extractor.py](../../src/award_agent/intent/extractor.py): `TemporalCandidateSelector` protocol.
- [temporal_selector.py](../../src/award_agent/intent/temporal_selector.py): selection planning,
  opaque view projection, restoration, and validation.
- [workflow.py](../../src/award_agent/intent/workflow.py): optional selector in compiler route.
- [test_temporal_selector.py](../../tests/unit/test_temporal_selector.py): contract/privacy tests.

Only local temporal text and opaque `eN`/`aN`/`gN`/`cN`/`pN` handles serialize. Reference date,
timezone, resolved dates, provider state, source offsets, canonical IDs, internal handles,
priority, and expected outputs do not. Evidence is source-ordered before public handles are
assigned; literal anchor clauses appear even when not candidate-covered. Selector output remains
exactly `{"selected_candidates":["c0","c3"]}`.

Current production grammar has zero genuinely ambiguous groups. The ready-corpus compiler E2E
path should make zero selector calls; it cannot establish selector quality.

### Explicit production slots

Global target dependency labels were replaced with request-local production slots. Alternatives in
an exclusive group share a slot; selected alternatives produce it. Composition carries an explicit
operand slot; compiler validation/topological ordering and generated constraint binding use that
slot, not “last departure.” Public projection maps slots to opaque `pN` values. Grammar only binds
a dependent candidate when there is one compatible upstream slot; otherwise it conservatively
uses unresolved. No canonical domain relation classes changed.

Tests cover reverse-order Labor-Day/Thursday binding, shared alternative slots, unresolved
upstream closure, invalid/multiple/cross-target/cyclic operands, chained composition, and public
slot privacy.

## Required next sequence

Run an architect checkpoint after every numbered cut, incorporating its findings before delegating
the next one.

1. **OpenAI selector adapter.** Add `select_candidates()` to `OpenAIIntentExtractor` with a
   dedicated date-free prompt and `TemporalSelectorOutput` as the only structured output. One call,
   no repair. Use a distinct selector stage, trace, usage, latency, and independently configured
   selector model. Do not reuse Pass-2 wire models or converter.

2. **Frozen selector-only evaluator.** Create checked-in frozen public inputs plus corresponding
   private/manual candidate catalog construction. Public JSON cannot restore Pydantic private
   maps, so loading must rebuild a catalog/projection before output restoration and compilation.
   Use manual genuine ambiguities: current scanner grammar has none. Cover target, reference,
   composition, scope, dependency closure, and unsupported-to-unresolved. Report parse,
   membership, validation/compiler completion, semantic oracle accuracy, per-class accuracy,
   unsupported accuracy, zero repairs, latency, and usage.

   For frozen inputs evaluate only None/Mini/Luna selector arms. Pass-one model selection cannot
   influence a frozen payload, so the original A–E comparison would duplicate experiments.

3. **True non-temporal Pass 1.** On compiler route replace the old `CoarseIntentExtraction`
   prompt/schema, which still requests ignored temporal anchors/phrases, with temporal-free
   extraction. `CompiledTemporalIntent` remains the sole temporal assembly input. This must happen
   before a decision-grade E2E comparison.

4. **E2E runner wiring.** Add `compiler_select_v1` and independent `--selector-model` to
   `cli/intent_eval.py`. Keep Pass-1 versus selector trace, usage, latency, and failure category
   separate; selector errors must not be legacy Pass-2 wire errors. Test that compiler route never
   invokes a Pass-2 resolver.

5. **Evaluation order.** Focused one-trial ready-corpus compiler smoke (expect zero selector
   calls), frozen selector study, then full compiler E2E matrix. Do not enable a live selector
   unless parse/membership/compiler completion are 100%, overall semantic accuracy is >=95%, each
   target/reference/composition/scope class is >=90%, unsupported-to-unresolved is 100%, and schema
   repairs are zero.

## Adapter acceptance tests

Use a fake client to assert exact payload/schema privacy and strict output shape; malformed/no
parsed output and client errors fail explicitly; duplicate/unknown/missing/multi-group,
unmet-dependency, cross-target, cyclic, and upstream-unresolved/dependent-supported outputs fail
after restoration; empty and auto-only inputs make zero selector calls; selector routes make zero
repair calls. Ensure OpenAI strict schema has only required `selected_candidates` and
`additionalProperties: false`.

## File ownership / safe parallelism

| Cut | Main files | Notes |
| --- | --- | --- |
| Adapter | `openai_extractor.py`, selector model views, adapter tests | Frozen fixture design may run in parallel. |
| Frozen evaluator | new fixture YAML, selector eval CLI/module/tests | Integrate after adapter contract is fixed. |
| Non-temporal Pass 1 | model views, extractor, OpenAI adapter, workflow/tests | Sequential after adapter: overlapping model boundary. |
| E2E runner | `cli/intent_eval.py`, runner tests/docs | After above interfaces stabilize. |

Update ADR 0009, project state, and build log after each objective result; do not modify the
external workbook unless asked. See AGENTS.md for parent integration and subagent reporting rules.
