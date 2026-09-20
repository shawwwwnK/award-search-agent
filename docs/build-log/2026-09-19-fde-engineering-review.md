# 2026-09-19: Engineering evidence review and deferred-work register

## Owner request and scope

The owner requested a second inspection focused on engineering proof for FDE
recruiting, additions to the existing detailed review, a concise chat summary,
and a maintained root-level list of work to revisit after completing the core
workflow. The owner explicitly requested agents to inspect build logs and
critical parent-led analysis.

Three investigators reviewed engineering tooling and historical/planning
deferrals. The parent inspected implementation and workbook evidence, ran two
targeted experiments, integrated recommendations, and edited documentation.
No implementation, prompt, fixture, catalog, or external workbook changed.

## Concrete findings and checks

### Tracked-tree portability probe

Exported tracked `HEAD` (`5219c99`) with `git archive` into
`/private/tmp/award-search-fde-review.kmgdKr`, then ran:

```text
PYTHONPATH=src /Users/shawnkang/bots/award-search/.venv/bin/python -m award_agent.cli.search_planning_eval
```

Result: exit 1, `ValueError: capability source
'seats-aero-cached-search-local-2026-09-08' does not name a local regular file`.
The pinned capability source is inside ignored `.provider-docs`; it is present
in the working directory but absent from tracked source. This is an observed
handoff dependency, not a reason to bypass evidence hashes. The experiment
reused installed dependencies, so it is not a clean installation benchmark.
The temporary export remains available; no user data or private trace was removed.

### Offline transport attempt probe

Used `OpenAI(api_key='offline-review-placeholder',
http_client=httpx.Client(transport=httpx.MockTransport(handler)))`; the handler
returned only synthetic 429 responses. A single `responses.create` invocation
made three in-process HTTP attempts and ended with `RateLimitError`.

Observed installed SDK: `1.109.1`; default `max_retries=2`; timeout
`Timeout(connect=5.0, read=600, write=600, pool=600)`. No external request or
real credential was used. These are installed-default observations, not a claim
about every injected client or the number of HTTP attempts in past live evals.

This supports a recommendation to distinguish proposal count, semantic repair,
transport retries, pagination, and whole-workflow deadline/attempt budgets.

### Investigator checks

- `.venv/bin/ruff check .`: passed.
- `.venv/bin/mypy src tests`: failed, 266 errors in 14 files, including
  historical tests and test fakes. No typing fixes were attempted.
- `.venv/bin/ruff format --check .`: failed on existing formatting drift;
  formatting is not a newly imposed gate and no exact new count is claimed.
- Full `.venv/bin/pytest -q` was started twice by the investigator. No terminal
  results were recovered; no current full-suite pass count is claimed. A later
  parent process check found no remaining pytest processes. This does not recover
  exit status or validate the prior recorded 507-pass/99-skip result anew.
- No tracked CI workflow or dependency lock was found. The existing bounded
  dependency ranges are not a reproducible environment lock.

The prior review's focused passing tests and ten-case local golden result remain
recorded in `2026-09-19-pre-m2c-architecture-review.md`; they were not relabeled
clean-checkout or full-suite qualification.

## Documentation delivered

- Extended `docs/reviews/2026-09-19-search-planning-architecture-review.md` with
  engineering strengths, measured gaps, six high-signal demonstrations, and
  staged recommendations.
- Created root `DEFERRED.md`: seven claim-specific gates, fourteen parked/proposed
  entries, source links, revisit triggers, closure evidence, explicit non-goals,
  completed/superseded exclusions, and disposition/maintenance rules.
- Added upkeep instructions to `AGENTS.md` and discovery links in `README.md`.
- Replaced the obsolete broad deferred list in `docs/project-state.md` with the
  new register and recorded the owner-requested review.
- Updated `docs/workboard.md` to point to the review/register without duplicating
  a long-range backlog or claiming implementation has begun.

The register uses “first complete core workflow” as an organizational definition:
a supported one-way award flow reaches observed, validated, source-linked output
with bounded work and truthful partial/empty outcomes. This does not approve
changing the roadmap, adopting 2A, reopening 2B, or deploying the project.

## Recommendations versus owner decisions

- Owner decision: perform the engineering review and maintain a root deferred register.
- Proposed engineering priorities: portable verification, explicit attempt/deadline
  policy, coherent active quality gates, failure injection, and end-to-end lineage.
- Proposed post-core proof: a handoff exercise, a real user observation, an
  incremental-value experiment, and a concise evidence index.
- Owner adoption or rejection of those implementation recommendations: **not yet recorded**.
- No claim of customer adoption, deployment, production scale, or current full-suite success.

## Final documentation verification

Checked 55 local Markdown targets/anchors in the root register and expanded
review: all resolved. `git diff --check` passed; `git diff --no-index --check`
against `/dev/null` reported no whitespace issues for the new register, review,
and this log (exit 1 denotes the expected file difference). An investigator's
final register consistency review found no obsolete resurrected work, falsely
approved recommendations, or missing source-scope distinctions requiring correction.
Runtime tests were not added for these documentation edits.
