#!/usr/bin/env python3
"""Merge the static map (actions.py) with the live results into correspondence/correspondence.json.

    python build.py

Inputs ($RUN_DIR/correspondence): probe0/*.int (INT text), live/traces/<scenario>/{trace.json,monitor.json},
live/checks.json (check_all.py), live/coverage.json (coverage.py), live/lockplan/lockplan.json, live/capacity/capacity.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from actions import ACTIONS  # noqa: E402
import cls_lines  # noqa: E402

RUN = Path(os.environ["RUN_DIR"]) / "correspondence"
OUT = Path(__file__).resolve().parents[1] / "correspondence.json"

ERRPAT = re.compile(r'Err\(|ErrLimit|ThrowStatus|ThrowOnError|Throw |TROLLBACK|Return "[a-z_ ]*(failed|required|not|must|unknown|was|does|refuses|exists|reserved)|'
                    r'Return tReason|Return tErr|Return tResult|\$\$\$ISERR|SqlErr|While \$TLevel', re.I)


def kind(text: str) -> str:
    return "error/refusal path" if ERRPAT.search(text) else "branch not taken"


def load(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def actions_md(actions) -> str:
    rows = []
    for a in actions:
        hs = [h for h in a["handler_coverage"] if "executable" in h]
        ex, hit = sum(h["executable"] for h in hs), sum(h["exercised"] for h in hs)
        locks = "; ".join(f"{l['name']}" + (f" {l.get('mode', '')}, {l.get('timeout', '')}; taken {l['taken']}; released {l['released']}"
                                             if l.get("taken") else f": {l.get('note', '')}") for l in a["locks"])
        rows.append(f"### {a['id']}\n\n"
                    f"- **Model**: {a['model']}\n"
                    f"- **Handlers**: {'; '.join(a['handlers'])}\n"
                    f"- **Reads**: globals {', '.join(a['reads']['globals']) or '-'}; tables {', '.join(a['reads']['tables']) or '-'}\n"
                    f"- **Writes** ({a['writes'].get('journal', '')}): globals {', '.join(a['writes']['globals']) or '-'}; "
                    f"tables {', '.join(a['writes']['tables']) or '-'}\n"
                    f"- **Transaction**: {a['txn']}\n"
                    f"- **Locks**: {locks}\n"
                    f"- **Status / decoder**: {a['status']}\n"
                    f"- **α**: {a['alpha']}\n"
                    f"- **Grade**: **{a['grade']}**{(' — ' + a['grade_note']) if a['grade_note'] else ''}"
                    f"{(' (' + ', '.join('run:' + e for e in a['grade_evidence']) + ')') if a['grade_evidence'] else ''}\n"
                    f"- **Lines** (ObjectScript handler methods; Python handler lines in §3): {hit}/{ex} executable lines exercised by the checked traces; "
                    f"unchecked lines: {a['unchecked_lines']} (listed per method in correspondence.json)\n")
    return "\n".join(rows)


def main() -> int:
    cov = load(RUN / "live" / "coverage.json")
    checks = load(RUN / "live" / "checks.json")
    lock = load(RUN / "live" / "lockplan" / "lockplan.json")
    cap = load(RUN / "live" / "capacity" / "capacity.json")
    src = {}
    per_method = {}
    if cov:
        for cls, v in cov["classes"].items():
            for m in v["methods"]:
                per_method[(cls, m["method"])] = m
    out = {"pin": "3eaa79cf77d3e0a879b2cced634cf2729d81499e", "namespace": "AUDITC",
           "int_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16] for f in sorted((RUN / "probe0").glob("*.int"))},
           "scenarios": cov["runs"] if cov else [], "actions": []}
    for a in ACTIONS:
        handlers = []
        for cls, methods in a["methods"].items():
            if cls not in src:
                src[cls] = cls_lines.class_file(cls).read_text().split("\n")
            for meth in methods:
                m = per_method.get((cls, meth))
                if m is None:
                    handlers.append({"class": cls, "method": meth, "coverage": "no data"})
                    continue
                un = [{"line": n, "kind": kind(src[cls][n - 1]), "text": src[cls][n - 1].strip()[:140]} for n in m["unexercised"]]
                handlers.append({"class": cls, "method": meth, "lines": m["lines"], "executable": m["executable"],
                                 "exercised": m["exercised"], "unchecked": un, "by_scenario": m["by_run"]})
        a2 = dict(a)
        a2["handler_coverage"] = handlers
        a2["unchecked_lines"] = sum(len(h.get("unchecked", [])) for h in handlers)
        out["actions"].append(a2)
    pyc = load(RUN / "live" / "pycoverage.json")
    if pyc:
        out["python_coverage"] = pyc
    for name, f in (("frame_shapes", RUN / "checks" / "frame-shapes.json"), ("closure", RUN / "checks" / "closure.json"),
                    ("int_alignment", RUN / "checks" / "int-alignment.json")):
        v = load(f)
        if v is not None:
            out[name] = v
    lsum = [load(RUN / "live" / d / "summary.json") for d in ("lockplan", "lockplan-2", "lockplan-3")]
    out["lockplan_summary"] = [x for part in lsum if part for x in part]
    out["findings"] = load(OUT.parent / "findings.json")
    out["registered_runs"] = sorted(p.stem for p in (OUT.parents[1] / "evidence" / "runs").glob("corr-*.json"))
    if checks:
        out["checks"] = checks
    if lock:
        out["lockplan"] = lock
    if cap:
        out["capacity"] = cap
    grades = load(Path(__file__).resolve().parent / "grades.json") or {}
    for a in out["actions"]:
        a["grade"] = grades.get(a["id"], {}).get("grade", "source-inspected only")
        a["grade_evidence"] = grades.get(a["id"], {}).get("evidence", [])
        a["grade_note"] = grades.get(a["id"], {}).get("note", "")
    OUT.write_text(json.dumps(out, indent=1, default=str))
    md = OUT.parent / "CORRESPONDENCE.md"
    if md.exists():
        text = md.read_text()
        b0, b1 = "<!-- BEGIN ACTIONS (generated by tools/build.py) -->", "<!-- END ACTIONS -->"
        if b0 in text and b1 in text:
            text = text[:text.index(b0) + len(b0)] + "\n" + actions_md(out["actions"]) + "\n" + text[text.index(b1):]
            md.write_text(text)
    print("wrote", OUT, "actions", len(out["actions"]))
    for a in out["actions"]:
        hs = [h for h in a["handler_coverage"] if "executable" in h]
        print(f"{a['id']:24s} executable {sum(h['executable'] for h in hs):4d} exercised {sum(h['exercised'] for h in hs):4d} "
              f"unchecked {a['unchecked_lines']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
