"""cypher_export binding: fresh rows on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the actual
export_rdf_from_cypher; answers compared with a port of cypher_export.rs. Mutations mirror the controls. Ordinary data;
files under $CX_FILES or /tmp; one fixture-only SQL table (a mapped label) makes a query that IRIS refuses."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("CE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
FILES = Path(os.environ.get("CX_FILES", "/tmp")) / f"cypher-export-binding-{RUN}"
MUTS = ["positional_checks_null", "error_raised", "named_drops_falsy", "null_written"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def written(cols, vals, m):
    if cols == "named":
        return True if m.get("null_written") else all(v != "null" for v in vals) and (not m.get("named_drops_falsy") or all(v == "other" for v in vals))
    return all(v != "null" for v in vals) if m.get("positional_checks_null") else all(v == "other" for v in vals)


def main():
    t0 = time.time(); FILES.mkdir(parents=True, exist_ok=True); c = runtime.connect(); e = runtime.engine(c)
    p = f"ce{TAG}_"; L = f"CEL{TAG}"
    e.create_node(p + "a", labels=[L], properties={"v": 0, "w": 5}); e.create_node(p + "b", labels=[L], properties={"v": 0, "w": 6})
    def ans(q, name):
        try:
            return e.export_rdf_from_cypher(q, str(FILES / name))["triples"]
        except Exception:
            return "Raised"
    got = {"named_other": ans(f"MATCH (n:{L}) RETURN n.node_id AS s, 'w' AS p, n.w AS o", "a.nt"),
           "positional_other": ans(f"MATCH (n:{L}) RETURN n.node_id AS x, 'w' AS y, n.w AS z", "b.nt"),
           "named_zero": ans(f"MATCH (n:{L}) RETURN n.node_id AS s, 'v' AS p, n.v AS o", "c.nt"),
           "positional_zero": ans(f"MATCH (n:{L}) RETURN n.node_id AS x, 'v' AS y, n.v AS z", "d.nt"),
           "named_null": ans(f"MATCH (n:{L}) RETURN n.node_id AS s, 'nope' AS p, n.nope AS o", "e.nt")}
    cur = c.cursor(); S = f"CEx{TAG}"
    cur.execute(f"CREATE TABLE {S}.T (id VARCHAR(50) PRIMARY KEY)"); cur.execute(f"INSERT INTO {S}.T (id) VALUES ('m1')"); c.commit()
    e.map_sql_table(f"{S}.T", "id", f"CEM{TAG}", [])
    got["failed_query"] = ans(f"MATCH (m:CEM{TAG})-[r]->(x) RETURN m.id AS s, type(r) AS p, x.node_id AS o", "f.nt")
    e.remove_table_mapping(f"CEM{TAG}"); c.close()

    def predict(m):
        n = lambda cols, vals: 2 if written(cols, vals, m) else 0  # noqa: E731
        return {"named_other": n("named", ["other"] * 3), "positional_other": n("positional", ["other"] * 3),
                "named_zero": n("named", ["other", "other", "falsy"]), "positional_zero": n("positional", ["other", "other", "falsy"]),
                "named_null": n("named", ["other", "other", "null"]), "failed_query": "Raised" if m.get("error_raised") else 0}

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "cypher_export", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "cypher_export.rs", HERE / "model.json"]},
                       "iris_vector_graph/_engine/rdf_export.py": sha(Path(runtime.PIN) / "iris_vector_graph/_engine/rdf_export.py")},
            "scope": "Actual export_rdf_from_cypher on IRIS 2026.1 (pin 3eaa79cf), rdflib 7.6.0; answers (distinct triples or a raise)."}
    d = REPO / ".g5/Verus_verification/results/cypher_export" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
