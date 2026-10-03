# Results Stage authored-template clarification

Date: 2026-10-03. Documentation/design clarification only.

The owner clarified that the LLM should produce the main answer and its structure, leaving
factual blanks for code to fill, and asked whether a tool call would make sense. Parent recorded
that the earlier code-assembled answer interpretation gave code too much structural authority.

Created the [template refinement](../handoffs/2026-10-03-results-stage-authored-template.md) and
linked its supersession from the v1 design, milestone plan, detailed execution plan, and project
state. The proposal uses model-authored Markdown with typed placeholders scoped to the selected
journey, code substitution/required-slot checks, and M3 evaluation of the complete filled answer.
This preserves LLM control of layout and prose while retaining variant and price-scope bindings.

The owner asked about tool calls; no tool requirement was inferred. The document distinguishes
optional fact lookup from a proposed submission tool that validates/fills the authored document
and returns the final artifact without a subsequent model rewrite. Structured output and tool
submission are alternative transports for that boundary.

No runtime implementation, agent delegation, provider/model calls, or behavioral tests were
performed. Existing changes were preserved. `git diff --check` and relative-link/whitespace
checks on both new documents passed.

Owner decision: LLM authors the main output and structure; code fills factual blanks.
Tool transport choice and precise placeholder contract: **recommendations, not yet owner-decided**.
