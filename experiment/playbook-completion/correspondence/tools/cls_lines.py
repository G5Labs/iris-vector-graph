#!/usr/bin/env python3
"""Methods and executable lines of the pin's ObjectScript classes (correspondence lane, playbook §3.5).

    python cls_lines.py [--json OUT] [CLASS ...]

A method is a member declared at column 0 (ClassMethod, Method, Trigger) whose body is the block between the next
line that is exactly "{" and the matching "}" at column 0. A body line is *executable* when it carries code: not
blank, not a comment (//, ;, #;), not pure block punctuation ("{", "}", "} Else {", "Try {", "} Catch ex {"), and not
a continuation line of a multi-line embedded SQL statement (&sql( ... ) spanning lines counts once, on its first
line; a cursor DECLARE generates no code and is not executable). This is the denominator of the line-coverage report; it is decided from the source text only, so a reviewer
can recompute it.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "iris_src" / "src"
DECL = re.compile(r"^(ClassMethod|Method|Trigger)\s+([%\w]+)")
PUNCT = re.compile(r"^\}?\s*(Else|Try|Catch(\s+\w+)?)?\s*\{?$", re.I)


def class_file(cls: str) -> Path:
    return SRC.joinpath(*cls.split(".")).with_suffix(".cls")


def methods(cls: str):
    lines = class_file(cls).read_text().split("\n")
    out = []
    i = 0
    while i < len(lines):
        m = DECL.match(lines[i])
        if not m:
            i += 1
            continue
        kind, name = m.groups()
        j = i + 1
        while j < len(lines) and lines[j].strip() != "{":
            j += 1
        k = j + 1
        while k < len(lines) and lines[k] != "}":
            k += 1
        body = list(range(j + 2, k + 1))  # 1-based numbers of the body lines (exclusive of the braces)
        out.append({"class": cls, "method": name, "kind": kind, "decl": i + 1, "open": j + 1, "close": k + 1,
                    "executable": executable(lines, body)})
        i = k + 1
    return out


def executable(lines, body):
    ex = []
    in_sql = 0
    for n in body:
        t = lines[n - 1].strip()
        if in_sql > 0:
            in_sql += t.count("(") - t.count(")")
            continue
        if not t or t.startswith(("//", ";", "#;", "///")):
            continue
        if PUNCT.match(t):
            continue
        if t.startswith("&sql(DECLARE"):  # a cursor declaration generates no code; its continuation lines are skipped
            depth = t.count("(") - t.count(")")
            in_sql = depth if depth > 0 else 0
            continue
        ex.append(n)
        if "&sql(" in t:
            depth = t[t.index("&sql("):].count("(") - t[t.index("&sql("):].count(")")
            if depth > 0:
                in_sql = depth
    return ex


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        args = [a for a in args if a != str(out)]
    classes = args or ["Graph.KG.Ledger", "Graph.KG.LedgerApply", "Graph.KG.LedgerRedact", "Graph.KG.LedgerGenesis",
                       "Graph.KG.LedgerRevision", "Graph.KG.LedgerStats", "Graph.KG.Eraser", "Graph.KG.Txn"]
    res = {c: methods(c) for c in classes}
    if out:
        out.write_text(json.dumps(res, indent=1))
    for c, ms in res.items():
        print(c, len(ms), "methods", sum(len(m["executable"]) for m in ms), "executable lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
