"""Verify saved Results and assemble the local early-2027 reviewer index. No live calls."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from award_agent.results import replay_results
from award_agent.results.contracts import ResultsArtifact
from award_agent.results.core import check_document

HERE = Path(__file__).resolve().parent


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    verified = []
    for path in sorted(HERE.rglob("results-artifact.json")):
        artifact = ResultsArtifact.model_validate_json(path.read_bytes())
        replay_error = None
        try:
            markdown = replay_results(artifact)
            assert markdown == (path.parent / "answer.md").read_text(), path
        except ValueError as error:
            replay_error = str(error)
            assert replay_error == "saved Results check receipt differs from source", path
            # Preserve the receipt. Diagnose order-only differences without accepting replay.
            for attempt in artifact.attempts:
                if attempt.document is not None:
                    fresh = check_document(attempt.document, artifact.projection,
                                           version=artifact.contract_version)
                    assert Counter(f.model_dump_json() for f in fresh) == Counter(
                        f.model_dump_json() for f in attempt.findings), path
            markdown = (path.parent / "answer.md").read_text()
        assert artifact.projection.model_dump(mode="json") == read(path.parent / "solutions.json"), path
        verified.append({"artifact": str(path.relative_to(HERE)),
                         "delivery": artifact.delivery_outcome,
                         "markdown_bytes": len(markdown.encode()),
                         "source_projection_equal": True, "exact_results_replay": replay_error is None,
                         "replay_error": replay_error,
                         "finding_order_only_mismatch": replay_error is not None})

    usage = read(HERE / "early-2027/usage-summary.json")
    manifest = read(HERE / "cases-early-2027.json")
    rows = []
    standard_policy = read(HERE.parents[2] / "data/provider_capabilities/provider-stage-current.json")["policy"]

    def valid_profile(directory: Path, summary: dict) -> bool:
        policy = read(directory / "provider-bundle.json")["policy"]
        assert read(directory / "provider-result.json")["execution_plan"]["policy"] == policy, directory
        return policy == standard_policy if summary["provider_profile"] == "standard" else (
            policy["award_budget"]["requests"] == 3 and policy["cash_budget"]["requests"] == 1)

    for case_id in manifest["cases"]:
        root = HERE / "early-2027/runs" / case_id
        attempts = [(p.parent, read(p)) for p in root.rglob("summary.json")]
        completed = [(p, d) for p, d in attempts if (p / "results-artifact.json").exists()]
        assert completed, (case_id, "missing terminal Results artifact")
        eligible = [(p, d) for p, d in completed if valid_profile(p, d)]
        assert eligible, (case_id, "no correctly bound acquisition profile")
        directory, summary = max(eligible, key=lambda item: (item[0] / "results-artifact.json").stat().st_mtime_ns)
        chain = []
        current = directory
        while True:
            stage_summary = read(current / "summary.json")
            chain.append((current, stage_summary))
            if not stage_summary.get("resume_from"):
                break
            current = Path(stage_summary["resume_from"])
        stage_times: dict[str, float] = {}
        for _, attempt in reversed(chain):
            for stage, info in attempt["stages"].items():
                if "elapsed_seconds" in info:
                    stage_times[stage] = info["elapsed_seconds"]
        initial = read(root / "intent.json")
        parsed = initial["parsed_request"]
        observed = parsed.get("departure_window")
        expected = manifest["cases"][case_id]["expected_departure_window"]
        date_match = observed is not None and all(observed.get(k) == v for k, v in expected.items())
        effective = read(directory / "session.json")["revisions"][-1]["effective_request"]
        assert all(effective["departure_window"][k] == v for k, v in expected.items()), directory
        assert effective["travelers"] == 1, directory
        matched = read(directory / "matched.json")
        provider = read(directory / "provider-result.json")
        result = read(directory / "results-artifact.json")
        selected = result.get("selected_attempt")
        selected_count = None
        selected_findings = []
        if selected is not None:
            selected_findings = result["attempts"][selected]["findings"]
            document = result["attempts"][selected].get("document")
            if document:
                selected_count = len(document.get("selection", {}).get("journey_ids", []))
        metric = usage["cases"][case_id]
        comparisons = [{"trace": str(p.relative_to(HERE)), "profile": d["provider_profile"],
                        "valid_profile_comparison": valid_profile(p, d),
                        "results": d["stages"]["results"],
                        "ranked_journeys": d["stages"]["ranking"]["journeys"],
                        "attempt_live_seconds": d.get("live_pipeline_seconds"),
                        "answer": str((p / "answer.md").relative_to(HERE))}
                       for p, d in completed]
        rows.append({"case": case_id, "input": read(root / "case.json")["executed_input"],
                     "reference_date": "2026-10-08", "expected_departure_window": expected,
                     "initial_action": initial["clarification"]["action"],
                     "initial_departure_matches_declared_window": date_match,
                     "initial_travelers": parsed.get("travelers"),
                     "final_departure_matches_declared_window": True,
                     "final_travelers_match_source": True,
                     "scripted_continuation": any((p / "scripted-answer.json").exists() for p, _ in chain),
                     "provider_profile": summary["provider_profile"],
                     "provider_status": summary["stages"]["providers"]["status"],
                     "provider_observations": len(provider["observations"]),
                     "provider_award_usage": provider["award_usage"],
                     "provider_cash_usage": provider["cash_usage"],
                     "ranking_accounting": matched["accounting"],
                     "selected_journeys": selected_count,
                     "selected_finding_outcomes": dict(Counter(f["outcome"] for f in selected_findings)),
                     "remaining_failed_findings": [{"code": f["code"], "message": f["message"]}
                                                   for f in selected_findings if f["outcome"] == "failed"],
                     "notices": len(result["notices"]),
                     "results": summary["stages"]["results"],
                     "stage_seconds": stage_times,
                     "live_stage_seconds_including_initial_and_continuation": round(sum(stage_times.values()), 3),
                     "generation_calls": metric["generation_calls"],
                     "generation_api_seconds": metric["model_api_seconds"],
                     "input_tokens": metric["input_tokens"], "output_tokens": metric["output_tokens"],
                     "estimated_generation_cost_usd": metric["generation_estimate_usd"],
                     "answer": str((directory / "answer.md").relative_to(HERE)),
                     "acquisition_profile_comparisons": comparisons,
                     "trace": str(directory.relative_to(HERE)),
                     "initial_trace": str(root.relative_to(HERE))})
    report = {"scope": "Six owner-requested early-2027 derivatives; one trial each, scripted followups labeled",
              "cross_process_replay_probe": read(HERE / "replay-order-probe.json"),
              "cost_exclusions": "Provider billing, input-token measurement billing and absent usage",
              "latency_basis": "Compose latest measured completed stages along the final continuation chain, including original intent; excludes replay, idle permission gaps and superseded acquisition/authoring runs",
              "cases": rows, "verification": verified}
    (HERE / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Early-2027 input-to-Results diagnostic", "",
             ("Six derivatives of the intent golden corpus, using reference date **2026-10-08**. "
              "These are review candidates; no end-to-end golden set has been selected."), "",
             "| Case | Initial intent | Provider profile | Admitted / conditional | Results | Live stages | Tokens (in / out) | Model estimate |",
             "| --- | --- | --- | ---: | --- | ---: | ---: | ---: |"]
    for row in rows:
        intent = "ready; date matched" if row["initial_action"] == "none" and row["initial_departure_matches_declared_window"] else "clarification required" if row["initial_action"] == "ask" else "review mismatch"
        n = f"{row['ranking_accounting']['admitted']} / {row['ranking_accounting']['conditional']}"
        lines.append(f"| [{row['case']}]({row['answer']}) | {intent} | {row['provider_profile']} | {n} | "
                     f"{row['results']['delivery']} / {row['results']['validation']} | "
                     f"{row['live_stage_seconds_including_initial_and_continuation']:.1f}s | "
                     f"{row['input_tokens']:,} / {row['output_tokens']:,} | ${float(row['estimated_generation_cost_usd']):.4f} |")
    lines += ["", ("Live latency composes the latest completed stages with initial intent and any scripted clarification; superseded budget runs, replay and permission gaps are separate. "
              "Tokens and model cost include all retained generation attempts for that case, including profile contrasts. "
              "Cost excludes provider and token-count endpoint charges. "
              "Every acquired provider result is partial. Compact runs can omit itinerary details after exhausting their budget; "
              "zero complete journeys does not mean no awards were available. Clean Results checks do not establish semantic truth."), ""]
    totals = {key: sum(c[key] for c in usage['cases'].values())
              for key in ('generation_calls', 'input_tokens', 'output_tokens')}
    cost = sum(Decimal(c['generation_estimate_usd']) for c in usage['cases'].values())
    lines += [(f"Revised campaign total, including all retained contrasts: {totals['generation_calls']} generation calls; "
               f"{totals['input_tokens']:,} input and {totals['output_tokens']:,} output tokens; estimated generation cost ${cost:.6f}."), ""]
    for row in rows:
        lines += [f"## {row['case']}", "", f"> {row['input']}", "",
                  (f"[Original intent and complete stage traces]({row['initial_trace']}/summary.json) · "
                  f"[Final stage summary]({row['trace']}/summary.json) · [Answer]({row['answer']}) · "
                  f"[Ranking dispositions]({row['trace']}/matched.json) · [Results checks and claims]({row['trace']}/results-artifact.json)"), "",
                  "Stages: " + "; ".join(f"{k} {v:.1f}s" for k, v in row["stage_seconds"].items()) + ".", ""]
        lines += [(f"Acquisition retained {row['provider_observations']} normalized observations; "
                  f"{row['provider_award_usage']['requests']} award requests including "
                  f"{row['provider_award_usage']['detail_calls']} detail calls, and "
                  f"{row['provider_cash_usage']['requests']} cash requests. "
                  f"Ranking dispositions: {row['ranking_accounting']['admitted']} admitted, "
                  f"{row['ranking_accounting']['conditional']} conditional, "
                  f"{row['ranking_accounting']['rejected']} rejected. Results selected {row['selected_journeys']} journeys."), ""]
        if row["scripted_continuation"]:
            lines += ["The original request needed clarification. A separately recorded fixture-derived answer enabled this continuation; it is not a first-pass success.", ""]
        if row["remaining_failed_findings"]:
            lines += ["Remaining failed checks (delivered with local notices):", ""]
            lines.extend(f"- `{f['code']}`: {f['message']}" for f in row["remaining_failed_findings"])
            lines += [""]
        if len(row["acquisition_profile_comparisons"]) > 1:
            lines += ["| Acquisition profile | Ranked journeys | Results | Saved answer |",
                      "| --- | ---: | --- | --- |"]
            for comparison in row["acquisition_profile_comparisons"]:
                label = comparison["profile"] if comparison["valid_profile_comparison"] else "invalid: compact reused under standard label"
                lines.append(f"| {label} | {comparison['ranked_journeys']} | "
                             f"{comparison['results']['delivery']} / {comparison['results']['validation']} | "
                             f"[Answer]({comparison['answer']}) |")
            lines += [""]
    lines += ["Replay verification: all saved source projections match. A retained annotated compact comparison has a cross-process finding-order replay defect: incomplete-observation findings iterate a Python set. Its finding content is unchanged, but exact replay is not reliable. See [hash-seed probes](replay-order-probe.json) and machine verification records; runtime code and saved receipts remain unchanged.", ""]
    lines += [("See [machine report](report.json), [per-call usage and cost](early-2027/usage-summary.json), "
              "[pricing basis](pricing-basis.json) and [metric definitions](metrics-notes.md). "
              "Earlier development attempts remain separately indexed in [original usage](usage-summary.json), "
              "including context-limit failures, initial intent misses and runner/network failures."), ""]
    (HERE / "report.md").write_text("\n".join(lines))
    print(json.dumps({"cases": len(rows), "verified_results_artifacts": len(verified),
                      "exact_replay_passes_this_process": sum(v["exact_results_replay"] for v in verified),
                      "delivered": sum(r["results"]["delivery"] == "delivered" for r in rows)}))


if __name__ == "__main__":
    main()
