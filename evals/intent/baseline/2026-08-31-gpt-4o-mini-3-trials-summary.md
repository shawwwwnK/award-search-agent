# `gpt-4o-mini` intent baseline — three trials

- Date: 2026-08-31
- Corpus: 16 scenarios marked `status: ready`
- Runs: 48
- Passed all automatic checks: 14 (29.2%)
- Completed with failed checks: 31
- Errors: 3
- Total latency: 185.066 seconds
- Mean / median latency: 3.856 / 3.639 seconds
- Minimum / p95 / maximum latency: 2.128 / 5.858 / 8.075 seconds
- Usage and cost: unavailable because the current adapter does not retain response usage
- Human-review invariants: preserved but not included in the pass rate

## Per-scenario outcomes

| Scenario | Passed | Failed | Error |
| --- | ---: | ---: | ---: |
| `labor_day_thailand` | 0 | 3 | 0 |
| `labor_day_thursday_flexibility` | 0 | 1 | 2 |
| `return_weekend_after_departure` | 0 | 3 | 0 |
| `exact_dates_and_cabin` | 3 | 0 | 0 |
| `missing_origin` | 0 | 3 | 0 |
| `missing_travel_period` | 3 | 0 | 0 |
| `relative_date_expression` | 0 | 2 | 1 |
| `approximate_duration` | 3 | 0 | 0 |
| `conflicting_dates` | 0 | 3 | 0 |
| `multiple_destination_options` | 0 | 3 | 0 |
| `repositioning_allowed` | 0 | 3 | 0 |
| `adversarial_schema_instruction` | 0 | 3 | 0 |
| `early_month_with_approximate_duration` | 3 | 0 | 0 |
| `unbounded_after_new_year` | 1 | 2 | 0 |
| `whole_month_with_exact_duration` | 0 | 3 | 0 |
| `tentative_city_and_month` | 1 | 2 | 0 |

## Automatic failed-check counts

| Check | Failures |
| --- | ---: |
| `departure_window` | 11 |
| `destination` | 8 |
| `clarification` | 7 |
| `return_window` | 6 |
| `temporal_phrases` | 6 |
| `origin` | 4 |
| `unknowns` | 3 |
| `conflicts` | 3 |
| `travelers` | 3 |
| `resolved_anchor` | 2 |

## Explicit errors

- Two `labor_day_thursday_flexibility` trials raised `TemporalResolutionValidationError` because
  the second pass cited `leaving on the Thursday as well`, which is not a verbatim substring.
- One `relative_date_expression` trial raised `TemporalResolutionValidationError` because the
  second pass invented duration evidence `about a week`.

## Evidence requiring classification

- The stable cases were exact dates, missing travel period, approximate duration, and early-month
  duration behavior.
- The project owner classified the golden holiday-window boundaries as correct. The second-pass
  policy should use Friday–Monday for the Labor Day request and December 24–26 for the “over
  Christmas” request so late-Friday departures remain searchable. The baseline model instead used
  Saturday–Monday and Christmas Day alone.
- `missing_origin` expects the speaker to remain an unknown traveler, while the extractor contract
  explicitly counts “I” as one. This is a golden-contract inconsistency, not enough evidence of a
  model failure.
- Location canonicalization varied (`SF` versus `San Francisco`, `South East Asia` versus
  `Southeast Asia`, and accented or corrected spellings of São Paulo). The baseline contract did
  not define a deterministic canonical vocabulary. The subsequent owner-approved policy treats
  model-normalized names as resolver candidates and permits only explicit golden aliases; these
  historical baseline counts have not been rescored.
- Relative-weekend arithmetic, conflict preservation, region extraction, adversarial traveler
  counting, and clarification selection produced repeatable failures. The trial-level evidence is
  detailed below.

## Repeatable failures requiring trace review

“Repeatable” here means that the same scenario failed the relevant check in repeated trials; it
does not mean that the model returned the same wrong value each time.

- **Relative-weekend arithmetic:** `return_weekend_after_departure` failed its departure and return
  windows in all three trials. Against the expected September 4–7 departure and September 12–13
  return, the model produced September 5–7 plus September 11–13, September 7 plus September 7, and
  September 5–7 plus September 6–14. One trial incorrectly created a second Labor Day anchor for
  the return, while another treated “the weekend afterwards” as a one-to-seven-day duration.
  `relative_date_expression` also failed all three trials: one run was rejected for inventing
  duration evidence (`about a week`), and the two completed runs resolved “two weekends after
  Thanksgiving” to December 10–12 and December 3–5 instead of December 5–6. These traces point to
  unstable semantic interpretation before deterministic date acceptance, not one consistent
  off-by-one error.
- **Conflict preservation:** `conflicting_dates` failed to emit `return_before_departure` in all
  three trials. One proposal left both windows unresolved, so the deterministic detector had no
  dates to compare. The other two proposed July 10 outbound and July 20 return, apparently allowing
  the stated 10-day duration to overwrite “back before July 8.” Because conflict detection only
  receives the accepted windows, it could not recover the discarded contradiction. All three runs
  consequently asked about another missing field rather than asking the user to resolve the date
  conflict.
- **Region extraction:** `repositioning_allowed` omitted Europe from `destinations` in all three
  trials, despite preserving Portland, business class, award intent, and permission to reposition.
  The deterministic clarification policy therefore asked for a destination instead of the expected
  departure period. Separately, all three `whole_month_with_exact_duration` runs extracted
  `South East Asia` as a region with the original raw text and got the date arithmetic right, but
  the recorded check expected the canonical value `Southeast Asia`. That second pattern is a
  normalization/scoring-contract issue rather than evidence that the region was semantically lost.
- **Adversarial traveler counting:** `adversarial_schema_instruction` returned `travelers: null` in
  all three trials even though the request uses first-person singular and the extractor contract
  counts “I” as one traveler. The runs did resist the instruction to ignore missing details: they did
  not add point-balance fields or provider actions and all asked for the missing return timing. The
  repeatable failure is therefore narrow to first-person traveler extraction in this adversarial
  phrasing.
- **Clarification selection:** Seven runs failed the clarification check: all three
  `conflicting_dates` trials, all three `repositioning_allowed` trials, and one
  `relative_date_expression` trial. In the first six, the deterministic selector was reacting to an
  already incorrect parsed state—an absent conflict or missing Europe—rather than varying its
  priority policy. In the remaining trial, the model invented a return window and duration from
  “two weekends after Thanksgiving,” leaving no return unknown and causing `action: none`. Trace
  review should therefore separate upstream extraction/resolution errors from any issue in the
  clarification policy itself.

The highest-value trace questions are whether pass one preserved every conflicting or relative
phrase, whether pass two allowed one constraint to overwrite another, and whether deterministic
acceptance has enough structured evidence to reject a semantically unsupported but verbatim-cited
window. The `South East Asia` result should instead be reviewed in the scorer and canonicalization
contract.

## Current-workflow rerun

The full 16-scenario, three-trial matrix was rerun against the current corpus and current two-pass
workflow. The new artifact is
`2026-08-31-gpt-4o-mini-current-3-trials.json`.

- Passed all automatic checks: 30 of 48 runs (62.5%), up from 14 (29.2%).
- Completed with failed checks: 16, down from 31.
- Explicit errors: 2, down from 3.
- “Solved” below means three of three trials passed the current automatic checks. It does not prove
  future model stability, and some scenarios were solved through an approved deterministic or
  golden-policy change rather than improved model behavior.

| Scenario | Baseline | Current rerun | Mark | Evidence |
| --- | ---: | ---: | --- | --- |
| `labor_day_thailand` | 0/3 | 3/3 | **Solved** | Deterministic Friday–Monday holiday handling and accepted `SF` aliases removed all failures. |
| `missing_origin` | 0/3 | 3/3 | **Solved** | The corrected contract counts first-person “I” as one and asks for origin. |
| `multiple_destination_options` | 0/3 | 3/3 | **Solved** | Deterministic “over Christmas” handling produced December 24–26 in every trial. |
| `adversarial_schema_instruction` | 0/3 | 3/3 | **Solved in this rerun** | All trials counted “I” as one while continuing to preserve the missing return constraint. |
| `unbounded_after_new_year` | 1/3 | 3/3 | **Solved in this rerun** | All trials extracted and resolved New Year’s Day without inventing a bounded departure window. |
| `whole_month_with_exact_duration` | 0/3 | 3/3 | **Solved** | The approved location-candidate aliases accept `South East Asia`; date arithmetic remained correct. |
| `tentative_city_and_month` | 1/3 | 3/3 | **Solved** | Approved aliases accept the observed SF and São Paulo variants; January and return clarification remained correct. |
| `exact_dates_and_cabin` | 3/3 | 3/3 | Stable | No regression. |
| `approximate_duration` | 3/3 | 3/3 | Stable | No regression. |
| `early_month_with_approximate_duration` | 3/3 | 3/3 | Stable | No regression. |
| `labor_day_thursday_flexibility` | 0/3 | 0/3 | **Unsolved** | Two trials still invented the non-verbatim span `leaving on the Thursday as well`; the completed trial failed exact phrase preservation despite correct windows. |
| `return_weekend_after_departure` | 0/3 | 0/3 | **Partially improved, unsolved** | The departure window was correct in all trials, but return windows were September 1–10 or September 10–12 instead of September 12–13. |
| `relative_date_expression` | 0/3 | 0/3 | **Unsolved** | All trials produced the wrong departure weekend, invented return timing, and suppressed the required return clarification. |
| `conflicting_dates` | 0/3 | 0/3 | **Unsolved** | All trials still lost `return_before_departure`, so clarification asked about travelers or departure instead of the date conflict. |
| `repositioning_allowed` | 0/3 | 0/3 | **Unsolved** | All trials still omitted Europe and asked for destination; two also failed to count “I.” |
| `missing_travel_period` | 3/3 | 0/3 | **Automatic-check regression** | All trials normalized `LAX` to `Los Angeles International Airport`, which is not an accepted value in this golden; one trial also invented one traveler. The location portion needs policy classification before calling it a product regression. |

The rerun therefore solved seven previously failing scenarios under the current checks, preserved
three stable scenarios, left five scenarios unsolved, and introduced one scenario-level automatic
regression. The five remaining behavior clusters are verbatim flexibility evidence, relative-return
arithmetic, relative-weekend arithmetic plus unsupported return inference, conflict preservation,
and destination-region extraction.

This summary records observed behavior only. Product-owner interpretation and the next cut line
remain pending.
