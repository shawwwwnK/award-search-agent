# 2026-09-19: Architecture review before Milestone 2C

## Owner request

The owner indicated intent to proceed to Milestone 2C and requested a critical review first: whole-project purpose, completed stages, search-planning goals, LLM use, future intent/clarification redesign, the proposed 2C boundary, and possible database/agentic-workflow improvements. The owner explicitly requested independent subagent investigation and parent-led deep architectural reasoning, then a detailed saved document with a concise chat response.

This session did not implement 2C or adopt the review's recommendations.

## Work performed

- Read the relevant product/portfolio, workflow ownership, scope, and data sections of the external workbook without modifying it.
- Reviewed current project state, milestone roadmap, architecture, ADRs, stage closeouts, planner code, contracts, policy, and provider capability references.
- Used four subagents for deep architectural critique, compiler architecture review, upstream investigation, and quantitative 2B evidence analysis. The parent independently evaluated product goals, code, policy behavior, and verification, and integrated the review.
- Checked current public Seats.aero Cached Search/Get Trips references. No authenticated inventory requests or new product-model evaluations were performed.
- Saved advisory recommendations in `docs/reviews/2026-09-19-search-planning-architecture-review.md`.

## Evidence and observations

- Existing planner golden gate: 10/10 passed.
- Parent's focused planner/gateway suite: 134 passed.
- Upstream investigator's focused suite: 46 passed.
- Compiler architect's focused suite: 111 passed, overlapping the parent's suite; not summed into a unique-test count.
- A read-only synthetic-fixture probe varied `repositioning_allowed` across false, null, and true. Every setting produced three endpoint probes, one physical-path hypothesis, and five award items. This matches the approved v1 nonconsumption policy; the review proposes reconsidering it for 2C rather than claiming an implementation regression.
- The 2B audit reconciled the existing final v6 artifact: 46 case-trials, 42 calls, 82 accepted candidates, 400 relationships, and 186,549 tokens. The largest observed relationship count was 65 from four candidates.
- All 43 accepted hub scopes used original endpoint references; none exercised access-gateway references within a hub scope.
- An explicitly hypothetical component-query expansion estimated 55 items for one India record and 43 for one Los Angeles/Australia–New Zealand record. These are analytical estimates under the investigator's stated deduplication assumptions, not implemented 2C output or provider request counts.
- Documentation inspection found retired workflow descriptions in `docs/architecture.md` and unfilled claims in `docs/evidence-ledger.md`. Neither file was changed during this review.

## Commands and verification

```text
.venv/bin/python -m award_agent.cli.search_planning_eval
.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_search_planning_grounding.py tests/unit/test_search_planning_evaluation.py tests/unit/test_gateway_discovery.py tests/unit/test_gateway_generator.py
.venv/bin/pytest -q tests/unit/test_intent_semantic.py tests/unit/test_clarification_controller.py tests/unit/test_clarification_openai_interpreter.py tests/unit/test_one_way_award_live_eval.py tests/unit/test_one_way_award_clarification_eval.py
.venv/bin/pytest -q tests/unit/test_search_planning_endpoint.py tests/unit/test_search_planning_paths.py tests/unit/test_selector_workflow_integration.py tests/unit/test_gateway_discovery.py tests/unit/test_gateway_generator.py tests/unit/test_market_policy.py
git diff --check
git diff --no-index --check /dev/null docs/reviews/2026-09-19-search-planning-architecture-review.md
git diff --no-index --check /dev/null docs/build-log/2026-09-19-pre-m2c-architecture-review.md
```

Additional read-only work used `rg`, `sed`, git status/history inspection, and inline Python. The repositioning probe loaded `tests/unit/test_search_planning_paths.py` with `runpy`, reused its synthetic SFO→JFK→HND fixture, and compiled requests differing only in the repositioning flag. The 2B investigator aggregated existing public evaluation records and immutable result sidecars; no raw private traces were added to the review.

All 15 local links in the review resolved to existing targets. An initial check of the untracked review flagged two Markdown hard-break trailing-space sequences; those were removed before the final whitespace check.

## Files changed

- Added `docs/reviews/2026-09-19-search-planning-architecture-review.md`.
- Added this build-log entry.
- No implementation, prompt, fixture, catalog, workbook, or approved project-state changes.

## Decisions and next cut

- Owner conclusion on proposed 2C contract: **not yet recorded**.
- Owner conclusion on repositioning policy and compatible planning budgets: **not yet recorded**.
- Owner conclusion on moving provider integration ahead of optional RAG/coverage work: **not yet recorded**.
- Owner conclusion on future upstream redesign: **not yet recorded**.

The review is advisory. It preserves 2B closure, 2A's open adoption gate, and the upstream behavioral-evidence limitations. No new claim of human semantic qualification, operational connectivity, inventory usefulness, or end-to-end product readiness is made.
