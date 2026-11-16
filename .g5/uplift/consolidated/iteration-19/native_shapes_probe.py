"""W20: anchored read shapes answered by the native executor and by the SQL path (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W20_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def rows(r):
    return None if r is None else {"rows": [list(x) for x in r.rows], "error": str(r.error) if getattr(r, "error", None) else None, "columns": list(r.columns)}
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    A = f"ns{RUN}A"; R = f"NSR{RUN}"
    e.create_node(A, labels=["NS"])
    vals = ["s", 7, 2.5, True, ["x", 1], None]
    T = []
    for i, v in enumerate(vals):
        t = f"ns{RUN}t{i}"; T.append(t)
        e.create_node(t, labels=["NSL"] if i % 2 == 0 else ["NSM"], properties={} if v is None else {"p": v})
        e.create_edge(A, R, t, qualifiers={"w": 0.5 + i})
    e.create_edge(T[3], R, A); e.create_edge(T[0], R, T[1])
    qs = {
        "out": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.id, b.p",
        "in": f"MATCH (x {{id: '{A}'}})<-[:{R}]-(b) RETURN b.id",
        "undirected": f"MATCH (x {{id: '{A}'}})-[:{R}]-(b) RETURN b.id",
        "rel_prop": f"MATCH (x {{id: '{A}'}})-[r:{R}]->(b) RETURN b.id, r.w",
        "label": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b:NSL) RETURN b.id",
        "str_prop": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b {{p: 's'}}) RETURN b.id",
        "count": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN count(b), count(*)",
        "distinct": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN DISTINCT b.p",
        "two_hops": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b)-[:{R}]->(c) RETURN c.id",
        "order_limit": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.p ORDER BY b.p LIMIT 3",
        "order_skip": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.id ORDER BY b.id SKIP 2 LIMIT 2",
        "order_desc": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.p ORDER BY b.p DESC",
        "node_value": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b",
        "labels": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.id, labels(b)",
        "keys": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.id, keys(b)",
        "where_id": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) WHERE b.id = '{T[2]}' RETURN b.p",
    }
    out = {"run": RUN, "fixture": runtime.NAME, "queries": {}}
    for name, q in qs.items():
        try:
            nat = e._try_native(parse_query(q), {})
        except Exception as x:
            nat = None; nerr = f"{type(x).__name__}: {x}"
        else:
            nerr = None
        sql = e._execute_parsed_sql(parse_query(q), {}, None)
        n, s = rows(nat[1]) if nat else None, rows(sql)
        ordered = "ORDER BY" in q
        same = None if n is None else ((n["rows"] == s["rows"]) if ordered else (sorted(map(json.dumps, n["rows"])) == sorted(map(json.dumps, s["rows"]))))
        out["queries"][name] = {"query": q, "native_routed": nat is not None, "native_exception": nerr, "native": n, "sql": s, "equal": same}
    c.close()
    path = HERE / f"native-shapes-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, x in out["queries"].items():
        tag = "SQL-ONLY" if not x["native_routed"] else ("equal" if x["equal"] else "DIFF")
        print(f"{k:12s} {tag:8s}", "" if x["equal"] in (None, True) else (x["native"]["rows"], x["sql"]["rows"]))
if __name__ == "__main__":
    main()
