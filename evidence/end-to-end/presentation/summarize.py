"""Build a live-only index from immutable Results presentation iterations."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    rows: list[dict] = []
    for iteration in sorted((ROOT / "iterations").iterdir()):
        if not iteration.is_dir():
            continue
        config_path = iteration / "config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text())
        review_path = iteration / "review.md"
        review = review_path.read_text() if review_path.exists() else ""
        status = next((line.removeprefix("Status: ").strip() for line in review.splitlines()
                       if line.startswith("Status: ")), "agent review pending")
        for case in sorted(iteration.iterdir()):
            artifact_path = case / "artifact.json"
            if not artifact_path.exists():
                continue
            artifact = json.loads(artifact_path.read_text())
            receipt = json.loads((case / "receipt.json").read_text())
            attempts = []
            for attempt in artifact["attempts"]:
                writer_receipt = attempt.get("writer_receipt") or {}
                count = attempt.get("input_token_receipt") or {}
                attempts.append({
                    "phase": attempt["phase"],
                    "outcome": attempt["outcome"],
                    "measured_input_tokens": count.get("input_tokens"),
                    "writer_usage": writer_receipt.get("usage", {}),
                    "failed_findings": sum(f["outcome"] == "failed"
                                           for f in attempt.get("findings", [])),
                })
            rows.append({
                "iteration": iteration.name,
                "case": case.name,
                "model": config["model"],
                "source_projection": receipt["source_projection"],
                "source_projection_sha256": receipt["source_projection_sha256"],
                "config_sha256": receipt["config_sha256"],
                "answer": str((case / "answer.md").relative_to(ROOT)),
                "artifact": str(artifact_path.relative_to(ROOT)),
                "receipt": str((case / "receipt.json").relative_to(ROOT)),
                "generation": artifact["generation_outcome"],
                "validation": artifact["validation_outcome"],
                "delivery": artifact["delivery_outcome"],
                "selected_attempt": artifact["selected_attempt"],
                "final_notices": len(artifact["notices"]),
                "attempts": attempts,
                "agent_review": status,
                "owner_review": "pending",
            })
    (ROOT / "index.json").write_text(json.dumps({"scope": "live Results-only iterations",
                                                 "runs": rows}, indent=2) + "\n")
    lines = ["# Live Results presentation evidence", "",
             "Each row uses a saved Ranking export and a live Results writer. Earlier iterations",
             "remain immutable. Offline authored examples are under `offline/` and are excluded here.", "",
             "| Iteration | Case | Model | Final check | Writer calls | Answer | Review |",
             "| --- | --- | --- | --- | ---: | --- | --- |"]
    for row in rows:
        label = ("generation error; no answer" if row["delivery"] != "delivered" else
                 "clean" if row["validation"] == "clean" else row["validation"])
        evidence_link = (["answer", row["answer"]] if row["delivery"] == "delivered"
                         else ["failure receipt", row["receipt"]])
        notice_text = (f"; {row['final_notices']} notices" if row["delivery"] == "delivered"
                       else "")
        lines.append(f"| {row['iteration']} | {row['case']} | {row['model']} | {label}"
                     f"{notice_text} | {len(row['attempts'])} | "
                     f"[{evidence_link[0]}]({evidence_link[1]}) | "
                     f"[review](iterations/{row['iteration']}/review.md) |")
    lines += ["", "`index.json` contains each attempt's exact writer usage, measured input",
              "tokens, failed-finding count, source/config hashes, and current review status.",
              "A clean checker outcome alone does not qualify traveler-facing prose.", ""]
    (ROOT / "index.md").write_text("\n".join(lines))
    print(f"indexed {len(rows)} live case runs")


if __name__ == "__main__":
    main()
