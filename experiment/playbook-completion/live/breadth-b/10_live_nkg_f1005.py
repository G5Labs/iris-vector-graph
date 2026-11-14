#!/usr/bin/env python3
"""Module 10 live check F-1005 with a built snapshot (rerun of the F-1005 part of 10_live_nkg.py, whose first run
synced before any edge existed, so ^NKG was unbuilt and the reader correctly fell back to ^KG).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_nkg.py

F-1005: after engine.sync() (^NKG current), an ordinary edge b10_a -> b10_b and a temporal edge b10_b -> b10_c in the
default graph. A ^KG reader (degree_centrality) sees b10_b -> b10_c; a ^NKG reader (betweenness_centrality, through
EnsureNKG) does not, and nothing marks ^NKG stale (EnsureNKG answers 1 without a rebuild; builtFrom vs the token).
After engine.sync() the ^NKG reader sees the edge.
F-1002: engine.random_walk answers [] without the Arno library although b10_a has out-edges; and the walk it would
call, Graph.KG.NKGAccel.RandomWalkJson (pure ObjectScript, deployed), steps from a default-graph node along a named
graph's edge of a node with the same id once ^NKG holds both graphs (named graph b10g1: b10_a -> b10_n).
Everything b10 is removed and engine.sync() leaves ^KG/^NKG rebuilt from the tables.
"""
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import capture, gget, session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")


def meta(s):
    return {k: gget(s.c, "$meta", k, root="NKG") for k in ("version", "builtFrom", "invalidated", "stale", "edgeCount")}


def interned(s, nid):
    return int(s.c.o.isDefined("NKG", "$NI", nid)) > 0


def main():
    log = {"steps": []}

    def step(name, **kw):
        log["steps"].append({"step": name, **kw})
        print(name, json.dumps(kw, default=str)[:600])

    with session("10-live-nkg-f1005") as s:
        eng = s.eng
        log["state_before"] = c10.state(s)
        log["cleanup_before"] = c10.cleanup_b10(s, graphs=["b10g1"])
        for n in ("b10_a", "b10_b", "b10_c"):
            eng.create_node(n, labels=["B10"])
        eng.create_edge("b10_a", "B10R", "b10_b")
        eng.sync()  # ^NKG built with b10_a -> b10_b
        m0 = meta(s)
        built = interned(s, "b10_a") and interned(s, "b10_b")
        ts = int(time.time())
        cap = capture(s, lambda: eng.create_edge_temporal("b10_b", "B10T", "b10_c", timestamp=ts))
        kg_has = int(s.c.o.isDefined("KG", "out", 0, "b10_b", "B10T", "b10_c")) > 0
        m1 = meta(s)
        tok = int(gget(s.c, "__version", root="KG") or 0)
        deg = {r.get("id", r.get("node")): r.get("degree") for r in eng.degree_centrality(direction="out")}
        ensure = s.c.call("Graph.KG.TraversalBuild", "EnsureNKG")
        m2 = meta(s)
        btw_before = eng.betweenness_centrality()
        clo_before = eng.closeness_centrality()
        step("F-1005-before-sync", nkg_built_with_ab=built, nkg_meta_after_sync=m0, temporal_write_stores=cap.stores(),
             kg_shadow_present=kg_has, nkg_interns_b10_c=interned(s, "b10_c"), nkg_meta_after_temporal=m1,
             kg_version=tok, builtFrom_lags_token=(m1.get("builtFrom") is not None and int(m1["builtFrom"]) < tok),
             ensure_nkg=ensure, nkg_meta_after_ensure=m2, degree_out=deg, betweenness=btw_before, closeness=clo_before)
        eng.sync()
        btw_after = eng.betweenness_centrality()
        clo_after = eng.closeness_centrality()
        step("F-1005-after-sync", nkg_meta=meta(s), nkg_interns_b10_c=interned(s, "b10_c"), betweenness=btw_after,
             closeness=clo_after, differs=(btw_before != btw_after or clo_before != clo_after))
        try:
            eng.delete_edge_temporal("b10_b", "B10T", "b10_c", timestamp=ts)
        except Exception as e:  # noqa: BLE001
            log["temporal_delete_error"] = repr(e)
        log["cleanup_after"] = c10.cleanup_b10(s, graphs=["b10g1"])
        eng.sync()
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        st = {x["step"]: x for x in log["steps"]}
        b = st["F-1005-before-sync"]
        log["verdict"] = {"F-1005": "reproduced" if (b["nkg_built_with_ab"] and b["kg_shadow_present"] and
                                                     not b["nkg_interns_b10_c"] and not b["nkg_meta_after_temporal"].get("stale")
                                                     and st["F-1005-after-sync"]["differs"]) else "not-reproduced"}
        p = write_log(s, log)
        print("verdict", log["verdict"], "log", p)


if __name__ == "__main__":
    main()
