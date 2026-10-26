# Results M2 composition correction

Date: 2026-10-25. Starting commit: `4d951d52d9cae26525f8c2922f0f617321401d25`.

## Authorization and accepted requirements

The owner invoked implement with subagents, independent code review, full saved-case
live authoring and iteration; the skill requires a current-branch commit.
The [correction contract](../plans/2026-10-25-results-m2-composition-correction.md)
records the interview. Runtime multi-agent orchestration was considered, not adopted.
No frontend or new provider search is in this invocation.

## Initial work allocation (historical checkpoint)

Subagents own structured authoring and isolated campaign-runner changes. Parent owns
integration, docs, live execution, evidence accounting and engineering acceptance.
Independent reviewers assess Standards and Spec separately; source-backed answer
review assesses composition separately from mechanical checks. Results follow below.

## ADR disposition

ADR 0029 and its index are amended for accepted composition/model ownership.
Milestone goals are unchanged. Owner presentation acceptance and M3 remain open.

## Implementation and initial engineering checks

The base structured authoring instructions now express whole-answer composition,
individual Ranking-informed explanations, embedded exact references, cash context
and consolidated applicable limitations. The existing wire schema, deterministic
resolver/checker and bounded runner are unchanged. A public-seam composed-document
control verifies block order, exact IDs, inventory preservation and new replay.
Prompt assertions/fake writers are not treated as narrative-quality evidence.

The campaign runner accepts `--campaign-root`, with isolated configurations,
immutable outputs and pre-invocation reserved-call ledgers. New tests cover isolation,
per-root budget exhaustion and undeclared rounds before calls. The evaluation agent
recorded RED before implementing the new campaign seam; its seven-file-test cases
passed. The authoring agent's focused file passed 17 tests. Parent integration gate:
43 Results/runner/CLI/workspace/adapter tests passed in 102.73 seconds. Scoped mypy
(four changed runtime/test files) and Ruff passed. These are engineering checks.

Parallel initial code review returned Standards 0, Spec 0. Full review report and
source-backed narrative dispositions are in the new campaign evidence folder.
Network preflight found sandbox DNS failure; outside-sandbox DNS succeeded. Live
calls use the approved outside-sandbox command, not a silent retry/fallback model.

Round one used four generations/four counts and delivered mechanically clean
answers, but independent composition and source review required revision. The
incomplete answer described Jan17 Alaska leads while selecting Jan1 Aeroplan/United
aliases; binding code was correct. Admitted traveler-support wording contradicted
supported seats and visible text leaked checker definitions. Conditional inspected
facts/composition passed. A generalized second prompt revision adds alias/member
identity auditing, traveler-versus-quote scope distinctions, natural visible claims
and meaningful departure/whole-journey countercosts. Round two reruns all three
cases under one shared base brief with no prior diagnostic patch guidance.

## Compatibility disposition

The owner expressly permits development breaks. Base instructions are part of
recomputed preparation, so old October24 V6 artifacts intentionally fail current
preparation comparison. No check was relaxed to accept them. Saved source archives
retain their original implementation and the original 27/27 replay record remains
historical evidence. New generated artifacts must replay under their captured
source; final-cohort artifacts must also replay under final current source.
Historical V1–V5 code/schema paths remain unchanged. Original campaign/source bytes
are not rewritten.

## Round-two investigation and structured lead identities

The complete second cohort used five generations/five counts. Conditional source
and composition review passed; admitted still duplicated complete factual summaries
in reference.text and compared point costs across programs. Incomplete again
selected A1/A2 while describing different Taipei components. Independent review
found the prepared incomplete_leads index held only ref/kind, requiring a join
against 383 component groups. This does not prove causality, but justified a small
input ergonomics change before another generation.

Architect recommendation: enrich every lead in structured preparation only with
source-copied identity (route/date/program/cabin/points/price_scope/cash fields),
matching exact component-group member aliases. Preserve all rows/order/groups,
typed unknowns and canonical source. Recompute prepared binding. Shared V5 compact
preparation stays unchanged. No source facts, output contract or claim checker
are relaxed. A meaningful RED/GREEN control at the existing preparation/run/replay
seam checks the actual source alias identities, including the Alaska Jan17 pair.

The third brief also limits reference.text to short interpretation/claims rather
than duplicated factual summaries; requires meaningful incremental roles for nearby
highlights; distinguishes point programs and one-traveler echo from quote scope;
and describes cash as end-to-end rather than necessarily nonstop. New evidence
will determine whether this resolves the observed association/composition failures.

## Stronger single-composer strategy

Four Luna cohorts (12 saved-case runs, 18 generations/count requests) did not produce
a complete passing cohort. Round4 admitted still omitted the material cabin/booking
alternative and gave a wrong 3h35m arrival difference (actual8h25m). One source
reviewer initially missed that new comparison; parent caught it and the reviewer
retracted the pass explicitly. The review record preserves this evaluator limitation.

Architect recommended a stronger single-composer trial with the SAME final input,
brief and output contract rather than another prompt-only patch or runtime agent
framework. Official GPT-6.1 Sol documentation was searched/fetched to check Responses,
structured output and context compatibility. No general quality inference follows
from those docs. The current owner iteration instruction authorizes the separately
recorded bounded campaign under `2026-10-25-composition-sol`: admitted first, source
and composition review, then complete the cohort if it passes. No global model
default is adopted. All other numerical settings are unchanged.

Admitted passed both independent reviews. Exact model-comparison evidence confirms
only the model setting changed, with identical source/input/instructions/code.
Every cited numerical comparison was independently recomputed. Reviewers retained
editorial length/repetition limitations rather than spend on stylistic perfection.
Conditional and incomplete run next under that same configuration. No new provider
search or FX acquisition occurred.

## Final results and verification

The complete GPT-6.1 Sol cohort passed independent composition and source review for
the inspected exact answers. Numerical comparisons were independently recomputed.
The writer produces individually useful recommendations within a connected argument,
with compact exact references, material alternatives, cash context and consolidated
applicable limitations. The incomplete case truthfully offers only leads. Final
readable previews contain unchanged model prose and source-derived card markers;
no second answer was authored and no frontend renderer/explorer controls were built.

- Final cohort: three runs, four generations and four input counts; 740,382 writer
  input tokens and 6,044 output tokens. Admitted and conditional used one generation;
  incomplete used its bounded mechanical correction. No failed findings in final
  selected answers. No comparison/claim checker is presented as arbitrary prose proof.
- Full session: 15 saved-case runs, 22 generations and 22 counts; 3,935,205 writer
  input tokens and 59,351 output tokens. No billing estimate, travel-provider search
  or FX acquisition is inferred. All failed Luna outputs remain unchanged.
- Final integrity command:
  `.venv/bin/python evidence/results-stage/m2/structured/2026-10-25-composition-luna/audit.py --campaign-root evidence/results-stage/m2/structured/2026-10-25-composition-sol --final-round 1`
  passed nine fresh-process source-version replays (three artifacts × seeds 11/23/37).
  Exact digests, source identities, grouped membership, raw alias-bound documents,
  request/count/writer receipts, token totals and reserved calls reconcile. Final
  settings/snapshots are equal across all three and match current code. Luna's separate
  audit passed 36 replays of 12 archived-source artifacts, so all 15 new artifacts have
  45 replay checks. This is integrity, not semantic qualification.
- Full repository suite once:
  `.venv/bin/python -m pytest -q` finished **931 passed, 99 skipped, 2 failed in
  834.65 seconds**. Failures are unchanged `test_gfly_compat.py` fixture/launcher tests.
  A fresh pinned-interpreter probe confirms the path resolves to system Python without
  `fast_flights`/`gfly`. Launcher/tests are unchanged; no environment repair was attempted.
  The suite is not green. [Output](../../evidence/results-stage/m2/structured/2026-10-25-composition-luna/full-suite-output.txt)
  and [probe](../../evidence/results-stage/m2/structured/2026-10-25-composition-luna/gfly-environment.json).
- During implementation: campaign controls seven passed; parent five-module integration
  gate 43 passed in 102.73 seconds; authoring focused gate 18 passed after lead identity
  enrichment, and again 18 passed in 94.96 seconds after final prompt-only refinement.
  The full suite ran after input-transform logic settled; final focused checks cover
  the final instruction refinement as well. No prompt assertion/fake writer is treated
  as evidence of live prose quality.
- Final combined mypy on the changed runtime, runner, tests and audit script passed
  (five files); scoped Ruff passed. Combined typing initially exposed eight audit-only
  errors that isolated checking missed; Optional narrowing and local types fixed them.
- Legacy matrix command using the previous explicit baseline inventory ran 18 checks:
  15 pass and the same three historical V4 preparation mismatches. Source artifact
  hashes, schema digests and per-case exit/stdout outcomes match baseline. Intentional
  original V6 current-code preparation mismatch is separately documented; strict checks
  were not relaxed. Original October24 and compact-source evidence bytes are unchanged.
- Independent Standards and Spec reviews ran in parallel twice, with final delta
  follow-ups; each axis reports zero findings. [Report](../../evidence/results-stage/m2/structured/2026-10-25-composition-luna/code-review.md).
  Native architect/investigator reviews supplied source/composition evidence; no paid
  external judging system, calibration or held-out study was introduced.

## Files and documentation disposition

Runtime: structured.py (composition brief and per-lead identity); existing campaign
runner (isolated root), with the two corresponding test modules. Output schema,
Ranking, shared legacy authoring, resolver/checker and bounded-attempt policy remain.
ADR 0029/index, AGENTS, project state, current plan, correction contract, usage and
G08/deferred history now link this evidence and explicitly retain owner/frontend/M3
boundaries. The original untracked October8 end-to-end files predate this task and
are excluded from its commit. No credentials or private new travel input were added.

## Remaining limits and owner disposition

This is one final source-reviewed three-case cohort after development iteration,
not repeatability, broad model superiority, exhaustive narrative truth, user benefit,
rendered usability or M3 qualification. Long limitations passages and some repeated
qualification remain accepted reviewer-noted editorial limits. Independent AI review
can miss errors (the Luna round4 arithmetic retraction is preserved). No global model
default is adopted; reproduce with the explicit evaluated Sol configuration.

Owner presentation acceptance and the final next-cut decision remain open. The
existing delivery sequence still places Frontend M1 after this Results M2 correction;
this implementation does not claim that frontend is built or owner-accepted.

## Final documentation and evidence hygiene checks

Relative Markdown file links passed (351 links across 17 changed/new documents at
that check; file existence, not heading anchors). The readable full-suite transcript
normalizes trailing whitespace emitted by pytest; its byte-exact original is retained
as [raw gzip](../../evidence/results-stage/m2/structured/2026-10-25-composition-luna/full-suite-output.raw.txt.gz).
No model response, request, paid artifact or original diagnostic was normalized.
Text/JSON credential scanning found no credentials; apparent key-pattern matches
were confined to SDK encrypted reasoning blobs and were inspected by field path
without exposing their values. Runtime/evidence types, scoped Ruff and diff checks
pass. Only this task's files are staged; earlier untracked owner work is preserved.
