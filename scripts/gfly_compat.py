"""Run pinned gfly with the reviewed empty-price parser compatibility fix.

The Google response can contain an itinerary whose price vector is ``[]``.
fast-flights 3.1.0 raises while parsing that row, losing every itinerary in the
response. This launcher preserves that row with an unknown price. It keeps the
installed packages, gfly CLI, Google backend, and persistent throttle intact.

Effective version v2 (2026-09-27) keeps this launcher's behavior unchanged and
adds the award-search adapter's party-echo mapping: the adapter records the
provider-returned query echo ``adults`` value, already validated against the
requested party, as returned-traveler evidence for completed searches. Saved
executions that embed the v1 capability keep their original replay bytes.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_PREFIX = Path("/private/tmp/gfly-live-py312")
EXPECTED_VERSIONS = {"gfly": "0.3.0", "fast-flights": "3.1.0"}
EXPECTED_HASHES = {
    "gfly/backend.py": "954c81e009c4441c61692c06655222024ab1c2be235c8f51057ada01c1500cb5",
    "fast_flights/parser.py": "fd9034aea2066e0b4c96e79668f3b39cb7b94e2ce93509011d79d2cdea39c972",
}
PATCH_VERSION = "0.3.0+award-search-unpriced-party-echo-v2"
ORIGINAL = "        price = k[1][0][1]\n"
REPLACEMENT = "        price = _award_search_price(k[1][0])\n"


def _award_search_price(vector: Any) -> Any:
    """Preserve an observed unpriced row; retain original failure otherwise."""
    if isinstance(vector, list) and not vector:
        return None
    return vector[1]


def _verify_installation() -> tuple[Path, dict[str, str]]:
    if Path(sys.prefix) != EXPECTED_PREFIX:
        raise RuntimeError(f"use the pinned interpreter at {EXPECTED_PREFIX}/bin/python")
    versions = {name: importlib.metadata.version(name) for name in EXPECTED_VERSIONS}
    if versions != EXPECTED_VERSIONS:
        raise RuntimeError("gfly dependency versions differ from reviewed baseline")
    site = EXPECTED_PREFIX / "lib/python3.12/site-packages"
    hashes = {
        name: hashlib.sha256((site / name).read_bytes()).hexdigest()
        for name in EXPECTED_HASHES
    }
    if hashes != EXPECTED_HASHES:
        raise RuntimeError("gfly parser/backend source differs from reviewed baseline")
    return site, hashes


def _install_compatibility(parser_source: str) -> None:
    from fast_flights import parser

    if parser_source.count(ORIGINAL) != 1:
        raise RuntimeError("reviewed price extraction anchor is absent or ambiguous")
    if parser.parse_js.__code__.co_filename != str(
        EXPECTED_PREFIX / "lib/python3.12/site-packages/fast_flights/parser.py"
    ):
        raise RuntimeError("fast-flights parser was replaced before compatibility install")
    namespace = dict(vars(parser))
    namespace["_award_search_price"] = _award_search_price
    source = parser_source.replace(ORIGINAL, REPLACEMENT, 1)
    # The exact installed source is hash-verified above; compile it only in memory.
    exec(compile(source, parser.parse_js.__code__.co_filename, "exec"), namespace)  # noqa: S102
    patched = namespace["parse_js"]
    patched.__globals__["_award_search_price"] = _award_search_price
    parser.parse_js = patched


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    site, hashes = _verify_installation()
    parser_source = (site / "fast_flights/parser.py").read_text()
    if args == ["version", "--json"]:
        print(json.dumps({"version": PATCH_VERSION}, sort_keys=True))
        return 0
    if args == ["--award-search-version"]:
        print(json.dumps({
            "effective_version": PATCH_VERSION,
            "base_versions": EXPECTED_VERSIONS,
            "source_sha256": hashes,
            "compatibility_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }, sort_keys=True))
        return 0
    _install_compatibility(parser_source)
    from gfly.cli import run

    return int(run(args))


if __name__ == "__main__":
    sys.exit(main())
