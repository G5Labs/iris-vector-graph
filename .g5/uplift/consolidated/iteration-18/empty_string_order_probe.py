"""W19b: ORDER BY with an empty-string property, native executor vs SQL path (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-15"))
import runtime  # noqa: E402
RUN = os.environ.get("W19B_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
def rows(r): return None if r is None else {"rows": [list(x) for x in r.rows], "error": str(r.error) if getattr(r, "error", None) else None}
def main():
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.cypher.parser import parse_query
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    a = f"eo{RUN}a"; rel = f"EOR{RUN}"
    e.create_node(a, labels=["EO"])
    values = ["", "b", 2, None, "a", 1]
    for i, v in enumerate(values):
        t = f"eo{RUN}t{i}"
        e.create_node(t, labels=["EOT"], properties={} if v is None else {"p": v})
        e.create_edge(a, rel, t)
    cur = c.cursor(); cur.execute("SELECT s, val, LENGTH(val), ASCII(val) FROM Graph_KG.rdf_props WHERE s %STARTSWITH ? AND \"key\" = 'p'", [f"eo{RUN}t"]); raw = [list(r) for r in cur.fetchall()]; cur.close()
    out = {"run": RUN, "fixture": runtime.NAME, "values": [repr(v) for v in values], "raw_rdf_props": raw, "queries": {}}
    for q in [f"MATCH (x {{id: '{a}'}})-[:{rel}]->(b) RETURN b.p ORDER BY b.p", f"MATCH (x {{id: '{a}'}})-[:{rel}]->(b) RETURN b.p ORDER BY b.p DESC"]:
        nat = e._try_native(parse_query(q), {})
        sql = e._execute_parsed_sql(parse_query(q), {}, None)
        pub = e.execute_cypher(q)
        out["queries"][q] = {"native_routed": nat is not None, "native": rows(nat[1]) if nat else None, "sql": rows(sql), "execute_cypher": rows(pub)}
    c.close()
    path = HERE / f"empty-string-order-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    print("raw", raw)
    for q, x in out["queries"].items():
        print(q[-14:], "native" if x["native_routed"] else "NOT-NATIVE", [r[0] for r in (x["native"] or {"rows": []})["rows"]], "sql", [r[0] for r in x["sql"]["rows"]], "public", [r[0] for r in x["execute_cypher"]["rows"]])
if __name__ == "__main__":
    main()
