# Results M2 implementation review

Date: 2026-10-07. Scope: new Results package, CLI, four test files, usage documentation,
`pyproject.toml` entry point and atomic output's exact-byte option. An additional independent
Markdown test file and fixture generator were reviewed during follow-up. Existing uncommitted owner
design changes supplied requirements; unrelated changes were excluded. Fixed scope was captured
before reviewers started. Two independent architect subagents applied the `code-review` skill.

Requirements: [implementation spec](../handoffs/2026-10-07-results-m2-implementation-spec.md)
and [delivery contract](../handoffs/2026-10-07-results-m2-validation-and-delivery-contract.md).
Standards: repository `AGENTS.md`, applicable ADR 0026 policy and the skill's Fowler smell baseline.
No live calls ran. Reviewer line numbers below refer to the reviewed version.

## Standards

Three documented-standard findings; no additional consequential baseline smell findings:

- **P2 — Unresolved shared reference receives source facts**, `core.py:618`.
  A shared part with a non-null invalid reference still obtains the shared slot map.
  Public-API reproduction rendered provider status against an unknown reference.
  ADR 0026 requires unresolved references to display unavailable details.
- **P2 — Notice insertion ignores surrounding Markdown**, `core.py:639`.
  Appended notices can remain inside an open fence or interrupt a table across parts.
  ADR 0026 requires visible notices associated with affected information.
- **P2 — Required-disclosure notices escape source values twice**, `core.py:541`.
  Already escaped slot text is escaped again in the notice, causing visible backslashes.
  ADR 0026 requires supplying the source-backed disclosure; grounding must be preserved.

Verification: the reviewer ran the 49-test focused Results suite and public-API probes for invalid
shared scope and open-fence notices. Table placement and double escaping were code-inspection
findings. No edits, no escalation recommended.

## Spec

Seven findings:

- **P1 — Notices trapped in Markdown**, `core.py:639`. Violates local visible Validation notices
  and cross-part layout coverage. Open-fence probe confirmed; table row placement also affected.
- **P1 — Invalid shared references obtain facts**, `core.py:618`. Violates unavailable-detail
  handling without borrowed facts.
- **P1 — Incomplete cash leads labeled benchmarks**, `core.py:122`. Component kind determines
  disposition even for unpaired incomplete cash observations. Violates distinct incomplete and
  benchmark outcomes.
- **P1 — Reported mixed-cabin disclosure missing**, `core.py:171`, `core.py:531`.
  `mixed_cabin_pct` is retained in source but absent from slots/obligations. Violates user story 13.
- **P2 — Claim scopes not exact**, `core.py:511`. A valid journey plus an extra unknown ID still
  receives supported cabin checking. Violates exact journey/comparison scopes.
- **P2 — Resumed identity ambiguous**, `core.py:485`. A common route is accepted as identity for
  different variants. Violates visible association when a journey resumes.
- **P2 — Replay accepts contradictory evidence**, `core.py:648`. Altered prompt digests and
  generation/validation outcomes are accepted on a clean delivered artifact. Violates distinct,
  retained outcome and digest evidence.

Verification: read-only public-API probes confirmed fence hiding, surplus claim scope, common-route
resumption and contradictory replay evidence; remaining findings were source-backed inspection.
No edits, no architectural escalation recommended.

Initial summary: Standards 3 findings (worst within axis: unsafe notice placement); Spec 7 findings
(worst within axis: notices can be hidden). Findings remain separate; overlaps are intentional.

## Fix disposition

The implementation agent fixed the initial findings through public-API regression tests. Re-review
then reproduced additional edge cases: an empty cash-leg report despite a business component cabin,
invalid references suppressing disclosure obligations or supplying another category's facts, and
side-by-side table columns receiving a notice in the wrong cell. These were also corrected.

The final Standards recheck found no blocking findings: five targeted regressions and two independent
public-API probes passed. It verified source/reference validity, disclosure supply and the originating
table cell's notice offset, and inspected the deterministic fixture generator. The final Spec recheck
found no blocking findings: three targeted regressions passed for per-component leg evidence and
exact disclosure references. Earlier scope, identity, replay and literal-binding fixes remained.

An independent worker added Markdown-to-HTML assertions through the public API using a development-only
renderer: four tests passed for valid layouts, code-fence notice visibility, split rows, side-by-side
cells and escaped pipes. Rendering evidence is independent of the implementation's own Markdown logic.
No reviewer or worker made a live model/provider call. Full-suite evidence is recorded in the build log.

Final summary: Standards and Spec have no unresolved blocking findings in the declared scope.
The original counts remain Standards 3 and Spec 7; the re-review edge cases above are recorded
separately rather than treating overlapping findings as a single ranked list. M3 semantic quality,
model-specific context fit and broader traveler benefit remain unqualified.
