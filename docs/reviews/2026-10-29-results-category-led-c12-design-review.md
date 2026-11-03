# C12 fresh design review: make choice evidence easier to use

Recorded 2026-10-29. Recommendation for parent integration; no runtime changes or
live calls. **C11 does not qualify. Eleven iterations are used and nine remain.**
This review supplements the mandatory post-c10 review; it does not replace the
post-c15 checkpoint or final acceptance review.

Sources: [campaign plan](../plans/2026-10-29-results-category-led-campaign.md),
[post-c10 review](2026-10-29-results-category-led-c10-architect-review.md),
[current contract](../results-m2.md),
[ADR0029](../adr/0029-structured-results-and-local-workspace.md),
[V3–V30 lessons](../handoffs/2026-10-29-results-m2-fast-profile-handover.md), and
[exact review index](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-index.json).

## Finding and decision

Recommend one prospective C12 authoring-input intervention: **a compact neutral
table of selected choice facts, coupled with replacement of the conflicting
card-fact instruction**. Expose program, cabin, reported points with scope, and
connection waits across the selected nonbenchmark pool. Retain the existing
temporal relations, condition applicability, complete authoring records and
source-resolved cards. Luna decides which differences matter and writes the
reason, including conditional program access where useful. Code supplies neither
advantages nor recommended winners.

The observed failure is weak explanation of optional alternatives, not missing
source facts, failed category coverage or recurrent condition repetition. A
table is a salience hypothesis, not proof of a cause or a guarantee of improvement.
It is worth one frozen experiment because the actual input centrally juxtaposes
temporal comparisons and conditions while leaving the other demonstrated choice
distinctions nested in individual records. Avoid another isolated instruction
reminder, field rename or new editorial call.

## Evidence from the actual draw

C11 scouts q031–q033 pass the six recorded source-review axes. Confirmation
q034/q036–q039 passes; [q035](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q035/review.md)
passes H/U/K/P and fails M2/C. Its checked workflow is15.0014s; all six
confirmations are12.7060–18.2984s. This review inspected their saved summaries,
not fresh executions. No controlled-correction result follows this failed gate.

Q035 displays these exact selected facts:

| Choice | Source membership | Relevant evidence already in the composition request |
| --- | --- | --- |
| Turkish economy J18 | time | 110,000 reported Turkish points; unknown scope; LAX separate-booking wait301 minutes; IST award wait60 minutes; total1803 minutes |
| Turkish business J63 | time and premium | 275,000 reported Turkish points; unknown scope; LAX separate-booking wait150 minutes; IST award wait140 minutes; total1719 minutes; arrival275 minutes earlier |
| Aeroplan lead A1 | no journey styles | Jan8 SFO–BKK economy;65,000 reported Aeroplan points; unknown scope; CAD102 tax quote;9 reported seats; date-only schedule |

The economy explanation is only “An economy alternative if you don’t need
business class.” The business explanation gives its real cabin and timing
advantages. The lead explanation only asks the traveler to resolve schedule and
quote-scope gaps. Neither optional choice gets a reason that explains why to
consider it in this answer. The source can support a conditional preference for
more LAX connection time, or a qualified same-program points distinction; it can
also support investigating the lead if Aeroplan is a usable program for the
traveler. None requires an invented preference, a cheaper-total claim or a
mandatory numerical comparison.

Do not convert301 versus150 minutes into a code assertion of safety, protected
tickets or a superior journey. The IST waits differ in the opposite direction.
Likewise, different program point numerals are not economic comparisons.

Q035's shared journey conditions are consolidated successfully. Its lead and
cash limitations have separate applicable scopes. The existing independent
review explicitly separates this result from the earlier allocation defect.
Keep C11's applicability table and unknown-tax display correction.

The positive draws constrain the solution. Q034 explains distinct timing choices;
q038 explains economy timing versus a business cabin; q039 explains an earlier
arrival versus a longer LAX buffer. Q037 gives a conditional program reason for
its lead. These demonstrate acceptable ordinary explanations without a mandatory
numeric contrast, same-program pair or additional output fields. They do not
establish stable model behavior.

## Concrete implementation seam

Implement in the profile-scoped `_writer_input` path of
[`category.py`](../../src/award_agent/results/category.py). Derive a
`selected_choice_facts` list from the already constructed exact
`authoring_records`; do not reselect from the full inventory. Include every
selected journey and lead, at most six, with its exact alias and role. Exclude
the benchmark, which retains its separate one-sentence role.

Use a small shared field vocabulary rather than generated free-text summaries:

- Exact alias and source role; source date/route for identification.
- Award program and reported cabin; preserve journey-versus-leg cabin meaning.
- Reported points paired with the program and original price-scope state. Do not
  introduce point valuation, subtraction, normalization or a total-cost label.
- For journeys, all source connection rows with airport, connection kind and
  wait minutes, including award connections and separate-booking connections.
  Do not cherry-pick a favorable connection or merge different connection kinds.

Copy existing states exactly, including explicit unknown/null/absent distinctions;
an absent field must not become zero or a newly asserted limitation. Leads do not
receive fabricated connection rows, departure times, journey styles or complete
itinerary status. The full records remain authoritative and available for facts
outside this narrow table. Existing temporal relations already expose elapsed,
departure and arrival comparisons; reuse them instead of duplicating a second
temporal registry. Condition applicability retains uncertainty ownership. Preserve
source ordering deterministically without sorting by inferred merit.

The table contains observations, not `benefit`, `best`, `advantage`,
`recommended_for`, omission reasons or selector-authored purposes. No new
`CategoryBlock` or `CategoryAnswer` fields are needed in
[`category_contracts.py`](../../src/award_agent/results/category_contracts.py).
No change to the composer output wire, decoder, correction topology, exact card
resolution or category coverage checker is proposed.

**Replace the current blanket cue**, rather than appending instructions while
retaining it. The request currently says cards show schedules, routes, cabin,
points, fees, seats and conditions and to “not repeat those facts in prose as a
card recap.” It also requires supported benefits from those same facts. Although
these are logically compatible, the desired boundary is insufficiently clear
for this draw. Use a concise responsibility statement along these lines:

> Cards provide the itinerary details. Use the selected choice facts and exact
> records to explain why each shown option is worth considering. Briefly reuse
> a fact when it explains that reason; avoid narrating the card. The table does
> not rank options. A reason may be conditional on a program, cabin, date or
> connection preference, without assuming the traveler has that preference.

Retain the existing smallest-useful-subset rule, temporal accuracy rules,
quote-scope restrictions and one-place condition allocation. Do not add a
mandatory per-card countervailing advantage, difference count, numerical contrast
or selected-fact reference field. Fixing the competing cue is part of this one
input/interface experiment; it is not evidence that more reminders alone work.

Keep LOW selection, MEDIUM composition and LOW conditional correction. Changing
effort simultaneously would confound the experiment. Measure added input bytes
and exact tokens; do not claim the extra table improves latency.

## Category coverage and useful selection

The selector picks an authoring pool; its style witness is not an obligation to
display that specific witness. In q035, J63 itself represents both time and
premium. `_document_findings` correctly checks intersection with source members,
so omitting J18 need not drop time coverage. A1 has no style obligation. Preserve
that flexibility. One card with overlap is valid; source-supported omission is
not a failure merely because the pool contains more choices.

Conversely, the existence of an overlap member does not establish that all other
time members are redundant. A different connection, departure preference or
program can matter independently. Do not implement “keep overlap, drop the rest,”
hard dominance pruning or a code preference for a smaller card count. Nor must
the author retain every potentially useful alternative: the goal remains the
smallest materially useful subset, with the full explorer independent. Review
whether the final subset preserves meaningful perspectives and whether each
visible option has a supported reason. Card quantity is not the oracle.

An optional lead may be omitted when it adds no useful research direction, or
kept with an honest conditional program/date/cabin reason. Q3's incomplete-only
case still needs useful supported directions when present; no fixed lead count
or compulsory same-program pair follows. A gaps-only task list is not enough
merely because it is factually correct.

## Verification and acceptance criteria

Before live C12 execution, the implementer should verify:

1. Exact q035 projection: both Turkish point reports/scopes, both LAX and IST
   connection rows with their kinds, and Aeroplan's exact identity/cabin/program.
   No invented advantage or preference appears in the table.
2. Mixed-program, same-program, single-option, absent-versus-unknown, unknown
   connection wait and lead-only controls. Identical facts stay identical; no
   inferred differences, economic order or synthetic lead schedule appears.
3. Existing optional-subset behavior: J63 alone covers q035 time/premium; omitting
   a uniquely represented available perspective still produces the existing
   finding. No new card quota or automatic omission policy is introduced.
4. Deterministic request reconstruction, C11 and older request/replay isolation,
   and unchanged wire/correction behavior. The actual C12 generation request must
   contain the table and replacement cue, not both old and new competing cues.

Then apply the unchanged three-scout, six-confirmation and actual bounded-repair
gates, including all H/U/M2/C/K/P axes and22s individual/20s median latency.
The q035 source is now development evidence, not unseen confirmation evidence.
Do not promote a hand-edited q035 example or an unchanged extra retry. The key
semantic question is whether visible options earn their place through a useful
supported explanation while shared conditions stay consolidated. Merely reducing
card count or passing mechanical checks does not settle it.

## Limits and disposition

V17–V22 already showed that exact pair dossiers do not guarantee accurate natural
language. V28–V30 showed that smaller reference ceilings do not guarantee useful
coverage. This proposal therefore adds no general pair catalog, semantic regex,
evidence-citation wire, editor or new generation. It tests a narrow presentation
of already selected evidence and removes an instruction tension. The nine
remaining iterations are a ceiling, not a reason to repeat it if unsupported.

This review read repository instructions, project state, the relevant workbook
ownership section, ADR guidance, deferred-work context, the current runtime and
contracts, actual q035 generation request/selection/answer/review, positive
q034/q037–q039 answers, and q031–q039 review/summary metadata. Verification is
read-only source tracing and document checks; no runtime tests, fresh replay,
model/provider/FX calls or browser layout validation were performed here.

The older workbook's weighted-ranking suggestion is refined by current Ranking
contracts; it creates no requirement to change Ranking. This recommendation
does not change stage ownership, model/code responsibility or evaluation policy,
so no new ADR decision is proposed. The parent should record the accepted
experiment and evidence in the existing campaign/build log. No deferred item is
reopened or closed, and no qualification/default/frontend/M3 claim follows.

Remaining uncertainty is empirical: the table may be redundant, its token cost
may hurt timing, and Luna may still write weak reasons or source errors. No
unresolved cross-system decision warrants deep-architect escalation now. If this
experiment fails the same usefulness behavior, assess the failed request and
answer before another table or wording variant; do not treat structural input
work as proof that the semantic goal is met.
