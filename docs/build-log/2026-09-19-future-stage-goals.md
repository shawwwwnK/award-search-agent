# Future-stage goal reassessment

Date: 2026-09-19.

Subsequent owner-requested fresh Astra challenge revised the proposal in place; see the
[debate and revision record](2026-09-19-future-stage-astra-challenge.md). The initial verification
counts below describe this original drafting session, not the later revised document.

## Request and scope

The owner requested deep, project-grounded thinking about revising/finalizing the goals of
unstarted stages, combining implemented-stage lessons with agent-system engineering practice.
The requested deliverables were a discoverable repository document and a brief explanation.
This was an advisory documentation session, not authorization to open 2C or later implementation.

## Work performed

- Read current project state, roadmap, deferred register, prior architecture/engineering review,
  2B closeout, relevant ADRs, provider intake, and relevant workbook sections.
- Inspected existing planner contracts, budget admission behavior, policy limits, and the
  repositioning-policy receipt. No application code was changed.
- Consulted official Anthropic engineering articles on agent/workflow design, evaluation and tools,
  and the official Seats.aero Cached Search reference. Sources are linked in the review.
- Wrote `docs/reviews/2026-09-19-future-stage-goals.md`, proposing goals, completion evidence,
  sequencing, experiment limitations and conditional stop/drop decisions for remaining stages.
- Added discovery pointers to AGENTS.md, README.md, project state and the active roadmap.
- Refined advisory notes under existing deferred IDs without changing their disposition.

## Evidence and limits

Historical metrics in the review are attributed to existing project records; no new live
model/provider evaluation, user study, utility improvement or semantic qualification is claimed.
The 10 × 3 = 30 endpoint-pair example is illustrative arithmetic against the current 25-pair cap,
not a measured runtime failure. The workbook was not edited.

The workspace already contained modified instructions/state/README/workboard and untracked
architecture-review/register artifacts. These were preserved; edits here are additive and scoped
to this review's discoverability and recommendations.

## Verification

- Read-only inspection used `rg`, `rg --files`, `sed`, `cat`, and `git status --short`.
- One initial `rg` invocation named nonexistent `search_planning/airport_selection.py`; it reported
  the missing path. File discovery identified `airport_selector.py`; no change depended on the
  nonexistent file.
- `git diff --check`: passed.
- A local Python documentation check verified **69 local Markdown link targets across seven
  touched files** and checked both new documents for trailing whitespace and terminal newlines:
  passed. The review contains approximately 3,788 words.
- `.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_search_planning_evaluation.py`:
  **71 passed in 1.08 seconds**. This verifies existing focused offline planner behavior; it does
  not validate the proposed future architecture or resolve previously recorded repository-wide
  quality-gate failures.
- No new tests were authored for these documentation-only changes.

## Owner decisions

Pending owner consideration. Recommendations in the review are not owner conclusions.
M2B remains closed; M2C remains deferred; M2A remains diagnostic-only.

## Next cut line

Owner decision pending. No implementation work was opened by this session.
