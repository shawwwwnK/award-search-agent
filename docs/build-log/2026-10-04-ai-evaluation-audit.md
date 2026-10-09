# 2026-10-04 — AI evaluation audit and deferred-work capture

## Scope and disposition

The owner requested an evaluation audit of the stages completed so far, focused on production
AI evaluation practices, then requested placing the findings in the deferred-work register.
The substantive report, sources, proposed checks, triggers, independent oracles, valid controls
and interpretation limits are preserved in
[DEFERRED.md](../../DEFERRED.md#2026-10-04-ai-evaluation-audit-follow-up).
Recording the recommendations does not authorize their implementation or live execution.
Existing owner-qualified stage boundaries and deferred-entry statuses are preserved.

## Investigation and evidence

Read current project state, relevant workbook evaluation sections, prior October 3/4 reviews,
active evaluator code, casebooks, saved evidence and Results M3 design. Consulted primary
Anthropic agent-evaluation guidance and the MT-Bench LLM-judge research. An investigator traced
upstream oracle coverage; a fresh-context architect challenged consequential findings.

Observed missing live-diagnostic assertions cover intent cabin/full endpoint sets, exact
clarification values and the reason for an upstream-blocked planning result. Proposed wrong-value
counterexamples were not executed. Earlier seeded imported-condition/cost-summary faults were
reviewed from their existing evidence; they were not attributed to normal producers.
Independent timing/premium checks and separate offline semantic tests qualify these findings.

## Verification performed during the audit

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider tests/unit/test_ranking_m1_corpus.py tests/unit/test_ranking_m2_corpus.py tests/unit/test_search_planning_evaluation.py tests/unit/test_one_way_award_live_eval.py
```

Result: **21 passed in 52.56s**.

```sh
PYTHONPATH=src .venv/bin/python scripts/ranking_style_corpus.py --fx-snapshot data/ranking/m2/fx-2026-09-29.json --output-dir evidence/ranking-stage/m2/styled --verify
```

Result: exit 0, **3 cases verified**.

No live model/provider calls, new mutation probes, or product-code edits were made by the audit.
These results do not claim whole-repository health, generalization, current live-model quality,
or qualification of later unrelated working-tree edits.

## Documentation capture

Changed `DEFERRED.md` and added this log. Preserved unrelated working-tree changes. Documentation
verification checks whitespace and relative-link targets; no runtime tests need repeating for
this documentation-only capture. The audit recommends prioritizing semantic-state and
source-condition oracles. Owner implementation sequencing and acceptance remain undecided.
