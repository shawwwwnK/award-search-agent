# q034 blind source and composition review

Rubric: `fast-default-M2-v1.1-scope`.

| Dimension | Judgment | Basis |
| --- | --- | --- |
| H, hard factual | Pass | The selected award observations, cash benchmark, timing, scope warnings, and partial coverage match the canonical evidence. |
| U, useful next action | Pass | With no complete selectable award journey, the answer gives a specific partial lead to check and explains its limits. |
| M2, connected composition | Pass | The answer connects a lead, two alternatives, a separate cash baseline, and consolidated limitations in traveler prose around the references. |
| C, comparative depth | Basic | It compares the displayed leads, but the first-choice rationale is narrow and omits a closely comparable United lead in the same requested month. This is a coverage/depth concern, not an established hard factual contradiction. |

## Source checks

- `evidence.json` `source.view.request` asks for one SFO–BKK award seat in January 2027, with no cabin preference; `source.view.provider_status` is `partial`; `journeys` is empty and `source.view.match_accounting.admitted` and `.conditional` are both zero. The opening's no-complete-journey and partial-coverage statements are supported. `references.json` `journeys` is also empty.
- `document.json` `selection.incomplete_observation_ids` selects the three displayed leads. In `evidence.json` `components[observation_id=a8dad377…]`, United/economy, January 9, 55,000 miles, USD 16.20 fees, and 9 observed seats match the answer. `components[observation_id=cc7d8d9e…]` supports January 1 United/economy, 60,500 miles, USD 28.20 fees, and 9 seats. `components[observation_id=0c1f9d64…]` supports January 1 Alaska/economy, 42,500 miles, USD 50.90 fees, and 8 seats. All three have `price_scope=unknown`, no departure/arrival instant, and `legs[0].reported=false`. The USD 16.20 fee is lowest **among these three**, exactly as scoped in the answer. The answer does not equate observed seats with the one requested traveler or claim a leg-by-leg cabin.
- `evidence.json` `components[observation_id=456ce00d…]` is a `cash_itinerary`, not an award lead. Its Cathay Pacific carrier, SFO–HKG–BKK airport sequence, one stop, USD 640 cash amount, `price_scope=unknown`, and `returned_travelers.value=1` support the cash paragraph. The departure `2027-01-01T22:55:00-08:00` and arrival `2027-01-04T10:35:00+07:00` are 44 hours 40 minutes apart, matching `duration_minutes.value=2680`. `document.json` places it in `selection.benchmark_observation_id`.
- `evidence.json` `availability_guidance` says some results are not real-time and advises official-site confirmation; the closing limitation is supported.

## Comparative depth and uncertainty

The sentence “The most useful lead to check first is the United economy result for January 9” gives a plausible provisional action, and its fee claim explicitly says “among these three leads.” The full source, however, also contains `evidence.json` `components[observation_id=963e988d…]`: a January 13 SFO–BKK United economy summary for **50,600 miles**, **USD 16.20 fees**, and **9 seats**, with the same unknown price scope and missing schedule. It falls in the requested January window (`source.view.request.departure_window`). The answer does not explain why January 9 should precede that lower-mile same-program lead. Different dates and unknown itineraries prevent declaring one objectively best, so this is a C-depth/selection uncertainty rather than an H failure. `references.json` `awards` includes that observation, confirming it is within the canonical reference inventory.

The cash paragraph states a separate baseline accurately, but gives little decision context for its long 44-hour-40-minute journey. For example, `evidence.json` `components[observation_id=29289b6c…]` has a USD 686, 32-hour-10-minute one-stop cash benchmark, also with unknown quote scope. This additional benchmark is not required for H or M2; it is further evidence that a richer cash tradeoff was available. No award-versus-cash value winner can be inferred from these unknown quote scopes and program-specific miles.

No live calls were made. I inspected only this bundle and its parent `reviewer-instructions.md`. Escalation is not needed for source tracing; adjudication may consider whether the first-choice wording overstates the narrow displayed comparison.
