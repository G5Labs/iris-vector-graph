"""W20b: empty-string property in count/DISTINCT/plain projection, native vs SQL (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W20B_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def rows(r): return None if r is None else [list(x) for x in r.rows]
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    A = f"ea{RUN}A"; R = f"EAR{RUN}"
    e.create_node(A, labels=["EA"])
    for i, v in enumerate(["", "s", None]):
        t = f"ea{RUN}t{i}"; e.create_node(t, labels=["EAT"], properties={} if v is None else {"p": v}); e.create_edge(A, R, t)
    out = {"run": RUN, "fixture": runtime.NAME, "queries": {}}
    for name, q in {"count_p": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN count(b.p)",
                    "distinct": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN DISTINCT b.p",
                    "plain": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN b.p",
                    "count_all": f"MATCH (x {{id: '{A}'}})-[:{R}]->(b) RETURN count(*)"}.items():
        nat = e._try_native(parse_query(q), {}); sql = e._execute_parsed_sql(parse_query(q), {}, None); pub = e.execute_cypher(q)
        out["queries"][name] = {"query": q, "native_routed": nat is not None, "native": rows(nat[1]) if nat else None, "sql": rows(sql), "execute_cypher": rows(pub)}
    c.close()
    path = HERE / f"empty-string-aggregate-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, x in out["queries"].items():
        print(f"{k:10s}", "native" if x["native_routed"] else "SQL-ONLY", "native=", x["native"], "sql=", x["sql"], "public=", x["execute_cypher"])
if __name__ == "__main__":
    main()
