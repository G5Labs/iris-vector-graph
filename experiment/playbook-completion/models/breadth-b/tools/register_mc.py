#!/usr/bin/env python3
"""Register every breadth-b model check of one decisive full run as its own evidence/runs/<id>.json.

    python experiment/playbook-completion/models/breadth-b/tools/register_mc.py <full-run log> [--dry-run]

The full run is `$RUN_DIR/target/breadth-b/release/breadth-b` (all modules) writing models/breadth-b/RESULTS.json and
the log given here. For each check in RESULTS.json this writes the check's own excerpt (its result line and its
counterexample, cut from the full log) to $RUN_DIR/breadth-b/mc/checks/<check>.log and registers it with
tools/register_run.py as id `b-mc-<check>`:
  kind   = control for design `control`, else mc;
  result = pass (expectation "exhaustive pass" met), expected-violation (expected violation found), fail (not met).
The full log's path and SHA-256 are attached (--extra full_log=..., full_log_sha256=...).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CRATE = HERE.parent
REPO = CRATE.parents[3]
REG = REPO / "experiment" / "playbook-completion" / "tools" / "register_run.py"


def excerpts(log: str, ids):
    lines = log.splitlines()
    starts = {}
    for i, ln in enumerate(lines):
        tok = ln.split(" ", 1)[0]
        if tok in ids and (" expect " in ln):
            starts[tok] = i
    order = sorted(starts.items(), key=lambda kv: kv[1])
    out = {}
    for k, (cid, i) in enumerate(order):
        j = order[k + 1][1] if k + 1 < len(order) else len(lines)
        body = lines[i:j]
        while body and body[-1].startswith("breadth-b model checks:"):
            body.pop()
        out[cid] = "\n".join(body).rstrip() + "\n"
    return out


def main() -> int:
    full = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv
    run_dir = Path(os.environ["RUN_DIR"]).resolve()
    data = full.read_text()
    sha = hashlib.sha256(full.read_bytes()).hexdigest()
    res = json.loads((CRATE / "RESULTS.json").read_text())["checks"]
    ids = {c["id"] for c in res}
    ex = excerpts(data, ids)
    missing = sorted(ids - set(ex))
    if missing:
        raise SystemExit(f"checks in RESULTS.json absent from the log: {missing[:5]} ...")
    outdir = run_dir / "breadth-b" / "mc" / "checks"
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in res:
        p = outdir / f"{c['id']}.log"
        p.write_text(ex[c["id"]])
        kind = "control" if c["design"] == "control" else "mc"
        if not c["met"]:
            result = "fail"
        elif c["expectation"] == "exhaustive pass":
            result = "pass"
        else:
            result = "expected-violation"
        observes = (f"module {c['module']} machine {c['machine']} design {c['design']}: expectation {c['expectation']}; "
                    f"result {c['result']}{' (found ' + repr(c['found']) + ')' if c['found'] else ''}; {c['states']} states, "
                    f"{c['transitions']} transitions, depth {c['depth']}, {c['search']} within the model's bounds; covers: {c['covers']}")
        cmd = ["python", str(REG), f"b-mc-{c['id']}", kind, result, str(p), "--lane", "breadth-b",
               "--command", "CARGO_TARGET_DIR=$RUN_DIR/target/breadth-b cargo build --release && "
                            "bash experiment/playbook-completion/tools/locks.sh heavy timeout 1800 $RUN_DIR/target/breadth-b/release/breadth-b",
               "--observes", observes,
               "--extra", f"full_log=$RUN_DIR/{full.relative_to(run_dir)}", f"full_log_sha256={sha}",
               f"check={c['id']}", f"design={c['design']}", f"module={c['module']}",
               f"search={c['search']}", f"states={c['states']}", "results=experiment/playbook-completion/models/breadth-b/RESULTS.json"]
        if dry:
            print(" ".join(cmd[:6]))
            continue
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"register failed for {c['id']}: {r.stderr or r.stdout}")
        n += 1
    print(f"registered {n} model checks from {full.name} (sha256 {sha[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
