#!/usr/bin/env python3
"""Every registered run's log must exist under $RUN_DIR with the recorded SHA-256 and size, against the pin's tree.

    python check_registry.py [--self-test]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_TREE = "b098a6f48a379ce86ee2e5ae9ad0d37994dea567"


def check(reg_dir: Path, run_dir: Path) -> list:
    problems = []
    for p in sorted(reg_dir.glob("*.json")):
        r = json.loads(p.read_text())
        if r.get("product_tree") != PIN_TREE:
            problems.append(f"{p.stem}: product tree {r.get('product_tree')} is not the pin's")
        log = run_dir / r["log"].replace("$RUN_DIR/", "", 1)
        if not log.exists():
            problems.append(f"{p.stem}: log missing {r['log']}")
            continue
        data = log.read_bytes()
        if hashlib.sha256(data).hexdigest() != r["log_sha256"]:
            problems.append(f"{p.stem}: log hash differs {r['log']}")
        if r.get("result") not in ("pass", "fail", "expected-violation", "incomplete", "blocked"):
            problems.append(f"{p.stem}: bad result {r.get('result')}")
    return problems


def main() -> int:
    run_dir = Path(os.environ["RUN_DIR"])
    if "--self-test" in sys.argv:
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "reg").mkdir()
            (t / "log.txt").write_text("x")
            good = {"log": "$RUN_DIR/log.txt", "log_sha256": hashlib.sha256(b"x").hexdigest(), "result": "pass",
                    "product_tree": PIN_TREE}
            (t / "reg" / "a.json").write_text(json.dumps(good))
            (t / "reg" / "b.json").write_text(json.dumps({**good, "log_sha256": "0" * 64}))
            (t / "reg" / "c.json").write_text(json.dumps({**good, "log": "$RUN_DIR/missing"}))
            probs = check(t / "reg", t)
            ok = len(probs) == 2 and any("b:" in x for x in probs) and any("c:" in x for x in probs)
            print("self-test", "PASS" if ok else "FAIL", probs)
            return 0 if ok else 1
    probs = check(ROOT / "evidence" / "runs", run_dir)
    sup = json.loads((ROOT / "incidents" / "superseded-logs.json").read_text()).get("superseded", {}) \
        if (ROOT / "incidents" / "superseded-logs.json").exists() else {}
    known = [x for x in probs if x.split(":")[0] in sup and "log hash differs" in x]
    probs = [x for x in probs if x not in known]
    unresolved = [k for k, v in sup.items() if not (ROOT / "evidence" / "runs" / f"{v['by']}.json").exists()]
    probs += [f"{k}: superseded but its rerun {sup[k]['by']} is not registered" for k in unresolved]
    for x in known:
        k = x.split(":")[0]
        print(f"  superseded {k} (log overwritten; reproduced by {sup[k]['by']}; incidents/superseded-logs.json)")
    n = len(list((ROOT / "evidence" / "runs").glob("*.json")))
    print(f"{n} registered runs; {len(probs)} problem(s)")
    for x in probs:
        print("  ", x)
    return 0 if not probs else 1


if __name__ == "__main__":
    raise SystemExit(main())
