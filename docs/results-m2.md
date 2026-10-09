# Results M2 local API and CLI

Results M2 is [owner-closed as of 2026-10-08](handoffs/2026-10-08-results-m2-closeout.md) for its declared implementation boundary. M3 remains planned; diagnostic settings and broader qualification limits remain separate.

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

New runs use the `results-artifact-v3` disclosure checks with `results-prepared-v2`.
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
The internal candidate ID remains in the artifact; a visible ID slot is also supported.
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
selection, live budget approval, bookability, provider reliability, and traveler-task benefit remain
separate work. Offline fixtures do not supply those claims. The adapter follows the
[official Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
