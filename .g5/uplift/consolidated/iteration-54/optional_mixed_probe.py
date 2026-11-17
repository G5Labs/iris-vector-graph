"""Follow-up to optional_where_probe: a WHERE inside OPTIONAL MATCH that reads both a variable bound before it and one
it introduces. Prediction (openCypher, query.optional): one row per a, b null where no match passes. Neighbors: the
same condition under a plain MATCH (drops a's without a passing match), and the same test as a WITH ... WHERE after the
OPTIONAL MATCH (drops null rows). API-written and Cypher-written data. Records the emitted SQL. Fresh tag; USER."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()); TAG = RUN[-7:-1]
P = f"i54x_{TAG}_"; A = f"I54X{TAG}"; C = f"I54XC{TAG}"; K = f"KX{TAG}"
CONDS = {"plus": "b.v = a.v + 1", "gt": "b.v > a.v", "and_split": "a.v = 1 AND b.v = 2", "ne_names": "b.name <> a.name",
         "eq_props": "b.v = a.v", "or_mixed": "a.v = 1 OR b.v = 5", "id_cmp": "b.name STARTS WITH a.name"}
def main():
    from iris_vector_graph.cypher.parser import parse_query
    from iris_vector_graph.cypher.translator import translate_to_sql
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "product": runtime.PRODUCT}
    e.create_node(P + "a1", labels=[A], properties={"name": "a1", "v": 1})
    e.create_node(P + "a2", labels=[A], properties={"name": "a2", "v": 2})
    e.create_node(P + "a3", labels=[A], properties={"name": "a3"})
    e.create_edge(P + "a1", K, P + "a2"); e.create_edge(P + "a2", K, P + "a3")
    e.execute_cypher(f"CREATE (:{C} {{id: '{P}c1', name: 'a1', v: 1}}), (:{C} {{id: '{P}c2', name: 'a2', v: 2}}), (:{C} {{id: '{P}c3', name: 'a3'}})")
    e.execute_cypher(f"MATCH (a:{C} {{name: 'a1'}}), (b:{C} {{name: 'a2'}}) CREATE (a)-[:{K}]->(b)")
    e.execute_cypher(f"MATCH (a:{C} {{name: 'a2'}}), (b:{C} {{name: 'a3'}}) CREATE (a)-[:{K}]->(b)")
    def run(key, q):
        rec = {"q": q}
        try:
            r = e.execute_cypher(q); rec["rows"] = [list(x) for x in r.rows]; rec["error"] = str(r.error)[:300] if getattr(r, "error", None) else None
        except Exception as x:
            rec["error"] = f"{type(x).__name__}: {x}"[:300]
        try:
            s = translate_to_sql(parse_query(q), {}); rec["sql"] = (s.sql if isinstance(s.sql, str) else "\n".join(s.sql))[-1500:]
        except Exception as x:
            rec["sql"] = f"translate error {x}"
        out[key] = rec
    for lbl, L in (("api", A), ("cypher", C)):
        for k, cond in CONDS.items():
            run(f"{lbl}_opt_{k}", f"MATCH (a:{L}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE {cond} RETURN a.name, b.name ORDER BY a.name")
        run(f"{lbl}_match_plus", f"MATCH (a:{L}) MATCH (a)-[:{K}]->(b) WHERE b.v = a.v + 1 RETURN a.name, b.name ORDER BY a.name")
        run(f"{lbl}_with_after_plus", f"MATCH (a:{L}) OPTIONAL MATCH (a)-[:{K}]->(b) WITH a, b WHERE b.v = a.v + 1 RETURN a.name, b.name ORDER BY a.name")
        run(f"{lbl}_opt_count", f"MATCH (a:{L}) OPTIONAL MATCH (a)-[:{K}]->(b) WHERE b.v = a.v + 1 RETURN count(*)")
    c.close()
    p = HERE / f"optional-mixed-observed-{RUN}.json"; p.write_text(json.dumps(out, indent=1) + "\n"); print(p)
if __name__ == "__main__":
    main()
