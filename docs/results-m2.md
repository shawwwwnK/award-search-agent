# Results M2 local API and CLI

**2026-10-29 final category-led disposition:** Stopped at the authorized c20
ceiling without qualification. All three c20 scouts meet timing, but q064 fails
M2 composition for repeating a local separate-ticket condition; q065/q066 pass
all six source-review axes. No c20 confirmation or controlled repair followed.
All66 artifacts verify against129 generation/count pairs. Final focused offline
verification passes112 category tests plus Ruff/mypy(64 files); the broad baseline
retains two historical gfly environment failures and is not a current full-suite
pass. Details and limits are in the [build log](build-log/2026-10-29-results-category-led.md).
Latest explicit opt-in is `category-c20`; public V27 is unchanged and unqualified.
No c21 or unused-budget extension, default adoption, M2 acceptance or M3 closeout
follows. The card/explorer backend does not establish frontend integration.

The [final architect review](reviews/2026-10-29-results-category-led-c20-architect-review.md)
recommends a future offline condition-ownership author-contract prototype rather
than further prompt iteration. It is not implemented or accepted, and declared
ownership would not verify untagged prose or numerical truth.

**Category-led implementation status:** The isolated `results/category.py` API
and explicit CLI `--category-profile` (available versions listed by CLI help) are implemented,
including source-resolved journey/lead cards, inline cash context and category
artifact replay. No category-led version has qualified; see the [active campaign](../evidence/results-stage/m2/structured/2026-10-29-category-led/README.md) for current versions and gates.
Public V27 wiring is unchanged and unqualified. See the new campaign log above.

**2026-10-29 new category-led invocation:** The owner approved flexible natural
explanation of Ranking's meaningful time/cost/premium perspectives and overlaps,
with flight facts displayed in source-resolved cards, common uncertainties stated
once, useful incomplete leads and a single full-cash comparison sentence.
Implementation/review and a new live Luna campaign of up to twenty iterations are
authorized; architect reviews occur every fifth iteration. Historical fast-profile
evidence and the stopped V30 ledger remain intact. The provisional V27 runtime is
not promoted by this authorization. See the [maintained campaign plan](plans/2026-10-29-results-category-led-campaign.md)
and [session evidence](build-log/2026-10-29-results-category-led.md).

**Earlier October 29 handover (superseded for this new campaign):** The owner
requested a documentation-only stop. See the
[current handover and main V3–V30 cycle summary](handoffs/2026-10-29-results-m2-fast-profile-handover.md).
That stopped campaign remains intact; the later invocation above authorizes the
separate category-led implementation and evaluation.

**Accepted owner direction, 2026-10-29; category-led qualification pending:** Keep Luna-authored
wording, preserve Ranking's time/cost/premium recommendation categories and
multi-style overlap, and reduce the full-cash benchmark to one brief source-faithful
comparison sentence. No new inline comparison-binding contract. Ranking memberships
remain authoritative, including possible/undetermined states; incomplete leads do
not acquire categories. The current provisional V27 runtime below does not yet
implement this correction. See [ADR0029](adr/0029-structured-results-and-local-workspace.md).


**Current public API/CLI default candidate, 2026-10-28:** `focused-v27` remains provisionally wired through `run_default_results` and CLI `measure` or live `author` when no channel/profile is specified. Its owned shared client closes on exit, uses explicit timeout and zero retries, and injected writer and measurer components remain available for offline execution. V27's fixed six-run cohort took 10.21–22.14 seconds (median11.5758); all passed U/M2, three passed H, and five were decision-rich. q108/q110/q112 contain material errors. Its controlled correction diagnostic passed H/U/M2/C in26.23 seconds, beyond the allowed overage. V23 remains the best earlier full cohort on facts and latency but q095 was basic. Final V30 was opt-in only: across its three scouts, q119 (admitted) was decision-rich, q120 (conditional) and q121 (incomplete) passed H/U/M2 but were basic without sparse-source exceptions; no frozen cohort or correction diagnostic followed. No profile qualifies and this work does not close M2. Live calls use Luna. The Streamlit harness retains its historical route; frontend integration, owner presentation acceptance and M3 remain separate.

## Provisional default and final V30 experiment

The provisional V27 path selects up to four exact authoring references from the complete eligible inventory, including any cash benchmark. V30 tested a maximum of two non-benchmark references (journeys or leads) plus one benchmark, three total. Only its incomplete branch received the lossless program-grouped view of all 378 leads across 13 programs; the complete branch kept its original source view. Neither cap requires a particular mix; code does not rank or filter source records, and the complete canonical explorer remains independent.

Code supplies self-contained selected source records, exact pairwise comparison dossiers and canonical traveler evidence. Requested party size, award support and seats, and component returned-traveler echoes remain distinct. Missing echo does not erase upstream seat-based support; known party size never determines unknown price scope. Free-text selector purposes are retained in source evidence but excluded from downstream authoring. Exact selected identities and comparison targets remain available.

The provisionally wired V27 profile keeps the complete branch on V23 `roles-v21`/`complete-v19` with no-reasoning selection and low-reasoning authoring, both Fast. Its incomplete branch uses `roles-v25`/`complete-v23` with medium-reasoning selection and authoring, both Fast. V30 was a separate opt-in: complete cases used LOW selection/MEDIUM authoring (`roles-v28`/`complete-v26`), incomplete cases MEDIUM selection/LOW authoring (`roles-v30`/`complete-v28`), both Fast; only the V30 incomplete branch used the grouped source view. A recoverable draft with actual failed mechanical checks permits one low/Fast full-document correction. Clean drafts stop after two generations. Unrecoverable failures do not receive another generation; there is no fourth call or SDK retry. Correction receives the frozen selected facts, references, registry and recomputed findings. Fewer mechanical failures wins, with correction preferred on ties; failed correction retains the recoverable draft and its explicit failure trace. Neither a clean draft nor successful correction proves ordinary prose truth. Neither profile qualifies. V30 scout runs took16.38/12.29/11.06 seconds and passed H/U/M2, but only q119 was decision-rich; q120 (conditional) and q121 (incomplete) were basic without sparse-source exceptions. The unchanged scout gate therefore stopped V30 before frozen confirmation or an actual correction diagnostic. V30 correction latency is unmeasured.

Luna controls the complete connected traveler answer: individual reasons and downsides, useful alternatives and local tradeoffs, relevant cash context and consolidated limitations. Optional temporal cards carry code-resolved exact endpoints, metrics and differences. Ordinary numerical and comparative prose remains model-authored and is not exhaustively checked.

The provisional API/CLI default uses `results-artifact-v11`: V27 complete uses `roles-v21`/`complete-v19`, and incomplete uses `roles-v25`/`complete-v23`. V30 opt-in used the same Artifact V11 conditional-correction boundary with branch markers `roles-v28`/`complete-v26` and `roles-v30`/`complete-v28`. V22's V12 records unconditional editorial patches. Both retain their own settings and phase-policy replay. Earlier contracts remain historical routes. The profile owns effort/tier settings and rejects CLI overrides.

```bash
.venv/bin/python -m award_agent.cli.results measure --projection projection.json --config data/results/fast-default.json --output measurement.json
.venv/bin/python -m award_agent.cli.results author --projection projection.json --config data/results/fast-default.json --output artifact.json --live
.venv/bin/python -m award_agent.cli.results replay --artifact artifact.json --output resolved.json
```

`measure` prepares the selector without API calls; it does not qualify context fit. `author --live` makes bounded model and exact input-count calls. Output paths must be new. `replay` reconstructs the saved answer offline. Python callers use `run_default_results(projection, config, writer=None, input_measurer=None)`; the current default returns `FocusedResultsArtifactV11`, and injected writers support offline tests. Historical routes remain explicit through `--legacy`, `--structured`, `--interactive --packet-profile ...`, and `--draft`.

V23 source evidence derives from the separately reviewed V22 initial drafts; byte/delivery proof and all original outcomes remain in the campaign. V23's six-run cohort took7.62–17.68 seconds (median11.22), passed H/U/M2 6/6 and C-rich 5/6; q095 was basic. Its controlled conditional-correction diagnostic passed in18.73 seconds. V27's frozen cohort took10.21–22.14 seconds (median11.5758), U/M2 6/6, H3/6, C-rich5/6; q108/q110/q112 contain material errors. Its separate correction passed H/U/M2/C but took26.23 seconds. V30 scouts took16.38/12.29/11.06 seconds, all H/U/M2 pass, but C-rich1/3; q120 (conditional) and q121 (incomplete) were basic without sparse-source exceptions. No V30 six-run confirmation or correction diagnostic was run. The public default remains provisional V27; the V30 opt-in failed its scout gate. V28 was implemented and scouted: its conditional NONE-selector phase reached44.78 seconds and ended with an API incomplete response. V29 and V30 were also implemented and scouted afterward. Campaign reservations are254/278, with24 unused; no V31 or further paid calls. All 109 summarized artifacts replay identically; strict archive verification exited 1 with seven flags classified as four verifier-assumption bugs, not demonstrated artifact corruption. The434-test Results baseline passed before V24 and later profiles had bounded tests; this does not establish a full-repository pass. Timing measures source parsing through the checked/resolved artifact, not an application SLA. See [campaign evidence](../evidence/results-stage/m2/structured/2026-10-28-fast-default/README.md) and [build log](build-log/2026-10-28-results-fast-default.md).

## October 24 structured channel (historical)

The structured backend implemented Results M2 U1–U3 with source-resolved facts and replaced mandatory prose slots/status/checklists. Its original schemas, checks and replay routing remain available. Ranking policy and upstream trust remain unchanged.

## October 27 interactive experiment (historical)

The separate interactive path uses `results-prepared-v6` and
`results-artifact-v7`. It gives Luna a decision packet containing every eligible
journey, source-backed facts and unknowns, while the resolved artifact retains the
complete eligible explorer and canonical evidence. The model authors the answer
and selects references; code resolves them into existing source-backed cards.
Invalid or wrong-role references fail explicitly. They are not repaired silently.

The new wire omits optional model-declared claim annotations. Mechanical checks
and source-resolved cards help bind choices to facts, but ordinary numerical prose
is not exhaustively checked. Live execution returns the constructed artifact;
independent reconstruction and tamper checks are available through V7 replay,
which makes no model or provider calls. This allocates replay work outside the
interactive return path.

**Status at the October 27 evaluation: experimental.** In particular,
`--packet-profile joined-v3` with low effort and Fast service has not yet earned a
speed or quality qualification. Fast is premium processing; the artifact records
the service tier returned by the API. That experiment established no model default
or broad latency guarantee.

## October 26 focused V8 experiment (historical)

The candidate `--packet-profile focused-v3` ran two sequential Luna
tasks: a selector sees the
full eligible inventory at no reasoning effort, then a composer uses explicit low
reasoning. Both use Fast service. The selector chooses at most eight exact source
references, including any cash benchmark, and code builds the composer packet from
those records. The composer receives facts only for the selected records, so its
comparisons and conclusions must stay within the choices it can see. The complete
canonical evidence and eligible explorer remain available in the artifact. This
selection boundary can leave useful alternatives outside the composed answer; the
focused profile did not qualify as the default. Its selector has one typed list capped
at eight total references. Code supplies exact elapsed/departure/arrival
comparisons within the selected journey pool; Luna still owns the prose and can
misstate other facts. Older focused-v1/v2 requests retain exact replay routing.

The versioned `results-artifact-v8` records `selector_settings` and
`composer_settings`. The run makes at most two count requests and two generation
requests, with no third correction pass. V8 replay reconstructs and checks both
stages offline without API calls. Existing V7 profiles and replay routes remain
available. In the frozen six-run saved-case evaluation, all completions took
6.72–8.46s (median 7.63s); independent factual/usefulness review passed 5/6 and
6/6, with basic comparative depth. One answer reports one seat where the source
reports two. Thus the speed target passes on these cases while strict combined
qualification fails. See the [final decision report](../evidence/results-stage/m2/structured/2026-10-26-under20/README.md).

For V7 interactive profiles, the CLI requires an explicit reasoning effort. The
focused profile owns both efforts and tiers internally; passing
`--reasoning-effort` or `--service-tier` with it is rejected. Set
`config.json` to `gpt-6-luna` when reproducing that evaluation; the command
does not override the configured model. For example:

```bash
.venv/bin/python -m award_agent.cli.results measure --interactive --reasoning-effort low --service-tier fast --packet-profile joined-v3 --projection projection.json --config config.json --output measurement.json
.venv/bin/python -m award_agent.cli.results author --interactive --reasoning-effort low --service-tier fast --packet-profile joined-v3 --projection projection.json --config config.json --output artifact.json --live
.venv/bin/python -m award_agent.cli.results replay --artifact artifact.json --output resolved.json
.venv/bin/python -m award_agent.cli.results author --interactive --packet-profile focused-v3 --projection projection.json --config config.json --output focused-artifact.json --live
.venv/bin/python -m award_agent.cli.results replay --artifact focused-artifact.json --output focused-resolved.json
```

The first command prepares the packet and returns its version and digests; it
makes no API calls and does not measure input bytes, tokens, or context fit. The
explicit V7 `--live` command makes count and writer API calls, with at most one
bounded correction generation. V8 instead uses one selector and one composer,
with no third correction. Replay makes no calls. See the [experiment and evidence](../evidence/results-stage/m2/structured/2026-10-26-under20/README.md),
[session log](build-log/2026-10-26-results-under20.md), and
[ADR 0029](adr/0029-structured-results-and-local-workspace.md). Existing V1–V6
artifact replay and the historical CLI routes remain available.

## October 25 historical generation latency interpretation

`WriterReceipt.latency_seconds` for structured authoring measures approximately
client request construction through receipt/serialization of the complete response.
It excludes token-count calls, later authored-document validation and upstream travel
searches. It does not measure time to first token or full application completion.
The October 25 saved-input Luna retry averaged 58.31 seconds per generation and 77.74
seconds of summed generation time per completed answer (including correction).
Cases ran concurrently, so their summed time is not session wall time.

The owner considered these delays too long. Composition/cost evidence is not latency
acceptance. The [October 25 investigation](plans/2026-10-25-results-m2-latency-investigation.md)
proposed input reduction, lower reasoning and first-usable-result measurement. The
separately versioned October 27 interactive work above now implements and evaluates
those input/effort choices while recording first-event, first-text and full-response
timings. Its diagnostic evidence does not rewrite the October 25 measurements;
the current focused-default section governs the October 28 local choice.

## October 25 composition correction

The [composition contract](plans/2026-10-25-results-m2-composition-correction.md)
clarifies the structured channel: the LLM authors a naturally connected answer with
individual highlights, relevant alternatives, embedded exact journey references,
cash context and consolidated applicable limitations. Cards carry code-resolved
facts; ordinary numerical prose remains model-authored and is not fully checked.
The complete explorer is independent and is placed at the end by the future frontend.
No renderer or runtime multi-agent orchestration is part of this correction.

**Development compatibility disposition:** the base authoring instructions change
in this correction. October 24 V6 artifacts remain byte-for-byte historical evidence,
but current-code replay rejects their saved preparation. Their captured source archives
retain the original implementation. The earlier nested factual v1/v2 replay result was
verified under October 24 source; it is not a current-code compatibility claim.
New composition artifacts must replay exactly. Legacy V1–V5 paths are unchanged.

The final [source-reviewed composition cohort](../evidence/results-stage/m2/structured/2026-10-25-composition-sol/README.md)
uses [an explicit GPT-6.1 Sol configuration](../evidence/results-stage/m2/structured/2026-10-25-composition-sol/evaluated-config.json).
Use that configuration when reproducing this evaluated writer; there is no implicit
model default. It uses the same final input/brief/code as the rejected Luna cohort,
with only model changed. The lead index now carries source-derived identity beside
each alias; no lead or eligible journey is removed. Review remains scoped evidence,
not a promise of repeatability or owner acceptance.

The original campaign remains historical. Select a new isolated campaign explicitly:

```bash
.venv/bin/python scripts/run_structured_results_eval.py --campaign-root evidence/results-stage/m2/structured/2026-10-25-composition-luna --case admitted --round 1
```

This prepares offline. Add `--live` only for an authorized new paid invocation;
case directories, call reservations, requests and receipts cannot be overwritten.
See the [session log](build-log/2026-10-25-results-m2-composition-correction.md).

## Structured Results V6

`resolve_workspace(projection)` exposes every eligible exact variant, conservative
award-family groups, component facts, direct cash benchmarks and incomplete leads.
`select_groups(evidence, sort="shortest")` returns actual representatives with no
network work; supported sorts also include `departure`, `lowest_cash`,
`fewest_points` (requires one `program`) and `comparison_cost`. Missing or
incomparable values follow comparable values. The latter cost is Ranking's
heuristic, not payable cash. Known observed values use the projection's frozen FX
snapshot and retain their original amount/unit/scope; unsupported units and missing
rates remain explicit.

```python
from award_agent.results import resolve_workspace, select_groups
from award_agent.results.structured import run_structured_results, replay_structured_results
from award_agent.results.adapter import OpenAIStructuredResultsWriter, OpenAIResultsInputMeasurer

evidence = resolve_workspace(projection)  # no model/provider/rate calls
groups = select_groups(evidence)
artifact = run_structured_results(projection, config, OpenAIStructuredResultsWriter(),
                                 input_measurer=OpenAIResultsInputMeasurer())
answer = replay_structured_results(artifact)  # no calls
```

The model writes ordered narrative and typed exact references using the complete
compact catalog. Code binds aliases and resolves facts. Selected references and
declared claims are checked; one correction follows only a recoverable draft with
failed checks. The draft with fewer failed findings is retained, with correction
winning ties. Unrecoverable API/refusal/schema failure does not authorize another
generation. A failed or context-limited authored answer retains `artifact.evidence`;
its `resolved` answer is `None`. Invalid source is an explicit error. Scoped claim
checks do not prove arbitrary prose truth or useful selection.

New authoring contracts are `results-document-v2`, `results-prepared-v5` and
`results-artifact-v6`. Current factual output uses `results-workspace-evidence-v2`
and `results-resolved-v2`, including source-known component departure dates when
clock times are absent. Saved v1 factual shapes retain their original fields; the outer artifact version
remains V6. Historical exact-replay claims are source-version-specific as described
in the October 25 compatibility disposition above.
Inspect `artifact.resolved` alongside `artifact.evidence`; no second model-authored
Markdown answer is generated. `resolved.findings` and unavailable reference blocks
preserve annotated outcomes for the later frontend.

```bash
.venv/bin/python -m award_agent.cli.results measure --structured --projection projection.json --config config.json --output measurement.json
.venv/bin/python -m award_agent.cli.results author --structured --projection projection.json --config config.json --draft structured-draft.json --output artifact.json
.venv/bin/python -m award_agent.cli.results replay --artifact artifact.json --output resolved.json
```

`author --structured --live` replaces `--draft` and makes explicit paid count/writer
calls using supplied settings. Replay dispatches on the outer artifact version;
legacy replay emits the original Markdown, V6 replay emits the resolved JSON.
All output paths must be new. The bounded saved-case diagnostic is
`scripts/run_structured_results_eval.py`; it is offline by default, with explicit
`--case`, `--round` and `--live` controls and an immutable campaign call ledger.

New-run FX is explicit: `harness.pipeline.rank` (and the acquisition pipeline
entry points) accepts either `fx_snapshot=` or `fx_acquirer=acquire_fx_snapshot`.
The acquirer runs once before Ranking; the historical default remains the supplied
saved FX file. It returns an acquisition receipt on `RankingRun.fx_receipt`.
To retain that receipt in structured evidence, construct `FxAcquisition` from this
receipt and the run's embedded snapshot and pass `fx_acquisition=` to
`run_structured_results` or `resolve_workspace`. A mismatched snapshot is rejected.
Supplied historical snapshots need no invented acquisition receipt. Acquisition
outage is explicit and yields USD-only identity conversion, retaining original
non-USD amounts. Ordinary resolution/replay never refreshes FX.

Verification and diagnostic results are in the
[implementation log](build-log/2026-10-24-results-m2-structured-implementation.md)
and [evidence record](../evidence/results-stage/m2/structured/2026-10-24-luna/README.md).
That October 24 evidence used an explicit evaluated configuration; it did not
qualify a default or general model context fit. It does not establish frontend/M3 acceptance.

Results M2's [October 8 engineering closeout](handoffs/2026-10-08-results-m2-closeout.md)
is historical. On October 9 the owner reopened presentation acceptance after
reviewing the end-to-end answers. M3 remains planned; diagnostic settings and
broader qualification limits remain separate. The
[presentation iteration record](../evidence/end-to-end/presentation/README.md)
preserves original answers and separately labeled revisions for owner review.
Live iteration stopped at the owner's request after source revision 006 to review
API spending. On October 20 the owner authorized a bounded Luna evaluation of the
compact input; its three-case diagnostic is recorded. Presentation acceptance remains
pending. See the [session log](build-log/2026-10-09-results-m2-presentation.md)
for the original cost review and the [compact-input build log](build-log/2026-10-20-results-m2-compact-input.md)
for that evaluation's verification status.

## 2026-10-20 compact writer input

The compact implementation uses `results-artifact-v5` with `results-prepared-v4`.
All admitted and conditional candidates remain individually selectable; rejected
rows are replaced with source-backed summaries, while the full canonical projection
and comparison authority stay in retained artifacts. Short J/A/C references bind
writer choices to canonical records, and conservative fact groups retain each
member's reference, retrieval timestamp and source association. The implementation
and offline preservation/measurement gates have passed for their declared scope.
The three-case Luna diagnostic used five generations and five input-count calls,
recording 843,051 input and 21,591 output tokens. Admitted and incomplete deliveries
were mechanically clean; conditional delivery was annotated with two shared-disclosure
key findings. Independent review also identified presentation and choice-diversity
issues. These are diagnostic observations; no M2/M3 qualification or owner presentation
acceptance is claimed. See [ADR 0026](adr/0026-model-authored-results-with-bound-facts.md#2026-10-20-amendment--compact-model-facing-input),
the [plan](plans/2026-10-20-2238-perf-compact-results-input-plan.md), the
[case evidence](../evidence/results-stage/m2/compact-input/2026-10-20-luna/README.md)
and [build log](build-log/2026-10-20-results-m2-compact-input.md).
The post-live V5-specific cross-seed replay fix passed its seven-artifact matrix;
the older historical finding-order concern remains separately open.

Results consumes Ranking's `SolutionProjection` (the trusted `SolutionView` and its
`ProjectionReceipt`). It preserves alternatives and source dispositions, supplies scoped factual
slots, and checks selected claims and disclosure visibility. The writer controls answer layout.
No Results code invokes travel providers or recomputes upstream eligibility.

```python
from award_agent.results import ResultsConfig, run_results, replay_results
from award_agent.results.adapter import OpenAIResultsInputMeasurer, OpenAIResultsWriter

# projection is a validated Ranking SolutionProjection.
# All numeric settings and the model name must be supplied explicitly.
artifact = run_results(projection, config, writer, input_measurer=OpenAIResultsInputMeasurer())
markdown = replay_results(artifact)  # no writer or network access
```

`ResultsConfig` requires `model`, `max_output_tokens`, `timeout_seconds`,
`context_limit_tokens`, and `prompt_overhead_tokens`. This historical API has no
implicit model or campaign configuration; the current focused default and its
explicit config are described above. The adapter disables SDK retries, request
storage, and automatic input truncation. Each invocation has the configured
timeout; this is not a composed end-to-end deadline.
Caller interruption propagates; authoring does not start background tasks.

Optional `max_input_tokens` supplies a separate model input ceiling. `authoring_guidance` adds
explicit run-specific instructions; absent guidance preserves the original preparation. The writer
still controls layout and prose. API callers can omit `input_measurer` for the original conservative
byte gate; CLI `--live` counts the exact token-bearing request before each authoring attempt.

Use the CLI through `python -m award_agent.cli.results` (or the installed `award-results` entry
point). Every output path must be new, and inputs are checked again before atomic publication.

```sh
python -m award_agent.cli.results measure --legacy --projection solutions.json --config config.json --output measurement.json
python -m award_agent.cli.results author --legacy --projection solutions.json --config config.json --draft initial.json --correction corrected.json --output artifact.json
python -m award_agent.cli.results replay --artifact artifact.json --output answer.md
```

Offline authoring reads `ResultsDocument` JSON. Without `--correction`, the same frozen draft is
returned if correction is needed. Live authoring requires replacing `--draft` with the explicit
`--live` flag, retaining `--legacy`, and supplying API credentials through the
ordinary SDK environment. No live calls were made during the original October 7
implementation of this interface. A non-delivered authoring outcome writes its failure
artifact and exits with status 1. The [October 8 diagnostic](build-log/2026-10-08-results-m2-luna-live.md)
records subsequent live authoring. Invalid source or CLI configuration raises before authoring.

Documents contain a `selection` manifest and ordered `parts`. Each part has a `scope` (`shared`,
`journey`, `benchmark`, or `incomplete`), an exact `reference_id`, authored `markdown`, and declared
`claims`. Preparation exposes available slot names. `{{fact:key}}` resolves only within the part's
scope, once, as escaped literal source text. Parts can repeat and interleave; authored separators
are retained. Unsupported references use “Details unavailable” with local notices. The
`disclosures` metadata cannot substitute for visible source-bound facts.

New presentation runs use `results-artifact-v4` with `results-prepared-v3`; these
preserve the traveler-facing fact display, local flight dates/times, readable amounts,
short visible labels and ordinary language for search limits and booking conditions.
New compact-input runs use `results-artifact-v5` with `results-prepared-v4`, adding
the compact model-facing catalog and typed references. V1–V4 artifacts retain their
historical behavior. Writer structure remains free; formatting does not establish
semantic truth or bookability.

The V3 shared-disclosure rules continue in V4 and V5. Historical V3 uses `results-prepared-v2`.
`ResultsPart.shared_disclosures` binds a fact key to at least two selected eligible journey IDs
whose source-slot values match exactly; the shared part must visibly contain the fact and each
target's stable identifier. A key is unique within one part, while valid bindings and repeated
facts may appear across parts or other occurrences. Full journey disclosures apply only to
selected recommendations. Unselected journey notes retain visible identity, exact source status and
source requirements/reason; rejected candidates are visibly excluded, while admitted/conditional
notes preserve that exact status. The v1/v2 replay paths retain their original behavior. The
corrected v3 behavior passed the 112-test Results suite, historical replay and independent
identity/note probes; this verifies the scoped engineering cases, not full contract coverage or
semantic truth. See the
[disclosure-reconciliation record](build-log/2026-10-08-results-m2-disclosure-reconciliation.md).

An optional model-authored `identifier` on journey parts can provide a friendly label such as
“Option A.” It must be visible, unique to that variant and stable when the journey resumes.
The internal candidate ID remains in the artifact. In V4 and V5 selected journeys require
a friendly visible label; benchmark and incomplete observations likewise use
stable visible labels while their IDs stay in metadata. For a single award with
no cash flight, an overall route/departure/arrival slot also discloses its award
counterpart only when the underlying source values match exactly. This avoids
duplicated schedules without removing distinct flight facts.
Notice placement is tested with an independent Markdown renderer, including columns and cells
spanning parts. This mechanical evidence does not qualify arbitrary presentation or prose.

Claim kinds are `cabin`, `connection_protection`, `price_scope`, `comparison`, `eligibility`, and
`other`. Initial checked propositions include `journey_business`, `all_legs_business`,
`all_award_legs_business`, `protected_connection`, `party_total`, `per_traveler`, `fastest`, `cheapest`, and
`no_unresolved_requirements`. A claim binds its literal `text` to its exact `scope_ids` in an
authored part. Unimplemented propositions are unchecked; a defined check without enough source
information records insufficient evidence. Neither outcome confirms truth or counts as a material
failure. Checks cannot establish arbitrary paraphrase truth or detect every undeclared assertion.

Award-wide and whole-journey all-leg cabin assertions have different evidence boundaries; separate
cash flights are included in whole-journey assertions. Seats.aero's reported mixed-cabin percentage
describes distance flown below the reported cabin; its absence does not confirm uniform leg cabins.
See the [provider's concepts](https://developers.seats.aero/reference/concepts-copy).

One initial draft and at most one correction are requested. Correction receives the original
document and all failures together. The recoverable draft with fewer material failures is delivered;
correction wins ties. A correction API or generation failure preserves a recoverable initial draft.
Remaining failures receive local Validation notices that include omitted source-backed facts.
API failures and responses without recoverable content have separate generation outcomes.

Measurement includes the complete instructions, cleaned source, slot catalog, strict response schema,
and output reservation. UTF-8 byte counts provide a conservative token upper bound plus explicit
protocol overhead; they are not model-specific token counts or evidence of practical context fit.
Both initial and correction input bounds are checked without pruning. Exact replay verifies saved
rendered content, fact associations, and notices without invoking a writer.

With an input measurer, retained API counts replace the conservative byte bound for the context
gate, while byte estimates stay separately recorded. Each count is bound to the complete model,
instructions, input and strict schema. Counting failures have a distinct `measurement_error`
outcome; correction measurement failure preserves the initial recoverable answer. Replay checks
the retained count and its binding offline; it does not independently retokenize.

The owner-authorized October 8 Luna diagnostic used run-specific settings over saved Ranking
exports. Its initial run used 16,384 output tokens and a 300-second authoring timeout; a later
bounded diagnostic used 32,768 output tokens and a 600-second timeout. Neither profile changes
the API defaults or establishes M2 qualification. The [diagnostic record](build-log/2026-10-08-results-m2-luna-live.md)
contains exact attempts, usage, replay evidence and remaining limits.

New artifacts use rendering v2, which bounds prose notices to their originating part. Historical
v1 artifacts replay their original bytes. Parts still concatenate exactly; authors must supply
the desired whitespace at boundaries. A render-only derivative must be saved separately from
the original live artifact and must not be described as new generation.

The implementation spec is
[Results M2](handoffs/2026-10-07-results-m2-implementation-spec.md). M3 quality evaluation, model
selection, broader live budget approval, bookability, provider reliability, and traveler-task benefit remain
separate work. The bounded live evaluation authorized for this compact-input change does not supply
those claims. Offline fixtures do not supply those claims. The adapter follows the
[official Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
