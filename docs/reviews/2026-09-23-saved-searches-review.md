# Saved-search consolidation review

Date: 2026-09-23. Independent review outcome: no blocking findings.

## Reviewed boundary

The owner requested one reusable current saved-search collection and removal of confusing
superseded artifacts. The reviewed result is
[`evidence/provider-stage/saved-searches/`](../../evidence/provider-stage/saved-searches/README.md),
with a machine-readable index, current captures, source receipts, five current planning inputs,
controlled cash observations, and the original combined executor result and replay.

Currentness follows the provider and compiled-plan contracts rather than the acquisition date.
The 20 retained Seats.aero acquisitions remain applicable. The six standalone cash captures use
`0.3.0+award-search-unpriced-v1`; the old unpatched cash diagnostic is excluded from the current
controlled result. Its failure behavior remains covered by a separate synthetic regression.

## Independent evidence

- Before migration, recorded file hashes for all 122 files in the previous Provider Stage
  evidence tree. Compared all 26 retained raw captures with their original source hashes;
  every retained response is byte-identical.
- Compared the five current request/plan bundles with their pre-migration hashes; all are
  unchanged. Checked that the mapping's current output paths resolve to the canonical collection.
- Compared combined bundle, tape, result, replay result, and run receipt with their original
  hashes; all are unchanged. Ran the production CLI in replay mode to a fresh temporary output:
  exit 1 was expected for the partial result, and output bytes matched the saved result exactly.
- Validated the current controlled cash result and tape: six completed acquisitions, 81
  observations, one unknown price, and only the compatibility provider version. No original
  diagnostic failure appears as a current saved acquisition.
- Validated the active `provider-stage-current.json` policy and capabilities, and constructed
  execution plans from all five current trace bundles with their matching caller authority.
- Ran the corpus verifier independently: 20 Seats captures, six cash captures, 81 cash
  observations, one unknown cash price, and the combined eight observations / 25 coverage units
  passed. The verifier was subsequently optimized to reuse one validated catalog; reviewed that
  change and the added current-configuration and mapping checks, and the implementation agent
  reported a passing final verifier run.
- Ran `pytest -q` over `test_provider_adapters.py`, `test_provider_execution.py`,
  `test_provider_review.py`, and `test_provider_results_cli.py`: 35 passed.
- After deletion, confirmed that `evidence/provider-stage/` contains only `saved-searches/`.
  Verified derived-artifact index hashes and scanned active scripts, tests, source, README,
  AGENTS, project state, deferred register, and current provider guides: no retired campaign or
  v1/v2 development-configuration references remain. `git diff --check` passed.

The parent additionally reported a passing final 60-test Provider Stage suite, scoped Ruff,
credential-pattern scan, and active documentation link checks after deletion.

## Findings resolved during review

The initial verifier draft discarded some Seats request dimensions. It now retains cabin and
inline-trip settings, uses traveler counts from the matching frozen trace, and resolves Get Trips
to its actual saved parent availability. Cash parsing uses catalog timezone evidence. Provider-only
experimental acquisition filters remain explicitly recorded in the original request receipts;
they are not invented as user constraints. Standalone Seats verification is parser verification;
the combined task supplies exact executor replay.

The trace mapping's output references were updated to canonical paths. Frozen combined policy
and capability snapshots were preserved rather than rewritten. The separately named active
configuration uses current retained evidence, so users need not choose among historical settings.

## Limits and disposition

The controlled cash result has an explicitly synthetic execution binding. The five saved plans
do not imply full provider execution. The actual combined result remains partial: three completed
and 22 explicitly omitted coverage units. Older identifiers inside immutable execution snapshots
and provenance are historical identity records, not additional selectable saved-search folders.

No provider calls were made for this consolidation or review. This review establishes local
artifact integrity, usable replay, and dependency cleanup; it does not establish current inventory,
bookability, provider qualification, or owner stage acceptance. No unresolved implementation
blocker or escalation recommendation remains.
