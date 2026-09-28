"""Offline regression for the pinned gfly empty-price compatibility launcher."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PINNED_PYTHON = Path("/private/tmp/gfly-live-py312/bin/python")
FIXTURE = ROOT / "tests/fixtures/providers/gfly_missing_price_minimized.json"
SPEC = importlib.util.spec_from_file_location("gfly_compat", ROOT / "scripts/gfly_compat.py")
assert SPEC is not None and SPEC.loader is not None
gfly_compat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gfly_compat)


def test_price_extraction_changes_only_empty_list() -> None:
    assert gfly_compat._award_search_price([]) is None
    assert gfly_compat._award_search_price([None, 0]) == 0
    assert gfly_compat._award_search_price([None, 535]) == 535
    for malformed in ([None], None, {}):
        with pytest.raises((IndexError, TypeError, KeyError)):
            gfly_compat._award_search_price(malformed)


@pytest.mark.skipif(not PINNED_PYTHON.exists(), reason="pinned local gfly environment absent")
def test_reviewed_fixture_preserves_all_rows_and_unknown_price() -> None:
    code = """
import json, sys
from pathlib import Path
from scripts import gfly_compat as compat
from fast_flights import parser
from gfly.backend import _norm_google
fixture = json.loads(Path(sys.argv[1]).read_text())
payload = fixture['payload']
js = 'data:' + json.dumps(payload) + ','
try:
    parser.parse_js(js)
except IndexError:
    pass
else:
    raise AssertionError('baseline parser unexpectedly accepted empty price')
site, _ = compat._verify_installation()
compat._install_compatibility((site / 'fast_flights/parser.py').read_text())
rows = parser.parse_js(js)
normalized = [_norm_google(row, 'USD', True) for row in rows]
assert len(normalized) == 8
assert [row['price'] for row in normalized] == [535, 566, 570, 670, 697, 773, 1156, None]
assert all(row['origin'] and row['destination'] and row['departure'] and row['arrival'] for row in normalized)
payload[3][0][0][1][0] = [None, 0]
assert parser.parse_js('data:' + json.dumps(payload) + ',')[0].price == 0
payload[3][0][0][1][0] = [None]
try:
    parser.parse_js('data:' + json.dumps(payload) + ',')
except IndexError:
    pass
else:
    raise AssertionError('malformed nonempty vector was accepted')
print(json.dumps({'count': len(normalized), 'prices': [row['price'] for row in normalized]}))
"""
    result = subprocess.run(
        [str(PINNED_PYTHON), "-c", code, str(FIXTURE)],
        cwd=ROOT, capture_output=True, text=True, timeout=10, check=True,
    )
    assert json.loads(result.stdout) == {
        "count": 8, "prices": [535, 566, 570, 670, 697, 773, 1156, None],
    }


@pytest.mark.skipif(not PINNED_PYTHON.exists(), reason="pinned local gfly environment absent")
def test_launcher_reports_effective_version_and_source_digest() -> None:
    command = [str(PINNED_PYTHON), str(ROOT / "scripts/gfly_compat.py")]
    version = subprocess.run(command + ["version", "--json"], capture_output=True,
                             text=True, timeout=10, check=True)
    assert json.loads(version.stdout) == {"version": gfly_compat.PATCH_VERSION}
    identity = subprocess.run(command + ["--award-search-version"], capture_output=True,
                              text=True, timeout=10, check=True)
    details = json.loads(identity.stdout)
    assert details["effective_version"] == gfly_compat.PATCH_VERSION
    assert len(details["compatibility_sha256"]) == 64
    assert details["source_sha256"] == gfly_compat.EXPECTED_HASHES
