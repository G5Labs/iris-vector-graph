#!/usr/bin/env python3
"""Per-module verdict over a registered row-permutation log (permutation.py output), so each module's matrix cell
cites a run whose result is that module's own: pass when every read holds (a documented sample passing its validator
counts as holding), fail when any read differs, or when the module's writes or harness failed.

    python verdict.py RAW.json MOD OUT.json
"""
import json
import sys
from pathlib import Path

raw, mod, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
d = json.loads(raw.read_text())
r = d["modules"][mod]
cmp = r.get("comparison", {})
bad = {k: v for k, v in cmp.items() if v["verdict"] != "holds"}
res = {"source": str(raw.name), "module": mod, "reads": {k: v["verdict"] for k, v in cmp.items()},
       "modes": {k: v["mode"] for k, v in cmp.items()}, "write_errors": r.get("write_errors"),
       "harness_error": r.get("harness_error"),
       "differing": {k: v.get("values") for k, v in bad.items()},
       "sample_validators": {k: v.get("valid") for k, v in cmp.items() if v["mode"] == "sample"},
       "result": "pass" if cmp and not bad and not r.get("write_errors") and not r.get("harness_error") else "fail"}
out.write_text(json.dumps(res, indent=1, default=str))
print(mod, res["result"], json.dumps(res["reads"]))
