# Focused `gpt-4o-mini` prompt/schema evaluation

- Date: 2026-09-02
- Model: `gpt-4o-mini`
- Evaluator contract: schema v3, unchanged
- Trials: 3 across 10 unchanged ready scenarios (30 runs)
- Production corpus SHA-256: `c27ff9fc3295cdb50668386940b9d576e2566818bc4c8d611863d9dbcae27319`
- Focused temporary corpus SHA-256: `7a6a3bd3421e0941f4d307991ef4649812f7ee7f34f5351dd3ef12b9be6fe576`
- Artifact: `2026-09-02-gpt-4o-mini-prompt-schema-focused-3-trials.json`

The temporary corpus selected the original entries for no travel period, `next month`, `next
spring`, `first week of June`, relative weekend, relative weekday, exact week duration,
approximate week duration, unbounded `after New Year`, and conflicting dates. Expectations and
case bodies were not edited.

## Same-case comparison

| Measure | 2026-09-02 baseline subset | Prompt/schema candidate |
| --- | ---: | ---: |
| Passed / failed / error | 0 / 11 / 19 | 7 / 12 / 11 |
| First-attempt completion | 7/30 | 12/30 |
| Final completion | 11/30 | 19/30 |
| Pass-one failures | 1 | 0 |
| Pass-two wire failures | 5 | 1 |
| Grounding failures | 0 | 0 |
| Semantic-validation failures | 22 | 18 |
| Dependency-stage errors | 6 | 5 |
| Evidence-support failures | 3 | 1 |
| Deterministic-output failures | 3 | 4 |
| Clarification failures | 4 | 4 |
| Recorded repair attempts / successes | 23 / 4 | 18 / 7 |
| Total latency | 180.661 s | 143.853 s |
| Model calls | 84 | 78 |
| Input / output tokens | 194,413 / 11,865 | 275,385 / 10,809 |

The focused gate showed meaningful improvement in pass rate, completion, wire validity, and repair
success, so a full 16-case, three-trial evaluation was authorized by the stated gate. Input-token
usage increased because the generated schema now exposes substantially more field-level semantic
guidance.

## Observed limits

- `first week of June` failed all three trials. The current contract requires a literal June anchor
  claim but gives an unresolved wire item no way to consume that anchor; changing conformance was
  outside this task.
- `after New Year` remained unreliable and produced unresolved request-field dependencies.
- `next month` reached a correct symbolic relative-calendar-period relation in completed trials,
  but unrelated traveler expectations kept those cases from passing.
- `next spring` consistently became unresolved with target `departure`; non-temporal destination
  extraction and clarification priority still failed.

## Owner placeholders

- Product-owner interpretation: _Pending._
- Next cut-line decision: _Pending owner decision._
