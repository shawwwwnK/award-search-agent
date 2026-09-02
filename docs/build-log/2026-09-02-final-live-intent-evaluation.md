# Minimum-disclosure two-pass intent redesign and final live evaluation

- **Date:** 2026-09-02
- **Milestone:** `raw request -> ParsedRequest -> ClarificationDecision`
- **Architecture decision:** Preserve the two-model-pass trust checkpoint defined by ADR 0007:
  `Pass 1 -> deterministic grounding/catalog construction -> Pass 2 -> deterministic evaluation`.
- **Scope boundary:** This work did not add search planning, travel-provider calls, ranking,
  persistence, UI, authentication, deployment, city-to-airport expansion, or a season policy.

## Work completed

The model boundaries now use dedicated views instead of serializing request-domain and
resolved-calendar objects directly:

- Pass one receives only `CoarseExtractionInput.request_text`. It returns non-temporal request
  fields, literally supported exact-date/named-month/holiday anchors, and verbatim temporal
  evidence with coarse claim labels. Reference date, timezone, resolved dates, provider output,
  and inferred calendar values are structurally absent from the input.
- The deterministic checkpoint grounds quotes, assigns canonical evidence IDs and exact offsets,
  validates explicit-anchor provenance, assigns stable anchor IDs, privately resolves concrete
  anchors, and constructs allowed symbolic references including `context:request_date`.
- Pass two receives a bounded temporal transcript plus date-free evidence, explicit-anchor, and
  symbolic-reference catalogs. It selects catalog IDs and emits fixed per-relation collections;
  it does not receive resolved anchor dates, reference date, timezone, provider metadata, inferred
  years, expected answers, or unrelated coarse-extraction fields.
- Pass-two wire collections cover anchor windows, month portions, relative calendar periods,
  weekends, weekdays, point offsets, durations, unbounded boundaries, and unresolved relations.
  Conversion, catalog membership, evidence compatibility, dependency, and cycle validation remain
  deterministic and produce structured stage/error records.
- Duration wire output preserves literal minimum/maximum quantity, unit, and
  exact/approximate/alternative modifier. Deterministic code owns normalization, including exact
  two weeks to 14 days, about 10 days to 9--11 days, one or two weeks to 7--14 days, and the
  documented about-a-week policy.
- Each model boundary permits at most one repair. Repair sees the same narrow original input, the
  rejected output, and structured validation errors. It cannot see concrete calendar state, an
  expected result, or an inferred correction; full deterministic validation reruns after repair,
  and a second failure remains explicit.

`next month` is represented as a whole-calendar-period relation to the symbolic
`context:request_date`, distinct from a point offset. The model does not name the concrete month;
deterministic evaluation applies the hidden request date. `next spring` remains explicitly
unresolved because no deterministic season policy is approved.

## Main implementation areas

- **Architecture and state:** ADR 0007 plus refinements/cross-references in the request-boundary,
  temporal-resolution, and temporal-evidence ADRs; architecture and project-state documentation.
- **Domain and workflow:** typed calendar-period and literal-duration relations, narrow model-view
  contracts, deterministic evidence/anchor/reference catalogs, cross-pass conformance, structured
  errors, and bounded repair in `src/award_agent/domain/` and `src/award_agent/intent/`.
- **Adapter and evaluator:** fixed relation collections and strict Structured Output schemas in the
  OpenAI adapter; schema-v3 scoring, failure-stage aggregation, repair metrics, latency, and token
  usage in `src/award_agent/cli/intent_eval.py`.
- **Regression coverage:** payload non-leakage, context invariance, catalog membership, claim
  coverage, whole relative months, unsupported seasons, duration normalization, structured
  failures, bounded repair, and evaluator aggregation under `tests/`.
- **Evaluation corpus and documentation:** schema-v3 expectations in `evals/intent/cases.yaml`,
  evaluator documentation, retained baseline artifacts, and this build-log entry.

## Offline verification before the live run

The orchestration stop gate recorded:

| Gate | Result |
| --- | --- |
| `.venv/bin/python -m pytest` | Passed: 204 tests |
| `.venv/bin/ruff check .` | Passed |
| `.venv/bin/ruff format --check .` | Passed: 83 files already formatted |
| `.venv/bin/mypy src tests` | Passed: 43 source files |
| `git diff --check` | Passed |
| Strict schema inspection | No `oneOf`, `anyOf`, or nullable/null constructs |
| Serialized payload inspection | No prohibited reference date, timezone, or resolved calendar context |

These were offline gates using fake model passes and holiday providers where applicable. They do
not establish live-model accuracy.

## Live evaluation execution

The completed networked evaluation used:

```text
.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --trials 3 --output evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials-2.json
```

The command exited 1 because evaluated cases failed blocking checks. The runner itself completed
and persisted a valid artifact. `jq empty`, an independent artifact audit, and aggregate
recomputation passed. The artifact contains all 16 ready scenarios, 48 unique case/trial pairs, and
exactly three trials per scenario.

An earlier network-restricted attempt also exited 1 and persisted
`evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials.json`. Its 48 uniform pass-one model-output
errors were caused by unavailable network access. That file is retained only as an
**excluded, non-representative environment diagnostic** and is not included in any result or
comparison below.

## Live results

| Measure | Result |
| --- | ---: |
| Ready scenarios / runs | 16 / 48 |
| Passed all blocking checks | 4 (8.3%) |
| Runner status `failed` | 19 |
| Completed outputs with failed checks | 18 |
| Structured grounding failure without output | 1 |
| Runner status `error` | 25 |
| First-attempt completion | 15/48 (31.2%) |
| Final completion | 22/48 (45.8%) |
| Runs recovered to completion by repair | 7 |

Failure dimensions overlap and therefore must not be summed as mutually exclusive root causes:

| Dimension | Runs |
| --- | ---: |
| Pass-one failures | 3 |
| Pass-two wire failures | 5 |
| Grounding failures | 1 |
| Semantic-validation failures | 31 |
| Deterministic-output failures | 6 |
| Clarification failures | 5 |
| Evidence-support failures, reported separately | 4 |

All 25 explicit errors retained structured stage, error code, and validation cause. Representative
records include `pass_one_anchor_validation / anchor_kind_evidence_mismatch`,
`pass_two_wire_conversion / unknown_evidence_id`,
`pass_two_wire_conversion / unknown_anchor_id`,
`pass_two_conformance / incompatible_evidence_claim`,
`pass_two_conformance / unsupported_bounded_temporal_language`, and
`pass_two_dependency_validation / cyclic_dependency`. No error was collapsed into the generic
`invalid temporal reference` message.

### Repair observations

- 34 stage-level repair attempts occurred across 33 runs.
- 8 stage repairs succeeded across 7 runs; 26 failed.
- Pass one attempted 5 repairs and succeeded 2; pass two attempted 29 and succeeded 6.
- No model boundary repaired more than once. One run repaired once at each boundary, resulting in
  two run-level repair attempts.
- Persisted repair traces contained none of the prohibited reference-date, timezone, resolved-date,
  expected-answer, or inferred-correction keys. Actual request packet bodies are not persisted, so
  the live evidence is a trace audit supplemented by static DTO/serialization inspection, not a
  packet capture.

### Temporal observations

- **`next month`:** 0/3 trials completed. Trials 1 and 3 reached pass two without an accepted
  explicit inferred anchor, but emitted invalid month-portion anchor references rather than a
  symbolic relative-calendar-period relation. Trial 2 proposed an unsupported explicit month
  anchor and was rejected during pass-one validation. No inferred September anchor was accepted.
  Because no trial reached deterministic evaluation, this live run did not demonstrate the expected
  private September 1--30, 2026 result.
- **`next spring`:** All three trials retained the phrase as unresolved, created no explicit anchor
  or bounded departure window, and preserved departure as unknown. They failed other destination,
  relation-target, evidence, and clarification checks.
- **Duration:** All 14 completed duration relations matched independently recomputed deterministic
  day bounds. Ten literal-duration checks failed upstream because the model converted weeks to days,
  changed exactness, or omitted the expected duration relation. Deterministic code did not silently
  accept or repair those semantic changes.

### Latency and usage

| Measure | Result |
| --- | ---: |
| Total latency | 321.280 seconds |
| Mean / median | 6.693 / 5.954 seconds per run |
| p95 / range | 12.034 / 3.242--32.728 seconds |
| Model calls with captured usage | 132/132 |
| Input / output tokens | 306,602 / 23,281 |
| Total tokens | 329,883 |
| Cost | Not calculated by the runner |

## Retained-baseline comparison

| Artifact / evaluator contract | Passed | Failed | Errors | Total latency |
| --- | ---: | ---: | ---: | ---: |
| 2026-08-31 original, schema v1 | 14 | 31 | 3 | 185.066 s |
| 2026-08-31 current-workflow rerun, schema v1 | 30 | 16 | 2 | 197.078 s |
| 2026-09-01 post-fix relation run, schema v2 | 8 | 7 | 33 | 320.547 s |
| 2026-09-02 minimum-disclosure run, schema v3 | 4 | 19 | 25 | 321.280 s |

Raw pass rates are not directly comparable. Schema v1 predates the catalog boundary, typed
relations, conformance validation, and repair metrics. Schema v2 used the earlier flat nullable wire
and did not score current claim-level evidence support, literal-duration preservation, typed
relation invariants, or forbidden deictic-anchor behavior. Schema v3 adds the minimum-disclosure
catalogs, fixed relation collections, bounded repair, and structured failure aggregation. The
reduction from 33 to 25 explicit errors relative to schema v2 occurred under a different contract
and is not an accuracy delta.

## Remaining failures by owning layer

- **Pass one/model semantics:** unsupported inferred anchors, anchor/evidence-kind mismatches, one
  invalid repeated-evidence occurrence, and inconsistent non-temporal destination/traveler output.
- **Pass-two wire/catalog selection:** unknown evidence IDs and invalid anchor references, including
  treating `context:request_date` as evidence or a month-portion anchor.
- **Pass-two semantic interpretation:** incompatible claim/relation selections, self-referential
  dependency cycles, failure to preserve unsupported bounded language, and loss or rewriting of
  literal duration semantics.
- **Evidence support and grounding:** insufficient claim coverage in four completed records and one
  invalid occurrence that prevented completion.
- **Deterministic output scoring:** six runs differed on expected windows, normalized duration,
  conflict, or resolved-anchor checks. The artifact does not establish that all six are arithmetic
  defects; upstream semantic differences contribute to this dimension.
- **Clarification policy/output:** five runs differed from expected clarification fields or actions,
  sometimes downstream of earlier semantic or deterministic differences.
- **Instrumentation:** cost is unavailable, and non-leaking repair was not verified from persisted
  packet bodies because those bodies are intentionally not retained.

## Artifacts and commands

Primary evidence:

- `evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials-2.json`
- `evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials-2-summary.md`
- `docs/build-log/2026-09-02-final-live-intent-evaluation.md`

Excluded diagnostic:

- `evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials.json`

Recorded evaluation and validation commands:

- `.venv/bin/python -m award_agent.cli.intent_eval --help` — exit 0.
- Initial network-restricted evaluation command — exit 1; excluded diagnostic persisted.
- Completed networked evaluation command shown above — exit 1 due to evaluated failures, not a
  runner or persistence failure.
- `jq empty evals/intent/baseline/2026-09-02-gpt-4o-mini-3-trials-2.json` — exit 0.
- Independent 16-case/48-run/three-trials-per-case artifact audit — exit 0.
- `git diff --check` — exit 0.
- `git status --short` — exit 0.

## Assumptions, limitations, and preservation

- The approved two-pass architecture and strict grounding policy were retained. This session did
  not authorize collapsing the workflow, weakening validators, adding phrase-specific calendar
  correction rules, or introducing a deterministic season policy.
- The evaluator-contract changes prevent direct accuracy comparison with schema-v1 and schema-v2
  artifacts.
- The live runner reports overlapping failure dimensions; owning-layer classifications can overlap
  and are diagnostic rather than a mutually exclusive root-cause allocation.
- Existing unrelated dirty-worktree changes were preserved. The external workbook was not modified.
  No commit was created.

## Owner placeholders

- **Product-owner interpretation:** _Pending._
- **Final cut-line decision:** _Pending owner decision._
