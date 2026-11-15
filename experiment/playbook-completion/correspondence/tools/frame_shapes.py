#!/usr/bin/env python3
"""§3.6 frame per statement shape: the write statements of each module's handlers and whether a frame-checked trace
executed them.

    python frame_shapes.py COVERAGE.json --json OUT

A write statement is an executable .cls line of a handler method (actions.py, grouped by module) that SETs, KILLs or
$Increments a durable global (not process-private ^||), runs SQL INSERT / UPDATE / DELETE / DROP, or %Saves an object.
Executed = the line monitor counted it in a checked trace (coverage.json). Every transaction of those traces passed
the journal frame check (its written stores are in its operation's declared footprint), so an executed write statement
wrote only declared stores in every execution observed; an unexecuted one has no frame evidence.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from actions import ACTIONS  # noqa: E402
import cls_lines  # noqa: E402

WRITE = re.compile(r"\^(?!\|\|)[%\w.]+(?:\((?:[^()]|\([^()]*\))*\))?\s*=(?!=)|\b(?:Kill|K)\s+[^;]*\^(?!\|\|)|"
                   r"\$I(?:ncrement)?\(\^(?!\|\|)|\b(?:INSERT\s+INTO|UPDATE\s+[\w\"]|DELETE\s+FROM|DROP\s+TABLE)\b|"
                   r"%Save\(\)|%KillExtent", re.I)
MODULE = {"commit": "11", "replay": "11", "enable-genesis": "11", "reenable-adoption": "11", "disable-strict": "11",
          "erase-graph": "12", "erase-nodes": "12", "erase-edges-all": "12",
          "redact-start": "13", "redact-batch": "13", "redact-final": "13", "redact-stop-resume": "13",
          "verify": "14", "readers": "14", "post-commit-properties": "14"}


def main() -> int:
    cov = json.loads(Path(sys.argv[1]).read_text())
    out_p = Path(sys.argv[sys.argv.index("--json") + 1])
    per_method = {(c, m["method"]): m for c, v in cov["classes"].items() for m in v["methods"]}
    src = {}
    res = {}
    for a in ACTIONS:
        mod = MODULE[a["id"]]
        r = res.setdefault(mod, {"write_statements": {}, "executed": 0, "unexecuted": []})
        for cls, methods in a["methods"].items():
            lines = src.setdefault(cls, cls_lines.class_file(cls).read_text().split("\n"))
            for meth in methods:
                m = per_method.get((cls, meth))
                info = next((x for x in cls_lines.methods(cls) if x["method"] == meth), None)
                if info is None:
                    continue
                unexec = set(m["unexercised"]) if m else set(info["executable"])
                for n in info["executable"]:
                    if WRITE.search(lines[n - 1]):
                        key = f"{cls_lines.class_file(cls).relative_to(cls_lines.REPO)}:{n}"
                        if key in r["write_statements"]:
                            continue
                        hit = n not in unexec
                        r["write_statements"][key] = {"method": f"{cls}.{meth}", "executed": hit, "text": lines[n - 1].strip()[:110]}
    for mod, r in res.items():
        r["total"] = len(r["write_statements"])
        r["executed"] = sum(1 for v in r["write_statements"].values() if v["executed"])
        r["unexecuted"] = [f"{k} {v['text']}" for k, v in r["write_statements"].items() if not v["executed"]]
        print(f"module {mod}: {r['executed']}/{r['total']} write statements executed under the frame check")
        for u in r["unexecuted"]:
            print("   unexecuted", u[:150])
    out_p.write_text(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
