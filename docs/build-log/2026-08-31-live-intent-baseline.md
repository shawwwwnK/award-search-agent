# Live intent baseline

- Date: 2026-08-31
- Goal for this session: Run and score the sixteen ready intent scenarios with repeated live-model trials.
- User outcome shipped: A reproducible live-eval CLI, a three-trial `gpt-4o-mini` baseline artifact, and a concise evidence summary.
- Commands and tests run:
  - `.venv/bin/python -m pytest -q` — 54 passed.
  - `.venv/bin/ruff check .` — passed.
  - `.venv/bin/mypy src tests` — passed with no issues in 28 source files.
  - `.venv/bin/python -m award_agent.cli.intent_eval --model gpt-4o-mini --trials 3 --output evals/intent/baseline/2026-08-31-gpt-4o-mini-3-trials.json`.
- Evaluation result: 48 runs; 14 passed all automatic checks, 31 failed one or more checks, and 3 produced explicit errors. Run-level pass rate was 29.2%. Total measured latency was 185.066 seconds.
- Most instructive failure: The baseline mixes clear behavior failures with underspecified or inconsistent golden expectations, especially holiday-window boundaries, traveler counting for “I,” and location canonicalization.
- Failure classification: Model extraction, temporal interpretation, deterministic grounding rejection, golden-contract inconsistency, and underspecified normalization policy.
- Trace observation: Two trials invented non-verbatim Thursday evidence and one invented `about a week`; deterministic grounding rejected all three. Free-text invariants and API usage/cost remain unscored.
- Decision made: [Project-owner interpretation pending.]
- What Codex generated: `award-intent-eval`, scorer tests, the raw baseline artifact, the baseline summary, and documentation updates.
- What the project owner changed or rejected: [Project-owner input pending.]
- Next cut line: [Project-owner selection pending after failure review.]
