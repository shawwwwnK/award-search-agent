# Results M2 design grilling — 2026-10-06

Status: interview in progress; no implementation, qualification, model/provider calls or stage closeout.

## Work and owner answers

Applied grill-with-docs via grilling and domain-modeling. Read current project state, M2 opening,
Results design/contracts/milestones/execution plan, ADR 0026/0027 and ADR guidance, relevant workbook
product context, and the deferred register. No glossary existed at session opening.

Round 1 presented six independent questions and recommendations. The owner answered:

1. “M3 is more an evaluator (give metrics on output quality), not a validator (rule out invalid
   results). We need to converge on a proper validation logic and fallback for M2.” The owner
   reaffirmed “the flow needs to flow” and “it shouldn't error out or produce no results”.
2. Accepted scoped authored parts and visible identification when a journey resumes after another.
3. Expected capped searches and irrelevant-field cleaning to avoid fitting issues; accepted the
   recommendation to measure complete cleaned input and explicitly record residual context limits.
4. Accepted Q4's recommendation of initial explicit failure without factual fallback. This conflicts
   with answer 1; delivery semantics remain open rather than resolving the conflict by inference.
5. Allowed multiple materially distinct choices per award group; model justifies and avoids redundancy.
6. Accepted visible decision-changing facts/conditions, shared identical disclosures where clear,
   detailed provenance in artifact, observation dates visible and precise times when material.

## Documentation and ADR disposition

Amended ADR 0026 with accepted directions, alternatives, supersession scope, limits and the open
fallback conflict; updated ADR index, current Results handoffs and project state. Created a minimal
Results glossary with validation/evaluation and presentation terms. No runtime behavior changed.
No newly deferred feature or disposition change was established; existing user changes in DEFERRED.md
and the untracked October 4 evaluation-audit log were preserved.

Commands used: cat, sed, rg, git status --short, documentation-editing Python script,
and git diff --check. Documentation inspection checks are recorded after execution below.
Behavior tests are not applicable to this documentation-only interview; no historical tests rerun.
`git diff --check` passed. Inspected the selection-policy replacements and current-state diff;
searched active contracts for residual primary/alternate caps. Earlier validation/repair proposals
remain explicitly subordinate to the dated amendment pending the next interview decisions.

## Remaining frontier

Resolve continuity versus terminal generation failure, semantic-validation authority and false
claims beside correct facts, and permitted fallback authorship. Dependent repair/attempt settings,
exact resumed-scope/disclosure checks and numeric writer/live budgets follow those decisions.

Owner final shared-understanding confirmation and implementation authorization: pending.

## Round 2 — 2026-10-07

Owner answers: Q7 accepted grounded fallback delivery with generation-failure evidence retained;
Q8 proposed claim enums plus deterministic checks, asking whether this avoids overconstraining
semantics; Q9 rejected code-owned fallback layout and clarified API failures are system errors,
whereas validation errors should not stop the flow. Q9 refines Q7; no deterministic fallback
layout or semantic model-validator was adopted.

Amended ADR 0026, its index, active handoff notices and project state with these accepted boundaries.
Claim-enum design remains a proposal. No new glossary term was settled. Read Ranking contracts and
projection code: mixed journeys carry separate_tickets_unverified; journey-level cabin and reported
leg cabins are separate evidence. Neither admission nor a single-award booking proves connection
protection. An initial lookup of solution_contracts.py failed (no such file); rg --files located
projection_contracts.py and project_solutions.py. No runtime changes or live calls.

Remaining frontier: claim-to-prose coverage, unknown/false claim treatment, and bounded recovery
when repeated validation fails. Fallback selection and call settings depend on those decisions.
ADR disposition: accepted October 7 amendment, mechanics explicitly proposed/unsettled.

## Round 3 — 2026-10-07

Owner accepted claim-bearing span binding with model-owned wording and the explicit residual
semantic gap. They directed defining important deterministic claim logics, allowing unknown to
pass by default when no important check applies, and using M3 findings to inform future checks.
They rejected terminal validation/recovery errors: after calls, output results with validator
failures stitched on in customer-appropriate language; validation failures are not system errors.

Amended ADR 0026, index, project state, active contract notices and glossary. The added notices
are recorded as a narrow exception to the earlier no-code-added-content rule; exact placement
remains open. No runtime semantic judge or automatic catalog expansion was authorized. No
behavioral code, tests or model/provider calls. Existing unrelated changes remain preserved.
Read Ranking projection contracts to ground further questions in cabin/leg, quote-scope, booking
and comparison evidence. Next frontier: failed-claim notice association, unrenderable drafts,
unchecked versus checked-but-insufficient evidence, and initial check catalog/repair budget.
ADR disposition: accepted Round 3 amendment; engineering mechanics remain unsettled.

## Round 4 — 2026-10-07

Owner accepted Q13–Q17: separate unchecked/insufficient_evidence non-blocking outcomes; affected
claim/journey notices; recoverable-content preservation with unavailable references; five initial
claim families (cabin, protection, quote scope, comparisons, eligibility); one initial invocation
plus at most one correction, retaining original recoverable draft on correction API failure.
They explicitly classified no-recoverable-document/schema errors as system/generation failures
and required development testing. This records a requirement, not successful test evidence.

Amended ADR 0026, index, glossary, active contract notices and project state. No runtime changes,
behavior tests, model/provider calls or changes to unrelated owner files. Documentation checks:
git diff --check passed after edits; recorded decisions inspected against answers Q13–Q17.

Remaining interview frontier: disclosure omissions after correction, rejected/over-limit selections,
and selecting the retained draft when correction makes outcomes worse. Writer/model/token/timeout
and live settings follow prepared-input measurement; offline authoring does not require guessed
numbers. Final shared-understanding confirmation and implementation authorization remain pending.
ADR disposition: accepted Round 4 amendment; remaining policy choices explicitly open.

## Round 5 — 2026-10-07

Owner accepted Q18–Q20: notices supply known omitted disclosures; count is a soft target (the
owner explicitly said five or six is arbitrary and need not be followed); rejected candidates
remain visibly excluded without promotion; retain the recoverable draft with fewer unresolved
material failures and prefer correction on ties, excluding unknown outcomes from failure counts.

Created the consolidated October 7 M2 validation/recovery/delivery contract, shortened accumulated
active-contract notices to one current-policy pointer, updated central count rules, and amended
ADR 0026/index/project state. Previous rounds remain as dated decision history. No behavioral
implementation, tests, live calls, commits or upstream changes. No new deferred work or disposition
change; existing unrelated DEFERRED.md and evaluation-audit-log changes remain preserved.

The current interview policy frontier is empty. Exact claim-span/render serialization and fixture
implementation are engineering work. Writer/model/token/timeout/live settings await offline input
measurement rather than guessed values. Final shared-understanding confirmation remains pending;
this interview does not authorize implementation or live calls.

ADR disposition: Round 5 amendment to ADR 0026 with options, accepted decisions, supersession scope
and evidence limits; no new ADR ID required. Verification commands/results are recorded below.

Final documentation verification: `git diff --check` passed; a read-only Python local-link
inspection checked 137 targets across nine current documents and found none missing. Read the
consolidated contract and latest ADR against Q18–Q20; replaced obsolete single-call/no-repair,
terminal missing-disclosure and open deterministic-fallback passages in active contracts.
An `rg` sweep for old hard-five/no-repair/open-fallback language found only explicit supersession
notices. M3's historical single-call arithmetic is explicitly flagged for revision before an
evaluation budget is declared. No behavioral tests are applicable to these documentation edits;
no earlier test evidence was rerun or expanded. No remaining interview policy question was identified;
final shared-understanding confirmation, engineering work and measurement-dependent settings remain.
