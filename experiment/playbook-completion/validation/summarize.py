#!/usr/bin/env python3
"""Counts and non-pass cases of one validation run: $RUN_DIR/validation/<id>/{run.log,junit.xml,meta.json}.

    python summarize.py <id> [--list]

Counts come from pytest's own final summary line (passed/failed/errors/skipped/xfailed/xpassed/deselected) and are
cross-checked against the JUnit XML. --list prints every failure and error (node id and first message line), and the
skip reasons grouped by count.
"""
import collections
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KEYS = ("passed", "failed", "errors", "error", "skipped", "xfailed", "xpassed", "deselected", "warnings")


def final_line(log: str):
    lines = [ln for ln in log.splitlines() if re.match(r"^=+ .* in [0-9.]+s", ln)]
    return lines[-1] if lines else ""


def counts(line: str) -> dict:
    out = {}
    for n, k in re.findall(r"(\d+) (\w+)", line):
        if k in KEYS:
            out["errors" if k == "error" else k] = int(n)
    m = re.search(r"in ([0-9.]+)s", line)
    if m:
        out["pytest_seconds"] = float(m.group(1))
    return out


def junit(path: Path):
    if not path.exists():
        return None, []
    root = ET.parse(path).getroot()
    agg = collections.Counter()
    cases = []
    for ts in root.iter("testsuite"):
        for k in ("tests", "failures", "errors", "skipped"):
            agg[k] += int(ts.get(k, 0))
        for tc in ts.findall("testcase"):
            for kind in ("failure", "error", "skipped"):
                el = tc.find(kind)
                if el is not None:
                    full = ((el.get("message") or "") + "\n" + (el.text or "")).strip()
                    msg = full.splitlines()
                    cases.append((kind, f"{tc.get('classname')}::{tc.get('name')}", msg[0][:220] if msg else "", full[:4000]))
    return dict(agg), cases


def main():
    rid = sys.argv[1]
    d = Path(os.environ["RUN_DIR"]) / "validation" / rid
    log = (d / "run.log").read_text(errors="replace")
    line = final_line(log)
    c = counts(line)
    j, cases = junit(d / "junit.xml")
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    wall = re.search(r"# exit=(\d+) wall_seconds=(\d+)", log)
    res = {"id": rid, "summary_line": line.strip("= "), "counts": c, "junit": j,
           "exit": int(wall.group(1)) if wall else None, "wall_seconds": int(wall.group(2)) if wall else None,
           "namespaces_unchanged": meta.get("namespaces_unchanged"), "deploy_calls": len(meta.get("deploy_calls", [])),
           "guard_hits": meta.get("guard_hits")}
    print(json.dumps(res, indent=1))
    if "--list" in sys.argv:
        for kind in ("failure", "error"):
            for k, node, msg, _ in cases:
                if k == kind:
                    print(f"{kind.upper():8} {node} :: {msg}")
        skips = collections.Counter(msg for k, _, msg, _ in cases if k == "skipped")
        for msg, n in skips.most_common():
            print(f"SKIP x{n:5} {msg}")


if __name__ == "__main__":
    main()
