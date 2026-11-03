# Results fast-profile change review at V30

2026-10-28. Reviewed all tracked and relevant untracked work against
`b7bedf5b13daab0ec0d170ba0b519877698ae0ff`. The [pinned inventory](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/review-scope.json)
contains 4,398 file hashes; both independent reviewers received the same tracked
patch, 89 text snapshots and verification evidence. Closing documentation is a
metadata-only addendum. Runtime and tests were unchanged after the stop.

**No candidate qualified as the default or closed the current M2 revision.**
Latest opt-in is V30; the public API/CLI remains provisionally V27. Nothing is
committed. No V31 or further paid calls followed the owner's stop.

## Changes and outcome

The fast path originally omitted correction to keep two calls. This work restores
one LOW full-document correction after actual recoverable mechanical failures.
Clean drafts still stop after two calls; there is no fourth call or SDK retry.
This repairs detected defects, not arbitrary factual errors in otherwise clean
prose.

The model retains selection and complete narrative ownership. Code supplies exact
selected records, temporal comparison facts, pair dossiers, traveler evidence and
original-currency quotes with unknown scope preserved. The full explorer remains
independent. Public API/CLI default routing and an owned shared SDK client were
added. Later profiles cap the pool at two non-benchmark references and one
benchmark. The incomplete selector gets all 378 leads in 13 lossless program
groups. V30 changes only its points-unit guidance; complete requests match V29.

| Final V30 scout | Seconds | Facts / usefulness / M2 composition | Comparative depth |
| --- | ---: | --- | --- |
| Admitted | 16.38 | pass / pass / pass | decision-rich |
| Conditional | 12.29 | pass / pass / pass | basic |
| Incomplete | 11.06 | pass / pass / pass | basic |

The failed scout gate prevented V30 confirmation and live correction measurement.
Earlier V23's six answers passed H/U/M2 but only five were decision-rich; its
controlled correction took 18.73s. V27's confirmation passed H only 3/6; its
source-passing correction took 26.23s. These are historical evidence, not V30
qualification. All 254 generation and 254 input-count reservations remain, with
failures and adjudications preserved. No provider or live FX calls were made.

## Standards

**Zero hard violations; two Fowler-baseline heuristics.** Historical replay
support itself is justified.

- **P2 — Repeated Switches / Shotgun Surgery.** [CLI mapping](../../src/award_agent/cli/results.py:203)
  duplicates profile/branch policy from [runtime](../../src/award_agent/results/focused_comparison_runtime.py:302).
  Replay and packet/wire modules separately encode settings and caps. A profile
  change needs synchronized edits across several paths. Use one immutable,
  versioned policy definition while preserving independent acceptance tests.
- **P3 — Duplicated Code.** Measurement, receipt/digest validation, context limits
  and failure bookkeeping repeat in [comparison runtime](../../src/award_agent/results/focused_comparison_runtime.py:219),
  [patch runtime](../../src/award_agent/results/focused_patch_runtime.py:187) and
  [focused execution](../../src/award_agent/results/focused.py:261). Extract shared
  scaffolding while keeping version-specific decoding and outcomes explicit.

These are maintainability judgments, not documented-rule breaches.

## Spec

**Four P2 findings:** three unmet acceptance goals and one evidence-tooling defect.
No unasked product scope was established.

- **Factual acceptance remains unmet.** The provisional V27 cohort passed H only
  3/6. [q108](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/review-bundles/q108/review.md)
  calls Hong Kong earliest although shown Taipei arrives 550 minutes earlier.
  Mechanical cleanliness cannot close this gate; numerical prose remains trusted.
- **Comparative depth remains unmet.** V30 is rich in only 1/3 cases. q120 gives
  no authored offsetting benefit; q121 displays one lead without meaningful
  comparison despite nonsparse source. This is an argument-quality gap, not a
  minimum-option quota.
- **Correction latency remains unmet.** V27's actual correction takes 26.23s;
  V30 correction latency is unmeasured. The target includes correction and checks.
  Stopping rather than making extra calls respects the owner's ceiling.
- **Verifier-contract mismatch.** [verify.py](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/verify.py:112)
  rejects valid empty pairs for one option. The audit finds four assumptions
  behind seven flags, also involving fault identity, valid failed-selection
  termination and complete-branch guidance. This is not runtime corruption.

## Verification and limits

The full Results baseline passed 434 tests before V24. Later variants passed
bounded branch/cap/source-identity/recovery/replay/CLI checks; V30 had eight
targeted cases plus four independent checks. Parent mypy passed all 43 Results/CLI
source files; scoped Ruff and `git diff --check` passed. The full repository suite
was not rerun. Its prior run had two gfly environment failures; provider code was
unchanged.

The final `verify.py --verify` command exited 1. All 109 summarized artifacts
reached exact replay equality; [seven strict flags](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/verification-v30-final.json)
are classified as [four verifier defects](../../evidence/results-stage/m2/structured/2026-10-28-fast-default/verification-v30-audit.json).
An extra post-persistence failed V27 attempt has no summary, remains outside 109,
and was separately replayed and source-reviewed as q107. The strict verifier is
left unchanged and red. No strict-pass, population reliability, application SLA,
owner presentation acceptance or M3 claim follows.

**Counts: Standards 2 heuristics (worst P2); Spec 4 findings (worst P2).**
