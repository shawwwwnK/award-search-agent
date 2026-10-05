# Built stages review

Date: 2026-10-03. Baseline: `8ef1d6a`, initially clean working tree. Scope: owner-requested
orchestrated review, primary-source web research, offline verification, and documentation.
No runtime implementation, live model/provider calls, deployment, or new qualification.

## Request and review work

The owner requested a deep review of the built stages from product, production AI/eval,
FDE hiring, skeptical engineering, and additional professional perspectives, plus a concise
overview and matching detailed document under `docs/reviews`.

Six architect-role subagents conducted bounded read-only reviews: product manager,
production AI engineer with evaluation focus, FDE hiring manager, skeptical senior software
engineer, reliability/security engineer, and UX researcher/decision scientist. Agents did
not delegate further or edit repository files. Their temporary reports were synthesized by
the parent; simulated specialist agreement does not establish external human qualification.
The engineering reviewer then checked the integrated documents for factual/policy conflicts
and section alignment, finding no substantive must-fix conflict. Its wording/sequencing
suggestions were incorporated.

The parent used the codebase-recon skill for history context and write-page editorial guidance
for repository Markdown. Relevant workbook sections were consulted without modification.
Primary sources included current Anthropic agent/eval guidance, official OpenAI/Anthropic FDE
postings, Seats.aero usage/terms and product guidance, BA connection guidance, HTTPX docs,
GOV.UK user research, W3C accessibility guidance, OWASP output/logging guidance, and original
LLM-judge research. Exact supporting links appear beside claims in the detailed review.

## Files changed

- [Concise overview](../reviews/2026-10-03-built-stages-overview.md): under 700 words,
  eight sections, principal findings and proposed sequence.
- [Detailed review](../reviews/2026-10-03-built-stages-deep-review.md): the same eight top-level
  sections, code/artifact evidence, critical policy tradeoffs, experiments, acceptance evidence,
  user-study controls, and FDE demonstration/claim material.
- [Deferred register](../../DEFERRED.md): refreshed G05's current handoff/check evidence;
  added advisory sources/experiments under G06 and D02/D11/D14 and a dated disposition.
  Stable IDs/statuses, revisit triggers, and approved scope remain unchanged.
- This build log records objective review and verification evidence.

## Objective findings

- Saved M2 JSON inspection confirms 992 retained records: 22 admitted, 405 conditional,
  564 rejected, and one research lead. The 427 eligible records all have undetermined costs;
  all three provider runs are partial and share SFO→BKK/October 5, 2026. Record counts are
  not independent flights or user tasks.
- The exact-business case has 106 eligible records across three award-observation IDs,
  all conditional. These identities are not verified unique flight/choice counts.
- Two saved executions each performed two physically identical SFO→LAX cash searches
  under distinct award activations, consuming two of their three cash requests. This is
  query equality, not proof that observations captured at different instants are equivalent.
- Provider details execute after summary searches and share budgets. The detail-call
  ceiling is not a reserved allocation. Alternative scheduling/coalescing remains proposed.
- The recorded September 20 initial-input diagnostic has 13/19 behavioral passes and an
  unsafe ambiguous-departure ready/plan outcome. Its individual missing-window guard does
  not detect an invented bounded interpretation; the overall case correctly fails.
- Active model constructors inherit installed SDK defaults of 600-second timeout and two
  retries. Logical invocations/semantic repair counts do not prove composed deadline bounds.
- Results authored-template design is unimplemented; fact slots alone do not prove truthful
  surrounding prose, visible conditions, or safe browser rendering.
- History probe: 56 commits, August 29–October 3, two branches, one recorded git author.
  Documentation dominates churn; clarification adapters recur in fix-associated paths.
  Short history/partial months do not support a useful momentum trend or productivity claim.

## Commands and checks

Commands below ran against existing code/artifacts. No failures were fixed because the
authorized work was review and planning. Repeated reviewer checks are not extra coverage.

| Command or check | Result | Scope and interpretation |
| --- | --- | --- |
| `.venv/bin/pytest -q` | 604 passed, 2 failed, 99 skipped in 588.74 seconds | Full existing offline suite; both failures are the same pinned-gfly integration failures below |
| `.venv/bin/ruff check src tests` | Failed: one RUF059 unused `bundle` binding at `tests/unit/test_ranking_m1.py:213` | Existing lint issue |
| `.venv/bin/mypy src tests` | Failed: 308 errors in 22 files, 188 source files checked | Includes historical paths, tests, and active ranking typing; no claim that all are runtime defects |
| `.venv/bin/python scripts/provider_plan_corpus.py verify --corpus evidence/provider-stage/saved-searches --catalog data/search_planning/catalogs/m1a-3cb7981519612945` | Passed: 3 runs, 549 observations | Current machine, frozen artifacts, no new acquisition |
| `PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled --verify` | Passed: 3 cases | Hashes, timing oracle and saved replay; reviewer repeat not additional evidence |
| `.venv/bin/python -m award_agent.cli.search_planning_eval` | Passed locally: 4/4 | Engineering reviewer execution |
| Same planning CLI in a `git archive HEAD` export, with export `src` and existing installed venv | Failed: missing local catalog `manifest.json`, `CatalogPublicationError` | Specific tracked-export artifact gap; not a fresh dependency-install test; supersedes historical provider-doc failure cause |
| `.venv/bin/pytest -q tests/unit/test_intent_to_search_planning_live_eval.py tests/unit/test_one_way_award_live_eval.py tests/unit/test_intent_eval_runner.py` | Passed: 16 tests in 0.52 seconds | AI reviewer; offline harness/contract checks despite live in module names |
| `.venv/bin/pytest -q tests/unit/test_gfly_compat.py tests/unit/test_provider_replay.py` | 6 passed, 2 failed in 0.51 seconds | FDE reviewer; both failures in pinned gfly compatibility integration |
| Pinned gfly Python prefix/version probe | Compatibility guard rejected environment; `pyvenv.cfg` absent, prefix resolves to base Homebrew Python | Broken/incomplete referenced local environment, not demonstrated parser regression; no repair attempted |
| JSON grouping/counts, `rg`, targeted source/docs reads, git history analysis | Completed | Evidence and architecture inspection; no live behavioral qualification |

`git diff --check` passed. Local Markdown-link and trailing-whitespace checks passed for both
reviews, this log, and the updated register. The two reviews have identical eight-section
top-level outlines. The final full-suite failures are
`test_reviewed_fixture_preserves_all_rows_and_unknown_price` and
`test_launcher_reports_effective_version_and_source_digest` in `test_gfly_compat.py`;
the environment was inspected but deliberately left unchanged. No additional test failure
appeared. Process-list inspection was unavailable in the sandbox; test-session output was
used to observe continuing progress instead. Test-suite elapsed time is not an application
latency measurement.

## Interpretation and next cut

The review recommends completing/evaluating Results, resolving claim-specific conversational
gaps, establishing a reproducible continuous workflow, and measuring user action/effort before
expanding architecture. Those are reviewer recommendations. No owner conclusions, pilot
thresholds, new policy, scope expansion, or deployment mode were adopted.

Owner interpretation and selected next implementation cut: **not yet supplied**.

Remaining limitations: no current live rerun, no Results artifact or user study, no new price-scope
evidence, no successful clean handoff, and no deployment. All existing stage closeouts remain
scoped and intact. No subagent recommended deep-architect escalation.

## Continued review at the owner's request

The owner requested deeper review and more subagents. Six additional specialist reviews covered
cross-stage correctness, adversarial evaluation, provider semantics, competitive product strategy,
a smaller architecture counterproposal, and an FDE interview/ownership challenge. The provider
semantics role used an investigator; the other five used architects. A worker then packaged and
independently reran the supplied offline probes. No subagent delegated further. The architecture
reviewer checked the integrated additions and found no must-fix factual or policy conflict;
its two precision edits about parallel sequencing and limited M1 verification were incorporated.

The same two review documents now synthesize twelve specialist perspectives. New primary-source
research includes Seats.aero cabin and trip documentation, the gfly specification, official
Seats.aero/PointsYeah/Roame/point.me product guidance, and OpenAI's SWE-bench evaluation audit.
Competitor capabilities are documented claims, not a logged-in performance comparison. The
revised recommendations bring opportunity discovery alongside Results; owner adoption is unclaimed.

### New objective evidence and its limits

- Synthetic Seats responses demonstrate a vocabulary mismatch: `premium` is dropped by an
  exact `premium_economy` request, while canonical `premium_economy` survives. An unrestricted
  `premium` observation misses the premium-economy add-on. The full public M1/M2 synthetic
  contrast retains three admitted candidates in both versions and changes add-ons from zero
  to three. Live endpoint token frequency and outbound alias acceptance remain unverified.
- Synthetic positive `MixedCabinPct` remains raw-only and does not prevent admission under
  the current journey-cabin policy. This motivates disclosure and an explicit policy decision;
  it is not a demonstrated violation of owner-adopted m1-v2 or a saved live failure.
- Four deliberately seeded faults pass particular checks: omitted source-required M1 blockers;
  emptied M2 assessment `validation_needs`; coverage labels on an unexercised one-case planning
  corpus; and an empty Provider corpus index. Normal producers were not shown to generate those
  faults. Independent timing/premium/arithmetic assertions and frozen-byte checks still provide
  real coverage. The proposed M1 import verifier has a limited requirement-validation boundary.
- The saved runs contain ten actual transports serving exclusively hub queries, with no executed
  hub detail transports. The current matcher cannot assemble these components into complete
  journeys. Their possible research-lead value remains unmeasured; preserving the complete plan
  while testing provider allocation is advisory.
- Official Seats trip documentation provides a narrow per-passenger pricing example potentially
  relevant to 17 eligible direct Aeroplan records. No new quote-scope assignment or cost projection
  was made: all 427 eligible saved M2 records still have undetermined costs. The evidence does not
  establish universal pricing semantics or gfly party-price scope.
- The historical intent-to-planning workload has 19 attempts, 35 recorded calls, and 89,305 tokens.
  Its seven planning-eligible cases have 14 calls, 45,329 tokens, and a 19.484-second median recorded
  stage time; six of those seven pass the intent behavior check. Separate Provider receipt-duration
  sums are 24.638, 25.002, and 25.211 seconds. These cannot be combined into an observed app latency
  or dollar cost per useful task.
- Inspection identifies evaluator-owned application composition, a clarification receiver without
  resolved-state context, and terminal READY state. A shared local coordinator and comparisons of
  current clarification, compact context, and editable fields remain proposals; no interaction
  authority or Results authorship was changed.
- Product and FDE additions include narrower task hypotheses, distinct portfolio/personal/product
  continuation criteria, eight interview scenarios, and a 90-minute ownership rehearsal. No user,
  hiring, or personal-skill outcome was measured.

### Additional files and verification

The [evidence directory](../reviews/evidence/2026-10-03-built-stages/manifest.json) contains four
scripts, their four captured outputs, and a manifest with exact commands, baseline HEAD, input
hashes, artifact hashes, and provenance limits. The scripts use existing local dependencies and
catalog artifacts. Their presence does not establish clean-install portability.

| Additional command/check | Result | Interpretation |
| --- | --- | --- |
| `PYTHONPATH=src .venv/bin/pytest -q tests/unit/test_ranking_m1.py -k 'fanout_and_stale_authority or elapsed_transfer_boundary or exact_business_preserves'` | 5 passed, 21 deselected in 0.69 seconds | Focused existing matching controls |
| `PYTHONPATH=src .venv/bin/python -B docs/reviews/evidence/2026-10-03-built-stages/evaluation_oracles.py` | Exit 0; four seeded-fault results captured | Executes specific evaluator seams and three existing M2 corpus test bodies under in-memory mutation; not a full mutated-suite pass |
| `PYTHONPATH=src .venv/bin/python -B docs/reviews/evidence/2026-10-03-built-stages/cabin_contracts.py` | Exit 0; fake-response contrasts captured | Synthetic parser/cabin behavior, no API compatibility qualification |
| `PYTHONPATH=src .venv/bin/python -B docs/reviews/evidence/2026-10-03-built-stages/premium_style_contrast.py` | Exit 0; 0-versus-3 add-on contrast captured | Full public M1/M2 synthetic path over local catalog evidence |
| `PYTHONPATH=src .venv/bin/python -B docs/reviews/evidence/2026-10-03-built-stages/saved_workload.py` | Exit 0; saved metrics projected | Requires expected metric keys; no benchmark rerun |
| Independent worker reruns of the three supplied probes | Captured stdout matches original outputs byte-for-byte | Repeatability of the supplied counterexamples, not independent product qualification |

The manifest supplies stdout destinations for these commands. Probe mutations occur only in
memory or temporary directories; tracked production code, tests, provider data, and corpora were
unchanged. Runtime source was unchanged, so the first-round full-suite, lint, and typing results
were retained without a broad repeat. No live model/provider request, credential access, external
user contact, or deployment was made during this continuation.

The register gained sources under existing G03/G04/G05 and D01/D02/D14 entries plus a dated
disposition. IDs, statuses, and revisit triggers remain unchanged. Final documentation checks
cover matching eight-section outlines, local link targets, whitespace, Python syntax, evidence
hashes, and the register's stable fields. A stale pre-existing D07 roadmap anchor was corrected.
Recommendations remain advisory. The owner's next cut
and interpretation remain **not yet supplied**.
