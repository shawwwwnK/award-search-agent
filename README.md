# Award Travel Agent

Award Travel Agent is an independent portfolio project for building a narrow, measurable award-search workflow that turns vague travel requests into grounded, traceable recommendations. The request-understanding slice is implemented and frozen behind explicit interfaces and evaluation cases; later work can build the downstream search workflow on that boundary.

## Current milestone

Iterative clarification continuation — implementation active.

The current work is to add an additive session boundary after the frozen initial turn. Each
clarification prompt will list every current blocking requirement; a user may resolve any subset,
and the session will recompute the remaining blockers until it is ready or explicitly stopped.
It uses a conversation-aware `EffectiveRequest` with turn-level provenance and does not mutate the
initial `ParsedRequest`. A local Streamlit harness is allowed only for validation; it is not a
production UI. The decision is recorded in ADR 0011.

The implementation handoff, including step-by-step scope, invariants, code entry points, and
acceptance gates, is
[`docs/handoffs/2026-09-08-clarification-continuation-implementation-plan.md`](docs/handoffs/2026-09-08-clarification-continuation-implementation-plan.md).

The initial request-understanding turn remains qualified and frozen:

`raw request -> ParsedRequest -> ClarificationDecision`

The sole live implementation is selector-only: Luna performs non-temporal Pass 1 and opaque
temporal-candidate selection, while deterministic code scans, validates, compiles, evaluates, and
clarifies temporal facts. Sequential two-pass resolution has been retired. The final qualification
record is the traced three-trial Luna run at
`evals/intent/baseline/2026-09-06-gpt-5.6-luna-selector-only-prompt-repair-3-trials.json`:
47/48 records passed (97.92%), with zero errors and one documented clarification miss. The owner
has approved the additive clarification-continuation contract in ADR 0011; the existing parser,
selector, compiler, clarification policy, and ready corpus remain unchanged.

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
  --selector-model gpt-5.6-luna \
  --reference-date 2026-08-29 \
  --timezone America/Los_Angeles \
  "My boyfriend and I want to go to Thailand from SF leaving on Labor Day weekend for about 10 days."
```

The command prints `ParsedRequest` and `ClarificationDecision` as JSON. It uses a strict
non-temporal model boundary, deterministically scans and compiles temporal candidates, then uses
a separately configured model to select only opaque candidate handles. There is no model-authored
date-resolution pass or fallback. Both model responses request storage disabled; the workflow does
not persist requests locally. Holiday anchors use the public Nager.Holidays Community API v4 for
U.S. federal-holiday dates. Exact-date and month anchors do not make that API call. Holiday API
failures are returned as explicit errors rather than silently replaced with locally guessed dates.

Application and evaluation code select models by constructing an extractor
configuration. This makes model candidates ordinary test data:

```python
from award_agent.intent import OpenAIExtractorConfig, OpenAIIntentExtractor

pass_one = OpenAIIntentExtractor(config=OpenAIExtractorConfig(model="gpt-5.6-luna"))
selector = OpenAIIntentExtractor(config=OpenAIExtractorConfig(model="gpt-5.6-luna"))
```

The two configurations make the two model boundaries independently observable without changing
process-level configuration. The selector-only decision and historical comparison evidence are
recorded in ADR 0010.

## Current non-goals

- Point-balance constraints
- Spending-budget constraints
- Search planning
- Provider integrations
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
