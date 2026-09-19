# Milestone 2B gateway-discovery evaluation protocol

## Purpose and status

This is a development-only diagnostic protocol for the market-aware 2B
candidate generator. It evaluates whether a bounded grouped proposal is
useful and inspectable after deterministic gate and validation checks. It does
not qualify a production behavior, adopt the 2A selector, or establish any
route, schedule, award, connection, availability, feasibility, or bookability
fact.

The disclosed casebook is
`evals/gateway_discovery/development_cases_v1.yaml`. It uses the pinned M1A
catalog and planning-market policy. The casebook's endpoint codes and expected
gate outcomes are deterministic review context. Its candidate guidance is not
an exact-answer oracle: plausible alternatives, omissions, and abstentions
remain human judgments.

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
  supported by the correct originals, and absent by default for already useful
  gateways.
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

## Run controls and accounting

The default live configuration is `gpt-5.6-luna`, two trials, no retries, and
no rejected-candidate refill call. Run the complete eight-case development
book unless a smoke run is explicitly labeled with its selected cases and
trial count.

There are eight scenarios and one deterministic skip. Therefore each trial
has at most seven model calls, and two trials have an expected maximum of
14 calls. The skip must be represented in the public artifact with a
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

The final public artifact is
[`2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json`](../../evals/gateway_discovery/baseline/2026-09-19-gpt-5.6-luna-prompt-v2-development-2-trials.json).
It records 16 case-trials, 14 expected/attempted one-call generations, and
reconciled private sidecars. Its mechanically completed status does not change
this protocol's human-review or qualification rules.
