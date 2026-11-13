#!/usr/bin/env python3
"""Assign the coordinator's storage-order scan sites to modules 01-06 (gate 3.4-storage-order).

Reads $RUN_DIR/checks/storage-order.json, dedupes by file:line, finds each Python site's enclosing function (ast)
and the inventory entry points (models/breadth-a/inventory/NN.json) whose source range contains the line, and the
module exclusions (excluded_by_scope). Prints a context window for review and writes
$RUN_DIR/breadth-a/storage-order/sites.json. The dispositions themselves are reviewed by hand from the printed context
and recorded in models/breadth-a/storage-order/NN.json (see dispositions.py).

    python experiment/playbook-completion/models/breadth-a/tools/storage_order_sites.py [--context N]
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
INV = HERE.parent / "inventory"
MODULES = ["01", "02", "03", "04", "05", "06"]


def enclosing(path: Path, line: int) -> str:
    if path.suffix != ".py":
        # ObjectScript: the nearest ClassMethod/Method line above
        name = "?"
        for i, ln in enumerate(path.read_text(errors="replace").splitlines(), 1):
            if i > line:
                break
            if ln.startswith(("ClassMethod ", "Method ", "Query ")):
                name = ln.split("(")[0].split()[-1]
        return name
    tree = ast.parse(path.read_text())
    best = ("<module>", 0)
    stack = [(tree, "")]
    while stack:
        node, prefix = stack.pop()
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}{ch.name}"
                if ch.lineno <= line <= (ch.end_lineno or ch.lineno) and not isinstance(ch, ast.ClassDef):
                    if ch.lineno >= best[1]:
                        best = (q, ch.lineno)
                stack.append((ch, q + "."))
    return best[0]


def main() -> int:
    ctx = int(sys.argv[sys.argv.index("--context") + 1]) if "--context" in sys.argv else 0
    run_dir = Path(os.environ["RUN_DIR"])
    sites = json.loads((run_dir / "checks" / "storage-order.json").read_text())
    inv = {m: json.loads((INV / f"{m}.json").read_text()) for m in MODULES}
    scope = {m: set(inv[m]["scope_files"]["python"]) | set(inv[m]["scope_files"]["cls"]) for m in MODULES}
    seen = {}
    for s in sites:
        key = (s["file"], s["line"])
        seen.setdefault(key, {"file": s["file"], "line": s["line"], "kinds": set(), "excerpts": []})
        seen[key]["kinds"].add(s["kind"])
        seen[key]["excerpts"].append(s["sql"][:200])
    out = []
    for (f, line), rec in sorted(seen.items()):
        path = REPO / f
        func = enclosing(path, line)
        in_scope = [m for m in MODULES if f in scope[m]]
        eps = [(m, e["id"]) for m in MODULES for e in inv[m]["entry_points"]
               if e.get("file") == f and e.get("start", 0) <= line <= e.get("end", -1)]
        excl = [(m, x["name"], x.get("reason", "")) for m in MODULES for x in inv[m].get("excluded_by_scope", [])
                if x.get("source", "").startswith(f + ":") and
                int(x["source"].split(":")[1].split("-")[0]) <= line <= int(x["source"].split(":")[1].split("-")[-1])]
        r = {"file": f, "line": line, "function": func, "kinds": sorted(rec["kinds"]), "scope_modules": in_scope,
             "entry_points": eps, "excluded": excl, "excerpt": max(rec["excerpts"], key=len)}
        out.append(r)
        print(f"== {f}:{line} fn={func} scope={in_scope} eps={[m for m, _ in eps]} excl={[m for m, *_ in excl]}")
        if ctx and in_scope:
            lines = path.read_text(errors="replace").splitlines()
            for i in range(max(0, line - ctx - 1), min(len(lines), line + ctx)):
                print(f"   {i + 1:>5}: {lines[i][:160]}")
    od = run_dir / "breadth-a" / "storage-order"
    od.mkdir(parents=True, exist_ok=True)
    (od / "sites.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(out)} unique sites; {sum(1 for r in out if r['scope_modules'])} in files of modules 01-06")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
