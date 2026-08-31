# Defer Points and Budget Constraints Session

- **Date:** 2026-08-30
- **Goal for this session:** Downsize the MVP request-understanding contract by deferring points
  balances and spending budgets.
- **User outcome shipped:** `IntentExtraction` and `ParsedRequest` no longer expose points-balance
  or spending-budget fields, and award searches no longer produce a missing-points unknown. The raw
  request still preserves any such wording for a later post-MVP contract.
- **Commands and tests run:**
  - `.venv/bin/pytest -q`
  - `.venv/bin/ruff check src tests`
  - `.venv/bin/mypy src tests`
  - `git diff --check`
- **Evaluation result:** 41 offline tests passed; Ruff and mypy passed. The twelve-case intent corpus
  remains structurally valid, and a schema regression test confirms both deferred fields are absent
  from extraction and parsed-request JSON schemas.
- **Most instructive failure:** None observed in offline verification.
- **Failure classification:** Not applicable.
- **Trace observation:** No live-model trace was requested or run.
- **Decision made:** The project owner explicitly deferred point-balance and spending-budget
  constraints until after the MVP. Award-versus-cash search intent remains in scope.
- **What Codex generated:** Removed the deferred fields from extraction and parsed-request
  contracts, public exports, workflow assembly, unknown generation, model instructions, tests,
  eval expectations, and current documentation.
- **What the project owner changed or rejected:** The project owner removed points and budget
  constraints from the MVP design.
- **Next cut line:** Project-owner selection pending.
