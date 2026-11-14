#!/usr/bin/env python3
"""Mechanical extraction of the stated refusals (kind X statements) of the ontology (playbook gate 5c-refusals).

    python extract_x.py [--modules 01,04,...] [--out refusals/x-statements.json]
    python extract_x.py --self-test

Two independent readers must agree on the list:
  A. the ontology checker's own parser (ontology/tools/ontology_check.py parse_module, Statements table, Kind 'X');
  B. a raw line scan of every '| <Id> | <Parent> | X |' row of each module file (no table parsing).
A disagreement (an X row one reader sees and the other does not) is an error: a stated refusal must not be lost by
the parser. Each statement's cited `inspected:` references are listed with their line ranges, and every range is
checked to exist at the pin (file present, range inside the file) - the audit's implementing-code citations start
from these and are then read by hand.

Self-test (seeded fixture in a temp dir): a seeded X statement (with an escaped pipe in its text) must appear in the
audit list from both readers; a seeded B statement must not; a seeded X row the table parser cannot see (a
malformed row outside the Statements table) must be reported as a disagreement; an inspected range past the end of
its file must be reported.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
COMPLETION = LANE.parent
REPO = COMPLETION.parents[1]
ONTOLOGY = COMPLETION / "ontology"
sys.path.insert(0, str(ONTOLOGY / "tools"))
import ontology_check as oc  # noqa: E402

TARGET = ["01", "04", "06", "10", "11", "15", "16", "17", "18"]
RAW_ROW = re.compile(r"^\|\s*([A-Z]{3}-[A-Za-z0-9.]+)\s*\|\s*([^|]*?)\s*\|\s*X\s*\|")
INSPECTED = re.compile(r"inspected:([^\s;]+?):(\d+)(?:-(\d+))?(?=[;\s]|$)")


def reader_a(files: List[Path]) -> Dict[str, dict]:
    errs: List[str] = []
    out: Dict[str, dict] = {}
    for f in files:
        m = oc.parse_module(f, errs, 0)
        if m is None:
            continue
        for s in m.statements:
            if s.kind == "X":
                out[s.id] = {"id": s.id, "parent": s.parent, "module_code": m.code, "file": f.name,
                             "module": f.name[:2], "text": s.text, "evidence": s.evidence, "source": s.source,
                             "notes": s.notes}
    if errs:
        out["__errors__"] = errs  # type: ignore[assignment]
    return out


def reader_b(files: List[Path]) -> Dict[str, Tuple[str, int]]:
    out: Dict[str, Tuple[str, int]] = {}
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            m = RAW_ROW.match(line)
            if m:
                out[m.group(1)] = (f.name, n)
    return out


def inspected_refs(evidence: str, repo: Path) -> List[dict]:
    refs = []
    for m in INSPECTED.finditer(evidence):
        path, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        p = repo / path
        n = len(p.read_text(encoding="utf-8", errors="replace").splitlines()) if p.is_file() else None
        refs.append({"ref": f"{path}:{a}-{b}" if b != a else f"{path}:{a}", "path": path, "start": a, "end": b,
                     "exists": p.is_file(), "in_range": bool(n is not None and 1 <= a <= b <= n),
                     "file_lines": n})
    return refs


def extract(ontology: Path, modules: List[str], repo: Path) -> dict:
    files = sorted(f for f in ontology.glob("[0-9][0-9]-*.md") if f.name[:2] in modules)
    a = reader_a(files)
    errors = list(a.pop("__errors__", []))  # type: ignore[arg-type]
    b = reader_b(files)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    for i in only_a:
        errors.append(f"[disagree] {i} seen by the table parser only")
    for i in only_b:
        errors.append(f"[disagree] {i} seen by the raw scan only ({b[i][0]}:{b[i][1]})")
    stmts = []
    for sid in sorted(a, key=lambda k: (a[k]["module"], list(a).index(k))):
        s = dict(a[sid])
        s["line"] = b.get(sid, (None, None))[1]
        s["inspected"] = inspected_refs(s["evidence"], repo)
        for r in s["inspected"]:
            if not r["in_range"]:
                errors.append(f"[range] {sid}: inspected {r['ref']} not inside the file at the pin "
                              f"(lines {r['file_lines']})")
        stmts.append(s)
    per = {}
    for s in stmts:
        per.setdefault(s["module"], 0)
        per[s["module"]] += 1
    return {"modules": modules, "count": len(stmts), "per_module": per, "errors": errors, "statements": stmts}


def self_test() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        src = ONTOLOGY / "11-ledger.md"
        lines = src.read_text(encoding="utf-8").splitlines()
        # seed after the last statement row of the Statements table
        start = next(i for i, l in enumerate(lines) if l.strip() == "## Statements")
        end = start + 3
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1
        seeded_x = ("| LED-X99 | LED-0 | X | A seeded refusal with a \\| pipe is refused. | "
                    "inspected:iris_src/src/Graph/KG/Ledger.cls:1-2 | x | seeded |")
        seeded_b = "| LED-B99 | LED-0 | B | A seeded behaviour. | inspected:iris_src/src/Graph/KG/Ledger.cls:1 | x | seeded |"
        seeded_bad_range = ("| LED-X98 | LED-0 | X | A seeded refusal citing lines past the end. | "
                            "inspected:iris_src/src/Graph/KG/Ledger.cls:99998-99999 | x | seeded |")
        lines[end:end] = [seeded_x, seeded_b, seeded_bad_range]
        # an X row outside the Statements table: the raw scan sees it, the table parser does not
        lines.append("")
        lines.append("| LED-X97 | LED-0 | X | A stray refusal row outside the table. | | | |")
        (t / "11-ledger.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = extract(t, ["11"], REPO)
        ids = [s["id"] for s in r["statements"]]
        checks = {
            "seeded X listed": "LED-X99" in ids,
            "seeded X text keeps the escaped pipe": any(s["id"] == "LED-X99" and "| pipe" in s["text"]
                                                        for s in r["statements"]),
            "seeded B not listed": "LED-B99" not in ids,
            "stray X reported as disagreement": any("LED-X97" in e and "[disagree]" in e for e in r["errors"]),
            "range past end reported": any("LED-X98" in e and "[range]" in e for e in r["errors"]),
            "real X count unchanged (32 + 2 seeded in table)": len(ids) == 34,
        }
        for k, v in checks.items():
            print(("PASS " if v else "FAIL ") + k)
            ok &= v
    real = extract(ONTOLOGY, TARGET, REPO)
    c = real["count"] == sum(real["per_module"].values()) and not real["errors"]
    print(("PASS " if c else "FAIL ") + f"real extraction clean: {real['count']} X statements, errors {real['errors'][:3]}")
    ok &= c
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default=",".join(TARGET))
    ap.add_argument("--out", default=str(LANE / "x-statements.json"))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    r = extract(ONTOLOGY, a.modules.split(","), REPO)
    Path(a.out).write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    print(f"{r['count']} X statements: {r['per_module']}; errors {len(r['errors'])}")
    for e in r["errors"]:
        print("  " + e)
    return 0 if not r["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
