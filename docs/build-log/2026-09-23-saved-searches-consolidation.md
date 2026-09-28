# 2026-09-23: one reusable saved-search collection

Status: consolidation, removal, integration checks, and independent review complete.

## Owner request and scope

The owner asked an agent to assemble the final reusable saved searches, remove historical
searches that are not current, and eliminate ambiguity. This authorizes local artifact removal;
no provider calls, upstream planning changes, or stage qualification were requested.

An implementation agent owns corpus consolidation, script/test migration, and scoped deletion.
An independent architect reviews source identity, dependency closure, coverage claims, and replay.
The parent owns integration and current project documentation.

## Intended final organization

`evidence/provider-stage/saved-searches/` is the single reusable collection, with a README,
machine-readable index, current captures and receipts, five current planning inputs, controlled
cash contrast results, and the actual combined live task with exact offline replay.

Currentness is based on contract/provider compatibility, not directory age. Valid Seats.aero
summary, rectangle, pagination, and Get Trips captures remain applicable. Cash searches use the
reviewed `0.3.0+award-search-unpriced-v1` behavior. Superseded unpatched cash, duplicate pagination,
intermediate replay, and diagnostic-only campaign folders are removed after verification.
Minimal historical failures survive only as clearly separated regression fixtures.

`data/provider_capabilities/provider-stage-current.json` is the one active development
configuration. Frozen saved execution bundles retain their original embedded configuration and
identity so that moving the artifact does not rewrite what actually ran. Historical configuration
anchors are provenance identifiers, not alternative active configurations.

The controlled cash result contains only six successful current captures (81 observations,
80 priced and one null). The combined actual-plan result remains partial, with four award and
four priced cash observations, three completed and 22 omitted coverage units. The five saved
planning inputs are not claimed to have fully executed provider graphs.

## Documentation changes

Updated README, AGENTS, project state, deferred register, and current capability/coverage guide
to point to the canonical collection. Historical build/review logs retain original measured
outcomes, with an explicit artifact-retirement notice and current-corpus links.

## Verification and final disposition

The independent candidate review verified all 26 retained raw captures byte-for-byte against
pre-migration hashes: 20 award captures and six repaired cash contrast captures. It also verified
five frozen combined documents unchanged, then ran the production CLI offline replay and obtained
the exact saved result (eight observations, 25 coverage units). The controlled cash result validates
as six completed current-version captures, 81 observations, and no superseded failure entry.

A bounded worker is migrating adapter/execution/review tests independently of the main agent's
CLI-test and corpus-tool updates. Post-deletion integration verification passed; see the final checks below.

## Owner interpretation

<!-- Owner: record any stage-acceptance or next-cut decision separately. -->


The reusable layout uses `seats/search-contrasts/`, `seats/pagination-and-details/`,
`gfly/`, `cash-contrast/`, `trace-inputs/`, and `combined/`. The active policy is
`provider-development-v3`; current capability evidence anchors use retained captures.
The combined execution snapshot remains byte-identical.

Review corrected the new verifier to preserve captured Seats filters, inline-trip mode,
request traveler counts from their traces, detail-request attribution, and cash airport
timezones. The verifier now reuses one catalog context across cash cases.

The main agent reports the read-only verifier passed after regeneration under the active
configuration. The worker's 32 adapter/execution/review tests passed, and the main agent's
three CLI tests passed. Final combined test count and post-deletion checks are recorded below.


## Final removal and integration checks

Removed 11 retired provider-stage directories, the old proposed-runtime configuration, three
one-shot campaign scripts, and two superseded standalone capability configurations.
`evidence/provider-stage/` now contains only `saved-searches/`, with 73 files. The active
configuration is `data/provider_capabilities/provider-stage-current.json`. The useful remaining
tools are the offline corpus verifier, current cash replay builder, diagnostic wrapper, and
reviewed gfly compatibility launcher. No provider calls occurred.

Post-deletion checks:

- `.venv/bin/pytest -q` over all eight `test_provider_*` modules and `test_gfly_compat.py`: **60 passed in 2.64 seconds**.
- Scoped Ruff for the two corpus tools and four migrated test modules: passed.
- `git diff --check`: passed.
- Active script/source/test/data/README scan: no retired artifact, script, or configuration references.
- Seven active documentation files: no broken local Markdown links.
- Credential-value scan of 114 changed/untracked files: zero matches.
- Independent data audit: 26 capture bodies preserved byte-for-byte; five combined documents
  unchanged; combined production CLI offline replay exact; current cash result has six successful
  captures, 81 observations, one unknown price, and current effective provider identity.

Historical build logs retain their execution measurements with clear retirement notices.
Original acquisition identifiers and migration hashes remain provenance, not alternative active
search folders. No owner stage acceptance or provider qualification was inferred.


The [final independent review](../reviews/2026-09-23-saved-searches-review.md) found no blockers.
It independently checked retained source hashes, unchanged plans and combined documents,
canonical mapping, derived artifacts, exact combined replay, current configuration applicability
to all five trace inputs, and absence of active references to removed artifacts.
