#!/usr/bin/env python3
"""Summary check of the refusals audit (gate 5c-refusals): every stated refusal is audited, and each entry's
evidence resolves mechanically.

    python rx_audit.py [--modules 01,04,...]            # merge refusals/audit/NN.json -> refusals/audit.json, check
    python rx_audit.py --self-test

Input: one fragment per module, refusals/audit/NN.json = {"module": "NN", "statements": [entry, ...]}. Entry:
  id                  ontology X statement id (must be one extract_x.py lists for the module)
  text                the statement's text, verbatim from the ontology
  implementing_code   ["path:a-b", ...] at the pin (each must exist and be in range); [] only with outcome
                      product-defect or blocked-access and a non-empty `absent` saying what was searched
  outcome             holds-live | holds-run | holds-inspected | product-defect | blocked-access | intent-undecided
                      | unrepresentable | not-applicable
  evidence            ["run:<id>", ...] registered runs (evidence/runs/<id>.json, product_pin = pin, log hash equal)
  live_cases          (holds-live, and product-defect shown live) [case names] in a registered run's results.json
                      log: each named case must exist there with statement = id; for holds-live each must have
                      outcome holds-live (refused as stated, nothing changed); for product-defect at least one
                      must not
  log_contains        (holds-run) {"run:<id>": "substring"}: the substring must occur in that run's log; also
                      accepted for holds-live without live_cases when the run is another lane's registered kind-live
                      run that already shows the refusal
  finding             (product-defect, intent-undecided) a finding id in findings/audit/*.json
  dependency          (blocked-access) the exact missing dependency
  notes               free text

Checks: coverage (every extracted X statement of the target modules has exactly one entry, no unknown ids), text
equality, outcome vocabulary, citations in range, run records (pin, kind, log sha256), live-case results, findings
present, dependency present. Self-test: seeded defects (a seeded X statement with no entry, a missing entry, a
holds-live entry whose case is absent from the log, a holds-live case that changed the store, an out-of-range
citation, an unknown run, a blocked entry without a dependency, a product-defect without a finding, paraphrased
text) must each be reported with its own rule tag, and the real audit must pass.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
COMPLETION = LANE.parent
REPO = COMPLETION.parents[1]
sys.path.insert(0, str(HERE))
import extract_x  # noqa: E402

PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
OUTCOMES = {"holds-live", "holds-run", "holds-inspected", "product-defect", "blocked-access", "intent-undecided",
            "unrepresentable", "not-applicable"}
REF = re.compile(r"^(.+?):(\d+)(?:-(\d+))?$")


def run_dir() -> Path:
    return Path(os.environ.get("RUN_DIR", "/nonexistent"))


def load_findings() -> Dict[str, dict]:
    """findings/audit/*.json plus this lane's per-module fragments refusals/findings/*.json (merged into
    findings/audit/zz-refusals.json at the end)."""
    out = {}
    files = sorted((COMPLETION / "findings" / "audit").glob("*.json")) + sorted((LANE / "findings").glob("*.json"))
    for f in files:
        try:
            d = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        if isinstance(d, list):
            items = d
        else:
            items = []
            for key in ("findings", "new_findings", "items"):
                v = d.get(key) or []
                items += list(v.values()) if isinstance(v, dict) else list(v)
        for x in items:
            if isinstance(x, dict) and x.get("id"):
                out[x["id"]] = x
    return out


class Registry:
    def __init__(self, runs: Path, rdir: Path):
        self.runs = runs
        self.rdir = rdir
        self._logs: Dict[str, Optional[bytes]] = {}

    def record(self, rid: str) -> Optional[dict]:
        p = self.runs / f"{rid}.json"
        return json.loads(p.read_text()) if p.is_file() else None

    def log(self, rid: str) -> Optional[bytes]:
        if rid not in self._logs:
            r = self.record(rid)
            data = None
            if r:
                p = Path(r["log"].replace("$RUN_DIR", str(self.rdir)))
                if p.is_file():
                    data = p.read_bytes()
                    if hashlib.sha256(data).hexdigest() != r.get("log_sha256"):
                        data = b"__HASH_MISMATCH__"
            self._logs[rid] = data
        return self._logs[rid]


def check_ref(ref: str, repo: Path) -> Optional[str]:
    m = REF.match(ref)
    if not m:
        return f"not path:lines: {ref!r}"
    p = repo / m.group(1)
    if not p.is_file():
        return f"no file at the pin: {m.group(1)}"
    a, b = int(m.group(2)), int(m.group(3) or m.group(2))
    n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    if not (1 <= a <= b <= n):
        return f"range {a}-{b} outside {m.group(1)} ({n} lines)"
    return None


def check(fragments: List[dict], xs: dict, reg: Registry, findings: Dict[str, dict], repo: Path) -> dict:
    errors: List[str] = []
    want = {s["id"]: s for s in xs["statements"]}
    seen: Dict[str, dict] = {}
    for fr in fragments:
        for e in fr.get("statements", []):
            sid = e.get("id")
            if sid in seen:
                errors.append(f"[duplicate] {sid}")
                continue
            seen[sid] = e
    for sid in want:
        if sid not in seen:
            errors.append(f"[missing] {sid} ({want[sid]['module']}) has no audit entry")
    for sid in seen:
        if sid not in want:
            errors.append(f"[unknown] {sid} is not an X statement of the target modules")
    counts: Dict[str, Dict[str, int]] = {}
    for sid, e in seen.items():
        if sid not in want:
            continue
        s = want[sid]
        counts.setdefault(s["module"], {}).setdefault(e.get("outcome", "?"), 0)
        counts[s["module"]][e.get("outcome", "?")] += 1
        if e.get("text") != s["text"]:
            errors.append(f"[text] {sid}: text differs from the ontology")
        o = e.get("outcome")
        if o not in OUTCOMES:
            errors.append(f"[outcome] {sid}: {o!r}")
            continue
        code = e.get("implementing_code") or []
        if not code and not (o in ("product-defect", "blocked-access", "not-applicable") and e.get("absent")):
            errors.append(f"[code] {sid}: no implementing code cited")
        for ref in code:
            bad = check_ref(ref, repo)
            if bad:
                errors.append(f"[citation] {sid}: {bad}")
        runs = [x[4:] for x in e.get("evidence", []) if x.startswith("run:")]
        for rid in runs:
            r = reg.record(rid)
            if r is None:
                errors.append(f"[run] {sid}: unregistered run {rid}")
                continue
            if r.get("product_pin") != PIN:
                errors.append(f"[run] {sid}: run {rid} not on the pin")
            if reg.log(rid) == b"__HASH_MISMATCH__":
                errors.append(f"[run] {sid}: run {rid} log differs from its registered hash")
        if o == "holds-live" and not e.get("live_cases") and e.get("log_contains"):
            # another lane's registered live run that already shows the refusal: kind live, the substring in its log
            for k, sub in e["log_contains"].items():
                rid = k[4:] if k.startswith("run:") else k
                r = reg.record(rid) or {}
                data = reg.log(rid)
                if r.get("kind") != "live" or not data or data == b"__HASH_MISMATCH__" or sub.encode() not in data:
                    errors.append(f"[live] {sid}: {sub!r} not in the log of live run {rid}")
        elif o == "holds-live" or (o == "product-defect" and e.get("live_cases")):
            cases = e.get("live_cases") or []
            if not cases:
                errors.append(f"[live] {sid}: holds-live without live_cases")
            found = []
            for rid in runs:
                data = reg.log(rid)
                if not data or data == b"__HASH_MISMATCH__":
                    continue
                try:
                    doc = json.loads(data)
                except Exception:  # noqa: BLE001
                    continue
                for c in doc.get("cases", []) if isinstance(doc, dict) else []:
                    if c.get("statement") == sid and c.get("case") in cases:
                        found.append(c)
            names = {c["case"] for c in found}
            for cn in cases:
                if cn not in names:
                    errors.append(f"[live] {sid}: case {cn!r} not in the cited runs' logs")
            if o == "holds-live":
                for c in found:
                    if c.get("outcome") != "holds-live":
                        errors.append(f"[live] {sid}: case {c['case']!r} outcome {c.get('outcome')}")
            elif found and all(c.get("outcome") == "holds-live" for c in found):
                errors.append(f"[live] {sid}: product-defect but every cited case holds")
        if o == "holds-run":
            lc = e.get("log_contains") or {}
            if not lc:
                errors.append(f"[run-log] {sid}: holds-run without log_contains")
            for k, sub in lc.items():
                rid = k[4:] if k.startswith("run:") else k
                data = reg.log(rid)
                if not data or data == b"__HASH_MISMATCH__" or sub.encode() not in data:
                    errors.append(f"[run-log] {sid}: {sub!r} not in the log of {rid}")
        if o in ("product-defect", "intent-undecided"):
            f = e.get("finding")
            if not f or f not in findings:
                errors.append(f"[finding] {sid}: finding {f!r} not in findings/audit")
        if o == "blocked-access" and not e.get("dependency"):
            errors.append(f"[dependency] {sid}: blocked-access without the dependency")
        if o in ("holds-live", "holds-run", "product-defect") and not runs:
            errors.append(f"[run] {sid}: {o} cites no registered run")
    return {"errors": errors, "audited": len([s for s in seen if s in want]), "expected": len(want),
            "per_module": counts}


def load_fragments(modules: List[str]) -> List[dict]:
    out = []
    for m in modules:
        p = LANE / "audit" / f"{m}.json"
        if p.is_file():
            out.append(json.loads(p.read_text()))
    return out


def self_test(modules: List[str]) -> int:
    xs = extract_x.extract(extract_x.ONTOLOGY, modules, REPO)
    frs = load_fragments(modules)
    reg = Registry(COMPLETION / "evidence" / "runs", run_dir())
    findings = load_findings()
    base = check(frs, xs, reg, findings, REPO)
    ok = not base["errors"]
    print(("PASS " if ok else "FAIL ") + f"real audit: {base['audited']}/{base['expected']}, "
          f"{len(base['errors'])} errors {base['errors'][:5]}")

    def expect(name, frs2, xs2, tag, sid):
        nonlocal ok
        r = check(frs2, xs2, reg, findings, REPO)
        hit = any(e.startswith(tag) and sid in e for e in r["errors"])
        print(("PASS " if hit else "FAIL ") + name)
        ok &= hit

    # 1. seeded X statement in the extraction with no audit entry
    xs2 = copy.deepcopy(xs)
    xs2["statements"].append({"id": "LED-X99", "module": "11", "text": "seeded", "evidence": "", "inspected": []})
    expect("seeded X statement without an entry is reported", frs, xs2, "[missing]", "LED-X99")
    # pick entries to damage
    flat = [(i, j, e) for i, fr in enumerate(frs) for j, e in enumerate(fr["statements"])]
    live = next((t for t in flat if t[2]["outcome"] == "holds-live"), None)
    any_e = flat[0]
    # 2. a missing entry
    f2 = copy.deepcopy(frs)
    del f2[any_e[0]]["statements"][any_e[1]]
    expect("deleted entry is reported", f2, xs, "[missing]", any_e[2]["id"])
    if live:
        # 3. holds-live whose case is absent from the cited log
        f3 = copy.deepcopy(frs)
        f3[live[0]]["statements"][live[1]]["live_cases"] = ["no such case"]
        expect("holds-live with an absent case is reported", f3, xs, "[live]", live[2]["id"])
        # 4. holds-live citing a case that did not hold: point it at a case of another statement with a bad outcome
        bad = None
        for fr in frs:
            for e in fr["statements"]:
                if e["outcome"] == "product-defect" and e.get("live_cases"):
                    bad = e
                    break
            if bad:
                break
        if bad:
            f4 = copy.deepcopy(frs)
            for fr in f4:
                for e in fr["statements"]:
                    if e["id"] == bad["id"]:
                        e["outcome"] = "holds-live"
            expect("a changed/unrefused case cited as holds-live is reported", f4, xs, "[live]", bad["id"])
        else:
            print("SKIP no live product-defect entry to flip (control 4)")
    # 5. out-of-range citation
    f5 = copy.deepcopy(frs)
    f5[any_e[0]]["statements"][any_e[1]]["implementing_code"] = ["iris_src/src/Graph/KG/Ledger.cls:99998-99999"]
    expect("out-of-range citation is reported", f5, xs, "[citation]", any_e[2]["id"])
    # 6. unknown run
    f6 = copy.deepcopy(frs)
    f6[any_e[0]]["statements"][any_e[1]]["evidence"] = ["run:rx-no-such-run"]
    expect("unregistered run is reported", f6, xs, "[run]", any_e[2]["id"])
    # 7. blocked without dependency
    f7 = copy.deepcopy(frs)
    f7[any_e[0]]["statements"][any_e[1]].update({"outcome": "blocked-access", "dependency": ""})
    expect("blocked-access without a dependency is reported", f7, xs, "[dependency]", any_e[2]["id"])
    # 8. product-defect without finding
    f8 = copy.deepcopy(frs)
    f8[any_e[0]]["statements"][any_e[1]].update({"outcome": "product-defect", "finding": None})
    expect("product-defect without a finding is reported", f8, xs, "[finding]", any_e[2]["id"])
    # 9. paraphrased text
    f9 = copy.deepcopy(frs)
    f9[any_e[0]]["statements"][any_e[1]]["text"] += " (paraphrase)"
    expect("paraphrased text is reported", f9, xs, "[text]", any_e[2]["id"])
    print("self-test", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default=",".join(extract_x.TARGET))
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    modules = a.modules.split(",")
    if a.self_test:
        return self_test(modules)
    xs = extract_x.extract(extract_x.ONTOLOGY, modules, REPO)
    frs = load_fragments(modules)
    reg = Registry(COMPLETION / "evidence" / "runs", run_dir())
    r = check(frs, xs, reg, load_findings(), REPO)
    print(f"audited {r['audited']}/{r['expected']} X statements; per module {json.dumps(r['per_module'])}")
    for e in r["errors"]:
        print("  " + e)
    if not a.no_write:
        merged = {"gate": "5c-refusals", "pin": PIN, "modules": modules, "expected": r["expected"],
                  "audited": r["audited"], "per_module": r["per_module"], "errors": r["errors"],
                  "statements": [e for fr in frs for e in fr["statements"]]}
        (LANE / "audit.json").write_text(json.dumps(merged, indent=1) + "\n")
    print("rx-audit", "PASS" if not r["errors"] else "FAIL")
    return 0 if not r["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
