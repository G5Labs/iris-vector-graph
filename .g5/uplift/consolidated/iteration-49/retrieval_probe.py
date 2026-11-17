"""W56: composed retrieval on the run-isolated continuation fixture (ordinary data, fresh i49_ prefix and graphs).

Every surface is read at its own reader: engine and IRISGraphOperators return values, the SQL procedure's rows, and
Graph.KG.PyOps class methods called through the native API. The legs each fusion reads are read separately with the
same arguments, so the binding can recompute each surface's rule from the observed legs.
Frozen predictions: retrieval-PAIRS.md."""
import json, math, os, subprocess, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W56_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
P = f"i49_{TAG}_"
G, G2, G3, GV = f"i49f{TAG}", f"i49e{TAG}", f"i49u{TAG}", f"i49v{TAG}"
K2 = f"i49k{TAG}"
out = {"run": RUN, "fixture": runtime.NAME, "prefix": P, "graphs": {"fusion": G, "text_only": G2, "unrouted": G3, "vgs": GV}, "cases": {}}


def rec(name, fn):
    try:
        out["cases"][name] = fn()
    except Exception as x:  # noqa: BLE001
        out["cases"][name] = {"exception": f"{type(x).__name__}: {str(x)[:400]}"}


def strip(rows):
    return [[r[0][len(P):] if isinstance(r[0], str) and r[0].startswith(P) else r[0]] + [round(float(v), 9) if isinstance(v, (int, float)) else v for v in r[1:]] for r in rows]


def unit(deg):
    a = math.radians(deg); return [math.cos(a), math.sin(a), 0.0, 0.0]


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.operators import IRISGraphOperators
    c = runtime.connect(); e1 = IRISGraphEngine(c, embedding_dimension=768)
    cur = c.cursor()
    q = [1.0, 0.0, 0.0, 0.0]; qs = json.dumps(q)

    # ---------- graph G: x (vector rank 1, no text), n00..n59 (vector and text, same order), L (long vector at 45 deg)
    def doc(i):
        return " ".join(["zeta"] * (60 - i) + ["pad"] * i)
    e1.create_node(P + "x", properties={"text": "unrelated words"}, graph=G); e1.store_embedding(P + "x", q, graph=G)
    for i in range(60):
        nid = P + f"n{i:02d}"
        e1.create_node(nid, properties={"text": doc(i)}, graph=G); e1.store_embedding(nid, unit(i + 1), graph=G)
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [G, nid, doc(i)])
    e1.create_node(P + "L", properties={"text": "nothing"}, graph=G); e1.store_embedding(P + "L", [10.0, 10.0, 0.0, 0.0], graph=G)
    # a second model in G with another width (multi_vector_search's failing source)
    e1.store_embedding(P + "n00", [1.0, 0.0, 0.0], graph=G, model_key=K2)
    c.commit() if hasattr(c, "commit") else None
    bname = f"i49b{TAG}"
    out["bm25_build"] = e1.bm25_build(bname, ["text"], graph=G)
    # graph G2: text only (BM25 index, no vectors)
    for i in range(3):
        e1.create_node(P + f"t{i}", properties={"text": " ".join(["zeta"] * (3 - i) + ["pad"] * i)}, graph=G2)
    out["bm25_build_g2"] = e1.bm25_build(bname + "e", ["text"], graph=G2)

    legs = {}
    rec("leg_vector_G", lambda: strip(e1.kg_KNN_VEC(qs, k=200, graph=G)))
    rec("leg_bm25_G", lambda: strip(e1.bm25_search(bname, "zeta", k=200)))
    rec("leg_txt_G", lambda: strip(e1.kg_TXT("zeta", k=200, graph=G)))
    rec("leg_index_choice_G_before_ivf", lambda: list(e1._fusion_leg_index(("ivf", "hnsw"), G)))
    rec("F1_engine", lambda: strip(e1.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="zeta", graph=G)))
    rec("F2_engine_no_c", lambda: strip(e1.kg_RRF_FUSE(100, 200, 200, query_vector=qs, query_text="zeta", graph=G)))
    ops = IRISGraphOperators(c)
    rec("F2_ops_no_c", lambda: strip(ops.kg_RRF_FUSE(k=100, query_vector=qs, query_text="zeta", graph=G)))
    rec("F3_empty_text", lambda: strip(e1.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="", graph=G)))
    rec("F4_failed_vector", lambda: strip(e1.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector="[1.0, 0.0, 0.0]", query_text="zeta", graph=G)))
    rec("F4_failed_vector_leg_alone", lambda: strip(e1.kg_KNN_VEC("[1.0, 0.0, 0.0]", k=200, graph=G)))
    rec("F4_empty_vector", lambda: strip(e1.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="zeta", graph=G2)))
    rec("F4_empty_vector_leg_alone", lambda: strip(e1.kg_KNN_VEC(qs, k=200, graph=G2)))
    rec("F4_bm25_G2", lambda: strip(e1.bm25_search(bname + "e", "zeta", k=200)))
    rec("F5_ops_default_vector", lambda: strip(ops.kg_RRF_FUSE(query_text="zeta", graph=G)))
    rec("F5_ops_real_vector", lambda: strip(ops.kg_RRF_FUSE(query_vector=qs, query_text="zeta", graph=G)))

    # ---------- F7: IVF "cosine" index built for G by e1; e1 reads it, a fresh engine (and the operators) cannot tell
    iname = f"i49i{TAG}"
    out["ivf_build"] = e1.ivf_build(iname, nlist=1, graph=G, metric="cosine")
    rec("leg_index_choice_G_after_ivf_e1", lambda: list(e1._fusion_leg_index(("ivf", "hnsw"), G)))
    rec("leg_ivf_G", lambda: strip(e1.ivf_search(iname, q, k=200, nprobe=8)))
    rec("F7_engine_building", lambda: strip(e1.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="zeta", graph=G)))
    e2 = IRISGraphEngine(c, embedding_dimension=768)
    rec("leg_index_choice_G_fresh_engine", lambda: list(e2._fusion_leg_index(("ivf", "hnsw"), G)))
    rec("F7_engine_fresh", lambda: strip(e2.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="zeta", graph=G)))
    ops2 = IRISGraphOperators(c)
    rec("F7_ops_fresh", lambda: strip(ops2.kg_RRF_FUSE(k=100, k1=200, k2=200, c=60, query_vector=qs, query_text="zeta", graph=G)))

    # ---------- PyOps through the native API
    io = e1._iris_obj()

    def da(vec):
        return io.classMethodObject("%DynamicArray", "%FromJSON", json.dumps(vec))

    def pyops(method, *args):
        r = io.classMethodValue("Graph.KG.PyOps", method, *args)
        return json.loads(r.invoke("%ToJSON")) if hasattr(r, "invoke") else r

    def pyops_obj(method, *args):
        r = io.classMethodObject("Graph.KG.PyOps", method, *args)
        return json.loads(r.invoke("%ToJSON"))

    def hyb(vec, text, k, cc, graph):
        rows = pyops_obj("HybridSearch", da(vec), text, k, cc, graph)
        return [[r["id"][len(P):] if r["id"].startswith(P) else r["id"], round(r["score"], 9), r["extras"].get("vs"), r["extras"].get("bm25")] for r in rows]

    rec("F8_pyops_hybrid_G", lambda: hyb(q, "zeta", 100, 60, G))
    rec("F8_pyops_hybrid_G_c0", lambda: hyb(q, "zeta", 100, 0, G))
    rec("Y1_vectorsearch_routed", lambda: [[r["id"][len(P):], round(r["score"], 6)] for r in pyops_obj("VectorSearch", da(q), 5, "", G)])
    rec("Y1_vectorsearch_unrouted_4", lambda: pyops_obj("VectorSearch", da(q), 5, "", G3))
    rec("Y1_vectorsearch_unrouted_768", lambda: pyops_obj("VectorSearch", da([1.0] + [0.0] * 767), 5, "", G3))
    rec("Y1_engine_knn_unrouted_4", lambda: strip(e1.kg_KNN_VEC(qs, k=5, graph=G3)))
    rec("Y1_getVectorTable", lambda: [str(io.classMethodValue("Graph.KG.PyOps", "getVectorTable", g, "")) for g in (G, G3, "")])
    rec("Y1_getExpectedDimension", lambda: [io.classMethodValue("Graph.KG.PyOps", "getExpectedDimension", g, "") for g in (G, G3, "")])

    # ---------- default graph: SQL kg_RRF_FUSE, its legs, PyOps.HybridSearch (SQL path), engine and kg_RERANK
    def v768(deg):
        a = math.radians(deg); v = [0.0] * 768; v[0], v[1] = math.cos(a), math.sin(a); return v
    q768 = v768(0); q768s = json.dumps(q768)
    e1.create_node(P + "dx", graph=None); e1.store_embedding(P + "dx", q768, graph=None)
    for i in range(30):
        nid = P + f"d{i:02d}"
        e1.create_node(nid, graph=None); e1.store_embedding(nid, v768(i + 1), graph=None)
        cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", ["", nid, " ".join(["omega"] * (30 - i) + ["pad"] * i)])
    c.commit() if hasattr(c, "commit") else None

    def sql(qry, args):
        cur.execute(qry, args); return [list(r) for r in cur.fetchall()]
    rec("F6_sql_fuse", lambda: strip(sql("SELECT id, rrf, vs, ts FROM Graph_KG.kg_RRF_FUSE(?, ?, ?, ?, ?, ?, ?)", [100, 40, 40, 60, q768s, "omega", ""])))
    rec("leg_sql_knn_default", lambda: strip(sql("SELECT node_id, score FROM Graph_KG.kg_KNN_VEC(?, ?, ?, ?)", [q768s, 40, None, ""])))
    rec("leg_sql_txt_default", lambda: strip(sql("SELECT id, score FROM Graph_KG.kg_TXT(?, ?, ?, ?)", ["omega", 40, 0, ""])))
    rec("F8_pyops_hybrid_default", lambda: hyb(q768, "omega", 100, 60, ""))
    rec("F8_sql_fuse_200", lambda: strip(sql("SELECT id, rrf, vs, ts FROM Graph_KG.kg_RRF_FUSE(?, ?, ?, ?, ?, ?, ?)", [100, 200, 200, 60, q768s, "omega", ""])))
    rec("R1_rerank", lambda: strip(e1.kg_RERANK(20, q768s, "omega")))
    rec("R1_rrf_same_args", lambda: strip(e1.kg_RRF_FUSE(k=20, k1=40, k2=40, c=60, query_vector=q768s, query_text="omega")))
    rec("R1_ops_rerank", lambda: strip(ops2.kg_RERANK(20, q768s, "omega")))
    rec("leg_engine_default_index_choice", lambda: [list(e1._fusion_leg_index(("ivf", "hnsw"), "")), list(e1._fusion_leg_index(("bm25",), ""))])

    # ---------- kg_VECTOR_GRAPH_SEARCH in GV
    vg = {"a": unit(0), "b": unit(10), "p": unit(20), "r": unit(30), "t": unit(80)}
    for n, v in vg.items():
        e1.create_node(P + n, graph=GV); e1.store_embedding(P + n, v, graph=GV)
    for n in ("n", "m", "o"):
        e1.create_node(P + n, graph=GV)
    e1.create_edge(P + "a", "REL", P + "n", qualifiers={"confidence": 600}, graph=GV)
    e1.create_edge(P + "a", "REL", P + "m", qualifiers={"confidence": 400}, graph=GV)
    e1.create_edge(P + "a", "REL", P + "o", graph=GV)
    e1.create_edge(P + "a", "REL", P + "b", qualifiers={"confidence": 900}, graph=GV)
    cur.execute("INSERT INTO Graph_KG.docs (graph_id, id, text) VALUES (?, ?, ?)", [GV, P + "t", "kappa kappa"])
    c.commit() if hasattr(c, "commit") else None

    def vgs(**kw):
        return [{"id": r["entity_id"][len(P):], "vs": round(float(r["vector_similarity"]), 6), "exp": r["in_graph_expansion"]} for r in e1.kg_VECTOR_GRAPH_SEARCH(qs, graph=GV, **kw)]
    rec("V_legs", lambda: {"knn": strip(e1.kg_KNN_VEC(qs, k=50, graph=GV)), "expansion": [[d["source"][len(P):], d["target"][len(P):], d["confidence"]] for d in e1.kg_NEIGHBORHOOD_EXPANSION([P + n for n in vg], 1, 500, graph=GV)], "txt": strip(e1.kg_TXT("kappa", k=50, graph=GV))})
    rec("V1_k2", lambda: vgs(k=2))
    rec("V1_k10", lambda: vgs(k=10))
    rec("V3_text", lambda: vgs(k=10, query_text="kappa"))
    rec("V5_wrong_width", lambda: vgs(k=10) if False else [r for r in e1.kg_VECTOR_GRAPH_SEARCH("[1.0, 0.0]", graph=GV, k=3)])
    rec("V5_empty_graph", lambda: e1.kg_VECTOR_GRAPH_SEARCH(qs, graph=G3, k=3))
    rec("V_ops_kfinal", lambda: [r["entity_id"][len(P):] for r in ops2.kg_VECTOR_GRAPH_SEARCH(qs, k=10, k_vector=2, graph=GV)])
    # V1 across interpreter hash seeds: a fresh process per seed runs the same call
    seeds = {}
    for seed in range(8):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        code = (f"import sys, json; sys.path.insert(0, {str(HERE.parent / 'iteration-36')!r}); import runtime;"
                f"from iris_vector_graph.engine import IRISGraphEngine; c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768);"
                f"r = e.kg_VECTOR_GRAPH_SEARCH({qs!r}, k=2, graph={GV!r});"
                f"print(json.dumps([[x['entity_id'][{len(P)}:], x['vector_similarity'], x['in_graph_expansion']] for x in r]))")
        p = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=120)
        seeds[seed] = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {"error": p.stderr[-300:]}
    out["cases"]["V1_k2_by_hashseed"] = seeds

    # ---------- PPR-guided subgraph and kg_PPR on the default graph: s->a, s->c, a->b, c->d
    for n in ("s", "a", "b", "c", "d"):
        e1.create_node(P + n + "p", graph=None)
    for s_, o_ in (("s", "a"), ("s", "c"), ("a", "b"), ("c", "d")):
        e1.create_edge(P + s_ + "p", "LINK", P + o_ + "p", graph=None)
    c.commit() if hasattr(c, "commit") else None
    S = P + "sp"

    def sub(r):
        return {"nodes": sorted(n[len(P):] if n.startswith(P) else n for n in r.nodes), "edges": sorted(f"{x['src'][len(P):]}>{x['dst'][len(P):]}" for x in r.edges if isinstance(x, dict)),
                "ppr": [[k_[len(P):], round(v_, 6)] for k_, v_ in r.ppr_scores]}
    for t in (1, 2, 3, 10):
        rec(f"P1_top{t}", lambda t=t: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S], ppr_top_k=t, k_hops=1)))
    rec("P1_subgraph_1hop", lambda: sorted(n[len(P):] for n in e1.kg_SUBGRAPH([S], k_hops=1).nodes))
    rec("P2_missing_seed", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([P + "nope"], ppr_top_k=3)))
    rec("P2_duplicate_seed", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S, S], ppr_top_k=3)))
    rec("P2_single_seed", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S], ppr_top_k=3)))
    rec("P2_missing_plus_real", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([P + "nope", S], ppr_top_k=3)))
    rec("P3_damping", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S], damping=1.5)))
    rec("P3_iter0", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S], max_iterations=0)))
    rec("P4_ops_topk_maxhops", lambda: sub(ops2.kg_PPR_GUIDED_SUBGRAPH([S], top_k=10, max_hops=2)))
    rec("P4_engine_same", lambda: sub(e1.kg_PPR_GUIDED_SUBGRAPH([S], ppr_top_k=10, k_hops=2)))
    rec("R2_kg_PPR", lambda: [[k_[len(P):], round(v_, 6)] for k_, v_ in e1.kg_PPR([S]) if v_ > 0])
    rec("R2_personalized_20", lambda: sorted([[k_[len(P):], round(v_, 6)] for k_, v_ in e1.kg_PERSONALIZED_PAGERANK([S], max_iterations=20).items() if v_ > 0], key=lambda x: -x[1]))
    rec("N1_mentions", lambda: [e1.kg_MENTIONS([S], predicate="LINK"), e1.kg_NEIGHBORS([S], predicate="LINK")])

    # ---------- multi_vector_search over G's route (4-wide) and G/K2's route (3-wide)
    t1 = e1.resolve_route(graph=G, model_key=None).table_name; t2 = e1.resolve_route(graph=G, model_key=K2).table_name
    out["routes"] = [t1, t2]

    def mvs(sources, fusion="rrf"):
        return [[r["id"][len(P):], r.get("score"), r.get("source_table")] for r in e1.multi_vector_search(sources, q, top_k=3, fusion=fusion, graph=G)]
    rec("M1_one_wrong_width", lambda: mvs([{"table": t1, "col": "emb", "id_col": "node_id"}, {"table": t2, "col": "emb", "id_col": "node_id"}]))
    rec("M1_both_valid", lambda: mvs([{"table": t1, "col": "emb", "id_col": "node_id", "weight": 1.0}, {"table": t1, "col": "emb", "id_col": "node_id", "weight": 2.0}]))
    rec("M2_max_weighted", lambda: mvs([{"table": t1, "col": "emb", "id_col": "node_id", "weight": 0.01}, {"table": t1, "col": "emb", "id_col": "node_id", "weight": 100.0}], fusion="max"))
    rec("M3_source_graph", lambda: mvs([{"table": t1, "col": "emb", "id_col": "node_id", "graph": G3}]))
    rec("M_all_fail", lambda: mvs([{"table": t2, "col": "emb", "id_col": "node_id"}]))

    path = HERE / f"retrieval-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path)


if __name__ == "__main__":
    main()
