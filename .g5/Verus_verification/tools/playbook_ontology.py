#!/usr/bin/env python3
"""Read the playbook arm's completion ontology (experiment/playbook-completion/ontology/NN-*.md) as statement rows.

    python3 .g5/Verus_verification/tools/playbook_ontology.py ID [ID ...]      # print the rows
    python3 .g5/Verus_verification/tools/playbook_ontology.py --grep WORD      # rows whose text contains WORD
    python3 .g5/Verus_verification/tools/playbook_ontology.py --stats          # rows per module and kind

Each statement is one Markdown table row `| ID | parent | kind | text | evidence | source | notes |` in a module's
"Statements" section. The imported tree is read in place and never written. Standard library only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ONT = REPO / "experiment/playbook-completion/ontology"
ROW = re.compile(r"^\| ([A-Z]{3}-[A-Za-z0-9.]+) \| ([^|]*) \| ([A-Z]) \| (.*)$")


def split_cells(rest: str) -> list[str]:
    # the text, evidence, source and notes cells; a cell may contain escaped pipes (\|)
    cells, cur, i = [], "", 0
    while i < len(rest):
        ch = rest[i]
        if ch == "\\" and i + 1 < len(rest) and rest[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        cells.append(cur.strip())
    return cells


def load() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(ONT.glob("[0-9][0-9]-*.md")):
        section = None
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if line.startswith("## "):
                section = line[3:].strip()
            m = ROW.match(line)
            if not m or section != "Statements":
                continue
            sid, parent, kind, rest = m.groups()
            cells = split_cells(rest)
            out.setdefault(sid, {
                "id": sid, "module": f.name, "line": n, "parent": parent.strip(), "kind": kind,
                "text": cells[0] if cells else "", "evidence": cells[1] if len(cells) > 1 else "",
                "source": cells[2] if len(cells) > 2 else "", "notes": cells[3] if len(cells) > 3 else "",
            })
    return out


def main(argv: list[str]) -> int:
    st = load()
    if len(argv) > 1 and argv[1] == "--stats":
        from collections import Counter
        c = Counter((s["module"], s["kind"]) for s in st.values())
        for (mod, kind), k in sorted(c.items()):
            print(f"{mod}\t{kind}\t{k}")
        print(f"total\t{len(st)}")
        return 0
    if len(argv) > 2 and argv[1] == "--grep":
        rx = re.compile(argv[2], re.I)
        rows = [s for s in st.values() if rx.search(s["text"]) or rx.search(s["notes"])]
    else:
        rows = [st[i] for i in argv[1:] if i in st]
        for i in argv[1:]:
            if i not in st:
                print(f"MISSING {i}")
    for s in rows:
        print(f"{s['id']} [{s['module']}:{s['line']} parent={s['parent']} kind={s['kind']}]\n  TEXT: {s['text']}\n"
              f"  EVIDENCE: {s['evidence']}\n  SOURCE: {s['source']}\n  NOTES: {s['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
