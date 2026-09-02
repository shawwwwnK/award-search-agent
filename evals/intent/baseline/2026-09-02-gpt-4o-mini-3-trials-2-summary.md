# `gpt-4o-mini` final live intent evaluation — three trials

- Date: 2026-09-02
- Artifact: `2026-09-02-gpt-4o-mini-3-trials-2.json`
- Contract: schema version 3, production `two_pass` strategy
- Corpus: 16 scenarios marked `status: ready`; 48 runs; every ready scenario appears once in each
  of trials 1–3
- Outcome: 4 passed all blocking checks, 19 have runner status `failed`, and 25 have runner status
  `error` (8.3% all-check pass rate)
- Completion caveat: 18 of the 19 `failed` records are completed outputs with failed checks; the
  remaining record is a structured pass-one grounding failure without an output. Thus 22/48 runs
  completed finally, not 23/48.
- First-attempt completion: 15/48 (31.2%)
- Final completion: 22/48 (45.8%); seven runs completed only after repair
- Repairs: 34 stage-level attempts in 33 runs; 8 successful stage repairs in 7 runs; 26 failed
  stage repairs. Pass one attempted 5 and succeeded 2; pass two attempted 29 and succeeded 6. No
  boundary repaired more than once. One run repaired both boundaries, so its run-level total is 2.
- Latency: 321.280 seconds total; 6.693 seconds mean; 5.954 seconds median; 12.034 seconds p95;
  3.242–32.728 seconds range
- Usage: all 132 calls were captured across all 48 runs; 306,602 input tokens, 23,281 output
  tokens, and 329,883 total tokens
- Cost: not calculated by the runner

## Failure dimensions

These evaluator counters overlap. They describe failed dimensions, not mutually exclusive root
causes.

| Dimension | Runs | Objective detail |
| --- | ---: | --- |
| Pass-one failure | 3 | 2 anchor-kind/evidence mismatches; 1 invalid evidence occurrence |
| Pass-two wire failure | 5 | 3 unknown evidence IDs; 2 unknown anchor IDs |
| Grounding failure | 1 | `exact_dates_and_cabin` trial 2 used occurrence 1 for the sole `October 15` match |
| Semantic-validation failure | 31 | 18 explicit pass-two conformance/dependency errors plus 13 completed outputs with failed semantic checks |
| Deterministic-output failure | 6 | At least one expected window, interpreted duration, conflict, or resolved-anchor check failed |
| Clarification failure | 5 | Expected clarification fields/actions did not match |
| Evidence-support failure | 4 | Separate claim-support diagnostic; not included in the runner's one grounding-failure counter |

All 25 `status: error` records are `TemporalResolutionValidationError` records with structured
`stage`, `error_code`, and `validation_cause`. Representative retained errors include:

- `pass_one_anchor_validation / anchor_kind_evidence_mismatch`: literal evidence does not name the
  selected month or date.
- `pass_two_wire_conversion / unknown_evidence_id`: `context:request_date` was selected as evidence
  even though it is a symbolic reference, not an evidence-catalog ID.
- `pass_two_wire_conversion / unknown_anchor_id`: `unspecified` or `context:request_date` was
  selected as a month-portion anchor.
- `pass_two_conformance / incompatible_evidence_claim`: the selected evidence claim was
  incompatible with relation kind and target.
- `pass_two_conformance / unsupported_bounded_temporal_language`: `first week of June` was not
  preserved as unresolved under the approved vocabulary.
- `pass_two_dependency_validation / cyclic_dependency`: a departure or return relation depended on
  itself.

No result contains the prior generic `invalid temporal reference` message.

## Every non-passing run by owning layer

`P1` is pass-one validation/semantics, `P2-wire` is pass-two catalog/wire conversion, `P2-sem` is
pass-two semantic conformance or relation scoring, `ground` is exact grounding, `support` is
claim-evidence sufficiency, `det` is deterministic output scoring, and `clarify` is clarification
policy scoring.

| Scenario | Non-passing trials and classification |
| --- | --- |
| `labor_day_thailand` | T1 P1 anchor validation; T2 P2-sem incompatible evidence; T3 P2-sem literal duration + det return/duration |
| `labor_day_thursday_flexibility` | T1 P2-sem cyclic dependency; T2–T3 P2-sem incompatible evidence |
| `return_weekend_after_departure` | T1/T3 P2-sem incompatible evidence; T2 support |
| `exact_dates_and_cabin` | T2 ground invalid occurrence; T3 det return window + clarify |
| `missing_origin` | T1/T3 P2-sem literal duration; T2 P2-sem literal duration + det interpreted duration |
| `missing_travel_period` | T1–T3 P2-wire unknown evidence ID |
| `relative_date_expression` | T1–T2 P2-sem cyclic dependency; T3 P2-sem incompatible evidence |
| `approximate_duration` | T1–T3 P2-sem unsupported bounded temporal language |
| `conflicting_dates` | T1/T3 P2-sem cyclic dependency; T2 det conflict |
| `multiple_destination_options` | T1–T3 P2-sem literal duration |
| `repositioning_allowed` | T1–T3 P1 destination semantics + P2-sem relation + support + clarify; T2 also P1 travelers |
| `adversarial_schema_instruction` | T1/T3 P2-wire unknown anchor ID; T2 P1 anchor validation |
| `early_month_with_approximate_duration` | T3 det departure and return windows |
| `unbounded_after_new_year` | T1 P2-sem incompatible evidence; T2 P2-sem cyclic dependency; T3 det windows + clarify |
| `whole_month_with_exact_duration` | T1–T3 P2-sem literal duration |
| `tentative_city_and_month` | T1–T2 P2-sem incompatible evidence |

## Required temporal and repair checks

- `next month`: 0/3 runs completed. Trials 1 and 3 cleared pass one without an accepted explicit
  anchor, but pass two emitted invalid month-portion anchor references rather than the required
  symbolic `relative_calendar_period`. Trial 2 ended at pass-one anchor validation after the model
  proposed an unsupported month anchor; deterministic validation rejected it. No explicit inferred
  September anchor was accepted. Because no trial reached deterministic evaluation, no live output
  demonstrated the expected private result `2026-09-01` through `2026-09-30`.
- `next spring`: all 3 runs retained no explicit date anchor, emitted an unresolved relation for the
  exact phrase, left departure unbounded, and preserved `departure` as unknown. All three still
  failed unrelated destination/relation-target/evidence/clarification expectations.
- Duration normalization: all 14 completed duration relations mapped to their deterministic day
  bounds with zero recomputed mismatches. Ten literal-duration checks nevertheless failed because
  model relations converted stated weeks to days, changed exactness, or omitted the expected
  duration relation; deterministic code did not silently repair those semantics.
- Repair bound: no pass-one or pass-two trace records more than one repair. One run used one repair
  at each boundary.
- Repair disclosure: persisted repair traces contain no reference-date, timezone, resolved-date,
  expected/golden-answer, or inferred-correction keys. The repair DTOs and serialization call sites
  also expose only the narrow original model input, rejected output, and structured validation
  errors. The live artifact does not persist actual request payload bodies, so this is a trace plus
  static contract audit rather than packet-level evidence.
- Structured failures: all explicit errors retain their stage, code, relation/collection identifiers
  when applicable, and validation cause.

## Retained-baseline comparison

| Artifact / evaluator contract | Passed | Failed | Errors | Total latency |
| --- | ---: | ---: | ---: | ---: |
| 2026-08-31 original, schema v1 | 14 | 31 | 3 | 185.066 s |
| 2026-08-31 current-workflow rerun, schema v1 | 30 | 16 | 2 | 197.078 s |
| 2026-09-01 post-fix relation run, schema v2 | 8 | 7 | 33 | 320.547 s |
| 2026-09-02 minimum-disclosure run, schema v3 | 4 | 19 | 25 | 321.280 s |

Raw pass-rate changes are not directly comparable. The schema-v1 artifacts used exact
`temporal_phrases` checks and predate the current catalog boundary, typed relations, conformance
validation, and repair metrics. The schema-v2 post-fix run used the earlier flat nullable wire and
did not score the current claim-level evidence support, typed temporal-relation invariants, literal
duration, or forbidden deictic-anchor checks. Schema v3 adds the minimum-disclosure catalogs,
fixed per-relation wire collections, bounded repairs, structured stage aggregation, and those new
blocking checks. The reduction from 33 to 25 `status: error` records versus schema v2 occurred under
a different wire and evaluator contract and is not an accuracy delta.

## Runner and instrumentation observations

- The first sandboxed invocation persisted `2026-09-02-gpt-4o-mini-3-trials.json` with 48 uniform
  pass-one model-output errors because network access was unavailable. It is an execution-environment
  diagnostic, was excluded from all results above, and was not overwritten. The numbered artifact
  is the completed networked evaluation.
- Runner status `failed` combines check-failing completed outputs with structured grounding
  failures; `final_completion` is the authoritative completion count.
- Repair payload bodies and rejected outputs are not persisted, limiting live disclosure audits to
  the retained traces and static serialized DTO contract.
- Token usage is now complete for this run, but the runner does not calculate cost. Its fixed cost
  message still refers to potentially partial failed-parse usage even though this artifact reports
  zero missing calls.

## Owner placeholders

- Product-owner interpretation: _Pending._
- Final cut-line decision: _Pending owner decision._
