"""Characterize trace forwarding shared by the three live evaluators."""

from __future__ import annotations

from typing import Any

import pytest

from award_agent.evaluation.gateway_discovery_live import _TraceTee as DiscoveryTraceTee
from award_agent.evaluation.intent_to_search_planning_live import (
    _GatewayTraceTee as IntentPlanningTraceTee,
)
from award_agent.evaluation.search_planning_live import _GatewayTraceTee as PlanningTraceTee

TEES = (DiscoveryTraceTee, PlanningTraceTee, IntentPlanningTraceTee)


class _Inner:
    def __init__(self) -> None:
        self.proposal = object()
        self.usage = {"calls": 1}
        self.traces: list[Any] = []
        self.propose_inputs: list[Any] = []
        self.usage_calls = 0
        self.trace_calls = 0

    def propose(self, model_input: Any) -> Any:
        self.propose_inputs.append(model_input)
        return self.proposal

    def take_usage(self) -> dict[str, int]:
        self.usage_calls += 1
        return self.usage

    def take_call_traces(self) -> Any:
        self.trace_calls += 1
        return self.traces.pop(0)


@pytest.mark.parametrize("tee_type", TEES)
def test_forwards_original_objects_once_and_appends_each_drain_in_order(
    tee_type: type[Any],
) -> None:
    inner = _Inner()
    first = {"first": object()}
    second = {"second": object()}
    first_batch = [first, second]
    empty_batch: list[dict[str, object]] = []
    inner.traces = [first_batch, empty_batch]
    existing = {"existing": object()}
    sink = [existing]
    tee = tee_type(inner, sink)
    model_input = object()

    assert tee.propose(model_input) is inner.proposal
    assert inner.propose_inputs == [model_input]
    assert inner.propose_inputs[0] is model_input
    assert tee.take_usage() is inner.usage
    assert inner.usage_calls == 1
    assert tee.take_call_traces() is first_batch
    assert tee.take_call_traces() is empty_batch
    assert inner.trace_calls == 2
    assert len(sink) == 3
    assert sink[0] is existing
    assert sink[1] is first
    assert sink[2] is second


@pytest.mark.parametrize("tee_type", TEES)
def test_iterable_trace_return_is_extended_without_normalizing_result(
    tee_type: type[Any],
) -> None:
    inner = _Inner()
    trace = {"private": object()}
    iterable = (trace,)
    inner.traces = [iterable]
    sink: list[dict[str, object]] = []

    assert tee_type(inner, sink).take_call_traces() is iterable
    assert sink[0] is trace


@pytest.mark.parametrize("tee_type", TEES)
def test_noniterable_trace_return_raises_without_changing_sink(tee_type: type[Any]) -> None:
    inner = _Inner()
    inner.traces = [123]
    sentinel = {"existing": object()}
    sink = [sentinel]

    with pytest.raises(TypeError):
        tee_type(inner, sink).take_call_traces()
    assert sink == [sentinel]
    assert sink[0] is sentinel


@pytest.mark.parametrize("tee_type", TEES)
@pytest.mark.parametrize("method", ("propose", "take_usage", "take_call_traces"))
def test_inner_exception_propagates_unchanged_and_sink_is_untouched(
    tee_type: type[Any], method: str
) -> None:
    failure = RuntimeError("private failure")

    class FailingInner:
        def propose(self, _model_input: Any) -> Any:
            raise failure

        def take_usage(self) -> Any:
            raise failure

        def take_call_traces(self) -> Any:
            raise failure

    sentinel = {"existing": object()}
    sink = [sentinel]
    tee = tee_type(FailingInner(), sink)
    with pytest.raises(RuntimeError) as captured:
        if method == "propose":
            tee.propose(object())
        else:
            getattr(tee, method)()
    assert captured.value is failure
    assert sink == [sentinel]
    assert sink[0] is sentinel
