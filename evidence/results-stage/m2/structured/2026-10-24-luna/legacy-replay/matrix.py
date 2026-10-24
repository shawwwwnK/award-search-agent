from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path.cwd()
output = Path(sys.argv[1])
if len(sys.argv) > 2:
    records = json.loads(Path(sys.argv[2]).read_text())["artifacts"]
else:
    by_version = {}
    for path in sorted(Path("evidence").rglob("*artifact.json")):
        if "golden-diagnostic" in str(path):
            continue
        try:
            raw = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            continue
        version = raw.get("contract_version", "")
        if version.startswith("results-artifact-"):
            by_version.setdefault(version, path)
    chosen = list(by_version.values())
    chosen.extend(Path("evidence/results-stage/m2/compact-input/2026-10-20-luna").glob("*/artifact.json"))
    records = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in dict.fromkeys(chosen)]

schema_code = '''import json
from award_agent.results.request import response_schema
from award_agent.providers.contracts import content_digest
print(json.dumps({v:content_digest(response_schema(v)) for v in ("results-prepared-v1","results-prepared-v2","results-prepared-v3","results-prepared-v4")}))'''
schemas = subprocess.run([sys.executable, "-c", schema_code], capture_output=True, text=True, check=True)
results = []
for seed in (11, 23, 37):
    for record in records:
        code = '''import json,sys
from pathlib import Path
from award_agent.results import ResultsArtifact,replay_results
p=Path(sys.argv[1]); a=ResultsArtifact.model_validate_json(p.read_bytes())
assert replay_results(a)==a.rendered_markdown
print(json.dumps({"version":a.contract_version,"rendered_digest":a.rendered_digest}))'''
        run = subprocess.run([sys.executable, "-c", code, record["path"]],
                             env={**os.environ, "PYTHONHASHSEED": str(seed)},
                             capture_output=True, text=True)
        results.append({"path": record["path"], "seed": seed, "exit_code": run.returncode,
                        "stdout": run.stdout.strip(), "stderr": run.stderr[-2000:]})
        print(f'{seed} {record["path"]}: {"PASS" if run.returncode == 0 else "FAIL"}', flush=True)
result = {"artifacts": records, "schema_digests": json.loads(schemas.stdout), "results": results,
          "unchanged": all(hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() == r["sha256"] for r in records)}
output.write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps({"runs": len(results), "failed": sum(r["exit_code"] != 0 for r in results), "output": str(output)}))
