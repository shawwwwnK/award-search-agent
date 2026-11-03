"""Offline source replay and blind-bundle mutation controls."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import review_bundle


def _expect_rejected(run: str, bundle: str, *, pass_index: int | None = None) -> None:
    try:
        review_bundle.create(run, bundle, pass_index=pass_index)
    except ValueError:
        return
    raise AssertionError("tampered review source was accepted")


def main() -> int:
    from run import _preview

    from award_agent.results.focused import parse_focused_artifact, replay_focused_results

    original = (review_bundle.HERE, review_bundle.RUNS, review_bundle.INDEX)
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_bundle.HERE = root
            review_bundle.RUNS = root / "runs"
            review_bundle.INDEX = root / "review-index.json"
            review_bundle.INDEX.write_text('{"older":"runs/other"}')

            saved_v10 = (Path(__file__).resolve().parent /
                         "runs/scout-v8-admitted/artifact.json")
            v10 = parse_focused_artifact(saved_v10.read_bytes())
            assert v10.contract_version == "results-artifact-v10"
            assert v10.selected_pass_index == 2
            assert replay_focused_results(v10) == v10.resolved
            first_run = review_bundle.RUNS / "v10"
            first_run.mkdir(parents=True)
            (first_run / "artifact.json").write_bytes(saved_v10.read_bytes())
            (first_run / "settings.json").write_text('{"recovery_diagnostic":false}')
            (first_run / "answer-preview.md").write_text(_preview(v10.resolved))
            first = review_bundle.create("v10", "blind-a", pass_index=1)
            final = review_bundle.create("v10", "blind-b")
            assert (first / "answer.md").read_text() != ""
            assert (final / "answer.md").read_text() == _preview(v10.resolved)

            # A source test fake writer builds a real replayable V11 correction.
            sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "tests/unit"))
            from test_results_focused_v11 import _run

            v11, _writer = _run(first="missing_endpoint")
            assert v11.selected_pass_index == 2 and v11.resolved is not None
            assert replay_focused_results(v11) == v11.resolved
            second_run = review_bundle.RUNS / "v11"
            second_run.mkdir()
            (second_run / "artifact.json").write_text(v11.model_dump_json())
            (second_run / "settings.json").write_text('{"recovery_diagnostic":false}')
            preview_path = second_run / "answer-preview.md"
            preview_path.write_text("tampered markdown")
            _expect_rejected("v11", "bad-preview")
            preview_path.write_text(_preview(v11.resolved))
            initial = review_bundle.create("v11", "blind-c", pass_index=1)
            selected = review_bundle.create("v11", "blind-d")
            for bundle in (initial, selected):
                assert (bundle / "comparison-registry.json").is_file()
                answer = (bundle / "answer.md").read_text()
                assert any(metric in answer for metric in (
                    "Journey duration:", "Arrival:", "Departure:"))
                assert "T01" not in answer

            damaged = v11.model_dump(mode="json")
            damaged["comparison_registry"]["facts"][0]["difference_minutes"] = "7300"
            bad_run = review_bundle.RUNS / "damaged-registry"
            bad_run.mkdir()
            (bad_run / "artifact.json").write_text(json.dumps(damaged))
            (bad_run / "settings.json").write_text('{"recovery_diagnostic":false}')
            (bad_run / "answer-preview.md").write_text(_preview(v11.resolved))
            _expect_rejected("damaged-registry", "bad-registry", pass_index=1)
            index = json.loads(review_bundle.INDEX.read_text())
            assert index["older"] == "runs/other"
            assert index["blind-c"] == {"run": "runs/v11", "pass_index": 1}
            assert index["blind-d"] == {"run": "runs/v11", "pass_index": 2}
            assert "bad-preview" not in index and "bad-registry" not in index
    finally:
        review_bundle.HERE, review_bundle.RUNS, review_bundle.INDEX = original
    print("replayed V10/V11 paired bundles and tamper controls passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
