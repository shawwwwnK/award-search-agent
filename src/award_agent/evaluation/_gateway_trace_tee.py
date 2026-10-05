"""Forward gateway generator telemetry into an evaluator-owned trace sink."""

from __future__ import annotations

from typing import Any, cast


class GatewayTraceTee:
    def __init__(self, inner: Any, holder: list[dict[str, Any]]) -> None:
        self._inner = inner
        self._holder = holder

    def propose(self, model_input: Any) -> Any:
        return self._inner.propose(model_input)

    def take_usage(self) -> dict[str, int] | None:
        return cast(dict[str, int] | None, self._inner.take_usage())

    def take_call_traces(self) -> list[dict[str, Any]]:
        calls = cast(list[dict[str, Any]], self._inner.take_call_traces())
        self._holder.extend(calls)
        return calls
