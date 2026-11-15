#!/usr/bin/env python3
"""Freshness gate for the whole foundation: every model's latest prove receipt and the latest receipt of every
control named in its model.json must match the current input files and carry the expected verdict; every native
observation copy under receipts/native/ must match the current probe, helper and harness files.

    python3 .g5/Verus_verification/tools/check_evidence.py      # exit 0 fresh, 1 stale or wrong

Run from the repository root. Standard library only. It does not run Verus or IRIS.
"""
import glob
import hashlib
import json
import os
import sys

V = ".g5/Verus_verification"


def h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def main():
    problems = []
    for spec_path in sorted(glob.glob(f"{V}/models/*/model.json")):
        spec = json.load(open(spec_path))
        m = spec["name"]
        proves = sorted(glob.glob(f"{V}/results/{m}/*-prove/receipt.json"))
        if not proves:
            problems.append(f"{m}: no prove receipt under results/")
            continue
        d = json.load(open(proves[-1]))
        if d["verdict"] != "PASS" or d["observed"]["verified"] != spec.get("expected_verified"):
            problems.append(f"{m}: prove {d['verdict']} {d['observed']['verified']} != expected {spec.get('expected_verified')}")
        problems += [f"{m}: prove input changed: {p}" for p, x in d["inputs"].items() if h(p) != x]
        latest = {}
        for f in sorted(glob.glob(f"{V}/results/{m}/*-control-*/receipt.json")):
            c = json.load(open(f))
            latest[c["control"]["name"]] = c
        for c in spec["controls"]:
            r = latest.get(c["name"])
            if r is None:
                problems.append(f"{m}: control {c['name']} has no receipt")
            elif r["verdict"] != "EXPECTED_FAIL":
                problems.append(f"{m}: control {c['name']} {r['verdict']}")
            elif any(h(p) != x for p, x in r["inputs"].items()):
                problems.append(f"{m}: control {c['name']} receipt is stale")
        print(f"{m}: prove {d['observed']['verified']} verified, {len(spec['controls'])} controls checked")
        # Consolidated uplift: a model with a unit-level binding harness needs a fresh AGREES binding receipt.
        if os.path.exists(os.path.join(os.path.dirname(spec_path), "binding.py")):
            binds = sorted(glob.glob(f"{V}/results/{m}/*-binding/receipt.json"))
            if not binds:
                problems.append(f"{m}: binding.py has no binding receipt")
            else:
                b = json.load(open(binds[-1]))
                if b.get("verdict") != "AGREES":
                    problems.append(f"{m}: latest binding {b.get('verdict')}")
                problems += [f"{m}: binding input changed: {p}" for p, x in b["inputs"].items() if h(p) != x]
    obs = sorted(glob.glob(f"{V}/receipts/native/*.json"))
    for f in obs:
        d = json.load(open(f))
        ins = d.get("_probe_inputs")
        if not ins:
            problems.append(f"native {os.path.basename(f)}: no probe hashes")
            continue
        problems += [f"native {os.path.basename(f)}: input changed: {p}" for p, x in ins.items() if h(p) != x]
    print(f"native observations checked: {len(obs)}")
    # Consolidated uplift (2026-11-14): playbook-arm crate reruns (tools/run_playbook_crate.py). For each family and
    # label the latest receipt must carry the expected verdict (PASS for the baseline, EXPECTED_FAIL for a control) and
    # match the arm's recorded result where it recorded one; the crate's tree at HEAD must still be the tree it ran.
    # Earlier ERROR receipts superseded by a later verdict for the same label are kept and not counted.
    import subprocess
    pb = 0
    for fam_dir in sorted(glob.glob(f"{V}/results/playbook-*")):
        latest = {}
        for f in sorted(glob.glob(f"{fam_dir}/*/receipt.json")):
            d = json.load(open(f))
            if d.get("kind") == "playbook-crate-rerun":
                latest[d["label"]] = (f, d)
        for label, (f, d) in latest.items():
            pb += 1
            want = "PASS" if label == "baseline" else "EXPECTED_FAIL"
            if d["verdict"] != want:
                problems.append(f"{os.path.basename(fam_dir)} {label}: {d['verdict']} (expected {want}) in {f}")
            if d.get("recorded") and not d.get("matches_record"):
                problems.append(f"{os.path.basename(fam_dir)} {label}: differs from the arm's RESULTS.json")
            try:
                tree = subprocess.check_output(["git", "rev-parse", f"HEAD:{d['crate']}"], text=True,
                                               stderr=subprocess.DEVNULL).strip()
            except subprocess.CalledProcessError:
                tree = None
            if tree != d["sources"]["tree_at_source"]:
                problems.append(f"{os.path.basename(fam_dir)} {label}: crate tree at HEAD {tree} != the tree it ran")
    print(f"playbook crate reruns checked: {pb} (family, label) pairs")
    for p in problems:
        print("STALE/WRONG:", p)
    print("FRESH" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
