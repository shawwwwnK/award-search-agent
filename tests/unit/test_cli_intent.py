from datetime import date

import pytest

from award_agent.cli.intent import _parser


def test_cli_requires_explicit_model_selection() -> None:
    parser = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "Travel from Seattle to Tokyo.",
                "--reference-date",
                "2026-08-30",
                "--timezone",
                "UTC",
            ]
        )


def test_cli_parses_model_as_run_specific_input() -> None:
    args = _parser().parse_args(
        [
            "Travel from Seattle to Tokyo.",
            "--reference-date",
            "2026-08-30",
            "--timezone",
            "UTC",
            "--model",
            "intent-eval-candidate",
            "--selector-model",
            "selector-candidate",
        ]
    )

    assert args.model == "intent-eval-candidate"
    assert args.reference_date == date(2026, 8, 30)
    assert args.selector_model == "selector-candidate"


def test_cli_rejects_removed_temporal_strategy_switch() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "Travel from Seattle to Tokyo.",
                "--reference-date",
                "2026-08-30",
                "--timezone",
                "UTC",
                "--model",
                "intent-eval-candidate",
                "--selector-model",
                "selector-candidate",
                "--temporal-strategy",
                "retired",
            ]
        )
