"""Iteration 53 W59 probe: BM25 scores and ranks (bm25_search, kg_BM25, CALL ivg.bm25.search), query-time IDF after
incremental writes vs a fresh build, and percentileDisc/percentileCont through Cypher and the SQL functions. Fixture
ivg-cont-20261117-iris, namespace USER, fresh graph and property prefix i53s_<time>. Raw answers only; expectations are
in bm25-percentile-PAIRS.md (frozen first).

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/bm25/bm25_percentile_probe.py)
"""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[4])))
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[-7:-1]
P = f"i53s_{T}_"; G = f"i53sg{T}"; PROP = f"i53st{T}"
CORPUS = {"d1": "graph database graph", "d2": "vector database", "d3": "The graph of things",
          "d4": "state-of-the-art graph", "d5": "über vector", "d6": "vector database"}


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    out = {"run": RUN, "prefix": P, "graph": G}

    def obs(k, f):
        try: out[k] = f()
        except Exception as x: out[k] = f"EXC {type(x).__name__}: {str(x)[:300]}"

    for d, t in CORPUS.items():
        e.create_node(P + d, labels=["I53S"], properties={PROP: t}, graph=G)
    name = f"i53sbm{T}"; name7 = name + "x"; name_wo1 = name + "y"
    obs("build", lambda: e.bm25_build(name, [PROP], graph=G))
    q = lambda n, s, k=10, **kw: e.bm25_search(n, s, k, **kw)
    strip = lambda r: [(i[len(P):], s) for i, s in r] if isinstance(r, list) else r
    for key, s in [("graph", "graph"), ("Graph!", "Graph!"), ("the", "the"), ("things", "things"), ("über", "über"),
                   ("uber", "uber"), ("state art", "state art"), ("state-of-the-art", "state-of-the-art"),
                   ("vector", "vector"), ("zzz graph", "zzz graph"), ("graph graph", "graph graph"),
                   ("graph things", "graph things")]:
        obs(f"B1:{key}", lambda s=s: strip(q(name, s)))
    obs("B1e:vector_k2", lambda: strip(q(name, "vector", 2)))
    obs("B1f:cut0.4", lambda: (lambda r: {**r, "results": strip(r["results"])})(q(name, "graph things", max_df_fraction=0.4, report=True)))
    obs("B1g:graph_cut0.4", lambda: (lambda r: {**r, "results": strip(r["results"])})(q(name, "graph", max_df_fraction=0.4, report=True)))
    obs("B1i:k0", lambda: strip(q(name, "graph", 0)))
    obs("B1i:k1", lambda: strip(q(name, "graph", 1)))
    # B3: SQL and Cypher readers
    cur = c.cursor()
    def sql_bm25(k):
        cur.execute(f"SELECT {e._ivg_schema}.kg_BM25(?, ?, ?)", [name, "graph", k]); raw = cur.fetchone()[0]
        return raw
    obs("B3a:kg_BM25_k3", lambda: sql_bm25(3))
    obs("B3a:kg_BM25_k10", lambda: sql_bm25(10))
    obs("B3b:cypher", lambda: [[r[0][len(P):] if isinstance(r[0], str) else r[0], r[1]] for r in
                               e.execute_cypher(f"USE GRAPH '{G}' CALL ivg.bm25.search('{name}', 'graph', 3) YIELD node, score "
                                                "RETURN node.node_id AS id, score").rows])
    obs("B3b:cypher_nograph", lambda: e.execute_cypher(f"CALL ivg.bm25.search('{name}', 'graph', 3) YIELD node, score RETURN node, score").rows)
    # B2: incremental vs fresh build
    obs("B2a:insert", lambda: e.bm25_insert(name, P + "d7", "graph"))
    obs("B2a:incremental", lambda: strip(q(name, "graph")))
    e.create_node(P + "d7", labels=["I53S"], properties={PROP: "graph"}, graph=G)
    obs("B2a:fresh_build", lambda: (e.bm25_build(name7, [PROP], graph=G), strip(q(name7, "graph")))[1])
    obs("B2b:delete", lambda: e.bm25_delete(name, P + "d1"))
    obs("B2b:incremental", lambda: strip(q(name, "graph")))
    obs("B2b:info_after", lambda: e.bm25_info(name))
    # fresh build without d1 and d7: a second graph holding d2..d6
    G2 = G + "b"
    for d, t in CORPUS.items():
        if d != "d1": e.create_node(P + d, labels=["I53S"], properties={PROP: t}, graph=G2)
    e.create_node(P + "d7", labels=["I53S"], properties={PROP: "graph"}, graph=G2)
    obs("B2b:fresh_build", lambda: (e.bm25_build(name_wo1, [PROP], graph=G2), strip(q(name_wo1, "graph")))[1])
    # P1: percentiles, Cypher over UNWIND and the SQL functions
    def cy(xs, p):
        r = e.execute_cypher("UNWIND $xs AS x RETURN percentileDisc(x, $p) AS d, percentileCont(x, $p) AS c", {"xs": xs, "p": p})
        return {"rows": r.rows, "error": str(r.error) if getattr(r, "error", None) else None,
                "types": [[type(v).__name__ for v in row] for row in r.rows]}
    def sqlp(xs, p):
        res = {}
        for proc in ("PDISC", "PCONT"):
            try:
                cur.execute(f"SELECT {e._ivg_schema}.Percentile_{proc}(?, ?)", [json.dumps(xs), p]); res[proc] = cur.fetchone()[0]
            except Exception as x:
                res[proc] = f"EXC {str(x)[:200]}"
        return res
    cases = {"P1a_even_0.5": ([10, 20, 30, 40], 0.5), "P1a_odd_0.5": ([10, 20, 30], 0.5),
             "P1b_0.6": ([10, 20, 30, 40], 0.6), "P1b_0.9": ([10, 20, 30, 40], 0.9),
             "P1b_0.25": ([10, 20, 30, 40], 0.25), "P1b_0.75": ([10, 20, 30, 40], 0.75),
             "P1c_0": ([30, 10, 20, 40], 0.0), "P1c_1": ([30, 10, 20, 40], 1.0),
             "P1d_null": ([10, None, 30], 0.5), "P1d_allnull": ([None, None], 0.5), "P1d_empty": ([], 0.5),
             "P1e_1.5": ([10, 20], 1.5), "P1e_neg": ([10, 20], -0.1),
             "P1f_dups": ([10, 10, 20, 30], 0.5), "P1g_ints": ([1, 2, 3], 0.5), "P1g_floats": ([1.5, 2.5, 3.5], 0.5),
             "Px_p95_10": (list(range(1, 11)), 0.95), "Px_neg": ([-5, 3, -1], 0.5)}
    for k, (xs, p) in cases.items():
        obs(f"{k}:cypher", lambda xs=xs, p=p: cy(xs, p))
        obs(f"{k}:sql", lambda xs=[x for x in xs if x is not None], p=p: sqlp(xs, p))
    # stored property path: MATCH over node properties
    for i, v in enumerate([10, 20, 30, 40]):
        e.create_node(f"{P}pv{i}", labels=["I53SP"], properties={"v": v}, graph=G)
    obs("P1_match_0.9", lambda: e.execute_cypher(f"USE GRAPH '{G}' MATCH (n:I53SP) RETURN percentileDisc(n.v, 0.9) AS d, percentileCont(n.v, 0.9) AS c").rows)
    obs("P1_match_0.6", lambda: e.execute_cypher(f"USE GRAPH '{G}' MATCH (n:I53SP) RETURN percentileDisc(n.v, 0.6) AS d, percentileCont(n.v, 0.6) AS c").rows)
    for n_ in (name, name7, name_wo1):
        try: e.bm25_drop(n_)
        except Exception: pass
    c.close()
    path = HERE / f"bm25-percentile-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
