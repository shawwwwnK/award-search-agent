# Results Stage v1 design investigation

Date: 2026-10-02. Scope: design, read-only contract/corpus investigation, saved-evidence
verification, and discussion documentation. No Results runtime implementation or live calls.

## Owner request

The owner supplied a high-level Results Stage design covering evidence cleanup, model-selected
journey highlights, self-contained writing, price/condition preservation, other outcomes,
fallback, input limits, and evaluation. The owner requested orchestration of verification,
investigation, and detailed architecture design to work out the next design version.

## Work and files

- Two investigator tasks independently examined variant/price/condition preservation and
  request/planning/coverage/source context; an architect task developed the writing boundary,
  safeguards, grouping, and evaluation design. No subagent edited repository files.
- Parent integrated findings into
  [the detailed discussion draft](../handoffs/2026-10-02-results-stage-v1-design.md), with
  explicit distinctions between owner-supplied direction and proposed engineering choices.
- Parent linked the draft in [project state](../project-state.md) and the existing core Results
  entry in [DEFERRED.md](../../DEFERRED.md). No new parked feature or prerequisite was adopted.
- This build-log entry records evidence. Existing uncommitted stage-opening changes in
  `AGENTS.md`, `README.md`, `DEFERRED.md`, `docs/project-state.md`, and opening records were
  present before this task and preserved.

## Objective findings

The source chain already retains request, plan, provider observations, matching variants,
M2 features/style assessments, rejection/research material, direct cash, and coverage.
Results needs a compact deterministic join/projection, not additional search planning.
Family identity groups source/support alternatives; it is not semantic flight deduplication.

All 427 eligible candidates across three saved requests lack a complete cost reference due
to unknown price scope. The 992 retained records include query/source duplicates and excluded
records; they are not unique flight counts. Saved cash observations lack confirmed cabin and
detailed leg records; some award-leg cabins are unreported. Supplemental planning rationale
exists; endpoint proposals do not record individual narrative reasons. Traveler-facing coverage
and conditions must be derived from existing receipts and reason codes. Nonblocking price,
booking, and cabin unknowns remain relevant even for admitted journeys.

The draft recommends structured selection/editorial prose with deterministic factual summaries,
strict duplicate cleanup with source aliases, qualified objective comparisons, and explicit
fallback/volume outcomes. These recommendations are not recorded as owner-approved choices.
Mechanical validation cannot establish the truth of arbitrary model prose.

## Commands and verification

Read-only inspection used `git status --short`, `rg`, `sed`, `nl`, and `jq` over contracts,
stage records, the relevant workbook sections, deferred entries, and saved JSON shapes.

The documented verification command passed:

```sh
PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py \
  --fx-snapshot data/ranking/m2/fx-2026-09-29.json \
  --output-dir evidence/ranking-stage/m2/styled --verify
```

Output: `{"output_dir": "evidence/ranking-stage/m2/styled", "cases": 3}`; exit status 0.
This checks the existing saved corpus; it is not a Results-generation test or qualification.
No new behavior tests were needed for documentation-only work. The architect reviewed the
integrated draft and approved it for discussion after distinguishing award grouping from
duplicate consolidation and preserving valid observations from partial searches. Parent
applied both corrections and clarified that input-overflow fallback does not imply the LLM
reviewed the full set. No deep-architecture escalation was recommended.

Final documentation checks: `git diff --check` passed. A local Python check of relative
Markdown links and trailing whitespace passed for both new documents. No remaining failures
were observed in these scoped checks. Previously recorded broader repository evidence gaps
were not tested or closed in this documentation session.

## Remaining decisions and limits

At the initial draft, output factual-rendering authority, duplicate equivalence, alternate-count
interpretation, source packaging, fallback breadth, and numerical model/input budgets were
unsettled. The owner subsequently resolved several of these, as recorded below.
No generated traveler answers or live Results evaluations exist from this session. Upstream
qualification limits, unknown costs, parked D06/D15/D18 scope, and G04 claim gates remain.

## Subsequent owner decisions and milestone proposal

The owner accepted LLM authorship of fuzzy/editorial material with code filling facts, award
grouping and conservative duplicate consolidation, and counting alternates within five total
displayed journeys. The owner requested clear airline programs without a traveler-facing source
feature, expects cleaned inputs to be manageable instead of adding a size limit, asked for
clarification of “writing” and its failures, and requested proper milestones with LLM evaluation
as an additional milestone.

Parent updated the v1 design and project state, created the
[milestone proposal](../handoffs/2026-10-02-results-stage-milestones.md), and appended the
disposition to the existing deferred register. M1 produces the cleaned evidence brief; M2
selects/explains and renders factual answers; M3 adds calibrated LLM-assisted evaluation.
Milestone details and generation-failure/retry behavior remain proposals; no runtime changes,
new live calls, input cap, automatic repair architecture, or model-judge gate were added.

Owner interpretation / changes: the explicit decisions above are recorded. Further conclusions
about actual answer usefulness remain **not yet supplied**.

Implementation authorization / owner-approved next cut: **not yet supplied**. Proposed next
work is M1's cleaned-input contract and saved-example walkthrough.

Follow-up documentation checks: `git diff --check` passed; relative-link and trailing-whitespace
checks passed for the updated design, milestone proposal, and build log. No runtime behavior
changed, so the existing corpus verification was not repeated.
