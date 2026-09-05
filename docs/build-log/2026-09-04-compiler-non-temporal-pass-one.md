# 2026-09-04: Compiler non-temporal Pass 1

- **Milestone:** Cut 3: separate non-temporal extraction from deterministic temporal scanning.
- Added strict non-temporal input/output contracts and a dedicated one-call, no-repair OpenAI
  boundary with separate prompt, schema, trace stage, usage capture, and failure type.
- `compiler_select_v1` requires that boundary and explicitly assembles the compatibility coarse
  extraction from non-temporal output plus scanner/compiler temporal facts. Legacy two-pass
  extraction and repair behavior remain unchanged.

## Verification

- `.venv/bin/pytest -q tests/unit/test_openai_extractor.py tests/unit/test_workflow.py tests/unit/test_temporal_compiler.py tests/unit/test_temporal_selector.py` — 119 passed.
- `.venv/bin/ruff check src tests` — passed.
- `.venv/bin/mypy` — passed for 56 source files.

## Evaluation result

- No live model or end-to-end evaluation was run.

## Next cut line

- Run the required architecture checkpoint before E2E runner wiring; this does not qualify a live selector.
