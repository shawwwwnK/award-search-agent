# Location Candidate Policy

- Date: 2026-08-31
- Goal for this session: Reconcile location-string variability with the future city-to-airport boundary.
- User outcome shipped: The extractor now explicitly emits a normalized location-name candidate
  while preserving verbatim evidence, and the eval scorer supports exact, explicitly enumerated
  candidate aliases without fuzzy matching.
- Commands and tests run:
  - `.venv/bin/python -m pytest -q tests/unit/test_intent_eval_runner.py tests/unit/test_eval_cases.py tests/unit/test_openai_extractor.py::test_openai_extractor_uses_coarse_structured_output_without_storing_response tests/unit/test_domain_models.py` — 17 passed.
  - `.venv/bin/ruff check src/award_agent/domain/models.py src/award_agent/intent/openai_extractor.py src/award_agent/cli/intent_eval.py tests/unit/test_intent_eval_runner.py tests/unit/test_eval_cases.py tests/unit/test_openai_extractor.py` — passed.
  - `.venv/bin/mypy src tests` — 6 pre-existing errors in `src/award_agent/intent/temporal.py` for missing imported names.
  - `.venv/bin/python -m pytest -q` — 56 passed, 4 unrelated failures in in-progress holiday-window work.
- Evaluation result: Affected ready goldens now require exact location evidence and accept only
  project-listed semantic candidate strings.
- Most instructive failure: Exact display-string comparison conflated geographic extraction with
  deterministic entity resolution that does not exist yet.
- Failure classification: Underspecified normalization policy and overly strict golden matching.
- Trace observation: The three-run baseline produced `SF`/`San Francisco`, `South East Asia`/`Southeast Asia`, and three spelling/diacritic variants of São Paulo for the same intended entities.
- Decision made: The project owner chose model-proposed normalized names as non-authoritative
  resolver candidates. A later deterministic resolver will own stable entity IDs and canonical
  display names; search planning will separately own city-to-airport expansion.
- What Codex generated: ADR 0004, contract and prompt descriptions, explicit-alias scoring,
  updated ready goldens, scorer regression tests, and documentation.
- What the project owner changed or rejected: The project owner rejected model-generated strings
  as the eventual authoritative key for city-to-airport lookup.
- Next cut line: [Project-owner selection pending.]
