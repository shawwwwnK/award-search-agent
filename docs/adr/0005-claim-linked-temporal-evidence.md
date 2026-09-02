# 0005: Ground claim-linked quotes to canonical request spans

- Status: Approved

> Refined by ADR 0007: pass one still emits exact quotes and occurrence indexes for grounding;
> pass two selects canonical evidence IDs and does not repeat source quotes. One bounded model
> repair attempt may follow a failed pass-one validation, but deterministic grounding remains exact
> and authoritative.

## Context

The first temporal pass previously emitted an untyped bag of verbatim phrases. The live evaluator
required preferred human phrase strings to appear as exact set members. That conflated source
grounding with annotation boundaries: a grounded phrase such as `on the Thursday as well` failed
when the preferred annotation was `the Thursday as well`, while a synthetic splice still needed to
remain a hard error.

## Options

1. Keep exact preferred phrase-set equality as a hard eval requirement.
2. Accept phrases using fuzzy or bidirectional substring similarity.
3. Keep exact grounding as a hard gate and score sufficient evidence inside claim-specific source
   envelopes, with preferred boundaries diagnostic only.

Choose option 3. Option 1 tests annotation segmentation rather than product behavior. Option 2 can
accept insufficient or overbroad evidence and weakens traceability.

## Decision

Model-facing temporal evidence remains an exact quote with an optional zero-based occurrence index.
The model does not calculate offsets. Each quote is explicitly linked to one or more typed temporal
claims. A temporary adapter maps old `TemporalPhrase(applies_to, raw_text)` objects to a coarse
claim, but canonical workflow output always contains validated evidence spans.

Deterministic grounding uses exact Python string matching only. It performs no case folding,
whitespace or Unicode normalization, fuzzy matching, paraphrase repair, or model-based correction.
Unique quotes resolve automatically. Repeated quotes require an occurrence index. Canonical offsets
are start-inclusive and end-exclusive, and displayed evidence text is derived from
`original_request[start:end]`.

Evaluation fixtures define rules per claim:

- allowed source envelopes bound where support may come from;
- required-all fragments must all be covered by the candidate span union;
- each required-any group requires coverage of at least one member;
- preferred spans record human annotation boundaries for diagnostics only.

All spans for one claim must fit within one common allowed envelope by default. This rejects a
whole-request quote for a narrow claim, evidence that crosses into another claim, and arbitrary
combinations from unrelated request regions. A grounded but insufficient span also fails when it
omits a meaning-changing fragment such as `about`, `flexible`, or `as well`.

Strict grounding, semantic-field checks, claim/evidence support, and deterministic date and
clarification checks are separate hard gates. Preferred-boundary agreement is non-blocking.

Unknown values whose reason is `missing` carry an empty evidence list. Conflicts can retain separate
grounded evidence lists for each alternative. One canonical span may support multiple explicitly
linked claims without duplicating its source text.

## Consequences

- Alternative sufficient quote boundaries can pass without weakening exact source grounding.
- Malformed human fixtures fail compilation before an eval run can silently weaken coverage.
- Grounding and evidence-support regressions are deterministic and require no live model.
- Prompt instructions may improve first-attempt quote quality, but deterministic validation remains
  authoritative. Invalid quotes are never fuzzily or deterministically rewritten, silently dropped,
  coerced, or accepted. ADR 0007 permits at most one model repair attempt using the same narrow
  original input, the rejected output, and structured validation errors; exact grounding and all
  deterministic validation rerun on the replacement output, and a second failure remains explicit.
- Existing non-executable candidate notes may retain older phrase examples, but the executable
  ready-scenario evaluator has one claim-level evidence path and no exact-set fallback.

## Evaluation

Maintain offline regression fixtures for the three recorded Labor Day outputs. The two synthetic
splice outputs must fail grounding. The grounded output with different phrase boundaries must pass
claim support, semantic checks, date arithmetic, and clarification while reporting a preferred-span
mismatch. Unit tests cover exact matching, occurrence disambiguation, fixture compilation, envelope
and fragment scoring, unknowns, and conflict evidence without live model access.

## Revisit trigger

Revisit if the claim vocabulary cannot represent a needed temporal distinction, or if repeated
quotes require a more stable source-segment identifier than occurrence index.

Approved by the project owner on 2026-09-01.
