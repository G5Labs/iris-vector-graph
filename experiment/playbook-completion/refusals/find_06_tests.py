#!/usr/bin/env python3
"""Module 06 helper: for each `tested:` reference of a VEC X statement, find registered runs (evidence/runs) whose
log holds that test's pytest -v line with PASSED (or FAILED/SKIPPED/ERROR), so holds-run citations are mechanical.

    python find_06_tests.py > $RUN_DIR/refusals/06/tested-lookup.json
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parent
RD = Path(os.environ["RUN_DIR"])
xs = json.loads((HERE / "x-statements.json").read_text())
runs = []
for f in sorted((COMPLETION / "evidence" / "runs").glob("*.json")):
    d = json.loads(f.read_text())
    p = Path(d["log"].replace("$RUN_DIR", str(RD)))
    if p.is_file() and p.stat().st_size < 30_000_000:
        runs.append((d["id"], d["result"], p))
texts = {}
out = {}
for s in xs["statements"]:
    if s["module"] != sys.argv[1] if len(sys.argv) > 1 else "06":
        continue
    for m in re.finditer(r"tested:([^\s;]+)", s["evidence"]):
        ref = m.group(1)
        path, _, name = ref.partition("::")
        pat = re.compile(re.escape(path) + r"::(?:[A-Za-z0-9_]+::)?" + re.escape(name) + r"(?:\[[^\]]*\])? (PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)")
        hits = []
        for rid, res, p in runs:
            if rid not in texts:
                try:
                    texts[rid] = p.read_text(errors="replace")
                except Exception:
                    texts[rid] = ""
            for mm in pat.finditer(texts[rid]):
                hits.append({"run": rid, "run_result": res, "line": mm.group(0)})
        out.setdefault(s["id"], []).append({"tested": ref, "hits": hits})
print(json.dumps(out, indent=1))
