# q025 blind Results M2 review

- **H:** fail
- **U:** pass
- **M2:** pass
- **C:** decision-rich; no sparse-source exception

**Material H failure.** The answer states: “This Jan. 1 SFO–BKK summary reports 9 seats and USD 60,500 points, with USD 28.20 in fees shown.” Canonical `evidence.json` component `cc7d8d9eb93023cfdd2dc89a9db92fe94154a32100978836c3db10ed4c4a8044` has `points.value = 60500` and `money.points_raw.value = 60500` for the United award program. These are **60,500 award points**, with no USD unit. The separate `money.award_taxes` record has `raw_amount.value = 2820`, `raw_currency.value = USD`, and `unit = minor`, giving **USD 28.20**. The answer incorrectly attaches USD to the points quantity.

The other selected award leads are date-only summaries and match the source: Alaska economy reports 8 seats, 42,500 points, and USD 50.90 observed fees; Aeroplan economy reports 2 seats, 65,000 points, and CAD 116.50 observed fees. All quote scopes are unknown, and the award summaries do not contain timed itineraries or returned traveler support. `evidence.json` contains zero assembled journeys.

The separate January 1 SFO-TPE-BKK cash observation `29289b6c9db95327ccdcc1ca2eda4a84c3cdf070c64a81ab5ab8465981720f1d` reports one stop, **1930 minutes (32 hours 10 minutes)**, arrival on January 3, and **USD 686** with unknown price scope. The returned count of one traveler does not make that a per-person quote. Canonical coverage groups show SFO-BKK detail queries omitted for resource budget and partial SFO-TPE/TPE-BKK connection-route results, consistent with the answer's coverage caveat.

The United lead is still a defensible follow-up based on the reported seat count and observed fee quote. The response explains the three date-only choices, keeps cash separate, and consolidates the uncertainties. Its comparative content is decision-rich for this source, while the points-unit error independently fails H. The packet has other date-only summaries; the answer makes no exhaustive-coverage claim.
