"""Run the declared three-case diagnostic once, retaining each output and exact replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from award_agent.cli.results import main as results_main

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CASES = ("sfo_to_bkk_positioning", "exact_business", "mixed_access")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=OUT / "config.json")
    parser.add_argument("--label", choices=("baseline", "guided", "bound", "declared"),
                        default="baseline")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    for name in CASES:
        stem = name if args.label == "baseline" else f"{name}.{args.label}"
        artifact = OUT / f"{stem}.artifact.json"
        answer = OUT / f"{stem}.md"
        if not artifact.exists():
            print(f"{name}: live authoring begins; at most two generation calls", flush=True)
            code = results_main(["author", "--projection",
                str(ROOT / "evidence/ranking-stage/m2/solutions" / f"{name}.json"),
                "--config", str(args.config), "--live", "--output", str(artifact)])
            print(f"{name}: author command exit {code}", flush=True)
        if not artifact.exists():
            raise RuntimeError(f"{name}: no diagnostic artifact was retained")
        if not answer.exists():
            results_main(["replay", "--artifact", str(artifact), "--output", str(answer)])
        data = json.loads(artifact.read_text())
        if answer.read_bytes() != data["rendered_markdown"].encode("utf-8"):
            raise RuntimeError(f"{name}: replay bytes differ")
        print(json.dumps({"case": name, "delivery": data["delivery_outcome"],
            "validation": data["validation_outcome"], "attempts": len(data["attempts"]),
            "notices": len(data["notices"]), "replay_bytes": answer.stat().st_size}), flush=True)


if __name__ == "__main__":
    main()
