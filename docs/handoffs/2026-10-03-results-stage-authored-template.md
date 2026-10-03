# Results Stage: LLM-authored answer with factual placeholders

Date: 2026-10-03. Status: **owner clarification recorded; template/tool mechanics proposed**.

## Owner clarification and superseded interpretation

The owner clarified that the LLM should produce the main output and its structure for natural
writing, leaving factual blanks for code to fill. The owner asked whether a tool call makes sense.
This supersedes the earlier M2 proposal in which code assembled the answer from an opening and
per-journey explanations, with code-owned summaries/shared-note layout.

M1 input preparation and M3 evaluation remain applicable. M2's output boundary changes: the
LLM authors the answer's order, headings, paragraphs, emphasis, and explanations. Code resolves
factual references and checks required information, without constructing a separate fixed answer.

## Proposed output contract

Use an LLM-authored Markdown document with explicit typed placeholders rather than literal
empty strings. Blanks need an identity so code can fill the correct journey's fact.

One practical representation is an ordered array of authored blocks:

```text
ResultsDocument
  blocks[]:
    TextBlock {markdown_template}
    JourneyBlock {alternative_id, alternate_of | null, markdown_template}
    CashBenchmarkBlock {benchmark_id, markdown_template}
    IncompleteBlock {possibility_id, markdown_template}
```

Block boundaries bind references to the correct alternative; they do not prescribe cards,
headings, paragraph order, or a fixed visible layout. The model writes all Markdown and chooses
the ordering. A journey block can contain a heading, prose, bullets, or another permitted
Markdown form. Journey placeholders are resolved within that block's alternative ID, so the
model cannot ask for a different variant's fare inside it.

Illustrative journey template (not an actual generated answer):

```markdown
### A shorter journey with an award to investigate

{{route}} — {{schedule}}. {{cabins}}, taking {{total_duration}}.

This deserves a look if the schedule matters more to you than a premium cabin.
{{award_quote}}; {{cash_quote}}.

{{styles}}
{{requirements}} {{booking_checks}}
{{observation_timing}}
```

The text, heading, and placement are model-written. Code fills the route, local schedule, cabin
evidence, complete duration, program/award quote, cash quote, style labels, checks, and timing.
This is an example, not a mandatory layout. The model can write a different natural arrangement.

Prefer coherent factual slots such as `award_quote` over an isolated points number: the slot
includes the redemption program and applicable quote scope/fee limitations. Likewise, `cash_quote`
includes scope and covered component. This prevents a bare amount from losing its meaning.
The model still receives facts in the brief for selection and explanation; the placeholders
keep final factual displays bound to those facts.

Shared request facts, coverage, assumptions, and common checks have scoped shared placeholders
that the model places where they fit. An alternate uses its own bound journey block. Explicit
comparison slots remain authorized only by existing supplied comparison facts.

## Validation responsibilities

Code checks references, group/alternate rules, five complete alternatives total, rejected versus
incomplete boundaries, applicable comparison slots, and presence of required factual/condition
slots. Required information may be shared when valid for the whole answer, but journey-specific
requirements must appear within that journey's block.

Code substitutes slots without asking the model to rewrite the filled result. It must not silently
repair an omitted material condition by assembling a different fixed-layout answer. Missing
required slots are an invalid generation result; handling follows the settled failure policy.

This binds factual inserts and their selected alternative. It does not prove that surrounding
prose is accurate: “per person,” “guaranteed,” or “all business” in model-written text could
contradict the inserted facts. M3 evaluates the fully filled document, including framing and
implications. The existing observed-scope/cabin/timezone limits still apply.

## Tool-call recommendation

Two different tool designs should not be confused:

- A fact lookup tool, such as `get_journey_details(id)`, could help if the model needs details
  beyond its compact brief. Current M1 already supplies the relevant information; lookup is
  not necessary initially. Tool-returned facts can still be misquoted in subsequent model prose.
- A submission tool, such as `submit_results(document)`, accepts the authored template, validates
  references and required slots, and fills it. Its resulting artifact is the final traveler
  output. The model does not rewrite that artifact afterward.

Recommendation: adopt the authored-template boundary now; structured output and a submission
tool are alternative ways to deliver that same document. A submission tool is a reasonable fit
if explicit tool orchestration is desired. It is not a flight-search/booking tool or authority
to change upstream assessments. The choice of transport remains proposed, not owner-decided.

## Milestone changes

M2.1 builds the placeholder catalog, substitution, and validation using hand-authored templates.
M2.2 adds LLM document authorship and either structured submission or the submission-tool adapter.
M2.3 reviews naturalness of actual completed documents, plus generation failure behavior.
M3 tests factual correctness and whether the model-owned structure is useful and self-contained.
Include missing slots, wrong block reference, conflicting surrounding scope/cabin prose, and
an alternate drawing facts from its own variant in offline/evaluation cases.
