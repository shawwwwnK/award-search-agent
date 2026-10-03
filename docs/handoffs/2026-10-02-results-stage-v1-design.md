# Results Stage v1: evidence projection and grounded writing

Date: 2026-10-02. Status: **owner decisions recorded; remaining engineering details and milestones proposed**.

This document develops the owner's Results Stage proposal and records the subsequent decisions
below. Unsettled engineering choices remain proposals. No implementation or generated-answer
qualification is claimed. Ranking remains closed.
The [opening record](2026-10-02-results-stage-opening.md) supplies the inherited boundary.

The subsequent [detailed execution plan](2026-10-02-results-stage-implementation-plan.md)
refines contract boundaries and milestone slices using further investigation. It keeps audit
mappings out of the compact model view, stamps input binding in code, proposes code-rendered
explicit comparison sentences, and limits initial duplicate consolidation to the same observation
identities. Broader sketches below should be read with those specific refinements; all new
implementation choices remain proposals.

## Traveler decision and supplied direction

Help the traveler choose which observed journeys to investigate next, compare their tradeoffs,
and understand specific remaining checks. Consume one frozen `RankedJourneySet`; perform no
new searches, transfer research, bookings, upstream corrections, or style-policy changes.

The owner supplied these presentation standards:

- The LLM selects distinct highlights for speed, supported cost comparisons, editorial premium
  price appeal, useful style combinations, and meaningful alternatives. No overall score,
  best-overall designation, quota, or mandatory representative of every style.
- Conditional complete journeys can appear prominently, with their specific unresolved
  requirements beside them. Admitted and conditional journeys share the comparison pool.
- Show complete alternatives coherently, grouped around their award component; usually three
  highlights, up to five when useful, with one cash variant and at most one meaningful alternate
  per award option. Each variant retains its own facts and style labels.
- Preserve price scope, missing amounts, separate bookings, meaningful mixed cabins, dates,
  airline programs, observation times, and search limitations. Keep pure cash separate. Evidence
  references remain internal; traveler-facing citations are not required for current v1.
- A typical answer is about 300–500 words, with necessary conditions included in the answer.
- Without complete journeys, show up to two supported incomplete possibilities and what each
  lacks. Rejected combinations are explanations, never usable trips.
- The original proposal included a short factual summary on writing failure. Specific failure
  and fallback behavior remains to be discussed after clarifying the meaning of generation failure.

## Owner decisions after the initial review

2026-10-03: the owner clarified that the LLM must generate the main output and its structure,
leaving factual blanks for code. See the
[authored-template refinement](2026-10-03-results-stage-authored-template.md). This supersedes
the code-assembled answer structure proposed below; code owns factual substitution and checks.
The owner raised tool calls as a possibility, not an adopted requirement.

The owner accepted LLM authorship of the fuzzy/editorial content with code filling factual data,
award grouping with individually preserved cash variants and conservative duplicate cleanup,
and a maximum of five displayed complete journeys including alternates. Airline programs must
be clear; a traveler-facing source-label/legend feature is not required now.

The owner expects good input cleanup to keep the context manageable. Do not add a separate
input-size cap, overflow fallback, chunking architecture, or preselection policy to initial v1.
M1 should measure the actual cleaned saved inputs to check that expectation, retaining all
distinct alternatives. A real model context-limit error is a generation failure to record,
not permission to silently drop journeys.

The owner requested proper milestones and identified LLM-based evaluation as an additional
milestone. The [milestone plan](2026-10-02-results-stage-milestones.md) proposes M1 input
preparation, M2 selection/explanation plus factual output, and M3 LLM-assisted evaluation.
The specific one-call/no-repair recommendation and fallback breadth have not been accepted;
the owner asked what “writing” and “writing failure” mean before deciding those details.

Here, “writing” means one Results LLM operation that selects highlight IDs and produces the
opening, reasons to investigate, tradeoffs, and shared explanations. It does not supply the
authoritative route/price/time fields; code fills those from the selected journeys. “Writing
failure” means that operation cannot produce a usable response: for example timeout, refusal,
truncated/malformed output, or a selected ID absent from the brief. A valid empty-results answer
is not a writing failure. Fluent but misleading prose is a quality failure evaluated separately.

Time/cost/premium membership and cost assumptions remain those of the
[implemented M2 contract](2026-10-01-ranking-m2-styles-contract.md). Style labels describe
membership, not superlatives. Premium economy remains an additional choice, not Premium membership.

## Agreed authority and proposed flow

`RankedJourneySet -> ResultsBrief -> ResultsWritingPlan -> checks -> rendering -> ResultsArtifact`

The first step is a deterministic projection of existing evidence, not another ranking stage.
The model chooses and explains. Code renders factual journey details and material conditions
from the selected IDs. Retain original attachments outside the model context and bind every
projection and answer to them. A first implementation should be an explicit API/offline CLI,
with a narrow optional writer interface; integration into a broader workflow comes later.

This design reduces opportunities to splice variants or omit conditions. It does **not** prove
that unrestricted model prose is factually correct: editorial sentences can still invent facts
or implications. Mechanical validation and semantic evaluation have different responsibilities.

## Verified preservation and current evidence limits

Two read-only investigations and an architecture review examined the actual contracts and all
three saved result shapes. The documented M2 corpus verification passed on 2026-10-02 for all
three cases. The evidence chain is:

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

## Proposed typed records

Names below are proposed new Results contracts, not existing repository APIs.

| Record | Content and responsibility |
| --- | --- |
| `ResultsBrief` | Contract version, ranked-input digest, compact request, all distinct eligible complete alternatives, presentation groups, supplied comparison facts, separate cash observations, incomplete possibilities, relevant rejection summaries, planning explanations, coverage, internal evidence map, cleanup/accounting receipt. |
| `CompleteAlternative` | Stable presentation ID and original candidate/family IDs; intact award/cash observation links; chronological segments; endpoints and local dates/times; elapsed duration and waits; cabin evidence; program and scoped price components; unchanged status, concrete unresolved checks, style states, source and planning references. |
| `PriceQuote` | Component/observation ID; raw amount, currency and unit; observed/estimated/unknown state; traveler scope and traveler count where established; covered component; displayable amount only when units permit it; missing/conflicting evidence. Existing normalized heuristic values remain separate. |
| `ComparisonFacts` | Existing exact time minimum/ties and cost reference, where available; full comparison scope; membership states; supplied heuristic completeness and assumptions. No model arithmetic or new overall score. |
| Internal evidence map | Observation IDs mapped to provider, retrieval time, provider-updated time if reported, and existing evidence pointers. Retained for traceability and evaluation; no traveler-facing source legend is required. Provider retrieval time and inventory update time are different. |
| `ResultsWritingPlan` | Ordered selected alternative IDs; at most one alternate per award group; explanation prose and evidence references; explicit comparative-claim references; optional supported premium-price judgment; opening and shared-note prose; selected separate benchmark or incomplete IDs. The model does not author factual price/date/style fields. |
| `ResultsArtifact` | Self-contained rendered answer; selected IDs and internal evidence map; input/brief/prompt versions and digests; generation outcome and validation receipt. Failure/fallback handling remains to be settled. Raw model response and usage belong in the run evidence. |

### Projection rules

Join features and assessments by candidate ID, then the matching journey, its award/cash
observations, exact planning support, and evidence. Never select a price or timing independently
of the whole candidate. Include eligible candidates with no full style memberships.

Carry all supplied style states internally. Render Time/Cost/Premium labels only for definite
membership; explain a provisional cost possibility in words when relevant. Do not render an
unknown cost as Cost. Preserve unknown leg cabins even when M1 accepts journey-level award cabin.
An economy cash flight alongside a business award must be clearly identified.

Translate requirement/evidence unknowns into specific traveler checks using an explicit mapping
from recorded reason codes. Keep price limitations, ordinary reconfirmation, and separate-ticket
obligations separate from eligibility checks. A successful two-hour timing check does not establish
that bags, terminal changes, immigration, or check-in deadlines make the connection practical.
Unmapped material reasons must remain visible as recorded information, not disappear.

Recorded planning rationale is labeled as planning evidence and associated with the exact support.
Use request flexibility only when it is actually recorded. Never invent why an endpoint was
selected, or use a search hypothesis as evidence of a flight.

## Presentation grouping and duplicate cleanup

Existing `option_family_id` binds an award observation and planning support/topology. It is not
automatically a unique traveler-facing award option: repeated provider observations and different
supports can describe the same apparent schedule.

An award presentation group associates a common observed award with its separately retained
cash variants. Group membership does not require cash variants to share fares, schedules,
statuses, or styles. The strict equality rule below governs duplicate complete-alternative
consolidation, not membership in that award group.

Agreed direction: retain these family references, add a presentation-only group, and consolidate
only alternatives equal on every decision-relevant field: route/segments, instants, cabin evidence,
program, quotes and their scopes/units, status, unresolved checks, booking obligations, and style
assessments. Missing identity data is insufficient evidence of equality. Union source references
and original IDs; keep per-source observation times and any material differences visible.

Different programs, prices, scopes, schedules, cabins, requirements, or memberships remain distinct.
Do not merge contradictory observations or select the most favorable fields from them. Do not
introduce cross-source reconciliation or fuzzy schedule matching in v1. If strict equality leaves
duplicates, group for readability without asserting they are identical or rewriting M1/M2 identities.

Every original candidate must be accounted for as retained, exactly consolidated with aliases,
or excluded from the writing pool by its existing rejected/research status. There is no silent
pre-shortlist pruning and no skyline filter that removes distinct alternatives before the LLM.

## Selection and claim rules

The model may highlight a useful journey even without style membership. Its selection should
have a stated appeal and a meaningful difference from other highlights. Conditional status does
not reduce eligibility for selection.

- **Fastest:** only an alternative tied at the exact full eligible-pool time minimum supports
  “fastest among the complete journeys found.” Time membership alone is insufficient. Search
  coverage qualifications remain visible; this is not fastest across all possible flights.
- **Cheapest:** distinguish cash payable, points, and the heuristic cost. The existing rubric
  supports “lowest estimated comparison cost among options with complete cost information,”
  where justified; it does not itself establish the lowest cash price or cheapest travel in general.
  Incompletely priced alternatives can be cheaper and prevent an unqualified cheapest claim.
- **Heuristic:** when relied on, explain 100 points = USD 1 and any applicable USD 150 per-traveler
  tax estimate. These are comparison assumptions. Preserve actual observed quotes separately;
  unknown price scope still prevents a complete reference.
- **Premium price appeal:** an explicitly editorial judgment can cite a reported premium award
  quote. Identify its scope and missing costs beside it. With unknown traveler scope, avoid a
  per-person value assessment; at most describe the quote as potentially appealing pending that
  check. No current market benchmark, transfer eligibility, or redemption guarantee is supplied.
- **Savings:** no savings claim unless sufficiently comparable award/cash quantities and scopes
  support the specific comparison. A points valuation is not actual cash savings.

Owner-approved: count alternates toward a maximum of five displayed complete alternatives.
Usually use three primary highlights. The substantive limit is meaningful choice, not filling
available slots.

## Rendering and airline programs

Each highlight contains a short model explanation plus a code-rendered factual summary: route,
departure and arrival local dates/times, meaningful cabin differences, total duration and relevant
connections, program, points and monetary quotes with scope, style labels, separate bookings,
specific requirements, and observation timing. An alternate gets its own complete
summary and conditions, not a detached “cheaper/faster” teaser.

Shared traveler count, assumptions, common checks, and search limitations can appear once.
Journey-specific conditions stay beside the journey. Word count is a soft target; condition
coverage takes priority. Dates should be absolute; avoid calling saved observations “current.”

Clearly name the award program used for redemption and, where observed, the operating airline.
They may differ; do not confuse the two. When the program is unreported, say so. Retain existing
observation/evidence references internally for replay and evaluation. No inline source labels,
source legend, or booking-link feature is required in current v1. The self-contained answer
still includes essential facts, observation timing, and checks.

## Other outcomes and safeguards

Keep these dimensions independent: complete alternatives exist or not; provider coverage was
complete/partial/failed; generation succeeded or failed (and any fallback outcome if adopted).
One overloaded “success” flag would hide useful distinctions.

When complete alternatives exist, show the observed alternatives and describe actual coverage,
including partial searches. When none exist,
permit up to two observed award components or other supported incomplete possibilities, with
missing components/timing stated. A rejected pairing can inform the explanation but never be
relabeled as an incomplete viable journey. With no useful observations, state whether completed
searches found nothing suitable or failures prevented an answer.

Unsettled engineering recommendation: one generation invocation, no automatic prose-repair loop, explicit deadline
and token/output budgets selected before a live diagnostic. Count SDK retries separately from
application invocations; configure and record them. On timeout, malformed response, invalid
reference, prohibited selection, or failed mechanical check, discard the draft and render a short
factual fallback from validated source data. Mark this outcome in both artifact and receipt;
do not report successful model generation. A corrupt upstream artifact fails explicitly before
writing and cannot support a normal result-shaped fallback.

Fallback selection is a documented display rule, not a new ranking: one fastest complete candidate
with stable-ID tie-breaking and all its conditions; without one, one supported incomplete
possibility; otherwise a factual empty/failure summary. Mention partial coverage and omitted
alternatives as applicable. Broader fallback breadth is an open design choice.

For v1, compact without dropping distinct alternatives: factor common award details, consolidate
genuine duplicates, and remove irrelevant mechanics. Record cleaned input size on the saved
cases. The owner has not adopted an artificial input cap or overflow fallback. If measured
inputs or a real model error establish a size problem, report the evidence and revisit the
design; do not silently sample journeys or recalculate comparisons on a hidden subset.

Mechanical checks cover reference existence, original status and labels, grouping/alternate limits,
required condition inclusion, source validity, fact bindings, and superlative claim references.
They cannot prove arbitrary narrative entailment. Treat supplied provider/planning strings as data,
not instructions; the writer has no tools and cannot alter upstream state.

## Evaluation and execution milestones

The [milestone plan](2026-10-02-results-stage-milestones.md) is the execution proposal. The
sequence below supplies engineering and evaluation requirements within those milestones.

1. Verify information preservation and replay on all three saved M2 requests. Review one exact
   variant end to end: request -> support -> observations -> match -> styles -> brief -> answer.
2. Use the accepted authority, grouping, alternate limit, and airline-program presentation.
   Settle generation-failure handling and adapter settings as M2 engineering details.
3. Implement deterministic projection and factual rendering first, with offline behavioral tests
   for joins, source aliases, conditions, scope, dates, mixed cabins, and explicit failure paths.
4. Add a narrow structured writer and response validation. Unit tests use fake writers; no model
   or provider access is required. Test the generation-failure behavior once settled.
5. Build reviewed evaluation fixtures for overlapping styles; a prominent conditional option;
   opposing cash-price/time variants; missing taxes; unknown price scope; mixed cabins; premium
   economy; partial failure; incomplete-only; no useful results; malformed writing; conflicting
   duplicate evidence. Complete-cost cases are synthetic until observed
   provider evidence supplies adequate scope. Label that distinction.
6. Recommended bounded model diagnostic: three runs per case, frozen inputs, fixed prompt/model
   settings, recorded usage/attempts and raw responses. Selection variation is acceptable; every
   run is checked against the same factual boundaries. Live provider calls are unnecessary.
7. Human-review the rendered answer for useful distinct choices, concrete conditions, natural
   language, editorial-versus-observed distinctions, and usefulness without another view. Record
   hard failures separately from quality concerns, per case/run; averages cannot excuse them.

M3 adds a separate LLM evaluator against the cleaned brief, rendered answer, and deterministic
check receipt. It returns criterion-level judgments with specific answer passages and supporting
fact IDs. Its judgments are evidence for review, not proof of correctness. Calibrate it against
reviewed good and deliberately flawed answers, report missed failures and false alarms, and
inspect disagreements. Do not make it an automatic production gate or prose-repair loop in v1.

Hard failures are invented facts, mixed variants, wrong scope, changed eligibility/style, hidden
conditions, unsupported comparisons, rejected-trip promotion, false exhaustive-search claims,
and guaranteed-bookability language. Mechanical passes establish only their checkable scope;
semantic groundedness and traveler usefulness require reviewed answer evidence. Owner stage
acceptance is separate from implementation checks and broader provider/product qualification.

## Decisions to discuss next

- Settle generation-failure behavior and whether one attempt is sufficient for initial v1.
- Refine the proposed milestone boundaries and their completion evidence.
- In M3, select the evaluator model/prompt, reviewed calibration set, and reported criteria.

These are engineering/presentation recommendations. No price-scope assumption, new airport
rationale requirement, deferred topology, or provider acquisition expansion is approved here.

The opening record's rejection-over-fallback suggestion was explicitly unapproved. The owner's
newer factual-fallback direction takes precedence: reject an invalid generated draft, then
return a separately labeled deterministic summary when the source itself remains valid.
