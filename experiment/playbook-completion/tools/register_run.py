#!/usr/bin/env python3
"""Record one run of the completion audit as evidence/runs/<id>.json.

    register_run.py <id> <kind> <result> <log> --lane L --command "..." --observes "..." [--extra k=v ...]

kind:   mc | proof | control | live | probe | run | check | trace | review
result: pass | fail | expected-violation | incomplete | blocked
        expected-violation: an as-built model or a control produced the violation it is meant to produce.
        fail: the product or a check failed its oracle. blocked: a dependency was unavailable (say which in --observes).

One file per run, so parallel lanes never write the same file. The log stays under $RUN_DIR; the record keeps its
path relative to $RUN_DIR, its SHA-256 and size, and the product tree it ran against. A run is attributable only if
the product tree is the pin's tree; this script refuses to register otherwise.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parent.parent
PIN = "3eaa79cf77d3e0a879b2cced634cf2729d81499e"
PIN_TREE = "b098a6f48a379ce86ee2e5ae9ad0d37994dea567"
KINDS = ["mc", "proof", "control", "live", "probe", "run", "check", "trace", "review"]
RESULTS = ["pass", "fail", "expected-violation", "incomplete", "blocked"]


def product_matches_pin() -> bool:
    r = subprocess.run(["bash", str(HERE.parent / "check-product-scope.sh")], cwd=REPO,
                       capture_output=True, text=True)
    return r.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("result", choices=RESULTS)
    ap.add_argument("log")
    ap.add_argument("--lane", required=True)
    ap.add_argument("--command", required=True)
    ap.add_argument("--observes", required=True)
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    if not product_matches_pin():
        raise SystemExit("product tree differs from the pin: refusing to register")
    run_dir = Path(os.environ["RUN_DIR"]).resolve()
    log = Path(a.log).resolve()
    data = log.read_bytes()
    entry = {
        "id": a.id, "lane": a.lane, "kind": a.kind, "result": a.result,
        "command": a.command, "observes": a.observes,
        "log": "$RUN_DIR/" + str(log.relative_to(run_dir)),
        "log_sha256": hashlib.sha256(data).hexdigest(), "log_bytes": len(data),
        "product_pin": PIN, "product_tree": PIN_TREE,
        "experiment_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                                          text=True).stdout.strip(),
        "registered_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    for kv in a.extra:
        k, _, v = kv.partition("=")
        entry[k] = v
    out = ROOT / "evidence" / "runs" / f"{a.id}.json"
    out.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n")
    print(f"registered {a.id}: {a.kind} {a.result} {entry['log']} {entry['log_sha256'][:12]}")


if __name__ == "__main__":
    main()
