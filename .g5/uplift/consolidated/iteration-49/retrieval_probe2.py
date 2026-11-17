"""W56 follow-up 2: multi_vector_search with schema-qualified route tables (the first run passed resolve_route's bare
names, which the generic helper resolves in SQLUser), a text-only node kept out of kg_VECTOR_GRAPH_SEARCH's vector
leg, and kg_SUBGRAPH's node cap read directly (kg_PPR_GUIDED_SUBGRAPH caps it at ppr_top_k). Reuses the graphs of the
first run, named by W56_BASE (its run id)."""
import json, math, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

BASE = os.environ["W56_BASE"]; BT = BASE[-7:-1]
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i49_{BT}_"; G, G3 = f"i49f{BT}", f"i49u{BT}"; K2 = f"i49k{BT}"
P2 = f"i49_{TAG}_"; GW = f"i49w{TAG}"
out = {"run": RUN, "base": BASE, "fixture": runtime.NAME, "cases": {}}


def rec(name, fn):
    try:
        out["cases"][name] = fn()
    except Exception as x:  # noqa: BLE001
        out["cases"][name] = {"exception": f"{type(x).__name__}: {str(x)[:400]}"}


def unit(deg):
    a = math.radians(deg); return [math.cos(a), math.sin(a), 0.0, 0.0]


def short(i):
    return i[len(P):] if i.startswith(P) else (i[len(P2):] if i.startswith(P2) else i)


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768); cur = c.cursor()
    q = [1.0, 0.0, 0.0, 0.0]; qs = json.dumps(q)
    t1 = "Graph_KG." + e.resolve_route(graph=G, model_key=None).table_name
    t2 = "Graph_KG." + e.resolve_route(graph=G, model_key=K2).table_name
    out["routes"] = [t1, t2]

    def mvs(sources, fusion="rrf", top_k=3, graph=G):
        return [[short(str(r["id"])), r.get("score"), r.get("rank"), r.get("source_table")] for r in e.multi_vector_search(sources, q, top_k=top_k, fusion=fusion, graph=graph)]
    src = lambda w=1.0, **kw: dict({"table": t1, "col": "emb", "id_col": "node_id", "weight": w}, **kw)  # noqa: E731
    rec("M_leg_t1", lambda: [[short(str(r["id"])), r["score"]] for r in e.vector_search(t1, "emb", q, top_k=6, id_col="node_id", graph=G)])
    rec("M_leg_t2", lambda: [[short(str(r["id"])), r["score"]] for r in e.vector_search(t2, "emb", q, top_k=6, id_col="node_id", graph=G)])
    rec("M1_one_wrong_width", lambda: mvs([src(), dict(src(), table=t2)]))
    rec("M1_valid_only", lambda: mvs([src()]))
    rec("M1_both_valid_weights", lambda: mvs([src(1.0), src(2.0)]))
    rec("M2_max_low_high", lambda: mvs([src(0.01), src(100.0)], fusion="max"))
    rec("M2_max_single", lambda: mvs([src(1.0)], fusion="max"))
    rec("M3_source_graph_other", lambda: mvs([src(graph=G3)]))
    rec("M3_source_graph_none_call_graph", lambda: mvs([src()], graph=None))
    rec("M_all_fail", lambda: mvs([dict(src(), table=t2)]))

    # kg_VECTOR_GRAPH_SEARCH: t found only by text (vector rank 7 > k_vector = 6 for k = 3)
    vg = {"a": 0, "b": 5, "c": 10, "d": 15, "f": 20, "g": 25, "t": 80}
    for n, deg in vg.items():
        e.create_node(P2 + n, graph=GW); e.store_embedding(P2 + n, unit(deg), graph=GW)
    cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [GW, P2 + "t", "kappa kappa"])
    rec("V3_legs", lambda: {"knn6": [[short(i), round(s, 6)] for i, s in e.kg_KNN_VEC(qs, k=6, graph=GW)], "txt": [[short(i), s] for i, s in e.kg_TXT("kappa", k=12, graph=GW)]})
    rec("V3_k3_text", lambda: [{"id": short(r["entity_id"]), "vs": round(float(r["vector_similarity"]), 6), "exp": r["in_graph_expansion"]} for r in e.kg_VECTOR_GRAPH_SEARCH(qs, query_text="kappa", k=3, graph=GW)])
    rec("V3_k10_text", lambda: [{"id": short(r["entity_id"]), "vs": round(float(r["vector_similarity"]), 6), "exp": r["in_graph_expansion"]} for r in e.kg_VECTOR_GRAPH_SEARCH(qs, query_text="kappa", k=10, graph=GW)])

    # kg_SUBGRAPH's cap on the default-graph chain of the first run: s->a, s->c, a->b, c->d
    S = P + "sp"

    def sg(seeds, hops, cap):
        r = e.kg_SUBGRAPH(seeds, k_hops=hops, max_nodes=cap)
        return {"nodes": sorted(short(n) for n in r.nodes), "edges": sorted(f"{short(s)}>{short(o)}" for s, p, o in r.edges)}
    for cap in (1, 2, 3, 4, 5, 100):
        rec(f"S_cap{cap}_1hop", lambda cap=cap: sg([S], 1, cap))
        rec(f"S_cap{cap}_2hop", lambda cap=cap: sg([S], 2, cap))
    rec("S_seeds3_cap3", lambda: sg([S, P + "ap", P + "cp"], 1, 3))
    out["store"] = type(e._store).__name__
    path = HERE / f"retrieval-observed2-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)


if __name__ == "__main__":
    main()
