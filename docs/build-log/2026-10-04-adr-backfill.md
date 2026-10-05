# 2026-10-04: ADR backfill and decision-record workflow

## Scope and owner instruction

The owner requested backfilling recent consequential decisions and examining repository guidance
to prevent further ADR drift. This session changes documentation only. Results M2 remains open
and unimplemented; no upstream stage, runtime policy or qualification is changed.

## Findings and changes

The ADR README already defined consequential-decision criteria, but `AGENTS.md` only required
reading relevant ADRs. Neither the build-log guide nor session template required an ADR disposition.
Recent decisions were documented in handoffs/contracts and project state without corresponding
ADRs. ADR 0023 was also missing from the index.

Created [ADR 0024](../adr/0024-deterministic-award-led-journey-matching.md) for M1 matching and
evidence policy, [ADR 0025](../adr/0025-deterministic-overlapping-solution-styles.md) for M2 styles,
[ADR 0026](../adr/0026-model-authored-results-with-bound-facts.md) for Results authorship, and
[ADR 0027](../adr/0027-ranking-owned-solution-export-and-upstream-trust.md) for export ownership
and same-project trust. Original decision dates and sources are retained; recording is dated today.
Results engineering proposals remain explicitly proposed. Historical verification is attributed to
its original sessions, not presented as fresh results.

Updated `AGENTS.md`, the ADR index/workflow, build-log guide/template, project state and five
relevant handoffs. Guidance now requires an ADR check at design opening and before closeout/commit,
same-session recording of accepted consequential changes, explicit status/supersession and source
links, and a build-log ADR disposition. Routine implementation details remain exempt and existing
owner authorization does not require duplicate approval.

Reviewed workbook section 6.1 and Appendix B; they support recording options, evidence, tradeoffs
and revisit triggers. The workbook was not edited. Consulted `DEFERRED.md`; no deferred disposition
changes arise here, so its pre-existing edits and the separate AI evaluation audit log are untouched.

## Verification

Commands: source reads/searches and diff review; `python3 /private/tmp/verify_adr_backfill.py`;
`git diff --check`. The validation checks local Markdown link targets across this session's files,
all 27 ADRs' index coverage, required sections/status/backfill dates in the four new records, and
the proposed-mechanics distinction and closeout guidance. Result: PASS across 15 documents and 148 local links; all 27 ADRs are indexed,
and all four backfills and closeout guidance checks passed. `git diff --check` exited 0.
Runtime tests are not applicable to this documentation-only change; no model/provider calls ran.

## ADR disposition and remaining limits

Added ADRs 0024–0027; restored 0023's index entry. This is a source-backed backfill, not a new
comparative experiment or independently qualified architectural assessment. Prevention is enforced
through repository instructions and the session template, not an automated semantic decision detector.

Owner conclusions recorded: backfill decisions and strengthen guidance, as requested. No additional
product conclusion or next stage change is inferred. The owner subsequently requested committing and pushing this documentation change.
Unrelated deferred-work and AI evaluation-audit changes are excluded from this commit.
