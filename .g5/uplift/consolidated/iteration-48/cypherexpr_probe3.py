"""W55 follow-up 3: a function value in a relationship CREATE map; what is stored (raw qualifiers) and read back."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W55_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    from iris_vector_graph.engine import IRISGraphEngine
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768)
    p, T = f"i48c_{TAG}_", f"R48{TAG}"
    out = {"run": RUN, "fixture": runtime.NAME, "prefix": p, "cases": {}}
    shapes = {"literal": "'ab'", "toUpper_lit": "toUpper('ab')", "size_lit": "size('ab')", "arith": "1 + 1",
              "toString_lit": "toString(1)", "uuid": "randomUUID()", "param_fn": "toUpper($s)"}
    cur = c.cursor()
    for i, (k, expr) in enumerate(shapes.items()):
        cell = {"expr": expr}
        try:
            r = e.execute_cypher(f"CREATE (:{T}N {{id: '{p}a{i}'}})-[:{T} {{v: {expr}}}]->(:{T}N {{id: '{p}b{i}'}})", {"s": "ab"})
            cell["write_error"] = str(r.error) if getattr(r, "error", None) else None
        except Exception as x:
            cell["write_exception"] = f"{type(x).__name__}: {str(x)[:300]}"
        r = e.execute_cypher(f"MATCH (a {{id: '{p}a{i}'}})-[r:{T}]->(b) RETURN r.v, keys(r), properties(r)")
        cell["read"] = [list(x) for x in r.rows]
        cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ?", [f"{p}a{i}", T])
        cell["stored_qualifiers"] = [list(x) for x in cur.fetchall()]
        out["cases"][k] = cell
    # MATCH-then-CREATE (relationship between matched nodes) with a function value
    e.execute_cypher(f"CREATE (:{T}M {{id: '{p}m1'}}), (:{T}M {{id: '{p}m2'}})")
    cell = {}
    try:
        r = e.execute_cypher(f"MATCH (a {{id: '{p}m1'}}), (b {{id: '{p}m2'}}) CREATE (a)-[:{T} {{v: toUpper('ab')}}]->(b)")
        cell["write_error"] = str(r.error) if getattr(r, "error", None) else None
    except Exception as x:
        cell["write_exception"] = f"{type(x).__name__}: {str(x)[:300]}"
    r = e.execute_cypher(f"MATCH (a {{id: '{p}m1'}})-[r:{T}]->(b) RETURN r.v, keys(r)")
    cell["read"] = [list(x) for x in r.rows]
    cur.execute("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ?", [f"{p}m1", T])
    cell["stored_qualifiers"] = [list(x) for x in cur.fetchall()]
    out["cases"]["matched_toUpper"] = cell
    c.close()
    dest = HERE / f"cypherexpr-observed3-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
