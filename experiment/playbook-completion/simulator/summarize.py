#!/usr/bin/env python3
"""Aggregate the simulator's per-schedule reports into results.json.

    python summarize.py OUT_JSON RUN_SUBDIR [RUN_SUBDIR ...]
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1])
    dirs = [Path(d) for d in sys.argv[2:]]
    agg = {"schedules": 0, "operations": 0, "committed_units": 0, "journal_units": 0, "phase_seconds": 0.0,
           "wall_seconds": 0.0, "ops_by_kind": Counter(), "ok_by_kind": Counter(), "refusals": Counter(),
           "violations_by_invariant": Counter(), "violations_by_finding": Counter(), "persistent_by_invariant": Counter(),
           "transient_by_finding": Counter(), "schedules_by_template": Counter(),
           "invariant_x_finding": Counter(), "observations": Counter(), "replay_mismatch_seeds": [],
           "schedules_with_violation": Counter(), "kills": 0, "kills_mid_op": 0, "probe_schedules": 0,
           "workers": Counter(), "tenant_sets": Counter(), "quiescent_checks": 0, "verify_results": Counter(),
           "infra_errors": []}
    examples = defaultdict(list)
    for d in dirs:
        for f in sorted(d.glob("s*.report.json")):
            if f.name.startswith("shrink"):
                continue
            rep = json.loads(f.read_text())
            seed = rep.get("seed")
            agg["schedules"] += 1
            agg["operations"] += rep["ops"]
            agg["committed_units"] += rep["committed_units"]
            agg["journal_units"] += rep["units"]
            agg["wall_seconds"] += rep.get("wall_seconds", 0)
            agg["ops_by_kind"].update(rep["ops_by_kind"])
            agg["ok_by_kind"].update(rep["ok_by_kind"])
            agg["refusals"].update(rep["refusals"])
            agg["observations"].update(rep["observations"])
            agg["quiescent_checks"] += len(rep["quiescent"])
            for q in rep["quiescent"]:
                agg["verify_results"][f"{q['expected']}->{q['product']}"] += 1
            if not rep["replay_matches_engine"]:
                agg["replay_mismatch_seeds"].append(seed)
            seen_inv = set()
            for v in rep["violations"]:
                if v.get("persistent", True):
                    agg["persistent_by_invariant"][v["invariant"]] += 1
                else:
                    agg["transient_by_finding"][f"{v['invariant']}|{v['finding']}"] += 1
                agg["violations_by_invariant"][v["invariant"]] += 1
                agg["violations_by_finding"][v["finding"]] += 1
                agg["invariant_x_finding"][f"{v['invariant']}|{v['finding']}"] += 1
                seen_inv.add(v["invariant"])
                k = f"{v['invariant']}|{v['finding']}"
                if len(examples[k]) < 4:
                    examples[k].append({"seed": seed, "dir": d.name, "detail": v["detail"][:400], "why": v["why"]})
            for i in seen_inv:
                agg["schedules_with_violation"][i] += 1
            agg["kills"] += len(rep.get("kills", []))
            tr = f.with_name(f.name.replace(".report.json", ".trace.json.gz"))
            if tr.exists():
                with gzip.open(tr, "rt") as fh:
                    t = json.load(fh)
                agg["phase_seconds"] += sum(p["seconds"] for p in t["phases"])
                agg["probe_schedules"] += int(bool(t["plan"].get("probe")))
                agg["schedules_by_template"][t["plan"].get("template", "general")] += 1
                agg["workers"][str(t["plan"]["n_workers"])] += 1
                agg["tenant_sets"]["+".join(x["name"] for x in t["plan"]["tenants"])] += 1
                killed = {(str(k["w"]), k["i"], k["attempt"]) for p in t["phases"] for k in p["kills"] if k.get("pid")}
                for e in t["events"]:
                    if e.get("ev") == "op" and e.get("killed") and (str(e["w"]), e["i"], e["attempt"]) in killed:
                        agg["kills_mid_op"] += 1
        for f in sorted(d.glob("s*.infra-error.txt")):
            agg["infra_errors"].append({"seed": f.name.split(".")[0], "error": f.read_text()[:300]})
    res = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in agg.items()}
    res["phase_minutes"] = round(agg["phase_seconds"] / 60, 1)
    res["wall_minutes"] = round(agg["wall_seconds"] / 60, 1)
    res["examples"] = dict(examples)
    out.write_text(json.dumps(res, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: res[k] for k in ("schedules", "operations", "committed_units", "phase_minutes", "wall_minutes",
                                          "violations_by_invariant", "persistent_by_invariant", "violations_by_finding", "transient_by_finding", "kills", "kills_mid_op",
                                          "replay_mismatch_seeds", "verify_results")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
