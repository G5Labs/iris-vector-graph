"""W46: SQL table mappings through Cypher (run-isolated continuation fixture; fixture-only SQL tables in schema W46x<run>)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("W46_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]


def main():
    c = runtime.connect(); e = runtime.engine(c)
    o = runtime.connect(); O = runtime.engine(o)         # a second engine, as another process or the HTTP server would hold
    out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    S = f"W46x{TAG}"; L, LT = f"MDrug{TAG}", f"MTarget{TAG}"
    cur = c.cursor()
    cur.execute(f"CREATE TABLE {S}.Drug (id VARCHAR(50) PRIMARY KEY, name VARCHAR(50), yr INTEGER)")
    cur.execute(f"CREATE TABLE {S}.Target (id VARCHAR(50) PRIMARY KEY, drug_id VARCHAR(50))")
    cur.execute(f"CREATE TABLE W46Plain{TAG} (id VARCHAR(50) PRIMARY KEY, name VARCHAR(50))")
    for r in [("d1", "aspirin", 1899), ("d2", "imatinib", 2001), ("d3", "crizotinib", 2011)]:
        cur.execute(f"INSERT INTO {S}.Drug (id, name, yr) VALUES (?, ?, ?)", list(r))
    for r in [("t1", "d1"), ("t2", "d3")]:
        cur.execute(f"INSERT INTO {S}.Target (id, drug_id) VALUES (?, ?)", list(r))
    cur.execute(f"INSERT INTO W46Plain{TAG} (id, name) VALUES ('p1', 'plain')")
    c.commit()

    def rows(eng, q, params=None):
        r = eng.execute_cypher(q, params or {})
        if getattr(r, "error", None):
            return "ERROR " + str(r.error)[:300]
        return sorted([list(x) for x in r.rows], key=str)

    def case(k, fn):
        try:
            out["cases"][k] = fn()
        except Exception:
            out["cases"][k] = "RAISED " + traceback.format_exc().strip().splitlines()[-1][:400]

    e.create_node(f"own{TAG}", labels=[L], properties={"name": "ivg-own"})
    q = f"MATCH (n:{L}) RETURN n.id, n.name, n.yr"
    case("T2_before_mapping_engine_A", lambda: rows(e, q))
    case("T9_before_mapping_engine_B", lambda: rows(O, q))     # loads engine B's mapping cache
    nodes_before = O.get_node_count() if hasattr(O, "get_node_count") else None
    case("T1_map", lambda: e.map_sql_table(f"{S}.Drug", "id", L, ["name", "yr"]))
    case("T1_T2_after_mapping_engine_A", lambda: rows(e, q))
    case("T1_node_count_unchanged", lambda: {"before": nodes_before, "after": O.get_node_count() if nodes_before is not None else None})
    case("T9_after_mapping_engine_B_no_reload", lambda: rows(O, q))
    case("T8_where_integer", lambda: rows(e, f"MATCH (n:{L}) WHERE n.yr = 2011 RETURN n.id"))
    case("T8b_where_param_integer", lambda: rows(e, f"MATCH (n:{L}) WHERE n.yr = $y RETURN n.id", {"y": 2011}))
    case("T7_use_graph", lambda: rows(e, f"USE GRAPH 'g{TAG}' MATCH (n:{L}) RETURN n.id"))
    case("T4_map_rel", lambda: (e.map_sql_table(f"{S}.Target", "id", LT, []),
                                e.map_sql_relationship(LT, "OF", L, target_fk="drug_id"))[1])
    case("T4_rel_rows", lambda: rows(e, f"MATCH (t:{LT})-[:OF]->(d:{L}) RETURN t.id, d.id"))
    case("T6_khop_from_mapped", lambda: e.khop("t1", hops=2))
    case("T6_varlength_from_mapped", lambda: rows(e, f"MATCH (t:{LT} {{id: 't1'}})-[:OF*1..2]->(d) RETURN d.id"))
    case("T0_unqualified_table", lambda: e.map_sql_table(f"W46Plain{TAG}", "id", f"MPlain{TAG}", ["name"]))
    case("T5_T3_remove", lambda: (e.remove_table_mapping(L), {"mappings": [m.get("label") for m in e.list_table_mappings()["nodes"]] + [
        (m.get("source_label"), m.get("predicate"), m.get("target_label")) for m in e.list_table_mappings()["relationships"]]})[1])
    case("T3_after_remove_engine_A", lambda: rows(e, q))
    case("T3_table_untouched", lambda: (cur.execute(f"SELECT COUNT(*) FROM {S}.Drug"), cur.fetchone()[0])[1])
    case("T5_rel_after_remove", lambda: rows(e, f"MATCH (t:{LT})-[:OF]->(d) RETURN t.id, d.id"))
    case("T9_after_remove_engine_B_no_reload", lambda: rows(O, q))
    case("T9_engine_B_after_reload", lambda: (O.reload_table_mappings(), rows(O, q))[1])

    dest = HERE / f"sqlmap-observed-{RUN}.json"
    dest.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
