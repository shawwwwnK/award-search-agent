# Intent eval corpus validation

- Date: 2026-08-31
- Goal for this session: Validate the newly added intent-evaluation scenarios and restore the offline test suite.
- User outcome shipped: The YAML corpus parses successfully and its structural test distinguishes reviewed ready cases from generated candidates.
- Commands and tests run:
  - `.venv/bin/python -c 'from pathlib import Path; import yaml; ...'`
  - `.venv/bin/python -m pytest tests/unit/test_eval_cases.py -q`
  - `.venv/bin/python -m pytest -q`
- Evaluation result: 138 unique scenarios loaded; 16 are marked `ready`; 122 unmarked generated candidates have a layer, an expected clarification, and a supported evaluator type. Full suite: 52 passed in 0.37 seconds.
- Most instructive failure: Several invariant strings beginning with quoted phrases were not valid YAML scalars, so the corpus failed before any structural assertions ran.
- Failure classification: Evaluation-fixture syntax and corpus bookkeeping.
- Trace observation: No live-model evaluation or per-case semantic scoring was run; the current test validates corpus structure only.
- Decision made: [Project-owner interpretation pending.]
- What Codex generated: YAML quoting repairs and structural assertions for the ready/candidate split.
- What the project owner changed or rejected: [Project-owner input pending.]
- Next cut line: [Project-owner selection pending.]
