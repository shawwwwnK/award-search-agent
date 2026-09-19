# Award Travel Agent

Award Travel Agent is an independent portfolio project for building a narrow, measurable award-search workflow that turns vague travel requests into grounded, traceable recommendations. The request-understanding slice is implemented and frozen behind explicit interfaces and evaluation cases; later work can build the downstream search workflow on that boundary.

## Current milestone

Milestone 2B gateway-airport discovery — implemented; prompt-v2 diagnostic is awaiting owner and human semantic review.

The frozen upstream boundary uses one-way award-only request semantics. A ready request requires
origin, destination, an outbound departure window, and traveler
count. Return dates and durations receive visible guidance to submit a separate one-way request;
cash-only requests are unsupported; mixed award-and-cash requests remain eligible for award search
without implying cash pricing is available. The deterministic, retrieval-backed
`EffectiveRequest -> SearchPlan` boundary is implemented and qualified for its declared checked-in
fixture coverage. Milestone 1 supplied the reviewed, versioned local GeoNames/OurAirports catalog.
Milestone 2A implemented bounded model-proposed endpoint-airport selection, but it remains
diagnostic-only pending independent human review, holdout evidence, and an adoption decision. The
implemented 2B boundary uses an approved versioned global planning-market policy and selects one grouped
structured model proposal for bounded, explainable gateway candidates. Same-market skipping is
allowed only when every original endpoint is known and their market union has size one; mapping
gaps force generation, and model/policy market disagreements remain advisory for 2C. Candidates
remain unverified search hypotheses. The bounded prompt-v2 development run is mechanically complete,
not semantically qualified. Provider execution remains later; this cut ends before 2C
search-strategy compilation, a Seats.aero API call, provider payload mapping, result normalization,
or ranking. See the
[search-planning stage brief](docs/handoffs/2026-09-10-search-plan-design-stage.md) and
[`ADR 0016`](docs/adr/0016-one-way-award-request-boundary.md),
[`ADR 0020`](docs/adr/0020-market-aware-model-proposed-gateway-candidates.md), plus the
[Milestone 0–4 roadmap](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md) and
[Milestone 2B implementation brief](docs/handoffs/2026-09-17-m2b-gateway-airport-discovery-opened.md), and the
[2B evaluation protocol](docs/evaluation/gateway-discovery-evaluation-protocol.md).

The initial request-understanding turn now uses the ADR 0017 semantic boundary:

`raw request -> ParsedRequest -> ClarificationDecision`

One LLM receiver reads the complete request and emits grounded semantic facts plus generic
calendar operations. Deterministic code validates source grounding, computes calendar dates,
applies one-way/cash policy, and derives clarification. The legacy scanner/selector workflow is
historical evidence, not a live fallback. The bounded 2026-09-11 live diagnostic is not
qualification-ready: 46 of 57 runs became safe pending results after post-inference structured
proposal validation failures. See [ADR 0017](docs/adr/0017-llm-owned-initial-intent-semantics.md)
and `evals/intent/baseline/2026-09-11-intent-behavior-v1-gpt-5.6-luna-3-trials-redesign.json`.

## Intended workflow

The eventual workflow is:

`Raw request -> Parse request -> Clarify constraints -> Plan searches -> Run provider tools -> Normalize and validate -> Rank candidates -> Explain recommendations`

## Repository map

- `src/award_agent/`: Python package boundaries for the request-understanding slice and later workflow stages.
- `tests/`: unit, integration, and fixture directories.
- `evals/intent/`: frozen intent-evaluation scenarios and historical/current baselines.
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

To run the optional local clarification harness, install `.[harness]` as well.

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

## Local clarification harness

Install the optional dependency and run:

```bash
python -m pip install -e ".[harness]"
streamlit run apps/clarification_harness.py
```

The harness is an ephemeral local validation surface. Its preferred path starts
from a raw travel request: select explicit initial-extraction, temporal-selector,
clarification-interpreter, and prompt-composer models; enter a reference date and
IANA timezone; then click **Understand request and start session**. That single
explicit form event
runs the frozen public initial workflow and passes its resulting
`RequestUnderstandingResult` to `start_clarification()`. A collapsible JSON
input remains available for replaying an existing frozen snapshot.

The session view shows the prompt composition source, authoritative issue records,
active assumption disclosures, next clarification prompt, active typed blockers,
status, terminal reason when applicable, and the current session JSON. Assumptions
remain visible after the session reaches `ready`. Answers remain in their form
after an error, which is displayed immediately and leaves the stored session at
its prior revision.

The harness loads the repository-local, gitignored `.env` using the existing
`python-dotenv` dependency. Put `OPENAI_API_KEY` there; it is not copied into
source code, session state, session JSON, or UI output.

It stores the session, surfaced errors, and additional local diagnostics only in
Streamlit `session_state`.
The interpreter and post-reduction prompt composer are constructed and invoked
only inside explicit raw-start, frozen-JSON-start, or answer-submit events, so
ordinary Streamlit reruns cannot invoke a model. The initial models likewise run
only inside the separate initial-request submit event. No request context,
resolved dates, effective request, ledger, or session limits are sent to the
clarification models: the interpreter receives only its answer message and active
typed blockers plus date-free temporal catalogs, while the composer receives only
authoritative active blockers and post-reduction issue records. Responses storage
is disabled.
Aggregate interpreter/composer call counts, usage, latency, and error status are
captured per explicit event outside the domain session. Exact model-facing traces
are labeled private/local and are not shown in the public session JSON.
There are no travel-search or inventory-provider calls. A named U.S. federal
holiday in the initial request may use the existing Nager calendar boundary.
This harness has no persistence, deployment behavior, or UI-owned workflow
policy.

Live clarification evaluations always save full private model-call trace sidecars
under `evals/clarification/traces/`; that directory is gitignored. Their public
JSON artifacts remain redacted and contain only aggregate telemetry and trace
run metadata.

## Parse a request

Copy `.env.example` to `.env` and set `OPENAI_API_KEY`. The offline test suite
does not load or require it. Model selection is explicit per workflow run and is
never read from an environment variable.

Run the request-understanding workflow with an explicit temporal context:

```bash
award-intent \
  --model gpt-5.6-luna \
  --reference-date 2026-08-29 \
  --timezone America/Los_Angeles \
  "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend for about 10 days."
```

The command prints the completed request result or a typed non-session pending result. One model
receives the request language and returns grounded semantic facts plus generic calendar operations;
deterministic code validates and calculates dates without scanning the wording. The workflow does
not persist requests locally. Holiday anchors use the public Nager.Holidays Community API v4 for
U.S. federal-holiday dates. A provider failure becomes typed pending rather than a locally guessed
date.

Application and evaluation code select models by constructing an extractor
configuration. This makes model candidates ordinary test data:

```python
from award_agent.intent import OpenAISemanticIntentConfig, OpenAISemanticIntentInterpreter

interpreter = OpenAISemanticIntentInterpreter(
    config=OpenAISemanticIntentConfig(model="gpt-5.6-luna")
)
```

The receiver configuration makes the model boundary observable without process-level
configuration. The live decision is recorded in ADR 0017; ADR 0010 is historical comparison
evidence.

## Current non-goals

- Point-balance constraints
- Spending-budget constraints
- Provider integrations
- Provider-result normalization and validation
- Ranking
- RAG
- Production Web UI
- Authentication
- Persistence
- Multi-agent orchestration
- Deployment infrastructure

Travel-provider integrations have not yet been implemented. Nager.Holidays is used only for
holiday-calendar support inside request understanding. Measured results will be recorded only after
real runs, not inferred from scaffold-only setup.

The living design workbook is at `/Users/shawnkang/bots/workbook_formatted.md`. It is a design aid for broader product context; repository docs and ADRs capture implementation-specific decisions and superseding boundaries.
