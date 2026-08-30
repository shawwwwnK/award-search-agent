# Project State

## Phase

Initial implementation / project spine.

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

Implement and evaluate the request-understanding node.

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
