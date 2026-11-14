#!/usr/bin/env python3
"""Proposals for coverage records: the callers of every entry point coverage_reconcile.py reports uncovered.

    python3 experiment/playbook-completion/ontology/tools/derive_callers.py --out FILE [--module NN ...]

For each uncovered entry point it lists the call sites in the product tree at the pin (iris_src/src/**/*.cls and
iris_vector_graph/**/*.py, plus api/ and src/ for module 16) and the inventory entry point that encloses each site,
with that entry's coverage status. ObjectScript: "..Name(", "##class(Pkg.Class).Name(", "$CLASSMETHOD(...,\"Name\"",
Native API "classMethod*(\"Pkg.Class\", \"Name\"" and Python embedded "iris.cls(\"Pkg.Class\").Name(". Python:
".name(" and "name(" (ambiguous for common names; the output is a proposal, every record is reviewed by hand).
It also reports whether the declaration is Private/Internal (ObjectScript) or underscored (Python).
Nothing here decides coverage: coverage_reconcile.py validates the records written from these proposals.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage_reconcile as CR  # noqa: E402

ROOTS = ("iris_src/src/", "iris_vector_graph/", "api/", "src/", "scripts/mcp/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--module", nargs="*")
    a = ap.parse_args()
    tree = CR.PinTree()
    invs, _ = CR.run(CR.ONT, CR.ONT / "reconcile-records.json", tree)
    files = sorted(f for f in tree.files if f.startswith(ROOTS) and f.endswith((".cls", ".py")))
    texts = {f: (tree.text(f) or "").split("\n") for f in files}
    spans = {}
    for m, es in invs.items():
        for e in es:
            if e.file and e.start:
                spans.setdefault(e.file, []).append((e.start, e.end, m, e))

    def enclosing(f, ln):
        best = None
        for s, t, m, e in spans.get(f, []):
            if s <= ln <= t and (best is None or s >= best[0]):
                best = (s, m, e)
        return best

    out = {}
    for m, es in sorted(invs.items()):
        if a.module and m not in a.module:
            continue
        for e in es:
            if e.status != "uncovered" or e.kind == "file":
                continue
            n = e.name
            pats = []
            full = e.container if "." in e.container else ""
            if e.file.endswith(".cls"):
                cls = full or e.file.split("iris_src/src/")[-1][:-4].replace("/", ".")
                pats = [re.compile(r"##class\(" + re.escape(cls) + r"\)\." + re.escape(n) + r"\("),
                        re.compile(r"\$CLASSMETHOD\([^)]*\"" + re.escape(n) + r"\""),
                        re.compile(r"classMethod\w*\(\s*[\"']" + re.escape(cls) + r"[\"']\s*,\s*[\"']" + re.escape(n)),
                        re.compile(r"iris\.cls\([\"']" + re.escape(cls) + r"[\"']\)\." + re.escape(n) + r"\(")]
                own = [re.compile(r"(?<![\w.])\.\." + re.escape(n) + r"\(|\bdo \.\." + re.escape(n) + r"\b", re.I)]
                decl = texts.get(e.file, [""])[e.start - 1] if e.start else ""
                private = bool(re.search(r"\[[^\]]*\b(Private|Internal)\b", decl))
            else:
                pats = [re.compile(r"(?<![\w])\.?" + re.escape(n) + r"\(")]
                own = []
                private = n.startswith("_")
            sites = []
            for f in files:
                is_own = f == e.file
                for i, l in enumerate(texts[f], 1):
                    if e.start <= i <= e.end and is_own:
                        continue
                    hit = any(p.search(l) for p in pats) or (is_own and any(p.search(l) for p in own))
                    if hit:
                        enc = enclosing(f, i)
                        sites.append({"site": f"{f}:{i}", "in": enc[2].id if enc else None,
                                      "in_module": enc[1] if enc else None,
                                      "in_status": enc[2].status if enc else None})
            out.setdefault(m, {})[e.id] = {"file": f"{e.file}:{e.start}-{e.end}", "private": private,
                                           "callers": sites[:40], "caller_count": len(sites)}
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {a.out}: {sum(len(v) for v in out.values())} uncovered entry points")
    return 0


if __name__ == "__main__":
    sys.exit(main())
