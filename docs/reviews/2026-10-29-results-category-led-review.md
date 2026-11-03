# Results M2 category-led independent review

Recorded 2026-10-29 for the new category-led campaign. This review does not regrade
historical V3–V30 evidence. Implementation and generated-answer review are pending.
The [accepted invocation](../build-log/2026-10-29-results-category-led.md) and
[ADR0029](../adr/0029-structured-results-and-local-workspace.md) govern scope.

## Initial boundary trace

Read `AGENTS.md`, the current Results contract, project-state opening, October29
handover/invocation and ADR0029 amendment. Traced `workspace_contracts.py`,
`presentation.py`, `structured_contracts.py`, `structured.py`, `currency.py`,
`focused_packet.py`, `focused_records.py`, `focused_selection_plan.py`,
`focused_v4.py`, `focused_comparison_wire.py` and the historical campaign preview.

- A resolved journey block contains `JourneyView`: exact identities, route,
  local timing/duration, legs, connections/waits, program/points, observed money
  with component scopes, booking obligation, eligibility reasons and confirmed
  style memberships. Its `styles` tuple excludes possible/undetermined states.
- Full component facts remain in `artifact.evidence.components`, joined by the
  journey's award/cash observation IDs. These include seats, returned travelers,
  mixed-cabin reporting, source timestamps and provider attribution. Ranking's
  complete assessment states remain in the retained source projection.
- Lead and benchmark reference blocks resolve a component; date-only observations
  preserve their reported departure date without inventing flight times.
- The old campaign `_preview` renders authored text and display placeholders,
  not flight cards. It cannot establish the new card-delivery requirement.
- Existing structural checks verify identities, labels and basic role coverage;
  they do not establish category-faithful selection or arbitrary prose truth.

The new preview must actually render source-resolved card facts beside the exact
reference, joining retained component evidence where needed. Moving dense facts
out of prose must not hide material booking conditions or leave reviewers to
imagine a future frontend. Cards do not validate numerical or qualitative prose.

## Prospective review rubric

Review the complete delivered answer against the full source, selected identities,
resolved cards and checked workflow receipt. Keep these judgments separate:

1. **Source factuality:** each claim belongs to the exact cited option/component;
   preserve metric/direction, program, quote unit/currency/scope, traveler evidence,
   eligibility and unknowns. No inferred protection, all-leg cabin or availability.
2. **Category faithfulness:** materially distinct available time/cost/premium
   perspectives survive selection and final explanation; overlap is explained
   once; possible/undetermined cost states become truthful traveler implications.
   No fixed category quota or invented Ranking memberships for research leads.
3. **Decision usefulness and composition:** understandable reasons, real downsides
   or conditions, and supported comparisons; no fabricated compensating benefit.
   Consolidate genuinely common limitations while preserving distinct local ones.
   Incomplete answers compare useful research directions without claiming a trip.
4. **Card and cash delivery:** actual source-resolved flight cards carry relevant
   facts; each visible choice has its exact reference. Full-origin-to-destination
   cash context is one brief source-linked sentence, separate from cash access or
   egress costs within an award-led journey. The complete explorer remains intact.
5. **Engineering and latency:** exact replay and source/config bindings, explicit
   failure handling, frozen facts/FX, bounded conditional correction, no SDK retry,
   complete count-plus-generation-plus-check timing and cache conditions. Timing
   includes actual correction; a clean two-call result cannot qualify repair cost.

Semantic source review remains independent of mechanical pass/fail. Record every
draw and any later adjudication separately. A code test, model review or campaign
pass does not itself establish owner presentation acceptance or M3 qualification.

## Positive and negative controls

| Control | Expected judgment |
| --- | --- |
| Source has materially distinct time and premium choices; selection or final answer silently omits premium | Category fail |
| One exact journey belongs to time and premium; one card explains both strengths | Category pass |
| Identical journey repeated merely to fill category sections | Composition fail |
| Possible/undetermined cost is called confirmed cheapest or lowest total | Category and factual fail |
| Unknown scope is explained as inability to establish the lowest total, without claiming the traveler count is unknown | Pass when supported |
| Incomplete lead gains a Ranking time/cost/premium membership | Category and factual fail |
| Correct source card accompanies reversed arrival/elapsed comparison or wrong program/fee pairing | Factual fail despite correct card |
| Benchmark amount is attached to another routing or promoted to a per-person/party total without source support | Factual fail |
| Full-cash context expands into a prominent card or schedule paragraph | Design fail; one exact source-linked sentence is the positive control |
| Date-only lead gains exact times; airport join gains ticket protection; journey cabin becomes all-leg cabin; cash party echo becomes award-party support | Factual fail |
| Card joins a sibling variant's component, quote or conditional requirements | Binding fail |
| Shared caveat is omitted, or consolidation hides a materially different local condition | Composition/factual fail as applicable |
| Fact-light prose has actual readable source cards and clear conditions | Can pass; display placeholders alone cannot |

Engineering controls should also distinguish valid empty comparison pairs from
missing pair data, valid one-pass API-incomplete failure from a delivered answer,
complete-branch instructions from incomplete-only instructions, and the actual
injected recovery fault from an assumed fault identity. These are prospective
controls informed by the handover, not a revision of historical verifier outcomes.

## Review disposition

Initial work is read-only tracing plus this rubric. No live calls, source changes,
test execution or historical regrading were performed. No escalation is currently
recommended. Remaining uncertainty: the new implementation, final card surface,
correction behavior and generated-answer quality have not yet been reviewed.

## Initial implementation review — provisional while authors are active

Inspected the new `category.py`/`category_contracts.py` and campaign
`run.py`, `ledger.py`, `freeze.py`, `verify.py`, `preview.py`, source registry and
campaign controls. Findings below were sent directly to their implementers;
they are not a final review of the completed change.

1. **Final category omission could pass.** `_document_findings` computed its
   expected categories from the final document's own reduced selection, making
   its visibility check ineffective when the composer drops an entire category.
   Expected coverage must come from the frozen selection/category audit.
2. **Preview contract mismatch removed every new card.** The initial preview
   recognized old `reference` blocks but the new answer emits `journey_card` and
   `lead_card`. The old branch also discarded each reference's explanatory text.
3. **Writer category identities used another namespace.** An offline preparation
   probe showed landscape members `J17`/`J82` alongside authoring-record keys
   beginning `J17@...`/`J82@...`. Landscape references should use the same exact
   writer identities.
4. **Selection findings were absent from the resolved answer.** A selection
   coverage failure annotated the artifact while its resolved findings could be
   empty, obscuring the actual failure at the delivery surface.
5. **Verifier cross-bindings were incomplete.** Archive hashes, requests and a
   replayable artifact were checked independently. The initial verifier did not
   compare source/config/profile to captured input, saved resolved output and
   summary to the artifact, or captured requests/receipts to artifact passes.
   Tamper controls must test these relationships, not only each file separately.
6. **Initial lead preview invented a universal timing gap.** Its unconditional
   missing-flight/connection-times statement is wrong for source lead kinds that
   retain known itinerary timings. Derive caveats from exact lead evidence and
   display the known component facts.

The parent confirmed that an explicit nonmaterial-category omission reason may
proceed to independent semantic review; deterministic code must not treat every
unselected category as automatic failure or trust the rationale as source truth.
Missing audits remain distinguishable. Duplicate-card and cost-state controls
were requested from the implementer.

Offline preparation on the historical admitted source confirmed that individual
writer records retain `styles` states including `cost: undetermined`, plus
heuristic-cost completeness and missing parts. This addresses the concern that
only global possible-cost counts might survive. It does not test generated prose
or synthetic definite/possible-cost cases.

Checks performed: Python preparation/source inspection only, with no network or
writer invocation. One initial probe used the wrong registry key `admitted` and
failed before preparation; the corrected `prior-admitted` probe succeeded.
Tests were not yet available when this provisional review began. Required next
step: rerun review and meaningful controls against the completed implementation
before live acceptance. No deeper escalation is recommended.

## Runtime review and offline failure probes

The subsequent runtime resolves the initial category omission, writer namespace
and resolved-findings issues. An audited omission is retained as `unchecked`,
without leaking selector rationale into writer facts; absent audit remains a
failure. Final displayed categories are checked against the frozen selected pool.
The preview recognizes the new card kinds, retains explanatory prose and joins
the attached source components. Verifier source/config/profile and API
request/receipt cross-checks have been added.

Independent execution of `tests/unit/test_results_category.py` passed **10 tests
in 53.66 seconds**. Additional direct offline probes verified:

- first-pass API-incomplete: one pass, explicit generation error, no delivery,
  replay returns no answer;
- context ceiling: explicit context-limit outcome with no delivery;
- input-count failure: explicit measurement-error outcome with no delivery;
- failed correction: three passes, initial annotated answer retained, exact replay.

The fallback chosen index is guarded by an actual chosen draft before resolution,
so it does not attempt to resolve the failed selector after the fix.

Remaining findings sent to implementers before c01 freeze:

- Repeated benchmark blocks could each satisfy the sentence check while producing
  multiple cash sentences. A document-wide benchmark count control is required.
- Lead cash-fare components were labeled as taxes. Known quote scope should remain
  visible per component, alongside existing unknown-scope treatment.
- The shared presentation layer emits an opaque `reported=False` segment when a
  component has no reported legs. Preview must distinguish that overall route
  from a real reported flight; otherwise it can imply a discovered direct leg or
  known leg cabin for an incomplete summary.
- Successful correction and synthetic confirmed/possible/undetermined cost
  controls remain to be verified against the final files.

These are code/presentation review findings, not live quality results. Freeze/live
clearance remains pending their fixes and targeted verification. Blind source
review must still inspect unchecked omission audits against the full source;
mechanically clean status does not approve those rationales.

## c01 engineering clearance for scouts

The final reviewed c01 adds document-wide `repeated_cash_sentence` and duplicate
lead controls, preserves the missing-selector-benchmark failure, and passes the
new incomplete-lead card/replay case. Preview now excludes opaque
`reported=False` segments from reported-flight rows, labels a cash lead's amount
as cash fare, and displays known cash quote scopes. Blind review bundles include
the selector omission audit, full category landscape, final findings and
availability guidance separately from the traveler preview.

Independent targeted verification after these fixes:

- Added runtime controls: **2 passed, 10 deselected in 5.28 seconds**.
- Campaign verifier/preview controls: **11 passed in 2.29 seconds**.
- Earlier independent runtime result remains **10 passed in 53.66 seconds**,
  supplemented by the four failure/replay probes above.

No known reviewed engineering defect blocks spending the authorized c01 scout
calls. This is scoped engineering clearance, not a factuality, latency, default
adoption or M2 closeout claim. Synthetic confirmed/possible/undetermined cost
coverage, successful repair qualification and broader integration remain pending;
the parent explicitly keeps them as later acceptance requirements. No escalation
is recommended. Subsequent blind answer review must read each complete source and
selection audit without using run timing, profile or prior grades as evidence.

## First three blind answer reviews

Reviewed only each bundle's complete source, answer/card display, document and
selection audit, plus reviewer instructions. No run timing, candidate mapping,
prompt, checker verdict or earlier answer grade informed these judgments.
Per-bundle immutable reviews are saved beside the answers:

| Bundle | H | U | M2 | C | K | P |
| --- | --- | --- | --- | --- | --- | --- |
| [q001](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q001/review.md) | Fail | Pass | Fail | Pass | Pass | Fail |
| [q002](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q002/review.md) | Pass | Pass | Fail | Fail | Pass | Fail |
| [q003](../../evidence/results-stage/m2/structured/2026-10-29-category-led/review-bundles/q003/review.md) | Fail | Fail | Fail | Fail | Fail | Pass |

q001 misnames its Aeroplan/UA/CX economy itinerary as Singapore Airlines. q002
does not explain a positive reason for its longer economy alternative despite
supported same-program reported-points and separate-ticket-buffer distinctions.
Both show actual cards but suppress known positioning-component schedules when
individual flight legs are unreported. The proper fix is to show component-level
facts with that limitation, not invent individual flights.

q003 calls United's 60,500 points the lowest displayed total while also showing
Alaska's 42,500, and puts incomplete leads into Cost/Premium sections despite no
Ranking memberships. Full-source inspection found useful same-program Alaska
premium-economy leads on January17/18 at a reported 55,000 points, inside the
monthly window with a seat reported for the requested traveler, versus the
selected January12 140,000-point lead. Unknown scope prevents a total-savings
claim; the omission concerns useful research comparison, not a mandatory quota.
All three repeat shared caveats. Exact identities, source fields and semantic
interpretation limits are retained in each `review.json`.

## Subsequent API/CLI and c02 code review

Read the explicit category API exports, `measure_category_results`, CLI category
argument validation/author/replay branches, default profile, c02 guidance and new
tests. No new concrete runtime blocker was found in that bounded review:

- Category authoring requires an explicit category profile. Its owned client has
  zero retries, uses the configured timeout, is shared by counting and writing,
  and closes in `finally`.
- Measurement builds the category selector's actual request/schema and clearly
  limits its claim to selector preparation; it makes no network calls.
- Replay routes by the category artifact contract. The public default remains
  `focused-v27`; c02 is not promoted by adding the opt-in CLI/API.
- c02 appends identity, natural-composition and incomplete-research guidance to
  address observed errors. A same-program/date selector refinement is being added
  separately; generated quality is still unmeasured.

The parent is running the new integration tests; this read-only review does not
claim an independent rerun of those additions. Full synthetic cost-state and
successful-correction qualification remains separate. Prospective component-card
improvements must preserve the original q001–q003 views and grades. No escalation
is recommended.

## c03 preparation/code review

Reviewed the cohesive c03 author guide, profile registry/CLI choices,
incomplete-selector format selection, grouped lead projection, local composer
adaptation, reference bounds and targeted controls. c03 uses the grouped
`roles-v30` selector representation only when the trusted comparison pool is empty;
complete inputs and prior c01/c02 profiles retain `roles-v20`.

The initial check for an empty alternatives tuple was corrected: rejected or
research-only alternatives do not constitute an eligible journey. The grouped
test's initial quote-side-index count was also corrected because grouping moves
each original quote into its lead record. The final control compares the exact
grouped identity union to the full flat source lead inventory.

The category-owned decoder retains six nonbenchmark references and seven total.
The composer locally uses `roles-v20` to avoid importing the historical V30
two-reference policy. A three-lead-plus-cash end-to-end preparation/replay control
tests that seam. CLI category choices come from the profile registry rather than
a growing choice ladder. The public default is unchanged.

The new guide favors natural card explanations, supported conditional research
directions and one shared-limit discussion, without empty categories or mandatory
Time/Cost/Premium titles. It does not introduce another ranking policy. Prompt
quality remains an empirical question for the next saved draws.

Verification supplied by the implementer: **21 category/control tests passed in
113.80 seconds**, Ruff/mypy/diff checks passed, and all **six actual saved c01/c02
scout artifacts** replayed under the new code. This reviewer read the controls and
code but did not duplicate that test run. Newly generated prior-profile artifacts
alone would not prove historical preservation; actual saved replay was explicitly
requested and reported.

**Disposition: cleared for frozen c03 scouts.** No known reviewed implementation
blocker remains. This is not live quality, latency or milestone acceptance. No
live calls or product edits were made by this reviewer; no escalation recommended.


## c04 code review and preservation controls

Reviewed `src/award_agent/results/category.py`, its shared pass/replay checker
hooks, profile registry/CLI routing, and
`tests/unit/test_results_category_cash_dedup.py`. c04 inherits c03 selection,
grouped incomplete representation, six nonbenchmark/seven total reference bounds,
and low-effort/fast settings. Earlier prompt text remains intact. The new author
guidance requires a single cash sentence and an opening whose benefits belong to
the actual selected choices; it allows omitting an unsupported comparison.

The duplicate check is explicitly profile-scoped. Only c04 compares the
whitespace-normalized exact bound cash sentence against other block text,
including a sentence embedded within longer prose or a card explanation. Findings
identify the benchmark and affected block. Live composition, bounded correction
and replay all use the same profile checker. c01–c03 retain legacy findings.
Case changes and paraphrases are outside this mechanical control; it does not
establish semantic nonrepetition or validate benefit ownership.

An independent narrow offline probe embedded the benchmark sentence with changed
whitespace/newlines inside a journey explanation. c04 produced the expected
finding, correct `part_index` and benchmark `reference_id`; c01–c03 produced no
new duplicate finding. A case-changed sentence deliberately remained outside the
exact-match rule. This probe exited0. The new unit controls were read and cover
whole/embedded duplicates with successful one-pass repair, distinct context,
actual saved c03 replay and the prospective overlap instruction.

The runner reports current-code strict replay of all nine actual saved c01–c03
artifacts, original findings and archived previews, with zero integrity issues;
14 campaign controls and Ruff passed. The implementer reports all **26 category
runtime/control/cash-dedup tests passed in136.66 seconds**, Ruff on touched files,
mypy on category/CLI source and `git diff --check` passed. All nine actual archived
artifacts also replayed in their check. This reviewer did not duplicate the full
suite or inspect new answer metrics.

**Disposition: cleared for frozen c04 scouts.** No known reviewed implementation
blocker remains. This does not establish live quality, latency or milestone
acceptance. A final freeze replay is owned by the runner.

Prospective reviewer instructions preserve the owner-approved research-choice
boundary: conditional program access, cabin and date can explain useful next
checks without a mandatory same-program pair or numeric difference. Existing
source review grades remain intact. No product edits or live calls were made by
this reviewer; no escalation is recommended.


## c05 temporal-fact review

Reviewed the c05 changes in `category.py`, the existing temporal registry and
contracts, c05 temporal tests, prior registry controls, profile-aware run/replay
call sites and CLI registry routing. The new writer key is c05-only. It projects
canonical registry facts into exact author-record aliases, metric, relation and
absolute minute delta; it does not add inline claim binding, comparison cards,
a model editor or deterministic validation of ordinary prose.

The existing registry uses UTC instants for departure/arrival, separate elapsed
minute values for duration, like-airport scope checks and explicit equality. Its
alias map must be one-to-one with selected eligible source journeys. c05 maps
the canonical endpoints through the current writer aliases and includes facts
in the frozen preparation/request path. One/no selected journey yields no pair.
The q011 control checks equal arrivals, business departure187 minutes earlier,
and economy elapsed duration187 minutes shorter, without substituting one
metric for another.

The guide is neutral: a Ranking time-band member need not arrive earlier or be
shorter than another selected member; overlap does not imply an overall winner.
The prior illustrative business/earlier-arrival pairing is absent. c04 exact
cash deduplication and c03 conditional research reasons remain, with low effort,
the unchanged selector, grouped incomplete facts and six-plus-cash bounds.

Independent offline probes passed: c05's actual writer request includes the new
key, a generated artifact round-trips through exact replay, a mutated temporal
relation is rejected, and three reversed-order selected journeys produce nine
pair facts whose endpoints exist in the actual authoring records. These probes
made no live calls. The implementer reports **30/30 combined category tests passed
in149.76 seconds**, Ruff on current category files, mypy on category/CLI source
and `git diff --check` passed. All12 actual saved c01–c04 artifacts replayed
locally. The runner independently strict-verified those12 archived artifacts and
original previews with zero integrity issues under c05 code. Snapshot coverage
includes both registry dependencies and the new category tests.

**Disposition: cleared for frozen c05 scouts.** No known reviewed implementation
blocker remains. The runner owns the final post-freeze preservation verification;
this clearance does not qualify generated answer quality or latency.

The factual aid is not a prose truth guarantee or a new ranking policy. Live
answer quality, latency and general reliability remain separate. Only this review
document was edited by the reviewer; no escalation recommended.


## c06 optional-pool and guide review

Reviewed the replacement author guide, unchanged decoder/checker subset boundary,
profile registry, c06 editorial controls and inherited temporal/cash policies.
The new guide treats selected records as an optional pool and asks for the
smallest useful displayed subset preserving meaningful selected category
perspectives. It forbids prose about omitted records, preserves exact visible
references and Q3 conditional research reasons, and does not impose a per-card
downside when only shared uncertainty applies. The previous guide is not appended.

A preservation gap was identified in the first replacement: the prior explicit
boundary against cheapest/all-in claims from unknown-scope amounts was missing.
The final c06 guide restores that boundary explicitly: incomplete/unknown-scope
amounts do not establish per-person, all-in or cheapest-overall claims. This
retains existing source scope policy, not a new ranking rule or prose checker.

Independent offline probes confirmed that c05 and c06 selector requests,
selector/focus preparation, author input/schema and LOW reasoning are identical.
Only author instructions differ. Removing the premium card from a c06 subset
still produces `selected_category_not_shown`. The positive controls were read:
five selected journeys may yield two cards preserving time/premium, and four
research leads may yield two lead cards; both include one cash sentence and exact
replay. These fake-writer controls establish mechanical subset acceptance only,
not the natural quality of their prose.

The final patched guide was inspected. The implementer reports **32/32 full
category tests passed in 160.22 seconds** before the scope sentence, then **5/5
targeted c06/registry/CLI controls passed in 52.81 seconds** after it. Ruff, mypy
and diff checks passed, and all 15 actual c01–c05 saved artifacts replayed exactly.
The runner independently strict-verified all 15 actual archived artifacts and
original previews under frozen c06 source with zero integrity issues and exit 0.
The new editorial test file is covered by the source/test snapshot glob.

**Disposition: cleared for frozen c06 scouts.** No known reviewed implementation
blocker remains. Mechanical subset acceptance does not establish good editorial
selection, natural composition, semantic truth or latency; those require future
independent answer review. No live calls or product edits were made by this
reviewer; no escalation recommended.


## c07 category-witness selector review

Reviewed c07 schema, decoder, source alias mapping, selection findings, run/measure/
replay wiring, benchmark projection and seven new style-audit controls. Each of
time/cost/premium is required. Nonnull witnesses are restricted to that source
style's exact journey aliases and themselves select into the authoring pool;
union with free choices is deduplicated and bounded by six nonbenchmark plus one
cash reference. Overlap is source-derived, without model membership facts,
automatic member choice or separate display quotas.

For an available omitted perspective, a nonempty reason is mandatory but remains
unchecked audit evidence. An unavailable style requires null plus an empty reason.
Coverage derived from selected source IDs catches contradictory omission notes,
including incidental overlap. The author receives selected source membership,
not the selector's rationale. c06 author allocation, Q3, LOW effort, temporal facts
and cash deduplication remain. No extra selector retry/editor topology is added.

Initial test issues were corrected: witness-only selection must still report a
missing available cash benchmark; the projection control must actually select a
benchmark. The final test now compares prior/new quotes, confirms only the derived
fee-unit field is removed, and preserves the original prepared benchmark facts.
`writer_packet` deep-copies those facts. C07 removal is limited to benchmark records
whose quote kind is cash_fare; actual quote unit/display and raw evidence remain.

Independent offline probes passed for valid omission -> unchecked with rationale
absent from author facts; unavailable-style reason, blank available omission,
boolean witness, list alias and extra purpose rejection; witness/free overlap
at the exact six-plus-cash bound; and grouped incomplete lead/cash selection with
all styles null. Final source call sites pass the profile consistently into
schema, decoder, selection checks and replay.

The implementer reports **39/39 combined category tests passed in 181.18 seconds**,
Ruff on category/CLI source and tests, mypy on category/CLI source and diff checks
passed. All 18 actual saved c01–c06 artifacts replayed exactly locally. Final
independent runner verification passed all 18 actual archived artifacts, previews
and source/config/request/receipt bindings with zero integrity issues and exit 0.
Campaign bundle controls passed 16/16 with Ruff clean. Prospective bundles
will retain raw style audits/free choices plus normalized omission reasons and
actual derived source coverage; legacy bundles remain untouched.

**Disposition: cleared for frozen c07 scouts.** No known reviewed implementation
blocker remains. The structural audit does not judge omission truth, decide which
source member is useful, or validate ordinary prose. Live quality and latency
remain independent gates. No live calls or product edits by this reviewer, and
no escalation recommended.


## c08 schema/decoder branch alignment review

The three c07 selector outputs exposed a concrete contract gap: the schema allowed
string explanations for unavailable categories while the decoder required empty
reasons there. Prior c07 controls established decoder rejection but did not prove
that these schema-permitted branch combinations were usable. The three original
failures remain failures and are not source-answer reviews or regraded successes.

Reviewed c08's prospective schema/decoder change and actual-c07-wire controls.
Unavailable styles now require `{r: null, omission_reason: null}`. An available
style is either an exact source witness plus null reason, or null reference plus
a string omission reason. The decoder retains the existing nonblank requirement
for real omissions and source-derived union/overlap/bounds checks. c07 still uses
its original schema, string convention and failure outcome. There is no new
retry/editor topology, content policy or model effort change.

The new tests explicitly verify each actual c07 raw wire against old and new
schemas: old schema accepts, old decoder rejects, and old artifact replay remains
unavailable. New nullable equivalents preserve references rather than accepting
the old invalid output. The incomplete control retains all six grouped research
leads plus cash, and the c08 two-pass artifact replays exactly.

Independent probes checked six available-style combinations and seven inactive
cost reason types. Schema/decoder types align; whitespace-only real omission
reasons remain intentionally schema-permitted but decoder-rejected. A genuine
available omission is unchecked and its rationale is absent from author facts.
Dual-style and free-choice duplicates select one exact source journey; six plus
cash passes and seven nonbenchmark references fail. For an identical selected
source set, c07/c08 author guide, focus and writer facts are equal.

The implementer reports **44/44 combined category tests passed in 192.33 seconds**,
Ruff on category/CLI source and tests, mypy on category/CLI source and diff checks
passed. All 21 actual c01–c07 artifacts replayed locally, including the three c07
generation-error outcomes. The runner independently strict-verified all 21 actual
archived artifacts, previews and source/config/request/receipt bindings under
frozen c08 source with zero integrity issues and exit 0. All three c07 outcomes
remain not delivered; q019–q021 remain reserved rather than backfilled. Campaign
controls passed 17/17 and Ruff passed, including nullable audit normalization.

**Disposition: cleared for frozen c08 scouts.** No known reviewed implementation
blocker remains. This fixes the declared nullable branch contract, not every
possible semantic failure, and establishes no live quality or latency result.
No live calls or product edits by this reviewer; no escalation recommended.


## c09 phase-specific effort and cash role review

Compared current `category.py` with the source archived by the actual c08 admitted
scout. The runtime delta is limited to c09 profile registration and composition
settings: selector LOW, initial composer MEDIUM, bounded correction LOW. The c08
author/selector guides, nullable audit, grouped incomplete preparation, source
packet, schema, temporal facts, cash projection, checks and six-plus-cash bound
are unchanged. Existing profiles retain LOW in all phases. There is no extra
editor or fourth call, default switch, or selected-journey metadata refactor.

Independent offline probes covered admitted, conditional and incomplete inputs.
For the same source selection, the complete c08/c09 composition request differs
only in `reasoning`; selector requests and focus are equal. Complete correction
requests are equal across those profiles and remain LOW. An uncorrected c09
two-pass artifact replayed exactly; changing its saved composition request effort
to LOW was rejected as a request mismatch. The new phase-settings controls also
exercise a successful duplicate-cash correction, LOW/MEDIUM/LOW execution, and
rejection of changed composer or correction settings.

Reviewed the prospective preview's fixed `Cash comparison: ` prefix, applied
only to resolved `cash_sentence` blocks. It retains the exact authored sentence
and amount, emits no cash card, and HTML-escapes the resulting paragraph. The
focused control covers prose without the word cash, one amount and no article.
Old previews use their SHA-checked archived renderer; the new prefix does not
rewrite old evidence. This role label does not remove instruction leakage or
validate the meaning of authored prose.

The implementer reports **47/47 combined category tests passed in 200.84 seconds**,
Ruff on category/CLI source and tests, mypy on category/CLI source and diff checks
passed. All 24 actual c01–c08 artifacts replayed locally, including c07 failures.
Independent request/replay probes above passed with exit 0. The runner's final
strict verification under frozen c09 source passed all 24 actual archived
artifacts and previews, including c07 failure outcomes: 46 generation and 46
input-count reservations, zero integrity issues, exit 0. Campaign controls passed
18/18 with Ruff and diff checks clean.

**Disposition: cleared for frozen c09 scouts.** No known reviewed implementation
blocker remains. Higher composer effort establishes no quality or latency result;
all source/composition gates remain applicable. No live calls or product edits by
this reviewer, and no escalation recommended.


## c10 lead-caption responsibility review

Compared current source with `category.py` archived by the actual c09 admitted
scout. C10 changes the composer guide and adds a description only to the lead
branch's existing `v` field. It keeps the wire and decoder unchanged. The guide
assigns supported conditional next-check reasons to lead captions, common gaps
to one shared passage, and research status/reported gaps to source cards. It
still permits a local condition that changes the next action, and does not assume
that every lead is date-only. Existing quote-scope and useful-reason boundaries
remain intact.

Independent recursive schema probes on actual mixed and incomplete source
selections found exactly one difference: `l.properties.v.description`. The helper
replaces the value dict rather than mutating the shared dict used by other roles.
Subsequent c09 schema construction remains equal; journey, cash and text branches
do not acquire the lead description. Selector requests and focused source facts
are unchanged. Both composition and correction requests differ only in author
instructions and schema, with MEDIUM composition and LOW correction preserved.

Initial independent probing found a blocker: the helper raised an exception if
there was no lead branch, rejecting valid complete-journey-only selections. The
implementer removed that rejection and added a no-lead control. Re-probing proved
the no-lead schema equals c09, and an actual admitted-source offline run completed
in two passes with LOW/MEDIUM settings and exact replay. This defect was fixed
before any c10 live call. The mixed-answer control also preserves raw lead text
verbatim, rather than relying on deterministic rewriting for prose improvement.

The targeted lead-caption controls passed 4/4 in 6.65 seconds according to the
implementer, followed by **51/51 combined category tests in 207.19 seconds**, with
Ruff, mypy and diff checks passing. All 27 actual c01–c09 artifacts replayed
locally. Independent source/request, schema and no-lead run/replay probes passed.
The runner's final strict verification under frozen c10 source passed all 27
actual archived artifacts and previews, including c07 first-pass failures:
52 generation and 52 input-count reservations, zero integrity issues, exit 0.
Campaign controls passed 18/18 with Ruff clean.

**Disposition: cleared for frozen c10 scouts.** No remaining reviewed code blocker
is known. Semantic caption allocation still requires live answer review, and
mandatory post-c10 architect reflection remains pending after evaluation and
before further advancement. No live calls or product edits by this reviewer;
no escalation recommended.


## c11 condition applicability and explicit tax-card states review

Reviewed the c11 delta against actual archived c10 source. The new writer-only
table contains `code`, `state` and exact authoring-record `applies_to` aliases;
the raw records remain unchanged. The guide leaves visible-subset selection,
natural wording and local/shared allocation to the model. There is no output
clause binding, placement engine, suppression, fuzzy checker or extra model call.
The c10 wire/schema, nullable style audit, caps, temporal facts, cash deduplication
and MEDIUM composition / LOW selection and correction remain unchanged.

Traced table inputs through `focused_records.py`, `focused_details.py`,
`interactive_packet.py`, `interactive_packet_v2.py` and
`focused_traveler_evidence.py`. Party support uses the existing authoritative
requested-party support state, not raw seat counts or returned-party echo. Award
scope, award-tax scope, positioning cash scope, research quote scope and benchmark
cash scope retain separate codes. Missing fields add no condition. Explicit
unknown, absent and null amount states remain distinct, and known zero does not
become missing. Lead date-only state comes from its existing explicit schedule
field; the builder does not classify every lead as date-only.

Independent probes covered admitted, mixed and incomplete saved sources: every
condition matched its canonical quote/caveat/traveler/schedule field and every
alias identified an actual authoring record. Removing each record in turn yielded
exactly the original table intersected with remaining aliases. Optional omitted
pool members therefore remain distinguishable from displayed choices; the model
must still perform that visible intersection. Injected omission-reason and
selection-purpose sentinels did not enter writer facts. Raw packets, schemas and
phase settings stayed equal after removing only the new table. A separate null
amount / zero raw seats / absent echo probe preserved null and did not override
authoritative passed party support.

Reviewed the preview's narrow award-tax indicators for journey `award_taxes` and
award-lead money with kind `award_taxes`. Explicit unknown displays unconfirmed;
explicit absent displays not provided. Missing, null, cash-lead and benchmark
values do not acquire a tax warning, and a known amount with unresolved formatting
is not falsely called unreported. Independent comparison against the archived
c10 renderer found exact Markdown/HTML equality for 24 known-value/card cases,
including zero, major/minor units and all scope states. No authored words or
numbers are rewritten.

The implementer reports six targeted condition controls passed in 6.06 seconds,
followed by **57/57 combined category tests in 212.20 seconds**, with Ruff/mypy/diff
checks clean and all 30 actual c01–c10 artifacts replaying locally. Independent
probes above passed. The runner's final strict verification under frozen c11
source passed all 30 actual archives, including original failure outcomes,
source/request/artifact/replay bindings and exact Markdown/HTML previews:
58 generation and 58 input-count reservations, zero integrity issues, exit 0.
Preview/campaign controls passed 21/21 with Ruff and diff checks clean.

**Disposition: cleared for frozen c11 scouts.** No known reviewed implementation
blocker remains. This table does not validate prose truth or guarantee allocation
quality. If the same allocation failure persists after this hypothesis, the parent
has required fresh architectural critique before further continuation. No live
calls or product edits by this reviewer; no current escalation recommended.


## c12 neutral selected-choice facts review

Reviewed the accepted fresh design review and compared prospective runtime source
with `category.py` archived by the actual c11 conditional confirmation. The new
table includes each selected nonbenchmark record in existing record order, with
exact alias/role, date/route, reported program/cabin/points and original scope.
It copies observations without calculating advantages, differences, valuations,
rankings, safety or complete-lead status. Full authoring records, condition
applicability, temporal relations and source-resolved cards remain available.

Review caught a naming issue: the first draft called the source observation kind
`cabin_scope`, although `award_itinerary`/`award_summary`/`cash_itinerary` identify
component kinds rather than explicit cabin coverage. The implementer changed
this c12-only field to neutral `component_kind`. Reported cabin and leg-cabin
states remain separate, with no claim that a journey cabin proves every leg.

Traced all connection rows through `focused_details.py`: award connections and
all non-award connections partition the source journey's connections, including
cash and separate-booking kinds. Both partitions are copied in full with airport,
kind, wait and unknown reason; no favorable connection is cherry-picked. Points
remain raw program-specific reports with scope, not currency-converted prices or
party totals. Leads receive no invented connection rows, flight instants, styles
or completed-itinerary flag.

Independent probes used actual q035, admitted and incomplete source artifacts.
Every nonbenchmark alias and copied scalar/state matched its exact record; every
connection row matched canonical source. Missing, explicit null/unknown/absent,
zero and unknown waits remain distinct, and returned rows do not mutate source
records. Removing only the choice table makes the c12 writer packet equal to
c11. Composition/correction schemas and MEDIUM/LOW settings are equal. The old
blanket card-recap cue is replaced, not retained alongside the new cue. Existing
coverage permits the actual overlap business journey alone to represent time and
premium; economy alone still produces the missing-premium finding. There is no
new card quota or mandatory numeric contrast.

The implementer added the requested explicit offline c12 two-pass run/replay and
saved-table-request tamper control; it passes and was inspected. A broader category
run passed 60 tests with one stale registry expectation failure. That expectation
was corrected, then all six targeted controls (registry plus five new tests)
passed. Ruff, mypy and diff checks pass, and all 39 actual c01–c11 artifacts replay
exactly locally. Independent probes above passed. These are the actual verification
runs, not a claim that a subsequent complete suite was rerun. The dev-only
`jsonschema` and `types-jsonschema` declarations were inspected; the separate
test-typing cleanup was not re-reviewed mechanically here.

**Disposition: c12 implementation cleared, with no known reviewed code blocker.**
At the parent's request, formal code clearance was issued separately from the
runner's final archive gate. That gate subsequently passed under frozen c12:
all 39 actual c01–c11 archives, exact previews, source/request/receipt/artifact
bindings and replay, with 76 generation and 76 input-count reservations, zero
integrity issues and exit 0. The reviewed implementation and historical-preservation
gates are therefore clear for frozen scouts. This is a source-salience hypothesis,
not a semantic quality or latency result. Code clearance and future blind grades
remain separate. No live calls or product edits by this reviewer; no escalation
currently recommended.

## c13 composer-effort isolation review

Compared `category.py` with the source archived by the actual c12 admitted
scout. The complete runtime diff adds only c13 profile entries: exact c12
instructions, preparation formats, nullable style audit, checker policy,
temporal/condition/choice aids and lead description, with composer effort LOW.
The c12 entry remains MEDIUM. Selection and correction retain LOW; the existing
two-pass path and one bounded correction are unchanged. All 45 other archived
runtime/preview files inspected are byte-identical. No public-default switch,
new writer call, schema change or preview change accompanies this profile.

Independent probes compared prospective c13 requests directly with the actual
archived c12 admitted, conditional and incomplete requests, rather than merely
comparing two requests rebuilt by current code. Every selector request is exact.
Every composition request differs only at `reasoning.effort` (MEDIUM to LOW).
C13 decoding, selection findings and rebuilt focused preparation equal each
saved c12 artifact. Full correction envelopes, supplied the same saved previous
wire and findings, are equal between c12 and c13 and remain LOW. Checker function,
arguments and policy match. All three actual c12 artifacts replay exactly under
the current runtime.

Read `tests/unit/test_results_category_c13_effort.py` and the registry update.
The offline control injects duplicated cash text into an actual saved answer,
observes the expected checker failure, exercises three LOW passes, recovers the
original resolved answer and replays the serialized artifact. It separately
rejects a tampered composer setting and tampered composition request reasoning.
The implementer reports all ten targeted tests (new controls, c12 shared controls
and registry), Ruff and mypy passed. These tests and independent probes support
the settings-isolation claim; no duplicate full suite was run by this reviewer.

**Disposition: c13 source implementation cleared; no known reviewed code blocker.**
The runner's strict verification of all 42 actual prior artifacts remains a
separate required gate before scouts, along with the implementer's completed
historical replay. LOW effort does not establish retained prose quality or a
latency result; new draws require the unchanged source/card/composition rubric.
No live calls or product edits by this reviewer. No escalation recommended.

## c14 bounded authoring-pool review

Read the completed [deep design review](2026-10-29-results-category-led-c14-deep-design-review.md)
before clearance. The baseline is actual archived c12: LOW selection, MEDIUM
composition and LOW correction. C14 changes only the model-selected pool ceiling
to three nonbenchmark references plus one cash benchmark, with matching selector
wording and schema array bound. The full inventory, source records, choice facts,
temporal relations, condition applicability, author guide, output schema, checks,
preview and optional smaller display remain unchanged. This is an empirical
workload hypothesis, not a new ranking policy or a proven semantic/latency fix.

Inspected the complete `category.py` diff against archived c12 and its shared
`focused_packet.py` schema/decoder calls. The profile-scoped limit defaults to the
original six/seven for all older profiles. Nonnull style witnesses join the free
choices, deduplicating exact role/reference pairs; then the decoder enforces
total and nonbenchmark limits. No clipping, automatic witness choice, forced
card count or additional selection retry is introduced. The JSON Schema
`choices.maxItems=4` cannot express the cross-field union bound; the decoder is
authoritative for that condition.

Review caught an old-profile failure-text change from “six” to “6.” The
implementer restored the exact original error text. Independent seven-reference
overflow probes confirmed it for c01 legacy, c07 style-audit, c08 nullable-audit,
c12 and c13 profiles. C14 keeps its own explicit three-reference failure.

Independent probes on actual archived c12 admitted, conditional and incomplete
sources compared the prospective selector request directly with saved requests:
only the declared selector bound text and `choices.maxItems` change. Valid
three-reference selections yield equal c12/c14 decoding, selection findings and
focused preparation. On each such pool, the full composition and correction
envelopes are equal, including MEDIUM/LOW settings. All 45 other archived runtime
and preview files inspected remain byte-identical; only `category.py` differs.

Read the new `tests/unit/test_results_category_c14_pool.py` controls and registry
update. Controls exercise three disjoint style witnesses plus cash, overlapping
witnesses and witness/free-choice deduplication, explicit overflow, multiple-cash
rejection, grouped three-lead-plus-cash preparation without invented styles,
optional overlap-only display and the existing missing-category finding. A
schema-valid free-choice array whose union has four nonbenchmark members is
saved as a one-call selection failure, with no focused preparation or delivered
answer, and replays as that failure. Normal two-pass run/replay, changed-bound
request tamper and equal valid-pool composer/correction envelopes are also covered.

The implementer's final frozen-source evidence is **12/12 new pool and registry
controls passed**, Ruff/mypy/diff checks clean, and all 45 actual older artifacts
replayed exactly locally. Independent probes above passed; this reviewer did not
duplicate the full category suite. Review-document diff checks pass.

**Disposition: c14 source implementation cleared; no known reviewed code blocker.**
The runner's strict 45-artifact archive/preview/binding verification remains a
separate required scout gate. The smaller bound can still omit useful directions
or produce misleading prose; future grades must use full source and the unchanged
six-axis rubric. No live calls or product edits by this reviewer; no further
escalation recommended before the authorized bounded experiment.

## c15 indexed selector audit review

Reviewed `category.py`, `tests/unit/test_results_category_c15_indexed.py`, the
registry assertion, and the campaign `review_bundle.py`/`test_verify.py` delta.
The new profile changes selection only: one array of at most three journey/lead
choices, a separate benchmark alias or null, and per-style indices into that
array. Audits cannot add references. The full selector inventory and C14's
LOW/MEDIUM/LOW settings, author guide, facts/aids, author wire, checks, optional
display and preview remain intact. Comparing archived C14 runtime/preview files
found only `category.py` changed.

The decoder checks exact object fields, roles, duplicate choices and direct-cash
benchmark membership. A witness must be a strict Python integer, within the
actual returned array, pointing to a journey in the authoritative source style.
Booleans and floating representations are rejected rather than coerced. Every
style is required. An unavailable style requires null/null; an available omitted
style requires a nonblank reason and no chosen journey belonging to that style.
This last check scans the entire choices array, including an incidental member
not nominated by another audit. A witness requires a null omission reason.
Normalization appends only the separately selected benchmark and preserves the
chosen references; it neither clips choices nor selects additional members.

Schema bounds do not validate actual index existence or source membership. The
new control intentionally submits a schema-valid index1 for a one-item array;
runtime records a one-call selection failure with no focused preparation or
answer, and exact replay retains that failure. Other controls cover three
disjoint styles plus cash, overlap without filling the bound, three grouped
research leads without styles, wrong-style/lead/bool/fractional/negative indices,
un-nominated incidental coverage, absent/blank/null omission states, duplicates,
wrong aliases/roles, a positioning C alias used as benchmark, and over-three
choices rejected by schema and decoder. Valid audited omissions remain unchecked
semantic rationale, not automatically verified facts. Normal run/replay and
request-schema tamper controls are present; actual C14's saved overflow remains
undelivered in its original profile.

Independent probes on the three actual saved complete/mixed/incomplete sources
translated the same valid C14 normalized choices to indexed C15 wires. Source
inventory, normalized selection, selection findings and focused preparation
matched. Full composer and correction envelopes were equal, including
MEDIUM/LOW settings and all factual aids. No omission rationale becomes a writer
fact, and no numerical or composition brief was changed by this experiment.

The blind audit adapter preserves raw indexed wire, choice order, benchmark and
omission evidence while resolving each nonnull index through the actual returned
journey alias to its canonical ID. Independent reordered mixed-role probes
verified those joins and rejected boolean, float, string, negative, out-of-range,
lead and invalid-benchmark cases. Input wire was not mutated. Comparing the new
helper with the archived C14 helper on the actual saved overflow wire produced
exact legacy audit output. This adapter exposes evidence; it does not certify
omission rationale or arbitrary prose. Preview, rubric and older bundles are
unchanged.

The implementer reports an initial 13 targeted tests passed, followed by two
expanded negative-control tests after review requests; Ruff and mypy pass and
all 48 older actual artifacts replay exactly locally, including q046's original
failure. The runner reports 24 campaign controls passed with Ruff/diff clean.
Independent probes above passed; no duplicate full suite was run by this reviewer.

**Disposition: c15 source and audit-tooling implementation cleared; no known
reviewed code blocker.** The runner's final strict 48-artifact archive/binding/
preview gate remains separate. New source grades must remain independent of this
code result; the mandatory post-c15 architect review must occur after all three
scout outcomes and before confirmation or another candidate. No live calls or
product edits by this reviewer; no additional escalation recommended now.

## c16 program-unit author-clause review

Read the accepted [post-c15 architect review](2026-10-29-results-category-led-c15-architect-review.md)
and inspected `category.py`, `test_results_category_c16_units.py` and the registry
update. The new author passage replaces the old ambiguous “Do not force” grouping:
smaller raw counts in different loyalty programs do not establish an advantage
or reason to favor a lead. It retains optional comparisons, conditional program/
date/cabin reasons, and scoped same-program reported-quote comparisons. No
numerical minimum, pair/card quota, code-written prose or semantic checker is
introduced. The C15 selector and LOW/MEDIUM/LOW settings remain unchanged.

Compared the full runtime/preview snapshot with actual archived C15: only
`category.py` differs, through the new profile map entries and author clause.
Independent probes used all three actual C15 admitted, conditional and incomplete
saved requests. Every selector request is exact. Every composition request
differs only by the adopted clause replacement; input, schema and settings are
identical. Rebuilt C16 decoding, selection findings and focused preparation equal
the saved C15 values. Correction envelopes supplied the same wire/findings differ
only by that clause and remain LOW. All three actual C15 artifacts replay exactly.

The tests cover those three request branches, offline two-pass run/replay and
instruction tamper, plus registry inclusion. The offline writer reuses the
unedited prior incomplete wire, including its previously failed semantic content;
preserving that resolved object demonstrates engineering compatibility, not a
better answer or changed historical grade. The implementer reports **5/5 targeted
tests**, Ruff/mypy/diff checks and all **51 actual historical artifact replays**
passed under frozen source. Independent probes above passed; this reviewer did
not duplicate the full category suite.

**Disposition: c16 implementation cleared; no known reviewed code blocker.** The
runner's final strict 51-artifact archive/binding/preview verification remains a
separate required scout gate. Fresh source reviews must determine whether the
model follows the clarification; no semantic or latency qualification follows
from string/request tests. Earlier grades remain intact. No live calls or product
edits by this reviewer; no additional escalation recommended before this bounded
experiment. The next mandatory architect checkpoint remains c20 or earlier final
closeout, as specified by the parent.

## c17 source-proven award-scope normalization review

Inspected `category.py`, `test_results_category_c17_scope.py`, the registry update,
and the existing `interactive_packet.py`, `interactive_packet_v2.py`,
`focused_details.py`, `focused_records.py` and `currency.py` provenance paths.
The journey's award facts join through its exact award reference; the focused
quote copies that component's `price_scope`. `focused_records.writer_packet`
checks the selected journey/member component binding before attaching that quote.
`observed_money` and `journey_money` likewise retain the canonical
`SolutionComponent.price_scope` for taxes and points. This establishes shared
source ownership within the existing trusted preparation contract; C17 does not
add an upstream verifier or infer identity merely from two equal unknown values.

The C17-only predicate requires a nonempty string `member.award_ref` equal to
`award_component.ref`, quote kind `award_taxes`, and both projected scopes
explicitly `unknown`. Only then does that journey alias receive
`award_points_and_tax_quote_scope` instead of its two separate scope rows.
Missing/mismatched identity or nonqualifying scope preserves the applicable
separate rows. Tax **amount** state, party support, separate tickets, positioning
permission/cash, benchmark cash and lead conditions retain their prior handling.
The default flag remains false for every historical profile; raw authoring
records, cards and source facts are not mutated.

Independent probes compared all three actual archived C16 request branches.
Selector requests are exact. The complete composer and correction envelopes
differ only in `packet.condition_applicability`; instructions (including the C16
program-unit rule), schema, all other input and MEDIUM/LOW settings are exact.
The admitted q052 source and conditional source change from eight condition rows
to seven; the incomplete source remains three rows. All three C16 artifacts replay
exactly. A full archived runtime/preview comparison finds only the expected
`category.py` profile/table delta. Forty-five additional missing, null, absent,
empty and invalid-type probes across identity, kind and scope fields produce no
merged condition. No live calls were made.

The new tests cover q052 aliases J1/J82 against their exact canonical award
components, partial merging in one pool, wrong/missing identity and quote kind,
known versus unknown scope, unknown/absent/null tax amounts and known zero without
collapsing those states. They also cover the three request branches and an
offline two-pass artifact with exact replay and condition-table request tamper
rejection. Reusing saved q052 prose in that offline test preserves its historical
M2 failure; it does not demonstrate improved language or regrade the answer.
The implementer reports **7/7 targeted tests**, Ruff/mypy/diff checks and **54/54
actual historical artifact replays** passed under frozen source. This reviewer
ran the independent probes above, not a duplicate broad suite.

**Disposition: c17 implementation cleared; no known reviewed code blocker.**
The runner's final strict 54-artifact source/request/receipt/preview verification
remains a separate required gate. Whether the model now states the shared
limitation once, and its latency, remain prospective live-evaluation questions.
No semantic qualification or default adoption follows. No product edits by this
reviewer and no further architecture escalation recommended for this narrow cut.

## c18 natural-choice paragraph review

Reviewed `category.py`, `test_results_category_c18_reasons.py`, the registry
update and the exact accepted replacement in the campaign plan. The final
paragraph makes the complete-journey caption explain when a traveler might
choose the option, with a practical condition accompanying rather than replacing
that reason. Its nonexclusive examples include cabin, timing, trip duration,
connections and **scope-qualified cost or point quotes**. It translates category
strengths into ordinary language while retaining source memberships, temporal
comparison accuracy and overlap limits. A single journey remains valid; no
comparison, numeric minimum, added card or invented advantage is required.

The parent's final first-sentence clarification preserves supported cost/quote
reasons rather than restricting captions to a closed example list. After that
edit, an independent literal comparison confirmed that both the old span and
final replacement equal the plan's exact paragraphs plus trailing spaces. The
old span occurs exactly once. All other author clauses, including the C16
program-unit rule, remain unchanged.

Independent probes compared against the **actual saved C17 requests** for all
three admitted, conditional and incomplete sources. Every selector request is
exact. Every complete composition and correction request differs only by the
approved paragraph replacement; all input data, schemas and LOW/MEDIUM/LOW
settings remain exact. These probes were rerun after the final first-sentence
edit. All three C17 artifacts replay exactly. The archived runtime/preview
comparison finds only `category.py` changed, and every function/class AST in
that module equals archived C17: the delta is profile instructions/maps, not
selection, preparation, normalization, rendering, checking or call topology.

The new tests cover all three request branches, correction with supplied
findings, offline two-pass run/replay, request-instruction tamper and the registry.
The offline run reuses unedited saved admitted-case wires and establishes
compatibility only. It does not demonstrate improved composition; q056's prior
M2 failure and every historical grade remain intact. The implementer reports
**5/5 targeted tests**, Ruff/mypy/diff checks and **57/57 actual historical
artifact replays** passed after the final edit, with source/tests frozen. This
reviewer ran the independent exact-plan/request/AST/replay probes above rather
than duplicating the full suite.

**Disposition: c18 implementation cleared; no known reviewed code blocker.**
The runner's strict 57-artifact archive/request/receipt/preview gate remains
separate and required before authorized live evaluation. Natural explanations,
source truth and latency must be judged on new delivered answers; removing
internal terminology alone would not establish semantic success. No live calls
or product edits by this reviewer, and no additional escalation recommended for
this bounded authoring change. The hard c20 stop and mandatory final review
remain unchanged.

## c19 quote and condition interpretation review

Reviewed the exact adopted campaign-plan span, `category.py`,
`test_results_category_c19_quotes.py` and the registry update. This profile
replaces only the author paragraph governing quote meaning and condition
explanation. It distinguishes known reported amounts from unknown pricing basis,
applies uncertainty only to the relevant fields/shown aliases, and treats an
existing local or shared qualification as an explanation rather than a reason
to append another checklist. Either placement remains valid. The C16 program-unit
rule, C17 source-proven scope normalization and C18 natural-choice instruction
are retained, with no new display quota, binding, data field or semantic checker.

Review caught a preservation gap before freeze: the first replacement retained
the unknown-scope restriction but dropped the old **incomplete-quote** restriction.
The parent accepted a narrow repair to the exact passage: “incomplete quotes or
reported amounts with unknown scope do not establish a per-person fare, all-in
trip cost or cheapest-overall choice.” The plan, source and test constant now
match. Known raw values remain known, including zero; preserving them does not
establish a missing full-price basis or fill unknown amounts. This closes the
identified instruction-scope regression without changing runtime policy.

Independent post-fix probes verify literal old/new plan paragraphs (including
trailing spaces) against the runtime replacement, with one exact occurrence of
the old span. All three actual archived C18 selector requests are unchanged.
Complete composer requests equal those archived requests after only the adopted
paragraph substitution. Correction envelopes, both with and without supplied
findings, likewise differ only by that substitution. Inputs, output schemas and
LOW/MEDIUM/LOW settings remain exact. All three old C18 artifacts replay exactly.
Every runtime function/class AST equals archived C18, and the full archived
runtime/preview comparison finds only `category.py` profile-map/instruction
changes. No raw fact, card or normalized-condition row changes.

The new tests cover the three request branches, correction feedback, offline
two-pass run/replay, instruction-request tamper and registry inclusion. Saved
wires are reused unedited: that is compatibility evidence, not semantic proof
or a revision of q059's qualified H/M2 failures. The implementer reports **5/5
targeted tests**, Ruff/mypy/diff checks and **60/60 actual historical artifact
replays** passed after the guard repair, with source/tests frozen. This reviewer
ran the independent request/plan/AST/replay probes above rather than duplicating
the broad suite.

**Disposition: c19 implementation cleared; the identified preservation blocker
is resolved and no known reviewed code blocker remains.** Runner strict
60-artifact archive/request/receipt/preview verification is a separate required
gate before authorized scouts. Fresh delivered answers must still establish
source truth, useful explanations and consolidated uncertainty; no semantic or
latency improvement follows from these mechanical controls. No live calls or
product edits by this reviewer. No additional escalation recommended for this
narrow experiment; the hard c20 stop and mandatory final review remain intact.

## c20 final-candidate condition-group review

Reviewed the exact parent-approved campaign-plan replacement, `category.py`,
`test_results_category_c20_conditions.py` and the registry update. Only the two
C19 sentences governing condition-explanation coverage/placement are replaced.
The new wording intersects each relevant condition row's affected aliases with
the choices actually shown and calls for one explanation covering that group,
not a separate explanation for each quote/card. A singleton may remain local.
Caption, comparison, opening and other prose are all permitted locations. This
does not mean one output sentence or block per row and does not require a shared
limitations block, fixed order or new layout.

Independent probes confirmed the exact old/new plan paragraphs including
trailing spaces, with the old span occurring once. Against all three **actual
archived C19 requests**, selectors are exact and complete composer requests
differ only by that approved substitution. Correction requests with and without
supplied findings likewise differ only in the span. All other author text,
inputs, output schemas and LOW/MEDIUM/LOW settings remain exact, including the
C19 incomplete-known-scope restriction, known-value distinctions and prohibition
on an extra checklist; C18 natural reasons and C16 program-unit guidance remain.
C17 condition normalization and all raw facts/cards are unchanged. All three C19
artifacts replay exactly under the current code. Every runtime function/class
AST equals archived C19; only profile instructions/maps in `category.py` differ
across the archived runtime/preview source set.

The new controls exercise the three request branches, correction feedback,
offline two-pass run/replay, request-instruction tamper and registry inclusion.
The offline writer reuses the admitted C19 wires, including q061's original
qualified M2 failure. Exact replay preserves that answer; it is not semantic
improvement or historical regrading. The implementer reports **5/5 targeted
tests** and Ruff/mypy/diff checks passed with source/tests frozen. This reviewer
ran the independent probes above rather than duplicating the broad suite.

**Disposition: c20 implementation cleared; no known reviewed code blocker.**
The implementer's final receipt confirms **63/63 actual historical artifacts
replayed exactly**, exit zero, after the targeted/static checks, with no further
source edits planned. The runner's strict source/request/receipt/preview
verification remains a separate required scout gate. No live calls or product
edits by this reviewer; no additional escalation needed before this bounded
final experiment beyond the mandatory post-C20 review below.

C20 is the final authorized candidate, with no C21. The mandatory post-C20
architect review follows actual scouts and all source grades **before any
confirmation or closeout**, regardless of scout results. Request equality and
prompt wording do not establish semantic, latency or default qualification.
