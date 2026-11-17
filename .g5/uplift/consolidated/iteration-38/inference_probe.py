"""W44: materialize_inference / retract_inference on frozen shapes (run-isolated continuation fixture; ordinary data).
Readers: rdf_edges rows (qualifiers), ^KG adjacency, and a Cypher MATCH on the subject."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W44_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
SUB = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
SUBP = "http://www.w3.org/2000/01/rdf-schema#subPropertyOf"
TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
DOM = "http://www.w3.org/2000/01/rdf-schema#domain"
RNG = "http://www.w3.org/2000/01/rdf-schema#range"
SHORT = {SUB: "subClassOf", SUBP: "subPropertyOf", TYPE: "type", DOM: "domain", RNG: "range"}


def main():
    import iris
    c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c)
    from iris_vector_graph._validate import graph_index_key  # noqa: F401
    out = {"run": RUN, "fixture": runtime.NAME, "multigraph_default": e.is_multigraph(""), "cases": {}}

    def setup(q, triples, graph=None):
        for s, p, o in triples:
            for n in (s, o):
                if not e.get_node(q + n) if graph is None else not e.node_exists(q + n, graph=graph):
                    e.create_node(q + n, graph=graph)
            e.create_edge(q + s, p if p in SHORT else q + p, q + o, graph=graph)

    def rows(q, graph=None):
        cur = c.cursor()
        sql = (f"SELECT s, p, o_id, qualifiers FROM {e._ivg_schema}.rdf_edges WHERE s %STARTSWITH ? AND "
               + ("graph_id = ?" if graph else "COALESCE(graph_id, '') = ''"))
        cur.execute(sql, [q] + ([graph] if graph else []))
        res = sorted((s[len(q):], SHORT.get(p, p[len(q):] if p.startswith(q) else p), o[len(q):], "inferred" if qu and '"inferred"' in qu else "asserted")
                     for s, p, o, qu in cur.fetchall())
        cur.close()
        return [list(r) for r in res]

    def kg(q, s, p, o, graph=None):
        from iris_vector_graph._validate import graph_index_key
        return bool(nat.isDefined("^KG", "out", graph_index_key(graph), q + s, p if p in SHORT else q + p, q + o))

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    # I1/I2: subclass chain and a typed instance
    q1 = f"i{TAG}a_"
    setup(q1, [("A", SUB, "B"), ("B", SUB, "C"), ("x", TYPE, "A")])
    case("I1_materialize", lambda: {"answer": e.materialize_inference(), "rows": rows(q1)})
    case("I2_second_run", lambda: {"answer": e.materialize_inference(), "rows": rows(q1)})
    case("I1_cypher_types_of_x", lambda: sorted(r[0] for r in e.execute_cypher(
        "MATCH (a {node_id: $x})-[r]->(b) RETURN b.node_id", {"x": q1 + "x"}).rows))

    # I3: asserted before materializing
    q3 = f"i{TAG}c_"
    setup(q3, [("A", SUB, "B"), ("x", TYPE, "A"), ("x", TYPE, "B")])
    case("I3_materialize", lambda: {"answer": e.materialize_inference(), "rows": rows(q3)})
    # I4: asserted after materializing
    q4 = f"i{TAG}d_"
    setup(q4, [("A", SUB, "B"), ("x", TYPE, "A")])
    case("I4_materialize_then_assert", lambda: {"answer": e.materialize_inference(),
                                                "create_edge_returned": e.create_edge(q4 + "x", TYPE, q4 + "B"),
                                                "rows": rows(q4)})
    # I7/I8/I10
    q7 = f"i{TAG}p_"
    setup(q7, [("p", SUBP, "q"), ("x", "p", "y"), ("p", DOM, "D"), ("p", RNG, "R"), ("D", SUB, "E")])
    case("I7_I8_I10_materialize", lambda: {"answer": e.materialize_inference(), "rows": rows(q7)})

    # I5/I6: named graph
    G = f"ig{TAG}"; q5 = f"i{TAG}g_"
    setup(q5, [("A", SUB, "B"), ("x", TYPE, "A")], graph=G)
    setup(q5, [("A", SUB, "B"), ("x", TYPE, "A")])
    case("I5_materialize_named", lambda: {"answer": e.materialize_inference(graph=G), "named": rows(q5, G), "default": rows(q5)})

    # retract: default graph, then named graph
    def retract_default():
        n = e.retract_inference()
        return {"answer": n, "I1": rows(q1), "I3": rows(q3), "I4": rows(q4), "I7": rows(q7), "I5_named": rows(q5, G),
                "kg": {"I1 x type B": kg(q1, "x", TYPE, "B"), "I3 x type B": kg(q3, "x", TYPE, "B"),
                       "I4 x type B": kg(q4, "x", TYPE, "B"), "I1 x type A": kg(q1, "x", TYPE, "A")}}
    case("I9_retract_default", retract_default)
    case("I6_retract_named", lambda: {"answer": e.retract_inference(graph=G), "named": rows(q5, G), "default": rows(q5)})

    dest = HERE / f"inference-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
