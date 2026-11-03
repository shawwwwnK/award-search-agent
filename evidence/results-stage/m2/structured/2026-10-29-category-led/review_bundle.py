"""Prepare source-grounded, profile-blind answer bundles from saved live runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import ledger
import run

HERE = Path(__file__).resolve().parent
INDEX = HERE / "review-index.json"


def selection_wire_audit(wire: dict[str, object], *,
                         references: dict[str, object] | None = None) -> dict[str, object]:
    """Keep raw category witnesses and omission notes visible to blind review."""
    style_audit = wire.get("style_audit")
    indexed = "benchmark_alias" in wire
    if isinstance(style_audit, dict):
        omitted = [{"style": style, "reason": row["omission_reason"]}
                   for style, row in style_audit.items()
                   if isinstance(row, dict) and
                   (row.get("choice_index") if indexed else row.get("r")) is None
                   and isinstance(row.get("omission_reason"), str)
                   and row["omission_reason"].strip()]
    else:
        omitted = wire.get("omitted", [])
    result = {"free_choices": wire.get("choices", []),
              "style_audit": style_audit, "omitted_reasons": omitted}
    if not indexed:
        return result
    choices = wire.get("choices")
    journeys = references.get("journeys") if isinstance(references, dict) else None
    cash = references.get("cash") if isinstance(references, dict) else None
    if (not isinstance(choices, list) or not isinstance(style_audit, dict) or
            not isinstance(journeys, dict) or not isinstance(cash, dict)):
        raise TypeError("indexed selection audit lacks exact choices or references")
    witnesses: dict[str, dict[str, object]] = {}
    for style, row in style_audit.items():
        if not isinstance(row, dict) or "choice_index" not in row:
            raise ValueError("indexed style audit is incomplete")
        index = row["choice_index"]
        if index is None:
            continue
        if type(index) is not int or index < 0 or index >= len(choices):
            raise ValueError("indexed style witness is outside returned choices")
        choice = choices[index]
        if not isinstance(choice, dict) or choice.get("k") != "j":
            raise ValueError("indexed style witness does not name a journey")
        alias = choice.get("r")
        if not isinstance(alias, str):
            raise TypeError("indexed style witness alias is not text")
        canonical = journeys.get(alias)
        if canonical is None:
            raise ValueError("indexed style witness lacks an exact source identity")
        if not isinstance(canonical, str):
            raise TypeError("indexed style witness source identity is not text")
        witnesses[style] = {"choice_index": index, "alias": alias,
                            "canonical_id": canonical}
    benchmark_alias = wire["benchmark_alias"]
    if benchmark_alias is not None and (
            not isinstance(benchmark_alias, str) or
            not isinstance(cash.get(benchmark_alias), str)):
        raise ValueError("indexed cash benchmark lacks an exact source identity")
    result.update({"benchmark_alias": benchmark_alias,
                   "benchmark_canonical_id": cash.get(benchmark_alias)
                       if benchmark_alias is not None else None,
                   "indexed_witnesses": witnesses,
                   "raw_selection_wire": wire})
    return result


def condition_sidecar(request: dict[str, object]) -> dict[str, object] | None:
    """Expose only the exact source condition rows and their record aliases."""
    packet = json.loads(str(request["input"])).get("packet")
    if not isinstance(packet, dict) or "condition_applicability" not in packet:
        return None
    rows = packet["condition_applicability"]
    records = packet.get("authoring_records")
    if not isinstance(rows, list) or not isinstance(records, dict):
        raise TypeError("saved condition packet is incomplete")
    aliases = {alias: {"role": record["role"], "member": record["member"]}
               for alias, record in records.items()}
    if any(alias not in aliases for row in rows for alias in row["applies_to"]):
        raise ValueError("condition aliases are absent from saved authoring records")
    return {"condition_applicability": rows, "alias_members": aliases}


def create(run_name: str, bundle_name: str) -> Path:
    if (not run_name or Path(run_name).name != run_name or
            not bundle_name or Path(bundle_name).name != bundle_name):
        raise ValueError("run and bundle names must be single path components")
    source = run.RUNS / run_name
    artifact_path = source / "artifact.json"
    if not artifact_path.is_file():
        raise FileNotFoundError("run artifact is missing")
    if ledger.read_json(source / "settings.json").get("recovery_diagnostic"):
        raise ValueError("controlled recovery cannot enter blind natural-answer review")
    from preview_loader import render_saved

    from award_agent.results.category import parse_category_artifact, replay_category_results

    artifact = parse_category_artifact(artifact_path.read_bytes())
    replayed = replay_category_results(artifact)
    if replayed != artifact.resolved or replayed is None:
        raise ValueError("saved answer does not replay or is unavailable")
    if artifact.selected_pass_index is None:
        raise ValueError("delivered answer lacks selected pass")
    document = artifact.passes[artifact.selected_pass_index].document
    if document is None:
        raise ValueError("selected pass lacks document")
    markdown, html = render_saved(source, artifact)
    if ((source / "answer-preview.md").read_text() != markdown or
            (source / "answer-preview.html").read_text() != html):
        raise ValueError("saved review preview differs from replay")
    index = ledger.read_json(INDEX) if INDEX.exists() else {}
    if bundle_name in index or any(row["run"] == run_name for row in index.values()):
        raise ValueError("review bundle already indexed")
    target = HERE / "review-bundles" / bundle_name
    target.mkdir(parents=True, exist_ok=False)
    ledger.write_new(target / "document.json", document.model_dump(mode="json"))
    resolved_for_review = replayed.model_dump(mode="json")
    resolved_for_review.pop("findings", None)
    ledger.write_new(target / "resolved.json", resolved_for_review)
    ledger.write_new(target / "evidence.json", artifact.evidence.model_dump(mode="json"))
    references = artifact.selector_prepared.structured.references.model_dump(mode="json")
    ledger.write_new(target / "references.json", references)
    selector = artifact.passes[0]
    selection_wire = json.loads(selector.raw_wire) if selector.raw_wire else {}
    landscape = ((artifact.focus_prepared.packet.get("category_landscape") or {})
                 if artifact.focus_prepared is not None else {})
    ledger.write_new(target / "selection-audit.json", {
        "selected": selector.selection.model_dump(mode="json") if selector.selection else None,
        **selection_wire_audit(selection_wire, references=references),
        "category_landscape": landscape,
        "availability_guidance": replayed.availability_guidance,
    })
    request = ledger.read_json(source / f"pass-{artifact.selected_pass_index + 1:02d}"
                               / "generation-request.json")
    condition_data = condition_sidecar(request)
    if condition_data is not None:
        ledger.write_new(target / "condition-applicability.json", condition_data)
    (target / "answer.md").write_text(markdown, encoding="utf-8")
    (target / "answer.html").write_text(html, encoding="utf-8")
    index[bundle_name] = {"run": run_name,
                          "artifact_sha256": ledger.sha256(artifact_path),
                          "answer_sha256": ledger.sha256(target / "answer.md")}
    temporary = INDEX.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    temporary.replace(INDEX)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    print(create(args.run, args.bundle))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
