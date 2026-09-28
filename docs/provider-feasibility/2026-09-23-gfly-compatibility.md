# gfly empty-price compatibility record

Date: 2026-09-23. Scope: local Provider Stage development capture and runtime.

## Observed failure and supported correction

The saved SFO–BKK, 2027-05-15 Google response reached `fast-flights 3.1.0` but
`fast_flights/parser.py` raised `IndexError` at its price lookup. Seven of the
eight flight rows had numeric prices. The eighth row's inner price vector was
exactly `[]`, so the original parser discarded the entire response. The
minimized, redacted parser fixture is
`tests/fixtures/providers/gfly_missing_price_minimized.json`; private raw HTML
is not a repository artifact.

`scripts/gfly_compat.py` changes that one lookup **in memory** after verifying
the installed source. For exactly an empty list, it gives the row a Python
`None` price. The unchanged `gfly` Google normalizer emits JSON `null`, and the
Provider Stage adapter records an unknown cash price and its validation
finding. The other seven displayed amounts remain 535, 566, 570, 670, 697,
773, and 1156 USD in the minimized fixture. A numeric zero remains zero;
missing, null, short, or otherwise malformed nonempty price structures still
fail. The fix does not infer a fare, remove a row, or establish price scope or
bookability.

The compatibility launcher invokes the ordinary `gfly` CLI after installing
that in-process parser function. It does not modify installed package files,
change the Google backend, bypass the persistent throttle, add retries, or
change the provider call budget. Its effective version is
`0.3.0+award-search-unpriced-v1`. The adapter and live CLI bind that effective
version to the reviewed cash capability.

## Reproducing the local installation

The launcher requires the isolated **Python 3.12** environment at exactly
`/private/tmp/gfly-live-py312`. This local path is an executable precondition,
not a portable package location. The reviewed baseline has `gfly 0.3.0` from
source commit `43b1aa4bbe5b442cc7fd3a7c285c940bb39561db` and
`fast-flights 3.1.0`. The installation used a local gfly source checkout;
the commit identifies the reviewed source, while the following installed-file
hashes are the enforced binary provenance:

| Installed file beneath `lib/python3.12/site-packages` | Required SHA-256 |
| --- | --- |
| `gfly/backend.py` | `954c81e009c4441c61692c06655222024ab1c2be235c8f51057ada01c1500cb5` |
| `fast_flights/parser.py` | `fd9034aea2066e0b4c96e79668f3b39cb7b94e2ce93509011d79d2cdea39c972` |

The launcher refuses a different interpreter prefix, package version, file
hash, or parser anchor. To inspect its identity without a provider call, from
the repository root run:

```sh
/private/tmp/gfly-live-py312/bin/python scripts/gfly_compat.py --award-search-version
/private/tmp/gfly-live-py312/bin/python scripts/gfly_compat.py version --json
```

The first command reports base versions, installed-file SHA-256 values, the
launcher's own SHA-256, and effective version. The second returns the version
shape consumed by the live CLI. For an authorized live Provider Stage run, pass
the interpreter and launcher separately:

```text
--gfly-executable /private/tmp/gfly-live-py312/bin/python
--gfly-wrapper scripts/gfly_compat.py
```

The offline regression in `tests/unit/test_gfly_compat.py` reproduces the
original eight-row failure, then verifies all eight rows and one null price
under the compatibility launcher. It also verifies zero and malformed-vector
behavior. The pinned-environment integration tests skip when this local
environment is absent; they do not make provider calls.

This is a reproducible **local pin**, not portable installation support. A
different machine or environment needs a separately reviewed packaging path,
source fingerprint, and matching capability version before live use. The
observed defect is one response shape, so this correction does not establish
general parser compatibility or provider reliability.
