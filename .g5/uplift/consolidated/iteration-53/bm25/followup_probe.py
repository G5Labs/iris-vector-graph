"""Iteration 53 W59 follow-up (after the first probe): percentile through Cypher without a list parameter (literal
UNWIND, stored values with nulls, a $p parameter over MATCH), the type of CALL ivg.bm25.search's score in Cypher
arithmetic and comparison, and bm25_search's id rewrite (F-C0715) beside the Cypher reader. USER, prefix i53s_."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[4])))
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); T = RUN[-7:-1]
P = f"i53s_{T}_"; G = f"i53sg{T}"; PROP = f"i53st{T}"


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    out = {"run": RUN, "prefix": P, "graph": G}
    def cy(q, params=None):
        try:
            r = e.execute_cypher(q, params or {})
            return {"rows": r.rows, "types": [[type(v).__name__ for v in row] for row in r.rows],
                    "error": str(r.error) if getattr(r, "error", None) else None}
        except Exception as x:
            return f"EXC {type(x).__name__}: {str(x)[:300]}"
    for p in (0.5, 0.6, 0.9, 1.0, 0.0):
        out[f"unwind_lit_{p}"] = cy(f"UNWIND [10, 20, 30, 40] AS x RETURN percentileDisc(x, {p}) AS d, percentileCont(x, {p}) AS c")
    out["unwind_lit_odd"] = cy("UNWIND [10, 20, 30] AS x RETURN percentileDisc(x, 0.5) AS d, percentileCont(x, 0.5) AS c")
    out["unwind_lit_null"] = cy("UNWIND [10, null, 30] AS x RETURN percentileDisc(x, 0.5) AS d, percentileCont(x, 0.5) AS c")
    out["unwind_lit_p95"] = cy("UNWIND [1,2,3,4,5,6,7,8,9,10] AS x RETURN percentileDisc(x, 0.95) AS d, percentileCont(x, 0.95) AS c")
    out["unwind_lit_range"] = cy("UNWIND [10, 20] AS x RETURN percentileDisc(x, 1.5) AS d")
    out["unwind_lit_floats"] = cy("UNWIND [1.5, 2.5, 3.5] AS x RETURN percentileDisc(x, 0.5) AS d")
    for i, v in enumerate([10, 20, None, 30, 40]):
        props = {} if v is None else {"v": v}
        e.create_node(f"{P}pv{i}", labels=["I53SQ"], properties=props, graph=G)
    out["match_null_0.5"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SQ) RETURN percentileDisc(n.v, 0.5) AS d, percentileCont(n.v, 0.5) AS c")
    out["match_param_0.9"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SQ) RETURN percentileDisc(n.v, $p) AS d, percentileCont(n.v, $p) AS c", {"p": 0.9})
    out["match_param_1.5"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SQ) RETURN percentileDisc(n.v, $p) AS d", {"p": 1.5})
    out["match_none"] = cy(f"USE GRAPH '{G}' MATCH (n:I53SQ) WHERE n.v > 100 RETURN percentileDisc(n.v, 0.5) AS d, percentileCont(n.v, 0.5) AS c")
    # BM25: score type in Cypher
    for d, t in {"a": "graph graph", "b": "graph database", "c:.5x": "graph"}.items():
        e.create_node(P + d, labels=["I53SB"], properties={PROP: t}, graph=G)
    name = f"i53sbf{T}"
    out["build"] = e.bm25_build(name, [PROP], graph=G)
    out["py"] = e.bm25_search(name, "graph", 5)
    base = f"USE GRAPH '{G}' CALL ivg.bm25.search('{name}', 'graph', 5) YIELD node, score "
    out["cy_score"] = cy(base + "RETURN node.node_id AS id, score")
    out["cy_score_x2"] = cy(base + "RETURN node.node_id AS id, score * 2 AS s2")
    out["cy_where"] = cy(base + "WITH node, score WHERE score > 0.3 RETURN node.node_id AS id")
    out["cy_order"] = cy(base + "RETURN node.node_id AS id ORDER BY score DESC")
    out["cy_tofloat"] = cy(base + "RETURN node.node_id AS id, toFloat(score) AS f")
    out["sql_raw"] = e._iris_obj().classMethodValue("Graph.KG.BM25Index", "Search", name, "graph", 5)
    e.bm25_drop(name)
    c.close()
    (HERE / f"followup-observed-{RUN}.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
