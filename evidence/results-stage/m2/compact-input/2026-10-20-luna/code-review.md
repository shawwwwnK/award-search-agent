# Compact Results implementation review

Scope: current-branch Results changes, including the pre-existing V4 presentation prerequisite, new V5 compact authoring, bounded evaluation scripts, tests and the accepted plan. The initial captured tracked diff and untracked source listing were retained locally at `/private/tmp/results-compact-code-review/`. Reviews were read-only and independent of implementation; no external model CLI was invoked.

## Standards

The reviewer found one concrete current-document conflict: the usage guide still described V4 as the new-run default while code used V5. The final documentation pass corrected the version description and replaced pending implementation statements with measured status.

Two nonblocking smell judgments concerned repeated version feature checks and repeated leg-cabin formatting. They were left unchanged: the latter belongs to the pre-existing V4 prerequisite, and neither finding established a defect requiring an incidental refactor in this change. Historical behavior remains explicit.

Final disposition: the documented-standard conflict is resolved; two nonblocking maintenance judgments remain acknowledged, without a new cleanup commitment.

## Spec

The reviewer found no confirmed runtime requirement defect or scope creep. The initial review identified two pending evidence obligations: the field-disposition manifest and separate reduction-direction accounting. Both are now retained in `field-disposition.md` and `offline-measurement.json`. Counterfactual savings are explicitly nonadditive simulations, separate from the authoritative combined before/after measurement.

Independent canonical preservation probes initially exposed omitted component findings. The corrected writer view retains those warnings; the rerun and negative controls pass. Both complete cases preserve 116 factored pairs and all original eligible members.

Final disposition: planned evidence obligations are resolved; answer quality remains bounded diagnostic evidence rather than owner acceptance.

## Post-live replay correction

Actual live-artifact replay exposed a V5 incomplete-case finding-order defect under hash seed 37. The implementor reproduced it before fixing it. An independent architect identified the same set traversal and reviewed the final narrow change against the immutable live source ZIP.

Only V5 now sorts the benchmark/incomplete reference traversal. V1–V4 retain their original behavior. Saved findings still require strict equality; reversed findings and changed finding text remain rejected. The saved live source, requests, raw responses, artifacts and answers were not rewritten, and no paid rerun occurred.

`post-fix-replay-verification.json` records seven artifacts across seeds 11, 23 and 37. `post-fix-request-verification.json` confirms all five requests and all three live artifact hashes are unchanged. `replay-fix-source.json` identifies the sole post-live production change as `src/award_agent/results/core.py`.

## Verification and limits

Final Results/evaluation/harness acceptance: 162 tests passed in 172.36 seconds. Scoped mypy checked 11 files successfully; scoped Ruff and whitespace checks passed.

The repository-wide run before the final narrow replay correction completed with 878 passed, 99 skipped and the same two previously documented local gfly-environment failures. It is not reported as a passing full-suite run. The final targeted acceptance includes the new three-seed replay regression.

The independent live-answer review is retained in `answer-review.md`. The conditional answer has two attached validation notices and less cabin diversity than the saved comparison. Incomplete-lead wording has presentation defects. No broad selection-quality, semantic-truth or M2/M3 qualification follows from mechanical preservation and replay checks.
