#!/usr/bin/env python3
"""Check reflection/closure.json and CLOSURE.md (gate 3.6-closure).

    python check_closure.py              # exit 1 on any problem
    python check_closure.py --self-test  # the unmutated list passes; every seeded mutation is caught

The expected conditions are re-derived here from the sources, independently of build_closure.py's lists:
  contract-r6    clause ids of iris-contract/CONTRACT.md's "Clauses (validated)" table
  contract-2     clause ids of contract-2/VALIDATED.json
  outside        family ids of contract-2/coverage.json
  proof-premise  keys of reflection/premise_tests.json premises of class engine or progress outside iris-contract

Rules (problem tags): [missing] an expected condition has no entry; [extra] an entry names no expected condition, or
appears twice; [status] an unknown status; a contract-2 clause whose VALIDATED.json result is not pass marked
validated; a proof premise whose status differs from its premise_tests.json verdict; [run] a cited run is not
registered, or a validating run of a validated or validated-in-part condition did not pass (observed runs of assumed
or shown-false conditions may have failed); a validated condition with no validating run; [consequence] a
non-validated condition without a consequence, or an outside family whose consequence does not contain the
coverage.json text; [missing-test] an assumed or partly validated condition that names no test that should exist; [md] CLOSURE.md is not the rendering of closure.json.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
ROOT = LANE.parent
sys.path.insert(0, str(HERE))
from build_closure import render  # noqa: E402  (rendering only; the expected set is derived below)

MAP = LANE / "closure.json"
MD = LANE / "CLOSURE.md"
STATUSES = ("validated", "validated-in-part", "shown-false", "assumed")
VERDICT_STATUS = {"tested-holds": "validated", "tested-partial": "validated-in-part",
                  "tested-violated": "shown-false", "untested": "assumed"}


def expected() -> dict:
    """condition id -> source facts needed to judge it."""
    out = {}
    text = (ROOT / "iris-contract" / "CONTRACT.md").read_text()
    sec = re.search(r"^## Clauses \(validated\).*?(?=^## )", text, re.S | re.M).group(0)
    for ln in sec.splitlines():
        m = re.match(r"^\|\s*\**([EX]-[A-Z0-9-]+)\**\s*\|", ln)
        if m:
            out[f"contract-r6:{m.group(1)}"] = {}
    for cid, v in json.loads((ROOT / "contract-2" / "VALIDATED.json").read_text())["clauses"].items():
        out[f"contract-2:{cid}"] = {"result": v["result"]}
    for fid, fam in json.loads((ROOT / "contract-2" / "coverage.json").read_text())["families"].items():
        out[f"outside:{fid}"] = {"consequence": fam["consequence"]}
    for e in json.loads((LANE / "premise_tests.json").read_text())["premises"]:
        if e.get("class") in ("engine", "progress") and not e["key"].startswith("iris-contract:"):
            out[f"proof-premise:{e['key']}"] = {"verdict": e["verdict"]}
    return out


def registry() -> dict:
    out = {}
    for p in (ROOT / "evidence" / "runs").glob("*.json"):
        d = json.loads(p.read_text())
        out[d.get("id", p.stem)] = d.get("result")
    return out


def check(m: dict, exp: dict, reg: dict, md: str) -> list:
    probs = []
    seen = Counter(c.get("id") for c in m.get("conditions", []))
    for cid in exp:
        if seen[cid] == 0:
            probs.append(f"[missing] {cid} has no closure condition")
    for cid, n in seen.items():
        if cid not in exp:
            probs.append(f"[extra] {cid} is not an expected condition")
        if n > 1:
            probs.append(f"[extra] {cid} appears {n} times")
    for c in m.get("conditions", []):
        cid, st = c.get("id"), c.get("status")
        facts = exp.get(cid, {})
        if st not in STATUSES:
            probs.append(f"[status] {cid}: unknown status {st}")
        if cid.startswith("contract-2:") and st == "validated" and facts.get("result") != "pass":
            probs.append(f"[status] {cid}: validated but VALIDATED.json says {facts.get('result')}")
        if cid.startswith("proof-premise:") and "verdict" in facts and st != VERDICT_STATUS[facts["verdict"]]:
            probs.append(f"[status] {cid}: {st} but its premise verdict is {facts['verdict']}")
        for r in c.get("runs", []) + c.get("observed", []):
            if r not in reg and not str(r).startswith("tests/"):
                probs.append(f"[run] {cid}: run {r} is not registered")
        if st in ("validated", "validated-in-part"):
            runs = [r for r in c.get("runs", []) if r in reg]
            if not runs and not any(str(r).startswith("tests/") for r in c.get("runs", [])):
                probs.append(f"[run] {cid}: {st} with no validating run")
            if st == "validated" and cid.split(":")[0] in ("contract-r6", "contract-2"):
                for r in runs:
                    if reg[r] != "pass":
                        probs.append(f"[run] {cid}: validating run {r} has result {reg[r]}")
        if st != "validated" and not str(c.get("consequence") or "").strip():
            probs.append(f"[consequence] {cid}: {st} without a consequence")
        if st in ("assumed", "validated-in-part") and str(c.get("missing_test") or "").strip() in ("", "-"):
            probs.append(f"[missing-test] {cid}: {st} without the test that should exist")
        if cid.startswith("outside:") and facts.get("consequence") and facts["consequence"] not in (c.get("consequence") or ""):
            probs.append(f"[consequence] {cid}: consequence differs from coverage.json")
    if md != render(m):
        probs.append("[md] CLOSURE.md is not the rendering of closure.json (run build_closure.py)")
    return probs


def self_test() -> int:
    base = json.loads(MAP.read_text())
    exp, reg, md = expected(), registry(), MD.read_text()
    p0 = check(base, exp, reg, md)
    print(f"unmutated: {len(p0)} problems")
    for p in p0[:10]:
        print("  ", p)
    ok = not p0
    conds = base["conditions"]
    i_r6 = next(i for i, c in enumerate(conds) if c["id"].startswith("contract-r6:") and c["status"] == "validated")
    i_out = next(i for i, c in enumerate(conds) if c["id"].startswith("outside:") and c["status"] == "assumed")
    i_pp = next(i for i, c in enumerate(conds) if c["id"].startswith("proof-premise:") and c["status"] == "assumed")
    failing = next(r for r, res in reg.items() if res == "fail")

    def drop(m, e):
        m["conditions"].pop(0)

    def new_source(m, e):
        e["outside:zz-new-family"] = {"consequence": "seeded"}

    def extra(m, e):
        c = copy.deepcopy(m["conditions"][0])
        c["id"] = "contract-r6:X-NOSUCH"
        m["conditions"].append(c)

    def twice(m, e):
        m["conditions"].append(copy.deepcopy(m["conditions"][1]))

    def bad_status(m, e):
        m["conditions"][i_r6]["status"] = "proved"

    def verdict_mismatch(m, e):
        m["conditions"][i_pp]["status"] = "validated"
        m["conditions"][i_pp]["runs"] = [m["conditions"][i_r6]["runs"][0]]

    def unregistered(m, e):
        m["conditions"][i_r6]["runs"].append("rf-no-such-run")

    def failing_validator(m, e):
        m["conditions"][i_r6]["runs"] = [failing]

    def no_run(m, e):
        m["conditions"][i_r6]["runs"] = []

    def no_consequence(m, e):
        m["conditions"][i_out]["consequence"] = ""

    def changed_consequence(m, e):
        m["conditions"][i_out]["consequence"] = "something else"

    def no_missing_test(m, e):
        m["conditions"][i_out]["missing_test"] = ""

    def md_stale(m, e):
        m["conditions"][i_out]["consequence"] += " (edited without rebuilding)"

    muts = [("missing", drop), ("missing", new_source), ("extra", extra), ("extra", twice), ("status", bad_status),
            ("status", verdict_mismatch), ("run", unregistered), ("run", failing_validator), ("run", no_run),
            ("consequence", no_consequence), ("consequence", changed_consequence), ("missing-test", no_missing_test), ("md", md_stale)]
    caught = 0
    for tag, fn in muts:
        m, e = copy.deepcopy(base), copy.deepcopy(exp)
        fn(m, e)
        probs = check(m, e, reg, md)
        hit = any(p.startswith(f"[{tag}]") for p in probs)
        caught += hit
        ok &= hit
        print(f"mutation {fn.__name__:20s} expects [{tag}]: {'CAUGHT' if hit else 'MISSED'} ({len(probs)} problems)")
    print(f"self-test: {caught}/{len(muts)} seeded mutations caught; unmutated {'clean' if not p0 else 'NOT clean'}")
    print("SELF-TEST PASS" if ok else "SELF-TEST FAIL")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    m = json.loads(MAP.read_text())
    exp, reg = expected(), registry()
    probs = check(m, exp, reg, MD.read_text() if MD.exists() else "")
    groups = Counter(cid.split(":")[0] for cid in exp)
    print(f"expected conditions from the sources: {len(exp)} ({', '.join(f'{g} {n}' for g, n in sorted(groups.items()))}); "
          f"entries: {len(m.get('conditions', []))}")
    for g in sorted(groups):
        st = Counter(c["status"] for c in m["conditions"] if c["id"].startswith(g + ":"))
        print(f"  {g:14s} " + ", ".join(f"{k} {st.get(k, 0)}" for k in STATUSES))
    st = Counter(c["status"] for c in m["conditions"])
    print("all: " + ", ".join(f"{k} {st.get(k, 0)}" for k in STATUSES))
    print("shown-false: " + ", ".join(c["id"] for c in m["conditions"] if c["status"] == "shown-false"))
    nruns = len({r for c in m["conditions"] for r in c.get("runs", []) + c.get("observed", [])})
    print(f"distinct runs cited: {nruns}, every one registered: {all(r in reg for c in m['conditions'] for r in c.get('runs', []) + c.get('observed', []) if not str(r).startswith('tests/'))}")
    for p in probs:
        print("PROBLEM", p)
    print("CHECK PASS" if not probs else f"CHECK FAIL ({len(probs)} problems)")
    return 0 if not probs else 1


if __name__ == "__main__":
    sys.exit(main())
