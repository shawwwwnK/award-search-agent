# Results M2 structured implementation and live diagnostic

Date: 2026-10-24. Current branch: `main`. Starting commit:
`af585b70ad17bb4135ede497c7b6a80935e138f4`.

## Authorization and scope

The owner invoked the implement skill with implementer/reviewer subagents, asked
to continue through live evaluation and iterate on the results, and required a
current-branch commit through that skill. Scope is the current plan's U1–U3:
complete source-resolved facts, frozen FX/observed pricing, and structured
authoring/checking/replay. Frontend M1/M2, follow-ups, M3 qualification and owner
presentation acceptance remain separate. No travel-provider acquisition ran.

Applied implement, TDD at the plan's already-agreed public seams, requesting-code-review,
code-review and verification-before-completion workflows. There is no dedicated
Skill tool in this host; local skill instructions were read and executed through
the available file, command and native collaboration tools. No external model
CLI or cross-provider reviewer was launched.

## Implementation and integration

- U1: immutable workspace facts, full eligible ID/family membership, actual
  representatives, pure named sorts, instant-based connection waits and frozen
  local dates, source material facts, separate benchmarks and leads.
- U2: observed monetary conversion/scopes and comparable cash/points keys,
  separate heuristic cost, bounded one-request ECB-source adapter, explicit
  outage receipt/USD-only fallback, and injected pre-Ranking snapshot acquisition.
  Saved projections retain their original snapshots.
- U3: separate structured document/prepared/artifact models, compact exact aliases,
  new checker/resolver, bounded shared runner, exact request measurement, raw
  writer receipts, version-dispatched CLI and replay. Legacy response models and
  schemas remain unchanged.
- Parent integration: structured CLI and end-to-end offline CLI controls; bounded
  offline-default live evaluator with immutable request/count/writer receipts,
  call reservations and source archives; review/acceptance preparation records.

Review found and corrected component USD/cabin/stop loss, missing summary leads,
lost FX acquisition receipts, wrong-kind fact attachment, unrelated claim-scope
acceptance and missing selected support blocks. See the
[two-axis review](../../evidence/results-stage/m2/structured/2026-10-24-luna/code-review.md).

## Verification before live evaluation

- Original targeted legacy gate: 68 passed in 39.19 seconds.
- Combined Results/evaluation/projection/harness gate: 216 passed in 277.72 seconds
  (collection preceded final review regressions).
- Review-fix targeted structured/adapter/V5 gate: 29 passed in 89.59 seconds;
  an additional lead-scope control passed separately. Independent Spec follow-up:
  five selected tests passed in 35.49 seconds plus original reproducer probes.
- Mypy on runtime modules/script passed (15 files). A later expanded test-file
  gate exposed four annotation errors in tests; those were corrected without
  runtime changes, and 17 affected tests plus scoped mypy/Ruff passed.
- Legacy matrix: six saved artifacts across hash seeds 11/23/37, 18 checks before
  and after. Fifteen pass in each run. The same saved V4 preparation mismatch
  fails in each seed before and after; exception outcome is unchanged, with
  stack-frame line shifts ignored. Source bytes and original strict response-schema
  digests are unchanged. No saved V3 artifact was found in this inventory; generated
  regression tests cover that runtime version. See
  [matrix evidence](../../evidence/results-stage/m2/structured/2026-10-24-luna/legacy-replay/baseline.json).

## Live evaluation and iteration record

The [campaign](../../evidence/results-stage/m2/structured/2026-10-24-luna/campaign.json)
declares three saved cases, gpt-6-luna with explicit numerical settings, up to
18 generations/18 input counts over at most three targeted rounds, and no automatic
API retries or travel-provider calls. Each run has at most one correction.

Round one used five generations and five input counts. All three selected
artifacts were mechanically clean. Independent semantic review nevertheless found:

- admitted: omitted a material unselected business/separate-ticket alternative;
  weak next-day arrival and exact-variant rationale;
- conditional: falsely said no complete eligible journeys existed, although all
  232 complete eligible alternatives were present in writer input/workspace;
- incomplete: inspected narrative facts were supported, but source-known summary
  departure dates were absent from resolved component facts when times were unknown.

The next iteration adds explicit saved authoring guidance about conditional
eligibility, meaningful unselected choices, full local dates and nearby variants.
It does not alter Ranking or add a cabin/style quota. Source-known departure dates
are added through workspace/resolved v2 shapes, retaining original v1 shapes and
round-one replay; outer artifact V6/document v2/prepared v5 stay unchanged because
the changed factual shape is separately versioned and absent from the writer schema.

Two separate live FX adapter smoke invocations recorded unavailable outcomes:
the sandbox attempt hit a tunnel 403, and the required outside-sandbox rerun
reached HTTP 403. Both preserve explicit outage receipts and USD-only identity;
no saved-case snapshot was refreshed and no successful live rate acquisition is
claimed. Fake-backed positive-rate/partial/malformed controls remain distinct.

Round two fixed the substantial source-framing/choice failures but independent
review found a feeder airport error and an out-of-window partial-route suggestion.
Round three targeted those issues, then reran admitted with the same final
configuration to avoid mixing prompts in the final cohort. Final totals are
**nine runs, 14 generations, 14 input counts, 2,308,185 writer input tokens and
36,919 output tokens**. No billing estimate is inferred from these measurements.

Final selected artifacts all have no failed checks. Admitted has one unchecked
cabin declaration; conditional has three; incomplete has none. Native source
review supports those cabin statements, but they are not upgraded to deterministic
support. The reviewer identified no further substantial factual failure and
recommended no additional generation for two retained wording weaknesses:
admitted calls an 11h30m departure difference “slightly earlier”; incomplete's
“direct-route” benchmark wording can suggest nonstop despite its connecting facts.
See the [answer review](../../evidence/results-stage/m2/structured/2026-10-24-luna/answer-review.md)
for each original failure, exact source evidence and disposition. No owner
presentation acceptance or M3 qualification is inferred.

## Final verification

- **Full repository suite, once after runtime settled:**
  `.venv/bin/python -m pytest -q` finished with **926 passed, 99 skipped,
  2 failed in 817.80 seconds**. Both failures are the previously recorded,
  unchanged `test_gfly_compat.py` environment tests: preservation of fixture rows
  and launcher version/source digest. Direct diagnostics show the nominal pinned
  path resolves to system Python and neither `fast_flights` nor `gfly` is installed
  there. No code in the launcher/tests changed. See
  [final pytest output](../../evidence/results-stage/m2/structured/2026-10-24-luna/full-suite-final-output.txt)
  and [environment diagnostic](../../evidence/results-stage/m2/structured/2026-10-24-luna/gfly-environment.txt).
  The repository-wide suite is **not** claimed green.
- **Final scoped types:** `.venv/bin/mypy` over Results, CLI, harness pipeline,
  evaluator and the six new test modules passed for **21 files**. Final scoped
  Ruff passed for runtime, evaluator and changed tests. Earlier test-only annotation
  errors were fixed and their 17 affected tests passed.
- **Version refinement:** 25 focused structured/workspace tests passed after
  adding required v2 departure dates and preserving v1 shapes. Independent Spec
  probes verified all three round-one artifacts still produce their exact saved
  resolved JSON/digests and reject mixed-version shapes.
- **New artifact audit:**
  `PYTHONPATH=src .venv/bin/python evidence/results-stage/m2/structured/2026-10-24-luna/replay-check.py`
  passed **27 fresh-process replays** (nine artifacts × seeds 11/23/37), with
  zero artifact failures. Independent accounting verifies all eligible IDs occur
  exactly once in groups, new dates match source, original artifacts/source bytes
  are unchanged, aliases bind raw responses to saved drafts, call reservations
  match receipts and token totals, and final configs/source snapshots match across
  all three cases. See [verification summary](../../evidence/results-stage/m2/structured/2026-10-24-luna/verification-summary.json).
- Source-history characterization records the same historical V4 mismatch rather
  than rewriting original artifacts or claiming universal historical replay.
- Documentation checks: `git diff --check` passed; relative-file-link existence
  passed for **321 links across 13 documents** (not heading-anchor validation).
  The final legacy matrix was refreshed against the settled runtime and matched
  the same baseline; final live source snapshots match current source hashes.
  No dependency
  installation, environment repair or travel-provider search was performed.

## ADR and deferred-work disposition

ADR 0029 and its index were amended to record implementation and diagnostic status.
No new ADR was needed: the accepted ownership/product/trust decisions and
milestone goals are unchanged. The resolved-fact version refinement preserves
existing evidence behavior and adds source-known data. `AGENTS.md`, project state,
usage and plan invocation/verification notes link current evidence. `DEFERRED.md`
records the scoped result, known historical replay mismatch and positive-live-FX
claim prerequisite; no D01/D09/D10/D11 work was opened. Existing glossary terms
already cover this work. Broader G03/G05/G06/G08 claims remain separate.

Owner presentation disposition remains pending. The accepted next milestone is
Frontend M1, followed by Frontend M2 and Results M3 evaluation/acceptance; this
implementation does not infer owner closeout or a new next-cut decision.
