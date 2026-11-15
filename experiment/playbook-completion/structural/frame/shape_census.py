#!/usr/bin/env python3
"""Statement-shape classes per module, from the source at the pin (the denominator of the frame cells).

    python shape_census.py --json OUT

Module of a write line: the owners of the innermost inventoried entry (models/breadth-c/inventory.json entries[],
the product-wide Scope-line assignment with line ranges) containing it, else the file's owners (files[].owners). Classes (one per write statement line):
  sql-insert, sql-update, sql-delete-key (WHERE of equalities only), sql-delete-predicate (LIKE, %STARTSWITH, IN,
  ranges, sub-selects or no WHERE), sql-ddl (CREATE/DROP/ALTER TABLE|INDEX, TRUNCATE), global-set (Set ^X(..)=),
  global-kill (Kill ^X), global-increment ($Increment/$I(^X)), global-merge (Merge ^X), obj-save (%Save),
  obj-delete (%DeleteId, %KillExtent), native-set / native-kill / native-increment (Python Native API calls on a
  "^Name" literal).
Process-private ^|| globals are not durable stores and are not counted; Python docstrings and bare string
statements are skipped (ast). Over-approximates (a line can hold several
classes; SQL split across literals is counted where its verb is).
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
INV = REPO / "experiment/playbook-completion/models/breadth-c/inventory.json"

OS = [
    ("global-set", re.compile(r"\b(?:Set|S)\b[^;]*?\^(?!\|\|)[%A-Za-z][\w.]*(?:\([^=]*\))?\s*=(?!=)", re.I)),
    ("global-kill", re.compile(r"\b(?:Kill|K)\s+[^;]*\^(?!\|\|)[%A-Za-z]", re.I)),
    ("global-increment", re.compile(r"\$I(?:ncrement)?\(\s*\^(?!\|\|)", re.I)),
    ("global-merge", re.compile(r"\b(?:Merge|M)\s+\^(?!\|\|)", re.I)),
    ("obj-save", re.compile(r"\.%Save\(")),
    ("obj-delete", re.compile(r"%DeleteId\(|%KillExtent\(|%DeleteExtent\(")),
]
SQL_INS = re.compile(r"\bINSERT\s+(?:OR\s+UPDATE\s+)?(?:%\w+\s+)*INTO\b", re.I)
SQL_UPD = re.compile(r"\bUPDATE\s+(?:%\w+\s+)*[\w\"{}.%]+\s+SET\b", re.I)
SQL_DEL = re.compile(r"\bDELETE\s+(?:%\w+\s+)*FROM\b(.*)", re.I)
SQL_DDL = re.compile(r"\b(?:CREATE|DROP|ALTER)\s+(?:UNIQUE\s+|BITMAP\s+)?(?:TABLE|INDEX|VIEW|PROCEDURE|FUNCTION)\b|\bTRUNCATE\s+TABLE\b|\bBUILD\s+INDEX\b", re.I)
PY_NATIVE = re.compile(r"\.(set|kill|increment)\(\s*[^)]*[\"']\^(?!\|\|)", re.I)


def sql_classes(text: str):
    out = []
    if SQL_INS.search(text):
        out.append("sql-insert")
    if SQL_UPD.search(text):
        out.append("sql-update")
    m = SQL_DEL.search(text)
    if m:
        rest = m.group(1)
        w = re.search(r"\bWHERE\b(.*)", rest, re.I)
        if not w or re.search(r"\bLIKE\b|%STARTSWITH|\bIN\s*\(|<|>|\bSELECT\b|\bNOT\b|\bOR\b", w.group(1), re.I):
            out.append("sql-delete-predicate")
        else:
            out.append("sql-delete-key")
    if SQL_DDL.search(text):
        out.append("sql-ddl")
    return out


def docstring_lines(text: str):
    """Line numbers of docstrings and bare string statements (not executable SQL)."""
    import ast
    out = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            out |= set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return out


def scan_file(p: Path):
    rel = str(p.relative_to(REPO))
    text = p.read_text(errors="replace")
    lines = text.splitlines()
    skip = docstring_lines(text) if p.suffix == ".py" else set()
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if p.suffix == ".cls":
            if s.startswith("///") or s.startswith("//"):
                continue
            code = s.split("//")[0] if '"' not in s else s
            cls_ = [k for k, rx in OS if rx.search(code)]
            window = " ".join(x.strip() for x in lines[i - 1:i + 3])
            if re.search(r"INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|BUILD", s, re.I):
                cls_ += [k for k in sql_classes(window) if re.search(k.split("-")[1][:4], s, re.I) or k == "sql-ddl"]
        else:
            if s.startswith("#") or i in skip:
                continue
            cls_ = []
            if PY_NATIVE.search(s):
                cls_.append("native-" + PY_NATIVE.search(s).group(1).lower())
            if re.search(r"INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|BUILD INDEX", s):
                window = " ".join(x.strip() for x in lines[i - 1:i + 3])
                verbs = sql_classes(window)
                first = sql_classes(s + " " + (lines[i] if i < len(lines) else ""))
                cls_ += [v for v in verbs if v in first]
        for k in dict.fromkeys(cls_):
            yield rel, i, k, s[:140]


def owners_at(entries, f, line, fallback):
    """Owners of the innermost inventoried entry whose [line, end] contains the line, else the file's owners."""
    best = None
    for e in entries.get(f, []):
        if e["line"] <= line <= (e.get("end") or e["line"]) and e.get("owners"):
            if best is None or (e["end"] - e["line"]) < (best["end"] - best["line"]):
                best = e
    return best["owners"] if best else fallback


def main() -> int:
    inv = json.loads(INV.read_text())
    files = {f["file"]: f["owners"] for f in inv["files"] if f.get("owners")}
    entries = defaultdict(list)
    for e in inv["entries"]:
        if e.get("owners") and e.get("end"):
            entries[e["file"]].append(e)
    per = defaultdict(lambda: defaultdict(list))
    for f, owners in files.items():
        p = REPO / f
        if p.suffix not in (".py", ".cls") or not p.exists():
            continue
        if not (f.startswith("iris_vector_graph/") or f.startswith("iris_src/") or f.startswith("api/")):
            continue
        for rel, line, k, txt in scan_file(p):
            for m in owners_at(entries, f, line, owners):
                per[m][k].append(f"{rel}:{line}")
    out = {m: {k: {"count": len(v), "sample": v[:6]} for k, v in sorted(d.items())} for m, d in sorted(per.items())}
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1))
    for m, d in out.items():
        print(m, {k: v["count"] for k, v in d.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
