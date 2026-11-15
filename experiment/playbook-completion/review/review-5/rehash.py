#!/usr/bin/env python3
"""Review 5: re-hash the primary log (and the pinned JSON log, if any) of every run record listed in argv[1].

    python review/review-5/rehash.py review/review-5/scope-records.txt > rehash.json
"""
import hashlib, json, os, sys
from pathlib import Path

run_dir = Path(os.environ["RUN_DIR"])
out, bad = [], []
for rel in Path(sys.argv[1]).read_text().split():
    rec = json.loads(Path(rel).read_text())
    row = {"id": rec["id"], "lane": rec.get("lane"), "kind": rec["kind"], "result": rec["result"]}
    for key in ("log", "json_log"):
        if key not in rec:
            continue
        p = Path(rec[key].replace("$RUN_DIR", str(run_dir)))
        if not p.exists():
            row[key] = "MISSING"; bad.append((rec["id"], key)); continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        want = rec["log_sha256"] if key == "log" else rec.get("json_sha256")
        ok = (h == want and p.stat().st_size == rec["log_bytes"]) if key == "log" else (want is None or h == want)
        row[key] = "ok" if ok else f"MISMATCH {h[:12]} vs {str(want)[:12]}"
        if not ok:
            bad.append((rec["id"], key))
    out.append(row)
json.dump({"records": len(out), "problems": bad, "rows": out}, sys.stdout, indent=1)
