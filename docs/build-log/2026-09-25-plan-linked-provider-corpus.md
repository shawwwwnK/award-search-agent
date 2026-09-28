# 2026-09-25: plan-linked Provider Stage corpus refresh

## Objective and owner direction

The owner asked that every reusable saved search result come from an actual Search Planning
Stage plan. They asked for live award and cash searches from such plans, replacing standalone
search pairs, so Ranking M1 has same-plan positioning evidence. This is a local development
artifact refresh; it does not reopen the owner-complete Provider Stage boundary or implement
Ranking M1.

## Plan-to-provider audit

The five retained frozen plans were inspected through the Provider Stage projection. Each has
mandatory endpoint award probes that project corresponding direct endpoint cash queries. Two
plans (`mixed_award_cash_eligible` and `ready_exact_airports`) also have an SFO→LAX access
dependency. That cash query is conditional on a timed LAX-origin award observation. The
remaining three plans have no positioning dependency. The compiler remains provider-neutral;
Provider Stage derives cash work from its graph under ADR 0022. A focused parameterized unit
test now checks the projection across all five frozen inputs.

## Execution and implementation

An initial live mixed execution used both detail calls on mandatory SFO→BKK awards. LAX→BKK
summaries had no timed detail and could not activate SFO→LAX cash. Review also found that
positioning sampling capped award observations before filtering out dates outside the request
window. `src/award_agent/providers/execution.py` now schedules one in-window explicit-access
detail first, then mandatory details, then remaining candidates, while preserving omission
receipts. It filters in-window award observations before the positioning sample cap. The active
development policy version is `provider-development-v4-access-detail-priority`; numeric
request/detail/cash budgets remain unchanged. `tests/unit/test_provider_execution.py` covers
the scheduling, date filter, and five-plan projection.

Two fresh live runs used the frozen mixed-intent and exact-business SFO→BKK October 5, 2026
plans, Seats.aero, and the reviewed pinned gfly compatibility launcher. Live mode needed the
catalog **release directory** and network execution outside the default sandbox. Failed setup
attempts made no accepted corpus entry. Earlier live outputs under the old scheduling policy
remain diagnostic only in private temporary work files.

| Current run | Observations | Physical calls | Coverage | Status |
| --- | ---: | ---: | ---: | --- |
| `mixed_access` | 212 award summaries, 23 timed awards (six LAX→BKK), four direct cash, 76 SFO→LAX access cash | 13 | 154 units | partial |
| `exact_business` | 41 award summaries, six timed LAX→BKK awards, six direct cash, 66 SFO→LAX access cash | 9 | 55 units | partial |

The runs each made two positioning cash queries after timed access-award evidence. The corpus
contains each frozen planning input, exact provider bundle, acquisition tape, typed result, and
captured runtime bodies. `scripts/provider_plan_corpus.py add/verify` checks plan/request binding,
result attachment, file and evidence hashes, and byte-exact offline CLI replay. The old
standalone results and combined execution were removed from the active saved-search corpus.
Parser-only captures needed for regression tests moved to `tests/fixtures/providers/`.

Current evidence lives in [the corpus](../../evidence/provider-stage/saved-searches/README.md)
and its [index](../../evidence/provider-stage/saved-searches/index.json). Its two embedded
capability/policy snapshots are retained for replay. The active capability file now references
evidence hashes from the retained live runs and the new policy version.

## Verification and claim boundary

The two saved results were replayed byte-for-byte during packaging. After installation,
`scripts/provider_plan_corpus.py verify` passed with two runs and 434 observations, including
exact offline replay of both results. The nine scoped Provider Stage test modules passed
(66 tests). Scoped Ruff, `git diff --check`, and local links in active changed documents passed.
The configured Seats.aero secret does not occur in any of the 36 corpus files.

These results establish same-plan award and cash acquisition with honest partial coverage.
They do not establish a valid combined journey, complete provider coverage, returned traveler
or cabin adequacy, known cash price scope, booking availability, or Ranking M1 behavior.

## Owner interpretation and next cut

The owner explicitly required plan-linked saved results and authorized replacing the prior
standalone collection. Ranking M1 matching and validation remain the next implementation work;
its unresolved design decisions remain in the
[Ranking Stage design record](../handoffs/2026-09-25-ranking-stage-design.md).
