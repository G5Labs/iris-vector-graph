#!/usr/bin/env python3
"""Trace replay runner.

    python run.py capture NN [SCENARIO ...]   # live, under tools/locks.sh iris: writes $RUN_DIR/trace-replay/NN/<s>/trace.json
    python run.py check NN [SCENARIO ...]     # offline: replay through the module's machines + controls -> report.json

A module file mNN.py defines SCENARIOS {name: fn(cap)} (each fn resets what it needs, calls cap.begin(), runs its
steps), families(trace, design) -> [Family], DESIGNS (as-built first), footprint(trace) -> {op: stores}, and EXPECT
{scenario: [(family prefix, property, finding)]}: the product findings the as-built replay is expected to reproduce.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trlib  # noqa: E402

REPLAY_RULES = {"continuity", "model-post-state", "model-not-enabled", "faithfulness", "unmapped-transaction",
                "foreign-process", "unsnapshotted-root"}


def capture(nn: str, names):
    from iris_conn import Conn, version
    mod = importlib.import_module(f"m{nn}")
    c = Conn(trlib.NS)
    print("engine:", version(c), "namespace", trlib.NS, flush=True)
    c.close()
    for name in names or list(mod.SCENARIOS):
        out = trlib.run_dir() / nn / name
        print(f"# capture {nn}/{name} -> {out}", flush=True)
        cap = trlib.Capture(f"{nn}-{name}", lambda: Conn(trlib.NS))
        t = time.time()
        try:
            mod.SCENARIOS[name](cap)
            trace = cap.end(out)
        finally:
            for fn in getattr(cap, "after", []):
                fn()
        print(f"  {len(trace['steps'])} steps, {len(trace['journal'])} journal records, {round(time.time() - t, 1)} s",
              flush=True)


def check(nn: str, names) -> int:
    mod = importlib.import_module(f"m{nn}")
    rc = 0
    for name in names or list(mod.SCENARIOS):
        d = trlib.run_dir() / nn / name
        trace = json.loads((d / "trace.json").read_text())
        fp = mod.footprint(trace)
        result = {"module": nn, "scenario": name, "trace": str(d / "trace.json"), "designs": {}}
        for design in mod.DESIGNS:
            rep = trlib.check(trace, mod.families(trace, design), fp)
            replay_viol = [v for v in rep["violations"] if v["rule"] in REPLAY_RULES]
            frame = [v for v in rep["violations"] if v["rule"] == "frame"]
            result["designs"][design] = {"replay_violations": replay_viol, "frame": frame,
                                         "invariant_violations": rep["invariant_violations"],
                                         "model_steps": rep["model_steps"], "records": rep["records"],
                                         "replay_matches_engine": rep["replay_matches_engine"],
                                         "unmapped_writes": rep["unmapped_writes"], "steps": rep["steps"]}
        ab = result["designs"][mod.DESIGNS[0]]
        result["controls"] = trlib.run_controls(trace, lambda: mod.families(trace, mod.DESIGNS[0]), fp,
                                                getattr(mod, "CONTROL_PAIRS", {}).get(name))
        expected = mod.EXPECT.get(name, [])
        found = []
        for fam, prop, finding in expected:
            hit = [v for v in ab["invariant_violations"] if v["family"].startswith(fam) and
                   (v.get("invariant") == prop or v.get("property") == prop)]
            found.append({"family": fam, "property": prop, "finding": finding, "reproduced": bool(hit),
                          "at": hit[:1]})
        result["expected_findings"] = found
        unexpected = [v for v in ab["invariant_violations"]
                      if not any(v["family"].startswith(f) and (v.get("invariant") == p or v.get("property") == p)
                                 for f, p, _ in expected)]
        result["unexpected_invariant_violations"] = unexpected
        ok = (not ab["replay_violations"] and all(c["caught"] for c in result["controls"].values())
              and all(x["reproduced"] for x in found))
        result["pass"] = ok
        (d / "report.json").write_text(json.dumps(result, indent=1, default=str))
        print(f"== {nn}/{name}: {'PASS' if ok else 'FAIL'}  records {ab['records']}, model steps {ab['model_steps']}, "
              f"replay==engine {ab['replay_matches_engine']}")
        for v in ab["replay_violations"][:12]:
            print(f"   as-built replay violation [{v['rule']}] {v['msg'][:300]}")
        for v in ab["frame"][:8]:
            print(f"   frame (declared footprint) {v['msg'][:300]}")
        for x in found:
            print(f"   expected finding {x['finding']} via '{x['property'][:70]}': "
                  f"{'REPRODUCED' if x['reproduced'] else 'NOT REPRODUCED'} {x['at'][:1]}")
        for v in unexpected[:6]:
            print(f"   other invariant violation {v}")
        for design in mod.DESIGNS[1:]:
            r = result["designs"][design]
            first = r["replay_violations"][:1]
            print(f"   design {design}: {len(r['replay_violations'])} divergences; first: "
                  f"{first[0]['msg'][:240] if first else 'none'}")
        for k, cr in result["controls"].items():
            print(f"   control {k}: {'CAUGHT' if cr['caught'] else 'NOT CAUGHT'} by {cr.get('rules_fired')} "
                  f"({cr.get('mutation', cr.get('detail'))[:160]})")
        rc |= 0 if ok else 1
    return rc


def main() -> int:
    cmd, nn, *names = sys.argv[1:]
    if cmd == "capture":
        capture(nn, names)
        return 0
    return check(nn, names)


if __name__ == "__main__":
    raise SystemExit(main())
