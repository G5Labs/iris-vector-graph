"""W51: export_rdf_from_cypher and namespace prefixes (run-isolated continuation fixture; files under $W51_FILES)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W51_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
FILES = Path(os.environ.get("W51_FILES", "/tmp")) / f"w51-{RUN}"


def main():
    import rdflib
    FILES.mkdir(parents=True, exist_ok=True)
    c = runtime.connect(); e = runtime.engine(c); o = runtime.connect(); O = runtime.engine(o)
    out = {"run": RUN, "fixture": runtime.NAME, "files": str(FILES), "cases": {}}
    p = f"cx{TAG}_"; L = f"CXD{TAG}"; R = f"INH{TAG}"

    def trip(path):
        g = rdflib.Graph().parse(str(path)); return sorted([str(s), str(pp), str(oo)] for s, pp, oo in g)

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    e.create_node(p + "d1", labels=[L], properties={"yr": 2011, "zero": 0}); e.create_node(p + "d2", labels=[L], properties={"yr": 1999, "zero": 0})
    e.create_node(p + "t"); e.create_edge(p + "d1", R, p + "t"); e.create_edge(p + "d2", R, p + "t")
    q = f"MATCH (d:{L})-[r]->(t) RETURN d.node_id AS s, type(r) AS p, t.node_id AS o"
    case("C1_spo", lambda: {"answer": e.export_rdf_from_cypher(q, str(FILES / "c1.nt"))["triples"], "file": trip(FILES / "c1.nt")})
    case("C2_positional", lambda: {"answer": e.export_rdf_from_cypher(f"MATCH (d:{L})-[r]->(t) RETURN d.node_id AS a, type(r) AS b, t.node_id AS c", str(FILES / "c2.nt"))["triples"]})
    case("C3_number_object", lambda: trip(FILES / "c3.nt") if e.export_rdf_from_cypher(f"MATCH (d:{L}) RETURN d.node_id AS s, 'yr' AS p, d.yr AS o", str(FILES / "c3.nt")) else None)
    case("C11_zero_positional_vs_named", lambda: {"named": e.export_rdf_from_cypher(f"MATCH (d:{L}) RETURN d.node_id AS s, 'zero' AS p, d.zero AS o", str(FILES / "c11a.nt"))["triples"],
                                                  "positional": e.export_rdf_from_cypher(f"MATCH (d:{L}) RETURN d.node_id AS a, 'zero' AS b, d.zero AS c", str(FILES / "c11b.nt"))["triples"]})
    case("C4_one_column", lambda: trip(FILES / "c4.nt") if e.export_rdf_from_cypher(f"UNWIND ['http://x.org/{TAG}', 'plain{TAG}'] AS v RETURN v", str(FILES / "c4.nt")) is not None else None)
    case("C5_duplicate_rows", lambda: e.export_rdf_from_cypher(f"UNWIND [1, 2] AS k MATCH (d {{node_id: '{p}d1'}})-[r]->(t) RETURN d.node_id AS s, type(r) AS p, t.node_id AS o", str(FILES / "c5.nt"))["triples"])
    case("C6_null", lambda: e.export_rdf_from_cypher(f"MATCH (d:{L}) OPTIONAL MATCH (d)-[r:NOPE{TAG}]->(x) RETURN d.node_id AS s, 'q' AS p, x.node_id AS o", str(FILES / "c6.nt"))["triples"])
    # C10 (source-informed): a query IRIS refuses at run time (a mapped label through an IVG relationship, bug-cyp-109)
    def c10():
        cur = c.cursor(); S = f"W51x{TAG}"
        cur.execute(f"CREATE TABLE {S}.T (id VARCHAR(50) PRIMARY KEY)"); cur.execute(f"INSERT INTO {S}.T (id) VALUES ('m1')"); c.commit()
        e.map_sql_table(f"{S}.T", "id", f"CXM{TAG}", [])
        r = e.execute_cypher(f"MATCH (m:CXM{TAG})-[r]->(x) RETURN m.id AS s, type(r) AS p, x.node_id AS o")
        ans = e.export_rdf_from_cypher(f"MATCH (m:CXM{TAG})-[r]->(x) RETURN m.id AS s, type(r) AS p, x.node_id AS o", str(FILES / "c10.nt"))
        return {"query_error": bool(r.error), "export_answer": ans["triples"], "file_bytes": (FILES / "c10.nt").stat().st_size}
    case("C10_failed_query", c10)
    pf, uri = f"ex{TAG}", f"http://example.org/{TAG}/"
    case("C7_register", lambda: (e.register_namespace(pf, uri), {"this": e.list_namespaces().get(pf), "other_engine": O.list_namespaces().get(pf)})[1])
    case("C8_reregister", lambda: (e.register_namespace(pf, uri + "v2/"), e.list_namespaces().get(pf))[1])
    def c9():
        f = FILES / "c9.ttl"; e.export_rdf(str(f), node_ids=[p + "d1"]); txt = f.read_text()
        return {"prefix_declared": f"@prefix {pf}:" in txt}
    case("C9_prefix_in_turtle", c9)
    dest = HERE / f"cyphexport-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
