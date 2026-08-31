# Project State

## Phase

Request-understanding implementation and initial evaluation.

## Long-term thesis

An award-travel decision assistant that converts vague requests into grounded, traceable flight-search recommendations.

## Selected first workflow

Award-search agent.

## Current slice

Request understanding and clarification.

## Representative request

"My boyfriend and I want to go to Thailand from SF leaving on the weekend of Labor Day weekend and be back after about 10 days. Find award and cash flight options."

## Intended current output

A typed parsed request, explicit unknowns/conflicts, and at most one focused clarification question.

## Current technical assumptions

- Python with a `src/` layout.
- Pydantic domain models.
- pytest.
- Model interaction behind an interface.
- No agent framework selected.

## Largest project-level risk

Feasible access to useful award-inventory data.

## Immediate next milestone

Project-owner selection pending: run and score the ten-case live-model baseline, or review the
current request and clarification contracts before broader evaluation.

## Current implementation status

- Typed request, extraction, parsed-request, unknown, conflict, and clarification contracts exist.
- Date resolution, conflict detection, and clarification selection are deterministic.
- Model extraction sits behind `IntentExtractor`; offline tests use fakes.
- The OpenAI adapter uses Responses API Structured Outputs with response storage disabled.
- The `award-intent` CLI requires explicit reference-date and timezone context.
- Ten golden intent scenarios have ready expectations, but no full live baseline has been run.
- One representative `gpt-4o-mini` run succeeded after schema and extraction failures were fixed;
  this single case is not evidence of general accuracy.

## Explicit deferred work

- planning;
- providers;
- normalization;
- ranking;
- explanation;
- UI;
- persistence;
- deployment;
- RAG.

## Living workbook

Broader project design context is maintained at:

`/Users/shawnkang/bots/workbook_formatted.md`

The workbook evolves alongside the implementation and should be consulted when broader product or evaluation context is needed.

## Decisions that supersede older project notes

The first workflow has now been selected as the award-search agent.

Older source documents should not be automatically updated as part of this scaffold task.
