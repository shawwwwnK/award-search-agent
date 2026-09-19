# Milestone 2B gateway-discovery evaluation protocol

## Purpose and status

This is a development-only diagnostic protocol for the market-aware 2B
candidate generator. It evaluates whether a bounded grouped proposal is
useful and inspectable after deterministic gate and validation checks. It does
not qualify a production behavior, adopt the 2A selector, or establish any
route, schedule, award, connection, availability, feasibility, or bookability
fact.

The disclosed casebook is
`evals/gateway_discovery/development_cases_v3.yaml`. It uses the pinned M1A
catalog and planning-market policy. The casebook's endpoint codes and expected
gate outcomes are deterministic review context. Its candidate guidance is not
an exact-answer oracle: plausible alternatives, omissions, and abstentions
remain human judgments.

The prior `development_cases_v1.yaml` and `development_cases_v2.yaml`
casebooks and their checked-in live artifacts remain historical evidence for
their then-current fixtures and hashes; they are not rewritten by v3.

## Evaluation layers

Evaluate the run in two explicitly separate layers.

### Deterministic/offline layer

Before semantic review, run the repository's offline tests and the evaluator's
mechanical checks. These checks should verify:

- every case has nonempty individual IATA origin and destination sets;
- each endpoint resolves to the pinned catalog release and its recorded
  airport identity, country code, ISO region, and retained-facility metadata;
- each case's resolved outbound date context is ordered and bounded;
- the market policy digest and catalog identity match the casebook;
- the gate outcome and per-airport market IDs match the casebook;
- a same-market skip makes no model call;
- multi-market inputs, including equal-but-multi-market endpoint sets, make one
  grouped call;
- accepted proposal airport identities and relationship references are
  deterministically validated, with caps and dependency pruning applied; and
- the original endpoint sets are preserved in every result.

These assertions are structural and policy checks. They are not judgments that a
candidate is a good gateway or that a route exists. A candidate with a
model-asserted market that disagrees with the deterministic policy should be
retained when otherwise valid, with the mismatch recorded as an advisory for
2C.

The three candidate pools are independently bounded at 0–2 origin-access
gateways, 0–2 destination-access gateways, and 0–5 intermediate hubs (nine
candidates total). These are maxima, not targets; accepted access gateways do
not reduce the hub cap. There is no intermediate-hub market-diversity quota.

### Human semantic layer

For each trial, inspect the grouped response and the immutable result. Review
the three shared pools together, not as independent per-pair answer sheets.
Assess whether the model made a useful, bounded set of optional search
hypotheses and whether scopes make the implied pairings clear.

Do not treat a valid IATA code as evidence of usefulness. Do not use a
second call from the same model as a judge. Human reviewers should record
short evidence-based notes and can mark a dimension not applicable when a
pool is empty.

## Human rubric

Use a 0–2 score per dimension for each case/trial:

- **Incremental usefulness:** 0 = no useful additional opportunity or
  materially misleading; 1 = some plausible incremental value; 2 = strong
  complementary opportunities for this request.
- **Scope specificity:** 0 = missing, contradictory, or materially overbroad
  applicability; 1 = mostly interpretable with minor narrowing needed; 2 =
  each relationship is explicit and does not imply unsupported pairings.
- **Important omissions:** 0 = omits an important obvious opportunity for the
  case; 1 = defensible omission or limited coverage; 2 = no material omission
  observed. This is a review signal, not an exhaustive gateway oracle.
- **Weak extras and search burden:** 0 = padding or weak candidates would
  create substantial unnecessary search work; 1 = mixed quality or modest
  burden; 2 = concise, prioritized, and abstains when extras are weak.
- **Access-role appropriateness:** 0 = an origin/destination access gateway is
  misused or unsupported; 1 = role is plausible but rationale or applicability
  is incomplete; 2 = access candidates are relative to the opposite market,
  supported by the correct originals, and materially incremental. An
  already-strong endpoint raises the threshold but does not prohibit an access
  alternative; size, proximity, shared market, or geographic diversity alone
  is not incremental value.
- **Uncertainty honesty:** 0 = claims connectivity, schedules, awards,
  availability, or bookability; 1 = uncertainty is incomplete; 2 = material
  uncertainty is brief and explicit and all candidates remain hypotheses.
- **Rejected/advisory output handling:** 0 = deterministic rejection,
  dependency, or market-mismatch handling is obscured or unsafe; 1 = output
  is inspectable with a minor issue; 2 = accepted, rejected, partial, and
  advisory decisions are clearly represented.
- **Variation across trials:** 0 = unstable in a way that changes scope or
  produces unsafe additions; 1 = meaningful variation but generally
  interpretable; 2 = variation is bounded and remains useful. Variation is
  descriptive, not a pass/fail requirement.

Record the raw score and a one-sentence rationale for every non-2 score.
Report aggregate distributions and representative examples; do not collapse
the rubric into a claim of automatic quality.

## Case-specific review notes

- In `west_coast_to_paris_multi_origin`, JFK and ORD are eligible
  origin-market intermediate-hub hypotheses when their scopes are supported.
  Neither airport is required, and no exact candidate list is a pass oracle.
- In `san_francisco_to_southeast_asia_endpoints`, SAI and KTI are the two
  original Cambodian destination airports. Review destination-side
  applicability across both endpoints without treating either exact candidate
  list or a route claim as a pass oracle.
- In `equal_but_multi_market_endpoint_sets`, equal origin and destination
  market sets still contain multiple markets; the request must not be treated
  as a same-market skip.
- HNL's Pacific Islands classification and IPC's Pacific Islands
  classification are policy overlays. They do not rewrite the physical catalog
  country or prove connectivity.
- `hawaii_to_guam_same_market_skip` is a policy skip only. It is not evidence
  that no supplemental search could ever be useful.
- The Australia/New Zealand case tests the approved v1 boundary, not a
  universal aviation taxonomy.
- A model/policy market mismatch is an advisory to 2C. It is not, by itself,
  a reason to remove an otherwise catalog-valid candidate.
- Casebook v3 adds deliberate coverage of United Kingdom and Southern Europe
  (the latter is a review label within policy market `europe`); mixed
  US/Canada-to-Australia/New-Zealand requests; an ITO Hawaii override;
  Europe same-market skipping; South America-to-Southern Africa, North
  Africa-to-East Africa/Indian Ocean, and Middle East-to-Central
  Asia/Caucasus boundaries; and broad San Francisco, New York, Los Angeles,
  US-to-India, and US-to-South-America grouped endpoint sets. These are
  review situations, never candidate or connectivity oracles.

## Run controls and accounting

The current default live configuration is `gpt-5.6-luna`, prompt v6,
casebook v3, two trials, no retries, and no rejected-candidate refill call.
Run the complete 23-case development book unless a smoke run is explicitly
labeled with its selected cases and trial count.

There are 23 scenarios and two deterministic skips. Therefore each trial
has at most 21 model calls, and two trials have an expected maximum of
42 calls. Each skip must be represented in the public artifact with a
zero-call result. Reconcile:

- case count and trial count;
- expected model calls versus attempted calls;
- each attempted call versus one private trace;
- each successful call versus captured token usage;
- provider/model/configuration, prompt version, response-schema hash,
  catalog receipt, market-policy version/digest, and casebook hash; and
- failures, latency, and empty structured responses.

A missing trace or usage record is an evaluation failure to report, not a
reason to silently reduce the denominator. Do not estimate price unless a
versioned official price card is captured with the run.

## Artifact and privacy rules

The public artifact may contain case IDs, deterministic gate outcomes,
validated candidate IATA codes, role/scope decisions, issue codes, advisory
market comparisons, counts, usage totals, and review scores. It must not
contain raw user utterances, full prompts, raw provider responses, or
provider-error details.

Private raw traces belong under the ignored
`evals/gateway_discovery/traces-live/` path. Keep the public artifact and
private traces linked by stable case/trial identifiers without copying raw
request or response text into the public file. Never include credentials or
private travel information.

## Interpretation and qualification gate

This run is development evidence only. Human reviewers must inspect
incremental usefulness, scope, omissions, weak extras, access-role fit,
uncertainty, rejected/advisory decisions, and trial variation before any
qualification claim. Passing deterministic checks or producing valid airport
codes is insufficient. Connectivity and award availability remain unverified,
and this protocol does not authorize 2C provider execution or SearchPlan
adoption.

If results show repeated weak extras, material omissions, overbroad scopes,
unsafe uncertainty claims, systematic role errors, or excessive search burden,
revise the prompt/policy/validator or defer the next cut. Do not solve a
quality issue by adding an unreviewed curated gateway list or a same-model
judge.

## 2026-09-19 implementation diagnostic

The historical prompt-v1 run
[`2026-09-19-gpt-5.6-luna-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-development-2-trials.json)
identified bounded issues that were corrected before the final diagnostic:
self-pair pruning in access applicability and prompt guidance now explicitly
prohibiting such pairs. It is not the current baseline.

The historical public artifact for the v1 casebook is
[`2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json).
It records 16 case-trials, 14 expected/attempted one-call generations, and
reconciled private sidecars. Its mechanically completed status does not change
this protocol's human-review or qualification rules.

## 2026-09-19 prompt-v5 / casebook-v2 historical diagnostic

Prompt v3 and prompt v4 are retained diagnostic iterations on the disclosed
v2 casebook. Prompt v3 exposed saturation (58 accepted candidates, including
34 hubs). Prompt v4 reduced that burden but regressed IPC circuitousness and
endpoint-assessment behavior. Prompt v5 added the current marginal-distinctness,
circuitousness, and endpoint-assessment rules without changing the response
schema, adapter, catalog, or market-policy identity. The v2 casebook changes
the Southeast Asia scenario to SAI and KTI only; the v1 casebook and its hash
`9f4a1593ae7d06d132faaf5e5d3895f56823136f97a66d4bbde45292edb6789b` remain
historical evidence.

The v2 public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v2-2-trials.json).
It binds prompt `gateway-generator-prompt-v5`, the unchanged response-schema
SHA-256 `173a1d66ef5091a0f44837583579fc1616b406f440ce15976b430bae53a5a680`,
the unchanged `planning-market-v1` policy, and v2 casebook SHA-256
`65c455a9ca51f44ab98bd30800902271aab3077e578b2356b2bd1074e42a4b1d`.

It contains 16 case-trials: 14 expected, constructed, attempted, and
reconciled calls; 11 nonempty outcomes, 3 empty outcomes, and 2 policy skips;
zero partial, rejected-all, or generation-failure outcomes; and 35 accepted
candidates (7 origin access, 12 destination access, and 16 hubs) across 19
accepted scopes. The observed maxima were 2/2/3, within the 2/2/5 limits; the
review records 65 accepted declared relationships. There were 36,772 input
tokens and 19,745 output tokens (56,517 total), zero rejected candidates,
zero mismatch advisories, and endpoint assessments for all 40 original
endpoints. No cost was estimated. Artifact-integrity and AI semantic review
passed for owner human review; neither is human semantic qualification.

## Casebook-v3 first prompt-v5 historical diagnostic

Casebook v3 preserves all eight v2 scenarios and adds 15 reviewed endpoint
sets, including a second same-market skip (`CDG → ATH`). Its pinned catalog
metadata and `planning-market-v1` gate expectations are preflighted before a
generator can be constructed. The first prompt-v5 run is retained as a
diagnostic public artifact:
[`2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v3-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v5-casebook-v3-2-trials.json).
It mechanically completed all 46 case-trials, including 42 expected and
attempted calls, but semantic review exposed relationship multiplication: a
candidate could be applied too broadly or retained as a generic alternative
despite marginal, overlapping, circuitous, or positioning-weak pairings.

The first prompt-v5/v3 run exposed relationship multiplication: 46 records and
42 calls produced 125 accepted candidates, 76 scopes, and 731 accepted
relationships across 184,604 tokens. It is historical diagnostic evidence,
not a quality qualification result.

## 2026-09-19 prompt-v6 / casebook-v3 final diagnostic

Prompt v6 added relationship-level uncertainty/scope reconciliation and
same-scope candidate consolidation only. It did not change the response
schema, adapter, catalog, market-policy identity, deterministic validator, or
historical artifacts. The casebook-v3 SHA-256 is
`ba3b2e0efd73a2774da6af2950ff4addaf5e7763f754b49042dd56acec3b2f06`.

The public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v6-casebook-v3-2-trials.json).
It contains 46 records and 42/42 expected, constructed, attempted, and
reconciled calls across two trials: 37 nonempty outcomes, 4 empty outcomes,
4 policy skips, and 1 partial outcome. It accepted 82 candidates (22 origin
access, 18 destination access, and 42 hubs), 43 scopes, and 400 declared
relationships, with 186,549 total tokens. One PNH catalog-absence rejection
and three model/policy market-mismatch advisories were retained. There were
zero errors or generation failures. Artifact/privacy audit passed.

Independent AI semantic review passed the artifact for owner human review,
not human semantic qualification. The review recorded a 45.3% relationship
reduction and 34.4% candidate reduction versus prompt-v5/v3, with no important
omission observed. Residual notes include 65 relationships for the India case,
55 for Los Angeles/Australia-New Zealand, 36 for New York/Japan, one IPC→PPT
circuitous regression, trial variation, and a private control-character
hygiene note. No prompt-v7 or deterministic semantic rejection change is
currently recommended; 2C relationship/search-work budgeting is mandatory.
