#!/usr/bin/env python3
"""Check writesets/DISCHARGES.json against the writer census and the audit's registries.

    python experiment/playbook-completion/writesets/tools/check_discharges.py            # check the file
    python experiment/playbook-completion/writesets/tools/check_discharges.py --self-test # seeded mutations

Checks (every one is exercised by a seeded mutation in --self-test):
  C1  every census obligation id (matrix-input/writer-census-obligations.json extra_cells) has exactly one entry
      (duplicate keys in the file are caught at parse time), and no other WS-* id is present;
  C2  writer, invariant, kind and module of each entry equal the census cell's;
  C3  discharge is lemma | guard | finding | open, with a grade allowed for it (lemma: proved, mc, trace, live,
      inspected; guard: live, inspected; finding: live, inspected, model; open: open) and a non-empty reason;
  C4  a finding discharge cites at least one finding, and every cited finding exists in findings/audit/*.json with
      disposition reproduced-* or intent-undecided;
  C5  every "run:<id>" in evidence exists as evidence/runs/<id>.json;
  C6  every "path:N[-M]" resolves to existing lines: product paths in the pin's tree (git show <pin>:path),
      experiment/ paths in the working tree; a bare path must be an existing file;
  C7  one module:NN entry for every module whose 3.3a-writesets cell is open in matrix/obligations.json, and no
      other module:NN key;
  C8  every non-open discharge cites at least one evidence item;
  C9  a census discharge graded `live` cites at least one run that exercised this (invariant, writer) pair
      (writesets/RUN-PAIRS.json, the machine-readable map of what each lane run exercised);
  C10 every failed run a lemma or guard discharge cites is attributed in its failed_runs_other_pairs, and the map
      shows that run failing only on other pairs (a run that failed on this very pair makes the cell fail);
  C11 failed_runs_other_pairs lists only cited runs whose registered result is fail, each with a reason;
  C12 every run in RUN-PAIRS.json and every context_runs id is registered (review R4-02).
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

PC = Path(__file__).resolve().parents[2]
REPO = PC.parents[1]
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
DISCHARGES = PC / "writesets" / "DISCHARGES.json"
RUNPAIRS = PC / "writesets" / "RUN-PAIRS.json"
CENSUS = PC / "matrix-input" / "writer-census-obligations.json"
OBLIGATIONS = PC / "matrix" / "obligations.json"
GRADES = {"lemma": {"proved", "mc", "trace", "live", "inspected"}, "guard": {"live", "inspected"},
          "finding": {"live", "inspected", "model"}, "open": {"open"}}
REF = re.compile(r"^(?P<path>[^:\s]+):(?P<a>\d+)(?:-(?P<b>\d+))?$")


class Dup(Exception):
    pass


def _no_dups(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise Dup(k)
        seen[k] = v
    return seen


def load_text(text: str):
    return json.loads(text, object_pairs_hook=_no_dups)


def findings_index() -> dict:
    out = {}
    for f in sorted((PC / "findings" / "audit").glob("*.json")):
        d = json.loads(f.read_text())
        items = d if isinstance(d, list) else d.get("findings", d)
        if isinstance(items, dict):
            items = list(items.values())
        for x in items:
            if isinstance(x, dict) and x.get("id"):
                out.setdefault(x["id"], set()).add(str(x.get("disposition", "")))
    return out


_LINES: dict = {}


def line_count(path: str):
    if path in _LINES:
        return _LINES[path]
    if path.startswith("experiment/"):
        p = REPO / path
        n = len(p.read_text(errors="replace").split("\n")) if p.is_file() else None
    else:
        r = subprocess.run(["git", "show", f"{PIN}:{path}"], cwd=REPO, capture_output=True)
        n = len(r.stdout.decode(errors="replace").split("\n")) if r.returncode == 0 else None
    _LINES[path] = n
    return n


def open_module_cells() -> set:
    d = json.loads(OBLIGATIONS.read_text())
    # orchestrator integration (steer 7): a module cell this lane decided (source matrix-input/writesets.json) stays in
    # scope after the matrix applies the decision, so integrating the lane's own proposal does not break C0/C7
    return {c["module"] for c in d["cells"] if c.get("gate") == "3.3a-writesets" and "obligation_id" not in c
            and (c.get("status") == "open" or c.get("source") == "matrix-input/writesets.json")}


def check(data: dict, census_cells: list, findex: dict, runs: dict, open_modules: set, pairs: dict) -> list:
    errs = []
    for rid in sorted(pairs):
        if rid not in runs:
            errs.append(f"C12 RUN-PAIRS run {rid} not registered")
    want = {c["obligation_id"]: c for c in census_cells}
    have = {k for k in data if k.startswith("WS-")}
    for k in sorted(set(want) - have):
        errs.append(f"C1 missing discharge for {k}")
    for k in sorted(have - set(want)):
        errs.append(f"C1 discharge for unknown obligation {k}")
    mods = {k[len("module:"):] for k in data if k.startswith("module:")}
    for m in sorted(open_modules - mods):
        errs.append(f"C7 no entry for open module cell module:{m}")
    for m in sorted(mods - open_modules):
        errs.append(f"C7 module:{m} has no open 3.3a-writesets cell")
    for k in sorted(set(data) - have - {f"module:{m}" for m in mods} - {"_doc"}):
        errs.append(f"C1 unexpected key {k}")
    for k, e in sorted(data.items()):
        if k == "_doc":
            continue
        if not isinstance(e, dict):
            errs.append(f"C3 {k}: entry is not an object")
            continue
        if k in want:
            c = want[k]
            for f in ("writer", "invariant", "kind", "module"):
                if e.get(f) != c.get(f):
                    errs.append(f"C2 {k}: {f} {e.get(f)!r} != census {c.get(f)!r}")
        kind, grade = e.get("discharge"), e.get("grade")
        if kind not in GRADES:
            errs.append(f"C3 {k}: discharge {kind!r}")
        elif grade not in GRADES[kind]:
            errs.append(f"C3 {k}: grade {grade!r} not allowed for {kind}")
        if not str(e.get("reason", "")).strip():
            errs.append(f"C3 {k}: empty reason")
        fs = e.get("findings", [])
        if kind == "finding" and not fs:
            errs.append(f"C4 {k}: finding discharge cites no finding")
        for fid in fs:
            disp = findex.get(fid)
            if disp is None:
                errs.append(f"C4 {k}: finding {fid} not in findings/audit")
            elif not any(d.startswith("reproduced-") or d == "intent-undecided" for d in disp):
                errs.append(f"C4 {k}: finding {fid} disposition {sorted(disp)} is not reproduced-* or intent-undecided")
        ev = e.get("evidence", [])
        if kind != "open" and not ev:
            errs.append(f"C8 {k}: no evidence")
        for rid in e.get("context_runs", []):
            if rid not in runs:
                errs.append(f"C12 {k}: context run {rid} not registered")
        if k.startswith("WS-"):
            pair = (e.get("invariant"), e.get("writer"))
            cited = [x[4:] for x in ev if x.startswith("run:")]

            def outcomes(rid):
                return [x["outcome"] for x in pairs.get(rid, {}).get("exercised", [])
                        if (x["invariant"], x["writer"]) == pair]
            if grade == "live" and not any(outcomes(r) for r in cited):
                errs.append(f"C9 {k}: graded live but no cited run exercised {pair[0]} x {str(pair[1]).split('::')[-1]}")
            frop = e.get("failed_runs_other_pairs", [])
            why = e.get("failed_runs_other_pairs_reason", {})
            for rid in frop:
                if rid not in cited:
                    errs.append(f"C11 {k}: failed_runs_other_pairs names {rid}, which it does not cite")
                elif runs.get(rid) != "fail":
                    errs.append(f"C11 {k}: failed_runs_other_pairs names {rid}, whose result is {runs.get(rid)}")
                if not str(why.get(rid, "")).strip():
                    errs.append(f"C11 {k}: no reason for failed run {rid}")
            if kind in ("lemma", "guard"):
                for rid in cited:
                    if runs.get(rid) != "fail":
                        continue
                    if "fail" in outcomes(rid):
                        errs.append(f"C10 {k}: cites {rid}, which failed on this very pair: the cell must fail")
                    elif rid not in frop:
                        errs.append(f"C10 {k}: cites failed run {rid} without attributing it to another pair")
                    elif rid not in pairs:
                        errs.append(f"C10 {k}: failed run {rid} has no RUN-PAIRS entry")
        for item in ev:
            if item.startswith("run:"):
                if item[4:] not in runs:
                    errs.append(f"C5 {k}: run {item[4:]} not registered")
                continue
            m = REF.match(item)
            if m:
                a, b = int(m["a"]), int(m["b"] or m["a"])
                n = line_count(m["path"])
                if n is None:
                    errs.append(f"C6 {k}: {m['path']} not in the {'working tree' if m['path'].startswith('experiment/') else 'pin tree'}")
                elif not (1 <= a <= b <= n):
                    errs.append(f"C6 {k}: {item} outside 1..{n}")
                continue
            if line_count(item) is None:
                errs.append(f"C6 {k}: evidence {item!r} is neither run:<id>, path:lines nor an existing file")
    return errs


def inputs():
    census = json.loads(CENSUS.read_text())["extra_cells"]
    runs = {p.stem: json.loads(p.read_text()).get("result") for p in (PC / "evidence" / "runs").glob("*.json")}
    pairs = json.loads(RUNPAIRS.read_text())["runs"] if RUNPAIRS.exists() else {}
    return census, findings_index(), runs, open_module_cells(), pairs


def run_check(text: str, ins, pairs=None) -> list:
    try:
        data = load_text(text)
    except Dup as d:
        return [f"C1 duplicate key {d.args[0]}"]
    a = list(ins)
    if pairs is not None:
        a[4] = pairs
    return check(data, *a)


def self_test() -> int:
    ins = inputs()
    base_text = DISCHARGES.read_text()
    base = load_text(base_text)
    ok = run_check(base_text, ins)
    results = {"unmutated_passes": not ok}
    if ok:
        print("unmutated file fails:", ok[:5])
    ids = sorted(k for k in base if k.startswith("WS-"))
    fin = next(k for k in ids if base[k]["discharge"] == "finding")
    lem = next(k for k in ids if base[k]["discharge"] == "lemma")
    opn = next(k for k in ids if base[k]["discharge"] == "open")
    pathref = next((k, i) for k in ids for i, x in enumerate(base[k]["evidence"]) if REF.match(x)
                   and not x.startswith("experiment/"))
    exp_ref = next((k, i) for k in ids for i, x in enumerate(base[k]["evidence"]) if x.startswith("experiment/") and REF.match(x))
    runref = next((k, i) for k in ids for i, x in enumerate(base[k]["evidence"]) if x.startswith("run:"))
    bad_disp = next(fid for fid, d in ins[1].items()
                    if not any(x.startswith("reproduced-") or x == "intent-undecided" for x in d))

    def mut(fn):
        d = copy.deepcopy(base)
        fn(d)
        return json.dumps(d)

    def set_(k, f, v):
        return lambda d: d[k].__setitem__(f, v)

    mutations = {
        "C1 missing id": (mut(lambda d: d.pop(ids[0])), "C1 missing"),
        "C1 duplicate key": (base_text.replace(f'"{ids[0]}": {{', f'"{ids[0]}": {{}}, "{ids[0]}": {{', 1), "C1 duplicate"),
        "C1 unknown id": (mut(lambda d: d.__setitem__("WS-OBL-999", copy.deepcopy(d[lem]))), "C1 discharge for unknown"),
        "C2 writer changed": (mut(set_(lem, "writer", "x.py::nobody")), "C2"),
        "C2 invariant changed": (mut(set_(lem, "invariant", "INV-shape" if base[lem]["invariant"] != "INV-shape" else "INV-text")), "C2"),
        "C3 bad kind": (mut(set_(lem, "discharge", "waived")), "C3"),
        "C3 bad grade": (mut(set_(lem, "grade", "assumed")), "C3"),
        "C3 empty reason": (mut(set_(opn, "reason", "  ")), "C3"),
        "C4 finding without finding": (mut(set_(fin, "findings", [])), "C4"),
        "C4 unknown finding": (mut(set_(fin, "findings", ["F-C9999"])), "C4"),
        "C4 not-reproduced finding": (mut(set_(fin, "findings", [bad_disp])), "C4"),
        "C5 unknown run": (mut(lambda d: d[runref[0]]["evidence"].__setitem__(runref[1], "run:ws-no-such-run")), "C5"),
        "C6 line past end": (mut(lambda d: d[pathref[0]]["evidence"].__setitem__(
            pathref[1], REF.match(d[pathref[0]]["evidence"][pathref[1]])["path"] + ":999999")), "C6"),
        "C6 path not at pin": (mut(lambda d: d[pathref[0]]["evidence"].__setitem__(pathref[1], "iris_src/nope.cls:1")), "C6"),
        "C6 experiment path missing": (mut(lambda d: d[exp_ref[0]]["evidence"].__setitem__(
            exp_ref[1], "experiment/playbook-uplift/semantics/NOPE.md:1")), "C6"),
        "C6 junk evidence": (mut(lambda d: d[lem]["evidence"].append("see above")), "C6"),
        "C7 module entry missing": (mut(lambda d: d.pop(sorted(k for k in d if k.startswith("module:"))[0])), "C7"),
        "C7 module entry extra": (mut(lambda d: d.__setitem__("module:02", copy.deepcopy(d[lem]))), "C7"),
        "C8 no evidence": (mut(set_(lem, "evidence", [])), "C8"),
    }
    live_lem = next(k for k in ids if base[k]["discharge"] == "lemma" and base[k]["grade"] == "live"
                    and not base[k].get("failed_runs_other_pairs"))
    attributed = next(k for k in ids if base[k].get("failed_runs_other_pairs"))
    live_fin = next(k for k in ids if base[k]["discharge"] == "finding" and base[k]["grade"] == "live"
                    and any(x.startswith("run:") and ins[2].get(x[4:]) == "fail" for x in base[k]["evidence"]))
    fin_run = next(x[4:] for x in base[live_fin]["evidence"] if x.startswith("run:") and ins[2].get(x[4:]) == "fail")
    pass_run = next(r for r, res in sorted(ins[2].items()) if res == "pass" and r.startswith("ws-deploy"))

    def lemma_from_failing(d):
        d[live_fin]["discharge"] = "lemma"
        d[live_fin]["findings"] = []
        d[live_fin]["failed_runs_other_pairs"] = [fin_run]
        d[live_fin]["failed_runs_other_pairs_reason"] = {fin_run: "seeded"}

    mutations.update({
        "C9 live without exercising run": (mut(lambda d: d[live_lem].__setitem__(
            "evidence", [x for x in d[live_lem]["evidence"] if not x.startswith("run:")] + [f"run:{pass_run}"])), "C9"),
        "C10 unattributed failed run": (mut(lambda d: d[attributed].pop("failed_runs_other_pairs")), "C10"),
        "C10 lemma on a run that failed on this pair": (mut(lemma_from_failing), "C10"),
        "C11 attribution without reason": (mut(lambda d: d[attributed].__setitem__("failed_runs_other_pairs_reason", {})), "C11"),
        "C11 attributes an uncited run": (mut(lambda d: d[attributed]["failed_runs_other_pairs"].append("ws-live-noindex")), "C11"),
        "C11 attributes a passing run": (mut(lambda d: (d[live_lem].__setitem__("failed_runs_other_pairs", [pass_run]),
                                                        d[live_lem]["evidence"].append(f"run:{pass_run}"),
                                                        d[live_lem].__setitem__("failed_runs_other_pairs_reason",
                                                                                {pass_run: "seeded"}))), "C11"),
        "C12 context run not registered": (mut(lambda d: d[lem].__setitem__("context_runs", ["ws-no-such-run"])), "C12"),
    })
    pairs_mut = copy.deepcopy(ins[4])
    pairs_mut["ws-no-such-run"] = {"exercised": []}
    errs = run_check(base_text, ins, pairs_mut)
    results["C12 RUN-PAIRS run not registered"] = any(e.startswith("C12") for e in errs)
    pairs_mut2 = copy.deepcopy(ins[4])
    for rid in base[live_lem]["evidence"]:
        if rid.startswith("run:") and rid[4:] in pairs_mut2:
            pairs_mut2[rid[4:]]["exercised"] = [x for x in pairs_mut2[rid[4:]]["exercised"]
                                                if (x["invariant"], x["writer"]) != (base[live_lem]["invariant"],
                                                                                     base[live_lem]["writer"])]
    errs = run_check(base_text, ins, pairs_mut2)
    results["C9 map no longer lists the pair"] = any(e.startswith("C9") for e in errs)
    for name, (text, tag) in mutations.items():
        errs = run_check(text, ins)
        results[name] = any(e.startswith(tag) for e in errs)
        if not results[name]:
            print(f"NOT CAUGHT: {name}: {errs[:3]}")
    print(json.dumps(results, indent=1))
    caught = sum(1 for k, v in results.items() if k != "unmutated_passes" and v)
    total = len(results) - 1
    print(f"self-test: unmutated passes={results['unmutated_passes']}, {caught}/{total} seeded mutations caught")
    return 0 if results["unmutated_passes"] and caught == total else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    ins = inputs()
    text = DISCHARGES.read_text()
    errs = run_check(text, ins)
    gen = subprocess.run([sys.executable, str(PC / "writesets" / "tools" / "build_discharges.py"), "--check"],
                         capture_output=True)
    if gen.returncode != 0:
        errs.append("C0 DISCHARGES.json or RUN-PAIRS.json differs from build_discharges.py's output")
    data = load_text(text)
    n = {}
    for k, v in data.items():
        if k.startswith("WS-"):
            n[(v["discharge"], v["grade"])] = n.get((v["discharge"], v["grade"]), 0) + 1
    census_ids = len(ins[0])
    print(f"census obligations {census_ids}, entries {sum(1 for k in data if k.startswith('WS-'))}, module entries "
          f"{sum(1 for k in data if k.startswith('module:'))}, open module cells {sorted(ins[3])}")
    print("by (discharge, grade):", json.dumps({f"{a}/{b}": c for (a, b), c in sorted(n.items())}))
    for e in errs:
        print("ERROR", e)
    print("check:", "pass" if not errs else f"FAIL ({len(errs)} errors)")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
