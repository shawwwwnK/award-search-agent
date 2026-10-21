# Results M2 presentation revision — 2026-10-09

## Request and scope

The owner reviewed saved end-to-end answers, rejected their cosmetic presentation,
and requested orchestrated fixes plus documented evidence for future iterations.
They called out raw source IDs, dense unformatted search results, UTC-style times,
robotic language and headings. This reopens M2 presentation acceptance; it does
not reopen Ranking or earlier stages. The owner's future acceptance and next cut
remain pending.

The session began with existing modifications to `DEFERRED.md` and
`docs/project-state.md`, and untracked October 8 end-to-end diagnostic work. Those
changes and original run outputs are preserved. Relevant workbook sections 2.2–2.3
describe a useful shortlist and uncertainty; newer Results contracts control the
specific one-way scope and authoring boundary.

## Work and evidence

Implementation and evidence preparation were assigned to separate implementer
agents, followed by an independent architect review. Results V4 adds readable local
dates/times, points, durations and currency amounts; natural condition, cabin and
coverage text; friendly stable labels; exact-equality schedule aliases; specific
traveler notices; and heading-boundary checks. Preparation V3 injects required-key
and slot-usage guidance. V1–V3 preserve their historical semantics. The evidence
track uses existing saved Ranking exports.
Initial offline documents are development examples. The owner then explicitly
requested live LLM iteration on saved provider results, experimenting with prompts
and data injection until answers read naturally. Live Results calls are authorized;
provider acquisition is reused. The original answers are preserved as baselines.
Each new live attempt retains configuration, prompts, usage, source hashes, checks,
rendered answer and review disposition.

The owner then instructed stopping after the current in-flight run to review API
spending. No further generation or token-count calls will be made; source revision
006 is frozen. The planned wider confirmation cohort was cancelled. Presentation
remains unfinished rather than accepted or re-closed.

See [presentation iterations](../../evidence/end-to-end/presentation/README.md)
for the reproducible comparison and owner-review record. Evidence describes only
the declared offline/live attempts. Offline examples do not establish live writer
quality. Mechanical checks and presentation review do not establish semantic truth
of arbitrary prose, bookability, broader qualification or M3 completion.

## Verification

Parent verification of the frozen sixth source revision:

- `.venv/bin/pytest tests/unit/test_results_m2.py tests/unit/test_results_notice_v2.py tests/unit/test_results_v3_disclosures.py tests/unit/test_results_v4_presentation.py tests/unit/test_results_token_measurement.py tests/unit/test_results_cli.py tests/unit/test_results_adapter.py tests/unit/test_results_evidence.py tests/unit/test_results_markdown.py -q`: **121 passed in 48.83s**.
- `.venv/bin/mypy src/award_agent/results tests/unit/test_results_v4_presentation.py`: passed, six files.
- `.venv/bin/ruff check src/award_agent/results tests/unit/test_results_v4_presentation.py`: passed.
- `.venv/bin/pytest tests/unit/test_harness_pipeline.py tests/unit/test_harness_workflow_ui.py tests/unit/test_results_cli.py tests/unit/test_results_adapter.py -q`: **23 passed in 194.04s** on source revision 004. Subsequent display/prompt changes were covered by the Results suite; this integration suite was not repeated.

The initial parent regression run recorded **20 failures and 92 passes**: legacy
fixtures assumed V3 default display/identity and an invalid-version probe used V4.
Historical fixtures now explicitly pin their original version; new V4 tests cover
the revised behavior rather than changing their historical assertions.

Independent review found and prompted fixes for currency precision, unknown
currency preservation, label reuse/resumption, false-success partial status text,
missing zero-journey disclosures, component price-scope notice loss and a
heading-boundary false positive. Final targeted probes passed; representative
historical V1/V2/V3 artifacts replayed exactly. Live prose review remains separate.

Live iterations 001–003 were rejected by agents for presentation. 001–002 also
had residual material findings; 003 was mechanically clean but had joined headings,
ungrammatical slot placement, repetitive schedules and a false connection-city
heading. Each is retained with its exact Results source snapshot and successful
archived-source replay. They are not recast as passing examples.

The fourth experiment uses GPT-6.1 Sol with a revised positive example and the
same saved provider-derived inputs. This is an explicit run-specific model/prompt
experiment, not an adopted default or a controlled estimate of the effect of the
model alone. [Official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
confirms the declared context/input limits and Structured Outputs support.
Iterations 004–006 improved output, but saved admitted/conditional prose still has
grammatical seams, repetitive disclosures and generic headings. Mechanically clean
delivery does not establish product readiness. The final incomplete case of 006
was the only in-flight run when the owner requested stopping. It finished with
`generation_error` / `not_delivered`: one call, 253,293 input tokens and 32,768
output tokens, with raw response status `incomplete` and reason
`max_output_tokens`. No answer was produced and no correction or rerun was made.
Its saved failure artifact replayed exactly; this does not constitute a successful
answer or passing presentation review.

Revision 006 addresses an important injection gap: the authoring payload excluded
the rendered slot values, so the writer previously had to guess grammar around
placeholders. A compact vocabulary now supplies exact wording for 16 sensitive
slot types in both initial and correction calls; the full slot map is not injected.
The saved admitted input adds about 5,473 UTF-8 bytes. Source-derived display
vocabulary, required-key hints and model-authored layout remain versioned, with
historical versions preserved for replay.

## Spending and stop disposition

Estimate costs from saved raw generation receipts, separating ordinary input,
cached reads, cache writes and output. Simplified writer usage omits cache-write
detail; treating all uncached input at the ordinary rate undercounts this session.
The published long-context rates apply to whole requests above 272,000 input
tokens. Reasoning tokens are already included in output usage.

The main cost driver was repeated roughly 800,000-token requests, generally with
one correction, with little reuse of the large input. Escalating to Sol increased
the cost of an admitted two-call run to roughly $8. The parent did not surface
that increase before the model switch. Cost review precedes any further live work.
This estimate is not an invoice and does not include other sessions, provider
charges, unknown token-count endpoint charges, taxes or regional adjustments.
Final saved-receipt totals are **17 generation calls and estimated $41.82305029**:
six Luna calls, $1.22935729; eleven Sol calls, $40.593693. The failed incomplete
call contributed $0.954215 and was below the long-context threshold. The rate
sources are [official pricing](https://developers.openai.com/api/docs/pricing),
[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and
[Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
The [cost report](../../evidence/end-to-end/presentation/cost-report.md) retains
the reproducible offline breakdown, including 17 separate token-measurement calls
whose billing is excluded from this estimate.
All paid calls have stopped. No additional live experiment is inferred as authorized.

Final `git diff --check` passed. No commit or push was requested or performed.

## ADR and deferred-work disposition

ADR 0026 amended and ADR index updated: records accepted traveler-facing direction,
artifact identity display and scoped reopening of M2 presentation acceptance while
preserving model-owned layout, trust and disclosure obligations. Current project
state and local Results usage link the iteration record. `DEFERRED.md` identifies
presentation as active core work and retains existing broader qualification gates
and the historical cross-process replay-order issue. No parked feature was opened.

## Owner review

Pending. No owner quality acceptance or M2 re-closeout is inferred from engineering
verification or offline examples.
