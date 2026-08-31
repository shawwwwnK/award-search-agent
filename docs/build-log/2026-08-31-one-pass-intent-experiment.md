# Naive one-pass intent experiment

- Date: 2026-08-31
- Goal for this session: Compare the production two-pass request-understanding workflow with the most naive one-call approach on the same ready corpus.
- User outcome shipped: An isolated one-pass experiment, three repeated live trials, raw results, and a comparison summary.
- Commands and tests run:
  - `.venv/bin/python -m award_agent.cli.intent_eval --strategy one_pass --model gpt-4o-mini --trials 3 --output evals/intent/baseline/2026-08-31-gpt-4o-mini-one-pass-3-trials.json`.
  - `.venv/bin/python -m pytest -q`.
  - `.venv/bin/ruff check .`.
  - `.venv/bin/mypy src tests`.
- Evaluation result: 48 runs; 2 passed all automatic checks, 27 were schema-valid with failed checks, and 19 ended in schema-validation errors. Run-level pass rate was 4.2%.
- Most instructive failure: Asking directly for the large final contract reintroduced the conditional flat-`DateExpression` schema mismatch documented before the two-pass design; 17 runs failed those validators.
- Failure classification: Model/schema contract mismatch, semantic accuracy, and clarification-contract validation.
- Trace observation: The one-pass run had mean latency of 3.916 seconds versus 3.856 seconds for the two-pass baseline. Usage was captured only for the 29 schema-valid calls, so total token usage and cost are incomplete.
- Decision made: [Project-owner interpretation pending.]
- What Codex generated: The isolated experiment adapter, a reusable eval strategy flag, tests, raw results, and the comparison summary.
- What the project owner changed or rejected: [Project-owner input pending.]
- Next cut line: [Project-owner selection pending.]
