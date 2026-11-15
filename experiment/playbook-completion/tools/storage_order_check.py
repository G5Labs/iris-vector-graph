#!/usr/bin/env python3
"""§3.4 storage-order check (playbook principle 5: never depend on storage or insertion order).

    python storage_order_check.py [--self-test] [--json OUT]

Flags every SQL text in product code (iris_vector_graph/**/*.py string literals, iris_src/src/**/*.cls lines) that
takes a prefix of a result (SELECT TOP n, LIMIT, FETCH FIRST) without an ORDER BY in the same statement text. Such a
statement depends on the engine's scan order unless its WHERE pins at most one row by a unique key. The check cannot
decide that last condition, so each site is a candidate the matrix must disposition: `unique-key` (cite the key),
`existence-only` (the row's identity is not used, e.g. SELECT TOP 1 1 ... for an existence test), or a finding.
The self-test injects one ordered and one unordered statement and requires exactly the unordered one to be flagged.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PREFIX = re.compile(r"\bSELECT\s+(?:DISTINCT\s+)?TOP\s+\??\d*|\bLIMIT\s+[\d?]|\bFETCH\s+FIRST\b", re.I)
ORDER = re.compile(r"\bORDER\s+BY\b", re.I)
EXISTS = re.compile(r"\bSELECT\s+TOP\s+1\s+1\b", re.I)


def py_sites(path: Path, text: str):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        s = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
        elif isinstance(node, ast.JoinedStr):
            s = "".join(v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}" for v in node.values)
        if s and PREFIX.search(s) and re.search(r"\bSELECT\b", s, re.I) and not ORDER.search(s):
            yield node.lineno, " ".join(s.split())[:160]


def cls_sites(path: Path, text: str):
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if PREFIX.search(line) and re.search(r"\bSELECT\b", line, re.I):
            window = " ".join(lines[i - 1:i + 4])  # embedded &sql() statements span lines
            if not ORDER.search(window):
                yield i, " ".join(line.split())[:160]


def scan(files):
    out = []
    for p, text in files:
        gen = py_sites(p, text) if p.suffix == ".py" else cls_sites(p, text)
        for line, s in gen:
            out.append({"file": str(p.relative_to(REPO)) if p.is_absolute() else str(p), "line": line,
                        "kind": "existence-only" if EXISTS.search(s) else "candidate", "sql": s})
    return out


def product_files():
    for p in sorted((REPO / "iris_vector_graph").rglob("*.py")):
        yield p, p.read_text(errors="replace")
    for p in sorted((REPO / "iris_src" / "src").rglob("*.cls")):
        yield p, p.read_text(errors="replace")


def main() -> int:
    if "--self-test" in sys.argv:
        f = [(Path("t.py"), 'a = "SELECT TOP 1 id FROM t WHERE g = ?"\nb = "SELECT TOP 1 id FROM t ORDER BY id"\n')]
        r = scan(f)
        ok = len(r) == 1 and r[0]["line"] == 1
        print("self-test", "PASS" if ok else "FAIL", r)
        return 0 if ok else 1
    r = scan(product_files())
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(r, indent=1))
    by = {}
    for x in r:
        by[x["kind"]] = by.get(x["kind"], 0) + 1
    print(f"{len(r)} prefix-without-order sites: {by}")
    for x in r[:400]:
        print(f"{x['kind']:15} {x['file']}:{x['line']}  {x['sql'][:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
