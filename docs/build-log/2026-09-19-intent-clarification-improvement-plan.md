# 2026-09-19: Deferred intent and clarification improvement plan

## Owner request and scope

The owner requested a critical, creative improvement plan for intent and clarification, using build
logs, traces, relevant design documentation, and agentic-system engineering guidance. The owner
explicitly requested parallel agent review and a durable link in `DEFERRED.md`, with implementation
to be revisited after building the core project.

This session produced advisory documentation. It did not reopen upstream implementation or live
qualification, change runtime policy, start 2C, or reopen 2B.

## Work performed

- Read current project state, the deferred register, active ADRs 0011 and 0014–0017, evaluation
  protocols, earlier architecture review, and relevant intent/clarification build logs and closeouts.
- Consulted the external workbook's product intent, workflow ownership, scope, and evidence sections
  without modifying it. Distinguished its original trip-shaped/cash examples from newer one-way
  product decisions.
- Used two investigator agents for initial-intent and clarification evidence, one architect for an
  independent product/architecture challenge, and a separate architect for critical review of the
  written plan. The parent integrated the evidence and recommendations.
- Investigators inspected existing public artifacts and selected private synthetic-evaluation
  traces, including one-way intent and clarification cases. No raw private payloads were copied
  into the plan, and no new live model/provider evaluation was run.
- Read primary engineering guidance from Anthropic on workflows, context, and evaluation, and
  Microsoft HAX on correction and disambiguation. Links and the limits of their application are
  included in the plan.
- Wrote a task-oriented plan covering bounded context, request revision, alternatives, question
  policy, composer comparisons, recovery, downstream constraint enforcement, and experiments that
  can reject unnecessary complexity. Kept trip-shaped interaction and adaptive control conditional.
- Updated D01, linked the existing G01 claim gate, preserved stable register IDs and disposition
  history, and added an advisory navigation paragraph to project state.

## Evidence and limitations

- Current continuation has four amendment targets and lacks accepted values/prior choices in its
  receiver projection. Initial intent has a broader fact vocabulary. These are code-inspected
  contract limitations, not measurements of actual traveler friction.
- The controller rejects new answers after `ready`; the plan proposes an explicit revision entry
  point with downstream invalidation, rather than mutating old plans or observations.
- The historical broad intent diagnostic's 46 post-inference pending outcomes belong to the
  retired wire defect. They were not presented as current behavior.
- The final exact-request gate is recorded as 10/10 in the September 11 build log. Its recorded
  private temporary artifact, `/private/tmp/award-search-exact-gate-10.json`, was absent at review
  time. The plan therefore cites the logged result without claiming a fresh artifact audit.
- ADR 0015's unsafe return cases and sibling-loss examples involving duration are historical after
  ADR 0016; they motivate supported-only regression families, not a current safety-defect claim.
- No new live behavioral or human usability evidence was generated. New example interactions,
  proposed pilot size, and experiments are explicitly proposals.

## Files changed

- Added [the improvement plan](../reviews/2026-09-19-intent-clarification-improvement-plan.md).
- Updated [DEFERRED.md](../../DEFERRED.md), retaining D01 and G01 identities.
- Added a navigation paragraph to [project state](../project-state.md).
- Added this build-log entry.

Pre-existing worktree changes and untracked review documents were preserved. No runtime, prompt,
fixture, dependency, workbook, or evaluation artifact was changed.

## Commands and verification

Read-only inspection used `rg`, `sed`, `git status`, and JSON inspection of existing artifacts.
The missing temporary artifact lookup was an evidence limitation, not a runtime test failure.

```text
.venv/bin/pytest -q tests/unit/test_intent_semantic.py tests/unit/test_clarification_controller.py tests/unit/test_clarification_session_contracts.py tests/unit/test_clarification_composer.py
```

Result: **49 passed in 0.35s**. These existing offline tests check portions of the frozen semantic,
controller, session, and presentation contracts; they do not validate the proposed interaction
design or qualify model behavior. No new tests were added for this documentation-only change.

Final documentation verification: a Python standard-library check resolved **75 local links and 22
heading anchors across all four touched files**, with zero link/anchor or trailing-whitespace errors.
`git diff --check` passed. Separate
`git diff --no-index --check /dev/null <file>` checks for the new plan/build log and the existing
untracked `DEFERRED.md` emitted no whitespace diagnostics (exit 1 reflects differences from the
empty file). Only the targeted documentation additions are attributed to this session; the wider
worktree diff includes pre-existing changes.
Independent written-plan review found no material evidence-table overclaim and recommended five
refinements. The integrated plan routes structured edits directly to deterministic validation,
separates the current baseline from summary/editing comparison arms, reuses existing identity checks
before adding a projection digest, qualifies correction support as nonterminal, and requires summary
labels to distinguish active/unresolved/unsupported/deferred-validation constraints. The review
requested no deeper escalation; future uncertainty requires user/provider evidence.

## Decisions and next cut

Owner decision recorded: prepare the plan now and revisit implementation after the core project.

Owner decisions on the first experiment, shared semantics, composer policy, question sequencing,
post-ready interaction, model choice, and qualification thresholds: **not yet recorded**.

The original plan recommended establishing a current task baseline and choosing one small context
or presentation experiment. The fresh Astra debate below supersedes that default priority with
failure-led selection. G01/G03 remain prerequisites for their associated claims;
deferring a broad redesign does not waive them. No recommendation was adopted as runtime policy.

## Fresh Astra challenge and parent debate

The owner subsequently explicitly requested a fresh Astra agent to contest the plan and discuss
its ideas back and forth with the parent before revision. A new `gpt-6-astra` agent was started
without inherited conversation history. It reviewed the written plan, repository instructions,
current state/register, selected workbook sections, active ADRs/contracts/controller, and relevant
evidence. It did not edit files, run live evaluations, or delegate further.

The parent inspected the challenged controller/receiver behavior, exchanged substantive objections
and counterproposals with Astra, revised the plan in place, and requested a final adversarial read.
The discussion changed the recommendation rather than merely approving its wording:

| Challenged presumption | Parent response and integrated resolution |
| --- | --- |
| A confirmed context limitation makes contextual corrections the natural first build | The parent defended context as a plausible candidate, but accepted that capability limits do not establish task frequency or cost. The plan now branches from current diagnosis and allows no upstream redesign |
| Grounding plus write eligibility makes context-rich correction safe | The controller turns eligible emitted facts into replacements, but cannot establish semantic correction intent. The plan now measures induced accepted errors and wasted provider work, with targeted review and recovery rather than a model self-certification flag or universal confirmation |
| Scope friction requires linked-trip semantics | The parent required explicit user acceptance and preserved the frozen one-way boundary. A future reviewed mock can offer a fresh outbound-only request without building a draft ledger or parent-trip planner; activation still requires an approved policy/contract and user choice |
| A fixed hidden request is the universal task oracle | Both sides distinguished known-intent reconstruction from human preference discovery. Exploratory decisions are recorded prospectively; prior errors cannot be excused by retroactively changing expected meaning |
| Structured context and forms are obviously simpler | The plan now compares minimal accepted state plus the actual question, with bounded recent text when useful; separates missing context from missing calendar operations; and includes original-goal translation effort, equivalent capabilities, and order effects in form comparisons |
| A long design menu can become a mandatory roadmap | The reopening sequence now diagnoses, tests one hypothesis, and adopts only justified behavior. Alternatives, discourse redesign, choice registries, shared schemas, richer salvage, and adaptive questions are explicitly not required for D01 completion |

The parent rejected automatic outbound-subset activation and any claim that a stronger model can
recover unavailable context. Astra agreed with both boundaries. The discussion also established
that a displayed/accepted reduced-scope draft does not fulfill the original trip request, a return-
dependent outbound fact cannot simply be copied, and undo cannot erase searches already executed.
The revised scope-recovery option remains D04; adaptive control remains D09.

Updated files in this follow-up: the plan, D01/D04 and disposition history in `DEFERRED.md`, this
log, and the advisory project-state paragraph. Other existing worktree changes were preserved.
No runtime, prompt, fixture, model setting, workbook, or evaluation artifact was changed.

Verification for the follow-up: the final Astra read found the substantive objections resolved.
Its remaining edits aligned the context stop criterion with the no-safety-regression rule and
removed two residual phrases suggesting context-first work was already selected; both were applied.
A Python standard-library check resolved **81 local links and 24 heading anchors across the four
touched files**, with zero link/anchor or trailing-whitespace errors. `git diff --check` passed.
Comparison with the session-start document snapshots was inspected; unrelated concurrent advisory
edits were preserved and are not attributed to this review.

The earlier 49 passing offline tests remain evidence for the unchanged runtime; they were not rerun
as a substitute for testing the proposed design. No new behavioral or human-usability evidence was
generated. Remaining uncertainty concerns task demand, model quality, induced errors, and usability;
the reviewer recommended no further architecture escalation.

Owner decision recorded: request the fresh challenge and revision. Adoption of any revised design,
scope policy, experiment, or implementation remains **not yet recorded**.

## Real-use-case and FDE preparation pass

The owner requested another high-level pass focused on real application use cases and AI/FDE
engineering preparation, followed by an adversarial Astra challenge. The parent first formed an
independent working thesis from the workbook, existing plans, and role-source research, then gave
that thesis and the current plan to a new `gpt-6-astra` agent without inherited conversation history.
The temporary thesis was working material; its recommendations were integrated into the existing
plan rather than made a second roadmap.

The parent read the workbook's user/workflow, learning-ownership, and interview-evidence sections
without editing it. Primary public role descriptions checked on 2026-09-19 were OpenAI FDSWE SF,
Anthropic FDE Munich, and Palantir FDSE NYC; the plan links each exact source. They inform broad
preparation themes, not a selected target-role list or universal hiring rubric. No application,
outreach, customer contact, or product-model/provider evaluation was performed.

### Challenges and revisions

| Initial parent idea or assumption | Adversarial challenge and resolution |
| --- | --- |
| A bounded flexible search is a promising default use case because it exercises language/date/geography work | Existing inventory filters may already solve it cheaply. Removed the default niche and the idea that ambiguity itself justifies AI; task families are controls, candidate value tests, conditional follow-ups, or scope-fit probes |
| Help the user find options worth investigating | This can evade a falsifiable usefulness claim. The plan now defines qualifying options versus bounded research leads before results, counts rejected leads and remaining verification, and labels manually prepared/replayed briefs |
| The useful unit is a changed decision | The parent defended reaching the same justified next action with less effort/error as real value; Astra agreed. Neither a changed itinerary nor a changed architecture is required |
| Preserve why constraints matter | Avoid a narrative-state subsystem without a consumer. Reasons stay in pilot notes unless a supported query, validation rule, or decision needs them in software |
| A six-step FDE case-study sequence | Replaced with three evidence lanes: task understanding, personally owned AI diagnosis/integration, and explanation/adaptation/handoff. Reuse existing failure evidence before inventing a fresh feature or experiment |
| Start with a small multi-session pilot | One actual task and one existing failure can start discovery. A larger qualitative round is optional when the next decision needs it; neither replaces G01 or establishes general value |
| A sophisticated personal project supplies FDE customer-delivery evidence | It can support technical learning within observed limits. Independent customer negotiation, enterprise deployment and sustained adoption remain unproven; a self-rehearsal and an engineer's handoff are also different evidence |

The parent and Astra agreed that a manually reviewed decision brief is a discovery instrument,
not authorization to implement ranking/provider work or proof of automated discovery. Manual task
context must be supplied prospectively and its preparation/checking cost reported. The parent also
rejected requiring a new design change merely to improve the portfolio narrative; an existing fix
or justified decision to retain/narrow the design can supply the lesson.

The plan now includes concrete task families, a short manual decision brief, existing-workflow
comparison, one personally owned diagnosis/adaptation exercise, a finite revisit budget/decision
date, and explicit role-evidence limits. D01/D14 and project-state navigation were updated without
adding register IDs, gates, runtime behavior, or an approved product segment.

Astra's final text audit found the substantive objections resolved and confirmed the role-source
paraphrases. Its optional wording fix changed a lead with one remaining check to a bounded set of
stated checks, avoiding an accidental product policy. No further escalation was recommended.

### Verification and claim limits

Final documentation verification: a Python standard-library check resolved **83 local links and 26
heading anchors across the four updated documents with zero errors**; `git diff --check` passed.
No runtime changes or new behavioral tests/evaluations were made. The earlier offline test result
is retained as historical verification of unchanged code, not evidence that these use cases work.
No actual user timing, task-value comparison, independent interview assessment, or hiring outcome
was measured. The owner requested this analysis and challenge; choice of user segment, experiment,
implementation, job target, and career next step remains **not yet recorded**.
