# ADR 0026: Model-authored Results structure with bound facts

- Status: Accepted ownership boundary; detailed engineering mechanics remain proposed
- Decision dates: 2026-10-02 Results design opening; structural control reaffirmed 2026-10-04
- Recorded: 2026-10-04 (backfill; Results runtime remains unimplemented)

## Context

Results must explain checked alternatives while preserving facts, conditions and limitations.
The earlier code-assembled editorial-fields proposal imposed answer structure. The owner required
LLM control of structure and reaffirmed it on October 4. Sources are the
[revised design](../handoffs/2026-10-02-results-stage-v1-design.md),
[authored-document contract](../handoffs/2026-10-03-results-stage-authored-template.md), and
[active opening](../handoffs/2026-10-04-results-m2-opening.md).

## Options

The documented alternatives are a code-owned answer skeleton populated with model editorial fields
and the selected model-authored document with bound factual placeholders. The former was replaced
because the owner requires model control over headings, order, grouping, paragraphs, lists,
tables, emphasis and prose. This records that owner requirement rather than an experimentally
proven superiority claim.

## Decision

The model owns visible answer structure and explanatory prose. Code supplies factual slots,
fills them from trusted upstream facts and checks final visible content without imposing layout.
Required facts and disclosures are content obligations, not fixed sections or cards. Code must
not silently append a corrective section, rearrange the draft or conceal a journey's conditions
in a generic warning. Invalid authorship yields an explicit failure under the eventual call policy.

Conditional requirements, separate-booking obligations, quote scope, missing costs, cabin limitations
and coverage must remain visibly associated with selected journeys. Direct cash stays a benchmark;
rejected records cannot become selections or model-promoted validated journeys. Ranking owns
membership and eligibility; Results owns presentation selection and explanation.

## Consequences

This supersedes the earlier code-assembled answer proposal, without reopening upstream validation.
Flexible layout increases the burden on scope, substitution and visible-content checks.
A filled document alone cannot prove the model's prose is grounded or the answer is useful.
Results M2 is active but runtime remains unimplemented; M3 evaluation remains planned.

The scoped-parts wire schema, strict Markdown subset, source maps, exact replay and repair mechanics
in the authored-document contract are revised engineering proposals. This ADR does not elevate
all those mechanics to owner-approved product policy. Writer/judge settings, fallback breadth,
numerical live budgets and authoring context fit remain unsettled.

## Evaluation

Planned offline checks must accept both prose and table layouts, including repeated/interleaved
journey scopes, while rejecting missing, hidden, incorrectly associated or altered facts and
conditions. Check final concatenated visible content and preserve source attribution through
substitution. Later bounded authoring diagnostics and calibrated advisory evaluation must assess
unsupported prose and task usefulness separately from mechanical slot checks.
The [design review](../reviews/2026-10-04-results-stage-design-review.md) is design evidence,
not Results implementation or qualification. No new live call is authorized by this ADR.

## Revisit trigger

Revisit if authored layouts cannot preserve visible associations, unsupported prose remains material,
or owner-reviewed tasks require a different authorship boundary. Settle schema and failure/call
policy during Results implementation, recording consequential accepted changes explicitly.
