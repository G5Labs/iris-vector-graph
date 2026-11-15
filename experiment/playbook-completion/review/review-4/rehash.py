#!/usr/bin/env python3
"""Review 4: re-hash every in-scope run record's log (and json_log if present)."""
import hashlib, json, os, sys
from pathlib import Path
run_dir = Path(os.environ["RUN_DIR"])
repo = Path(sys.argv[1]); lst = Path(sys.argv[2])
out = []
for rel in lst.read_text().split():
    rec = json.loads((repo / rel).read_text())
    row = {"id": rec["id"], "kind": rec["kind"], "result": rec["result"]}
    for key in ("log", "json_log"):
        if key not in rec: continue
        p = Path(rec[key].replace("$RUN_DIR", str(run_dir)))
        if not p.exists():
            row[key] = "MISSING"; continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if key == "log":
            row[key] = "ok" if h == rec["log_sha256"] and p.stat().st_size == rec["log_bytes"] else f"MISMATCH {h[:12]} vs {rec['log_sha256'][:12]}"
        else:
            row[key] = "present " + h[:12]
    out.append(row)
json.dump(out, sys.stdout, indent=1)
