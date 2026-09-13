"""One-way composer experiment fixture compatibility."""

from award_agent.evaluation.clarification_composer_experiment import (
    DEFAULT_COMPOSER_EXPERIMENT_FIXTURES,
    _load_bundles,
)


def test_one_way_composer_fixture_has_no_return_or_duration_requirement() -> None:
    bundles, _ = _load_bundles(DEFAULT_COMPOSER_EXPERIMENT_FIXTURES)
    assert len(bundles) >= 8
    assert all(
        requirement.requirement_id != "return_or_duration"
        for bundle in bundles
        for requirement in bundle.requirements
    )
