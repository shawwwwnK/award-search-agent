# Results Stage: LLM-authored structure with bound factual placeholders

**Current status, 2026-10-08:** Results M2 is [owner-closed](2026-10-08-results-m2-closeout.md) for its declared implemented boundary; M3 remains planned. This supersedes earlier open/unimplemented/pending-closeout status in this document, while preserving historical evidence and policy limits.

**Current M2 policy, 2026-10-07:** use the [consolidated validation/recovery/delivery contract](2026-10-07-results-m2-validation-and-delivery-contract.md)
and [ADR 0026's dated amendments](../adr/0026-model-authored-results-with-bound-facts.md).
These supersede earlier terminal validation gates, hard five-choice and two-per-group caps,
no-repair/single-call proposals and prohibition on attached failure disclosures below.
The LLM owns answer layout; selected checks are non-blocking. Use at most two authoring calls,
retain the recoverable draft with fewer material failures (correction wins ties), and attach
traveler-facing notices/source-backed omitted disclosures. Unchecked/insufficient evidence
remain distinct. Schema output with no recoverable document is a system/generation failure.
Results remains unimplemented; measurement-dependent settings and live budgets remain future work.

Decision record: [ADR 0026](../adr/0026-model-authored-results-with-bound-facts.md).

**Boundary update, 2026-10-04:** the factual model view is supplied directly by the
[Ranking M2 export](2026-10-04-ranking-m2-solution-export.md). Results owns the scoped placeholder,
disclosure and authorship rules in this document; it does not duplicate that factual projection.

Date: 2026-10-03; revised 2026-10-04 after independent review and renewed owner direction.
Status: **LLM structural control is owner-required; wire and validation mechanics are the revised engineering proposal**.

## Ownership

The LLM controls the answer's headings, ordering, grouping, paragraphs, lists, tables, emphasis,
and explanatory prose. Code fills factual placeholders and validates the authored document.
There is no code-owned answer skeleton, card layout, section order, automatic note insertion,
or second LLM pass over the filled answer. Required information is a content obligation, not a
layout prescription. The owner explicitly reaffirmed structural control on 2026-10-04.

This replaces the earlier opening/per-journey editorial-fields design. The current
[v1 design](2026-10-02-results-stage-v1-design.md),
[execution plan](2026-10-02-results-stage-implementation-plan.md), and
[milestones](2026-10-02-results-stage-milestones.md) use the following boundary throughout.

## Proposed document contract

Use one model-authored document with an explicit selection manifest and an ordered list of
**invisible factual scopes**. These parts are serialization units; they are not visible cards,
sections, or imposed blocks. Repeating a scope allows one journey to appear in a comparison
row and later receive its explanation or conditions elsewhere in the same document.

```text
ResultsDocument
  selections[]: {alternative_id, alternate_of: alternative_id | null}
  benchmark_id: benchmark_id | null
  incomplete_ids[]
  parts[]:
    scope_kind: shared | journey | benchmark | incomplete
    scope_id: string | null
    markdown_template: string
```

The LLM writes all separators and whitespace. Code concatenates the parts in the supplied order
without adding headings, paragraphs, or punctuation. The model may use prose, a table, or a mix;
no scope order or journey contiguity is required. Scope metadata never appears automatically
in the traveler answer. Selection counting uses unique manifest IDs, not the number of parts. Successful authorship
targets one or more complete journeys when the complete pool is nonempty, and zero otherwise;
five is a soft presentation target, not a schema maximum.

In a journey scope, `{{route}}`, `{{schedule}}`, `{{award_quote}}`, and other allowed slots resolve
only from that scope's complete alternative. Cross-journey slot lookup is invalid. Each placeholder token must be wholly within one part;
a token split across parts has no valid scope and is rejected. Shared parts
may use shared slots and supplied `{{comparison:ID}}` slots; they cannot look up journey facts.
Benchmark/incomplete scopes use their own catalog. A scope ID must occur in the appropriate
selection manifest. The service stamps the brief digest after receipt; the model does not echo it.

For example, one author may put explanations first and facts below; another may begin with a
comparison table whose rows are separately scoped parts. Both must be accepted when their
facts, conditions, and associations are valid. M2.1 tests both layouts and multiple parts for
one journey. There is no preferred template enforced by code.

This uses a small strict object schema with required fields, explicit nulls, enums, and no
additional properties. The Markdown strings remain freeform within the supported syntax.
JSON structure does not prescribe the answer's visible structure.

## Factual slots and visible obligations

Prefer coherent slots: `award_quote` includes the redemption program, points, fees, quote scope,
and missing-cost limitations; `cash_quote` includes the actual component and its scope. A bare
number can lose its meaning. Local schedules retain dates and timezone context. Requirements,
separate-ticket checks, and observation timing retain the selected variant's evidence.

Projection creates a versioned obligation manifest for each selectable alternative and for
shared request/coverage facts. Selection activates those obligations. Applicable heuristic
comparisons activate their assumptions. Each selected journey must disclose its route, schedule,
cabin evidence, duration/waits, scoped prices/program, status and concrete unresolved requirements,
booking obligations, and component observation timing. Nonapplicable facts need no empty slot.
A condition may be placed anywhere the model chooses if its association with the affected
journey remains clear; a generic global warning cannot discharge a specific journey's condition.

Code checks the following, without inventing missing text:

1. Manifest IDs, original eligibility, group/alternate relationships, and the soft five-journey target.
2. Exact allowed placeholder syntax and scope, unknown slots, and required slot coverage.
3. The **final concatenated Markdown**, including constructs spanning part boundaries. Permit
   tested headings, paragraphs, lists, emphasis, and tables. Reject raw HTML/comments, images,
   links, and code constructs in v1; they are unnecessary for this local citation-free answer.
   Link syntax can be reconsidered with an explicit destination policy if a booking-link feature
   is opened. Facts and conditions must occur in visible text, not parser metadata.
4. Single substitution using literal escaped text nodes; provider/user strings cannot introduce
   markup, executable content, or a second placeholder expansion. Never use a general template
   engine capable of expressions, evaluation, filesystem access, or recursive interpolation.
5. Final parsed visible content and source maps connecting every inserted span to its slot,
   scope, and source fact. Preserve tables and line breaks without letting a slot break syntax. Test part boundaries
   inside Markdown constructs/table cells, and reject a placeholder split across scopes.

A missing mandatory fact or condition is a non-blocking check failure. Request correction
within the two-invocation policy; if it remains missing, attach a traveler-facing notice supplying
the known source-backed disclosure beside the affected journey. This narrow notice exception does
not authorize rearranging the authored recommendation layout. Annotated delivery is not a clean pass.

These checks bind inserted facts and visible disclosure. They cannot prove that a heading,
pronoun, comparison, or juxtaposition accurately describes those facts. “Per person,” “all
business,” or “protected connection” can still be false beside valid slots. M3 evaluates the
fully filled answer, including its structure and implications. This limitation is explicit,
not a reason to transfer structural control to code.

## Call transport

Recommend a Responses Structured Outputs submission for each authoring attempt: one initial
invocation and at most one correction. A strict response envelope is sufficient to return this
document; a submission function is unnecessary for this authoring operation. OpenAI distinguishes structured response formatting from function calls that connect
a model to application functionality. [Official Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs).

No fact lookup loop is needed while the complete brief is sufficient. If a submission-tool
transport is later chosen, it must submit the same contract per attempt, check/fill it, and
preserve the same bounded correction and annotated-delivery policy. No post-delivery rewrite follows. Tool use does not strengthen factual
truth or grant upstream authority. This transport recommendation is engineering judgment, not
an owner requirement to use or avoid tools.

Use explicit timeout/retry/output configuration, handle refusal and incomplete output, and
retain replay evidence as specified in the [execution plan](2026-10-02-results-stage-implementation-plan.md).
No Results implementation or model evaluation is claimed by this design revision.
