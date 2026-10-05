# Results Stage v1: model-authored answer with grounded facts

**Owner-approved boundary revision, 2026-10-04:** reusable factual projection now belongs to the
[Ranking M2 export extension](2026-10-04-ranking-m2-solution-export.md). Results directly consumes
its compact view and owns presentation grouping, factual slots/disclosures, model-input formatting
and authored answers. Earlier `ResultsBrief`/M1 projection references below describe the factual
content required, not a second Results-owned transformation or standalone milestone.

Date: 2026-10-02; revised 2026-10-04. Status: **owner direction recorded; reviewed engineering design, not implemented or qualified**.

The LLM controls the answer's structure and prose. Code binds and fills facts and checks the
completed document. The owner reaffirmed structural control during the October 4 review.
This revision replaces the old code-assembled editorial-plan sections throughout the active design.

Read this document for product scope and authority, the
[authored-template contract](2026-10-03-results-stage-authored-template.md) for structural freedom
and fact scopes, the [execution plan](2026-10-02-results-stage-implementation-plan.md) for concrete
contracts/gates, and the [milestones](2026-10-02-results-stage-milestones.md) for sequencing.
The [review record](../reviews/2026-10-04-results-stage-design-review.md) distinguishes findings,
engineering recommendations and remaining owner choices. Historical opening/build logs retain
their original status; they are not competing active contracts.

## Traveler decision and owner direction

Help a traveler decide which observed award-led journeys to investigate next, understand their
tradeoffs, and identify the remaining manual checks. Consume the factual solution view exported
from one frozen `RankedJourneySet`, with its source receipt retained internally. No new searches,
transfer research, bookings, upstream corrections or ranking-policy
changes belong to Results.

The accepted direction is:

- The model authors headings, order, grouping, paragraphs, tables, emphasis and explanations.
  Code has no normal-answer skeleton or section order and does not append missing conditions.
- Highlight useful distinct complete journeys, usually three, with at most five including
  alternates. Successful authorship selects at least one when complete alternatives exist.
  One primary per observed award group and at most one meaningful cash alternate
  from that group. Do not fill a style quota or invent an overall score/best-overall winner.
- Admitted and conditional complete alternatives share the selection/comparison pool. Specific
  requirements remain visible; a style label does not certify a condition or connection.
- Keep award programs clear, price scope/unknowns, meaningful cabin differences, separate bookings,
  dates, observation timing and search limitations in the answer. Evidence links remain internal;
  no traveler-facing source legend is required. Pure cash stays a separate benchmark.
- When there are no complete journeys, allow at most two supported incomplete possibilities with
  missing pieces stated. Rejected combinations cannot become viable recommendations.
- Aim for 300–500 words when useful; facts/conditions take priority. The model chooses their
  presentation. No hard input cap, hidden preselection or multi-pass selection is adopted.
- Clean and factor the full input; consolidate only true duplicates and preserve every distinct
  alternative. Measure the complete cleaned inputs before proposing an overflow architecture.

The original proposal contemplated a short factual summary if authoring fails. Exact fallback
breadth, retry settings and numerical call budgets were not owner-decided. The revised execution
plan recommends a concrete call policy and records fallback as an open choice. It does not
reinterpret a failure fallback as permission for code to structure successful answers.

The older workbook's 5–10 choices, source-link feature, weighted ranking, round trips and symmetric
cash scope are historical broader thinking. Newer owner decisions/ADRs govern this narrower stage;
no workbook edit or reopening follows. Ranking's original closeout remains evidence for its
declared boundary; the October 4 export extension adds the factual handoff described above.

## Authority and flow

```text
Frozen RankedJourneySet + source evidence
  -> Ranking M2 project_solutions()
  -> SolutionView + private ProjectionReceipt
  -> Results M2 slot/disclosure preparation on that same view
  -> one LLM-authored ResultsDocument
  -> document/slot/visible-content checks and literal factual substitution
  -> ResultsArtifact
```

The LLM selects complete alternative IDs and controls all supported Markdown structure. The
structured response includes a selection manifest and ordered Markdown parts with invisible fact
scopes. A scope may repeat in different positions; even comparison-table rows can be separate
parts. Code concatenates exactly, with model-written separators. Scope metadata creates no visible
card, heading or section. This supports layout freedom while preventing a slot from looking up
another journey's fare. Arbitrary prose and juxtaposition still need semantic evaluation.

Code owns source acceptance, stable IDs, joins, conservative grouping, required factual content,
allowed comparisons, single substitution, visible disclosure and exact replay. It never changes
admission/styles, manufactures scope/cabins, or silently repairs an invalid document's layout.
The first implementation is a narrow local API/CLI; broader workflow integration is separate.

## Input trust and information preservation

On 2026-10-04 the owner settled input authority: Results trusts the verified upstream output
produced within this project. The proposed additional matching-owned requirement verifier and
pinned-fixture alternative are dropped from Results scope. Results preserves upstream statuses,
styles, conditions and cost limitations without rederiving matching or ranking policy.

Use the existing typed input contract and resolve the references needed for projection; malformed
input or unresolved references remain explicit errors. Record source identity and versions for
traceability. See the
[preservation contract](2026-10-02-results-stage-implementation-plan.md#input-authority-and-independent-preservation-checks).

Independent source-backed assertions test quotes, variants, local dates, unknowns and required
conditions. A writer and judge that share the same incorrect projection can otherwise agree.
These assertions verify the Results transformation against the trusted input; they do not add a
second verification of upstream eligibility.

## Verified preservation and current evidence limits

Two read-only investigations and an architecture review examined the actual contracts and all
three saved result shapes. M2 corpus verification passed on 2026-10-02 and was rerun successfully on 2026-10-04 for all
three cases; 50 focused M1/M2/corpus tests also passed. Results uses those upstream outputs as
trusted inputs under the owner's decision above. The evidence chain is:

| Needed information | Existing source | Results work or limitation |
| --- | --- | --- |
| Request and supported flexibility | `MatchedJourneySet.request: EffectiveRequest` | Project supported fields and relevant recorded constraints; do not reactivate unsupported ones. |
| Complete variant identity | `MatchedJourney.candidate_id`, observation IDs, support/dependency IDs; M2 features/assessments | Join by exact IDs. Family IDs omit the cash observation but retain award/support identity. |
| Prices and heuristic assessment | `ProviderObservation` raw fields and `price_scope`; `JourneyCost.components`, completeness and missing parts | Observation-wide scope applies to source amounts; separate points/fee scopes are not currently recorded. Do not manufacture finer scope. |
| Requirements and booking checks | `MatchedJourney.reasons`, `booking_obligation` | Map reason codes/dimensions to traveler language. Price/booking/cabin unknowns do not automatically imply conditional eligibility. |
| Route, time and cabin | Component observations and `ObservedLeg`; M2 exact elapsed time | Saved cash rows lack detailed legs and confirmed cabin. Endpoint schedule/stops/carriers are available. Unreported award-leg cabins remain unknown. |
| Sources and timing | `ProviderObservation.evidence`, `retrieved_at`, `provider_updated_at` | Build compact registry; local evidence paths are not booking links. Preserve component-specific times. |
| Coverage and failures | `ProviderResultSet.coverage`, coverage units and findings | Derive a meaningful compact summary; omitted work cannot be described as empty. |
| Planning rationale | Attached `CompiledSearchPlan` strategies/support; journey positioning reason | Supplemental rationale exists. Endpoint M2A proposals retain codes without per-airport narrative reasons. |
| Cash, incomplete and rejected outcomes | Direct-cash IDs, summary/unmatched observation IDs, original journeys/reasons and pairing receipts | Separate pools; an incomplete presentation cannot launder a rejected combination. |

Relevant code: [M1 contracts](../../src/award_agent/ranking/contracts.py),
[M2 contracts](../../src/award_agent/ranking/style_contracts.py),
[provider contracts](../../src/award_agent/providers/contracts.py),
[compiled plan](../../src/award_agent/search_planning/compilation_contracts.py), and
[endpoint selector](../../src/award_agent/search_planning/airport_selector.py).

The [saved corpus](../../evidence/ranking-stage/m2/README.md) retains 992 candidates: 427
admitted/conditional and 565 rejected/research records. All 427 eligible cost assessments are
undetermined; no request has a complete cost reference. All provider result sets are partial.
These are candidate counts, not unique flight schedules. No new upstream collection is required
to write an honest bounded answer; absent cash cabins/legs and endpoint rationale remain absent.
Recovering them would be separate work with its own evidence and scope, not implicit cleanup.

### Concrete saved-result walkthrough target

Start with `sfo_to_bkk_positioning`: 64 eligible variants in four existing award/support families,
including five admitted cash-egress variants. The shortest complete reference is 27h27 from a
conditional access journey. The Time threshold is 32h56m24s; 22 variants qualify, including all
five admitted egress variants. The longest admitted egress variant is 32h25 with an 8h55 SIN
transfer. It earns Time membership without establishing that its wait is convenient or that
it is fastest.

A reviewed projection should expose the conditional fastest alternative alongside useful egress
alternatives, retain each one's own transfer and fare, show cash cabin as unreported, and include
separate-booking checks even for admitted variants. It should make no Cost label or cheapest
claim. Coverage includes 19 completed, one partial and 53 omitted units; explain the meaningful
uncompleted work rather than treating 73 units as 73 unsuccessful searches.

The other walkthroughs test different decisions: `mixed_access` separates five Time members
from 120 conditional Premium variants; `exact_business` has 106 eligible conditional Premium
variants, 34 of which also earn Time. These existing assignments supply useful design cases,
not yet evidence that an LLM selects or explains them well.

## Contracts and conservative cleanup

| Contract | Responsibility |
| --- | --- |
| Ranking `SolutionView` | Compact factual view: request, shared components/costs/reasons/styles, all complete and excluded alternatives, comparisons, separate cash, incomplete observations and coverage. Consumed directly by Results. |
| Ranking `ProjectionReceipt` | Source/view digests and versions, original candidate/observation links, technical provenance, raw local strings and coverage mappings. Kept outside model context; v1 retains every candidate without aliasing. |
| Slot catalog/obligations | Versioned coherent facts and the information each selected scope must visibly disclose, including price limitations and practical booking checks. |
| `ResultsDocument` | Model-selected manifest and ordered scoped Markdown parts. All headings, prose, order, grouping and separators are authored by the model. |
| `ResultsArtifact` | Filled answer, accepted document, selections, source/slot map, validation and independent source/search/generation/delivery outcomes, versions/digests and replay evidence. |

Group by exact award observation identity and original endpoint pair; preserve support, topology
and original family references internally. Grouping is a presentation association, not proof that
cash variants are interchangeable. Initial exact duplicate consolidation requires the same award
and cash observation IDs and equality of all decision-relevant facts, status, styles, conditions,
quotes/scopes and meaningful planning limitations. Union aliases/evidence without choosing favorable
fields from contradictions. Do not merge distinct observation identities in initial v1.

Account for every candidate as retained, alias, rejected or research-only, with separate accounting
for unmatched/summary and direct-cash observations. No hidden pruning or skyline filter. The saved
427 eligible candidates contain zero repeated award/cash observation pairs; factoring repeated
components, not deletion, supplies the demonstrated reduction. Earlier probe byte sizes are
incomplete exploratory measurements, not complete brief token counts or proof of context fit.

## Claims and factual disclosure

- **Fastest:** only an exact full eligible-pool minimum/tie supports a qualified fastest statement.
  Time membership alone does not. Preserve conditional requirements and observed-pool scope.
- **Cost:** the existing sufficiently complete heuristic reference supports only its stated
  comparison. Disclose 100 points = USD 1 and applicable USD 150 per-traveler unknown-tax estimate.
  Partial/unknown scope does not become a total, lower bound or Cost label. Results adds no new
  FX, pairwise valuation, savings arithmetic or weighted score. All saved Cost states are undetermined.
- **Premium appeal:** editorial interest in a quote remains conditional on missing scope/cost facts.
  Do not imply personal redeemability, market value, transfer eligibility or guaranteed inventory.
  Premium economy remains distinct from Premium membership.
- **Program/cabin:** redemption program differs from operating airline. Show only reported carrier
  evidence; preserve journey/leg/cash cabin distinctions and positive supplied mixed-cabin evidence.
  A requested cabin is not observed; journey-level acceptance does not confirm each leg.
- **Conditions:** ordinary reconfirmation, eligibility unknowns, price limitations and separate-ticket
  obligations have different meanings. Even admitted mixed journeys retain practical transfer checks.
  A passed two-hour timing rule does not establish baggage/immigration/terminal feasibility or protection.
- **Dates/freshness:** use validated instants and airport timezones, with absolute local dates and
  date-line changes. Preserve component-specific observation times. Raw local `Z` strings are not
  blindly treated as UTC. Saved observations are not called current.

The separate direct endpoint cash anchor from ADR 0022 must be addressed. Show a suitable observed
quote separately with limitations, or state the supplied missing/unsuitable benchmark outcome.
Unknown scope can support an indicative quote; it cannot establish award savings. Do not promote
cash into the award/style pool or trigger new acquisition.

## Structure, validation and failure

Use coherent factual slots rather than bare unqualified numbers. Derive visible-content obligations
from source facts; let the model place them. Every selected journey needs its own scoped facts and
conditions even when shown as an alternate or split across a table and later prose. Shared facts
may appear once if their applicability is clear. Code checks the final concatenated Markdown and
slot source map; a token hidden across comments/code/links does not count as disclosure.

Use a tested Markdown subset and escape source strings as literal text. No recursive template
execution, raw HTML, links/images or hidden content in initial v1. This is a proposed local
rendering contract, not a production Web UI. Missing content invalidates the draft; code does not
insert a fixed corrective section. Mechanically valid prose can still mislead through a heading
or comparison, so M3 evaluates the filled visible document and its implications.

Recommend one strict structured response carrying that document. This preserves freeform Markdown
inside a typed envelope; it does not require a function/tool loop. The API choice follows
[official Structured Outputs guidance](https://developers.openai.com/api/docs/guides/structured-outputs)
and remains an engineering recommendation. Prompt/schema/model settings, finite attempt/deadline
and output configuration, refusal/incomplete handling, private trace boundaries and replay are
specified in the execution plan. No model is selected without Results-specific evidence.

Separate source errors, genuine empty/partial search evidence, generation errors and delivery
outcomes. Invalid source cannot support a factual fallback. Refusal, truncation, transport errors,
invalid document and context exhaustion never become successful generated answers. The proposed
single invocation has SDK retries disabled and no repair loop; numerical budgets are recorded
before calls. A labeled factual-summary fallback remains an open choice. No normal answer is
streamed before all document checks complete.

Exact replay reconstructs the saved accepted document with the same brief/versions and zero LLM
calls. New generation creates a new artifact; it does not promise identical words or selection.
No input cap or silent truncation is introduced. Measure actual complete prompt/schema size and
report fit failures before revising the approach.

## Milestones and evidence

**Ranking M2 export** produces complete coherent input from trusted upstream output and checks projection preservation.
**M2** implements the LLM-authored document/factual-substitution boundary and demonstrates actual
answers and explicit failure handling. **M3** calibrates an advisory LLM judge and evaluates
repeated filled answers with human review. Fixtures and semantic criteria start during M1/M2;
there is no runtime judge or automatic prose-repair loop.

The existing 12-case, three-trial diagnostic remains a bounded development proposal. Correct
controls, planted failures, actual exercised-family predicates, independent held-out judge labels,
all failed-attempt denominators and human adjudication are explicit. Reuse compatible M2 outputs
instead of duplicating model calls. Structure variability is allowed; false factual implications
are not. The milestone plan defines completion evidence without claiming general reliability.

Before M2 acceptance, settle fallback breadth versus explicit delivery failure; before live
calls, record model choices and numerical timeout/output/campaign budgets. Offline M1 and M2.1
can proceed independently. These are remaining engineering/presentation choices, not reasons to
reopen frozen request, planning, provider or ranking policy.

Stage closeout requires owner review and explicit acceptance of the declared evidence and limits.
It does not establish personal redeemability, live bookability, observed-cost usefulness, broader
provider qualification or full-workflow task benefit. D06, broader D15 topologies and D18 acquisition
expansion remain parked. This review updates design only.
