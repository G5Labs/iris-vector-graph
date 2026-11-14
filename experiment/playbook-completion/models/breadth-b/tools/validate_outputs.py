#!/usr/bin/env python3
"""Structural check of breadth lane B outputs for modules 07..11 (with a self-test).

    python experiment/playbook-completion/models/breadth-b/tools/validate_outputs.py [--self-test]

Checks, per module NN:
- findings/audit/NN.json has exactly one record per ORIGINAL finding id in experiment/playbook-uplift/findings/NN.md,
  new ids match F-C<NN><kk>, every record has the CONVENTIONS fields, disposition/outcome/severity are in vocabulary;
- every evidence ref resolves: a registry id (evidence/runs/<id>.json, or an orchestrator/other-lane id there), a model
  check id in models/breadth-b/RESULTS.json (with or without the b-mc- prefix), or path:lines inside an existing file
  of the pin / experiment tree (line numbers within the file);
- a record with disposition reproduced-live cites at least one live/probe/run registry entry; reproduced-model cites a
  model check whose result is met;
- footprints/NN.json entries carry id/role/source; modules/NN.json has gates, env_features with sources, and
  gates_by_id covering every module / module-writer gate of matrix/gates.json.
Prints one line per problem; exit 1 if any.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMP = HERE.parents[2]
REPO = COMP.parents[1]
MODS = ["07", "08", "09", "10", "11"]
DISP = {"reproduced-live", "reproduced-model", "reproduced-test", "confirmed-source", "not-reproduced", "refuted",
        "blocked-access", "unrepresentable", "intent-undecided", "product-defect"}
OUTC = {"product-defect", "intent-undecided", "blocked-access", "unrepresentable", "holds-proved", "holds-mc",
        "holds-live", "holds-run", "holds-inspected", "not-applicable", "refuted", "not-reproduced"}
SEV = {"S1", "S2", "S3", "S4"}
FIELDS = ["id", "module", "title", "intended", "observed", "disposition", "evidence", "gates", "severity",
          "confidence", "remedy", "notes"]
STATUS = {"closed", "failed", "open", "blocked", "not-applicable"}
PATHREF = re.compile(r"^([\w./@+-]+\.\w+)(?::(\d+)(?:-(\d+))?)?$")


def load(p: Path):
    return json.loads(p.read_text())


def originals(mod: str):
    t = (REPO / "experiment" / "playbook-uplift" / "findings" / f"{mod}.md").read_text()
    return sorted(set(re.findall(r"^### (F-\d{4})\b", t, re.M)))


def ref_ok(ref: str, runs: set, checks: dict, lines_cache: dict) -> str | None:
    r = ref.strip()
    if r in runs or r in checks or (r.startswith("b-mc-") and r[5:] in checks):
        return None
    base = r.split(" ")[0].split("#")[0].rstrip(",;")
    if base.startswith("$RUN_DIR/"):  # a raw artifact outside the repository: it must exist under $RUN_DIR
        import os
        rp = Path(os.environ.get("RUN_DIR", "/nonexistent")) / base[len("$RUN_DIR/"):].split(":")[0]
        return None if rp.exists() else f"run artifact not found: {base}"
    if "::" in base:  # tested:<path>::<name> -> the test function or class must exist in the file
        path, _, name = base.partition("::")
        p = REPO / path
        if not p.exists():
            return f"test file not found: {path}"
        leaf = name.split("::")[-1]
        if not re.search(rf"^\s*(?:async\s+)?(?:def|class)\s+{re.escape(leaf)}\b", p.read_text(errors="replace"), re.M):
            return f"test {leaf} not in {path}"
        return None
    pm = re.match(r"^(?:assumed:)?(P-\d{4})\b", r)
    if pm:  # a premise of the original trust inventory
        trust = "\n".join(t.read_text() for t in (REPO / "experiment" / "playbook-uplift" / "trust").glob("*.md"))
        trust += (REPO / "experiment" / "playbook-uplift" / "TRUST.md").read_text()
        return None if pm.group(1) in trust else f"premise {pm.group(1)} not in the original trust inventory"
    m = PATHREF.match(base)
    if m:
        path = m.group(1)
        if path.startswith("$RUN_DIR/"):
            return None  # raw logs live outside the repository; registry records carry their hashes
        p = REPO / path
        if not p.exists():
            p2 = COMP / path
            if not p2.exists():
                return f"path not found: {path}"
            p = p2
        if m.group(2) and p.is_file():
            n = lines_cache.setdefault(str(p), len(p.read_text(errors="replace").splitlines()))
            hi = int(m.group(3) or m.group(2))
            if hi > n:
                return f"line {hi} beyond end ({n}) of {path}"
        return None
    if re.match(r"^(open:)?HD-\d{4}$", r) or re.match(r"^(F|F-C)\-?\w+$", r) or r.startswith("http"):
        return None
    if r.startswith("commit:") or re.match(r"^[0-9a-f]{7,40}$", r):
        return None
    return f"unresolved ref: {r[:80]}"


def check_module(mod: str, runs: set, checks: dict, gate_ids: set, problems: list):
    cache: dict = {}
    fa = COMP / "findings" / "audit" / f"{mod}.json"
    if not fa.exists():
        problems.append(f"{mod}: missing {fa.name}")
        return
    d = load(fa)
    recs = d.get("findings", [])
    new = d.get("new_findings", [])
    ids = [r.get("id") for r in recs]
    want = originals(mod)
    if sorted(ids) != want:
        problems.append(f"{mod}: original ids {sorted(set(want) - set(ids))} missing, extra {sorted(set(ids) - set(want))}")
    for r in recs + new:
        rid = r.get("id")
        for f in FIELDS:
            if f not in r:
                problems.append(f"{mod} {rid}: field {f} missing")
        if r.get("disposition") not in DISP:
            problems.append(f"{mod} {rid}: disposition {r.get('disposition')!r}")
        if "outcome" in r and r["outcome"] not in OUTC:
            problems.append(f"{mod} {rid}: outcome {r.get('outcome')!r}")
        if r.get("severity") not in SEV:
            problems.append(f"{mod} {rid}: severity {r.get('severity')!r}")
        kinds = set()
        for e in r.get("evidence", []):
            kinds.add(e.get("kind"))
            msg = ref_ok(str(e.get("ref", "")), runs, checks, cache)
            if msg:
                problems.append(f"{mod} {rid}: {msg}")
        if r.get("disposition") == "reproduced-live" and not any(
                str(e.get("ref", "")) in runs for e in r.get("evidence", []) if e.get("kind") in ("live", "probe", "run", "trace")):
            problems.append(f"{mod} {rid}: reproduced-live without a registered live/probe/run ref")
        if r.get("disposition") == "reproduced-model":
            ok = [e for e in r.get("evidence", []) if e.get("kind") == "mc"
                  and checks.get(str(e["ref"]).removeprefix("b-mc-"), {}).get("met")]
            if not ok:
                problems.append(f"{mod} {rid}: reproduced-model without a met model check")
    for r in new:
        if not re.match(rf"^F-C{mod}\d\d$", str(r.get("id"))):
            problems.append(f"{mod}: new finding id {r.get('id')!r} not F-C{mod}kk")
    fp = COMP / "footprints" / f"{mod}.json"
    if not fp.exists():
        problems.append(f"{mod}: missing footprints")
    else:
        for e in load(fp).get("entry_points", []):
            for f in ("id", "role", "source"):
                if f not in e:
                    problems.append(f"{mod} footprint {e.get('id')}: {f} missing")
            jv = e.get("journal_validation")
            if jv and jv.get("run_id") and jv["run_id"] not in runs:
                problems.append(f"{mod} footprint {e.get('id')}: run_id {jv['run_id']} not registered")
    mp = COMP / "modules" / f"{mod}.json"
    if not mp.exists():
        problems.append(f"{mod}: missing modules file")
        return
    m = load(mp)
    for g in m.get("gates", []):
        if g.get("status") not in STATUS:
            problems.append(f"{mod} gate {g.get('gate')}: status {g.get('status')!r}")
    gb = m.get("gates_by_id")
    if not isinstance(gb, dict):
        problems.append(f"{mod}: gates_by_id missing")
    else:
        miss = sorted(gate_ids - set(gb))
        if miss:
            problems.append(f"{mod}: gates_by_id lacks {miss}")
        for k, v in gb.items():
            if v.get("status") not in STATUS:
                problems.append(f"{mod} gates_by_id {k}: status {v.get('status')!r}")
            if v.get("status") == "not-applicable" and not (v.get("reason") or v.get("remaining") or v.get("evidence")):
                problems.append(f"{mod} gates_by_id {k}: not-applicable without a reason")
    if not m.get("env_features"):
        problems.append(f"{mod}: env_features empty")
    for f in m.get("env_features", []):
        if not f.get("source"):
            problems.append(f"{mod} env feature {f.get('feature')!r}: no source")
    if "storage_order" not in m and "3.4-storage-order" not in json.dumps(m.get("gates_by_id", {})):
        problems.append(f"{mod}: no storage_order dispositions")


def main() -> int:
    runs = {p.stem for p in (COMP / "evidence" / "runs").glob("*.json")}
    res = load(COMP / "models" / "breadth-b" / "RESULTS.json")["checks"]
    checks = {c["id"]: c for c in res}
    gates = load(COMP / "matrix" / "gates.json")["gates"]
    gate_ids = {g["id"] for g in gates if g["scope"] in ("module", "module-writer")}
    if "--self-test" in sys.argv:
        bad = []
        assert ref_ok("iris_vector_graph/fusion.py:1-2", runs, checks, {}) is None
        assert ref_ok("iris_vector_graph/fusion.py:999999", runs, checks, {}) is not None
        assert ref_ok("no/such/file.py:1", runs, checks, {}) is not None
        assert ref_ok("not-a-registered-run-id", runs, checks, {}) is not None
        assert ref_ok(next(iter(checks)), runs, checks, {}) is None
        assert ref_ok("tests/unit/test_ledger_guard.py::test_probe_failure_fails_open", runs, checks, {}) is None
        assert ref_ok("tests/unit/test_ledger_guard.py::test_no_such_test_xyz", runs, checks, {}) is not None
        assert ref_ok("P-0002", runs, checks, {}) is None and ref_ok("P-9999", runs, checks, {}) is not None
        print("self-test passed: valid refs accepted, bad line/path/id rejected")
        return 0
    problems: list = []
    for mod in MODS:
        check_module(mod, runs, checks, gate_ids, problems)
    for p in problems:
        print(p)
    print(f"{len(problems)} problems across modules {', '.join(MODS)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
