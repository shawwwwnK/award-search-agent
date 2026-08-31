# `gpt-4o-mini` naive one-pass intent experiment — three trials

## Experiment definition

- Input: the same raw request, reference date, and timezone from each of the 16 ready scenarios.
- Model input does not include golden expected values.
- Operation: one stored-disabled Responses API Structured Outputs call.
- Output type: the production workflow's final `RequestUnderstandingResult` contract.
- Deliberately omitted: coarse extraction, holiday lookup, anchor enrichment, temporal grounding,
  deterministic conflict detection, and deterministic clarification policy.
- Scoring: the same automatic scorer used for the two-pass baseline.
- Model: `gpt-4o-mini`.
- Trials: 3 per scenario.

## Result

- Runs: 48
- Passed all automatic checks: 2 (4.2%)
- Schema-valid but failed checks: 27
- Schema-validation errors: 19 (39.6%)
- Schema-valid outputs: 29 (60.4%)
- Pass rate among schema-valid outputs: 2 of 29 (6.9%)
- Total latency: 187.958 seconds
- Mean / median latency: 3.916 / 3.668 seconds
- Minimum / p95 / maximum latency: 2.036 / 5.858 / 7.802 seconds
- Captured usage for 29 schema-valid calls: 122,025 input tokens, 9,674 output tokens, 131,699 total
- Usage for the 19 parse failures was unavailable, so token totals and cost are incomplete.

## Per-scenario outcomes

| Scenario | Passed | Failed | Error |
| --- | ---: | ---: | ---: |
| `labor_day_thailand` | 0 | 1 | 2 |
| `labor_day_thursday_flexibility` | 0 | 2 | 1 |
| `return_weekend_after_departure` | 0 | 1 | 2 |
| `exact_dates_and_cabin` | 2 | 1 | 0 |
| `missing_origin` | 0 | 1 | 2 |
| `missing_travel_period` | 0 | 2 | 1 |
| `relative_date_expression` | 0 | 1 | 2 |
| `approximate_duration` | 0 | 1 | 2 |
| `conflicting_dates` | 0 | 2 | 1 |
| `multiple_destination_options` | 0 | 2 | 1 |
| `repositioning_allowed` | 0 | 2 | 1 |
| `adversarial_schema_instruction` | 0 | 2 | 1 |
| `early_month_with_approximate_duration` | 0 | 2 | 1 |
| `unbounded_after_new_year` | 0 | 3 | 0 |
| `whole_month_with_exact_duration` | 0 | 2 | 1 |
| `tentative_city_and_month` | 0 | 2 | 1 |

No scenario passed all three trials.

## Failure evidence

Seventeen of the 19 errors were conditional `DateExpression` validation failures after the model
returned schema-shaped output. Examples included relative weekends without counts or anchors,
relative months without offsets, ranges without boundary components, and unresolved expressions
without reasons. Two errors were clarification objects with `action: ask` but an incomplete field
or question pair.

Automatic failed-check counts across schema-valid outputs:

| Check | Failures |
| --- | ---: |
| `travelers` | 18 |
| `departure_window` | 15 |
| `clarification` | 15 |
| `interpreted_duration` | 14 |
| `return_window` | 9 |
| `destination` | 6 |
| `date_anchor` | 6 |
| `temporal_phrases` | 4 |
| `origin` | 3 |
| `unknowns` | 3 |
| `resolved_anchor` | 3 |
| `conflicts` | 2 |

## Comparison with the production two-pass baseline

| Metric | Naive one pass | Production two pass |
| --- | ---: | ---: |
| Passed | 2 / 48 (4.2%) | 14 / 48 (29.2%) |
| Failed checks | 27 | 31 |
| Errors | 19 | 3 |
| Mean latency | 3.916 s | 3.856 s |
| Median latency | 3.668 s | 3.639 s |

The one-pass arm did not provide a latency improvement in this run despite making half as many
model calls. Its final output schema is substantially larger, and schema-invalid responses account
for most of the reliability difference. This is observed experiment evidence, not a product-owner
decision about the architecture.
