"""Remove SDK wrapper duplicate entries from runs started with early runner revision.

The original index is retained verbatim. This never changes raw call files or
stage artifacts and never invokes a model or provider.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def reconcile(path: Path) -> None:
    source = path / "model-calls" / "index.json"
    if not source.exists():
        return
    original = path / "model-calls" / "index.original.json"
    if original.exists():
        entries = json.loads(original.read_text())
    else:
        entries = json.loads(source.read_text())
        if any(item["kind"] == "client.post" for item in entries):
            original.write_text(json.dumps(entries, indent=2) + "\n")
    corrected = [item for item in entries if item["kind"] != "client.post"
                 or (path / "model-calls" / f"call-{item['sequence']:03d}.json").exists()
                 and _is_count_request(path, item)]
    source.write_text(json.dumps(corrected, indent=2) + "\n")
    summary_path = path / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())
        summary["model_calls"] = len(corrected)
        summary["trace_reconciliation"] = {
            "duplicate_sdk_wrapper_entries_removed": len(entries) - len(corrected),
            "original_index": "model-calls/index.original.json" if original.exists() else None,
        }
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")


def _is_count_request(path: Path, item: dict[str, object]) -> bool:
    call = path / "model-calls" / f"call-{item['sequence']:03d}.json"
    data = json.loads(call.read_text())
    return (data.get("request", {}).get("args") or [None])[0] == "/responses/input_tokens"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", choices=("original", "early-2027"), default="original")
    args = parser.parse_args()
    root = HERE / "runs" if args.campaign == "original" else HERE / args.campaign / "runs"
    for summary in sorted(root.rglob("summary.json")):
        reconcile(summary.parent)
