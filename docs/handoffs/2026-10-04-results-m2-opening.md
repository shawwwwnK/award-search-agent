# Results M2 opening and Ranking closeout

**Current status, 2026-10-08:** Results M2 is [owner-closed](2026-10-08-results-m2-closeout.md) for its declared implemented boundary; M3 remains planned. This supersedes earlier open/unimplemented/pending-closeout status in this document, while preserving historical evidence and policy limits.

**Current M2 policy, 2026-10-07:** use the [consolidated validation/recovery/delivery contract](2026-10-07-results-m2-validation-and-delivery-contract.md)
and [ADR 0026's dated amendments](../adr/0026-model-authored-results-with-bound-facts.md).
These supersede earlier terminal validation gates, hard five-choice and two-per-group caps,
no-repair/single-call proposals and prohibition on attached failure disclosures below.
The LLM owns answer layout; selected checks are non-blocking. Use at most two authoring calls,
retain the recoverable draft with fewer material failures (correction wins ties), and attach
traveler-facing notices/source-backed omitted disclosures. Unchecked/insufficient evidence
remain distinct. Schema output with no recoverable document is a system/generation failure.
Results remains unimplemented; measurement-dependent settings and live budgets remain future work.

Decision records: [ADR 0026](../adr/0026-model-authored-results-with-bound-facts.md), [ADR 0027](../adr/0027-ranking-owned-solution-export-and-upstream-trust.md).

Date: 2026-10-04. Status: **Ranking owner-closed including its M2 factual export; Results M2 owner-opened, unimplemented**.

## Owner disposition

After reviewing the expanded Ranking boundary and its preservation behavior, the owner instructed:
“Ok, now mark ranking closed and open the milestone we'd do next for results stage. Then commit
and push”. Ranking is closed for its declared matching, solution-style and factual-export scope.
Results M2 — model-authored answer with bound facts — is the active next milestone. Results M3
evaluation remains planned; the former Results M1 is absorbed into Ranking's export and Results
authoring preparation.

## M2 input and deliverable

Consume Ranking's `SolutionView` directly, keeping its `ProjectionReceipt` internally. Trust
upstream decisions and preserve all candidates/source facts. No equivalent Results-owned factual
projection is required. Results chooses presentation groups/handles, defines coherent factual
slots and visible disclosures, and implements `ResultsDocument -> ResultsArtifact`.

The LLM controls headings, order, grouping, prose, tables and emphasis. Code resolves scoped facts,
substitutes them and checks final visible content. Conditional requirements, separate-booking
obligations, price scope, missing costs, cabin limitations and coverage must stay associated with
the selected journey. Cash remains a separate benchmark; rejected records cannot become selections.

## First slice and remaining choices

Start with M2.1 offline authoring preparation and rendering: display groups/handles, slot catalog,
activated disclosure obligations, strict selection/scoped-parts contract, substitution and final
Markdown visibility checks. Exercise both prose and table layouts using hand-authored documents.
Measure complete authoring input/schema size without silently dropping alternatives.

M2.2 adds the narrow writer adapter, explicit failures and saved-document replay; M2.3 supplies
the bounded actual-authoring diagnostic after dependent choices and numerical budgets are settled.
Recovery/delivery policy is settled in the October 7 contract; writer settings and live-call
limits remain dependent M2 decisions after input measurement. Judge settings and
calibration belong to M3. Opening M2 is not a claim of implementation, authorization for an
unspecified live evaluation, or a reopening of upstream policies.

## Evidence and limits carried forward

Ranking's final implementation gate passed 28 export tests and 62 existing Ranking tests, scoped
lint/type checks and three exact saved-export replays. All 992 candidates/427 eligible alternatives
are retained; the original sources remain unchanged. Unknown cost scope and partial coverage remain
visible. Model-context fit, cross-host timezone regeneration, live bookability/provider reliability
and complete traveler-task benefit remain unqualified.

Sources: [Ranking export](2026-10-04-ranking-m2-solution-export.md),
[Ranking closeout](2026-10-02-ranking-stage-closeout.md),
[Results milestones](2026-10-02-results-stage-milestones.md),
[authored-document contract](2026-10-03-results-stage-authored-template.md),
[execution plan](2026-10-02-results-stage-implementation-plan.md).
