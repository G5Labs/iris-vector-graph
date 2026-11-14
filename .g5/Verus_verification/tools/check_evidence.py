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
    obs = sorted(glob.glob(f"{V}/receipts/native/*.json"))
    for f in obs:
        d = json.load(open(f))
        ins = d.get("_probe_inputs")
        if not ins:
            problems.append(f"native {os.path.basename(f)}: no probe hashes")
            continue
        problems += [f"native {os.path.basename(f)}: input changed: {p}" for p, x in ins.items() if h(p) != x]
    print(f"native observations checked: {len(obs)}")
    for p in problems:
        print("STALE/WRONG:", p)
    print("FRESH" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
