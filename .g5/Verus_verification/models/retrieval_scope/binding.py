"""retrieval_scope binding: fresh shapes on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the
actual kg_NEIGHBORS, kg_MENTIONS and kg_NEIGHBORHOOD_EXPANSION; outcome classes compared with a port of
retrieval_scope.rs. Mutations mirror the controls. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("RS_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["neighbors_default_only", "missing_confidence_kept", "strict_threshold", "dedupe_per_chunk"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def predict(m):
    keep = lambda c: (c is None and m.get("missing_confidence_kept")) or (c is not None and (c > 500 if m.get("strict_threshold") else c >= 500))  # noqa: E731
    return {"neighbors_named_only_edge": not m.get("neighbors_default_only"),
            "expansion_named_edge_default_arg": False, "expansion_named_edge_graph_arg": True,
            "expansion_kept": sorted(t for t, c in [("h1", 900), ("h2", 500), ("h3", 499), ("h4", None)] if keep(c)),
            "distinct_count_over_chunks": 3 if m.get("dedupe_per_chunk") else 1, "mentions": ["m"]}


def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    p = f"rs{TAG}_"; N = lambda x: p + x; R = f"R{TAG}"; G = f"rsg{TAG}"  # noqa: E731
    got = {}
    for x in ["ga", "gb"]:
        e.create_node(N(x), graph=G)
    e.create_edge(N("ga"), R, N("gb"), graph=G, qualifiers={"confidence": 800})
    got["neighbors_named_only_edge"] = N("gb") in e.kg_NEIGHBORS([N("ga")])
    got["expansion_named_edge_default_arg"] = any(d["target"] == N("gb") for d in e.kg_NEIGHBORHOOD_EXPANSION([N("ga")], confidence_threshold=500))
    got["expansion_named_edge_graph_arg"] = any(d["target"] == N("gb") for d in e.kg_NEIGHBORHOOD_EXPANSION([N("ga")], confidence_threshold=500, graph=G))
    for x in ["h", "h1", "h2", "h3", "h4", "m", "t"]:
        e.create_node(N(x))
    for t, conf in [("h1", 900), ("h2", 500), ("h3", 499), ("h4", None)]:
        e.create_edge(N("h"), R, N(t), qualifiers={"confidence": conf} if conf is not None else None)
    got["expansion_kept"] = sorted(d["target"][len(p):] for d in e.kg_NEIGHBORHOOD_EXPANSION([N("h")], confidence_threshold=500))
    srcs = [N(f"s{i}") for i in range(3)]
    e.bulk_ingest_edges([(s, N("t"), R) for s in srcs], predicate=R)
    got["distinct_count_over_chunks"] = len(e.kg_NEIGHBORS(srcs, predicate=R, chunk_size=1))
    e.create_edge(N("h"), "MENTIONS", N("m"))
    got["mentions"] = [x[len(p):] for x in e.kg_MENTIONS([N("h")])]
    c.close()
    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "retrieval_scope", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "retrieval_scope.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/algorithms.py", "iris_vector_graph/_engine/vector.py", "iris_vector_graph/operators.py"]}},
            "scope": "Actual kg_NEIGHBORS (chunk_size 1 to force chunking), kg_MENTIONS and kg_NEIGHBORHOOD_EXPANSION on IRIS 2026.1 (pin 3eaa79cf)."}
    d = REPO / ".g5/Verus_verification/results/retrieval_scope" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
