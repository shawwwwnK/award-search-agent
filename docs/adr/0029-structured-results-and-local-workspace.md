# ADR 0029: Structured Results and a local flight workspace

- Status: Accepted product/ownership decision; U1–U3 backend implemented locally;
  frontend milestones and M3 remain planned, owner presentation acceptance open.
- Decision and recording date: 2026-10-23, on confirmation of shared understanding.
- Source: owner design interview Q1–Q23, architect challenge, and instruction to update
  docs and produce a complete plan. See the [interview/build log](../build-log/2026-10-23-results-frontend-design-interview.md).
- Execution plan and current Product Contract: [structured Results/workspace plan](../plans/2026-10-23-2334-feat-results-workspace-plan.md).

## 2026-10-24 implementation and diagnostic disposition

The owner subsequently invoked the implement skill through code review, live
evaluation/iteration and a current-branch commit. U1–U3 now implement structured
facts, observed/frozen currency handling, authoring/checking/bounded correction,
CLI inspection and replay. Workspace/resolved v2 adds source-known component
departure dates; saved v1 factual shapes preserve their exact fields/replay.
Outer artifact V6/document v2/prepared v5 stay unchanged because the downstream
fact shape has its own explicit version and is absent from the writer schema.

The three-round saved-case diagnostic records 14 generations/counts. Independent
review prompted meaningful source-framing, choice and date/airport corrections;
final unchecked declarations and wording limitations remain explicit. Two live FX
smoke invocations returned 403 and explicit fallback; positive acquisition remains
unclaimed. No travel-provider search, upstream policy change, frontend delivery,
M3 qualification or owner presentation closeout follows. See the
[implementation/evidence log](../build-log/2026-10-24-results-m2-structured-implementation.md)
and [diagnostic](../../evidence/results-stage/m2/structured/2026-10-24-luna/README.md).
This updates implementation status only; the accepted decisions and milestone
goals below are unchanged. Earlier uninvoked/planning-only wording describes the
original October 23 decision and October 24 preparation checkpoint.

## 2026-10-24 execution disposition

The owner opened U1–U3 Results M2 revision implementation in this session, first
requesting further subagent investigation, detailed implementation planning and
notice of milestone-goal changes. The preparation checkpoint refines the existing
plan without changing the accepted decisions or milestone goals. Runtime work and
verification are not yet claimed; frontend milestones and M3 retain their separate
scope. This supersedes the October 23 uninvoked-implementation status for U1–U3
only, not historical replay, qualification limits or later milestone gates.
See the [preparation log](../build-log/2026-10-24-results-m2-revision-preparation.md).

## Context

The owner rejected dense itinerary paragraphs, insufficiently convincing highlights and
hidden alternatives. Saved evidence shows that many journey variants are retained but
only a few appear in the answer. One October 20 answer highlighted two feeders for the
same economy award despite a business-cabin alternative. More cards alone would not
explain the meaningful choice. A flat catalog could also overstate diversity by presenting
combinations as independent flight discoveries.

The existing Results contract gives the model visible-layout control and requires
source-bound Markdown slots, status and condition text. The owner now wants consistent
flight displays, a complete explorer and a structured answer that can also be inspected
as text. Existing matching, styles and verified same-project input remain trusted.

## Options

1. Continue improving self-contained Markdown and merely add more prose recommendations.
2. Make a complete search list primary and leave most comparison work to the traveler.
3. Combine model-authored recommendations, reusable source-resolved flight data and an
   independently complete explorer in a local frontend.

The owner selected option 3. For factual objects, model-copying complete flight facts was
considered against model-selected exact references resolved by code; the owner selected
reference resolution. Pydantic was an example, not a prescribed technology. A separate,
equally important authored text answer was rejected in favor of inspecting the same
resolved data as JSON or another readable structured representation.

## Decision

### Ownership and recommendation

Ranking continues to own matching, overlapping time/cost/premium styles and the reusable
`SolutionProjection` under ADRs 0024/0025/0027. No overall scoring, eligibility penalty,
style quota or new matching verifier is introduced.

Results owns a structured authored answer: the model selects exact existing options,
organizes narrative and explains tradeoffs. It briefly explains the significant choice
landscape, including a notable unselected alternative when that changes the decision.
The policy does not require an inventory of every omission or a fixed option count.

Code resolves reference entries into flight data from the trusted projection, performs
supported arithmetic/formatting, and checks source association and scoped claims. The
frontend owns consistent factual displays and exploration controls; the model retains
narrative composition and recommendation selection. Exact data types, schema library,
frontend tooling and transport remain implementation choices.

### Presentation and exploration

Use a dedicated workspace alongside conversation, switchable on small screens. The
explorer includes every internally admitted/conditional journey in the bounded run,
independently of model selection or authoring success. Keep internal identities,
statuses, reasons and source bindings. Group related awards without dropping variants
or inventing physical-flight equivalence. A group representative is an actual journey,
never a composite of one member's price and another's schedule. Recommendation links
open the exact discussed variant.

Initially order groups by their shortest surviving complete journey. Explicit supported
sorts distinguish duration, departure, comparable complete cash totals, points within a
program, and the existing labeled heuristic comparison cost. Missing or incomparable
prices never count as zero or establish cheapest. Filtering selects representatives
from surviving variants and never automatically regenerates the recommendation.

Show route/date, local departure/arrival and day changes, whole duration, connection
airports/waits, cabin, program, scoped points/cash and material booking/pricing facts.
Details expose component legs, carriers/numbers, price/cabin evidence, sources and
freshness. Shared flight data may use compact and expanded displays. Do not invent
unknown connection times or treat the cash/award transfer duration as every layover.

Do not expose admitted/conditional labels or condition checklists. Preserve material
facts such as separate bookings, incomplete prices, unknown quote scope and cabin
limitations. Replace the old presentation obligation to enumerate internal requirements
with shared guidance that some results are not real-time and availability/current prices
must be confirmed on official booking sites. This does not authorize affirmative claims
of current seats, complete prices or protected connections. Internal evidence remains
available to the agent.

Direct cash stays a separate benchmark, outside award ranking/exploration. Incomplete
observations may appear as potential leads with missing information explained; they
must not masquerade as complete journeys. Existing coverage/exclusion facts support
the agent's explanation; a dedicated coverage-analysis subsystem is unnecessary.

### Currency and follow-ups

USD is the primary monetary display, with converted values marked approximate and the
original amounts/scopes, rate and timestamp available in details. One dated rate
snapshot belongs to each run and is shared by Ranking and display; saved runs retain
their original snapshot. Missing rates leave original-currency amounts visible.
Points valuation and the existing estimated-tax fallback remain heuristic inputs,
not observed payable cash. A currency API/vendor is an implementation choice.

Explicit follow-up questions may invoke an agent using existing retained evidence and
same-run option references. No planning, travel-provider search, FX refresh, reranking
or request mutation occurs in follow-ups. The agent states evidence limits. There is
no new Q&A/controller framework. User-requested conversational changes followed by a
new search remain deferred under D01; autonomous control remains D09.

### Local execution and historical evidence

This is accepted design for a local development frontend, not a deployment decision or
implementation invocation. Reuse the existing application pipeline for initial request,
clarification and explicit execution. Preserve ephemeral state, revision binding,
invalidation and no-call ordinary rendering. No production UI, authentication,
persistence or product multi-agent orchestration is opened.

Introduce new explicit structured document/prepared/artifact versions at implementation.
Keep historical V1–V5 Markdown contracts, request-schema digests and replay behavior on
their original paths. Share fixed bounded authoring orchestration where semantics match:
one initial call, at most one correction for a recoverable draft with failed checks,
fewest material failures retained with correction winning ties. An unrecoverable writer
failure remains an authored-answer failure while valid evidence stays browsable.
New presentation from historical source is a derived preview, not exact replay of the
old answer. Regeneration is a new invocation, including for follow-up prose.

### 2026-10-23 milestone allocation

After reviewing the complete plan, the owner accepted this stage sequence:

1. **Results M2 revision:** U1–U3 implement structured facts, consistent FX/USD
   presentation and structured authoring/checks/replay.
2. **Frontend M1:** U4 delivers the saved-results flight display and explorer.
3. **Frontend M2:** U5–U6 connect initial workflow execution and evidence-only
   follow-up conversation. Results retains follow-up evidence/answer-policy
   ownership; Frontend owns the interaction and integration.
4. **Results M3:** evaluation and acceptance after the integrated experience is
   available, with U7 supplying review evidence rather than automatically closing
   the stage. Prepare cases, expected facts and criteria during the M2 revision.

This chooses explicit Results/frontend milestones over treating M3 as all
LLM-related implementation followed by an undifferentiated frontend stage. It
preserves M3's evaluation meaning and makes the rendered experience available for
its final assessment. The stage allocation is accepted; implementation and M3
execution remain uninvoked. At M3 opening, adapt its earlier evaluator contract
to the structured/frontend output and declare scope/cohort and any live-call
budget. Historical proposed diagnostic counts are not automatically authorized.

## Consequences and supersession

For the new structured channel only, this supersedes ADR 0026's exclusive model control
of factual layout, self-contained Markdown delivery, visible eligibility/requirement
obligations and prose-slot completeness requirements. A generic footer is not retroactive
fulfillment of those old checks. New checks must target the resolved structured facts,
visible components and scoped claims. Historical artifacts keep their old obligations.

The October 20 compact-input preservation decision remains: every eligible option stays
selectable, canonical evidence stays complete, and source-member identity is not merged.
ADR 0027's Ranking ownership/upstream trust and ADR 0028's explicit-event local execution
and invalidation principles remain unchanged. A local frontend successor may reuse the
pipeline, but the new transport and follow-up path do not yet exist.

Results M2 presentation acceptance remains open. The October 8 engineering closeout is
historical for its declared boundary; M3 remains planned. New schema/checker/frontend
implementation and any later live diagnostic need their own evidence. Planning is not
implementation or a live-call budget.

## Evaluation

Use complete saved admitted/conditional/incomplete cases and independently specified
controls for price scopes, multiple connections and missing data. Verify full eligible
accounting, exact variants, group representatives, original/converted money, no-call
browsing, explicit initial-run execution, evidence-only questions and historical replay.
Review the duplicate-feeder/business alternative for actual selection usefulness.

Owner visual/choice review, mechanical checks and broader task benefit are separate.
No new runtime tests, paid generations, provider calls, FX acquisition, usability result
or M2/M3 qualification follows from this documentation session.

## Revisit triggers

Revisit if the structured answer cannot preserve model narrative freedom or source
association, grouping hides material alternatives, context cannot retain the comparison
scope, material caveats become unreadable, or saved-run conversion/replay changes.
Request revision/re-search, fresh follow-up acquisition, new Ranking policy, public
delivery or persistence requires an explicit scope decision rather than UI drift.
