#!/usr/bin/env python3
"""Add or replace one entry of experiment/playbook-uplift/evidence/runs.json.

    register_run.py <id> <kind> <result> <log> --command "..." --observes "..." [--extra key=value ...]

kind is run | live | mc. The log stays under $RUN_DIR; the registry keeps its path relative to $RUN_DIR and its
SHA-256, so a reader can confirm the log they hold is the one the claim rests on.
"""
import argparse, hashlib, json, os
from pathlib import Path

REG = Path(__file__).resolve().parent.parent / "evidence" / "runs.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id"); ap.add_argument("kind", choices=["run", "live", "mc"])
    ap.add_argument("result", choices=["pass", "fail", "incomplete"]); ap.add_argument("log")
    ap.add_argument("--command", required=True); ap.add_argument("--observes", required=True)
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    log = Path(a.log).resolve()
    run_dir = Path(os.environ["RUN_DIR"]).resolve()
    reg = json.loads(REG.read_text()) if REG.exists() else {"runs": {}}
    entry = {"kind": a.kind, "result": a.result, "command": a.command, "observes": a.observes,
             "log": "$RUN_DIR/" + str(log.relative_to(run_dir)),
             "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    for kv in a.extra:
        k, _, v = kv.partition("=")
        entry[k] = v
    reg.setdefault("runs", {})[a.id] = entry
    REG.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    print(f"registered {a.id}: {a.kind} {a.result} {entry['log']}")


if __name__ == "__main__":
    main()
