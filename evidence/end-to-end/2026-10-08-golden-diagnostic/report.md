# Early-2027 input-to-Results diagnostic

Six derivatives of the intent golden corpus, using reference date **2026-10-08**. These are review candidates; no end-to-end golden set has been selected.

| Case | Initial intent | Provider profile | Admitted / conditional | Results | Live stages | Tokens (in / out) | Model estimate |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| [ready_whole_month](early-2027/runs/ready_whole_month/answer.md) | ready; date matched | compact | 0 / 0 | delivered / clean | 186.2s | 256,262 / 5,704 | $0.0352 |
| [ready_early_month](early-2027/runs/ready_early_month/answer.md) | ready; date matched | compact | 0 / 0 | delivered / clean | 171.0s | 413,527 / 7,303 | $0.0555 |
| [ready_holiday_window](early-2027/runs/ready_holiday_window/continuation-1/answer.md) | clarification required | compact | 0 / 0 | delivered / clean | 212.1s | 65,228 / 8,655 | $0.0147 |
| [typo_recognizable_date](early-2027/runs/typo_recognizable_date/continuation-3/answer.md) | clarification required | standard | 0 / 232 | delivered / annotated | 313.6s | 1,538,869 / 27,395 | $0.3791 |
| [mixed_award_cash_eligible](early-2027/runs/mixed_award_cash_eligible/continuation-3/answer.md) | clarification required | standard | 26 / 232 | delivered / clean | 344.6s | 1,732,404 / 29,609 | $0.4270 |
| [default_award_home_airport_not_return](early-2027/runs/default_award_home_airport_not_return/answer.md) | ready; date matched | standard | 0 / 0 | delivered / clean | 196.6s | 65,179 / 7,565 | $0.0121 |

Live latency composes the latest completed stages with initial intent and any scripted clarification; superseded budget runs, replay and permission gaps are separate. Tokens and model cost include all retained generation attempts for that case, including profile contrasts. Cost excludes provider and token-count endpoint charges. Every acquired provider result is partial. Compact runs can omit itinerary details after exhausting their budget; zero complete journeys does not mean no awards were available. Clean Results checks do not establish semantic truth.

Revised campaign total, including all retained contrasts: 37 generation calls; 4,071,469 input and 86,231 output tokens; estimated generation cost $0.923774.

## ready_whole_month

> Find one award seat from SFO to BKK in January 2027.

[Original intent and complete stage traces](early-2027/runs/ready_whole_month/summary.json) · [Final stage summary](early-2027/runs/ready_whole_month/summary.json) · [Answer](early-2027/runs/ready_whole_month/answer.md) · [Ranking dispositions](early-2027/runs/ready_whole_month/matched.json) · [Results checks and claims](early-2027/runs/ready_whole_month/results-artifact.json)

Stages: intent 3.1s; clarification 0.0s; planning 74.4s; providers 68.0s; ranking 0.7s; results 40.1s.

Acquisition retained 383 normalized observations; 3 award requests including 0 detail calls, and 1 cash requests. Ranking dispositions: 0 admitted, 0 conditional, 0 rejected. Results selected 0 journeys.

## ready_early_month

> Find one award seat from SFO to BKK in early February 2027.

[Original intent and complete stage traces](early-2027/runs/ready_early_month/summary.json) · [Final stage summary](early-2027/runs/ready_early_month/summary.json) · [Answer](early-2027/runs/ready_early_month/answer.md) · [Ranking dispositions](early-2027/runs/ready_early_month/matched.json) · [Results checks and claims](early-2027/runs/ready_early_month/results-artifact.json)

Stages: intent 4.6s; clarification 0.0s; planning 64.3s; providers 43.5s; ranking 0.5s; results 58.1s.

Acquisition retained 289 normalized observations; 3 award requests including 0 detail calls, and 1 cash requests. Ranking dispositions: 0 admitted, 0 conditional, 0 rejected. Results selected 0 journeys.

## ready_holiday_window

> I need one award seat from Seattle to Tokyo over Martin Luther King Jr. Day weekend in 2027.

[Original intent and complete stage traces](early-2027/runs/ready_holiday_window/summary.json) · [Final stage summary](early-2027/runs/ready_holiday_window/continuation-1/summary.json) · [Answer](early-2027/runs/ready_holiday_window/continuation-1/answer.md) · [Ranking dispositions](early-2027/runs/ready_holiday_window/continuation-1/matched.json) · [Results checks and claims](early-2027/runs/ready_holiday_window/continuation-1/results-artifact.json)

Stages: intent 15.0s; clarification 2.4s; clarification_answer 2.4s; planning 87.9s; providers 61.8s; ranking 0.2s; results 42.4s.

Acquisition retained 69 normalized observations; 3 award requests including 0 detail calls, and 1 cash requests. Ranking dispositions: 0 admitted, 0 conditional, 0 rejected. Results selected 0 journeys.

The original request needed clarification. A separately recorded fixture-derived answer enabled this continuation; it is not a first-pass success.

## typo_recognizable_date

> Find one award seat from SFO to BKK on the Fridai after New Year's Day 2027.

[Original intent and complete stage traces](early-2027/runs/typo_recognizable_date/summary.json) · [Final stage summary](early-2027/runs/typo_recognizable_date/continuation-3/summary.json) · [Answer](early-2027/runs/typo_recognizable_date/continuation-3/answer.md) · [Ranking dispositions](early-2027/runs/typo_recognizable_date/continuation-3/matched.json) · [Results checks and claims](early-2027/runs/typo_recognizable_date/continuation-3/results-artifact.json)

Stages: intent 11.0s; clarification 1.3s; clarification_answer 2.8s; planning 70.0s; providers 61.8s; ranking 1.4s; results 165.3s.

Acquisition retained 247 normalized observations; 9 award requests including 2 detail calls, and 3 cash requests. Ranking dispositions: 0 admitted, 232 conditional, 296 rejected. Results selected 3 journeys.

The original request needed clarification. A separately recorded fixture-derived answer enabled this continuation; it is not a first-pass success.

Remaining failed checks (delivered with local notices):

- `shared_binding_key`: Shared journey fact provider_status has a duplicate or global key.
- `shared_binding_key`: Shared journey fact coverage has a duplicate or global key.
- `shared_binding_key`: Shared journey fact complete_journey_count has a duplicate or global key.
- `shared_binding_key`: Shared journey fact benchmark_status has a duplicate or global key.
- `claim_scope_mismatch`: Declared assertion does not have the exact supported scope.

| Acquisition profile | Ranked journeys | Results | Saved answer |
| --- | ---: | --- | --- |
| compact | 0 | delivered / clean | [Answer](early-2027/runs/typo_recognizable_date/continuation-1/answer.md) |
| standard | 528 | delivered / annotated | [Answer](early-2027/runs/typo_recognizable_date/continuation-3/answer.md) |
| invalid: compact reused under standard label | 0 | delivered / clean | [Answer](early-2027/runs/typo_recognizable_date/continuation-2/answer.md) |

## mixed_award_cash_eligible

> Find one award and cash flight from SFO to BKK on January 15, 2027.

[Original intent and complete stage traces](early-2027/runs/mixed_award_cash_eligible/summary.json) · [Final stage summary](early-2027/runs/mixed_award_cash_eligible/continuation-3/summary.json) · [Answer](early-2027/runs/mixed_award_cash_eligible/continuation-3/answer.md) · [Ranking dispositions](early-2027/runs/mixed_award_cash_eligible/continuation-3/matched.json) · [Results checks and claims](early-2027/runs/mixed_award_cash_eligible/continuation-3/results-artifact.json)

Stages: intent 4.8s; clarification 2.0s; clarification_answer 4.2s; planning 81.1s; providers 78.1s; ranking 1.7s; results 172.7s.

Acquisition retained 261 normalized observations; 8 award requests including 2 detail calls, and 3 cash requests. Ranking dispositions: 26 admitted, 232 conditional, 360 rejected. Results selected 3 journeys.

The original request needed clarification. A separately recorded fixture-derived answer enabled this continuation; it is not a first-pass success.

| Acquisition profile | Ranked journeys | Results | Saved answer |
| --- | ---: | --- | --- |
| compact | 0 | delivered / clean | [Answer](early-2027/runs/mixed_award_cash_eligible/continuation-1/answer.md) |
| standard | 618 | delivered / clean | [Answer](early-2027/runs/mixed_award_cash_eligible/continuation-3/answer.md) |
| invalid: compact reused under standard label | 0 | delivered / annotated | [Answer](early-2027/runs/mixed_award_cash_eligible/continuation-2/answer.md) |

## default_award_home_airport_not_return

> Find one business-class seat from my home airport SFO to BKK on February 10, 2027.

[Original intent and complete stage traces](early-2027/runs/default_award_home_airport_not_return/summary.json) · [Final stage summary](early-2027/runs/default_award_home_airport_not_return/summary.json) · [Answer](early-2027/runs/default_award_home_airport_not_return/answer.md) · [Ranking dispositions](early-2027/runs/default_award_home_airport_not_return/matched.json) · [Results checks and claims](early-2027/runs/default_award_home_airport_not_return/results-artifact.json)

Stages: intent 3.2s; clarification 0.0s; planning 67.8s; providers 60.8s; ranking 0.1s; results 64.7s.

Acquisition retained 33 normalized observations; 5 award requests including 2 detail calls, and 1 cash requests. Ranking dispositions: 0 admitted, 0 conditional, 0 rejected. Results selected 0 journeys.

Replay verification: all saved source projections match. A retained annotated compact comparison has a cross-process finding-order replay defect: incomplete-observation findings iterate a Python set. Its finding content is unchanged, but exact replay is not reliable. See [hash-seed probes](replay-order-probe.json) and machine verification records; runtime code and saved receipts remain unchanged.

See [machine report](report.json), [per-call usage and cost](early-2027/usage-summary.json), [pricing basis](pricing-basis.json) and [metric definitions](metrics-notes.md). Earlier development attempts remain separately indexed in [original usage](usage-summary.json), including context-limit failures, initial intent misses and runner/network failures.
