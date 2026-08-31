# Award Travel Agent

Award Travel Agent is an independent portfolio project for building a narrow, measurable award-search workflow that turns vague travel requests into grounded, traceable recommendations. The current repository only establishes the project spine for the first implementation slice so later work can add request-understanding behavior behind explicit interfaces and evaluation cases.

## Current milestone

Request understanding only:

`raw request -> ParsedRequest -> ClarificationDecision`

## Intended workflow

The eventual workflow is:

`Raw request -> Parse request -> Clarify constraints -> Plan searches -> Run provider tools -> Normalize and validate -> Rank candidates -> Explain recommendations`

## Repository map

- `src/award_agent/`: Python package boundaries for the request-understanding slice and later workflow stages.
- `tests/`: unit, integration, and fixture directories.
- `evals/intent/`: draft intent-evaluation scenarios and future baselines.
- `docs/`: durable project state, architecture notes, ADRs, workboard, and evidence process docs.
- `evidence/`: sanitized reproducible artifacts from real runs.
- `scripts/`: future reproducible maintenance or evaluation commands.

## Local setup

Create a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

Run type checks:

```bash
mypy src tests
```

## Parse a request

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` and `MODEL_NAME`. The
offline test suite does not load or require either value.

Run the request-understanding workflow with an explicit temporal context:

```bash
award-intent \
  --reference-date 2026-08-29 \
  --timezone America/Los_Angeles \
  "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend for about 10 days."
```

The command prints `ParsedRequest` and `ClarificationDecision` as JSON. Model
responses are requested with storage disabled; the workflow does not persist
requests locally.

## Current non-goals

- Search planning
- Provider integrations
- Ranking
- RAG
- Web UI
- Authentication
- Persistence
- Multi-agent orchestration
- Deployment infrastructure

Live provider integrations and model-dependent behavior have not yet been implemented. Measured results will be recorded only after real runs, not inferred from scaffold-only setup.

The living design workbook is at `/Users/shawnkang/bots/workbook_formatted.md`. It is a design aid for broader product context; repository docs and ADRs capture implementation-specific decisions and superseding boundaries.
