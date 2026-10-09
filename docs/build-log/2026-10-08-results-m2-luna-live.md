# Results M2 Luna live diagnostic

Date: 2026-10-08. The owner selected Luna, delegated output/timeout selection and instructed
completion of the live diagnostic. Source is the three saved Ranking exports; this is Results
authoring over historical observations, not refreshed provider acquisition.

## Declared boundary

Run-specific model `gpt-6-luna`; output limit 16,384; authoring timeout 300 seconds;
zero SDK retries; `store=False`; truncation disabled. Physical context 1,050,000 tokens,
separate input ceiling 922,000, additional safety margin 2,048. At most two authoring calls per
case and six across three cases; no travel-provider calls. The initial preflight counter uses
120 seconds. The original positioning run uses the earlier byte guard, while the remaining
cases use exact model-specific count receipts. Both representations remain explicit.

The [run plan](../../evidence/results-stage/m2/2026-10-08-luna/run-plan.json) was saved before
authoring. Conservative generation cost ceiling is $1.30 using full uncached long-context prices;
actual usage is recorded in artifacts and will be summarized below. Counting endpoint billing
is not inferred.

The owner later lifted the campaign generation-call ceiling. A retained
[budget amendment](../../evidence/results-stage/m2/2026-10-08-luna/budget-amendment.json)
supersedes that original campaign cap; the per-run initial-plus-one-correction policy stays
unchanged. A guided three-case diagnostic adds explicit boundary-whitespace, unit-label and
claim-name reminders. Guidance remains run-specific and model layout remains free.

The first baseline and guided batches retained the original 16,384-token output reservation and
300-second timeout. A later bound batch and a final declared-claim batch used 32,768 output tokens
and 600 seconds. These settings are specific to those artifacts. The declared batch added
targeted reminders for literal claim text, exact scope IDs and grounded comparisons; this improved
some outputs but did not make the check catalog semantically complete.

## Context measurement and engineering correction

Complete exact initial inputs measured 217,190 tokens for positioning, 468,897 for exact business,
and 688,786 for mixed access. The corresponding original input byte measures are 601,136,
1,248,191 and 1,855,734. The latter two byte bounds cause conservative rejection despite actual
token fit; no alternatives were trimmed and the model window was not inflated.

Added an optional injected input measurer, shared exact request construction and digest-bound
per-attempt receipts. Each correction is counted separately, including its feedback and prior
draft. Counting failure is distinct from generation failure and does not trigger unmeasured
fallback. Replay validates retained count observations and request bindings offline, without
claiming independent retokenization. The default offline byte measurement remains available.

Two local preflight setup failures were observed: an incorrect root path prevented credential
loading before client construction, and an unparameterized `cast_to=dict` raised `ValueError`
in the installed SDK. Both were corrected; the failed count receipt remains saved. The exact
count endpoint is accessed with `cast_to=dict[str, object]`, without upgrading the SDK. No
credentials were printed or saved.

## Initial observed answer and notice-placement fix

The positioning case produced two recoverable drafts. The correction reduced 34 failed findings
to three omitted booking-obligation slots; it was delivered with concrete notices. Input usage
was 217,190 / 224,904 tokens; output usage 6,110 / 4,801 tokens; generation latencies 61.25 / 42.08
seconds. Exact replay of its original v1 artifact succeeded.

The read-only walkthrough found a real placement defect: adjacent authored parts concatenate a
paragraph and the next heading without a newline, and prose-notice insertion follows that line
past the original part boundary. A prior option's notice therefore appears beneath the next
heading. The bounded fix changes notice positioning while preserving the model's layout choices;
historical v1 artifacts retain their original replay bytes through explicit renderer versioning.
The original live answer remains immutable evidence, including its presentation defects.

Other visible review items include duplicated units (`65000 points points`), minor-unit currency
display, raw coverage codes, unexplained choice among many variants, and declared propositions
that remain unchecked. "Operated by" may be stronger than a generic `carriers` field; this is a
source-semantic review hypothesis, not an established provider defect. Mechanical check outcomes
do not establish paraphrase truth. M3 has not been run.

## Verification and final run evidence

All four retained batches are indexed in the
[evidence README](../../evidence/results-stage/m2/2026-10-08-luna/README.md) and
[index](../../evidence/results-stage/m2/2026-10-08-luna/index.json); the detailed
[summary](../../evidence/results-stage/m2/2026-10-08-luna/summary.json) covers all ten artifact/
Markdown pairs, each of which replayed exactly. Across 15 authoring calls, writer receipts recorded
6,444,535 input tokens, including 8,780 cached input tokens, and 108,897 output tokens, including
50,275 reasoning output tokens.
Estimated generation cost is $1.22769210 at the published Luna rates; count-endpoint billing is
not included or claimed. Batch-level estimated costs were $0.04966490 baseline, $0.40062300
guided, $0.26678944 bound, and $0.51061476 declared.

| Batch and case | Authoring calls | Input / output tokens | Delivery |
| --- | ---: | ---: | --- |
| Baseline positioning | 2 | 442,094 / 10,911 | Annotated; 3 notices |
| Guided positioning | 2 | 443,352 / 11,166 | Annotated; 62 notices |
| Guided exact business | 2 | 948,272 / 14,632 | Annotated; 70 notices |
| Guided mixed access | 1 | 688,942 / 16,384 | Incomplete response; no recoverable draft |
| Bound positioning | 1 | 217,724 / 8,100 | Clean mechanically; 0 notices |
| Bound exact business | 1 | 469,431 / 5,479 | Clean mechanically; 0 notices |
| Bound mixed access | 1 | 689,320 / 7,389 | Clean mechanically; 0 notices |
| Declared positioning | 1 | 218,110 / 6,540 | Clean mechanically; 0 notices |
| Declared exact business | 2 | 944,005 / 14,216 | Annotated; 1 notice |
| Declared mixed access | 2 | 1,383,285 / 14,080 | Annotated; 3 notices |

The first baseline positioning artifact was generated with the earlier byte gate; subsequent
guided, bound and declared runs retained exact full-request token-count receipts. The
[`run-plan.json`](../../evidence/results-stage/m2/2026-10-08-luna/run-plan.json) and per-run
configurations preserve each setting; `baseline.original.config.json` was derived later from the
embedded original configuration, not saved as a pre-run declaration.

All 10 saved answer artifacts replayed byte-for-byte. The three-case bound batch selected its
first drafts and delivered with no failed mechanical findings: positioning declared no claims, exact
business had three supported cabin claims, and mixed access had six unchecked claims. This is
not a claim that all prose was evaluated. In the declared batch, positioning declared nine
correctly scoped but unchecked propositions; exact business delivered its correction with one
`claim_not_visible` notice caused by terminal punctuation differing from the visible sentence;
mixed access delivered its correction with three `claim_scope_mismatch` notices for truncated
scope IDs. A clean mechanical result records only the checks exercised by the saved document.

Independent review found that the final declared exact-business departures and mixed-access routes
support their relative comparisons. Earlier bound answers included an exact-business comparison
of identical departures and a mixed-access claim of differing connection airports where the routes
were the same; those original artifacts remain preserved. The declared positioning answer also
described unknown cash-cabin evidence as carrier evidence. Declared exact-business retained one
`claim_not_visible` notice because the claim sentence ended in a period while visible text used a
semicolon. Declared mixed-access retained three `claim_scope_mismatch` notices after a truncated
journey ID was copied into claim scopes.

An independent Markdown parse confirms that the original baseline positioning has a glued
`observations.##` boundary and only one parsed heading; bound positioning and declared exact-business
and mixed-access each parse all five intended headings. Renderer v2 fixes local prose-notice
placement at the originating part boundary. It does not insert general separators or correct
authored prose. Other visible issues include raw coverage/booking codes, unclear minor-unit fees,
opaque benchmark IDs and unchecked claims. No M3 semantic evaluation or owner quality qualification
was performed.

Before M2 closeout, the checker/contract reconciliation recorded as G08 in
[`DEFERRED.md`](../../DEFERRED.md) remains required. The contract allows identical shared
disclosures once when applicability is clear, while the checker currently counts only same-journey
scoped slots. The rejected-alternative contract requires visible exclusion and reason, while the
checker also imposes the full journey disclosure set. No owner-approved waiver exists for those
other fields; this is not optional M3 cleanup.

Focused engineering verification passed with these scoped checks:

```sh
.venv/bin/python -m pytest -q tests/unit/test_results_adapter.py tests/unit/test_results_cli.py \
  tests/unit/test_results_evidence.py tests/unit/test_results_m2.py tests/unit/test_results_markdown.py \
  tests/unit/test_results_token_measurement.py tests/unit/test_results_notice_v2.py \
  --junitxml=/private/tmp/results-m2-live-focused.xml
.venv/bin/mypy src/award_agent/results src/award_agent/cli/results.py \
  tests/unit/test_results_token_measurement.py tests/unit/test_results_notice_v2.py \
  evidence/results-stage/m2/generate.py evidence/results-stage/m2/2026-10-08-luna/preflight.py \
  evidence/results-stage/m2/2026-10-08-luna/run.py
.venv/bin/ruff check src/award_agent/results src/award_agent/cli/results.py \
  tests/unit/test_results_token_measurement.py tests/unit/test_results_notice_v2.py \
  evidence/results-stage/m2/generate.py evidence/results-stage/m2/2026-10-08-luna/preflight.py \
  evidence/results-stage/m2/2026-10-08-luna/run.py
```

The test command reported 91 passed in 38.23 seconds. Ruff passed and mypy reported no issues in
11 scoped source files. Final evidence checks ran
`.venv/bin/python evidence/results-stage/m2/2026-10-08-luna/summarize.py`, which verified all ten
replays and writer-call totals. A refreshed index verified 39 SHA-256/size entries; scoped Ruff,
mypy and `git diff --check` passed after the live evidence README/index update. The v1 fixture generator was run into
`/private/tmp/results-notice-v1-repro`; all 12 generated files matched the checked-in historical
fixtures byte-for-byte. Historical v1 answer replay remained exact; new run artifacts use renderer
v2.

## ADR and deferred-work disposition

ADR 0026 and its index record the accepted engineering measurement decision and run-specific
settings, the capped runtime attempt policy, renderer v2, run-specific guidance and the owner-lifted
campaign cap. The notice change versions renderer semantics without authorizing a code-owned answer
structure or changing eligibility. Broader G03/G05/G06 claims remain distinct; G08 is a required
pre-closeout reconciliation. Owner qualification, M2 closeout and M3 qualification remain unclaimed.
