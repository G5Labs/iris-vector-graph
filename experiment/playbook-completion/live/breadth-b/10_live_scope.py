#!/usr/bin/env python3
"""Module 10 live checks of graph scope on AUDITB (F-1009, F-1006, F-1007, F-1008, F-1013).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_scope.py

F-1009: khop("b10_z") for b10_z held only by named graph b10g1.
F-1006: kg_SUBGRAPH(["b10_s"], include_embeddings=True) where kg_NodeEmbeddings holds a default-graph row (engine
        store_embedding) and a named-graph row (SQL INSERT with graph_id = 'b10g1') for one id.
F-1007: named graph b10gm in multigraph mode (engine.set_multigraph, restored), three parallel b10_p -> b10_q edges:
        degree_centrality(direction="out"/"in"/"both", graph="b10gm").
F-1008: Graph.KG.VarLength.Ends (deployed class method) from b10_s, 2 hops, pAll = 1, where the default graph holds
        b10_s -> b10_k and b10g1 holds b10_k -> b10_m: an end no single graph reaches.
F-1013: Graph.KG.PageRankEmbedded.ComputePageRank("b10_%") (deployed, [Language = python]).
Everything b10 is removed (own graphs erased), multigraph mode restored, cache invalidated.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")


def main():
    log = {"steps": []}

    def step(name, **kw):
        log["steps"].append({"step": name, **kw})
        print(name, json.dumps(kw, default=str)[:600])

    with session("10-live-scope") as s:
        eng = s.eng
        log["state_before"] = c10.state(s)
        log["cleanup_before"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        # F-1009
        eng.create_node("b10_z", graph="b10g1")
        try:
            kz = eng.khop("b10_z")
        except Exception as e:  # noqa: BLE001
            kz = {"raised": repr(e)}
        kmissing = eng.khop("b10_nowhere")
        step("F-1009", khop_named_only=kz, khop_missing=kmissing,
             reproduced=(isinstance(kz, dict) and kz.get("nodes") == ["b10_z"]))

        # F-1006
        width = s.c.sql("SELECT TOP 1 1 FROM Graph_KG.kg_NodeEmbeddings")
        eng.create_node("b10_s", labels=["B10"])
        eng.create_node("b10_k", labels=["B10"])
        eng.create_edge("b10_s", "B10R", "b10_k")
        dim = getattr(eng, "embedding_dimension", None) or 4
        vdef = [1.0] + [0.0] * (int(dim) - 1)
        vnamed = [0.0] * (int(dim) - 1) + [1.0]
        try:
            eng.store_embedding("b10_s", vdef)
            stored_default = True
        except Exception as e:  # noqa: BLE001
            stored_default = repr(e)
        ins = None
        try:
            ins = s.c.sql("INSERT INTO Graph_KG.kg_NodeEmbeddings (graph_id, node_id, emb) VALUES (?, ?, TO_VECTOR(?, DOUBLE))",
                          "b10g1", "b10_s", ",".join(str(x) for x in vnamed))
        except Exception as e:  # noqa: BLE001
            ins = repr(e)
        rows = s.c.sql("SELECT graph_id, node_id, emb FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = 'b10_s'")
        try:
            sub = eng.kg_SUBGRAPH(["b10_s"], k_hops=1, include_embeddings=True)
            emb = dict(getattr(sub, "node_embeddings", {}) or {})
            sub = {"nodes": list(getattr(sub, "nodes", [])), "node_embeddings": emb}
        except Exception as e:  # noqa: BLE001
            sub, emb = {"raised": repr(e)}, None
        got = emb.get("b10_s") if isinstance(emb, dict) else None
        step("F-1006", dim=dim, stored_default=stored_default, named_row_insert=ins,
             rows=[(str(r[0]), str(r[1]), str(r[2])[:60]) for r in rows], subgraph_keys=list(sub.keys()) if isinstance(sub, dict) else None,
             embedding_returned=got, default_vector=vdef, named_vector=vnamed,
             reproduced=(got is not None and [round(x, 6) for x in got] == vnamed))
        s.c.sql("DELETE FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'b10_' AND graph_id = 'b10g1'")

        # F-1008: VarLength every-graph mode across graphs sharing b10_k
        eng.create_node("b10_k", graph="b10g1")
        eng.create_node("b10_m", graph="b10g1")
        eng.create_edge("b10_k", "B10R", "b10_m", graph="b10g1")
        ends_all = json.loads(str(s.c.call("Graph.KG.VarLength", "Ends", "b10_s", "", "out", 2, 2, 1, "")))
        ends_def = json.loads(str(s.c.call("Graph.KG.VarLength", "Ends", "b10_s", "", "out", 2, 2, 0, "")))
        step("F-1008", ends_every_graph_mode=ends_all, ends_default_graph=ends_def,
             reproduced=any(e.get("t") == "b10_m" for e in ends_all))

        # F-1007: parallel edges in a multigraph-mode named graph
        mode_before = eng.is_multigraph("b10gm") if hasattr(eng, "is_multigraph") else None
        eng.set_multigraph("b10gm", True)
        for n in ("b10_p", "b10_q", "b10_r"):
            eng.create_node(n, graph="b10gm")
        for _ in range(3):
            eng.create_edge("b10_p", "B10P", "b10_q", graph="b10gm")
        eng.create_edge("b10_r", "B10P", "b10_q", graph="b10gm")
        nrows = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'b10gm'")[0][0]
        deg = {}
        for d in ("out", "in", "both"):
            try:
                deg[d] = {r.get("id", r.get("node")): r.get("degree") for r in eng.degree_centrality(direction=d, graph="b10gm")}
            except Exception as e:  # noqa: BLE001
                deg[d] = repr(e)
        out_sum = sum(v for v in deg["out"].values()) if isinstance(deg["out"], dict) else None
        in_sum = sum(v for v in deg["in"].values()) if isinstance(deg["in"], dict) else None
        step("F-1007", mode_before=mode_before, edge_rows=nrows, degree=deg, out_sum=out_sum, in_sum=in_sum,
             reproduced=(out_sum is not None and in_sum is not None and out_sum != in_sum))

        # F-1013: PageRankEmbedded over unqualified tables, no graph predicate
        try:
            o = s.c.o.classMethodObject("Graph.KG.PageRankEmbedded", "ComputePageRank", "b10_%", 5, 0.85, "", 0, 1.0)
            pre = json.loads(str(o.invoke("%ToJSON")))
        except Exception as e:  # noqa: BLE001
            pre = {"raised": f"{type(e).__name__}: {e}"[:500]}
        step("F-1013", answer=pre)

        # cleanup
        log["cleanup_after"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        try:
            eng.set_multigraph("b10gm", False)
        except Exception as e:  # noqa: BLE001
            log["multigraph_restore_error"] = repr(e)
        log["multigraph_after"] = eng.is_multigraph("b10gm") if hasattr(eng, "is_multigraph") else None
        s.c.sql("DELETE FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'b10_'")
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        log["verdict"] = {x["step"]: x.get("reproduced") for x in log["steps"]}
        p = write_log(s, log)
        print("verdict", log["verdict"], "log", p)


if __name__ == "__main__":
    main()
