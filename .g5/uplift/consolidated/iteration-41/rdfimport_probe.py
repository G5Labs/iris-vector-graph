"""W47: import_rdf from fixture RDF files (generated per run under the run directory) into the graph readers
(run-isolated continuation fixture; ordinary data)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W47_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
OUT = Path(os.environ.get("W47_FILES", "/tmp")) / f"w47-{RUN}"
SUB = "http://www.w3.org/2000/01/rdf-schema#subClassOf"; TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = runtime.connect(); e = runtime.engine(c)
    out = {"run": RUN, "fixture": runtime.NAME, "files": str(OUT), "cases": {}}
    x = f"http://ex.org/w47{TAG}/"
    T, H = f"trials{TAG}", f"http://example.org/g{TAG}"
    (OUT / "ctx.nq").write_text(
        f"<{x}s1> <{x}rel> <{x}o1> <urn:ivg:graph:{T}> .\n"
        f"<{x}s2> <{x}rel> <{x}o2> <{H}> .\n"
        f"<{x}A> <{SUB}> <{x}B> <urn:ivg:graph:{T}> .\n"
        f"<{x}i> <{TYPE}> <{x}A> <urn:ivg:graph:{T}> .\n")
    (OUT / "lit.ttl").write_text(
        f"<{x}s> <{x}knows> <{x}o> .\n<{x}s> <http://a.org/name> \"x\" .\n<{x}s> <http://b.org#name> \"y\" .\n"
        f"<{x}s> <{x}yrInt> \"2011\"^^<http://www.w3.org/2001/XMLSchema#integer> .\n<{x}s> <{x}yrStr> \"2011\" .\n"
        f"<{x}s> <{x}flag> \"true\"^^<http://www.w3.org/2001/XMLSchema#boolean> .\n")
    (OUT / "v1.ttl").write_text(f"<{x}u> <{x}label> \"first\" .\n<{x}u> <{x}knows> <{x}w> .\n")
    (OUT / "v2.ttl").write_text(f"<{x}u> <{x}label> \"second\" .\n<{x}u> <{x}knows> <{x}w> .\n")

    def node(i, graph=None):
        n = e.get_node(x + i, graph=graph) if graph is not None else e.get_node(x + i)
        return None if n is None else {k: v for k, v in n.items() if k not in ("id",)}

    def edges(graph, s):
        cur = c.cursor()
        cur.execute(f"SELECT p, o_id, qualifiers FROM {e._ivg_schema}.rdf_edges WHERE s = ? AND COALESCE(graph_id, '') = ?", [x + s, graph or ""])
        r = sorted([p.replace(x, ""), o.replace(x, ""), q] for p, o, q in cur.fetchall()); cur.close(); return r

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    case("R1_R2_R10_import_nq_infer", lambda: e.import_rdf(str(OUT / "ctx.nq"), infer=True))
    case("R1_trials_graph", lambda: {"s1": node("s1", T), "edges": edges(T, "s1"), "default_s1": node("s1", "")})
    case("R2_iri_graph", lambda: {"s2": node("s2", H), "edges": edges(H, "s2")})
    case("R10_inference_where", lambda: {"trials_i_types": edges(T, "i"), "default_i_types": edges("", "i")})
    case("R3_R4_R5_import_lit", lambda: e.import_rdf(str(OUT / "lit.ttl")))
    case("R3_R4_R5_node", lambda: {"node": node("s"), "edges": edges("", "s")})
    G6 = f"tg{TAG}"
    case("R6_import_graph_arg", lambda: e.import_rdf(str(OUT / "v1.ttl"), graph=G6))
    case("R6_node", lambda: {"named": node("u", G6), "default": node("u", "")})
    case("R7_reimport_same", lambda: e.import_rdf(str(OUT / "v1.ttl"), graph=G6))
    case("R7_edges_after", lambda: edges(G6, "u"))
    case("R9_import_changed", lambda: e.import_rdf(str(OUT / "v2.ttl"), graph=G6))
    case("R9_node_after", lambda: node("u", G6))
    case("R9_cypher_after", lambda: [list(r) for r in e.execute_cypher(f"USE GRAPH '{G6}' MATCH (n {{node_id: $u}}) RETURN n.label", {"u": x + "u"}).rows])

    dest = HERE / f"rdfimport-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
