# Results Stage detailed execution planning

Date: 2026-10-02. Scope: orchestrated read-only investigation, temporary cleanup prototype,
architecture design/review, and planning documentation. No Results runtime implementation.

## Request and work

The owner requested more detailed planning before implementation and explicitly requested
orchestrated investigation and architecture work. Retain the previously accepted LLM/editorial
versus code/data boundary, variant/group rules, five-journey limit, clear programs without public
citations, cleanup before any size mechanism, and an additional LLM evaluation milestone.

Three investigators handled M1 identity/cleanup, M2 adapter/rendering/error, and M3 evaluation.
An architect coordinated findings and reviewed the parent-integrated plan. No agents edited
repository files or delegated further. M1 wrote only an exploratory script and JSON outputs
under `/private/tmp`; no model or provider calls were made.

Parent created the [detailed execution plan](../handoffs/2026-10-02-results-stage-implementation-plan.md),
linked it from the existing design/milestone documents and project state, and updated the
existing Results disposition in the deferred register. Existing unrelated changes were preserved.

## Objective evidence

- The plan separates the compact brief, internal candidate/evidence accounting, editorial
  response, and final rendered answer. Explicit comparisons are code-bound facts; arbitrary
  prose still needs semantic review.
- No eligible award/cash pair repeats within the saved cases; same-observation consolidation
  removes none. Factoring common components and reason sets gives the observed reduction.
- Original versus incomplete factored-probe JSON bytes: mixed access 6,513,717 / 206,775;
  exact business 4,866,650 / 98,469; positioning 2,106,611 / 62,050. Eligible variants are
  257/106/64; award groups 23/3/4; used cash observations 48/42/28. Useful incomplete/rejected
  detail, full coverage explanation, and an internal map are absent. Sizes are exploratory
  lower bounds, not a sufficient brief or model context-fit measurement.
- Actual same-award Aeroplan cash variants quote USD 196 / 29h50 / 6h20 wait and USD 290 /
  27h30 / 3h50 wait, with unknown scope/cash cabin. These anchor a planned non-splicing test.
- Seats.aero raw local strings can end in `Z` while representing wall time; the parser strips
  the suffix before airport timezone interpretation. SFO Oct 5 23:45 local / Oct 6 06:45 UTC
  is an explicit planned rendering regression.
- Program does not establish operating airline; minor-unit conversion does not establish price
  scope. Existing structured adapters and traces are reusable patterns, not Results code.
- Local SDK inspection found two default transport retries. Application invocations, HTTP
  attempts, and deadlines therefore need explicit configuration/accounting.
- Proposed diagnostic workload: twelve cases × three writer trials = 36 answers; those 36
  judge evaluations plus eleven initial calibration answers = 47 judge evaluations, or 83
  proposed application invocations before retries. This is not measured usage/cost.

## Checks and review

Investigation used `rg`, `sed`/`nl`, saved-JSON Python inspection, and local SDK signature
inspection. Sources included ranking/provider contracts, matching/style derivation, Seats.aero
parsing, clarification's structured adapter, `LLMCallTraceCollector`, immutable CLI output,
existing evaluation protocols, saved M2 cases, deferred entries, and relevant workbook sections.

Temporary measurement script: `/private/tmp/results_m1_probe.py`; outputs:
`/private/tmp/results-probe-*.json`. These are not required implementation artifacts; no
clean-checkout reproduction of the exploratory script is claimed.

Architect review requested two corrections, both applied: initial consolidation is
same-observation-only, and limited fallback discloses the larger complete pool. The remaining
plan was approved for design discussion. No escalation was recommended. No runtime tests or
live evaluations ran for this documentation-only change; earlier corpus verification was not
repeated or reported as newly executed.

Final documentation checks passed: `git diff --check`, plus relative-link and trailing-whitespace
checks on the detailed plan, milestone/design documents, and this build log. No failures remained
in those scoped checks.

## Remaining choices and claims

M1 implementation must finish sufficient schema/examples, reason mapping, and complete input
measurement. M2 must settle failure breadth and explicit attempt/deadline settings. M3 must
calibrate its judge and obtain fresh labels after tuning before broader accuracy claims.

Owner interpretation or changes to these new proposals: **not yet supplied**.

Owner-approved implementation start / next cut: **not yet supplied**. Proposed first slice is
M1.1 contracts and exact joins. No input cap, repair loop, runtime judge, upstream policy change,
new deferred feature, implementation, or qualification was adopted.
