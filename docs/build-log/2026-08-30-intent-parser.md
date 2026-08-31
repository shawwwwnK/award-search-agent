# Intent Parser Implementation Session

- **Date:** 2026-08-30
- **Goal for this session:** Implement the accepted request-understanding boundary from
  `raw request -> ParsedRequest -> ClarificationDecision`.
- **User outcome shipped:** A typed offline-testable request-understanding workflow, an OpenAI
  Structured Outputs adapter, and an `award-intent` CLI that accepts explicit date and timezone
  context and prints JSON.
- **Commands and tests run:** `python -m pip install -e '.[dev]'`, `pytest -q`, `ruff check .`,
  `mypy src tests`, YAML loading checks, CLI help, and live `gpt-4o-mini` smoke runs using the
  representative Thailand request. Final verification: 19 tests passed, measured line coverage was
  84%, Ruff passed, mypy passed, all ten YAML cases loaded as ready, and `git diff --check` passed.
- **Evaluation result:** The final representative live run extracted two travelers, San Francisco
  as a city, Thailand as a country, both award and cash modes, and an approximate 10-day duration.
  Deterministic code resolved the Labor Day departure window to 2026-09-04 through 2026-09-07
  and the return window to 2026-09-13 through 2026-09-18. It preserved cabin and point balances
  as unknown and returned no clarification. This is one observed case, not a full baseline score.
- **Most instructive failure:** The initial schema used a discriminated union that the Responses
  API rejected because `oneOf` was not permitted. After flattening the schema, early model runs
  populated irrelevant date fields, performed date arithmetic, and once missed that “my boyfriend
  and I” means two travelers.
- **Failure classification:** Schema integration error followed by intent-extraction errors and
  unsupported inference.
- **Trace observation:** Separating raw date expressions from deterministic resolution made the
  errors visible. Strict validation prevented the first bad extraction from producing a
  success-shaped parsed request; deterministic sanitization removed fields unrelated to the
  selected expression kind, and explicit prompt rules corrected the remaining representative
  extraction errors.
- **Decision made:** The project owner approved ADR 0001. Implementation keeps semantic extraction
  behind `IntentExtractor`, with validation, date arithmetic, conflict checks, and clarification
  policy in deterministic code.
- **What Codex generated:** Domain contracts, date resolver, conflict detector, clarification policy,
  workflow orchestration, OpenAI adapter, CLI, unit tests, completed golden-case expectations,
  environment documentation, and this build log.
- **What the project owner changed or rejected:** The project owner changed ADR 0001 from Proposed
  to Approved.
- **Next cut line:** **PROJECT OWNER INPUT NEEDED:** choose whether the next session should execute
  and score all ten live intent cases or first review and revise the contract/clarification policy.
