#!/usr/bin/env python3
"""Module 10 live rerun of F-1006 and F-1007 with corrected fixtures (AUDITB).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 600 python experiment/playbook-completion/live/breadth-b/10_live_scope2.py

The first run (10_live_scope.py) had two invalid fixtures: kg_NodeEmbeddings has a foreign key (graph_id, node_id) to
nodes, so a named graph's vector row needs the node in that graph; and engine.create_edge does not add a parallel
edge (it keeps one edge per triple), so the multigraph fixture held no parallel edge.
F-1006: b10_s in the default graph and in named graph b10g1; a default-graph vector (engine.store_embedding) and a
        named-graph vector row (SQL INSERT, FK satisfied); kg_SUBGRAPH(["b10_s"], include_embeddings=True).
F-1007: named graph b10gm in multigraph mode; three parallel b10_p -[:B10P]-> b10_q edges made by Cypher CREATE after
        MATCH (as tests/e2e/test_234_multigraph_cypher_e2e.py:100-104 does), one b10_r -> b10_q;
        degree_centrality(direction=out/in/both, graph="b10gm").
Everything b10 is removed, multigraph mode restored, cache invalidated.
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
        print(name, json.dumps(kw, default=str)[:700])

    with session("10-live-scope2") as s:
        eng = s.eng
        log["cleanup_before"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        # F-1006
        eng.create_node("b10_s", labels=["B10"])
        eng.create_node("b10_k", labels=["B10"])
        eng.create_edge("b10_s", "B10R", "b10_k")
        eng.create_node("b10_s", graph="b10g1")
        vdef, vnamed = [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]
        eng.store_embedding("b10_s", vdef)
        try:
            ins = s.c.sql("INSERT INTO Graph_KG.kg_NodeEmbeddings (graph_id, node_id, emb) VALUES (?, ?, TO_VECTOR(?, DOUBLE))",
                          "b10g1", "b10_s", ",".join(str(x) for x in vnamed))
        except Exception as e:  # noqa: BLE001
            ins = repr(e)
        rows = s.c.sql("SELECT graph_id, node_id, emb FROM Graph_KG.kg_NodeEmbeddings WHERE node_id = 'b10_s'")
        sub = eng.kg_SUBGRAPH(["b10_s"], k_hops=1, include_embeddings=True)
        got = dict(getattr(sub, "node_embeddings", {}) or {}).get("b10_s")
        step("F-1006", named_row_insert=ins, rows=[(str(r[0]), str(r[1]), str(r[2])[:40]) for r in rows],
             subgraph_nodes=list(getattr(sub, "nodes", [])), embedding_returned=got, default_vector=vdef, named_vector=vnamed,
             reproduced=(got is not None and [round(x, 6) for x in got] == vnamed),
             both_rows_read=len(rows) == 2)
        s.c.sql("DELETE FROM Graph_KG.kg_NodeEmbeddings WHERE node_id %STARTSWITH 'b10_'")

        # F-1007
        mode_before = eng.is_multigraph("b10gm")
        eng.set_multigraph("b10gm", True)
        for n in ("b10_p", "b10_q", "b10_r"):
            eng.create_node(n, graph="b10gm")
        q = "USE GRAPH 'b10gm' MATCH (a {id: 'b10_p'}), (b {id: 'b10_q'}) CREATE (a)-[:B10P]->(b)"
        errs = []
        for _ in range(3):
            try:
                eng.execute_cypher(q)
            except Exception as e:  # noqa: BLE001
                errs.append(repr(e)[:200])
        eng.create_edge("b10_r", "B10P", "b10_q", graph="b10gm")
        nrows = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'b10gm'")[0][0]
        par = s.c.call("Graph.KG.GraphMode", "ParallelCount", "b10gm")
        deg = {}
        for d in ("out", "in", "both"):
            deg[d] = {r.get("id", r.get("node")): r.get("degree") for r in eng.degree_centrality(direction=d, graph="b10gm")}
        out_sum, in_sum = sum(deg["out"].values()), sum(deg["in"].values())
        step("F-1007", mode_before=mode_before, cypher_errors=errs, edge_rows=nrows, parallel_triples=par, degree=deg,
             out_sum=out_sum, in_sum=in_sum, reproduced=(nrows >= 4 and out_sum != in_sum))
        log["cleanup_after"] = c10.cleanup_b10(s, graphs=["b10g1", "b10gm"])
        try:
            eng.set_multigraph("b10gm", False)
        except Exception as e:  # noqa: BLE001
            log["multigraph_restore_error"] = repr(e)
        log["multigraph_after"] = eng.is_multigraph("b10gm")
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        log["verdict"] = {x["step"]: x.get("reproduced") for x in log["steps"]}
        p = write_log(s, log)
        print("verdict", log["verdict"], "log", p)


if __name__ == "__main__":
    main()
