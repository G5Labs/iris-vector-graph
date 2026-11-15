#!/usr/bin/env python3
"""Full per-module statement lists for the classes the frame sub-lane left unobserved, with how each line was
attributed (inventory entry or file owners). Uses structural/frame/shape_census.py's scanner unchanged (imported).

    python census_full.py OUT.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "frame"))
import shape_census as SC  # noqa: E402

UNOBSERVED = {"01": ["sql-ddl", "sql-delete-key", "sql-delete-predicate", "sql-update"], "02": ["sql-ddl"], "03": ["sql-ddl"],
              "04": ["sql-ddl", "sql-delete-predicate", "sql-update"], "05": ["sql-ddl"], "06": ["sql-ddl"],
              "07": ["sql-ddl", "sql-insert", "sql-update"], "08": ["sql-ddl"],
              "09": ["global-increment", "global-kill", "global-merge", "global-set", "sql-ddl"], "10": ["sql-ddl"],
              "11": ["sql-ddl"], "12": ["sql-update"], "13": ["sql-delete-key"], "14": ["sql-ddl"], "15": ["sql-ddl"],
              "17": ["sql-ddl", "sql-update"]}


def main() -> int:
    inv = json.loads(SC.INV.read_text())
    files = {f["file"]: f["owners"] for f in inv["files"] if f.get("owners")}
    entries = defaultdict(list)
    for e in inv["entries"]:
        if e.get("owners") and e.get("end"):
            entries[e["file"]].append(e)
    out = defaultdict(lambda: defaultdict(list))
    for f, owners in files.items():
        p = SC.REPO / f
        if p.suffix not in (".py", ".cls") or not p.exists():
            continue
        if not (f.startswith("iris_vector_graph/") or f.startswith("iris_src/") or f.startswith("api/")):
            continue
        for rel, line, k, txt in SC.scan_file(p):
            best = None
            for e in entries.get(f, []):
                if e["line"] <= line <= (e.get("end") or e["line"]) and e.get("owners"):
                    if best is None or (e["end"] - e["line"]) < (best["end"] - best["line"]):
                        best = e
            mods = best["owners"] if best else owners
            for m in mods:
                if k in UNOBSERVED.get(m, []):
                    out[m][k].append({"at": f"{rel}:{line}", "entry": best["name"] if best else None,
                                      "by": "entry" if best else "file-owners", "text": txt})
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
    for m in sorted(out):
        for k, v in sorted(out[m].items()):
            print(m, k, len(v), "entry:", sum(1 for x in v if x["by"] == "entry"), "file:", sum(1 for x in v if x["by"] != "entry"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
