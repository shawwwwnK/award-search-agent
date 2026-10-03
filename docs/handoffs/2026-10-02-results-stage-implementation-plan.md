# Results Stage: detailed execution plan

Date: 2026-10-02. Status: **investigation-backed implementation proposal; no implementation or qualification claimed**.

This plan makes the [three milestones](2026-10-02-results-stage-milestones.md) executable.
Accepted presentation choices remain in the [v1 design](2026-10-02-results-stage-v1-design.md).
New schemas, file names, commands, failure settings, and evaluation counts below are proposals.
They do not change request, planning, provider, matching, or M2 style policy.

**2026-10-03 clarification:** the owner requires the LLM to author the main answer and its
structure, with code filling factual blanks. The
[authored-template refinement](2026-10-03-results-stage-authored-template.md) supersedes the
M2 editorial-choice/assembled-answer contract below. M1 and M3 remain applicable; M2 should
implement model-authored Markdown with bound factual placeholders, not a code-owned layout.
Structured output versus a submission tool is still a recommendation to discuss.

## Execution order

| Slice | Work product | Gate before the next slice |
| --- | --- | --- |
| M1.1 | Typed brief, projection receipt, identity and grouping rules | Exact variant and price linkage; all original records accounted for. |
| M1.2 | Factored model input, condition and coverage summaries, saved walkthroughs | All three saved requests preserve distinct options; cleaned size and missing information documented. |
| M2.1 | Code-rendered answer skeleton from a fake editorial plan | Correct facts, local dates, scope, labels, and mandatory conditions without a model. |
| M2.2 | Structured LLM selection/editorial adapter, validation and failure handling | Fake-writer error tests and CLI replay pass; failure behavior is explicit. |
| M2.3 | Bounded saved/synthetic generation diagnostic | Actual rendered answers and receipts preserved for review and M3. |
| M3.1 | Judge contract, labeled calibration examples, offline runner checks | Judge references validate; prompt/rubric frozen for the diagnostic. |
| M3.2 | Repeated writer trials, advisory judging, adjudication report | Per-case hard failures, judge misses/false alarms, and useful-selection evidence reported. |

M1 is the first implementation cut. Tests and examples accompany each slice rather than being
left to M3. M3 evaluates semantic quality and usefulness that structural checks cannot establish.

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

1. Validate the original `RankedJourneySet`, including its existing derivation/source binding.
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

- Requirement/evidence unknowns that make a journey conditional become specific checks beside
  that journey, such as confirming enough seats or traveler coverage.
- Separate-ticket obligations remain visible even for admitted mixed journeys. Render the
  recorded transfer interval, and distinguish passing the timing rule from practical transfer
  assurance. Never infer baggage, immigration, terminal, or protection arrangements.
- Price limitations and unreported cabins remain visible without being relabeled as eligibility
  blockers. Observed zero fees are different from absent/unknown fees.
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

## M2 contract: editorial plan and code-filled answer

Proposed minimal response schema:

```text
ResultsWritingPlan
  opening
  highlights[]
    primary: EditorialChoice
    alternate: EditorialChoice | null
  cash_benchmark_id | null
  incomplete_choices[]: {possibility_id, explanation}

EditorialChoice
  alternative_id
  explanation
  comparison_ids[]
  premium_price_judgment | null
```

The response carries no authoritative route, amount, time, style, status, or required-condition
fields. The service stamps the canonical plan with the exact brief digest; the model need not
echo an opaque digest. `explanation` carries the fuzzy appeal/tradeoff; the optional premium-price judgment is
explicitly editorial and attached to that whole alternative. The renderer may combine those
two text fields into one paragraph. A valid choice need not have a full style membership.

The opening supplies shared editorial interpretation. Code supplies mandatory shared notes
(actual coverage, comparison assumptions when used, common booking checks) once; option-specific
requirements stay beside the affected option. Give those intended notes to the writer so it
can avoid repetition. Do not let model prose suppress a required note.

Validate response binding, selected IDs, original pool/status, award groups, and at most one
alternate per primary, with five complete alternatives total. Incomplete choices are allowed
only when no complete journey exists, capped at two; rejected combinations cannot be selected.
The separate benchmark cannot enter the award shortlist or style-label pool.

Each award group may have only one primary highlight. Its optional alternate must belong to
that same group and be a different complete alternative. Selected IDs cannot repeat across
highlights. Multiple primary/alternate combinations cannot bypass the per-group limit.

### Comparison authority

Explicit comparison IDs authorize code-owned sentences. A fastest sentence binds the exact
existing full eligible-pool time minimum (including conditional alternatives), qualified to
the observed complete journeys. Time membership alone does not authorize it.

A lowest-cost sentence binds the sufficiently complete heuristic reference and its stated pool,
not cash payable or market value. Render the points valuation and applicable tax-estimate
assumptions when used; incompletely priced alternatives still prevent an unqualified cheapest
claim. The three saved requests expose no such complete cost comparison. Do not introduce new
FX, pairwise valuation, savings calculations, or weighted scores in Results.

An LLM can still imply unsupported comparisons in its prose. A mechanically valid plan therefore
does not establish semantic groundedness; M3 reviews the whole answer, including implications.

### Rendering rules and actual repository traps

- Derive local dates/times from validated timezone-aware instants plus IANA airport timezones.
  Some saved award raw local strings contain a misleading `Z` suffix. Do not treat those strings
  as UTC or print that suffix. If a timezone is unavailable, disclose the display limitation
  instead of guessing. Preserve overnight/date-line arrival differences.
  The saved `2026-10-05T23:45:00Z` SFO wall-time example displays Oct 5, 23:45 locally;
  its actual UTC instant is Oct 6, 06:45. This exact difference needs a regression assertion.
- Elapsed journey duration includes positioning and transfer waits; use the existing exact value.
- Show reported journey cabin and reported per-leg differences at their actual evidence level.
  Journey-level cabin acceptance does not confirm every leg. Saved cash cabin/legs are unreported;
  requested search cabin is not observed cabin.
- Name the redemption program clearly. Do not infer operating airline from a flight-number
  prefix, a program name, or requested cabin. Show carriers only when reported.
- Show points, fees, and cash quotes as separate components with currency/unit/scope and relevant
  unknowns. An estimated fee is not observed, and unknown scope is not a normalized lower bound.
- Render Time/Cost/Premium only for definite supplied memberships. Premium economy remains a
  separately described option; possible/undetermined Cost is not a Cost label.
- Keep source paths internal; present component observation timing accurately. A newer cash
  observation does not imply the award was refreshed then.

The public answer remains journey-first, usually three choices and 300–500 words as a soft
target. An alternate retains its own factual summary and checks. Required information takes
priority over a rigid word count.

### Invocation and failure proposal

Reuse the repository's narrow structured-response adapter and optional trace collector. Configure
the actual timeout, maximum output tokens, and SDK retry count explicitly and record them.
The inspected local SDK defaults allow two retries: one application invocation can mean three
transport attempts. Record both, without claiming an end-to-end bound that was not tested.

Initial recommendation: one application generation invocation, no automatic rewrite/repair,
and a short deterministic fallback when valid source data exists but generation fails. A
timeout, refusal, truncated/malformed response, or invalid plan is a generation failure. An
empty search result is a valid outcome. Invalid upstream data is a source error and cannot
support a normal factual fallback.

Proposed fallback breadth: one fastest complete alternative, stable-ID tie-break, with all
its facts/conditions and a brief coverage note; otherwise one supported incomplete possibility,
or a truthful no-useful-results/failure summary. Mark fallback in the artifact and state briefly
that the usual explanation could not be generated. This remains a recommendation, not a new
owner decision. When showing one of a larger complete pool, state how many complete alternatives
remain in that pool so the limited summary cannot imply an exhaustive shortlist. Fluent but
misleading prose is evaluated separately; M3 is not a runtime judge.

No input cap or overflow architecture is introduced. Measure cleaned inputs first. If a real
context-limit failure occurs, report it without silently pruning distinct alternatives.

## M3: practical evaluation protocol

Judge input: frozen brief and digest, complete rendered answer, deterministic validation receipt,
and compact fact-ID index. Do not expose private reasoning or ask the writer to judge its own
answer. Use a separate judge prompt and preferably a distinct model, record identities, and
disclose that model separation does not guarantee independent errors.

Proposed judge response: one record per criterion, with `pass`, `fail`, `not_applicable`, or
`uncertain`; exact answer passage (null for omission), affected alternative IDs, supporting fact
IDs, and concise rationale. Multiple findings can belong to one criterion. Validate referenced
facts and passage existence; invalid judge output is an evaluator error, not a clean answer.

Hard criteria: invented facts; combined variants; wrong scope; changed status/style; hidden
conditions; unsupported comparisons; rejected-trip promotion; false exhaustive-search claims;
guaranteed bookability. Quality criteria: useful distinct choice, clear tradeoffs, honest premium
judgment, natural/concise language, and self-contained usefulness. No weighted overall score.

### Proposed case matrix

| Case | Main purpose |
| --- | --- |
| Saved mixed access | Time versus conditional Premium choices; missing complete cost reference. |
| Saved exact business | Overlapping styles, all-conditional pool, choice without redundant highlights. |
| Saved positioning | Conditional fastest versus admitted egress variants, long wait, missing scopes/cabins, partial coverage. |
| Synthetic complete costs | Comparable heuristic costs and clearly disclosed valuation/tax estimate. |
| Synthetic opposing cash variants | Same award, meaningful price/time alternate, no splicing. |
| Synthetic fees | Missing taxes versus observed zero; estimation without invented scope. |
| Synthetic cabins | Mixed reported cabins, unknown legs/cash cabin, no implied all-business journey. |
| Synthetic premium economy | Useful choice without full Premium membership. |
| Synthetic failed coverage | Partial/failure outcome distinct from exhaustive empty findings. |
| Synthetic incomplete only | Up to two supported observations with missing pieces, no rejected promotion. |
| Synthetic no useful results | Accurate empty/failure answer without padding. |
| Synthetic conflicting near-duplicates | Same-looking schedules with materially different scope/status/conditions remain distinct. |

Proposed repeated diagnostic: three writer trials per case, or 36 answers; one judge evaluation
per answer. Start calibration with two reviewed good answers and nine deliberately flawed
answers, one for each hard criterion. Include fluent false editorial prose beside code-correct
factual summaries. That means 47 judge evaluations and 83 writer-plus-judge invocations if each
finishes in one application call. SDK attempts/retries, tokens, elapsed time, and errors are
measured separately; this is a proposed workload, not observed cost or usage.

If the judge prompt is tuned on the calibration examples, freeze it before the diagnostic and
use fresh labeled examples for any later accuracy claim. Report missed planted failures and
false alarms with denominators; do not claim holdout reliability from training examples.
Judge results are advisory. Review every hard flag, every known flawed calibration answer,
and a declared sample of apparently clean outputs. Adjudicate all disagreements relevant to
acceptance. A missed failure does not make a flawed writer answer acceptable.

Report selection IDs and variation across trials, per-case failures, structural results, judge
errors, adjudication, prompt/settings hashes, and reconciled traces/usage. Three trials provide
development diagnostics, not statistical reliability. Owner interpretation and acceptance
remain explicit and separate from generated measurements.

## Proposed implementation seams

| Files to add | Responsibility |
| --- | --- |
| `src/award_agent/results/contracts.py`, `projection.py` | Brief, internal receipt, joins/grouping/factoring/conditions/coverage. |
| `src/award_agent/results/rendering.py`, `validation.py` | Code-filled answer, mandatory notes, editorial-plan checks. |
| `src/award_agent/results/writer.py`, `openai_writer.py`, `pipeline.py` | Narrow writer protocol, adapter, orchestration and explicit outcomes. |
| `src/award_agent/cli/results.py` | Explicit saved-ranked-input CLI; new immutable output paths; no provider execution. |
| `tests/unit/test_results_projection.py`, `test_results_rendering.py`, `test_results_generation.py`, `test_results_cli.py` | Offline invariant, regression, fake-writer and CLI tests. |
| `src/award_agent/evaluation/results_stage.py`, `src/award_agent/cli/results_stage_eval.py` | Case runner, advisory judge and evaluation receipts. |
| `evals/results_stage/`, `tests/unit/test_results_stage_eval.py` | Versioned casebooks/calibration and offline runner/judge contract tests. |
| `docs/evaluation/results-stage-protocol.md`, `evidence/results-stage/` | Protocol, reviewed examples and public/sanitized evidence indexes; raw private traces stay ignored. |

Reuse frozen ranking/provider/planning contracts, existing Pydantic base conventions,
`LLMCallTraceCollector`, and current immutable-output conventions. Do not refactor upstream
stages to accommodate Results. Entry points and package exports are added only as implemented.

After implementation, run the scoped tests above, applicable lint checks, saved brief/renderer
replay checks, and the existing ranking corpus verification to confirm no upstream change.
These proposed files/commands do not exist yet; no clean-checkout Results execution is claimed.

## Remaining design work before the first cut

The principal product decisions are already settled. Finish concrete M1 schema examples and
condition-code coverage during M1.1; settle minimal generation failure/retry behavior before
M2.2; choose writer/judge settings and approved run budgets before live diagnostics. These are
targeted implementation details, not reasons to reopen accepted policies or add infrastructure.
