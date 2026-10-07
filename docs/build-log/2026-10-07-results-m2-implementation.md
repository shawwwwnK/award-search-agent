# Results M2 implementation

Date: 2026-10-07. Trigger: owner invoked `$implement` for the
[Results M2 spec](../handoffs/2026-10-07-results-m2-implementation-spec.md).

## Work and scope

Implemented a public Results API consuming Ranking's trusted `SolutionProjection`, explicit
configuration and an injected writer. Added scoped factual slots and literal rendering, a selected
claim catalog, independent disclosure checks, one bounded correction opportunity, draft comparison,
local notices, and exact replay. Added a no-retry Responses adapter and CLI measurement/offline
author/live/replay modes. The atomic-output helper now optionally preserves exact Markdown bytes.

Files: `src/award_agent/results/`, `src/award_agent/cli/results.py`,
`src/award_agent/cli/_atomic_output.py`, `pyproject.toml`, five `test_results_*` files,
[usage](../results-m2.md), [review](../reviews/2026-10-07-results-m2-implementation-review.md),
and `evidence/results-stage/m2/`. Project-state, ADR index/disposition and deferred-work updates
record implementation status without claiming owner qualification.

Used TDD at the owner-confirmed public Results seam. Boundary-focused fake-transport and minimal
CLI tests cover guarantees that need observation outside that seam. Delegated core implementation,
two independent review axes, and saved evidence generation. Parent owns integration and acceptance.
The owner authorized live model and provider calls during the session. No live models, providers,
or paid diagnostics were needed or run for this implementation.

## Review and observed failures

The [two-axis review](../reviews/2026-10-07-results-m2-implementation-review.md) reported three
Standards and seven Spec findings, including hidden/disrupted notices, invalid shared substitution,
incomplete cash disposition, mixed-cabin disclosure, exact scope/resumed identity and replay
consistency. Public-API regression tests cover the corrections. Both final independent reviewer
rechecks found no blocking findings. Follow-up corrections cover absent cash-leg evidence,
invalid references suppressing disclosures, and notice placement in the originating table cell.
Four independent Markdown-to-HTML tests verify visible notices and layout behavior.

Independent source-backed tests also reproduced two claim-check failures: a known economy leg plus
another unknown leg was insufficient rather than failed; a known per-traveler award plus unknown
cash quote scope was insufficient for an asserted party total. Both were fixed so missing evidence
does not erase a known contradiction.

## Verification

The console-script pytest invocation failed collection before executing tests because an existing
Ranking test imports `tests.unit.test_ranking_m2` and that invocation omits the repository root.
The module invocation collects all 896 tests:

```sh
.venv/bin/python -m pytest -q --junitxml=/private/tmp/results-m2-full-tests.xml
```

Result: **795 passed, 99 skipped, two failed**, in 718.16 seconds. All **75 Results tests passed**
with no skips. The failures are the previously recorded gfly compatibility tests
`test_reviewed_fixture_preserves_all_rows_and_unknown_price` and
`test_launcher_reports_effective_version_and_source_digest`. The local gfly subprocess exits with
status 1: the nominal pinned executable resolves to the Homebrew base interpreter, so the
compatibility launcher's installation guard raises `RuntimeError: use the pinned interpreter at
/private/tmp/gfly-live-py312/bin/python`. They are outside Results and match the existing G05
environment limitation.
Full output is `/private/tmp/results-m2-full-pytest.log`; JUnit is at the command's declared path.

Scoped Results mypy and Ruff passed, including the CLI, atomic-output helper and five test files.
`MYPYPATH=src .venv/bin/mypy --explicit-package-bases src tests` checks 211 files and reports
325 pre-existing errors across 29 files, with no Results source or test diagnostics. The initial
aggregate mypy invocation failed on duplicate test-module mapping; explicit package bases resolve
that invocation issue. Full Ruff reports eight existing findings in older review evidence scripts
and `tests/unit/test_ranking_m1.py`. Provider source has no diff. `git diff --check` passed.

Complete input measurements retain all 992 alternatives (427 eligible complete journeys) across
the three saved Ranking exports. Input UTF-8 bytes are 1,855,734 for mixed access, 1,248,191 for exact
business, and 601,136 for positioning. Each conservative total adds the explicitly supplied
100-token protocol allowance and 10,000-token output reservation. These are conservative byte
bounds, not model-specific token counts.

The saved positioning clean fixture uses one writer call with zero failed findings; its annotated
fixture retains the initial draft with one failure over a correction with two. Serialized artifacts
replay exact UTF-8 bytes with no writer: 4,036 clean bytes and 4,291 annotated bytes. Source, request,
schema, draft, artifact and replay digests are recorded in the evidence index.

The canonical generator and a fresh build into `/private/tmp/results-m2-final-rebuild` both
succeeded. All six indexed artifact, draft and replay files matched byte-for-byte, checked with
`/private/tmp/compare_results_m2_rebuilds.py`. Generator verification:
`.venv/bin/ruff check --fix evidence/results-stage/m2/generate.py` corrected one lint issue;
`.venv/bin/mypy src/award_agent/results evidence/results-stage/m2/generate.py` passed on five
source files. No obsolete `.replay.md` files are present in the canonical evidence folder.

## ADR and deferred-work disposition

No new ADR was needed: this implements the existing accepted policy in ADR 0026 and upstream
ownership/trust in ADR 0027. ADR 0026 and its index gain implementation-status dispositions;
numeric settings remain explicitly supplied engineering inputs rather than adopted model defaults.
G03/G05/G06 retain broader claim-specific gates, and no parked feature was reopened.

## Limits and owner interpretation

The cleaned full input is measured as instructions, payload and strict schema plus explicit output
reservation. Conservative UTF-8 token bounds are not model-specific tokenization or context-fit
qualification. Fixture drafts are deterministic offline authoring controls, not model-quality
evidence. Typed checks do not prove arbitrary paraphrase truth or detect every undeclared assertion.
M3, live settings/budget, owner qualification, bookability, reliability and traveler benefit remain
unclaimed. No owner learning conclusion or next cut is invented; owner interpretation is pending.
