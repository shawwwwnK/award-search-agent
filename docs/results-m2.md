# Results M2 local API and CLI

**Current channel, 2026-10-24:** [ADR 0029](adr/0029-structured-results-and-local-workspace.md) and the [current plan](plans/2026-10-23-2334-feat-results-workspace-plan.md) govern the new structured backend, implemented for Results M2 U1–U3. Frontend rendering/integration and Results M3 retain separate milestones. Historical V1–V5 Markdown generation remains the CLI default, with its original schemas, checks and replay routing. The new channel replaces mandatory prose slots/status/checklists with source-resolved facts. Ranking policy and upstream trust remain unchanged; owner presentation acceptance remains open.

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
clock times are absent. Saved v1 factual shapes retain their original fields and
exact replay; the outer artifact version remains V6.
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
The evidence includes an explicit evaluated configuration, not an adopted default
or general model-context qualification. This API guide does not establish frontend/M3 acceptance.

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
for current verification and evaluation status.

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
`context_limit_tokens`, and `prompt_overhead_tokens`. There is no adopted default model or live
campaign configuration. The adapter disables SDK retries, request storage, and automatic input
truncation. Each invocation has the configured timeout; this is not a composed end-to-end deadline.
Caller interruption propagates; authoring does not start background tasks.

Optional `max_input_tokens` supplies a separate model input ceiling. `authoring_guidance` adds
explicit run-specific instructions; absent guidance preserves the original preparation. The writer
still controls layout and prose. API callers can omit `input_measurer` for the original conservative
byte gate; CLI `--live` counts the exact token-bearing request before each authoring attempt.

Use the CLI through `python -m award_agent.cli.results` (or the installed `award-results` entry
point). Every output path must be new, and inputs are checked again before atomic publication.

```sh
python -m award_agent.cli.results measure --projection solutions.json --config config.json --output measurement.json
python -m award_agent.cli.results author --projection solutions.json --config config.json --draft initial.json --correction corrected.json --output artifact.json
python -m award_agent.cli.results replay --artifact artifact.json --output answer.md
```

Offline authoring reads `ResultsDocument` JSON. Without `--correction`, the same frozen draft is
returned if correction is needed. Live authoring requires replacing `--draft` with the explicit
`--live` flag and supplying API credentials through the ordinary SDK environment. No live calls
were made to implement this interface. A non-delivered authoring outcome writes its failure
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
