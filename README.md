# Award Travel Agent

Award Travel Agent is an independent portfolio project for building a narrow, measurable award-search workflow that turns vague travel requests into grounded, traceable recommendations. The request-understanding slice is implemented and frozen behind explicit interfaces and evaluation cases; later work can build the downstream search workflow on that boundary.

See [DEFERRED.md](DEFERRED.md) for work intentionally parked until the core workflow
is complete, its revisit triggers, and prerequisites that must be met before
making broader claims. The [pre-2C architecture and engineering review](docs/reviews/2026-09-19-search-planning-architecture-review.md)
records the design input used for the implemented compiler; recommendations outside the accepted
2C boundary remain advisory.
For proposed goals, completion evidence, and sequencing for each remaining stage, read
[Future stage goals](docs/reviews/2026-09-19-future-stage-goals.md). This is advisory;
it does not open implementation work.

## Current milestone

The search-planning stage is complete and owner-closed as of 2026-09-21. Milestones 1, 2A, 2B, and
2C are implemented and owner-qualified for their declared planning boundaries; Milestone 0 is
retired. The next separately scoped work is provider/result execution under ADR 0022, which consumes
the frozen `CompiledSearchPlan` rather than extending planning.

Milestone 2B gateway-airport discovery is implemented and owner-closed. Milestone 2C deterministic
search-strategy compilation is implemented in place, with no V1 compatibility path. Its integrated
live diagnostic is model-only: the compiler itself makes no additional model call, and neither the
compiler nor the diagnostic calls a travel provider. The completed search-planning milestones are
owner-monitored, owner-reviewed, and owner-qualified for their declared planning boundaries; no
independent external/holdout, provider/product, itinerary, or recommendation qualification is claimed.

The frozen upstream boundary uses one-way award-only request semantics. A ready request requires
origin, destination, an outbound departure window, and traveler
count. Return dates and durations receive visible guidance to submit a separate one-way request;
cash-only requests are unsupported; mixed award-and-cash requests remain eligible for award search
without implying cash pricing is available. The deterministic, retrieval-backed
`EffectiveRequest -> CompiledSearchPlan` boundary is implemented and offline verified for its declared checked-in
fixture coverage. Milestone 1 supplied the reviewed, versioned local GeoNames/OurAirports catalog.
Milestone 2A's bounded model-proposed endpoint-airport selection is the owner-adopted official
source for exactly resolved geographic entities as of 2026-09-21. Explicit and uniquely resolved
named airports remain direct catalog singletons. The selector retains model-proposed provenance;
independent human- or holdout corroboration is not claimed and may inform future policy revision.
ADR 0023 also retires the executable Milestone 0 JSON
and reviewed-group compatibility path. The
implemented 2B boundary uses an approved versioned global planning-market policy and selects one grouped
structured model proposal for bounded, explainable gateway candidates. Same-market skipping is
allowed only when every original endpoint is known and their market union has size one; mapping
gaps force generation, and model/policy market disagreements remain advisory for 2C. Candidates
remain unverified search hypotheses. Access gateways may be materially complementary departure or
arrival alternatives even for already-strong endpoints, but must have specific incremental value;
size, proximity, shared market, or diversity alone is insufficient. The independently bounded pools
are 0–2 origin access, 0–2 destination access, and 0–5 hubs (nine total maximum), with no
intermediate-market diversity quota. The prompt-v5/casebook-v2 and first prompt-v5/casebook-v3 runs are
historical diagnostics, not semantic qualification. The final prompt-v6/casebook-v3 run recorded 46
case-trials and 42/42 calls across two trials, with 82 accepted candidates, 43 scopes, and 400 accepted
relationships; one PNH catalog-absence rejection and three market-mismatch advisories were retained.
The provider-neutral compiler preserves pair-level logical coverage; grouped provider requests are
a downstream projection. Provider execution remains later, including Seats.aero API calls, provider
payload mapping, result normalization, and ranking. See the
[search-planning stage brief](docs/handoffs/2026-09-10-search-plan-design-stage.md) and
[`ADR 0016`](docs/adr/0016-one-way-award-request-boundary.md),
[`ADR 0020`](docs/adr/0020-market-aware-model-proposed-gateway-candidates.md),
[`ADR 0021`](docs/adr/0021-deterministic-search-strategy-compilation.md), plus the
[`ADR 0023`](docs/adr/0023-adopt-m2a-and-retire-m0-endpoint-selection.md), plus the
[completed search-planning milestone record](docs/handoffs/2026-09-13-search-planning-milestone-roadmap.md) and
[Milestone 2B implementation brief](docs/handoffs/2026-09-17-m2b-gateway-airport-discovery-opened.md), and the
[2B evaluation protocol](docs/evaluation/gateway-discovery-evaluation-protocol.md). The durable
[Milestone 2B closeout](docs/handoffs/2026-09-19-m2b-gateway-airport-discovery-closeout.md) records
the final design, evidence, limitations, and later-stage inheritances. The
[Milestone 2C implementation record](docs/build-log/2026-09-19-m2c-implementation.md) records the
initial compiler boundary, verification, and model-only integrated diagnostic. The active
[provider-neutral revision](docs/build-log/2026-09-20-m2c-provider-neutral-revision.md) removes
provider capability and provisional execution-shaped allocation limits from 2C, retaining only the
all-or-nothing 100-pair compiler structural guard.

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
