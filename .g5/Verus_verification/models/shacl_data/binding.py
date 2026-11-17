"""shacl_data binding: fresh W45 shapes on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the
actual validate_shacl (pySHACL 0.40.2, rdflib 7.6.0 from the pinned [rdf] extra); report.conforms compared with a port
of shacl_data.rs (min_ok_built, class_ok_built). Mutations mirror the controls. Ordinary data, ids unique per run."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("SH_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["keep_graphs_apart", "focus_loads_targets", "class_ignores_label"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- port: facts {graph: {"prop": set(ids), "label": set(ids), "edge": set((s, o))}} ----
def loaded(focus, n, m):
    return True if focus is None or m.get("focus_loads_targets") else n in focus


def min_ok_built(f, focus, n, m):
    graphs_with_node = [g for g in f if n in f[g]["nodes"]]
    if m.get("keep_graphs_apart"):
        return loaded(focus, n, m) and all(n in f[g]["prop"] for g in graphs_with_node)
    return loaded(focus, n, m) and any(n in f[g]["prop"] for g in f)


def class_ok_built(f, focus, n, m):
    for g in f:
        for s, o in f[g]["edge"]:
            if s == n and loaded(focus, n, m):
                has = any(o in f[h]["label"] for h in f) or m.get("class_ignores_label")
                if not (loaded(focus, o, m) and has):
                    return False
    return True


def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    D, Gn, p, G = f"BDrug{TAG}", f"BGene{TAG}", f"b{TAG}_", f"bg{TAG}"
    shape_min = f"""@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:ivg:shape/{D}> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ; sh:property [ sh:path <urn:ivg:prop/approved> ; sh:minCount 1 ] ."""
    shape_cls = f"""@prefix sh: <http://www.w3.org/ns/shacl#> .
<urn:ivg:shape/{D}c> a sh:NodeShape ; sh:targetClass <urn:ivg:{D}> ; sh:property [ sh:path <urn:ivg:INH{TAG}> ; sh:class <urn:ivg:{Gn}> ] ."""
    f = {"": {"nodes": set(), "prop": set(), "label": set(), "edge": set()}, G: {"nodes": set(), "prop": set(), "label": set(), "edge": set()}}

    def node(n, labels, props, graph=""):
        e.create_node(p + n, labels=labels, properties=props, graph=graph or None)
        f[graph]["nodes"].add(n)
        if "approved" in props: f[graph]["prop"].add(n)
        if Gn in labels: f[graph]["label"].add(n)

    def edge(s, o, graph=""):
        e.create_edge(p + s, f"INH{TAG}", p + o, graph=graph or None); f[graph]["edge"].add((s, o))

    node("ok", [D], {"approved": 2011}); node("bad", [D], {"name": "x"})
    node("twin", [D], {"approved": 1999}); node("twin", [D], {"name": "y"}, graph=G)
    node("drug", [D], {"approved": 2020}); node("gene", [Gn], {}); edge("drug", "gene")
    node("drug2", [D], {"approved": 2021}); node("other", ["BOther"], {}); edge("drug2", "other")
    cases = [("min_ok", "min", ["ok"], "ok"), ("min_bad", "min", ["bad"], "bad"), ("min_twin_masked", "min", ["twin"], "twin"),
             ("class_full", "cls", ["drug", "gene"], "drug"), ("class_focus_only", "cls", ["drug"], "drug"),
             ("class_bad_target", "cls", ["drug2", "other"], "drug2")]
    got = {}
    for name, kind, ids, _ in cases:
        r = e.validate_shacl(shape_min if kind == "min" else shape_cls, node_ids=[p + i for i in ids])
        got[name] = bool(r.conforms)
    c.close()

    def predict(m):
        return {name: (min_ok_built(f, set(ids), n, m) if kind == "min" else class_ok_built(f, set(ids), n, m))
                for name, kind, ids, n in cases}

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    import pyshacl, rdflib
    body = {"kind": "binding", "model": "shacl_data", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "providers": {"pyshacl": pyshacl.__version__, "rdflib": rdflib.__version__},
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()),
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "shacl_data.rs", HERE / "model.json"]},
                       **{x: sha(Path(runtime.PIN) / x) for x in ["iris_vector_graph/_engine/shacl.py", "iris_vector_graph/_engine/_rdf_utils.py"]}},
            "scope": "Actual validate_shacl on IRIS 2026.1 (pin 3eaa79cf) with node_ids naming this run's nodes, shapes sh:minCount and sh:class; "
                     "report.conforms compared. Other Core constraints, URL shapes and the literal typing rule (W45 S3) are not part of this binding."}
    d = REPO / ".g5/Verus_verification/results/shacl_data" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x))


if __name__ == "__main__":
    main()
