# Results Stage execution milestones

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

Date: 2026-10-02; revised 2026-10-04. Status: **Ranking owner-closed with M1 preparation absorbed; Results M2 owner-opened, M3 planned; no Results implementation or qualification**.

## Active boundary revision — 2026-10-04

The owner approved the [Ranking M2 solution-export extension](2026-10-04-ranking-m2-solution-export.md).
Reusable factual projection and its preservation tests belong to Ranking. Results consumes that
view directly and retains presentation grouping, handles, slots, activated disclosures and prompt
preparation in M2. There is no standalone Results M1 or second equivalent brief projection. The M1
section below records the original work requirements; use the extension contract for current
ownership. M2/M3 identifiers are retained for continuity.

The owner requested a thorough design/milestone review with subagent verification and current
LLM-call guidance, and reaffirmed that **the LLM controls the output structure**. The sequence
is now completed Ranking M2 factual export, then Results M2 model-authored answer and M3
LLM-assisted evaluation. This revision
makes the gates concrete; it does not claim owner acceptance of unimplemented engineering choices.

Use the [v1 design](2026-10-02-results-stage-v1-design.md) for product authority, the
[authored-document contract](2026-10-03-results-stage-authored-template.md) for structure/scopes,
and the [execution plan](2026-10-02-results-stage-implementation-plan.md) for exact proposed mechanics.

## Rules across all milestones

The LLM selects useful complete journeys and authors headings, order, grouping, prose, lists,
tables and emphasis. Code fills scoped factual placeholders and checks content; it never imposes
a normal-answer skeleton or appends omitted conditions. Internal scope parts can repeat and
interleave. Required facts constrain content, not layout.

Retain every distinct complete input alternative with conservative same-observation duplicate
rules. Usually display three complete choices; five including alternates is a soft target. Preserve
programs, conditional requirements, scoped quotes, unknowns, separate bookings, component timing
and actual coverage. Cash remains a separate anchor. No input selection cap, new provider calls,
upstream policy reinterpretation, production UI or workflow framework is part of these milestones.

## Original M1 — requirements now owned by Ranking M2 export

**Status:** original Results allocation superseded on 2026-10-04. It was owner-opened earlier
that day for the design and unresolved-decisions walkthrough.
The owner subsequently confirmed that verified same-project upstream output is trusted and
accepted the suggested brief/condition/coverage design direction. See the
[opening log](../build-log/2026-10-04-results-m1-opening.md).

**Deliverable:** deterministic `ResultsBrief`, internal `ProjectionReceipt`, and versioned factual
slot/obligation catalog from one frozen `RankedJourneySet`.

**M1.1: exact projection of trusted upstream output.** Consume the verified same-project
`RankedJourneySet` using its existing typed contract. Preserve upstream decisions and conditions;
no additional requirement verifier or upstream-policy recomputation is part of Results.

Join exact candidate/component/support IDs; preserve whole variants, statuses, style states,
price scopes, missing costs, conditional reasons and nonblocking booking obligations. Factor shared
award/cash/condition records, group by award identity and endpoints, and account for every input
record/alias. Derive price limitations from component evidence, not only convenience summaries.
Separate complete alternatives, direct cash, supported incomplete observations and rejected conclusions.

**M1.2: independent preservation evidence.** Project all three saved cases without model/provider
calls. Review source-backed variant examples and expected facts independently of the projector.
Measure complete serialized prompt/schema size, actual token counts where supported (label estimates),
and group/variant counts. Earlier incomplete probe sizes do not establish fit. Supply meaningful
coverage summaries without treating overlapping graph units as a search completion percentage.

Exit evidence:

- All three saved cases preserve 257/106/64 eligible variants before any justified aliases,
  23/3/4 award groups, all unknown cost scopes and complete record accounting.
- Projection fault/valid controls demonstrate preservation of supplied seat/party/cabin conditions
  and cost limitations. Independent expected facts catch Results omissions or altered associations
  rather than agreeing with the same projector's output; upstream eligibility is trusted.
- Offline tests cover same-observation equivalence and conflicting near-duplicates, status/styles,
  missing versus zero fees, component-cost-summary inconsistencies, missing cabin/legs, positive
  mixed-cabin evidence, actual coverage, empty/failure/incomplete/rejected separation.
- A walkthrough reconstructs the Aeroplan USD 196 / 29h50 and USD 290 / 27h30 variants, conditional
  fastest versus admitted egress, and SFO local-time/UTC difference without invented facts.
- No input is silently dropped to fit context. Any measured fit problem is reported as evidence.

**Checkpoint:** review one multi-cash award group, one conditional
complete journey and the complete compact inputs. Resolve preservation gaps before model selection.

## M2 — Let the LLM author the answer and fill its facts

**Status:** owner-opened on 2026-10-04 after Ranking's expanded closeout. See the
[opening handoff](2026-10-04-results-m2-opening.md). Start with M2.1 offline preparation/rendering;
model/fallback/live-budget decisions belong to dependent M2 work. M3 remains planned.

**Deliverable:** `ResultsDocument -> ResultsArtifact`, with a narrow authoring call and exact
saved-document replay. No code-owned visible layout.

**M2.1: document rendering without a model.** Implement the strict manifest/scoped-parts contract,
slot lookup, literal substitution, Markdown parsing and visible-content receipts. Code concatenates
model-written strings exactly. Build hand-authored prose and comparison-table examples, with the
same journey referenced in multiple parts. Validate the final concatenated document so syntax
spanning parts cannot hide slots. Escape untrusted values; prohibit recursive interpolation.

Target useful complete selections when the complete pool is nonempty (zero otherwise),
with five including alternates as a soft target rather than a schema maximum. Permit multiple
justified alternatives per group; check same-variant facts, scoped conditions, unchanged memberships,
qualified comparisons and separate benchmark treatment. Residual failures receive local notices. The model determines where these facts appear. A required
condition's presence does not prove that surrounding prose is true; preserve that limitation.

**M2.2: authoring adapter and failure/replay.** Recommend one strict Responses structured output
containing the freely authored document. Use one initial invocation and at most one correction;
recommended client configuration retains `store=False`, `max_retries=0`, explicit finite
timeout/output/cancellation settings and no automatic truncation. Select numeric budgets/model
settings before live calls. Distinguish no-recoverable-document generation errors from non-blocking
checks on recoverable answers. Transport/client configuration remains an engineering recommendation.

Keep source, search, generation and delivery outcomes separate. Source corruption stops generation.
Genuine empty results are valid evidence. No-recoverable-document generation errors retain explicit
failure evidence. For recoverable authorship, retain the draft with fewer material failures
(correction wins ties), then deliver with local notices and omitted known disclosures. The answer
layout stays model-authored; a correction API failure retains the original recoverable draft.

Save the accepted document, source/brief/version hashes, inserted-fact map, settings and attempt
receipts. Exact replay substitutes the saved document without a model; regeneration is a new run.

**M2.3: actual document diagnostic.** Run a small declared writer diagnostic only after offline
checks and numerical budgets are settled. Preserve the completed visible answers for M3. Review
how the LLM's actual organization helps a reader compare journeys and locate conditions, including
a table-led and prose-led layout if produced. Required content takes priority over a word target.

Exit evidence:

- Fake-writer tests cover invalid/missing IDs, spliced lookup attempts, alternate cycles/group
  violations, six selections, missing/hidden/cross-part slots, untrusted markup/instructions,
  unsupported comparisons, refusal, truncation, context failure and transport/deadline paths.
- Correct prose/table layouts and valid alternative wording pass; a reject-everything validator
  cannot satisfy the gate. No code inserts a heading, card, note or section order on success.
- All selected facts/conditions remain bound and visible; exact offline replay matches final bytes.
  Invalid source makes zero calls. Attempt/timeout assertions match the configured client behavior.
- Actual saved/synthetic answers, failures, usage and limitations are available for owner review.
  Known complete-cost examples are synthetic until provider scope supports observed comparisons.
- Owner walkthrough assesses structural control, useful distinct choices, clear programs, remaining
  checks and settled delivery-failure behavior. Mechanical passes are not semantic qualification.

## M3 — Evaluate completed answers and the evaluator

**Deliverable:** versioned casebook/rubric, saved writer outputs, calibrated advisory judge findings
and adjudicated report. Define the rubric/fixtures while M1/M2 proceed; repeated judging follows
stable M2 outputs. No runtime judge or self-approval is introduced; M2's single correction is separate from M3 evaluation.

**M3.1: calibration and independent checks.** Use an ordinary separate structured judge call with
frozen brief, fact index, filled visible answer and slot map. Grade criterion-level truth and
usefulness, including misleading headings/table associations beside correct inserted facts.
Apply the writer's explicit storage, timeout/retry/output and refusal/incomplete-response discipline
to the judge, with its own configuration and error counts. Keep deterministic verdicts separate
where practical to reduce anchoring. Require passages,
affected IDs and supporting facts; invalid judge output counts as evaluator error.

Build the proposed initial two correct/nine deliberately flawed seeds. Include valid layouts and
benign alternative wording as controls. Freeze the rubric after tuning, then use separately labeled
held-out examples before claiming judge accuracy. Record misses, false alarms, uncertainty and
harness errors. Prefer an independently evaluated model, while acknowledging shared blind spots.

**M3.2: repeated diagnostic and adjudication.** Retain the proposed 12 cases × 3 trials: 36 writer
outputs and 36 judge calls, plus 11 calibration judge calls = 83 application calls if each completes
once. Additional held-out/calibration/model-comparison work has a separately declared finite budget;
83 is not the whole expanded evaluation budget. No calls are authorized merely by this arithmetic.
Reuse M2 outputs only with matching frozen hashes, without double-counting attempts.

Require actual exercised predicates for saved mixed/exact/positioning cases and synthetic complete
costs, opposing variants, fee/cabin uncertainty, premium economy, failed coverage, incomplete-only,
empty and conflicting near-duplicate cases. Preserve writer failures in the denominator. Separate
legitimate selection/layout variation from factual violations and poor selection usefulness.

Exit evidence:

- Versioned source/oracle manifest, all planned case families actually exercised, independent valid
  controls/planted faults, frozen prompts/settings and all output/error receipts.
- Final-document hard violations reported per case/trial: invention, splicing, scope/status/style
  changes, hidden/misassociated conditions, false comparisons/exhaustiveness/bookability and rejected
  promotion. No unresolved hard violation in the declared passing slice is hidden by average scores.
- Judge calibration and held-out results distinguished; failures/uncertainty are not converted to
  passes. Human adjudication covers hard flags/disagreements and a predeclared clean-output sample.
- Owner reviews whether the answer supports choosing what to investigate, identifying the program,
  understanding the tradeoff/conditions and knowing the next manual check. Useful omission/selection
  concerns are recorded, not reduced to style diversity or word-count scores.

Three trials are development evidence, not statistical reliability or a user-benefit study.

## Closeout and immediate next cut

Summarize M1 preservation/authority, M2 structural authorship/failure/replay, and M3 observed quality
with exact scope, versions, failures and limits. Update state/build log/deferred entries and record
explicit owner acceptance before claiming stage closeout. Observed cost usefulness, bookability,
personal redeemability, provider reliability and full-workflow benefit remain separate claims.

The Ranking M2 export and its saved-example preservation checks are complete. Start Results M2.
Fallback breadth and numeric LLM settings can be
settled before their dependent M2 work. No provider acquisition or parked scope must be opened to
complete this design. Results M2/M3 remain unimplemented and unqualified; the Ranking export's
completed engineering evidence is recorded separately in its contract/build log.
