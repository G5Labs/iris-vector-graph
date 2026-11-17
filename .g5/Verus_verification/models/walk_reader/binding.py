"""walk_reader binding: fresh graphs on the run-isolated continuation fixture (ivg-cont-20261117-iris).

For each shape, the producer's own edge order (BFSFast, read whole through khop, which returns every walked edge in
walk order) is fed to a port of walk_reader.rs `stage`; the port's rows, ordered by (step, target), must equal what
kg_GRAPH_WALK returns. One star is long enough that the walk's reply exceeds an IRIS string: the port predicts khop
answers, the walk raises, and the stage stays in ^ArnoKG("bfs_r"). Mutations mirror the controls. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("WR_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
BIG = int(os.environ.get("WR_BIG", "40000"))
MUTS = ["first_wins", "key_ignores_step", "walk_has_stream", "stage_killed_on_raise"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def stage(rows, m):
    st = {}
    for s, p, o, step in rows:
        key = (0 if m.get("key_ignores_step") else step, o)
        if m.get("first_wins") and key in st:
            continue
        st[key] = (s, p, step)
    return sorted(((v[0], v[1], k[1], v[2]) for k, v in st.items()), key=lambda r: (r[3], r[2]))


def predict_large(m):
    walk_answers = bool(m.get("walk_has_stream"))
    return {"khop_answered": True, "walk_answered": walk_answers,
            "stage_left": (not walk_answers) and not m.get("stage_killed_on_raise")}


def main():
    import iris
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c); nat = iris.createIRIS(c)
    p = f"wr{TAG}"
    shapes = {
        "chain": [("s", "R", "a"), ("a", "R", "b"), ("b", "R", "c"), ("s", "R", "d")],
        "diamond": [("s", "R", "a"), ("s", "R", "b"), ("a", "R", "x"), ("b", "R", "x")],
        "two_types": [("s", "R", "a"), ("s", "Q", "a"), ("a", "R", "b")],
        "cross": [("s", "R", "a"), ("s", "R", "b"), ("a", "R", "b"), ("b", "R", "c")],
        "back_edge": [("s", "R", "a"), ("a", "R", "s"), ("a", "R", "b")],
    }
    got, want = {}, {}
    for name, edges in shapes.items():
        q = f"{p}{name}_"
        for a, t, b in edges:
            for n in (a, b):
                if not e.get_node(q + n):
                    e.create_node(q + n, labels=["WR"])
            e.create_edge(q + a, t, q + b)
        k = e.khop(q + "s", hops=3, max_nodes=10_000)
        produced = [(x["s"][len(q):], x["p"], x["o"][len(q):], int(x["step"])) for x in k["edges"]]
        walk = [(a[len(q):], t, b[len(q):], int(h)) for a, t, b, h in e.kg_GRAPH_WALK(q + "s", max_depth=3, max_results=1000)]
        got[name] = {"walk": walk, "produced": produced}

    hub = f"{p}hub"; pad = "y" * 40
    e.bulk_ingest_edges([(hub, f"{p}leaf{i:06d}{pad}", "STAR") for i in range(BIG)], predicate="STAR")
    before = set(_children(nat, "^ArnoKG", "bfs_r"))
    big = {}
    try:
        big["khop_answered"] = len(e.khop(hub, hops=1, max_nodes=BIG + 10)["edges"]) == BIG
    except Exception:
        big["khop_answered"] = False
    try:
        big["walk_answered"] = len(e.kg_GRAPH_WALK(hub, max_depth=1, max_results=BIG + 10)) == BIG
        big["walk_error"] = None
    except Exception as exc:
        big["walk_answered"] = False; big["walk_error"] = str(exc)[:200]
    left = sorted(set(_children(nat, "^ArnoKG", "bfs_r")) - before)
    big["stage_left"] = bool(left)
    for t in left:                      # remove this run's residue so the fixture stays tidy (fixture-only data)
        nat.kill("^ArnoKG", "bfs_r", t)
    c.close()

    def predict(m):
        out = {n: stage(got[n]["produced"], m) for n in shapes}
        out["large"] = predict_large(m)
        return out

    observed = {n: [list(r) for r in got[n]["walk"]] for n in shapes}
    observed["large"] = {k: big[k] for k in ("khop_answered", "walk_answered", "stage_left")}
    exp = predict({}); exp = {n: ([list(r) for r in v] if n != "large" else v) for n, v in exp.items()}
    mism = [{"case": n, "observed": observed[n], "expected": exp[n]} for n in exp if observed[n] != exp[n]]
    sens = {}
    for mm in MUTS:
        pm = predict({mm: True}); pm = {n: ([list(r) for r in v] if n != "large" else v) for n, v in pm.items()}
        sens[mm] = sum(1 for n in pm if pm[n] != observed[n])
    body = {"kind": "binding", "model": "walk_reader", "fixture": runtime.NAME, "port": runtime.PORT,
            "product_baseline": runtime.PRODUCT, "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES",
            "cases": len(exp), "mismatches": mism, "observed": observed, "produced_edge_order": {n: got[n]["produced"] for n in shapes},
            "walk_error": big.get("walk_error"), "sensitivities_detected_cases": sens,
            "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "walk_reader.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_vector_graph/_engine/algorithms.py", "iris_vector_graph/host.py",
                                                                    "iris_vector_graph/schema.py", "iris_src/src/Graph/KG/TraversalBFS.cls",
                                                                    "iris_src/src/Graph/KG/Traversal.cls"]}},
            "scope": "Actual khop and kg_GRAPH_WALK (default graph, outbound, no edge-type list, max_depth 3) on IRIS 2026.1 (pin 3eaa79cf). "
                     "The walk's rows are compared with walk_reader.rs `stage` applied to the producer's own edge order (khop). One star of "
                     f"{BIG} edges with 40-character padding exceeds an IRIS string. Edge-type sequences, inbound walks and named graphs are not "
                     "exercised here (W43 observed them)."}
    d = REPO / ".g5/Verus_verification/results/walk_reader" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "all_sensitivities_detected", "sensitivities_detected_cases", "walk_error", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


def _children(nat, glo, *subs):
    out, k = [], ""
    while True:
        k = nat.nextSubscript(False, glo, *subs, k)
        if k is None or k == "":
            return out
        out.append(k)


if __name__ == "__main__":
    main()
