# 2026-09-19: Fresh-context Astra challenge of the pre-2C review

## Request and scope

The owner requested another Astra agent with fresh context to contest the
existing findings and recommendations, followed by parent-led revisions.
The agent used `gpt-6-astra`, a fresh context (`fork_turns=none`), and repository
artifacts as evidence. It performed read-only inspection and no tests or live
calls. The parent integrated the challenge, checked specific source paths,
and revised the existing review/register rather than creating another design.

No runtime code, ADR, roadmap, prompt, fixture, catalog, or external workbook
changed. Implementation recommendations remain advisory, not owner-adopted.

## Challenge disposition

| Challenge | Parent disposition |
| --- | --- |
| Unrestricted hub components imply a potentially large assembly problem | Accepted. Keep explicit market-query semantics; first provider pilot validates provider-returned itineraries and labels incomplete access/hub components as research leads. Cross-query assembly is new deferred entry D15. Component hits cannot count as completed-journey lift. |
| User/provider feedback arrives too late | Accepted. Propose an owner mock/replay walkthrough before full 2C qualification, followed by a narrow provider pilot. Existing access is evidenced; trip-detail/error semantics still need a targeted, separately opened experiment. |
| Historical ambiguous-return failures were overstated as current defects | Corrected. ADR 0015's three unsafe cases were `bare_return_endpoint`; ADR 0016 changed supported scope. Current qualification remains missing, but persistence of the old failure has not been demonstrated. |
| Handoff requirements became prerequisites for any demonstration | Narrowed. Privacy/honest labels apply to shared evidence; reproducibility gates apply to reproducibility claims. The six engineering demonstrations are options, not a new completion checklist. |
| G → A composition was described as requiring a new 2B contract | Corrected. A future versioned compiler rule could derive a hypothesis with both source relationships; exclusion is first-slice scope control. |
| RAG/coverage were described as unconditional roadmap work | Corrected. Existing M3/M4 are evidence-driven; earlier provider feedback is the actual sequencing proposal. Human knowledge authoring and runtime retrieval remain distinct. |
| Compiler caps were treated as pre-replay resource bounds | Corrected. Replay eagerly forms finite scope products; distinguish input, replay, and compiler-output bounds. Measure saturation before proposing extra machinery. |
| Portability/retry findings could invite excessive infrastructure | Findings retained; remedies narrowed to documented artifact acquisition, explicit finite adapter policies, and focused exhaustion/partial-result tests. No execution platform prerequisite. |

Core conclusions retained: zero-model-call deterministic 2C; mandatory selected
endpoint coverage with explicit overflow; pinned provenance; semantic query
deduplication; omission receipts; distinction between hypotheses, queries,
HTTP work, and observations; no promotion into route facts or itinerary claims.
Use compatible pilot endpoints now, not a new general admission subsystem.

## Parent evidence checks

- Read ADR-0015 closeout, ADR 0016, the one-way recut diagnostic, and current
  controller handling to separate historical failures from current guarantees.
- Inspected `gateway_discovery.py`'s per-scope Cartesian materialization and
  `gateway_generator.py`'s finite structural limits: 20 pool entries, 40 scopes,
  and 40 references per side. No saturation benchmark or performance failure
  is claimed.
- Read the roadmap's M3 comparative gate and evidence-driven M4 scope.
- Inspected capability verification: the earlier tracked-export failure is a
  demonstrated dependency of the golden CLI, not proof all planner paths fail.
- Ran `.venv/bin/mypy src`: **49 errors in 6 files; 96 source files checked**.
  Errors include three legacy temporal modules and three evaluation modules.
  This qualifies the earlier 266-error `src tests` result: failures are not
  solely historical tests. No type fixes were attempted.
- A read-only AST import scan of 96 source files found no static imports of
  `clarification.temporal`, `temporal_templates`, or `temporal_approximations`.
  This does not rule out dynamic use or establish runtime correctness.

No new model/provider evaluation or full pytest run was performed. Earlier
passing focused checks remain historical evidence for those exact commands.

## Documentation changes

- Revised the [architecture/engineering review](../reviews/2026-09-19-search-planning-architecture-review.md)
  in place, including factual corrections, pilot scope, sequencing, and type-check evidence.
- Updated [DEFERRED.md](../../DEFERRED.md): early feedback, proportional gates,
  stable existing IDs, D15 assembly decision, and partial disposition of bundled options.
- Added a short project-state pointer to this challenge record.

Owner acceptance/rejection of the implementation recommendations: **not yet
recorded**. No outreach, provider requests, stage reopening, or feature adoption
was performed.

## Verification

Checked 59 local Markdown targets/anchors across the revised review, register,
and this log: all resolved. `git diff --check` passed for tracked changes;
`git diff --no-index --check /dev/null <file>` produced no whitespace errors
for these three new files (exit 1 denotes their expected content difference).
A targeted wording search found no remaining superseded retry-count,
relationship-contract, or unconditional-roadmap assertions in the review/register.
