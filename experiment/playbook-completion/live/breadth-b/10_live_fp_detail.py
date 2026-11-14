#!/usr/bin/env python3
"""Module 10: raw journal nodes behind three footprints b-10-live-fp found outside the static declaration (AUDITB).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_fp_detail.py

1. kg_PERSONALIZED_PAGERANK wrote ^KG: which nodes?
2. engine.sync wrote Graph_KG.rdf_edges / rdf_labels storage: data rows or index globals?
3. triangle_count wrote ^IVG.Deploy, ^oddDEP, ^oddTSQL (class dictionary): which routines? Is it once per namespace?
   The wrappers' classes and ^IVG.Deploy("routines") are read, then triangle_count runs again (a second call should
   write no dictionary global once the routine record lists the wrappers).
Same fixture as 10_live_fp.py; everything b10 removed after.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, session, write_log  # noqa: E402
import journal as J  # noqa: E402

c10 = importlib.import_module("10_common")


def nodes(cap, smap, limit=40):
    out = []
    for r in cap.records:
        if not r["g"]:
            continue
        out.append({"t": r["t"], "x": r["x"], "pid": r["p"], "store": J.store_of(r["g"], smap), "g": r["g"][:160]})
    return out[:limit], len(out)


def main():
    log = {}
    with session("10-live-fp-detail") as s:
        eng = s.eng
        log["cleanup_before"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        for n in ("b10_a", "b10_b", "b10_c", "b10_d", "b10_e"):
            eng.create_node(n, labels=["B10"])
        for a, b in (("b10_a", "b10_b"), ("b10_b", "b10_c"), ("b10_c", "b10_a"), ("b10_c", "b10_d")):
            eng.create_edge(a, "B10R", b)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        cap = capture(s, lambda: eng.sync())
        log["sync"], log["sync_n"] = nodes(cap, s.smap, 60)
        log["sync_storage_globals"] = sorted({r["g"].split("(")[0] for r in cap.records if r["g"] and "rdf_" in J.store_of(r["g"], s.smap)})
        cap = capture(s, lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"]))
        log["ppr"], log["ppr_n"] = nodes(cap, s.smap)
        cap = capture(s, lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"]))
        log["ppr_second"], log["ppr_second_n"] = nodes(cap, s.smap)
        log["deploy_routines"] = str(s.c.o.get("IVG.Deploy", "routines"))[:2000] if int(s.c.o.isDefined("IVG.Deploy", "routines")) % 10 == 1 else None
        log["arno_function_classes"] = [tuple(str(x) for x in r) for r in s.c.sql(
            "SELECT Name, TimeChanged, TimeCreated FROM %Dictionary.CompiledClass WHERE Name %STARTSWITH 'Graph.KG.func' "
            "AND (Name [ 'ARNO' OR Name [ 'arno' OR Name [ 'Arno')")]
        cap = capture(s, lambda: eng.triangle_count())
        log["triangle_again"], log["triangle_again_n"] = nodes(cap, s.smap)
        log["triangle_again_error"] = cap.error
        log["cleanup_after"] = c10.cleanup_b10(s)
        eng.sync()
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        p = write_log(s, log)
        print(json.dumps({k: (v if not isinstance(v, list) else v[:12]) for k, v in log.items() if k not in ("state_after",)}, default=str)[:6000])
        print("log", p)


if __name__ == "__main__":
    main()
