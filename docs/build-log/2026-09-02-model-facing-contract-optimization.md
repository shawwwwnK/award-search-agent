# Model-facing contract optimization and live evaluation

- **Date:** 2026-09-02
- **Milestone:** `raw request -> ParsedRequest -> ClarificationDecision`
- **Scope:** Pydantic descriptions and LLM instructions for the approved two-pass workflow only.

## Work attempted

The generated pass-one and pass-two schemas, repair schemas, serialized payloads, prompts, tests,
and final schema-v3 live artifact were audited. The intervention added field-local guidance for
claim labels, ID namespaces, targets and references, literal duration values, unresolved targets,
and nonredundant relation selection. Initial and repair instructions received concise positive and
negative examples plus error-code-specific repair guidance that does not disclose corrections.

No deterministic validator, calendar arithmetic, corpus expectation, season policy, evaluator
semantic, model choice, provider boundary, or search-planning behavior changed.

## Files changed

- `src/award_agent/domain/models.py`
- `src/award_agent/intent/model_views.py`
- `src/award_agent/intent/openai_extractor.py`
- `tests/unit/test_openai_extractor.py`
- focused and full JSON artifacts and Markdown summaries under `evals/intent/baseline/`
- this build-log entry

## Offline evidence

| Command | Exit | Result |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | 206 passed |
| `.venv/bin/ruff check .` | 0 | All checks passed |
| `.venv/bin/ruff format --check .` | 0 | 85 files already formatted |
| `.venv/bin/mypy src tests` | 0 | 43 source files, no issues |
| `git diff --check` | 0 | Passed |

Targeted contract tests verify generated schema descriptions, supported strict-schema union shapes,
literal duration language, namespace and reference guidance, prompt-visible examples, repair
instructions, and prohibited-context absence from serialized pass and repair payloads.

## Live evidence

The focused 30-run command exited 1 because evaluated cases failed and persisted a valid artifact.
It improved from 0 to 7 passes and from 11 to 19 final completions on the corresponding prior
case/trial subset, satisfying the stated gate for a full run.

The full 48-run command also exited 1 because evaluated cases failed and persisted a valid artifact.
Against the directly comparable prior schema-v3 artifact, passes increased 4 to 11, first-attempt
completion 15 to 17, and final completion 22 to 30. Explicit errors decreased 25 to 18. Pass-one
failures fell 3 to 0, wire failures 5 to 1, and evidence-support failures 4 to 0. Dependency errors
rose 6 to 10, deterministic-output mismatch dimensions rose 6 to 11, and input tokens rose 306,602
to 450,127. Full details are in the artifact summary.

Captured-call reconciliation verifies that the prior artifact omitted five successful pass-one
repairs from its trace-derived aggregate after later pass-two failures replaced the trace. Corrected
prior repair accounting is 39 attempts and 13 successes, rather than 34 and 8. The new artifact's
31 attempts and 13 successes reconcile exactly with 127 captured calls.

## Observed limitation

`first week of June` exposes a pre-existing contract gap: pass one must retain the literal June
anchor claim, while an unresolved pass-two item cannot reference that anchor to consume the claim.
Adding a deterministic exception or changing conformance was deliberately not included. Unbounded
boundary and duration dependency selection also remain unreliable despite clearer guidance.

## Owner placeholders

- **Architectural/product interpretation:** _Pending project owner._
- **What the project owner changed or rejected:** _Pending project owner._
- **Final next cut line:** _Pending project owner decision._

## Pass 2-only model experiment

### Work attempted

The first Pass 2 contract evaluation suggested a targeted capacity experiment. The evaluator now
accepts optional `--pass-one-model` and `--pass-two-model` overrides while preserving the existing
single-`--model` default. Usage from split extractors is combined per workflow run; production
workflow wiring and model defaults are unchanged.

### Evidence

With Pass 1 fixed at `gpt-4o-mini` and Pass 2 set to `gpt-4o`, the focused 24-run sample improved
passes 9 to 13 and final completion 16 to 18; relative-date and return-weekend evidence association
improved. Approximate duration and unbounded-boundary failures remained.

The full 48-run sample improved passes 15 to 23, first-attempt completion 23 to 34, final completion
34 to 40, and explicit errors 13 to 8. Pass-two wire failures fell 7 to 2, evidence-support
failures 3 to 0, and deterministic-output failures 12 to 7. Dependency terminal errors rose 0 to 3
and clarification failures 4 to 8.

Total latency rose from 285.463s to 451.516s (mean 5.947s to 9.407s). Total tokens fell 474,532 to
409,878 because fewer repairs were needed. Captured calls reconciled exactly (123/123 versus
109/109). Cost was not calculated.

The artifacts are:

- `evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-focused-3-trials.json`
- `evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-focused-3-trials-summary.md`
- `evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-full-3-trials.json`
- `evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-full-3-trials-summary.md`

Both live commands exited 1 because the corpus still contains failing cases; the runner executed and
persisted complete artifacts.

Exact experiment commands:

- `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --pass-one-model gpt-4o-mini --pass-two-model gpt-4o --cases /private/tmp/award-intent-pass2-focused-2026-09-02.yaml --trials 3 --output evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-focused-3-trials.json` (exit 1)
- `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --pass-one-model gpt-4o-mini --pass-two-model gpt-4o --trials 3 --output evals/intent/baseline/2026-09-02-gpt-4o-pass2-only-full-3-trials.json` (exit 1)

### Interpretation boundary

This is evidence that Pass 2 model capacity matters for ID/evidence association, but it is not a
production model recommendation. The latency increase, remaining high-occurrence failures, small
sample, and increased clarification failures require project-owner cost/quality interpretation.

### Owner placeholders

- **Model-quality/cost interpretation:** _Pending project owner._
- **Production model-selection decision:** _Pending project owner._
- **Final next cut line:** _Pending project owner decision._

## Pass 2 contract follow-up

### Work attempted

The high-occurrence dependency and conformance failures in the first prompt/schema candidate were
traced to three model-visible ambiguities: catalogs named valid identifiers without stating how
they could be used; canonical named-month anchors did not state their required direct relation;
and dependency errors did not locate the consuming constraint precisely enough for repair.

The Pass 2 contract now includes:

- a canonical `direct_relation_kind` on every explicit anchor catalog entry;
- `allowed_targets` and `allowed_relation_kinds` on symbolic reference entries;
- `allowed_relation_kinds` derived for every temporal evidence entry;
- field-adjacent instructions to copy IDs exactly and obey those permissions;
- repair guidance to replace only the invalid local dependency rather than inventing a producer;
- exact collection, constraint index, relation kind, evidence ID, and reference key on deterministic
  dependency and cycle failures.

Both the OpenAI adapter and shared deterministic conformance layer enforce the catalog permissions.
No phrase-specific correction, calendar arithmetic, approved policy, golden expectation, repair
limit, or private prompt context changed.

### Files changed in this follow-up

- `src/award_agent/intent/model_views.py`
- `src/award_agent/intent/openai_extractor.py`
- `src/award_agent/intent/conformance.py`
- `src/award_agent/intent/temporal.py`
- `tests/unit/test_openai_extractor.py`
- `tests/unit/test_repair.py`
- `tests/unit/test_temporal_conformance.py`
- `tests/unit/test_temporal_relations.py`
- `tests/unit/test_workflow.py`
- focused and full Pass 2 JSON artifacts and Markdown summaries under `evals/intent/baseline/`
- `docs/project-state.md`
- this build-log entry

### Offline evidence

| Command | Exit | Result |
| --- | ---: | --- |
| `.venv/bin/python -m pytest -q` | 0 | 213 passed |
| `.venv/bin/ruff check .` | 0 | All checks passed |
| `.venv/bin/ruff format --check .` | 0 | 92 files already formatted |
| `.venv/bin/mypy src tests` | 0 | 43 source files, no issues |
| `git diff --check` | 0 | Passed |

New tests cover permission-bearing serialized catalogs, canonical direct named-month relations,
self-reference and permission rejection at both enforcement layers, localized dependency/cycle
errors, prompt-visible repair instructions, prohibited-context absence, and strict-schema shape.
The strict Pass 2 schema contains no `oneOf`, `anyOf`, or nullable fields.

### Live evidence

The first 24-run focused candidate was retained but rejected because the legitimate
`return_weekend_after_departure` case passed 0/3. After evidence-relation permissions were added, a
second non-overwriting focused run passed 9, completed with failed checks 7, and ended in error 8.
On the identical immediate-before subset, the counts were 3 / 3 / 18. First-attempt completion rose
4 to 10 and final completion 6 to 16, so the focused gate justified a full run.

The full run passed 15, completed with failed checks 20, and ended in error 13. Against the immediate
pre-Pass 2 artifact, passes rose 11 to 15, first-attempt completion 17 to 23, and final completion 30
to 34. Dependency terminal failures fell 10 to 0 and semantic-validation failure dimensions fell
26 to 14. Wire failures rose 1 to 7 because invented IDs and an evidence/relation mismatch were
rejected explicitly. Evidence-support failures rose 0 to 3, deterministic-output failures changed
11 to 12, and clarification failures remained 4.

The candidate recorded 28 repairs and 14 stage-level successes: Pass 1 was 5/6 and Pass 2 was 9/22.
Recorded repairs exactly match attempts inferred from 123 captured calls. Total latency increased
246.320 to 285.463 seconds; total tokens increased 468,246 to 474,532. Cost was not calculated.

Both live commands exited 1 because one or more evaluated cases failed; each runner executed and
persisted its requested artifact. Detailed per-case results, regressions, and unchanged limits are
recorded in the adjacent artifact summaries.

Exact live commands:

- `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --cases /private/tmp/award-intent-pass2-focused-2026-09-02.yaml --trials 3 --output evals/intent/baseline/2026-09-02-gpt-4o-mini-pass2-contract-focused-3-trials-2.json` (exit 1: case failures; artifact persisted)
- `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --trials 3 --output evals/intent/baseline/2026-09-02-gpt-4o-mini-pass2-contract-full-3-trials.json` (exit 1: case failures; artifact persisted)

### Observed limitations

The stronger contract eliminates self-referential dependency terminal failures in this sample, but
does not make ID copying or evidence-to-target association reliable. `missing_travel_period`
invented unresolved evidence IDs, relative weekday evidence repeatedly attached to the wrong
target, and approximate-duration repairs invented month-anchor IDs. These should not be accepted by
weaker validation.

`first week of June` retains the unresolved-anchor consumption gap identified in the prior session.
Any deterministic conformance change for that gap remains a separate proposed follow-up.

### Owner placeholders for the Pass 2 follow-up

- **Interpretation of evidence:** _Pending project owner._
- **Workflow or model change decision:** _Pending project owner._
- **What the project owner changed or rejected:** _Pending project owner._
- **Final next cut line:** _Pending project owner decision._
