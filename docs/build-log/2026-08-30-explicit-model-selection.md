# Explicit Model Selection Session

- **Date:** 2026-08-30
- **Goal for this session:** Remove model selection from environment configuration so model
  candidates can be evaluated and assigned independently per workflow.
- **User outcome shipped:** `OpenAIIntentExtractor` now receives an immutable
  `OpenAIExtractorConfig`; the CLI requires `--model`; only `OPENAI_API_KEY` remains in `.env`.
- **Commands and tests run:** `pytest -q --cov=award_agent --cov-report=term-missing` returned
  25 passing tests and 90% measured line coverage; `ruff check .`, `mypy src tests`, and
  `git diff --check` passed. CLI help confirmed that `--model` is required, and a local
  configuration check confirmed `.env` contains only `OPENAI_API_KEY`.
- **Evaluation result:** No live-model quality evaluation was run because request behavior did not
  change; offline adapter tests parameterize multiple model IDs and verify the selected ID reaches
  the Responses API request.
- **Most instructive failure:** The previous `MODEL_NAME` fallback coupled all workflows and eval
  runs to one process-wide model, making comparisons vulnerable to hidden environment state.
- **Failure classification:** Configuration and evaluation-isolation risk.
- **Trace observation:** Model identity is now available directly from `extractor.config.model` and
  is passed explicitly in each API request.
- **Decision made:** Model choice belongs at the workflow composition/evaluation boundary. API-key
  loading remains a provider concern and may continue to use the environment.
- **What Codex generated:** Typed model configuration, constructor and CLI refactor, parameterized
  adapter tests, environment cleanup, documentation, and this build log.
- **What the project owner changed or rejected:** The project owner explicitly rejected model
  selection through an environment variable.
- **Next cut line:** **PROJECT OWNER INPUT NEEDED:** define the first model-comparison rubric and
  candidate set for the ten intent cases.
