"""rdf_import binding: fresh RDF files (written under $RDF_FILES or /tmp) imported on the run-isolated continuation
fixture (ivg-cont-20261117-iris) through the actual import_rdf, read back with get_node, Cypher and rdf_edges; outcome
classes compared with a port of rdf_import.rs. Mutations mirror the controls. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("RI_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
FILES = Path(os.environ.get("RDF_FILES", "/tmp")) / f"rdf-import-binding-{RUN}"
SUB = "http://www.w3.org/2000/01/rdf-schema#subClassOf"; TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
INT = "http://www.w3.org/2001/XMLSchema#integer"
MUTS = ["context_ignored", "keep_datatype", "upsert_property", "full_iri_key", "infer_on_contexts"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def predict(m):
    return {"ctx_node_in_context_graph": not m.get("context_ignored"),
            "int_literal_reads_as": "int" if m.get("keep_datatype") else "str",
            "int_literal_equals_in_cypher": bool(m.get("keep_datatype")),
            "reimport_value": "second" if m.get("upsert_property") else "first",
            "reimport_properties_counted": 1 if m.get("upsert_property") else 0,
            "collision_keys": 2 if m.get("full_iri_key") else 1,
            "inferred_rows_in_context_graph": 1 if m.get("infer_on_contexts") else 0}


def main():
    t0 = time.time(); FILES.mkdir(parents=True, exist_ok=True)
    c = runtime.connect(); e = runtime.engine(c)
    x = f"http://ex.org/ri{TAG}/"; G, GA = f"ric{TAG}", f"ria{TAG}"
    (FILES / "ctx.nq").write_text(f"<{x}A> <{SUB}> <{x}B> <urn:ivg:graph:{G}> .\n<{x}i> <{TYPE}> <{x}A> <urn:ivg:graph:{G}> .\n")
    (FILES / "lit.ttl").write_text(f"<{x}s> <{x}yr> \"2011\"^^<{INT}> .\n<{x}s> <http://a.org/nm> \"p\" .\n<{x}s> <http://b.org#nm> \"q\" .\n")
    (FILES / "v1.ttl").write_text(f"<{x}u> <{x}label> \"first\" .\n")
    (FILES / "v2.ttl").write_text(f"<{x}u> <{x}label> \"second\" .\n")
    got = {}
    e.import_rdf(str(FILES / "ctx.nq"), graph=GA, infer=False)
    got["ctx_node_in_context_graph"] = e.node_exists(x + "i", graph=G) and not e.node_exists(x + "i", graph=GA)
    e.import_rdf(str(FILES / "lit.ttl"))
    n = e.get_node(x + "s")
    got["int_literal_reads_as"] = type(n.get("yr")).__name__
    got["int_literal_equals_in_cypher"] = e.execute_cypher("MATCH (n {node_id: $s}) WHERE n.yr = 2011 RETURN count(n)", {"s": x + "s"}).rows[0][0] == 1
    got["collision_keys"] = sum(1 for k in n if k == "nm" or k.endswith("nm"))
    e.import_rdf(str(FILES / "v1.ttl"))
    r2 = e.import_rdf(str(FILES / "v2.ttl"))
    got["reimport_value"] = e.get_node(x + "u").get("label"); got["reimport_properties_counted"] = r2["properties"]
    e.import_rdf(str(FILES / "ctx.nq"), infer=True)          # quads in G, no graph argument
    cur = c.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {e._ivg_schema}.rdf_edges WHERE graph_id = ? AND qualifiers LIKE '%\"inferred\":%'", [G])
    got["inferred_rows_in_context_graph"] = int(cur.fetchone()[0]); cur.close(); c.close()

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "rdf_import", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "files": str(FILES), "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism,
            "observed": got, "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "rdf_import.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/snapshot.py", "iris_vector_graph/_engine/schema.py"]}},
            "scope": "Actual import_rdf (rdflib 7.6.0) on IRIS 2026.1 (pin 3eaa79cf) with N-Quads and Turtle files; read back through node_exists, "
                     "get_node, Cypher and rdf_edges. Which colliding literal survives follows rdflib's iteration order and is not compared."}
    d = REPO / ".g5/Verus_verification/results/rdf_import" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x_ in mism:
        print("MISMATCH", json.dumps(x_, default=str))


if __name__ == "__main__":
    main()
