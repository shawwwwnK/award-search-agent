# Results/frontend design interview — deferral record

Date: 2026-10-23. The owner confirmed shared understanding and requested further
investigation, documentation updates and a complete plan. This is documentation
and planning only; no runtime implementation.

The owner answered Q6 with: "Yes. Put C in the DEFERRED.md". Q6-C meant
conversational changes to preferences or constraints followed by another search.
The recommended first frontend slice was browsing, filtering, sorting, expanding
and comparing existing results, plus follow-up questions about existing evidence.

Updated existing entry D01 in `DEFERRED.md` rather than creating a duplicate
post-ready-editing entry. Added the explicit deferred scope, revisit trigger,
required completion evidence and dated disposition. User-initiated re-search is
distinct from D09 autonomous result-responsive control. Persistence and deployment
remain separately deferred under D10/D11.

Initial deferral-only verification: inspected that documentation diff and ran
`git diff --check`. No ADR amendment was needed at that point because the broader
interview remained open and no runtime authority had changed.

## Confirmed owner decisions

| Interview | Accepted direction |
| --- | --- |
| Q1–Q3 | Help travelers choose what to verify, with accessible exploration. Preserve existing Ranking/Results highlight policy; consistent factual displays coexist with flexible agent explanation. |
| Q4–Q7 | Group related award options, retain all eligible variants, and place results in a dedicated workspace alongside conversation. Use existing evidence for a compact search explanation. Initial follow-ups explain existing results; re-search remains D01. |
| Q8/Q12 | Refine compact/expanded flight displays using structured fields. Show actual connection airports and waits rather than a generic stops field. USD is the primary monetary display. |
| Q9/Q13/Q14 | Unified options without admitted/conditional labels or requirement checklists. Use shared official-site availability/current-price guidance, retaining material booking/pricing facts, unknowns and separate bookings. |
| Q10/Q11/Q16 | Separate potential leads when no complete journey qualifies. Give retained evidence to the agent for questions/comparisons; do not build separate coverage/QA systems or search again in follow-ups. Primary presentation acceptance concerns readability, highlight rationale and finding alternatives. |
| Q15/Q22 | Converted USD values are approximate, with original currency, scope, rate and timestamp in details. One dated snapshot is shared by Ranking/display per run; saved runs retain theirs. |
| Q17/Q18 | Explorer completeness is independent of agent selections. Default groups use their shortest complete surviving variant; supported explicit sorts preserve incomparable/missing values. |
| Q19/Q20 | Explain meaningful alternatives, including a notable unselected tradeoff when relevant. Distinguish payable cash, program-specific points and existing heuristic comparison cost. |
| Q21/Q23 | Frontend is primary; inspect the same structured data as text/JSON rather than authoring a second Markdown answer. The model selects exact references; code resolves facts. Pydantic is an example, not a chosen implementation requirement. |

The owner confirmed the consolidated design before authorizing this planning work.
These are owner decisions, not inferences from tests. Exact schema/tooling, model
settings and FX vendor remain implementation choices.

## Further investigation

Two investigator agents traced Results contracts/checkers/adapter/replay/FX and the
workspace/harness/follow-up boundaries. An architect reviewed their evidence and
the migration strategy. The parent integrated findings and authored the docs;
additional repository investigations stayed with subagents at the owner's request.

Material findings:

- Current V1–V5 Markdown checkers require visible statuses/requirements and many
  prose slots; the accepted new channel needs explicit versioned contracts and
  disclosure supersession rather than globally relaxing historical checks.
- Ranking's full projection already preserves the eligible candidates and source
  facts. Harness Ranking output precedes authoring and survives its failure.
- There is no React/HTTP frontend or post-Results conversation path today. The
  plan names them as additions, not existing capabilities.
- `transfer_minutes` covers the cash/award boundary. Other connection waits need
  compatible adjacent UTC instants and matching airports; local strings alone do
  not establish a wait.
- Raw observed money must be converted separately from heuristic costs. Existing
  minor-unit support is USD/CAD; unknown quote scope cannot become a total.
- The existing FX snapshot contract can represent a USD-only identity snapshot.
  A new-run rate outage can be explicit while non-USD display stays in original
  currency and Ranking preserves incomplete-cost treatment.
- Retaining a projection does not establish that an arbitrary follow-up fits a
  model request. Reuse compact evidence, measure context and expose fit limits.

Research used read-only `rg`, `sed`, `cat` and bounded code/contract inspection.
No runtime tests or live model/travel-provider/FX calls were made. Official React
build-tool guidance was consulted only to ground the need for a local application
seam; no frontend dependency/version or FX vendor was adopted.

## Documentation delivered

- Current contract and seven-unit plan:
  `docs/plans/2026-10-23-2334-feat-results-workspace-plan.md`.
- New accepted ADR 0029, with a scoped successor notice in ADR 0026 and links in
  the ADR index and ADR 0028. ADRs 0024/0025/0027 retain their existing policies.
- Current-state pointers in `docs/project-state.md` and `AGENTS.md`, active-core
  disposition in `DEFERRED.md`, and domain terms in `GLOSSARY.md`.
- Supersession notices in the older Results design/milestone/template/spec/delivery
  documents and API guide; their dated bodies and implemented CLI instructions remain.

## Plan document review

The non-interactive document review used six separate native reviewer contexts:
coherence, feasibility, design, scope, product and adversarial. There were no
reviewer failures. No cross-provider CLI pass was run; this session did not
authorize external model calls. Native role review is not cross-provider validation.

| Finding | Disposition and basis |
| --- | --- |
| Design: authoring-pending state absent from lifecycle table | Applied. The plan already publishes Ranking evidence before authoring completes; distinguish pending from absent/failed and prevent a duplicate in-flight authoring invocation. Added a lifecycle row and U5 verification scenario under existing explicit-event authority. |
| Design: exact filter dimensions unspecified | Not retained as a defect. R4/R5 and U4 already define available facts, exact-variant filtering and representative behavior. Exact controls were reserved for implementation; prescribing dimensions now would add a UI decision without evidence that a competent implementer cannot choose them. |
| Scope: remove new FX acquisition adapter | Rejected. The owner agreed to obtaining a dated snapshot for each new run and explicitly discussed API conversion. A bounded acquisition adapter with supplied offline snapshots implements that accepted behavior; removing it would narrow the agreed path. No retries, background refresh or vendor framework is planned. |

Resolved review state: one implementation/lifecycle correction applied; no proposed
fixes, owner decisions, FYI findings or launch-blocking product questions remain.
Reviewers' claims were checked against the whole plan and confirmed interview.
The original review findings and their dispositions remain recorded here rather
than resurfacing dismissed claims as future tasks.

## Verification and limits

Documentation checks cover relative link targets, requirement/unit/acceptance
references, duplicate IDs, expected plan sections, Markdown fences and whitespace.
Commands and results:

- `git diff --check` — exit 0, no whitespace findings.
- `git diff --stat` / `git status --short` — fourteen tracked documentation/instruction
  files changed, plus the new plan, ADR 0029 and this session log. No runtime files
  changed; pre-existing untracked end-to-end evidence was left untouched.
- `python3 /private/tmp/results-frontend-plan-d4aczmp3/check_docs.py` — exit 0;
  33 relative links resolve, seven required plan sections exist, R1–R11/U1–U7/
  AE1–AE6/KTD1–KTD6 definitions are unique and references valid, Markdown fences
  and portable plan paths pass. The check also reruns `git diff --check`.
- A worker independently audited scope/links/IDs and identified the missing
  verification-command record, which this section now supplies.

Research dispatches/dossiers and the resolved review record remain in the session's
private temporary directory for inspection; they are not product artifacts or
implementation files.

No runtime suite is run for this documentation-only change. Existing replay-order, model-context,
live-quality and task-benefit limits are not closed by planning.

ADR disposition: ADR 0029 added; ADR 0026 amended with precise new-channel
supersession; ADR 0028 and index linked. No Ranking valuation/eligibility or upstream
trust decision changed. Implementation, new runtime verification, live diagnostics,
owner presentation acceptance and M3 qualification remain unclaimed.

## Milestone allocation and requested publication

The owner accepted the proposed stage map and instructed updating the docs:
Results M2 revision U1–U3; Frontend M1 U4; Frontend M2 U5–U6; Results M3 evaluation
and acceptance, with U7 supplying integrated review evidence. M3 preparation may
begin during M2, but final rendered assessment follows frontend integration.
Results retains follow-up evidence/answer-policy ownership. U7 is not the entire
M3 evaluator/calibration/qualification contract; M3's actual scope/cohort/budget
must be reconciled at opening rather than importing old proposed call counts.

A read-only investigator checked current plan/stage/ADR/state/deferred documents
and identified that qualification boundary. The parent updated the plan, current
milestone and execution-plan notices, ADR 0029/index, project state, AGENTS and the
deferred register. No additional product question or runtime change was needed.
ADR disposition: amended ADR 0029 to record accepted sequencing and stage ownership;
no new ADR or upstream policy change was needed.

The owner also explicitly requested committing and pushing after documentation
verification. That authorization covers this session's design/planning/stage docs;
pre-existing untracked end-to-end diagnostic evidence is excluded. Publication
outcome is reported from actual git command results, not assumed here.

Stage-update verification: `python3 /private/tmp/results-frontend-plan-d4aczmp3/check_docs.py`
passed with 38 relative links and all existing R/U/AE/KTD identifiers valid;
`git diff --check` passed. A separate read-only worker confirmed the stage/ownership
map and checked 380 relative links, including heading fragments, across its broader
documentation scan, with no missing target/heading. No runtime tests were run.
`git fetch origin main` succeeded and `git rev-list --left-right --count HEAD...origin/main`
reported `0 0` before staging. Only the 17 session documentation files are selected
for the requested commit; existing untracked diagnostic material remains separate.
