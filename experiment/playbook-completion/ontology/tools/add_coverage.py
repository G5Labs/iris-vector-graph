#!/usr/bin/env python3
"""Apply the coverage additions (ontology-2 lane, gate 3.1-coverage and 3.1-cells) to the ontology modules.

    python3 experiment/playbook-completion/ontology/tools/add_coverage.py               # apply the recorded spec
    python3 experiment/playbook-completion/ontology/tools/add_coverage.py --spec F --ontology DIR   # a scratch copy

The spec is `coverage_additions` in ontology/evidence-additions.json (the file independent_recheck.py reads):

    {"statements": [{"file": "12-erasure.md", "after": "<id of an existing row>", "row": [Id, Parent, Kind,
                     Statement, Evidence, Source, Notes]}, ...],
     "cells": [{"file": "07-text-search.md", "entity_line": "Entity X: states a, b; commands c, d",
                "rows": [[Entity, State, Command, Outcome, Statements, Decision], ...]}, ...],
     "scope_addenda": [{"file": "03-writes.md", "line": "Also owns (...): ..."}, ...]}

A scope addendum is one line placed at the end of the header's Scope paragraph (before its first blank line): an
owner assignment the coverage reconciliation made for code no Scope line named.

A statement row goes immediately after the row `after` names (after earlier spec rows anchored to the same row, in
spec order). An entity line goes after the module's last "Entity ..." line; cell rows go at the end of the Cells
table. Idempotent: a row whose id is already present must equal the spec row (else it stops); an entity line or a
cell row already present is skipped. It runs after repair.py and add_evidence.py and changes nothing else.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ONT = Path(__file__).resolve().parent.parent


def esc(c: str) -> str:
    return c.replace("|", "\\|")


def fmt(row) -> str:
    return "|" + "|".join(f" {esc(c)} " if c else " " for c in row) + "|"


def split_row(line: str):
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def apply(spec: dict, ont: Path) -> int:
    by_file = {}
    for s in spec.get("statements", []):
        by_file.setdefault(s["file"], {"st": [], "cells": []})["st"].append(s)
    for c in spec.get("cells", []):
        by_file.setdefault(c["file"], {"st": [], "cells": []})["cells"].append(c)
    for c in spec.get("scope_addenda", []):
        by_file.setdefault(c["file"], {"st": [], "cells": []}).setdefault("scope", []).append(c["line"])
    changed = 0
    for name, parts in sorted(by_file.items()):
        path = ont / name
        lines = path.read_text(encoding="utf-8").split("\n")
        ids = {}
        for k, l in enumerate(lines):
            if l.startswith("| ") and not l.startswith("|---"):
                r = split_row(l)
                if r and re.match(r"^[A-Z]{2,4}-", r[0]) and len(r) == 7:
                    ids[r[0]] = k
        for line in parts.get("scope", []):
            if line in lines:
                continue
            k = next(i for i, l in enumerate(lines) if l.startswith("Scope:"))
            while k + 1 < len(lines) and lines[k + 1].strip():
                k += 1
            lines.insert(k + 1, line)
            ids = {k2: (v + 1 if v > k else v) for k2, v in ids.items()}
            changed += 1
        last_after = {}
        for s in parts["st"]:
            rid = s["row"][0]
            if len(s["row"]) != 7:
                raise SystemExit(f"{name} {rid}: a statement row has 7 cells")
            if rid in ids:
                have = split_row(lines[ids[rid]])
                if have != [c.strip() for c in s["row"]]:
                    raise SystemExit(f"{name} {rid}: present with different content")
                last_after[s["after"]] = ids[rid]
                continue
            anchor = s["after"]
            if anchor not in ids:
                raise SystemExit(f"{name} {rid}: anchor {anchor} not found")
            pos = last_after.get(anchor, ids[anchor]) + 1
            lines.insert(pos, fmt(s["row"]))
            ids = {k2: (v + 1 if v >= pos else v) for k2, v in ids.items()}
            last_after = {k2: (v + 1 if v >= pos else v) for k2, v in last_after.items()}
            ids[rid] = pos
            last_after[anchor] = pos
            changed += 1
        if parts["cells"]:
            try:
                cstart = next(k for k, l in enumerate(lines) if l.strip() == "## Cells")
            except StopIteration:
                raise SystemExit(f"{name}: no Cells section")
            for c in parts["cells"]:
                if c.get("entity_line") and c["entity_line"] not in lines[cstart:]:
                    ent = [k for k in range(cstart, len(lines)) if lines[k].startswith("Entity ")]
                    at = (ent[-1] + 1) if ent else cstart + 2
                    lines.insert(at, c["entity_line"])
                    changed += 1
                end = cstart
                while end < len(lines) and not lines[end].startswith("|"):
                    end += 1
                while end < len(lines) and lines[end].startswith("|"):
                    end += 1
                for row in c.get("rows", []):
                    text = fmt(row)
                    if text in lines[cstart:]:
                        continue
                    lines.insert(end, text)
                    end += 1
                    changed += 1
        path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, help="a JSON file holding the spec (default: evidence-additions.json)")
    ap.add_argument("--ontology", type=Path, default=ONT)
    a = ap.parse_args()
    if a.spec:
        spec = json.loads(a.spec.read_text(encoding="utf-8"))
        spec = spec.get("coverage_additions", spec)
    else:
        spec = json.loads((ONT / "evidence-additions.json").read_text(encoding="utf-8")).get("coverage_additions", {})
    n = apply(spec, a.ontology)
    print(f"add_coverage: {n} line(s) added to {a.ontology}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
