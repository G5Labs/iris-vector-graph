#!/usr/bin/env python3
"""One line per scenario from the replay reports, and per lock log from locklog/NN.json (for TRACE-REPLAY.md).

    python summarize.py [NN ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trlib  # noqa: E402


def replay_lines(nn: str):
    base = trlib.run_dir() / nn
    for rep in sorted(base.glob("*/report.json")):
        r = json.loads(rep.read_text())
        ab = r["designs"][next(iter(r["designs"]))]
        others = {d: len(v["replay_violations"]) for d, v in r["designs"].items() if d != next(iter(r["designs"]))}
        steps = sum(ab["model_steps"].values())
        txns = sum(len(s["txns"]) for s in ab["steps"])
        found = [f"{x['finding']}:{'yes' if x['reproduced'] else 'NO'}" for x in r["expected_findings"]]
        ctl = {k: (v["caught"], v.get("rules_fired")) for k, v in r["controls"].items()}
        yield (f"{nn}/{r['scenario']}: {'PASS' if r['pass'] else 'FAIL'}; steps {len(ab['steps'])}, records "
               f"{ab['records']}, txns {txns}, model actions {steps}; replay==engine {ab['replay_matches_engine']}; "
               f"replay violations {len(ab['replay_violations'])}; frame {len(ab['frame'])}; findings {found}; "
               f"other designs divergences {others}; controls {ctl}")


def lock_lines(nn: str):
    p = trlib.run_dir() / "locklog" / f"{nn}.json"
    if not p.exists():
        return
    r = json.loads(p.read_text())
    for k, w in r["workloads"].items():
        yield f"{nn} workload {k}: {w['work'] if 'receipt' not in str(w['work']) else 'redaction'}; {w['summary']}"
    for k, pr in r["probes"].items():
        yield (f"{nn} probe {k}: waited={pr['waited']} at={pr['wait_at']} held={pr['held_while_waiting']} "
               f"x={pr['x']} records_before_release={len(pr['x_records_before_release'])}")


def main() -> int:
    mods = sys.argv[1:] or sorted(p.name for p in trlib.run_dir().iterdir() if p.is_dir() and p.name.isdigit())
    for nn in mods:
        for line in replay_lines(nn):
            print(line)
        for line in lock_lines(nn) or []:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
