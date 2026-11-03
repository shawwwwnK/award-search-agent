# Results M2 offline comparison prototype

**Superseded proposal, 2026-10-29:** Owner chose Luna wording, rejected inline
comparison binding, required Ranking categories and a one-sentence cash benchmark.
The pending questions below are historical; C/D are withdrawn, not answered.
See the [current handover](../handoffs/2026-10-29-results-m2-fast-profile-handover.md).

2026-10-28. The owner asked to execute the advisor's proposed next step and bring
proper product questions. Scope is a zero-model-call, reviewable prototype and
calibration package. The prior V30 campaign remains stopped.

## Work produced

[Review prototype](../../evidence/results-stage/m2/design/2026-10-28-comparison-prototype/review.html)
contains four saved situations and eight complete hand-authored answer variants.
Pairs preserve the same selected records, source facts and recommendation. Only
the expression of selected comparisons changes. Neither column is presented as
live Luna output or compared unfairly against the original failed answer.

A/q108 compares arrival and elapsed time; B/q110 separates points and fee endpoints;
C/q095 retains a weak pool; D/q106 presents a conditional date/points choice. A/B
keep historical three-option pools as stress cases, without changing current V30's
cap or claiming incremental value for that current profile. CaseC's additional
Jan2 United lead is verified in its own q095 source but excluded from the paired
pool, so binding cannot disguise a selection improvement.

An investigator extracted10selected canonical records across14case-reference slots,
plus1nonselected context record, with21source hashes and pointers. Artifact-local
stdlib code rendered9clauses and checked20synthetic controls plus2saved-source
rejections. Known undetected whole-answer counterexamples remain visible: false
opening, mixed-comparator connective, unsupported schedule benefit and conditional
usefulness judgment. This is limited clause validation, not a semantic checker.

An independent architect found no material factual errors. Two P3 presentation
corrections were applied: rename the current A example to its actual arrival/
duration choice, and avoid calling differently dated leads globally dominated.
Repeated endpoint names and scope qualifications remain visible as a real wording
tradeoff for owner review.

## Verification performed

- Source hashes/pointers, selected pools, native fee units, dates, party/seat states
  and exact deltas checked. 21source hashes reverified by parent.
- `check_prototype.py`:9clauses,20synthetic+2saved controls pass.
- `build_review.py`:8complete variants, correct selected-card sets and all inserted
  clause endpoints visible in the corresponding case.
- `node .../ui-smoke.cjs`:12case/mode renders, resolved clauses, selected cards,
  context separation and failure-tab events pass using a DOM stub. This is not
  browser layout or visual QA.
- Local HTTP serving tested200 on127.0.0.1:8767. Initial sandbox bind/private-network
  checks were blocked; the approved localhost-server/curl escalation succeeded.
- All61preexisting Python files pinned in the earlier WIP review remain byte-identical.
  Product source, tests, configuration, dependencies, old artifacts and grades were
  not changed. `git diff --check` passes.

No model, provider or FX calls. No model-generated fluency, semantic reliability,
latency or M2 qualification claim. The old strict verifier's four assumption defects
remain unchanged and separate from these prototype checks.

## Product decisions pending

Questions presented with the complete examples ask whether to trial shared factual
wording ownership(A/B), revisit weak selection(C), and credit a conditional date
choice without inventing a preferred day(D). Current October25 prose policy stays
in force until explicit disposition; a trial decision would not adopt a default.
Historical grades are not retroactively changed by calibration.

ADR disposition: ADR0029 adds an explicitly proposed/not-adopted offline wording
section; no accepted stage ownership or product contract changes. Owner answers,
interpretation and subsequent implementation/live-campaign direction remain pending.
