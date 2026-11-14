#!/usr/bin/env python3
"""Write the registered logs: logs/tr-replay-NN.log (run.py check output), logs/tr-controls-NN.log (each scenario's
three seeded defects and the rules that flagged them), logs/tr-locklog-NN.log (lockcheck output).

    python make_logs.py replay NN ... | locklog NN ...
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trlib  # noqa: E402

HERE = Path(__file__).resolve().parent
LOGS = trlib.run_dir() / "logs"


def run(cmd):
    r = subprocess.run([sys.executable, "-I"] + cmd, cwd=HERE, capture_output=True, text=True)
    return r.returncode, "\n".join(line for line in (r.stdout + r.stderr).splitlines()
                                   if not line.startswith("WARNING:root"))


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    what, mods = sys.argv[1], sys.argv[2:]
    for nn in mods:
        if what == "replay":
            rc, out = run(["run.py", "check", nn])
            (LOGS / f"tr-replay-{nn}.log").write_text(f"$ python -I run.py check {nn}   (exit {rc})\n{out}\n")
            ctl = {}
            for rep in sorted((trlib.run_dir() / nn).glob("*/report.json")):
                r = json.loads(rep.read_text())
                ctl[r["scenario"]] = r["controls"]
            (LOGS / f"tr-controls-{nn}.log").write_text(json.dumps(ctl, indent=1) + "\n")
            print(nn, "replay exit", rc)
        else:
            rc, out = run(["lockcheck.py", nn])
            raw = trlib.run_dir() / "locklog" / f"{nn}.json"
            (LOGS / f"tr-locklog-{nn}.log").write_text(f"$ python -I lockcheck.py {nn}   (exit {rc}; raw log {raw})\n{out}\n")
            print(nn, "lockcheck exit", rc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
