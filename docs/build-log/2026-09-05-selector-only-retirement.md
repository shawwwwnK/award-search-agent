# 2026-09-05: selector-only temporal workflow retirement

## Implemented

- Retired the runtime `two_pass` strategy, Pass-2 model configuration, temporal resolver,
  model-authored relation wire, conformance layer, and repair trace surface.
- Made deterministic compiler plus required opaque selector the sole request-understanding route.
  Normal requests always use `supported_or_unresolved`; no fallback is available.
- Kept test-only injected catalogs private to selector workflow integration. They require exact raw
  request matching and retain their historical planner only to replay frozen manual fixtures.
- Updated the runtime and ready evaluator to construct separately observable non-temporal and
  selector adapters. New evaluator artifacts use schema v6 with only those two telemetry stages.
- Added ADR 0010. Historical artifacts and older build logs were retained as evidence, rather than
  rewritten as current claims.

## Verification

- Focused selector/compiler/integration/CLI tests: 102 passed.
- Full suite: 263 passed.
- `ruff check src tests`, `mypy src tests`, and `git diff --check` passed.
- Source audit over `src` and `tests` found no two-pass strategy, Pass-2 resolver/wire,
  conformance, repair, or removed model-view identifier.

## Owner decision recorded

The project owner judged the selector path sufficiently validated and directed retirement of the
sequential two-pass path. The frozen 44/48 traced Luna result remains the evidence record; no live
evaluation was run during this implementation change.

## Selector-only runtime proof (2026-09-06)

- A subsequent full live run exercised the retired implementation through the new selector-only
  evaluator CLI: Luna for both model boundaries, all sixteen ready cases, three trials, and
  `--trace-all-calls`. It did not accept a strategy, Pass-2 model, or legacy policy argument.
- The schema-v6 artifact declares `architecture: selector_only` and has no strategy field:
  `evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-final-3-trials.json`.
- It completed all 48 records with 40 passes (83.33%), 8 completed failed checks, zero errors,
  zero Pass-1 boundary failures, zero selector failures, and zero grounding failures. It made 90
  calls (48 non-temporal Pass 1 and 42 selector), captured 65,947 tokens, and recorded 157.400
  seconds total latency.
- The artifact's all-call trace directory contains exactly 48 private sidecars:
  `evals/intent/traces/run-2026-09-06T053703.204177-0000-95a380c0`. Its only call stages are
  `compiler_non_temporal_pass_one` and `temporal_candidate_selector`; no Pass-2, repair, legacy,
  or strategy stage was invoked. This is runtime proof of the removal, not a new quality baseline.

## Post-retirement comparison

- The selector-only proof was compared record-by-record with the immediate pre-retirement traced
  Luna run (`44/48`, 91.67%). The selector-only run scored `40/48` (83.33%): 39 paired passes,
  3 paired failures, 5 pre-pass-to-post-fail regressions, and 1 post improvement.
- The regression is not attributed to normal sampling alone. Request/context, model IDs, Pass-1
  payloads, selector catalog payloads, and 48 Pass-1 plus 42 selector calls were identical across
  matched records. The retirement refactor reduced Pass-1 instructions from 36 to 10 lines and
  selector instructions from 22 to 3 lines, while preserving the same schema shapes.
- All eight post-run failures selected explicit unresolved alternatives for supported literal
  candidates. The three exact-date trials changed from supported selections (`c0,c2`) to unresolved
  (`c1,c3`) on the same catalog; January, next-month, and relative-weekend records showed the same
  pattern. The shortened selector instruction retained a conservative unresolved rule but removed
  material interpretation and selection guidance.
- Selector-only runtime removal remains proven. A future quality correction should restore the
  full pre-retirement Pass-1 and selector instruction contracts, then rerun the same traced
  selector-only matrix; it should not restore a two-pass path.

## Selector prompt repair (2026-09-06)

- Trace review established that the post-retirement score drop was selector conservatism caused by
  instruction contraction, not by the retired runtime path. The only implementation change was a
  concise replacement for the selector instruction contract. It restores group-scoped supported
  versus unresolved selection, neutral treatment of an unspecified endpoint cue, exact anchor-use
  modes, dependency/composition constraints, and duration semantics. Pass 1, schemas, projection,
  compiler, evaluator, cases, and tests were not changed for this repair.
- Full offline checks after the prompt-only edit passed: 263 tests, Ruff, mypy, and
  `git diff --check`.
- The same traced selector-only Luna matrix completed 48/48 records with 47/48 passes (97.92%),
  one clarification failure, and zero errors, Pass-1 failures, selector failures, grounding
  failures, semantic failures, or deterministic-output failures. It used 90 calls (48 Pass 1,
  42 selector), 71,051 captured tokens, and 121.566 seconds total latency. Artifact:
  `evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`.
- All eight conservative selector abstentions in the preceding selector-only proof were resolved.
  Exact dates, named-month/relative period, anchor-relative weekend, tentative city/month, and
  adversarial cases each passed all three trials. The one remaining miss was one
  `repositioning_allowed` clarification asking for origin instead of the expected departure; no
  follow-up behavior change was made. Its 48 private all-call sidecars are under
  `evals/intent/traces/run-2026-09-06T055812.402359-0000-53a0103c`.

## Final owner conclusion

- Request-understanding is complete and frozen. The selector-only Luna configuration is the sole
  live path: Luna runs non-temporal Pass 1 and opaque temporal selection, with deterministic
  temporal compilation and clarification. Sequential two-pass resolution is retired and is not a
  runtime fallback.
- The prompt-repair artifact above is the current qualification record at 47/48 (97.92%), with
  zero errors and one documented clarification miss. The preceding 44/48 and 40/48 runs are
  historical milestones retained for comparison.
- No further intent changes are authorized without an explicit owner decision to reopen the slice.
  The 48 all-call trace sidecars are private/local evaluation evidence and must not be committed
  as public artifacts.
