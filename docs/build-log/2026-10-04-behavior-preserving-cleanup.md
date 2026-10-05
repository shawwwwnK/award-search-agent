# Behavior-preserving cleanup — 2026-10-04

## Scope and disposition

The owner authorized implementation of the reviewed [cleanup plan](../plans/2026-10-04-2040-refactor-behavior-preserving-cleanup-plan.md). Work started from `9ae261645cd89bcee780ba02f6998ecc09a6ea81` with no existing source/test modifications. Three implementation agents handled usage, identity, and trace work; the parent handled atomic publication and integration. A fresh-context architect reviewed the resulting patch.

The final implementation extracts three duplicated responsibilities:

- Token-record validation and aggregate arithmetic into `src/award_agent/observability/usage.py`, used by the clarification interpreter/composer and airport selector/gateway generator. SDK extraction, counters, resets, guards, and capture positions stay in each adapter.
- Gateway trace forwarding into `src/award_agent/evaluation/_gateway_trace_tee.py`, imported under the existing private names by gateway discovery, integrated planning, and intent-to-planning evaluators.
- Atomic new-file publication into `src/award_agent/cli/_atomic_output.py`, imported as `_write_new_atomic` by both ranking CLIs. The original body, caller guards, and input rechecks are retained.

The attempted query-identity extraction was **not retained**. Preserving the two callers' different input handling and error order required six callbacks; the fresh reviewer judged the resulting indirection more complex than the two explicit recipes. The parent restored `planner.py` and `compilation_contracts.py` byte-for-byte from the starting commit, and retained independent literal-identity regression tests. This is a completed investigation with no new implementation commitment, not an abandoned helper left in the codebase.

Audit cuts 1 and 3 remain intact: historical capability APIs/source verification and evaluator aliases are retained. D12 remains proposed; this session neither retires historical code nor reopens a stage. No prompts, dependencies, policy versions, saved evidence, provider behavior, or Results behavior changed. All execution was offline; there were no model/provider calls, commits, or publication.

## Files and measurements

Nine existing production files use the three new helpers: the four adapters, three evaluators, and two ranking CLIs named above. Tests add `test_usage_accounting.py`, `test_gateway_trace_tee.py`, `test_atomic_output.py`, and `test_query_identity.py`; `test_intent_to_search_planning_live_eval.py` gains a bounded fake-runtime integration case.

Measured against the starting commit, existing production files shrink by 151 lines and new helpers add 82 lines: **69 production lines removed net**. Regression tests add 971 lines net. Source plus tests therefore grow by 902 lines; documentation is additional. The earlier 100–150 production-line estimate was too high. No dependency was removed or added, and no deletion quota was used.

Concurrent changes to `DEFERRED.md` and `docs/build-log/2026-10-04-ai-evaluation-audit.md` belong to separate work and were preserved, excluded from this cleanup's measurements and review.

## Baseline and characterization

Environment: Python 3.12.14, pytest 9.1.1, Ruff 0.16.5, mypy 2.3.1. Before production edits, the parent captured SHA256 hashes of 418 tracked source/test/data/evidence/eval/config files and exact serialization, query IDs, and plan digests for nine saved plans. Temporary logs and snapshots are under `/private/tmp/award-cleanup-lfclofvb`; this directory is session evidence, not a durable project artifact.

Before extraction, new characterization tests passed against the original code: usage 16, identity 9, trace forwarding 18, and atomic publication 24. Further characterization was added during review. The eight new usage tests covering serialization-before-count and capture on invalid parsed output passed against an isolated export of the original source as well as the final implementation. The isolated run asserted its module import path; it emitted one harmless pytest import-rewrite warning. An initial archive command used the system Python without the required tar extraction API; it was corrected to the repository Python before accepting that original-source check.

Protected cases include integer/boolean/negative token behavior, malformed SDK usage, missing calls and drains, exceptions, trace list/element identity, malformed trace iterables, exact UTF-8/newline bytes, existing and dangling symlinks, publication races, fsync/link failures, and cleanup errors after successful publication. The new intent runtime uses fake adapters/repository and checks the planning handoff, two attempted/captured traces, usage totals, and absence of private trace content from the public result.

## Verification

| Gate | Baseline | Final result |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 604 passed, 99 skipped, 2 failed; 595.92 seconds | 692 passed, 99 skipped, the same 2 failures; 663.94 seconds. All 88 added tests passed. |
| `.venv/bin/ruff check src tests` | One RUF059, `tests/unit/test_ranking_m1.py:213` | Same finding; no new diagnostic |
| `.venv/bin/mypy` | 308 errors in 22 files; 188 files checked | Same 308 diagnostics in 22 files, after normalizing shifted line numbers; 195 files checked |
| `.venv/bin/python -m award_agent.cli.search_planning_eval --output …` | 4/4; exact gate passed | 4/4; exact gate passed; entire JSON result equals baseline |
| `PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled --verify` | Three cases verified | Three cases verified |
| Nine saved `CompiledSearchPlan` values | Captured before edits | Exact serialized bytes, query IDs, and plan digests match |
| Saved files and retained imports | Captured before edits | Captured tracked data/evidence/eval files and `pyproject.toml` unchanged; 12 evaluator aliases and 8 historical capability exports import successfully |

Focused checks include the usage/adapters gate (53 passed before the final eight review cases), atomic writer plus both CLI suites (39 passed), final usage characterization (34 passed), retained identity characterization (11 passed), and the four-file trace/evaluator gate (47 passed). The initial combined mypy run found four errors in new identity-test annotations; two typed casts resolved these, and the final diagnostic multiset matches the baseline exactly. No existing diagnostic was suppressed or fixed as part of this cleanup.

The two baseline pytest failures are:

- `tests/unit/test_gfly_compat.py::test_reviewed_fixture_preserves_all_rows_and_unknown_price`
- `tests/unit/test_gfly_compat.py::test_launcher_reports_effective_version_and_source_digest`

Both fail in the existing local gfly compatibility subprocess environment. A separate offline `scripts/gfly_compat.py version --json` diagnostic rejects the pinned interpreter identity. The environment and compatibility code were not changed. Skipped tests remain outside the exercised coverage; local replay does not establish clean-install reproducibility, live provider qualification, or broader product qualification.

## Independent review

The fresh-context architect approved the final three-extraction patch with no unresolved findings. The reviewer checked the uncommitted source and new helpers/tests against the plan, verified the exact writer body and local ownership of usage state/trace orchestration, and recommended not retaining the identity callback protocol. The parent accepted that recommendation and resolved the reviewer's two usage-test coverage observations.

Reviewer-run atomic/initial-usage suites passed 92 tests; final trace/evaluator suites passed 47. A further 76-test planning/usage run had imported the attempted identity extraction before restoration, so it is not counted as verification of the final identity source. Original-source identity tests, the parent final aggregate run, and saved-plan/golden comparisons establish the final-source evidence. The reviewer made no edits or live calls and recommended no escalation.

## Final integration result

The final aggregate run adds 88 passing tests with no new failures or skips. Failure-node sets match the baseline exactly; Ruff output is byte-identical, and normalized mypy error multisets match. Final source hashes confirm no production edits occurred during aggregate verification. `git diff --check` passed. Saved-plan/golden/ranking comparisons passed without changing expected outputs or saved evidence.

The three extractions satisfy the reviewed preservation gates for exercised behavior. Existing failures, skipped coverage, and clean-install/live-qualification limitations remain disclosed above. The owner has not supplied a new product or stage-qualification conclusion; none is inferred. The owner subsequently authorized committing this cleanup; unrelated evaluation-audit changes are excluded from that commit.
