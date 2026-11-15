#!/usr/bin/env python3
"""Module 10 footprint validation with the journal oracle (AUDITB).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 python experiment/playbook-completion/live/breadth-b/10_live_fp.py

Fixture (default graph): b10_a -> b10_b -> b10_c -> b10_a, b10_c -> b10_d, edgeless b10_e; engine.sync() first.
Each entry point runs between two journal marks (blive.capture); the stores written per process (journal footprint
over the namespace's storage map) are compared with the DECLARED persistent write set: the static source closure of
the entry point (inventory/10.json `hint`, globals/tables written, excluding process-private ^|| globals, which IRIS
does not journal, and IRISTEMP ^IRIS.Temp.*). An observed store outside the declared set is `undeclared`.
Writes outside a transaction are listed; module 10's readers claim no atomic write (ALG-I6: a read algorithm changes
no content, it may write only its own work areas and caches).
"""
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import REPO, capture, session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")
INV = json.loads((REPO / "experiment/playbook-completion/models/breadth-b/inventory/10.json").read_text())
HINT = {e["id"]: e.get("hint", {}) for e in INV["entry_points"]}


def declared(ep):
    h = HINT.get(ep, {})
    g = set(h.get("globals_written", [])) | set(h.get("globals_killed", []))
    g = {x for x in g if not x.startswith("^||") and not x.startswith("^IRIS.Temp")}
    t = set(h.get("tables_written", []))
    return sorted({"global:" + x for x in g} | {"sql:Graph_KG." + x for x in t})


def main():
    log = {"entries": []}
    with session("10-live-fp") as s:
        eng = s.eng
        # also clear what an interrupted earlier run may have left (own named graphs, multigraph mode of b10gm)
        log["cleanup_before"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        try:
            if eng.is_multigraph("b10gm"):
                eng.set_multigraph("b10gm", False)
        except Exception as e:  # noqa: BLE001
            log["multigraph_restore_error"] = repr(e)
        s.c.sql("DELETE FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'b10_'")
        for n in ("b10_a", "b10_b", "b10_c", "b10_d", "b10_e"):
            eng.create_node(n, labels=["B10"])
        for a, b in (("b10_a", "b10_b"), ("b10_b", "b10_c"), ("b10_c", "b10_a"), ("b10_c", "b10_d")):
            eng.create_edge(a, "B10R", b)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        runs = [
            ("eng:IRISGraphEngine.sync", lambda: eng.sync()),
            ("eng:IRISGraphEngine.kg_PAGERANK", lambda: eng.kg_PAGERANK()),
            ("eng:IRISGraphEngine.kg_PAGERANK#hit", lambda: eng.kg_PAGERANK()),
            ("eng:IRISGraphEngine.kg_PERSONALIZED_PAGERANK", lambda: eng.kg_PERSONALIZED_PAGERANK(["b10_a"])),
            ("eng:IRISGraphEngine.kg_WCC", lambda: eng.kg_WCC()),
            ("eng:IRISGraphEngine.kg_CDLP", lambda: eng.kg_CDLP()),
            ("eng:IRISGraphEngine.degree_centrality", lambda: eng.degree_centrality()),
            ("eng:IRISGraphEngine.betweenness_centrality", lambda: eng.betweenness_centrality()),
            ("eng:IRISGraphEngine.closeness_centrality", lambda: eng.closeness_centrality()),
            ("eng:IRISGraphEngine.eigenvector_centrality", lambda: eng.eigenvector_centrality()),
            ("eng:IRISGraphEngine.khop", lambda: eng.khop("b10_a")),
            ("eng:IRISGraphEngine.random_walk", lambda: eng.random_walk("b10_a")),
            ("eng:IRISGraphEngine.kg_SUBGRAPH", lambda: eng.kg_SUBGRAPH(["b10_a"], k_hops=2)),
            ("eng:IRISGraphEngine.kg_GRAPH_WALK", lambda: eng.kg_GRAPH_WALK("b10_a", max_depth=2)),
            ("eng:IRISGraphEngine.triangle_count", lambda: eng.triangle_count()),
            ("eng:IRISGraphEngine.strongly_connected_components", lambda: eng.strongly_connected_components()),
            ("eng:IRISGraphEngine.k_core", lambda: eng.k_core()),
            ("eng:IRISGraphEngine.leiden_communities", lambda: eng.leiden_communities()),
        ]
        for ep, op in runs:
            base = ep.split("#")[0]
            cap = capture(s, op)
            obs = cap.stores()
            dec = declared(base)
            if ep.endswith("#hit"):
                dec = [x for x in dec if x != "global:^IVG.AlgoCache"]
            rec = {"id": ep, "error": cap.error, "seconds": round(cap.seconds, 3), "declared_stores": dec,
                   "observed_stores": obs, "undeclared": sorted(set(obs) - set(dec)),
                   "declared_not_observed": sorted(set(dec) - set(obs)), "match": set(obs) <= set(dec),
                   "records": len(cap.records), "outside_txn": len(cap.writes_outside_txn(s.smap)),
                   "outside_txn_stores": sorted({w["store"] for w in cap.writes_outside_txn(s.smap)}),
                   "txns": cap.txn_summary(s.smap)[:6],
                   "result_preview": json.dumps(cap.result, default=str)[:200]}
            log["entries"].append(rec)
            print(ep, "obs", obs, "undeclared", rec["undeclared"], "err", cap.error)
        log["cleanup_after"] = c10.cleanup_b10(s)
        eng.sync()
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        log["summary"] = {"entries": len(log["entries"]), "match": sum(1 for e in log["entries"] if e["match"]),
                          "errors": [e["id"] for e in log["entries"] if e["error"]]}
        p = write_log(s, log)
        print("summary", log["summary"], "log", p)


if __name__ == "__main__":
    main()
