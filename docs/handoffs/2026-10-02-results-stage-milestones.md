# Results Stage execution milestones

Date: 2026-10-02. Status: **proposed milestone breakdown following owner decisions**.

The owner requested proper milestones and a separate milestone for LLM-based evaluation.
The milestone boundaries and completion evidence below are proposals, not implementation
authorization or owner qualification. The accepted product choices are recorded in the
[v1 design](2026-10-02-results-stage-v1-design.md).

The investigation-backed [detailed execution plan](2026-10-02-results-stage-implementation-plan.md)
specifies implementation slices, brief/writer/judge contracts, concrete saved regressions,
exploratory cleanup measurements, proposed file seams, and a bounded evaluation workload.

## Agreed stage direction

The LLM selects journeys and writes editorial explanations; code fills factual data. Preserve
award groups and individual cash alternatives; consolidate only genuine duplicates. Usually
show three choices, at most five complete journeys including alternates. Make award programs
clear. Retain internal evidence links without requiring traveler-facing citations.

Clean the input by removing irrelevant mechanics, factoring shared details, and consolidating
duplicates. Preserve every distinct complete alternative and its relationships. No additional
input cap, overflow mechanism, or multi-pass selection architecture is adopted now.

The sequence is **M1 cleaned evidence -> M2 traveler answer -> M3 LLM-assisted evaluation**.
Owner review and stage closeout follow the milestone evidence; they are not a fourth feature.
No milestone reopens request, planning, provider, matching, or style policy.

## M1 — Prepare coherent results for the LLM

**Goal:** turn one frozen `RankedJourneySet` into a concise, sufficient `ResultsBrief`.

Scope:

- Define the brief and presentation IDs, award groups, and exact duplicate equivalence.
- Join each complete alternative to its own route, times, cabin evidence, program, scoped
  prices, styles, unresolved requirements, booking checks, and observations.
- Factor shared award information without losing the complete identity of any cash variant.
- Summarize supported request flexibility, recorded planning explanations, and meaningful
  coverage gaps/failures. Keep planning hypotheses distinct from observed flights.
- Include separate cash observations, supported incomplete possibilities, and useful rejection
  conclusions at the appropriate granularity. Remove successful validation mechanics.
- Preserve original IDs/evidence internally and account for all original records. Measure
  cleaned sizes for the three saved cases; do not preemptively cap the input.

Completion evidence:

- All three saved M2 inputs project reproducibly without model/provider calls, with complete
  record accounting and no mixed variant facts.
- Offline tests cover distinct variants versus duplicates, differing status/styles/scopes,
  missing cash cabin/legs, unknown prices, mandatory booking checks, conditional causes,
  partial/empty/failed coverage, and incomplete/rejected separation.
- Reviewed input examples show that a reader can reconstruct each whole alternative from the
  brief and understand which facts are unknown. Record before/after sizes without claiming
  that a particular cleanup ratio is inherently good.

**Review checkpoint:** inspect one grouped award with multiple cash alternatives and one
conditional complete journey. Resolve projection gaps before implementing LLM selection.

## M2 — Select, explain, and render the traveler answer

**Goal:** produce a self-contained `ResultsArtifact` from the M1 brief.

2026-10-03 owner clarification: the LLM authors the main answer's layout and text; code fills
the factual blanks. Follow the [authored-template refinement](2026-10-03-results-stage-authored-template.md)
instead of the earlier assembled-answer interpretation. M2 first builds placeholder substitution
and required-slot checks, then adds LLM-authored documents. Tool submission is a proposed option.

Scope:

- Define the structured generation response: selected IDs, optional alternate IDs, opening,
  reasons to investigate, tradeoffs, editorial premium-price judgments, and shared explanation.
- Implement the narrow LLM interface and versioned prompt. The LLM does not return authoritative
  factual itinerary fields or alter eligibility/styles.
- Code fills the selected journeys' factual details and required conditions; make the redemption
  program clear and distinguish it from operating airlines when reported.
- Enforce valid IDs, award-group/alternate limits, five complete journeys in total, original
  style labels, and specific conditions. Support qualified fastest/heuristic-cost statements
  only through supplied comparisons; free prose still needs semantic evaluation.
- Handle useful separate cash comparison, no-complete-journey possibilities, and no useful
  results without padding or promoting rejected trips.
- Specify generation-failure behavior before wiring it. The original proposal calls for a
  short factual summary; precise breadth and retry policy remain unsettled after the owner's
  clarification questions. A failed LLM response is different from a valid no-flights answer.
- Record prompt/model settings, usage, attempts, raw response, selected IDs, and checks for replay.

Completion evidence:

- Fake-writer offline tests exercise valid selection and invalid IDs, spliced variant attempts,
  wrong labels, alternate-limit violations, missing conditions, and model-call/schema errors.
- Saved-result examples and synthetic cases render complete, readable factual summaries with
  no assumed price scope. Cost cases use explicitly synthetic supported scopes.
- Run a bounded generation diagnostic on frozen inputs and preserve its actual outputs for M3.
  No new provider searches are needed. Demonstrate the settled failure behavior.
- Owner walkthrough confirms the intended answer shape: fuzzy explanations from the LLM,
  accurate data from code, understandable programs, and essential conditions in the answer.

**Review checkpoint:** assess actual answers before adding the LLM judge. M2 tests can establish
structural correctness; they do not qualify editorial judgment or arbitrary prose.

## M3 — Evaluate results with an LLM and reviewed evidence

**Goal:** obtain repeatable evidence about factual faithfulness and traveler usefulness,
including evidence about the evaluator's own limitations.

Scope:

- Define criterion-level evaluation for invented facts, combined variants, wrong price scope,
  changed eligibility/styles, hidden conditions, unsupported comparisons, exhaustive-search
  or guaranteed-bookability claims, and promotion of rejected combinations.
- Evaluate useful distinct selection, meaningful tradeoffs, restrained premium-price judgment,
  concise natural language, and usefulness without opening another view.
- Give the evaluator the M1 brief, rendered answer, and deterministic checks. Require specific
  passages, fact IDs, and reasons for each failure rather than one unsupported overall score.
- Build reviewed calibration examples containing correct answers and deliberately planted
  failures; compare judge findings with known labels and inspect false alarms/missed failures.
- Repeat generation on cases with overlapping styles, a prominent conditional option, cash
  variants, unknown taxes/scope, mixed cabins, premium economy, partial failures, incomplete-only
  and empty results. Three generation runs per case is an initial diagnostic proposal.
- Report per-case/run failures, selection variation, evaluator disagreements, and usage. Keep
  selection variation distinct from factual violations. Judge output is advisory evaluation
  evidence; it is not a runtime approval gate or automatic repair step.

Completion evidence:

- Versioned fixture set, generator/evaluator prompts/settings, saved answers and judge reports,
  calibration labels, and deterministic check results can be reproduced for the declared scope.
- Report observed judge accuracy on the labeled examples without claiming general reliability.
  Explicitly review hard failures and unresolved disagreements rather than hiding them in averages.
- Owner reviews representative good answers and failure cases, decides whether the answers are
  useful, and records accepted limitations or required revisions.

## Stage closeout

Closeout summarizes M1 preservation, M2 behavior, and M3 quality evidence; records the owner's
acceptance and remaining limits; and updates project state, build log, and the deferred register.
Current unknown price scope still prevents observed-cost claims. Personal redeemability, provider
reliability, bookability, and broader workflow qualification are not established by an LLM judge.

The immediate next cut is M1's cleaned-input contract and saved-example walkthrough. M2 failure
handling can be settled while M1 proceeds; it does not require an input-cap design now.
