"""Shared token-bearing Results request fields for counting and authoring."""

from __future__ import annotations

from openai.lib._pydantic import to_strict_json_schema

from award_agent.providers.contracts import content_digest

from .contracts import PreparedResultsInput, ResultsConfig, ResultsDocument


def response_schema(prepared_version: str) -> dict[str, object]:
    schema = to_strict_json_schema(ResultsDocument)
    if prepared_version == "results-prepared-v1":
        definitions = schema["$defs"]
        part = definitions["ResultsPart"]
        part["properties"].pop("shared_disclosures")
        part["required"].remove("shared_disclosures")
        definitions.pop("SharedDisclosureBinding")
    elif prepared_version != "results-prepared-v2":
        raise ValueError("unsupported Results prepared version")
    return schema


def token_request(prepared: PreparedResultsInput, config: ResultsConfig,
                  payload: str) -> dict[str, object]:
    return {
        "model": config.model,
        "instructions": prepared.instructions,
        "input": payload,
        "text": {"format": {"type": "json_schema", "name": "ResultsDocument",
                            "strict": True, "schema": response_schema(prepared.contract_version)}},
    }


def token_request_digest(request: dict[str, object]) -> str:
    return content_digest(request)
