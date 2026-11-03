"""Current local Results authoring choice, with injectable offline execution."""

from __future__ import annotations

from typing import Literal

from award_agent.ranking.projection_contracts import SolutionProjection

from .contracts import ResultsConfig, ResultsInputMeasurer
from .currency import FxAcquisition
from .focused import run_focused_results
from .focused_comparison_contracts import FocusedResultsArtifactV11
from .focused_patch_contracts import FocusedResultsArtifactV12
from .interactive_contracts import InteractiveWriter

DEFAULT_RESULTS_PROFILE: Literal["focused-v27"] = "focused-v27"


def run_default_results(projection: SolutionProjection, config: ResultsConfig,
                        writer: InteractiveWriter | None = None,
                        input_measurer: ResultsInputMeasurer | None = None, *,
                        fx_acquisition: FxAcquisition | None = None,
                        ) -> FocusedResultsArtifactV11 | FocusedResultsArtifactV12:
    """Author with the selected profile; injected writers remain fully offline by default."""
    if config.model != "gpt-6-luna":
        raise ValueError("default Results requires explicit gpt-6-luna model")
    if writer is None:
        from openai import OpenAI

        from .adapter import OpenAIResultsInputMeasurer
        from .interactive_adapter import OpenAIInteractiveResultsWriter

        client = OpenAI(max_retries=0, timeout=config.timeout_seconds)
        try:
            writer = OpenAIInteractiveResultsWriter(client)
            if input_measurer is None:
                input_measurer = OpenAIResultsInputMeasurer(client)
            return _run(projection, config, writer, input_measurer, fx_acquisition)
        finally:
            client.close()
    return _run(projection, config, writer, input_measurer, fx_acquisition)


def _run(projection: SolutionProjection, config: ResultsConfig,
         writer: InteractiveWriter, input_measurer: ResultsInputMeasurer | None,
         fx_acquisition: FxAcquisition | None,
         ) -> FocusedResultsArtifactV11 | FocusedResultsArtifactV12:
    artifact = run_focused_results(projection, config, writer, input_measurer,
                                   fx_acquisition=fx_acquisition,
                                   profile=DEFAULT_RESULTS_PROFILE)
    if not isinstance(artifact, (FocusedResultsArtifactV11, FocusedResultsArtifactV12)):
        raise TypeError("default Results returned an unexpected artifact contract")
    return artifact
