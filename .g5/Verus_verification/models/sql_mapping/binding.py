"""sql_mapping binding: fresh fixture-only SQL tables on the run-isolated continuation fixture (ivg-cont-20261117-iris),
through the actual map_sql_table / map_sql_relationship / remove_table_mapping / reload_table_mappings and Cypher on two
engines; observed outcome classes compared with a port of sql_mapping.rs. Mutations mirror the controls."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("SM_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["join_on_source_fk", "unmapped_rel_translated", "unqualified_checks_sqluser", "caches_shared", "mapping_ignored"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def label_source(cache_has_mapping, m):
    return "Table" if cache_has_mapping and not m.get("mapping_ignored") else "IvgNodes"


def cache_current(made_last, reloaded, first_after, m):
    return True if m.get("caches_shared") else (made_last or reloaded or first_after)


def joined(s_id, s_fk, t_id, t_fk, m):
    return (s_fk == t_id) if m.get("join_on_source_fk") else (t_fk == s_id)


def pattern_outcome(source, rel, m):
    return "SqlError" if source == "Table" and rel == "Unmapped" and not m.get("unmapped_rel_translated") else "Rows"


def accepted(qualified, schema, actual, m):
    checked = schema if qualified else ("SQLUser" if m.get("unqualified_checks_sqluser") else "USER")
    return checked == actual


def main():
    t0 = time.time()
    c = runtime.connect(); A = runtime.engine(c); o = runtime.connect(); B = runtime.engine(o)
    S = f"W46b{TAG}"; L, LT, LS = f"BD{TAG}", f"BT{TAG}", f"BS{TAG}"
    cur = c.cursor()
    cur.execute(f"CREATE TABLE {S}.Drug (id VARCHAR(50) PRIMARY KEY, name VARCHAR(50))")
    cur.execute(f"CREATE TABLE {S}.Target (id VARCHAR(50) PRIMARY KEY, drug_id VARCHAR(50))")
    cur.execute(f"CREATE TABLE {S}.Src (id VARCHAR(50) PRIMARY KEY, target_id VARCHAR(50))")
    cur.execute(f"CREATE TABLE BPlain{TAG} (id VARCHAR(50) PRIMARY KEY)")
    for sql, args in [(f"INSERT INTO {S}.Drug (id, name) VALUES (?, ?)", ["d1", "a"]), (f"INSERT INTO {S}.Target (id, drug_id) VALUES (?, ?)", ["t1", "d1"]),
                      (f"INSERT INTO {S}.Src (id, target_id) VALUES (?, ?)", ["s1", "t1"]), (f"INSERT INTO BPlain{TAG} (id) VALUES (?)", ["p1"])]:
        cur.execute(sql, args)
    c.commit()
    A.create_node(f"own{TAG}", labels=[L])
    q = f"MATCH (n:{L}) RETURN n.id"

    def src_of(eng):
        r = eng.execute_cypher(q)
        ids = {x[0] for x in r.rows}
        return "Table" if "d1" in ids else ("IvgNodes" if f"own{TAG}" in ids else "Neither")

    def outcome(eng, query):
        r = eng.execute_cypher(query)
        return "SqlError" if r.error else "Rows"

    got = {}
    src_of(B)                                                    # B loads its cache before the mapping exists
    A.map_sql_table(f"{S}.Drug", "id", L, ["name"])
    got["A_after_map"] = src_of(A); got["B_after_map_no_reload"] = src_of(B)
    A.map_sql_table(f"{S}.Target", "id", LT, []); A.map_sql_table(f"{S}.Src", "id", LS, [])
    A.map_sql_relationship(L, "HAS", LT, target_fk="drug_id")    # key on the target table (as built)
    A.map_sql_relationship(LS, "TO", LT, target_fk="target_id")  # key on the source table (as documented)
    r = A.execute_cypher(f"MATCH (a:{L})-[:HAS]->(b:{LT}) RETURN a.id, b.id"); got["join_key_on_target"] = sorted(map(list, r.rows)) if not r.error else "SqlError"
    r = A.execute_cypher(f"MATCH (a:{LS})-[:TO]->(b:{LT}) RETURN a.id, b.id"); got["join_key_on_source"] = sorted(map(list, r.rows)) if not r.error else "SqlError"
    A.create_node(f"x{TAG}"); A.create_edge("d1", f"IVGREL{TAG}", f"x{TAG}")
    got["mapped_unmapped_rel"] = outcome(A, f"MATCH (a:{L})-[:IVGREL{TAG}]->(x) RETURN x.id")
    got["mapped_mapped_rel"] = outcome(A, f"MATCH (a:{L})-[:HAS]->(b:{LT}) RETURN b.id")
    A.create_node(f"i{TAG}", labels=[f"BI{TAG}"]); A.create_edge(f"i{TAG}", f"IVGREL{TAG}", f"x{TAG}")
    got["ivg_unmapped_rel"] = outcome(A, f"MATCH (a:BI{TAG})-[:IVGREL{TAG}]->(x) RETURN x.id")
    try:
        A.map_sql_table(f"BPlain{TAG}", "id", f"BP{TAG}"); got["unqualified_accepted"] = True
    except ValueError:
        got["unqualified_accepted"] = False
    try:
        A.map_sql_table(f"SQLUser.BPlain{TAG}", "id", f"BQ{TAG}"); got["qualified_sqluser_accepted"] = True
    except ValueError:
        got["qualified_sqluser_accepted"] = False
    A.remove_table_mapping(L); got["A_after_remove"] = src_of(A)
    B.reload_table_mappings(); got["B_after_reload"] = src_of(B)
    c.close(); o.close()

    def predict(m):
        return {"A_after_map": label_source(cache_current(True, False, False, m), m),
                "B_after_map_no_reload": label_source(cache_current(False, False, False, m), m),
                "join_key_on_target": [["d1", "t1"]] if joined("d1", None, "t1", "d1", m) else "SqlError",
                "join_key_on_source": [["s1", "t1"]] if (m.get("join_on_source_fk") and joined("s1", "t1", "t1", None, m)) else "SqlError",
                "mapped_unmapped_rel": pattern_outcome("Table", "Unmapped", m), "mapped_mapped_rel": pattern_outcome("Table", "Mapped", m),
                "ivg_unmapped_rel": pattern_outcome("IvgNodes", "Unmapped", m),
                "unqualified_accepted": accepted(False, None, "SQLUser", m), "qualified_sqluser_accepted": accepted(True, "SQLUser", "SQLUser", m),
                "A_after_remove": label_source(False, m), "B_after_reload": label_source(False, m)}

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "sql_mapping", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "sql_mapping.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/fhir.py", "iris_vector_graph/cypher/translator.py"]}},
            "scope": "Actual mapping calls and Cypher on two engines over IRIS 2026.1 (pin 3eaa79cf); outcome classes (which source a label "
                     "reads, rows or SQL error, accepted or refused). The join key case on the source table has no same-named column on the "
                     "target table, so IRIS refuses it; with such a column the join would silently use it (not exercised)."}
    d = REPO / ".g5/Verus_verification/results/sql_mapping" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
