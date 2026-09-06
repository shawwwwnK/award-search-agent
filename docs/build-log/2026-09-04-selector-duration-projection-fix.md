# 2026-09-04: Selector duration-projection repair

## Objective evidence

- Reviewed the matched selector artifacts and trace sidecars for the five focused cases.
  `labor_day_thursday_flexibility`, `early_month_with_approximate_duration`,
  `approximate_duration`, and the scored portion of `unbounded_after_new_year` selected an
  unresolved duration alternative. The deterministic compiler and clarification output correctly
  preserved those selections.
- The public selector summary incorrectly described every duration candidate using the candidate
  relation ordinal, whose default is `1`, rather than its literal duration. Thus evidence such as
  “about 10 days” was projected as “a 1-unit trip duration.”
- The selector projection now exposes only date-free literal duration semantics: modifier,
  minimum/maximum quantity, and unit. Duration candidates no longer publish a relation ordinal.
  The compiler, calendar evaluation, clarification policy, and selector fallback behavior were
  not changed.
- Added projection/restoration coverage for approximate ten- and nine-day durations, exact
  two-week duration, alternative one-or-two-week duration, and approximate one-week duration.
  Each test verifies date/context non-leakage and deterministic restored compilation.
- Added the existing unbounded-after-New-Year expected relation to the ready evaluator oracle so
  an unresolved departure boundary cannot receive an accidental pass.

## Verification

- `.venv/bin/pytest -q tests/unit/test_temporal_selector.py tests/unit/test_temporal_compiler.py tests/unit/test_eval_cases.py tests/unit/test_intent_eval_runner.py` — 121 passed.
- `.venv/bin/ruff check src/award_agent/intent/temporal_selector.py tests/unit/test_temporal_selector.py tests/unit/test_eval_cases.py` — passed.
- `.venv/bin/mypy src/award_agent/intent/temporal_selector.py` — passed.
- `git diff --check` — passed.

## Live evaluation status

- The repository-local, git-ignored `.env` supplied `OPENAI_API_KEY` to the evaluation process;
  the key was not printed or copied.
- Focused three-trial selector runs across five cases improved from 0/15 to 8/15 with
  `gpt-4o-mini` Pass 1 and from 0/15 to 5/15 with `gpt-5.6-luna` Pass 1. Both had zero errors.
- The full Mini Pass-1 plus Luna-selector matrix completed 33/48 with zero errors, compared with
  the prior matched 24/48 artifact. It retained failures for `labor_day_thursday_flexibility` and
  `approximate_duration`, where the selector still chose unresolved duration, and for
  `multiple_destination_options`, whose temporal output was correct but non-temporal Pass 1
  failed traveler/origin expectations.
- A combined four-arm matrix was stopped after its first two arms so it would not continue spending
  calls on `two_pass`. The full Luna-selector arm was consequently not completed.
- A subsequent parallel full comparison held compiler Pass 1 on `gpt-5.6-luna` while changing only
  the selector between `gpt-4o-mini` and `gpt-5.6-luna`. Both 48-run artifacts ended in 48 explicit
  `NonTemporalExtractionError` records at `compiler_non_temporal_pass_one`, with zero selector
  attempts and zero selector failures. The artifacts are invalid as a selector-model comparison;
  no duration-projection, compiler, oracle, or clarification conclusion follows from them.
- Sequential reruns of those same two 48-run arms completed with zero errors and 48 non-temporal
  Pass-1 attempts plus 42 selector attempts each. With Luna at Pass 1, the Mini selector passed
  11/48 (22.9%; 143.08 seconds) and the Luna selector passed 39/48 (81.3%; 194.20 seconds).
  These runs establish that the preceding all-error artifacts were not a deterministic selector or
  compiler failure. They are independent stochastic end-to-end samples, so the gap is decision
  evidence rather than a controlled per-request selector-only attribution.
- In the six previously focal cases, Mini/Luna selector passes were respectively:
  approximate-duration 3/3 vs 1/3; early-month approximate duration 0/3 vs 3/3; Labor-Day
  Thailand 2/3 vs 3/3; Labor-Day Thursday 0/3 vs 0/3; multiple-destination 0/3 vs 2/3; and
  unbounded-after-New-Year 0/3 vs 3/3. Neither sequential arm raised an explicit error.
- On 2026-09-05, a three-trial full Luna-Pass-1 plus Luna-selector rerun was made with local trace
  capture enabled. All 48 attempts failed at non-temporal Pass 1 before selector invocation; the
  artifact reports the sanitized `missing_or_invalid_model_output` classification, while every
  captured call sidecar records `APIConnectionError: Connection error.` No selector call was made,
  so this is provider-connectivity evidence only and cannot revise the sequential selector result.
- An immediate same-configuration traced retry repeated the result: 48 Pass-1 failures, zero
  selector attempts, and the same captured `APIConnectionError`. The repetition rules out a
  one-off sampled selector outcome, but does not identify the provider/network boundary that
  rejected the calls.
- Error-path review established that trace capture was not causal: the SDK `responses.parse` call
  happens before the in-memory collector records it, and sidecars are written only after the
  workflow result. A preceding 48-sidecar attempt and both recorded 48-run attempts all had null
  responses and the same `APIConnectionError`. The ignored, mode-0600 `.env` key file was
  unchanged from the successful sequential run. The evidence supports a transient transport
  failure (local network/proxy/TLS/firewall or provider connection path), but retained envelopes
  lack cause-chain, TLS/proxy, endpoint, retry-history, and request-ID diagnostics to decide
  which boundary failed.
- A single authorized minimal `OpenAI().responses.parse` probe reproduced the error in 1.57
  seconds and retained its immediate cause: `httpx.ConnectError`, `gaierror` errno 8 (hostname
  not known). The client endpoint is the official `api.openai.com`; no base-URL, proxy, or
  certificate override is present, and direct DNS resolution of that endpoint fails with the same
  errno. This narrows the current issue to local DNS/name-resolution connectivity, not credentials,
  response schema, trace capture, or selector behavior. No retry/fallback behavior was changed.

## Connectivity recovery check (2026-09-05)

- A subsequent minimal authenticated `GET https://api.openai.com/v1/models` request returned
  HTTP 200 in 1.03 seconds. It did not invoke a model or print a key, request header, response
  body, model ID, or trace payload.
- The first direct-shell attempt found no inherited `OPENAI_API_KEY`. Loading the repository's
  git-ignored `.env` through the same `python-dotenv` mechanism used by the live-evaluation CLIs
  supplied the key and succeeded. Thus a bare shell environment is not a reliable prerequisite
  check for this repository.
- This demonstrates current DNS, TLS, routing, and credential viability at the API boundary. It
  does not retroactively turn the preceding failed matrices into selector evidence.

### Repeatable, credential-safe preflight

Before a live eval after a connectivity incident, run this command from the repository root. It
loads the local `.env`, makes one non-model API request, prints only an HTTP status and elapsed
time, and exits nonzero on a missing key, transport failure, or non-2xx status:

```sh
PYTHONPATH=src .venv/bin/python -c 'import os, sys, time, urllib.request, urllib.error; from dotenv import load_dotenv; load_dotenv(); key = os.environ.get("OPENAI_API_KEY");
if not key: print("api_key=missing_after_project_load"); sys.exit(2)
request = urllib.request.Request("https://api.openai.com/v1/models", headers={"Authorization": "Bearer " + key})
started = time.perf_counter()
try:
    with urllib.request.urlopen(request, timeout=15) as response: print(f"status={response.status} elapsed_ms={(time.perf_counter() - started) * 1000:.0f} api_connectivity=ok")
except urllib.error.HTTPError as error: print(f"status={error.code} api_connectivity=failed"); sys.exit(1)
except Exception as error: print(f"network_error={type(error).__name__} api_connectivity=failed"); sys.exit(1)'
```

Do not replace this with a model generation call merely to verify connectivity. If it succeeds,
record the result separately from any subsequent eval; it verifies the connection path, not model
quality or selector behavior.

## Traced Luna selector rerun (2026-09-05)

- After the successful preflight, the full ready-corpus compiler-selector arm was rerun with
  `gpt-5.6-luna` for both non-temporal Pass 1 and selector, `compiler_select_v1`,
  `supported_or_unresolved`, three trials, and `--trace-all-calls`.
- The normal sandbox attempt recorded 48 Pass-1 `APIConnectionError` results and zero selector
  attempts. It is retained at
  `evals/intent/baseline/2026-09-05-gpt-5.6-luna-pass1-selector-supported-unresolved-rerun-3-trials.json`
  as transport evidence, not a scored selector outcome.
- The authorized network retry completed 48/48 records with 39 passed (81.25%), 9 failed checks,
  and zero errors, repairs, Pass-1 failures, selector failures, Pass-2 wire failures, or grounding
  failures. It used 90 calls (48 Pass 1 and 42 selector), 85,732 captured tokens, and 188.409
  seconds total latency. The artifact is
  `evals/intent/baseline/2026-09-05-gpt-5.6-luna-pass1-selector-supported-unresolved-rerun-network-3-trials.json`.
- The successful artifact records `all_calls` trace mode and a private 48-case sidecar directory:
  `evals/intent/traces/run-2026-09-05T172925.755812-0000-61d462b5`. These traces may contain
  request content and must remain private.
- The remaining nine records are completed semantic, deterministic-output, or clarification
  failures (7, 6, and 6 flagged respectively; categories overlap), not model transport or selector
  boundary failures. This run is a fresh stochastic sample, so it should be compared with earlier
  matched runs as evidence rather than merged into them as an additional controlled trial.

## Owner interpretation

<!-- Project owner: record any live-evaluation conclusion and the next cut line here. -->
