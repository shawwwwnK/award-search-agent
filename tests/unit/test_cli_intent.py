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
        ]
    )

    assert args.model == "intent-eval-candidate"
    assert args.reference_date == date(2026, 8, 30)
    assert args.temporal_strategy == "two_pass"


def test_cli_accepts_the_opt_in_compiler_strategy() -> None:
    args = _parser().parse_args(
        [
            "Travel from Seattle to Tokyo.",
            "--reference-date",
            "2026-08-30",
            "--timezone",
            "UTC",
            "--model",
            "intent-eval-candidate",
            "--temporal-strategy",
            "compiler_select_v1",
        ]
    )

    assert args.temporal_strategy == "compiler_select_v1"
