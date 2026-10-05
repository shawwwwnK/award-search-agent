# Results Stage design and milestone review

Date: 2026-10-04. Scope: documentation/design and read-only verification.

## Owner request and recorded decisions

The owner requested a thorough Results Stage/milestone review, subagent verification, current
LLM-call best practices and design updates. During the task the owner reaffirmed: “I want the
LLM to have the control over the structure.” That structural authority is explicitly preserved.
No Results runtime implementation, paid/live evaluation or stage closeout was requested or claimed.

## Work performed

Three subagents independently reviewed architecture/milestones, verified actual contracts/saved
artifacts, and searched/fetched official OpenAI guidance using the OpenAI Docs skill. The
architect reviewed the proposed flexible scoped-parts contract and then all four revised handoffs.
The LLM investigator separately checked the integrated call/evaluation sections against the
fetched official sources. Agents made no edits and did not delegate further. Parent integrated
all edits; no escalation was recommended.

Changed documents:

- `docs/handoffs/2026-10-02-results-stage-v1-design.md`: replaced assembled-answer flow with
  model-owned structure, explicit source authority and visible factual/claim boundaries.
- `docs/handoffs/2026-10-03-results-stage-authored-template.md`: repeated invisible scopes,
  exact concatenation, freeform supported layout, scoped single substitution and visible checks.
- `docs/handoffs/2026-10-02-results-stage-implementation-plan.md`: concrete source/slot/call/
  failure/replay/evaluation contracts, independent oracles and complete milestone slices.
- `docs/handoffs/2026-10-02-results-stage-milestones.md`: deliverables, sequencing, success/valid
  controls, actual family coverage and review gates for M1/M2/M3.
- `docs/reviews/2026-10-04-results-stage-design-review.md`: findings, dispositions, verified
  evidence, current official sources, recommendations and unresolved choices.
- `docs/project-state.md`, `AGENTS.md`, `DEFERRED.md`: current design pointers, accurate status,
  dated disposition under existing gates. This log records the session.

The final architecture pass confirmed that flexible repeated scopes do not prescribe cards,
order or contiguous journey blocks. Its corrections were integrated: require nonempty selection
when complete journeys exist; scope the import verifier to its independently checked requirement/
obligation subset instead of claiming complete status rederivation; describe calibration seeds as
proposed; make condition association independent of visual placement. The source-guidance pass
confirmed strict response/storage/refusal/incomplete/retry guidance and diagnostic arithmetic;
explicit equivalent judge-call discipline and cross-part filled-Markdown checks were added.

## Verification and evidence

Read-only investigations used `rg`, file reads, local SDK inspection and Python saved-JSON
summaries. Relevant workbook product, ownership and evaluation sections were read without editing.
Primary guidance was searched and fetched via OpenAI Docs tools; URLs and access date are in the
[review](../reviews/2026-10-04-results-stage-design-review.md). No travel-provider or model-inference
call was made. Documentation retrieval is not a Results evaluation.

Commands run by the contract investigator:

```sh
.venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled --verify
.venv/bin/python -m pytest -q tests/unit/test_ranking_m1.py tests/unit/test_ranking_m2.py tests/unit/test_ranking_m2_corpus.py
```

Results: three saved corpus cases verified; **50 tests passed in 63.35 seconds**. Saved counts
remain 992 retained/427 eligible, with eligible 257/106/64, award groups 23/3/4 and zero repeated
eligible award/cash pairs. All complete cost references remain absent and coverage partial.
These checks do not test an unimplemented Results runtime.

The earlier missing-M1-blocker and cost-summary mutation results were read from the preserved
October 3 probe, not rerun or reported as normal production failures. They motivate a proposed
matching-owned import acceptance check and independent projection oracles. No runtime fix,
source artifact rewrite or changed admission policy was made.

Documentation verification passed: `git diff --check` and
`python3 /private/tmp/check_results_design_docs.py`. The latter checked all nine changed/new
session documents, 181 relative links/anchors, whitespace, balanced code fences and targeted
active-contract consistency. The checker is a temporary session aid, not a new runtime test or
clean-checkout dependency. No failures remain in these scoped checks.

## Preserved work and claim limits

The pre-existing modified `DEFERRED.md` and untracked October 3 review/build-log/evidence files
were preserved. No provider/ranking artifact, runtime code, dependency, workbook, credential or
private travel export changed. Historical logs remain historical. The active documents now agree
on LLM structural authority and the updated proposed boundaries.

The strict response transport, one-invocation/no-repair profile, source-verifier extension and
milestone details are reviewed engineering recommendations, not invented owner approval. Exact
failure-summary breadth, numerical call budgets and writer/judge models remain open. No model
quality, general import safety, production UI, user benefit or stage qualification is claimed.

Owner interpretation/acceptance of new engineering proposals: **not yet supplied**.

Next implementation cut: **M1.1 source authority/brief/obligation contract and independent saved
examples, proposed; not executed by this design review**.
