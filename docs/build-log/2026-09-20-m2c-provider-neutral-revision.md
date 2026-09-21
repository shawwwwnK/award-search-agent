# 2026-09-20: Milestone 2C provider-neutral compiler revision

## Owner decision and boundary

The owner approved a development correction to the implemented Milestone 2C compiler. This is an
in-place contract revision in a local development repository, not a deployment or data migration.
Historical V1 artifacts and the original 2026-09-19 implementation evidence remain preserved.

The correction separates provider-neutral search-strategy compilation from later provider planning
and execution:

- `CachedSearchCapability` is no longer an input to 2C, part of plan identity, or part of the trusted
  compilation binding;
- the provisional 31-day input-window, 24 supplemental relationship, 128 unique-query, and 4,000
  query-date-day admission controls are removed;
- every replay-valid representable 2B relationship compiles deterministically, with semantic query
  deduplication and exact many-to-many provenance;
- explicit positioning refusal still suppresses work that requires positioning, unknown permission
  remains conditional, and finite unrepresentability remains explicit;
- the sole compiler limit is an all-or-nothing structural safety guard at 100 selected origin ×
  destination pairs. It is not a provider limit or an upstream endpoint-count guarantee; and
- finite departure windows longer than 31 days are accepted. Intent and clarification own whether a
  frozen request is valid before it reaches 2C.

Provider capability acceptance, exact rectangle-safe multi-airport batching, pages, attempts,
returned rows, bytes, time, result validation, and scheduled-versus-deferred accounting remain for a
separate provider-planning/execution stage. No model or provider call was made for this revision.

The durable decision is the dated amendment in
[ADR 0021](../adr/0021-deterministic-search-strategy-compilation.md#2026-09-20-amendment-provider-neutral-compilation-and-structural-safety).

## Implementation evidence

The active compiler and contracts were revised in place. Focused compiler tests recorded:

```text
37 passed
```

Focused evaluator tests independently recorded:

```text
24 passed
```

Scoped Ruff and mypy checks passed, and `git diff --check` was clean for the compiler work.

Final offline verification after the evaluator refresh and independent integrity fixes recorded:

```text
.venv/bin/pytest -q <10 focused compiler/integration/evaluator/catalog files>
70 passed in 473.84s

.venv/bin/pytest -q
495 passed, 99 skipped in 552.45s
```

Ruff passed over every changed or new Python source and test file. Mypy reported no issues in the
nine changed source modules, and `git diff --check` passed. The active fixture-only evaluator ran
`cases_v2.json` with 4/4 cases passing its exact gate. Historical V1 casebooks and tracked baseline
artifacts remained byte-identical. All verification was offline; no model or provider call was made.

## Offline replay observation

The saved trial-1 bundle was compiled twice with zero model or provider calls. It recorded:

- outcome `PLANNED`;
- 52 accepted relationships and 52 compiled relationships;
- 57 unique logical queries;
- 52 supplemental strategies: 36 destination-access strategies and 16 scoped-hub strategies;
- 68 strategy query uses;
- 183 conceptual query-date-days, recorded only as an observation and not an admission budget;
- equal compiler output across both compiles and after serialization/reload; and
- a `CURRENT` trusted handoff.

This verifies deterministic replay of that declared bundle under the revised contract. It does not
adopt M2A, reopen M2B, prove candidate usefulness, qualify model semantics, establish provider
request behavior, validate returned itineraries, or establish provider/product coverage.

## Fresh one-trial integrated live verification

After the revision and integrity review settled, the active V2 casebook was run once through request
understanding, controlled clarification, M1 catalog access, live M2A and M2B model seams,
deterministic M2C compilation, source-bundle reload, replay, and handoff. Preflight reserved 28 model
calls and attempted none. The full run attempted 20 calls, completed all six trajectories with zero
errors, reconciled all six traces, replayed all five planning trajectories equally with `CURRENT`
handoffs, and stopped the cash-only case upstream. It was mechanically complete. No provider call or
provider-capability binding occurred.

The public artifact is
[`2026-09-20-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v2-provider-neutral-1-trial.json`](../../evals/search_planning_live/baseline/2026-09-20-gpt-5.6-luna-m2a-m2b-m2c-integrated-casebook-v2-provider-neutral-1-trial.json).
Every accepted relationship compiled: SFO–NRT 1/1, United States–Japan 12/12, Lyon–France 0 after
the authentic policy skip, United States–India 72/72, and clarified United States–Japan 40/40. The
corresponding logical-query counts were 2, 47, 8, 84, and 57. Public-record latency totaled 199.688
seconds; private adapter traces recorded 43,178 tokens. The public redaction check found no raw
request, prompt, response, credential, or authorization fields. This is development evidence, not
independent semantic or provider/product qualification.

## Resulting status

Milestone 2C remains implemented as a zero-additional-model-call, provider-neutral compiler. M2A
remains diagnostic-only and M2B remains owner-closed. Provider planning/execution and upstream
intent/clarification artifact-constraint cleanup are separately owned follow-on work recorded in
`DEFERRED.md`.
