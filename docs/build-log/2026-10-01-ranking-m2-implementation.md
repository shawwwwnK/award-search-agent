# 2026-10-01: Ranking M2 implementation and corpus verification

Status: locally implemented and independently reviewed; owner qualification is not claimed.

## Owner instruction and boundary

The owner requested orchestrated implementation and review, verification and interpretation using
the saved searches, and iteration. The accepted policy is in the
[M2 contract](../handoffs/2026-10-01-ranking-m2-styles-contract.md). M1 validation, provider
acquisition, wider topology, and Output Stage behavior remain unchanged.

## Orchestration and initial evidence

- An implementer owns M2 contracts, normalization, style assignment, exports, and core/corpus tests.
- A worker owns the explicit offline CLI, entry point, corpus generation/verification script,
  and CLI/script tests. These write scopes do not overlap.
- An architect owns independent strategy and adversarial code review; the parent owns integration,
  source preservation, actual FX capture, final verification, and corpus interpretation.
- Before integration, the existing M1 gate passed 35 tests in 6.98 seconds. The scoped provider
  contracts/adapters/replay/review regression gate passed 39 tests in 1.08 seconds.
- The parent independently computed raw-source time/premium/highlight anchors: mixed access
  5/120/0, exact business 34/106/34, and positioning 22/0/0. The eligible pools are 257/106/64.
- Captured a dated official Bank of Canada response at `data/ranking/m2/fx-source-2026-09-29.json`
  and a USD/CAD snapshot at `data/ranking/m2/fx-2026-09-29.json`. The September 30 request had no
  observations; the latest returned observation was September 29. Verified source SHA-256,
  observation date, and reciprocal at 28-digit precision. No travel-provider/model calls occurred.

## Review findings and iteration

Initial review rejected acceptance of the first implementation for three substantive defects:

1. Source journey endpoints/transfer features were trusted without checking attached component
   evidence. An altered conditional journey could incorrectly set the time reference.
2. Early Decimal division could exclude a cost exactly at the inclusive 200% boundary for a
   three-traveler party. Exact comparison arithmetic is required, not merely higher precision.
3. The corpus verifier used ambient Decimal precision and could disagree with core on second-
   precision instants. An independent exact elapsed-time oracle is required.

The parent additionally required an owned arithmetic context and end-to-end synthetic coverage
of complete cost references, provisional highlights, premium-economy add-ons, zeros, isolated
feature changes, and source/derived tampering. These findings were fixed with source-component
coherence checks, exact rational cost receipts, UTC-microsecond comparisons, an owned precision-50
display context, and an independent exact corpus oracle. Final runtime review passed.

A later review found the first three-traveler synthetic fixture rebound identity hashes without
updating compiled traveler semantics. It was replaced by an actually compiled mandatory-only
three-traveler plan, derived execution queries, three timed party-price awards, and M1 assembly.
The architect independently rebuilt execution and reproduced M1 assembly. Costs 1/3, 2/3,
and 67/100 yield member/member/not_member at the exact 2/3 threshold. Final fixture review passed;
no material findings remain. Broader scoped mypy initially found ten test annotation/narrowing
errors; a worker fixed these without weakening assertions, and the final eight-file gate passed.

One CLI input-change test accidentally modified the original `mixed_access` M1 fixture. The
worker restored its exact original bytes and changed tests to use temporary copies. Parent
SHA-256 checks confirmed all three original M1 artifacts match their recorded hashes; no source
artifact change is accepted as part of this implementation.

## Final commands and measurements

- `.venv/bin/pytest -q tests/unit`: **606 passed, 99 skipped in 657.60 seconds**. This broad
  run overlapped the final fixture iteration; the final targeted gate below rechecked final files.
- `.venv/bin/pytest -q tests/unit/test_ranking_m1.py tests/unit/test_ranking_m1_corpus.py
  tests/unit/test_ranking_m1_cli.py tests/unit/test_ranking_m2.py
  tests/unit/test_ranking_m2_corpus.py tests/unit/test_ranking_m2_cli.py
  tests/unit/test_ranking_m2_script.py`: **71 passed in 91.69 seconds**.
- Scoped Ruff passed for the ranking package, new CLI/script, and four M2 test modules.
- Scoped mypy passed for eight changed code/test files: `style_contracts.py`, `styles.py`,
  `ranking_styles.py`, `ranking_style_corpus.py`, and the four M2 test modules. A separate worker
  check including unchanged M1 `contracts.py` reported five preexisting errors; those were left
  untouched. No whole-repository type-clean claim is made.
- `PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot
  data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled` generated
  all three saved projections, including byte-identical second replay and independent time oracle.
  The same command with `--verify` passed against the saved directory.
- A parent independent JSON/SHA-256 audit confirmed input/output index hashes, exact full source
  attachments, all 992 retained journeys, and unchanged recorded M1 source hashes.
- `git diff --check` passed. Documentation newline/whitespace/local-link checks passed for
  eleven changed documents and 170 local links before final log updates.
- All required agent reports were collected; the worker, implementer, and architect were closed.

| Saved request | Retained | Eligible | Time | Cost | Premium | Definite highlights |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mixed_access | 473 | 257 | 5 | 0 | 120 | 0 |
| exact_business | 396 | 106 | 34 | 0 | 106 | 34 |
| sfo_to_bkk_positioning | 123 | 64 | 22 | 0 | 0 | 0 |

All 427 eligible cost assessments are undetermined because no sufficiently complete price-scope
reference exists. There are no manufactured cost winners, possible-cost memberships, or possible
highlights on unchanged saved inputs. Premium-economy add-ons are empty on this corpus and covered
by synthetic tests. All rejected/research records and direct-cash baselines remain preserved.

## Changed files and evidence

- Runtime: new `src/award_agent/ranking/style_contracts.py`, `styles.py`, exported API in
  `ranking/__init__.py`, new `src/award_agent/cli/ranking_styles.py`, and CLI entry in `pyproject.toml`.
- Tests/tooling: four new `tests/unit/test_ranking_m2*.py` modules, new
  `scripts/ranking_style_corpus.py`, and `scripts/README.md` instructions.
- Artifacts: `data/ranking/m2/` source/FX snapshot/README and
  `evidence/ranking-stage/m2/` result/index/README. Original M1/provider evidence is unchanged.
- Documentation: README, AGENTS, project state, Ranking Stage design and M2 contract, DEFERRED,
  this implementation log, and the earlier investigation log's disposition amendment.

## Parent engineering interpretation and owner review

The resulting time/premium assignments match independent raw-source anchors and the owner policy.
The mixed-access time group isolates five shorter award-only routes; premium lists the conditional
business alternatives without pretending they are fast or confirmed. Exact-business premium
membership is broad by design, with 34 shorter variants earning two-style highlights. Positioning
includes all five admitted egress variants and 17 conditional access variants under the unified
120% threshold, including an 8h55-transfer variant whose whole time remains within the rule.
These are engineering interpretations, not owner conclusions or product-usefulness qualification.

The substantive remaining evidence limitation is cost scope: unknown per-person/party pricing
prevents real-corpus cost membership despite the implemented estimation/valuation mechanics.
G04 records the claim-specific prerequisite. Do not invent scope or alter the provider stage to
hide it. See the [saved results and interpretation](../../evidence/ranking-stage/m2/README.md).

Parent engineering acceptance is for the implemented, tested, source-preserving M2 boundary.
Owner review/qualification, observed-cost style usefulness, full-workflow usefulness, and Output
Stage completion remain unclaimed. Wider D15/D18 scope stays parked. No new owner decision or
stage closeout is inferred from this implementation request.
