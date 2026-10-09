# Local intent-to-Results Streamlit harness

Date: 2026-10-08. Owner request: update the harness for newly added stages and enable
end-to-end intent-to-Results testing. The owner also requested stopping if the five-hour
limit is reached.

## Implementation

- Extended `apps/clarification_harness.py` with ready-request full-run and separate planning,
  acquisition/ranking and Results events; retained initial intent and clarification behavior.
- Added `src/award_agent/harness/` application orchestration for M2A/M2B/M2C, bounded Provider,
  matching/styles/export and Results. Stage APIs retain their existing contracts and policy.
- Added saved provider replay and frozen Results draft/correction inputs; historical requests
  are explicitly separate from the current intent session.
- Bound downstream state to session ID, revision and effective-request digest; invalidate
  dependent output before new events. Preserve completed stages when later stages fail.
- Exposed explicit planning models, catalog, pinned provider configuration/budgets, FX and
  Results configuration. Initial Results values mirror the October 8 Luna diagnostic and do
  not establish adopted model settings. Live authoring uses exact full-input measurement.
- Added Markdown/ZIP downloads including stage JSON, acquisition tape and response bodies.
  Temporary provider capture is cleaned after bytes are retained in local session state.
- Updated README, project state, deferred register and harness guidance, preserving unrelated
  existing Results implementation/design edits in the working tree.

## Review and corrections

An independent read-only architecture review found two integration defects: named airports
bypassed catalog alias grounding, and provider configuration was parsed only after model-backed
planning. Both were assigned for correction and regression coverage. Review found no material
issue with ordinary rerun isolation, revision invalidation or temporary response export paths:
evidence references are relative and tapes embed complete response bodies.

The parent also found that the compatibility launcher requires its reviewed Python environment,
so using the harness interpreter would fail live preflight. The application now uses an explicit
editable gfly interpreter, defaulting to `/private/tmp/gfly-live-py312/bin/python`. That environment
was incomplete locally (missing venv metadata and distribution records); restored it with
`.venv/bin/python -m venv /private/tmp/gfly-live-py312` and
`/private/tmp/gfly-live-py312/bin/python -m pip install gfly==0.3.0 fast-flights==3.1.0`.
The sandbox package download failed with a proxy 403; the authorized rerun installed successfully.
The offline version command returned `0.3.0+award-search-unpriced-party-echo-v2` and verified
the launcher's pinned package source hashes. No flight search was made.

## Verification

Verification commands and fresh observed outcomes:

- `pytest tests/unit/test_clarification_harness.py tests/unit/test_harness_workflow_ui.py
  tests/unit/test_provider_execution.py tests/unit/test_provider_replay.py
  tests/unit/test_ranking_m1.py tests/unit/test_ranking_m2.py tests/unit/test_results_m2.py -q`:
  **130 passed** in 101.05 seconds.
- `pytest tests/unit/test_search_strategy_compiler.py tests/unit/test_search_planning_endpoint.py
  tests/unit/test_airport_selector.py tests/unit/test_gateway_discovery.py -q`:
  **43 passed** in 133.08 seconds.
- Final UI rerun after interpreter/export changes: clarification and workflow UI tests
  **20 passed** in 0.98 seconds. AppTest exercises an explicit offline replay click and checks
  that ordinary reruns invoke no pipeline stages. Binding tests check dependent-state disposal.
- `MYPYPATH=src mypy --follow-imports=silent apps/clarification_harness.py
  tests/unit/test_harness_workflow_ui.py`: passed for both files.
- Final `MYPYPATH=src mypy --follow-imports=silent src/award_agent/harness
  apps/clarification_harness.py tests/unit/test_harness_pipeline.py
  tests/unit/test_harness_workflow_ui.py`: passed for all five files.
- Ruff over the app, backend and new tests, and `git diff --check`: passed.
- Backend planning compilation verification (explicit IATA, unique named airport and geographic
  M2A), ready gating, generator ordering/stop and configuration preflight:
  **6 passed** in 162.81 seconds (`pytest tests/unit/test_harness_pipeline.py -q
  -k 'not provider_replay'`, before the additional interpreter test).
- Selected-interpreter live preflight regression: **1 passed** with a fake subprocess transport.
  The earlier saved provider replay → ranking → frozen Results and stale binding checks also
  passed. Final parent run `pytest tests/unit/test_harness_pipeline.py -q
  -k 'not planning_compiles'`: **5 passed, 3 deselected** in 53.98 seconds; this freshly
  checked complete saved provider replay → ranking → frozen Results, stale binding rejection,
  ready/config gating, stage order/stop and interpreter preflight. The three deselected
  catalog-backed planning cases had already passed in the preceding backend run.

Commands use the repository `.venv/bin/` executables. No live model or travel
provider calls ran for this implementation. The Streamlit server started locally on
`http://127.0.0.1:8501`; its health endpoint returned `ok`.

## ADR and deferred-work disposition

Added accepted ADR 0028 for the owner's explicit local end-to-end harness request and amended
ADR 0011's narrow provider-call exclusion. Updated ADR index and `AGENTS.md`; no eligibility,
planning, provider budget, valuation or Results authorship/check policy changed.
The deferred register records this harness disposition without closing existing broader gates.

The independent recheck confirmed the named-airport/configuration fixes and interpreter wiring;
no unresolved important review issue remained within that scope.

Live end-to-end behavior, provider reliability, owner qualification, M3 calibration and
traveler-task benefit remain unclaimed. Unexpected infrastructure exceptions can stop a stage;
only completed stages are guaranteed retained for download. Stage timeouts remain separate;
there is no new whole-workflow deadline. Owner interpretation and next cut: not supplied.

## Layout revision — 2026-10-08

Owner request: rearrange the confusing Streamlit harness. Updated only the presentation
in `apps/clarification_harness.py`:

- Numbered request, clarification/review, search and answer sections.
- Moved model and downstream run settings into sidebar expanders; collapse request entry
  once a session exists and keep imported request JSON under an advanced expander.
- Made the complete live run the primary action. Grouped individual planning,
  acquisition/ranking and answer authoring/retry controls in one collapsed panel;
  retained a separate explicitly historical offline replay panel.
- Show frozen draft/correction fields only in offline authoring mode.
- Show the answer before detailed search evidence; retain provider coverage summaries,
  Results outcomes/notices and downloads. Collapse clarification history, usage and JSON.

Verification: `.venv/bin/pytest tests/unit/test_clarification_harness.py
 tests/unit/test_harness_workflow_ui.py -q`: **20 passed** in 0.86 seconds.
Scoped Ruff and `MYPYPATH=src .venv/bin/mypy --follow-imports=silent
 apps/clarification_harness.py` passed. An ad hoc Streamlit AppTest probe verified
four-step ordering, sidebar settings, conditional offline fields, rendering a saved
annotated answer, and no stage execution during reruns. The first check exposed an
omitted boundary label; the final sidebar/guidance preserves the scope labels.
No live model/provider calls ran. This is AppTest verification, not browser visual QA.

ADR disposition: no new/amended ADR needed; layout changes preserve ADR 0028 events,
application boundaries, revision invalidation and ephemeral artifacts. Reviewed the
deferred register; no deferred entry changed. Owner assessment of the revised layout
and next cut: not supplied.
