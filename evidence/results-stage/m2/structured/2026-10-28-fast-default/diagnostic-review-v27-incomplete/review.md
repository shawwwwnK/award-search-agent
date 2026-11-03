# Controlled correction diagnostic source review

Rubric: `fast-default-M2-v1.2-calibrated`. This is the final delivered answer after an injected mechanical fault and one correction. It is **controlled diagnostic evidence**, not a natural confirmation draw or evidence of natural failure frequency.

| Dimension | Judgment | Source basis |
| --- | --- | --- |
| H, hard factual | Pass | The selected observations and cash baseline match the stated identities, quantities, roles, and limits. |
| U, useful next action | Pass | With no complete journey in the source, the answer conditionally recommends a specific lead to verify and explains why booking cannot yet be confirmed. |
| M2, composition | Pass | The opening recommendation, embedded lead references, bounded alternatives, separate cash baseline, and final limitations form a coherent traveler answer. |
| C, comparative depth | Decision-rich | The displayed Alaska leads establish a real economy versus premium economy/points tradeoff; the United lead adds a different date and program with a lower raw tax quote, subject to unknown scope. |

## Source checks

- `document.json.selection` identifies no journeys, three incomplete award observations, and one benchmark. `evidence.json.journeys` is empty. The award records in `evidence.json.source.view.components` are `award_summary` entries with only departure dates, no schedule instants or reported legs, and absent returned-traveler counts. `requested_travelers` is one; observed seat counts are distinct from confirmed traveler support.
- Alaska economy reference **A3** (`0c1f9d…`): January 1, SFO–BKK, 42,500 Alaska miles, 5,090 USD minor units in reported award taxes (USD 50.90), eight observed seats, AS/JX carrier list, unknown price scope. United economy **A26** (`a8dad3…`): January 9, 55,000 United miles, 1,620 USD minor units (USD 16.20), nine seats, B6/BR/CA/ET/SQ/UA/ZH carrier list, unknown scope. Alaska premium economy **A37** (`42cf9b…`): January 12, 140,000 Alaska miles, 5,090 USD minor units (USD 50.90), nine seats, JX carrier list, unknown scope. The 140,000 minus 42,500 comparison is 97,500 miles. The award cabin is a summary field; none supplies a cabin by reported leg.
- Cash reference **C1** (`456ce0…`) is a `cash_itinerary`, not an award recommendation. Its route is SFO–HKG–BKK with one reported stop; it has a USD 640 quoted fare with unknown scope and one returned traveler. Its offset-aware departure is January 1, 2027 at 22:55 -08:00 and arrival January 4 at 10:35 +07:00. The source duration is 2,680 minutes, or 44 hours 40 minutes. The answer does not treat its returned-traveler count as price scope or compare its fare with award taxes as a trip total.
- `evidence.json.source.view.provider_status` is `partial`. In `coverage_groups`, 93 detail queries were omitted for resource budget, and related logical queries were partial from a pagination budget. The answer states the result coverage is partial and calls for current booking checks.

The January 1 recommendation is expressly conditional on economy and interest in Alaska miles, and its lower-point claim applies only to the **two shown Alaska leads**. January 9's date or program fit is a conditional possibility, not evidence that the traveler prefers it; the raw USD 16.20 versus USD 50.90 quote comparison is correctly constrained by unknown scope. The January 12 lead gives a distinct cabin benefit at a clearly stated same-program points cost. That actual argument supports C without assuming a global best choice or requiring a particular option count. The source contains more leads, so the sparse-source exception does not apply.

No hard factual failures found. Residual uncertainty is intrinsic to the source: exact award flights, leg cabins, booking availability, traveler support, and final fee totals remain unverified. No escalation is recommended for this source judgment; any dispute over whether the conditional date/program fit is sufficiently useful belongs in rubric adjudication.
