# 2026-09-27: Ranking M1 live evidence run (positioning-permitted mixed journey)

## Goal

Close the Ranking M1 review's evidence gap — no live admitted mixed journey — with the
bounded pipeline the owner approved in this conversation: a new upstream case with explicit
positioning permission, bounded Seats.aero + pinned `gfly` execution, M1 matching, corpus
ingestion, and documentation. The owner had separately approved recording the gfly
provider-returned `adults` query echo as returned-traveler evidence; that adapter change
(from the prior session, `0.3.0+award-search-unpriced-party-echo-v2`) is landing with this
run.

## What ran

- The intent-to-planning harness is SHA-pinned to the 19-case intent corpus, so the new case
  went through the integrated casebook harness (`award-search-planning-live-eval`), which pins
  policy/catalog identities but accepts a custom casebook through `--casebook`. The
  purpose-built casebook (`evals/search_planning_live/casebook-ranking-m1-evidence.yaml`)
  contains one case: `sfo_to_bkk_positioning_permitted`, SFO→BKK, October 5, 2026, one
  traveler, economy, award-and-cash intent with "permits positioning flights" wording. The
  casebook contract requires a non-empty cabin list, so the case declares economy rather
  than mirroring the no-cabin mixed corpus case.
- First live attempt (05:22Z) extracted the intended request — travelers 1, economy, modes
  `[award, cash]`, `repositioning_allowed=True`, exact single-day window — and a gateway
  proposal including LAX origin access, but M2C refused to compile with
  "gateway outbound date input differs from EffectiveRequest". Root cause:
  `search_planning_live.py` hardcoded `effective_window_precision="window"` in the gateway
  input, while the compiler's replay binding requires the request's actual precision; every
  reviewed casebook case was a multi-day window, so exact single-day cases had never run
  through this harness. The failed run's baseline artifact and private traces are retained
  as the honest record.
- Fix: project the gateway outbound date from the validated ready request, mirroring the
  intent-to-planning harness; behavior-identical for all reviewed window cases. Added the
  regression test `test_exact_single_day_case_compiles_through_gateway_replay`.
- Second run (05:35Z): mechanical completion, but that trial's gateway proposal accepted only
  TPE/HKG hubs — live sampling variance, since the earlier proposal did include LAX access.
  A two-trial run inside the reviewed bound (05:37Z) provided two samples: trial 1 again had
  no origin access; trial 2 accepted LAX origin access, an HKG hub, and SIN destination
  access. Per the pre-set decision rule (first trial whose plan carries the origin-access
  dependency), trial 2 — session `live:sfo_to_bkk_positioning_permitted:2` — became the
  frozen planning input.
- Provider bundle `ranking-stage-2026-09-27-positioning-permitted-v2` embeds the current
  policy, the reviewed award capability, and the v2 cash capability that records the
  provider-returned party echo. The bounded live execution made 10 transport calls (award
  summary/detail calls under the two-detail-call priority policy, three cash requests
  including both activated access-cash searches) and returned status `partial`:
  115 observations, 73 coverage units.
- M1 matching under the then-current `m1-v1` rules assembled 123 journeys: 64 conditional,
  58 rejected, 1 research lead, 0 admitted. Blocker analysis on the five destination-side
  candidates (aeroplan SFO→TPE→SIN award joined to SIN→BKK cash positioning) showed every
  requirement dimension passing except per-leg cabin: the `cached-search-v1` adapter does not
  map `AvailabilitySegments[].Cabin`, although the Seats.aero detail source returns it
  ("economy" per segment, with per-segment fare classes).

## Owner decisions recorded in this session (2026-09-27)

- Keep the Seats.aero adapter unchanged and relax the M1 rule instead: a confirmed, matching
  journey-level cabin is accepted when award legs do not report their own cabin. This is
  matching policy `m1-v2`; unreported legs stay visible as non-blocking `cabin`-dimension
  reasons, and a leg that does report an out-of-request cabin still rejects the journey.
- Live re-run outcomes are accepted as observed, without re-rolling inventory. No provider
  re-run was needed after the rule change; the September 27 capture stands.

## Results

- Matching policy `m1-v2` on the new run: 123 journeys — 5 admitted, 59 conditional,
  58 rejected, 1 research lead. The five admitted are the first live admitted mixed
  journeys: `award_cash_egress` topology joining the two-seat aeroplan SFO→TPE→SIN economy
  award to SIN→BKK cash positioning whose party echo is recorded as returned-traveler
  evidence, with resolved positioning permission and transfers of 230–535 minutes passing
  the two-hour and same-or-next-local-day rules. Per-leg cabins are unreported and accepted
  at journey level; price scope remains incomplete; admission is not a booking or
  availability guarantee.
- The two September 25 saved M1 outputs were regenerated under `m1-v2`: `mixed_access` is
  unchanged apart from the policy-version field; `exact_business` changes only the leg-cabin
  reason code and dimension (792 occurrences of `award_leg_cabin_unreported` replacing
  `award_leg_cabin_unknown`), with the status distribution unchanged (0/106/290). The
  regenerated outputs replace the saved files and the M1 README digests are updated.
- The provider run entered the saved-search corpus as `sfo_to_bkk_positioning`; the full
  corpus verifies with byte-exact replay of every run (3 runs, 549 observations). The frozen
  planning input is preserved in
  `trace-inputs/sfo_to_bkk_positioning_permitted.json`, and the trace-input mapping records
  its source records and trial-2 selection.

## Commands and tests

- `award-search-planning-live-eval`: preflight, the 1-trial failed run, the 1-trial fixed
  run, and the 2-trial fixed run; artifacts under
  `evals/search_planning_live/baseline/2026-09-27-gpt-5.6-luna-sfo-to-bkk-positioning-permitted-*`.
- `award-provider-results --mode live` with the pinned gfly environment;
  `scripts/provider_plan_corpus.py add` and `verify` (byte-exact replay of all three runs).
- `award-ranking-match` on the new run under both matching policies, plus regeneration of
  both saved September 25 outputs under `m1-v2`.
- Tests: 13 passing in `test_search_planning_live_eval.py` (including the exact-day
  regression), 48 passing across the ranking M1 suites (including the new corpus-case row
  and the two new cabin-rule tests), and the full scoped gate recorded in the session
  summary before commit.

## Files changed

- `src/award_agent/evaluation/search_planning_live.py` — gateway outbound date projected
  from the validated request (exact single-day fix).
- `src/award_agent/ranking/contracts.py` — `cabin` reason dimension added; matching policy
  version `m1-v2` (`m1-v1` remains a valid historical value on saved outputs).
- `src/award_agent/ranking/matching.py` — journey-level cabin acceptance for unreported
  leg cabins under `m1-v2`.
- Party-echo change landing with this evidence run: `src/award_agent/providers/gfly.py`,
  `src/award_agent/cli/provider_results.py`, `scripts/gfly_compat.py`,
  `data/provider_capabilities/provider-stage-current.json`,
  `tests/unit/test_provider_adapters.py`.
- Tests: `tests/unit/test_search_planning_live_eval.py`,
  `tests/unit/test_ranking_m1.py`, `tests/unit/test_ranking_m1_corpus.py`.
- Evidence and corpus: `runs/sfo_to_bkk_positioning/`,
  `trace-inputs/sfo_to_bkk_positioning_permitted.json`, the trace-input mapping, both
  READMEs, the two regenerated M1 outputs, and the new
  `evidence/ranking-stage/m1/sfo_to_bkk_positioning.json`.

## Observed limits (unchanged claims)

Turkish award observations still carry unknown seats and returned-traveler evidence, so the
origin-side (SFO→LAX cash + LAX→BKK award) journeys remain conditional for that documented
reason. The mandatory direct SFO→BKK award query was not detailed in this run — both
detail calls went to access legs under the priority policy — so this run has no
`direct_award` journeys. Cash price scope, bookability, and provider qualification remain
unclaimed.
