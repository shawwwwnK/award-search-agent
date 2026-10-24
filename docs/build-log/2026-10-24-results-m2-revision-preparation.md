# Results M2 revision — implementation preparation

Date: 2026-10-24.

## Owner instruction and scope

The owner opened Results M2 revision implementation for this session, requested
additional subagent investigation and a detailed implementation plan before coding,
and asked for notice of anything changing the milestone goals. This record covers
the preparation checkpoint only. Implementation is authorized for U1–U3; no runtime
work or live-call campaign was performed in this checkpoint.

## Investigation evidence

Three read-only investigators traced separate units:

- U1: Ranking projection/matching contracts and Results compact authoring. The
  projection contains exact candidate/component identities, option-family IDs,
  projected leg instants/local dates, original money/scopes and source digests.
  Authoring fact-compression groups are distinct from explorer groups. Existing
  `option_family_id` supports conservative variant grouping without physical-flight
  equivalence claims. Saved-case eligible counts observed were 258/232/0; future
  tests must independently reconcile source ID sets, not rely on those counts.
- U2: Ranking snapshot/style/projection and harness Ranking entry. The immutable
  snapshot is already supplied to Ranking and embedded in the projection. The
  harness currently loads a fixed September 29 snapshot; new-run acquisition belongs
  immediately before Ranking. Observed payable cash must be derived separately
  from heuristic costs that can include valued points and estimated taxes.
- U3: Results contracts, authoring, request schema, adapter, core, CLI and harness.
  Legacy strict document schemas affect request digests. New separate structured
  types/checker and explicit dispatch are required; compact alias/source binding
  and bounded orchestration can be reused where semantics match. Ranking is already
  yielded before authoring, supporting independent evidence availability.

Investigators used `rg`, `cat` and `sed`; they made no edits and ran no tests,
provider/model/FX calls or further delegation. Each reported no goal change or
need for escalation. The parent read the current plan/ADR/project state, relevant
deferred entries, and workbook workflow/evaluation sections; the workbook was not
modified.

The parent read [Frankfurter's official documentation](https://frankfurter.dev/)
to ground the initial provider-specific v2 FX adapter target. No rate acquisition
was performed. Rate direction, effective dates and raw provenance remain explicit
implementation controls; no live-adapter success is inferred from documentation.

## Documentation changes

- Expanded U1–U3 in
  `docs/plans/2026-10-23-2334-feat-results-workspace-plan.md` with concrete module,
  schema, grouping, schedule, currency, request, checker and replay seams; independent
  controls; execution order and future verification commands.
- Updated `docs/project-state.md`, `AGENTS.md`, ADR 0029 and its index to record
  the current invocation and distinguish it from the October 23 planning-only session.
- Preserved existing unrelated untracked end-to-end diagnostic files/evidence.

## Plan review and disposition

Applied the ce-plan and ce-doc-review workflows. Four native reviewers covered
coherence, feasibility, scope and adversarial technical assumptions independently.
No external model CLI/cross-provider job was launched; no cross-provider
corroboration is claimed. UI visual review is a later frontend/owner gate.

- Coherence raised one P2, confidence-100 consistency finding: U2 named an initial
  FX source target while the final sources note still described selection as open.
  Applied the mechanical correction to the sources note. No open finding remains.
- Feasibility returned no findings after tracing the code seams; execution-time
  compatibility tests are still required.
- Scope returned no findings; frontend integration/follow-ups remain later units.
- Adversarial review returned no findings after inspecting grouping, money,
  frozen historical facts and version/schema isolation.

Resolved review: one correction applied; zero proposed fixes, unresolved decisions
or retained advisory findings. Confidence is based on read-only investigation and
review, not passing runtime checks. No milestone-goal change was identified.

## ADR and deferred-register disposition

ADR 0029's dated execution disposition and ADR index were amended. No new ADR is
needed: accepted ownership, policy, trust, recovery and milestone goals are unchanged.
The update supersedes only U1–U3's prior uninvoked status. `DEFERRED.md` was consulted;
no item was completed, newly deferred, reopened or dropped at this checkpoint, so
no register entry changed. G03/G05/G06/G08, historical replay concerns and M3 retain
their existing claim-specific gates.

## Verification and limits

Commands at this checkpoint: read-only `rg`, `cat`, `sed`, `wc`, `date`,
`git status --short`, `git diff --stat`, `git diff --check`; a local Markdown
relative-file-link check over changed documents. `git diff --check` passed; the
link check passed for 116 relative file links across six documents (file existence,
not heading-anchor validation). No Python runtime tests, type/lint checks,
generations, token-count requests, travel-provider calls or FX acquisition ran.
No code, saved artifacts, qualification outcomes or owner acceptance changed.

Owner presentation acceptance remains open. The accepted sequence remains Results
M2 U1–U3, Frontend M1 U4, Frontend M2 U5–U6, then Results M3 evaluation/acceptance,
with evaluation preparation earlier. These are existing owner decisions; no new
owner conclusion is inferred here.
