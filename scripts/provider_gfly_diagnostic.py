"""One-call, pinned gfly parser diagnostic with its normal CLI and throttle.

Run with the isolated gfly Python interpreter. This wrapper observes the parser,
then invokes gfly's ordinary CLI exactly once. It neither retries nor changes
the Google backend or gfly's persistent throttle. The receipt contains shapes
and traceback locations only; optional raw HTML stays under /private/tmp.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_PREFIX = Path("/private/tmp/gfly-live-py312")
EXPECTED_FILES = {
    "gfly/backend.py": "954c81e009c4441c61692c06655222024ab1c2be235c8f51057ada01c1500cb5",
    "fast_flights/parser.py": "fd9034aea2066e0b4c96e79668f3b39cb7b94e2ce93509011d79d2cdea39c972",
}
MAX_PRIVATE_HTML_BYTES = 4 * 1024 * 1024
MAX_OUTPUT_CAPTURE_BYTES = 4 * 1024 * 1024
SECRET_KEY = re.compile(
    r"authorization|api.?key|(?:access|auth|session|booking).?token|cookie|secret|booking.?url|booking.?link",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(r"(?i)(bearer\s+[A-Za-z0-9._~-]+|sk-[A-Za-z0-9_-]{20,})")


class _Tee:
    """Forward CLI output unchanged while retaining a bounded copy for evidence."""

    def __init__(self, target: Any) -> None:
        self.target = target
        self.parts: list[str] = []
        self.bytes_seen = 0
        self.complete = True

    def write(self, value: str) -> int:
        written = self.target.write(value)
        data = value.encode("utf-8")
        self.bytes_seen += len(data)
        if self.complete and self.bytes_seen <= MAX_OUTPUT_CAPTURE_BYTES:
            self.parts.append(value)
        else:
            self.complete = False
            self.parts.clear()
        return written

    def flush(self) -> None:
        self.target.flush()

    def isatty(self) -> bool:
        return self.target.isatty()

    @property
    def encoding(self) -> str:
        return self.target.encoding


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SECRET_KEY.search(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub("[REDACTED]", value)
    return value


def _sanitized_output(stdout: _Tee, stderr: _Tee, exit_code: int | None) -> Any:
    if not stdout.complete or not stderr.complete:
        return {"capture_incomplete": True, "reason": "output_over_4_mib_bound"}
    selected = "".join(stdout.parts) if exit_code == 0 else "".join(stderr.parts)
    try:
        return _redact(json.loads(selected))
    except (ValueError, TypeError):
        return {
            "unparsed_stdout_redacted": SECRET_VALUE.sub("[REDACTED]", "".join(stdout.parts)),
            "unparsed_stderr_redacted": SECRET_VALUE.sub("[REDACTED]", "".join(stderr.parts)),
        }


def _write_json_once(path: Path, value: Any) -> tuple[str, int]:
    data = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return _sha256(data), len(data)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_fingerprints() -> dict[str, Any]:
    if Path(sys.prefix) != EXPECTED_PREFIX:
        raise RuntimeError(f"use the pinned interpreter at {EXPECTED_PREFIX}/bin/python")
    versions = {
        "gfly": importlib.metadata.version("gfly"),
        "fast-flights": importlib.metadata.version("fast-flights"),
    }
    if versions != {"gfly": "0.3.0", "fast-flights": "3.1.0"}:
        raise RuntimeError("gfly dependency versions differ from the reviewed capture")
    installed = Path(sys.prefix) / "lib/python3.12/site-packages"
    file_hashes = {
        name: _sha256((installed / name).read_bytes()) for name in EXPECTED_FILES
    }
    if file_hashes != EXPECTED_FILES:
        raise RuntimeError("gfly parser/backend source differs from the reviewed capture")
    return {
        "python": sys.version.split()[0],
        "environment": str(EXPECTED_PREFIX),
        "versions": versions,
        "sha256": file_hashes,
        "gfly_source_commit": "43b1aa4bbe5b442cc7fd3a7c285c940bb39561db",
    }


def _value_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"type": "list", "length": len(value)}
    if isinstance(value, dict):
        return {"type": "object", "length": len(value)}
    if value is None:
        return {"type": "null"}
    return {"type": type(value).__name__}


def _at(value: Any, *indices: int) -> Any:
    for index in indices:
        if not isinstance(value, list) or index >= len(value):
            return None
        value = value[index]
    return value


def _shape(html: str) -> dict[str, Any]:
    """Inspect only container sizes at the offsets used by fast-flights 3.1.0."""
    from selectolax.lexbor import LexborHTMLParser

    result: dict[str, Any] = {
        "html_bytes": len(html.encode("utf-8")),
        "html_sha256": _sha256(html.encode("utf-8")),
    }
    try:
        script = LexborHTMLParser(html).css_first(r"script.ds\:1")
        result["script_present"] = script is not None
        if script is None:
            return result
        js = script.text()
        result["script_bytes"] = len(js.encode("utf-8"))
        result["data_marker_present"] = "data:" in js
        if "data:" not in js:
            return result
        data = js.split("data:", 1)[1].rsplit(",", 1)[0]
        payload = json.loads(data)
        result["payload"] = _value_shape(payload)
        for name, path in {
            "metadata": (7,),
            "metadata_body": (7, 1),
            "alliances": (7, 1, 0),
            "airlines": (7, 1, 1),
            "flight_group": (3,),
            "flight_rows": (3, 0),
        }.items():
            result[name] = _value_shape(_at(payload, *path))
        rows = _at(payload, 3, 0)
        if isinstance(rows, list):
            result["row_count"] = len(rows)
            anomalies: list[dict[str, Any]] = []
            for row_index, row in enumerate(rows):
                flight = _at(row, 0)
                price = _at(row, 1, 0)
                legs = _at(flight, 2)
                extras = _at(flight, 22)
                bad_leg_indices = []
                if isinstance(legs, list):
                    bad_leg_indices = [i for i, leg in enumerate(legs) if not isinstance(leg, list) or len(leg) < 22]
                if (
                    not isinstance(row, list) or len(row) < 2
                    or not isinstance(price, list) or len(price) < 2
                    or not isinstance(flight, list) or len(flight) < 23
                    or not isinstance(legs, list) or bad_leg_indices
                    or not isinstance(extras, list) or len(extras) < 9
                ):
                    anomalies.append({
                        "index": row_index,
                        "row": _value_shape(row),
                        "flight": _value_shape(flight),
                        "price": _value_shape(price),
                        "legs": _value_shape(legs),
                        "short_leg_indices": bad_leg_indices[:20],
                        "extras": _value_shape(extras),
                    })
            result["anomaly_count"] = len(anomalies)
            result["anomalies"] = anomalies[:20]
    except (ValueError, TypeError, AttributeError, IndexError) as exc:
        result["shape_error_type"] = type(exc).__name__
    return result


def _write_private_html(path: Path, html: str) -> dict[str, Any]:
    data = html.encode("utf-8")
    if len(data) > MAX_PRIVATE_HTML_BYTES:
        return {"written": False, "reason": "over_4_mib_bound", "bytes": len(data)}
    root = Path("/private/tmp").resolve()
    if not path.is_absolute() or not path.parent.resolve().is_relative_to(root):
        raise ValueError("private HTML path must be beneath /private/tmp")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return {"written": True, "bytes": len(data), "sha256": _sha256(data)}


def _query_identity(argv: list[str]) -> dict[str, Any]:
    def flag(name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    return {
        "origin": argv[1],
        "destination": argv[2],
        "date": flag("--depart"),
        "travelers": flag("--adults"),
        "cabin": flag("--cabin"),
        "currency": flag("--currency"),
        "backend": flag("--backend"),
    }


def _validate_gfly_args(argv: list[str]) -> None:
    if len(argv) < 3 or argv[0] != "search":
        raise ValueError("diagnostic accepts exactly one gfly search")
    if "--backend" not in argv or argv[argv.index("--backend") + 1:argv.index("--backend") + 2] != ["google"]:
        raise ValueError("diagnostic requires the pinned google backend")
    if any(arg.split("=", 1)[0] in {"--no-throttle", "--min-interval", "--proxy"} for arg in argv):
        raise ValueError("diagnostic must retain default throttle and network path")
    if not {"--json", "--no-input", "--wait"}.issubset(argv):
        raise ValueError("diagnostic requires --json --no-input --wait")
    if any(key in os.environ for key in (
        "GFLY_NO_THROTTLE", "GFLY_MIN_INTERVAL", "GFLY_PROXY", "GFLY_STATE_DIR",
        "GFLY_ABUSE_COOKIE", "XDG_STATE_HOME",
    )):
        raise ValueError("diagnostic requires gfly's ordinary throttle and network environment")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--private-html", type=Path)
    parser.add_argument("--compatibility", action="store_true",
                        help="Install the reviewed repository empty-price compatibility before this one call.")
    parser.add_argument("gfly_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv: list[str] = args.gfly_args
    if argv and argv[0] == "--":
        argv = argv[1:]
    _validate_gfly_args(argv)
    for output in (args.receipt, args.response):
        if output.exists():
            raise FileExistsError(output)
    if args.private_html is not None:
        root = Path("/private/tmp").resolve()
        if not args.private_html.is_absolute() or not args.private_html.parent.resolve().is_relative_to(root):
            raise ValueError("private HTML path must be beneath /private/tmp")
        if args.private_html.exists():
            raise FileExistsError(args.private_html)
    fingerprints = _source_fingerprints()

    if args.compatibility:
        import gfly_compat

        site, hashes = gfly_compat._verify_installation()
        gfly_compat._install_compatibility((site / "fast_flights/parser.py").read_text())
        fingerprints["effective_version"] = gfly_compat.PATCH_VERSION
        fingerprints["compatibility_sha256"] = _sha256(
            Path(gfly_compat.__file__).read_bytes()
        )
        if hashes != fingerprints["sha256"]:
            raise RuntimeError("compatibility baseline differs from diagnostic source")

    from fast_flights import fetcher
    from gfly.cli import run

    original_parse = fetcher.parse
    telemetry: dict[str, Any] = {"parser_status": "not_reached"}

    def observed_parse(html: str) -> Any:
        telemetry["parser_status"] = "entered"
        try:
            result = original_parse(html)
            telemetry["parser_status"] = "completed"
            return result
        except Exception as exc:
            telemetry["parser_status"] = "exception"
            telemetry["exception_type"] = type(exc).__name__
            telemetry["traceback"] = [
                {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                for frame in traceback.extract_tb(exc.__traceback__)
                if Path(frame.filename).name in {"parser.py", "fetcher.py"}
            ]
            try:
                telemetry["shape"] = _shape(html)
            except Exception as diagnostic_exc:  # noqa: BLE001 - diagnostic must not mask parser failure
                telemetry["shape_diagnostic_error_type"] = type(diagnostic_exc).__name__
            if args.private_html is not None:
                try:
                    telemetry["private_html"] = _write_private_html(args.private_html, html)
                except Exception as diagnostic_exc:  # noqa: BLE001 - diagnostic must not mask parser failure
                    telemetry["private_html_error_type"] = type(diagnostic_exc).__name__
            raise

    fetcher.parse = observed_parse
    stdout = _Tee(sys.stdout)
    stderr = _Tee(sys.stderr)
    started = time.monotonic()
    exit_code: int | None = None
    run_error: BaseException | None = None
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = int(run(argv))
    except BaseException as exc:  # noqa: BLE001 - retain receipt even if CLI raises
        run_error = exc
    finally:
        fetcher.parse = original_parse
    elapsed_seconds = time.monotonic() - started
    status = {0: "completed", 3: "empty", 7: "rate_limited", 20: "blocked", 21: "schema_drift"}.get(exit_code, "failed")
    error_code = {7: "RATE_LIMITED", 20: "BLOCKED", 21: "SCHEMA_DRIFT"}.get(exit_code)
    response = _sanitized_output(stdout, stderr, exit_code)
    if isinstance(response, dict) and isinstance(response.get("code"), str):
        error_code = response["code"]
    response_sha256, sanitized_bytes = _write_json_once(args.response, response)
    receipt = {
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "query_identity": _query_identity(argv),
        "source_fingerprints": fingerprints,
        "status": status,
        "exit_code": exit_code,
        "error_code": error_code,
        "elapsed_seconds": elapsed_seconds,
        "stdout_bytes": stdout.bytes_seen,
        "stderr_bytes": stderr.bytes_seen,
        "response_bytes": stdout.bytes_seen + stderr.bytes_seen,
        "response_path": str(args.response),
        "response_sha256": response_sha256,
        "sanitized_bytes": sanitized_bytes,
        "telemetry": telemetry,
    }
    if run_error is not None:
        receipt["run_error_type"] = type(run_error).__name__
    _write_json_once(args.receipt, receipt)
    if run_error is not None:
        raise run_error.with_traceback(run_error.__traceback__)
    assert exit_code is not None
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
