# Explicit airport-code preservation

- **Date:** 2026-08-31
- **Goal for this session:** Resolve the `LAX` regression so explicitly supplied airport codes
  remain directly usable by the next workflow.
- **Decision made:** When the user supplies a three-letter airport code and the model classifies it
  as an airport, deterministic request-understanding code preserves the uppercase code in
  `LocationRef.value`. The original spelling remains in `raw_text`. This rule does not convert city
  abbreviations into airports.
- **Work attempted:** Added deterministic airport-code preservation after coarse extraction,
  clarified the model prompt and contract description, added unit and workflow coverage, and ran a
  focused three-trial live evaluation.
- **Files changed:** `src/award_agent/intent/locations.py`,
  `src/award_agent/intent/workflow.py`, `src/award_agent/intent/openai_extractor.py`,
  `src/award_agent/domain/models.py`, `tests/unit/test_locations.py`,
  `tests/unit/test_workflow.py`, `tests/unit/test_openai_extractor.py`,
  `docs/adr/0004-location-names-are-resolver-candidates.md`, `docs/architecture.md`,
  `docs/project-state.md`, the baseline summary, the focused live artifact, and this build log.
- **Commands and tests run:** `.venv/bin/python -m pytest -q` (71 passed);
  `.venv/bin/ruff check src tests` (passed); `.venv/bin/mypy src tests` (passed); focused live
  `gpt-4o-mini` evaluation of `missing_travel_period` for three trials.
- **Evaluation result:** 3 of 3 focused live runs passed every automatic check with no errors. The
  origin was retained as `{kind: airport, value: LAX, raw_text: LAX}` while the missing departure,
  return-or-duration, and traveler constraints remained explicit.
- **Trace observation:** The policy closes the regression regardless of whether the model proposes
  `LAX` or the airport display name as `value`, provided it preserves the verbatim code and airport
  classification.
- **What Codex generated:** Deterministic policy, prompt and contract updates, tests, documentation,
  and the focused live artifact.
- **What the project owner changed or rejected:** The owner selected direct preservation of explicit
  airport codes for use by the next workflow.
- **Next cut line:** Return to the five still-unsolved request-understanding scenarios.
