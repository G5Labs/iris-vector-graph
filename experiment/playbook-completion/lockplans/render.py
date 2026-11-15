#!/usr/bin/env python3
"""Render the lockplans lane's per-module obligation files into LOCKPLANS.md and MATRIX-INPUT.json, and check refs.

    python experiment/playbook-completion/lockplans/render.py [--check]

Inputs: lockplans/NN.json for the modules whose 3.5-lockplans cell was open (01, 05, 06, 08, 10, 16, 17).
Checks (exit 1 on any problem): every evidence ref of kind live/run/probe/control names a registered run
(evidence/runs/<id>.json); every mc ref names a check id in a models RESULTS.json (lockplans/models, models/*,
semantics models); every finding id exists in findings/audit/*.json; every obligation has a verdict from
{holds, violated, not-needed, open}; a cell's as_built_findings are reproduced findings.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PC = HERE.parent
MODULES = ["01", "05", "06", "08", "10", "16", "17"]
VERDICTS = {"holds", "violated", "not-needed", "open"}
REPRODUCED = {"reproduced-live", "reproduced-model", "reproduced-test", "confirmed-source", "product-defect"}


def mc_ids() -> set:
    ids = set()
    for f in [HERE / "models" / "RESULTS.json", *map(Path, glob.glob(str(PC / "models" / "*" / "RESULTS.json")))]:
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        for c in d.get("checks", d if isinstance(d, list) else []):
            if isinstance(c, dict) and "id" in c:
                ids.add(c["id"])
    return ids


def findings() -> dict:
    out = {}
    for f in glob.glob(str(PC / "findings" / "audit" / "*.json")):
        d = json.loads(Path(f).read_text())
        for r in (d if isinstance(d, list) else d.get("findings", []) + d.get("new_findings", [])):
            if isinstance(r, dict) and r.get("id"):
                out.setdefault(r["id"], r.get("disposition"))
    return out


def main() -> int:
    problems = []
    runs = {p.stem for p in (PC / "evidence" / "runs").glob("*.json")}
    mcs = mc_ids()
    fnd = findings()
    mods = []
    for nn in MODULES:
        p = HERE / f"{nn}.json"
        if not p.exists():
            problems.append(f"{nn}: lockplans/{nn}.json missing")
            continue
        m = json.loads(p.read_text())
        mods.append(m)
        for ob in m["obligations"]:
            if ob.get("verdict") not in VERDICTS:
                problems.append(f"{ob['id']}: verdict {ob.get('verdict')!r}")
            for ev in ob.get("evidence", []):
                k, ref = ev["kind"], ev["ref"]
                if k in ("live", "run", "probe", "control") and ref not in runs:
                    problems.append(f"{ob['id']}: run {ref} not registered")
                if k == "mc" and ref not in mcs:
                    problems.append(f"{ob['id']}: model check {ref} not found")
            for f in ob.get("findings", []):
                if f not in fnd:
                    problems.append(f"{ob['id']}: finding {f} not found")
        cell = m["cell"]
        for f in cell.get("as_built_findings", []):
            if fnd.get(f) not in REPRODUCED:
                problems.append(f"cell {nn}: as_built_finding {f} has disposition {fnd.get(f)}")
        for e in cell.get("evidence", []):
            if e.startswith("run:") and e[4:] not in runs:
                problems.append(f"cell {nn}: {e} not registered")
    if "--check" not in sys.argv:
        render_md(mods)
        render_input(mods)
    for pr in problems:
        print("PROBLEM", pr)
    print(f"{len(mods)} modules, {sum(len(m['obligations']) for m in mods)} obligations, {len(problems)} problems")
    return 1 if problems else 0


def esc(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def evs(ob) -> str:
    return "; ".join(f"{e['kind']}:{e['ref']}" for e in ob.get("evidence", [])) or "-"


def render_md(mods) -> None:
    head = (HERE / "LOCKPLANS.head.md").read_text() if (HERE / "LOCKPLANS.head.md").exists() else ""
    out = [head.rstrip() + "\n"] if head else []
    out.append("## Summary\n\n| Module | Obligations | holds | violated | not needed | open | Proposed cell | Product obligation |\n"
               "|---|---:|---:|---:|---:|---:|---|---|\n")
    for m in mods:
        c = {v: sum(1 for o in m["obligations"] if o["verdict"] == v) for v in VERDICTS}
        out.append(f"| {m['module']} {m['name']} | {len(m['obligations'])} | {c['holds']} | {c['violated']} | "
                   f"{c['not-needed']} | {c['open']} | {m['cell']['status']} | {m['cell'].get('product_obligation', '')} |\n")
    for m in mods:
        out.append(f"\n## Module {m['module']} ({m['name']})\n\n")
        if m.get("summary"):
            out.append(m["summary"].rstrip() + "\n\n")
        out.append("Lock inventory (as built at the pin):\n\n| Site | Lock / transaction | Reached by |\n|---|---|---|\n")
        for i in m["inventory"]:
            out.append(f"| `{esc(i['site'])}` | {esc(i['what'])} | {esc(i.get('reached_by', ''))} |\n")
        out.append("\n| Id | Entry points | Conflict to exclude (source) | Plan as built | Verdict | Evidence |\n"
                   "|---|---|---|---|---|---|\n")
        for o in m["obligations"]:
            fx = f" Findings: {', '.join(o['findings'])}." if o.get("findings") else ""
            out.append(f"| {o['id']} | {esc(o['entry_points'])} | {esc(o['conflict'])} ({esc(o['conflict_source'])}) | "
                       f"{esc(o['plan'])} | **{o['verdict']}**{esc(fx)} {esc(o.get('notes', ''))} | {esc(evs(o))} |\n")
        c = m["cell"]
        out.append(f"\nProposed cell 3.5-lockplans/{m['module']}: **{c['status']}**, level {c['level']}, "
                   f"product obligation {c.get('product_obligation', 'unknown')}. Remaining: {c.get('remaining') or 'none'}\n")
    (HERE / "LOCKPLANS.md").write_text("".join(out))


def render_input(mods) -> None:
    cells = []
    for m in mods:
        c = m["cell"]
        cells.append({"gate": "3.5-lockplans", "module": m["module"], "status": c["status"],
                      "evidence": c.get("evidence", []), "evidence_grade": c.get("evidence_grade", "live"),
                      "level": c.get("level", "product"), "product_obligation": c.get("product_obligation", "unknown"),
                      "product_basis": c.get("product_basis", ""), "as_built_findings": c.get("as_built_findings", []),
                      "reason": c.get("reason", ""), "remaining": c.get("remaining", "")})
    (HERE / "MATRIX-INPUT.json").write_text(json.dumps(
        {"lane": "lockplans (gate 3.5-lockplans for modules 01, 05, 06, 08, 10, 16, 17)",
         "source": "experiment/playbook-completion/lockplans/NN.json rendered by lockplans/render.py; obligations, "
                   "verdicts and evidence per module in lockplans/LOCKPLANS.md",
         "cells": cells}, indent=1) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
