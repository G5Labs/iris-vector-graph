#!/usr/bin/env python3
"""Merge the per-check JSON files of a core-models run into RESULTS.json, adding each check's log path and peak RSS.

    merge_results.py <run-out-dir> <RESULTS.json> [--register]

With --register every check is registered through tools/register_run.py (lane core-models): kind `control` for
controls, `mc` otherwise; result `pass` / `expected-violation` when the expectation was met, `fail` otherwise.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

out, dest = Path(sys.argv[1]), Path(sys.argv[2])
register = "--register" in sys.argv
checks = []
for f in sorted((out / "json").glob("*.json")):
    data = json.loads(f.read_text())
    for c in data["checks"]:
        log = out / "logs" / f"{c['id']}.log"
        text = log.read_text() if log.exists() else ""
        m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", text)
        c["peak_rss_mb"] = round(int(m.group(1)) / 1024) if m else None
        c["log"] = "$RUN_DIR/" + str(log.relative_to(Path(os.environ["RUN_DIR"]))) if log.exists() else None
        checks.append(c)
order = {"M1": 0, "M2": 1, "M3-retry": 2, "M3-readers": 3, "refinement": 4}
checks.sort(key=lambda c: (order.get(c["machine"], 9), c["id"]))
meta = json.loads(next((out / "json").glob("*.json")).read_text())
res = {k: meta[k] for k in ("crate", "explorer_rev", "product_pin", "max_states")}
res["summary"] = {"checks": len(checks), "met": sum(c["met"] for c in checks),
                  "truncated": sum(c["exhaustive"] == "truncated" for c in checks)}
res["checks"] = checks
dest.write_text(json.dumps(res, indent=1) + "\n")
print(f"{dest}: {res['summary']}")
if register:
    root = Path(__file__).resolve().parents[3]
    for c in checks:
        kind = "control" if c["design"] == "control" else "mc"
        result = ("expected-violation" if c["violated"] else "pass") if c["met"] else "fail"
        observes = (f"{c['machine']} {c['design']}: {c['what']} | expect {c['expectation']} | {c['result']}; "
                    f"{c['states']} states, {c['exhaustive']}")
        cmd = f"$CARGO_TARGET_DIR/release/ivg-core-models --only {c['id']} (models/core, CARGO_TARGET_DIR=$RUN_DIR/target/core-models)"
        subprocess.run([sys.executable, str(root / "tools" / "register_run.py"), f"core-{c['id']}", kind, result,
                        str(out / "logs" / f"{c['id']}.log"), "--lane", "core-models", "--command", cmd,
                        "--observes", observes], check=True)
