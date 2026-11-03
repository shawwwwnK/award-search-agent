# Results fast profile — next-session checkpoint

**Historical V3 checkpoint; superseded for new-session navigation by the**
[V30 closeout and October29 owner-direction handover](2026-10-29-results-m2-fast-profile-handover.md).
The checkpoint below retains its original scope; subsequent iteration did not
qualify a default or close the current M2 revision.

The owner requested this commit and intends to make the fast profile the default
after inspecting details and iterating in another session. The actual default
switch is not part of this checkpoint. Preserve the established traveler-facing
answer structure and full eligible explorer; the experiment changes authoring.

## Starting point

- Candidate: explicit `focused-v3` under the interactive CLI/API, same Luna model.
- First call: `none`/Fast selects exact references from the full indexed inventory.
- Code validates at most eight total references and builds a small exact-source
  bundle with deterministic selected-journey time comparisons.
- Second call: `low`/Fast authors highlights, alternatives, cash context and
  limitations within that bundle. No third correction call.
- Final document/resolved-card contracts are reused; artifact V8 records both
  stages. Full inventory/canonical evidence remains available independently.
- Current defaults and older routes remain unchanged. CLI focused profiles own
  reasoning/tier settings; omit those override flags.

## Evidence and open issue

Six unchanged full runs took 6.72–8.46s, median 7.63s. Independent review passed
usefulness 6/6 and factual correctness 5/6; all answers had basic comparative depth.
The second admitted answer reports one seat where its source reports two. Both
support the requested one traveler, but the strict combined gate failed. The
resolved journey card does not itself expose this count; canonical evidence does.
Do not erase the failure or infer owner acceptance of it from the default intent.

- [Final report, answers and keep/cut matrix](../../evidence/results-stage/m2/structured/2026-10-26-under20/README.md)
- [Frozen final cohort](../../evidence/results-stage/m2/structured/2026-10-26-under20/confirmation-focused-v3.json)
- [Specific source review](../../evidence/results-stage/m2/structured/2026-10-26-under20/review-bundles/b032/review.md)
- [Session log](../build-log/2026-10-26-results-under20.md)
- [Contract and CLI](../results-m2.md), [ADR0029](../adr/0029-structured-results-and-local-workspace.md)

The campaign is closed at 46 generation/47 count reservations under 48/48.
Keep existing run directories immutable; future live work needs its own explicit
bounded evidence record. Do not use the one remaining count as an unexplained
extension. No new live calls are needed to inspect this checkpoint.

## Relevant code and verification

Runtime/contracts: `src/award_agent/results/focused.py`, `focused_contracts.py`.
Source selection/bundle/comparisons: `focused_packet.py`; composer wire:
`focused_wire.py`. CLI routing: `src/award_agent/cli/results.py`.

Full Results scope passed 221 tests; source audits, Ruff/mypy and strict
ledger/archive/replay verification passed. This is not a whole-repository test
claim, owner presentation acceptance, M3 closure or a population latency SLA.
Before default adoption, resolve the remaining prose/source binding concern and
review whether the simpler comparative coverage meets the owner's quality goal.
