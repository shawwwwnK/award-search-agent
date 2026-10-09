"""Capture complete model-specific input counts; no generation or provider calls."""
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, OpenAI
from openai.lib._pydantic import to_strict_json_schema

from award_agent.providers.contracts import content_digest
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, ResultsDocument, authoring_payload, prepare_results

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CASES = ("sfo_to_bkk_positioning", "exact_business", "mixed_access")
CONFIG = ResultsConfig(model="gpt-6-luna", max_output_tokens=16384,
    timeout_seconds=300, context_limit_tokens=1050000, prompt_overhead_tokens=2048)


def main() -> None:
    load_dotenv(ROOT / ".env")
    client = OpenAI(max_retries=0, timeout=120)
    config_path = OUT / "config.json"
    if not config_path.exists():
        config_path.write_text(CONFIG.model_dump_json(indent=2) + "\n")
    for name in CASES:
        target = OUT / f"{name}.count.json"
        if target.exists():
            old = json.loads(target.read_text())
            if old["status"] == "success":
                print(f"{name}: count already saved", flush=True)
                continue
            attempt = 1
            while (OUT / f"{name}.count.failed-{attempt}.json").exists():
                attempt += 1
            target.rename(OUT / f"{name}.count.failed-{attempt}.json")
        projection = SolutionProjection.model_validate_json(
            (ROOT / "evidence/ranking-stage/m2/solutions" / f"{name}.json").read_text())
        prepared = prepare_results(projection, CONFIG)
        payload = {"model": CONFIG.model, "instructions": prepared.instructions,
            "input": authoring_payload(prepared),
            "text": {"format": {"type": "json_schema", "name": "ResultsDocument",
                "strict": True, "schema": to_strict_json_schema(ResultsDocument)}},
            "truncation": "disabled"}
        request_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        (OUT / f"{name}.count.request.json").write_text(request_text + "\n")
        print(f"{name}: counting complete input", flush=True)
        result: dict[str, object]
        try:
            response = client.post("/responses/input_tokens", cast_to=dict[str, object], body=payload)
            result = {"status": "success", "response": response}
        except (APIError, ValueError) as exc:
            result = {"status": "error", "error_type": type(exc).__name__,
                "status_code": getattr(exc, "status_code", None)}
        result.update({"model": CONFIG.model, "request_digest": content_digest(request_text),
            "input_bytes": prepared.input_bytes,
            "source_digest": prepared.source_digest})
        target.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"case": name, **result}), flush=True)
        if result["status"] != "success":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
