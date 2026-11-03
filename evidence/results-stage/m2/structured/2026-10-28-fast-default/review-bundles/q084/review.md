# Blind review: q084

- Rubric: `fast-default-M2-v1.2-calibrated`
- H: **fail**
- U: **pass**
- M2: **fail**
- C: **basic**; sparse-source exception: **no**

## Hard factual findings

1. > “This is the earlier-arriving of the two shown business options, but its points quote is 165,000 higher than the later business option.”

   `evidence.json` journeys `0286e918614a7b41ec9aa8f5d5ec9042bf1bd5234d22fba3e9d968b1511b0bee` and `018b54daf2f1619248319c7f13f9107aba62b5deee4200e1d9f54f45759e8153` each have `award_points.value = 275000`; their difference is zero. The displayed economy journey has 110,000 points, which yields the stated 165,000 difference against the wrong comparator.

2. > “Compared with the recommended choice, it leaves 3 hours 11 minutes later and arrives 4 hours 35 minutes later; its elapsed time is 84 minutes shorter.”

   Journey `010ec2caa13dc729a813d55f4e5761340e533c25779d178524fe0bd6af2e6669` has `elapsed_minutes = 1803` versus `1719` for recommended journey `0286e918614a7b41ec9aa8f5d5ec9042bf1bd5234d22fba3e9d968b1511b0bee`. Economy is **84 minutes longer**, as the following comparison block correctly says.

3. > “For a later arrival in the same reported award cabin as the recommendation, the other business option uses the same 275,000 Turkish Airlines Miles&Smiles points quote and reports an earlier SFO departure and a longer Istanbul wait.”

   Journey `018b54daf2f1619248319c7f13f9107aba62b5deee4200e1d9f54f45759e8153` has `departure.local_iso = 2027-01-08T08:40:00-08:00`, four minutes **later** than the recommendation at `2027-01-08T08:36:00-08:00`. Its points and Istanbul wait clauses are correct; the departure direction is not.

4. > “It has an earlier Bangkok arrival, but takes longer overall than the recommended option.”

   The same two journeys have `arrival.local_iso = 2027-01-10T08:50:00+07:00` and `2027-01-10T04:15:00+07:00`, respectively. The other business journey arrives **four hours 35 minutes later**. Its `elapsed_minutes = 1990` versus `1719`, so the duration clause is correct.

## Other judgments

The selected business journey still provides a defensible exact next action for an early-arrival preference, with award seats, taxes and separate-ticket protection unverified. The displayed economy option offers a genuine cabin and 165,000-point tradeoff against that recommendation. This supports U. The answer has the formal components of M2, but its other-business explanation invents a points penalty and an earlier arrival and departure, so its comparison is materially unsupported and M2 fails. C is **basic**: some local gains and losses survive, but the false claims prevent a reliable understanding of each meaningful displayed option. The answer explicitly treats the displayed set as selected examples, so no global-optimum claim or coverage quota is inferred.

The separate one-stop EVA Air SFO–TPE–BKK cash benchmark matches `evidence.json` component `5436f6892bc314630a4d33086ede20fd08197aa93b8dfbbf21f0fa8bbeaf07ed`: `stops = 1`, USD 605 quote, unknown price scope. Positioning cash quotes also have unknown scope; no all-in total is established. Checked selected journey `departure`, `arrival`, `elapsed_minutes`, `award_program`, `award_cabin`, `award_points`, `money`, `connections`, and selected cash components. No live calls were made.

Uncertainty: no material source ambiguity remains for the four failed comparisons. Escalation is not needed for the source judgment; the parent can adjudicate the independent rubric dimensions.
