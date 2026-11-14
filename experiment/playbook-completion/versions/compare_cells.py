#!/usr/bin/env python3
"""Compare the version lane's engine x driver cells on the same cases.

    python compare_cells.py <out.json> <cell dir> [<cell dir> ...]

Per cell: the cases whose observed outcome lies outside the contract (src/lib.rs, Semantics::default), and for every
mutant the cases that kill it, counted only over cases whose observation is inside the contract (an observation the
contract itself does not permit is usually outside every mutant's set too, which would "kill" all of them; those are
reported apart, not as kills). Across cells: the cases whose observation differs from the first cell's.
Uses the snapshot binary `iris-contract permitted <cases> [--mutant NAME]`; changes nothing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(os.environ["RUN_DIR"]) / "versions" / "bin" / "iris-contract"


def permitted(cases: Path, mutant: str | None = None) -> dict:
    cmd = [str(BIN), "permitted", str(cases)] + (["--mutant", mutant] if mutant else [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def canon(x) -> str:
    return json.dumps(x, sort_keys=True)


def main() -> int:
    out = Path(sys.argv[1])
    cells = [Path(p) for p in sys.argv[2:]]
    mutants = subprocess.run([str(BIN), "mutants"], capture_output=True, text=True, check=True).stdout.split("\n")
    mutants = [m for m in mutants if m.strip()]
    cases_file = cells[0] / "cases.json"
    for c in cells[1:]:
        assert (c / "cases.json").read_bytes() == cases_file.read_bytes(), f"{c} ran other cases"
    base = {k: {canon(o) for o in v} for k, v in permitted(cases_file).items()}
    mut = {m: {k: {canon(o) for o in v} for k, v in permitted(cases_file, m).items()} for m in mutants}
    report = {"cases_file": str(cases_file), "cells": {}, "differences_from_first": {}}
    observed = {}
    for c in cells:
        obs = json.loads((c / "observed.json").read_text())
        observed[c.name] = obs
        outside = sorted(k for k, runs in obs.items() if any(canon(r) not in base[k] for r in runs))
        kills = {}
        for m in mutants:
            kills[m] = sorted(k for k, runs in obs.items() if k not in outside
                              and any(canon(r) not in mut[m][k] for r in runs))
        head = (c / "driver.log").read_text().splitlines()
        engine = next((ln.split("engine: ", 1)[1] for ln in head if ln.startswith("engine: ")), None)
        driver = next((ln.split("driver: ", 1)[1].split(" |")[0] for ln in head if ln.startswith("driver: ")), None)
        report["cells"][c.name] = {
            "engine": engine, "driver": driver, "cases": len(obs),
            "runs": sum(len(v) for v in obs.values()),
            "outside_contract": outside,
            "mutants_killed_in_contract": {m: v for m, v in kills.items() if v},
            "mutants_not_killed_in_contract": [m for m, v in kills.items() if not v],
        }
    first = cells[0].name
    for c in cells[1:]:
        diff = sorted(k for k in observed[first] if canon(observed[first][k]) != canon(observed[c.name].get(k)))
        report["differences_from_first"][c.name] = diff
    out.write_text(json.dumps(report, indent=1))
    for name, r in report["cells"].items():
        print(f"{name}: engine {r['engine']} | driver {r['driver']} | cases {r['cases']} | outside {r['outside_contract']}"
              f" | in-contract kills {len(r['mutants_killed_in_contract'])}")
    for name, d in report["differences_from_first"].items():
        print(f"differs from {first}: {name}: {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
