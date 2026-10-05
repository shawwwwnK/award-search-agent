# Results Stage: detailed execution plan

Date: 2026-10-02; revised 2026-10-04. Status: **reviewed engineering design; not implemented or qualified**.

## Active responsibility allocation — 2026-10-04

Ranking including its factual export is owner-closed; Results M2 is now owner-opened. The
[opening handoff](2026-10-04-results-m2-opening.md) makes offline M2.1 preparation/rendering the
first slice. This session opens the milestone without implementing Results runtime.

The owner approved moving reusable M1 factual projection into the
[Ranking M2 solution-export extension](2026-10-04-ranking-m2-solution-export.md). That contract
supersedes the M1 ownership/file proposals below: Ranking exports one compact view and receipt,
reusing existing assessments; Results consumes it directly. Slot formatting, presentation groups,
short handles, activated disclosure obligations and prompt preparation remain in Results M2.
Do not implement an equivalent `ResultsBrief` projection or a standalone Results M1 pipeline.
The M1 preservation requirements below apply to the Ranking export; later authoring/evaluation
mechanics retain their scope. Models, live budgets and fallback policy remain M2/M3 decisions.

The owner requested this design update and reaffirmed that the LLM controls the output structure.
The [v1 design](2026-10-02-results-stage-v1-design.md) records the product boundary;
[authored-template contract](2026-10-03-results-stage-authored-template.md) defines the model's
structural authority. Engineering recommendations below are concrete implementation targets,
not invented owner acceptance or authorization to run a live evaluation.

## Execution order

| Slice | Work product | Gate before the next slice |
| --- | --- | --- |
| Ranking M2 export | Trusted upstream input, factored solution view and source receipt | Preserved supplied conditions, exact variant/price linkage, complete record accounting and saved-case size measurements. |
| Results M2 preparation (next step) | Directly consume Ranking view; define display groups, handles, slots and activated disclosures | Authoring contract references exact exported facts without rebuilding another brief. |
| M2.1 | Substitute/validate hand-authored documents with different structures | Prose and comparison-table layouts pass; no code-owned skeleton; cross-part hidden slots fail. |
| M2.2 | Strict document-authoring adapter, outcomes and replay | Fake refusal/incomplete/error paths, explicit call budgets, saved-document replay pass. |
| M2.3 | Small generation diagnostic on frozen inputs | Actual filled answers reviewed for structural freedom, faithful conditions and usefulness. |
| M3.1 | Judge rubric, independent labels, runner and calibration | References/error accounting pass; judge frozen before held-out checks. Can begin alongside M2. |
| M3.2 | Repeated generation, advisory judging and adjudication | Exercised cases, hard failures, judge misses/false alarms and usefulness reported separately. |

Tests and examples accompany each slice. M3 does not postpone M1/M2 behavioral tests, and its
rubric starts early enough to inform the fixtures. Runtime judging is not part of v1.

## M1 contract: model view and internal evidence

Produce two bound artifacts. `ResultsBrief` is the compact model view. `ProjectionReceipt` is
the internal map to the validated frozen input; do not send raw attachments, repeated hashes,
provider bodies, and successful validation proofs to the model.

Suggested brief sections:

| Section | Content |
| --- | --- |
| Request | Original endpoints and supported endpoint alternatives, bounded departure timing, travelers, cabins, positioning permission, relevant supported preferences/flexibility. |
| Award components | One record per retained observed award identity: route, instants/local displays, known legs/cabins, program, points/fees and scope/units, evidence limitations, observation timing. |
| Cash components | One record per retained observed cash identity: endpoint schedule, known legs or reported sequence/stops, carriers if reported, cabin evidence, fare/currency/scope, observation timing. |
| Award groups | Common award reference and original request endpoint pair; separately retained complete alternative IDs. Existing family IDs remain in the internal map. |
| Complete alternatives | Award/cash references, topology, checked elapsed time and transfer, unchanged status, reason/condition IDs, full style states, complete/partial/unknown heuristic assessment, relevant planning-note IDs. |
| Conditions and shared notes | Concise dictionaries of specific requirements, booking checks, price limitations, cabin unknowns, and search limitations. Alternatives refer to applicable records. |
| Comparison facts | Qualified full-pool fastest ties and complete heuristic-cost reference/ties where supported. Include comparison scope and applicable assumptions. |
| Other outcomes | Separate cash benchmark candidates, supported incomplete observations and missing pieces, relevant rejected-combination conclusions. They are not complete alternatives. |
| Planning notes | Recorded supplemental rationale and relevant request flexibility, explicitly classified as planning explanation rather than flight observation. |

Common-record factoring is compression, not a different journey contract: resolving an alternative
must recover its complete route, price, elapsed duration, status, memberships, and conditions.
Small dictionaries may be expanded when that improves model readability; avoid opaque references
that require the model to infer missing relationships.

The internal receipt contains ranked-input and brief digests, projection version, candidate and
observation mappings, source paths/times, original reason records, exact-duplicate aliases,
excluded-status accounting, and summary provenance. Every original candidate has one disposition:
retained complete alternative, alias of a strictly equal alternative, rejected, or research-only.
Summary/unmatched observations and direct cash get separate accounting because they are not
necessarily journey candidates. Use collision-checked short presentation IDs, retaining full
original IDs internally; repeated projection must give the same IDs and content.

### Input authority and independent preservation checks

Owner decision, 2026-10-04: trust verified upstream output from this project. Results does not
add a matching-owned requirement verifier, restrict the workflow to pinned fixtures, or rederive
upstream eligibility and policy. Earlier verifier proposals are superseded by this decision.

Use the existing `RankedJourneySet` typed contract and resolve component/support references needed
for projection. Preserve supplied statuses, styles, requirements, booking obligations, component
cost completeness and unknowns. Keep source IDs and versions in the receipt. Malformed input or
unresolvable references produce an explicit source error.

Independent expected facts are manually asserted from the trusted input, without using the
production projector. Tests check that Results preserves supplied seat/party/cabin conditions,
exact variant/quote linkage, timezone displays, zero versus missing fees and cost limitations.
Pair deliberately faulty Results projections with valid controls. These tests target Results
omissions and alterations; they do not revalidate upstream matching decisions. A writer and judge
sharing one brief cannot discover facts that projection wrongly discarded.

### Exploratory cleanup measurement

The read-only probe factored award/cash components, repeated unknown-reason sets, and planning
rationale, without deleting eligible alternatives:

| Saved case | Original saved JSON bytes | Factored probe JSON bytes | Eligible variants | Award groups | Unique cash observations used by eligible variants |
| --- | ---: | ---: | ---: | ---: | ---: |
| Mixed access | 6,513,717 | 206,775 | 257 | 23 | 48 |
| Exact business | 4,866,650 | 98,469 | 106 | 3 | 42 |
| Positioning | 2,106,611 | 62,050 | 64 | 4 | 28 |

These are exploratory measurements, **not final sufficient brief sizes or token counts**. The
probe omits detailed incomplete possibilities, rejection conclusions, complete coverage
explanation, and the internal evidence map. The map belongs outside the model input, but useful
outcome/coverage details still need adding. No model context fit was measured. Strict duplicate
consolidation removes zero eligible variants here: no eligible award/cash observation pair
repeats within a saved case. Factoring drives the reduction.

M1 will measure the actual complete model view after those missing details are included. The
probe is `/private/tmp/results_m1_probe.py` with `/private/tmp/results-probe-*.json` outputs;
temporary probe paths are not required implementation artifacts or clean-checkout dependencies.

### Grouping and duplicate algorithm

1. Load the trusted upstream `RankedJourneySet` through its existing typed contract and record
   source identity and versions. Do not add a second upstream requirement verifier.
2. Resolve each candidate through its original award, optional cash, support/dependency, and
   assessment references. Missing/inconsistent references are source errors, not empty results.
3. Group initially by exact award observation identity and original endpoint pair. Preserve
   topology/positioning side as variant/subgroup information. This avoids speculative matching
   across programs, schedules, or incomplete identity data.
4. Consolidate complete alternatives only with the same award and cash observation IDs and if
   the entire decision-relevant resolved record agrees:
   component identity, schedule/route/cabin evidence, quotes/scope/units, status, requirements,
   booking obligations, styles, and meaningful planning limitations. Union original IDs and
   evidence; do not choose a favorable value from conflicting records.
5. Do not consolidate distinct observation IDs in initial v1. Equal-looking displays remain
   separate; grouping/factoring can improve readability without asserting identity. Missing
   flight-leg/cabin identity is especially insufficient evidence. Revisit cross-observation
   equivalence only with a separately specified rule and supporting evidence.
6. Recheck all alias/retained/excluded accounting and reconstruct every complete alternative.

Different cash prices, arrival times, requirements, or styles remain distinct within one award
group. Award identity grouping is deliberately conservative; a polished semantic grouping system
is not required to ship this bounded stage.

### Conditions, coverage, and unknowns

Use explicit mappings from existing reason codes, preserving original detail internally:

- Requirement/evidence unknowns that make a journey conditional become specific checks clearly
  associated with that journey, such as confirming enough seats or traveler coverage.
- Separate-ticket obligations remain visible even for admitted mixed journeys. Render the
  recorded transfer interval, and distinguish passing the timing rule from practical transfer
  assurance. Never infer baggage, immigration, terminal, or protection arrangements.
- Price limitations and unreported cabins remain visible without being relabeled as eligibility
  blockers. Observed zero fees are different from absent/unknown fees. Preserve positive supplied
  mixed-cabin evidence (including a reported raw mixed-cabin indicator) with its actual scope; do
  not reinterpret cabin policy or invent per-leg cabins from that indicator.
- An unmapped material reason gets a visible conservative description and mapping-gap receipt.
  Do not omit it or reclassify the upstream status.

Coverage summaries derive from actual streams/units and logical work: distinguish completed empty,
partial with observations, failed, unsupported, and omitted/budget-limited work. Counts alone do
not establish exhaustive airport/date coverage. Any described gap must map to the recorded work;
observations from partial work remain usable. The same applies to failure-only/empty outcomes.

The positioning case has 52 omitted detail units, one omitted cash unit, and one partial
positioning dependency under budget limits. Those overlapping graph units must not be presented
as 54 independent failed searches or as evidence that no more awards exist.

Existing scope is observation-wide, not individually established for points and fees. Copy that
scope to the relevant quotes without inventing finer granularity. Retain reported monetary units;
convert known minor units for display deterministically, without creating a per-person amount.
Unknown scope remains unknown even when traveler count or returned-party evidence is known.

For example, `award_travelers_unknown` and `result_validation_minimum_award_seats` can share one
plain-language party/seat-confirmation check while retaining both original reasons internally.
`separate_ticket_obligation` maps to separate bookings and applicable practical connection checks,
including when the source status is admitted. Test status-causing versus nonblocking reasons;
mapping does not change classification.

### Concrete saved variant checks

The positioning example provides these actual contrasting alternatives (IDs abbreviated only
for this discussion; implementation must retain full identifiers):

| Candidate | Complete route | Elapsed / separate-ticket wait | Award and cash quotes | Assessments / remaining checks |
| --- | --- | --- | --- | --- |
| `5d002…` | SFO–LAX cash, then LAX–IST–BKK award | 27h27 / 2h18 at LAX | Turkish: 110,000 points, taxes unknown; cash USD 179. Both quote scopes unknown. | Conditional; Time; Cost undetermined. Traveler/seat evidence and separate-booking checks stay visible. |
| `89c654…` | SFO–TPE–SIN award, then SIN–BKK cash | 27h30 / 3h50 at SIN | Aeroplan: 65,000 points and CAD 113.20 fees (11,320 minor units); cash USD 290. Quote scopes unknown. | Admitted; Time; Cost undetermined. Separate bookings and unreported component cabin details remain relevant. |

Neither example supports a per-traveler total or savings statement. M1 must preserve each
complete chain; M2 must not take one candidate's price and the other's duration.

Within the same Aeroplan egress group, another admitted Time variant has a quoted USD 196
SIN–BKK flight and yields a 29h50 journey with a 6h20 transfer, versus USD 290 / 27h30 / 3h50
above. Unknown fare scope and cabin remain visible. This is the direct same-award regression
case: selecting USD 196 with the 27h30 duration would be a hard failure.

## M2 contract: model-authored document, code-filled facts

Use `ResultsDocument {selections, benchmark_id, incomplete_ids, parts}` from the
[authored-template contract](2026-10-03-results-stage-authored-template.md). Every part has a
scope and model-written Markdown. Parts may repeat a journey scope and form table rows, separate
paragraphs or any supported arrangement. The LLM writes headings, order, grouping, whitespace,
explanations and emphasis. Code concatenates exactly, fills slots, and validates the final parsed
content. No code-generated cards, skeleton, shared-note section, or post-fill model rewrite.

### Selection, slots and association

- Each selection is a complete admitted/conditional alternative. No style membership is required.
  One primary per award group and at most one distinct alternate in that same group; `alternate_of`
  must name that selected primary. No cycles, repeated IDs or cross-group alternates. Count unique
  selected journeys, including alternates: **one to five when the complete pool is nonempty**
  for successful authorship, and zero when it is empty. A benchmark-only or empty shortlist
  cannot be a successful answer when complete alternatives exist. Display order remains model-owned.
- Code derives required slot obligations from each alternative and shared evidence. Aggregate
  fulfillment across all parts for the selected scope. A selected ID without visible facts is
  invalid; extra scope IDs are invalid. Requirements must be visibly associated with their journey.
  Shared universal checks may appear once; scope-specific checks cannot become a generic caveat.
- The separate cash anchor required by ADR 0022 must be addressed. If usable direct endpoint
  observations exist, the model chooses one separate benchmark and explains its limitations; if
  none is suitable, use the supplied benchmark-unavailable/unsuitable fact. Unknown scope permits
  an indicative quote, not a value/savings comparison. The benchmark never counts as an award
  highlight, receives a style, or displaces a complete award journey.
- Incomplete selections are allowed only when the complete pool is empty, with at most two
  supported possibilities. Rejected pairings are not incomplete viable journeys. Every incomplete
  presentation states the missing pieces; rejected conclusions are shared factual explanation.
- A slot resolves only within its scope. Parse the **whole concatenated** Markdown, retaining slot
  source maps; HTML/comments/code/link syntax crossing parts cannot hide a required disclosure.
  Use the small tested Markdown subset and single literal substitution from the template contract.

### Comparison authority

Shared `comparison:ID` slots authorize complete code-filled comparison statements. A fastest
statement binds the exact existing eligible-pool time minimum, including conditional alternatives,
and its ties. Qualify it to observed complete journeys; Time membership alone is insufficient.

A cost statement binds the existing sufficiently complete heuristic reference and stated pool.
Its slot includes the points valuation and applicable tax estimate, or requires their shared
assumption slots. Incompletely priced alternatives prevent an unqualified cheapest claim.
All three saved cases lack a complete cost reference. No new FX, savings arithmetic, pairwise
valuation, weighted score, or inferred price scope is introduced in Results. Editorial premium
appeal may discuss a quote with its limitations, without inventing personal redeemability or
current market value. Comparisons cannot serve as undeclared extra complete recommendations.

Scope checks prevent wrong-variant slot lookup; they do not prove that surrounding prose or table
headings describe the right scope. M3 reviews that semantic association in the completed answer.

### Factual display regressions

- Derive local dates/times from validated timezone-aware instants and airport IANA timezones;
  retain the timezone inputs/version needed for replay. Some saved award wall-time strings end
  in a misleading `Z`. SFO `2026-10-05T23:45:00Z` denotes Oct 5 23:45 locally in the saved parser
  context; the validated UTC instant is Oct 6 06:45. Test the distinction, overnight/date-line
  arrival dates, and missing timezone disclosure. Never reinterpret the raw suffix as UTC.
- Use the existing complete elapsed duration, including cash components and waits. Compare the
  Aeroplan USD 196 / 29h50 / 6h20 variant with USD 290 / 27h30 / 3h50 without splicing.
- Preserve journey versus leg cabin evidence. Requested cash cabin is not observed cabin;
  accepted journey-level award cabin does not prove all legs. Positive reported mixed-cabin
  information remains visible without silently changing matching policy.
- Name redemption program; name operating carriers only when actually reported. Flight-number
  prefixes and program names are not sufficient carrier evidence.
- Keep points, fees and cash quotes separate, including units, scope and unknowns. Convert
  known minor units for display, not to infer per-person amounts. Observed zero is not unknown.
- Definite Time/Cost/Premium memberships alone receive labels; premium economy is separate.
  Observation times remain component-specific. A cash retrieval does not refresh the award.

The usual three-choice, 300–500-word target is soft. Completeness and understandable association
of facts/conditions take priority. The LLM determines the actual visible arrangement.

### LLM call contract and failure outcomes

Use one strict Responses `text.format` submission, through a narrow writer protocol and a Results
adapter. Reuse repository Pydantic/trace patterns, not implicit client defaults. All wire fields
are required with explicit nulls where applicable; nested objects reject extra fields. Validate
the generated schema against the supported JSON Schema subset in offline tests. Strict formatting
does not establish truthful prose. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Instructions contain the authoring rules, slot catalog, and a few contrasting valid layouts.
The compact brief is separately delimited data; provider/planning text is never an instruction.
Do not pass raw provider bodies, credentials, unrelated history, or reasoning traces. No retrieval,
provider, booking, or fact-lookup tools are exposed. [Prompt guidance](https://developers.openai.com/api/docs/guides/prompt-engineering).

Proposed initial diagnostic profile: **one writer invocation, SDK `max_retries=0`, no automatic
repair or model fallback**, `store=False`, no conversation continuation or automatic truncation.
Set finite request timeout, cancellation/deadline behavior and `max_output_tokens` explicitly
before running; choose numerical budgets from actual prompt sizes and the chosen model. Do not
invent a measured latency/cost bound. The installed SDK is 1.109.1 and defaults to two retries
and a 600-second read timeout; using a bare client would hide material attempts/wait time.
A later transient-only retry policy requires an explicit bound/receipt, not stacked retry loops.
[Rate limits/retries](https://developers.openai.com/api/docs/guides/rate-limits),
[Responses migration/storage](https://developers.openai.com/api/docs/guides/migrate-to-responses).

`max_output_tokens` includes reasoning tokens on reasoning models. Require a completed response,
no refusal, the expected parsed type, and all deterministic document checks. Incomplete output,
even if partly parseable, never becomes a traveler answer. Do not rewrite the finished artifact.
[Reasoning output budgets](https://developers.openai.com/api/docs/guides/reasoning),
[refusals](https://developers.openai.com/api/docs/guides/structured-outputs#refusals-with-structured-outputs).

| Outcome dimension | Recorded meaning and behavior |
| --- | --- |
| Source | Trusted upstream input loaded and references resolved, or explicit `source_invalid`. Malformed/unresolvable input stops before generation and cannot support a factual fallback. |
| Search evidence | Complete alternatives / incomplete only / no useful observations, plus independent provider coverage state. Empty completed searches differ from failed or omitted work. |
| Generation | `completed`, `refused`, `incomplete`, `transport_error`, `invalid_document`, or `context_limit`; retain precise cause and attempt evidence. |
| Delivery | Model-authored filled answer, optional labeled factual fallback, or explicit failure. A fallback is never recorded as successful authorship. |
| Evaluation | Semantic and usefulness findings on the filled answer. An undetected false sentence may pass mechanical checks; the offline judge is not a runtime gate. |

Keep the originally proposed factual-summary fallback as an **open presentation choice**. The
concrete candidate policy is one fastest complete alternative with a stable-ID tie break and
all conditions; otherwise one supported incomplete possibility or a factual empty/failure summary.
It discloses generation failure, coverage, and how many complete alternatives were not displayed.
The owner has not chosen this breadth. Initial fake/live diagnostic failures can return explicit
failed artifacts while that choice is settled; do not silently install a fixed-layout fallback
as the normal answer. Resolve delivery behavior before claiming M2 accepted failure handling.

Measure the complete serialized prompt, schema and output allowance. No separate input cap,
hidden pruning, truncation, map/reduce selection or model-switch-on-overflow is adopted. If it
does not fit the chosen model, report that failure and measurements before changing policy.
Stable instructions/schema before variable data may benefit normal prefix caching; record any
cached tokens if reported. No custom cache infrastructure or saving claim is required.
[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

### Replay and observability

A `ResultsArtifact` binds the source and brief digests, projection/slot/Markdown-render versions,
upstream source versions, accepted typed document, selections, final Markdown and digest,
visible slot-to-fact map, validation receipt, and outcome dimensions. Freeze display time and
source timezone data used in substitution. Keep raw prompts/responses in private traces and
publish only sanitized evidence. `store=False` does not mean local traces are absent or establish
provider zero-retention guarantees.

Record writer/judge model identifiers (resolved snapshot when available), prompt/schema hashes,
SDK version, supported reasoning/settings, timeout/output/retry configuration, application calls,
observed HTTP attempts, latency, provider request ID where available, and reported usage. Unknown
usage on failure remains unknown. Do not label unobserved transport attempts as measured.

**Replay** validates the saved accepted document and substitutes against the same frozen brief
and versions with zero model/provider calls, producing identical final bytes/digest. **Regenerate**
makes a new model call and creates a new artifact; it need not reproduce wording or selection.
Unsupported historical versions fail explicitly. Add no application persistence service.

## M3: calibrated evaluation of the completed document

Judge the filled, parsed visible answer (including table headings/order and implications), not
merely the template or raw model JSON. Supply the brief, compact fact index and slot/source map.
Compute deterministic checks separately; they cannot be overruled by the judge. Withhold their
pass/fail verdict during semantic grading where practical to avoid anchoring the judge. Compare
outputs later. M1's independent source assertions remain necessary because both models see the brief.

Use a separate stateless judge call/prompt, preferably a different evaluated model; separation
alone does not guarantee independent errors. No private chain-of-thought is requested. A criterion
returns `pass`, `fail`, `not_applicable` or `uncertain`, plus exact passage/span (null for omission),
affected alternative IDs, source fact IDs and concise reason. Validate reference existence and
passage matching. A malformed/refused/timed-out judge response is an evaluator error, never a pass. Apply the
same explicit `store=False`, timeout/deadline, `max_output_tokens`, `max_retries=0`, no silent
repair, and completed-status/refusal/incomplete checks to the judge, with separately recorded
settings and evaluator-error counts.

Hard criteria: invented facts; combined variants; wrong price scope; changed eligibility/style;
hidden or misassociated conditions; unsupported comparisons; rejected-trip promotion; false
exhaustive-search claims; guaranteed bookability. Quality criteria: useful distinct selection,
omission regret, understandable tradeoffs and next checks, restrained premium judgment, natural
structure, concision and self-contained usefulness. Keep criterion results separate, without
one weighted score masking a hard violation. [Official evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

### Case matrix and diagnostic budget

| Case | Required exercised behavior |
| --- | --- |
| Saved mixed access | Time versus conditional Premium choices, absent complete cost reference. |
| Saved exact business | All-conditional pool, overlapping styles, useful selection from few award groups. |
| Saved positioning | Conditional fastest, admitted egress, opposing cash variants, long waits, missing scope/cabins, partial coverage. |
| Synthetic complete costs | Comparable heuristic costs, precise scope and disclosed valuation/tax assumptions. |
| Synthetic opposing cash variants | Same award with meaningful alternate, different prices/timing; no splicing. |
| Synthetic fees | Missing versus observed zero fees; estimate stays distinct from observation. |
| Synthetic cabins | Mixed reported cabin, unreported legs/cash, no all-business implication. |
| Synthetic premium economy | Useful choice without full Premium membership. |
| Synthetic failed coverage | Partial/failure distinguishable from completed empty work. |
| Synthetic incomplete only | Supported missing pieces, maximum two possibilities, no rejected promotion. |
| Synthetic no useful results | Truthful no-useful-observations answer, no padding. |
| Synthetic conflicting near-duplicates | Material scope/status/condition differences retained despite similar display. |

Each case declares source hashes, expected feature predicates, independent oracle origin, valid
controls and planted faults. Verify those predicates actually occur; labels and an empty artifact
index do not constitute exercised coverage. Add offline adversarial variants for malformed IDs,
missing/cross-part-hidden slots, injection text, refusal, truncation, invalid scopes and a sixth
journey. These are fake-adapter/parser tests, not extra live calls by default.

Keep the existing **12 cases × 3 writer trials = 36 answers** development diagnostic. One judge
call per answer plus the initial two correct/nine planted-fault calibration answers gives
47 judge calls, **83 total application calls** if each completes once. This arithmetic excludes
any extra calibration revision, held-out judge set or model comparison, which needs a separately
listed finite budget. No run occurred as part of this design update.

Build the proposed eleven calibration seeds; include both fluent false prose beside correct
slots and valid alternative layouts/wordings. Freeze after tuning and use newly labeled held-out
correct/incorrect pairs before claiming judge accuracy. Choose/report actual denominators, misses,
false alarms, uncertain decisions and harness errors; eleven tuned examples are not a holdout.
Retain human review of all hard flags/disagreements and a predeclared sample of apparently clean
answers. A missed planted fault cannot be excused by a favorable average.

Freeze input/projection, slot/render/schema versions, prompt, writer/judge settings and rubric
before the repeated campaign. Reuse M2.3 outputs only when all relevant hashes match and each
unique attempt is assigned once; otherwise rerun and disclose prior tuning. Three trials measure
development variation, not statistical reliability. Different good selections are allowed.

Acceptance requires no unresolved observed hard violations within the declared passing slice,
all planned families exercised, evaluator errors explicitly resolved/excluded from pass counts,
and owner review of representative useful and failed answers. Exclude no failed writer trial
from the denominator. Record selection variation, omission concerns, structural freedom, and
whether the traveler can identify program, remaining conditions, tradeoff and next manual check.
LLM judge scores alone do not establish task benefit, observed-cost coverage, or stage acceptance.

## Proposed implementation seams

| Files to add | Responsibility |
| --- | --- |
| `src/award_agent/ranking/projection_contracts.py`, `project_solutions.py` | Compact factual view, receipt, reference joins/factoring/conditions/coverage; implemented by the Ranking extension. |
| `src/award_agent/results/contracts.py` | Future authored-document/slot/disclosure contracts; directly consume the Ranking factual view. |
| `src/award_agent/results/rendering.py`, `validation.py` | Scoped slot parsing/substitution, visible obligations, model-authored document checks. |
| `src/award_agent/results/writer.py`, `openai_writer.py`, `pipeline.py` | Narrow writer protocol, adapter, orchestration and explicit outcomes. |
| `src/award_agent/cli/results.py` | Explicit saved-ranked-input CLI; new immutable output paths; no provider execution. |
| `tests/unit/test_ranking_solution_projection.py` | Implemented Ranking-owned factual preservation tests; do not duplicate their arithmetic/source projection in Results. |
| `tests/unit/test_results_rendering.py`, `test_results_generation.py`, `test_results_cli.py` | Future Results slot/disclosure, fake-writer, replay and CLI tests. |
| `src/award_agent/evaluation/results_stage.py`, `src/award_agent/cli/results_stage_eval.py` | Case runner, advisory judge and evaluation receipts. |
| `evals/results_stage/`, `tests/unit/test_results_stage_eval.py` | Versioned casebooks/calibration and offline runner/judge contract tests. |
| `docs/evaluation/results-stage-protocol.md`, `evidence/results-stage/` | Protocol, reviewed examples and public/sanitized evidence indexes; raw private traces stay ignored. |

Reuse frozen ranking/provider/planning contracts, existing Pydantic base conventions,
`LLMCallTraceCollector`, and current immutable-output conventions. Verified upstream output is
trusted under the owner's decision; no additional upstream verifier is required. Entry points
and package exports are added only as implemented.

After implementation, run the scoped tests above, applicable lint checks, saved brief/renderer
replay checks, and the existing ranking corpus verification to confirm no upstream change.
These proposed files/commands do not exist yet; no clean-checkout Results execution is claimed.

## Remaining choices and first cut

The Ranking M2 factual export is implemented and independently reviewed. Start Results M2 with
slot/disclosure preparation directly on `SolutionView`, then hand-authored rendering examples.
The owner accepted the factual preparation direction and settled the upstream trust boundary.
Authoring prompt/schema size and fit are measured during Results work, separately from export bytes.

Before M2 acceptance settle factual-fallback breadth versus explicit failure. Before live calls,
record writer/judge choices and finite numerical timeout/output/campaign budgets. Model selection
must follow Results evidence, not a general popularity recommendation. These choices do not delay
offline M1 or differently structured hand-authored M2.1 examples. No Results implementation,
live-model call, stage qualification, or full-workflow usefulness is claimed here.
