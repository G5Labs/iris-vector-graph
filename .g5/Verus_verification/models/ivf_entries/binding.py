"""ivf_entries binding: fresh IVF indexes on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the
actual ivf_build, ivf_insert, ivf_delete, ivf_search and ivf_info; the cells come from ivf_insert's answers and the
outcomes are compared with a port of ivf_entries.rs. Mutations mirror the controls. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("IE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["insert_replaces", "delete_all", "width_checked", "delete_noop", "cosine_normalized", "cosine_takes_l2_branch",
        "insert_by_distance"]
# iteration 50 (review 47-49 m8): two well-separated clusters, one short and one long; a1 is re-inserted with its own vector
CELL_VECS = {"a1": [1.2, 0.0, 0.0, 0.0], "a2": [1.0, 0.0, 0.0, 0.0], "a3": [0.8, 0.1, 0.0, 0.0],
             "b1": [10.0, 10.0, 0.0, 0.0], "b2": [11.0, 9.0, 0.0, 0.0], "b3": [9.0, 11.0, 0.0, 0.0]}
COS_VECS = {"long_off": [10.0, 0.0, 0.0, 0.0], "unit_on": [0.6, 0.8, 0.0, 0.0], "other": [0.0, 0.0, 1.0, 0.0]}
COS_Q = [0.6, 0.8, 0.0, 0.0]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def port_seq(cells, deletes, m):
    st = {"cells": set(), "indexed": 0}
    for c in cells:
        if m.get("insert_replaces"):
            if not st["cells"]: st["indexed"] += 1
            st["cells"] = {c}
        else:
            st["cells"].add(c); st["indexed"] += 1
    for _ in range(deletes):
        if st["cells"] and not m.get("delete_noop"):
            if m.get("delete_all"):
                st["indexed"] -= len(st["cells"]); st["cells"] = set()
            else:
                st["cells"].remove(min(st["cells"])); st["indexed"] -= 1
    return {"found": bool(st["cells"]), "indexed_delta": st["indexed"]}


def entry_score(metric, q, v, m):
    """Port of ivf_entries.rs entry_score / ivf_above (and, under the mutations, the controls' replacements)."""
    dot = sum(a * b for a, b in zip(q, v)); sq = sum((a - b) ** 2 for a, b in zip(q, v))
    if metric == "cosine" and m.get("cosine_normalized"):
        n = sum(b * b for b in v) ** 0.5; return dot / n if n else 0.0
    if metric == "cosine" and m.get("cosine_takes_l2_branch"):
        return -sq
    return dot if metric in ("cosine", "dot") else -sq


def sqd(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def build_cell(v, cents):
    """Port of build_cell: the Euclidean-nearest centroid (lower cell on a tie)."""
    return min(range(len(cents)), key=lambda k: (sqd(v, cents[k]), k))


def insert_cell(metric, v, cents, m):
    """Port of insert_score / insert_cell: the first best cell by the metric branch (or by distance under the control)."""
    def score(cn):
        if metric in ("cosine", "dot") and not m.get("insert_by_distance"):
            return sum(a * b for a, b in zip(v, cn))
        return -sqd(v, cn)
    best = 0
    for k in range(1, len(cents)):
        if score(cents[k]) > score(cents[best]):
            best = k
    return best


def cos_predict(m):
    sc = {n: entry_score("cosine", COS_Q, v, m) for n, v in COS_VECS.items()}
    order = sorted(sc, key=lambda n: (-sc[n], n))
    return {"order": order, "scores": {n: round(sc[n], 3) for n in order}}


def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    G, K, p = f"ieg{TAG}", f"ie-k-{TAG}", f"ie{TAG}_"
    for n, v in {"a": [1, 0, 0, 0], "a2": [0.9, 0.1, 0, 0], "b": [0, 0, 0, 1], "b2": [0, 0, 0.1, 0.9]}.items():
        e.create_node(p + n, graph=G); e.store_embedding(p + n, [float(x) for x in v], graph=G, model_key=K)
    got, plan = {}, {}

    def run(case, vecs, deletes):
        name = f"ie{TAG}{case}"; e.ivf_build(name, nlist=2, graph=G, model_key=K); base = e.ivf_info(name)["indexed"]
        cells = [e.ivf_insert(name, p + "x", v) for v in vecs]
        for _ in range(deletes):
            e.ivf_delete(name, p + "x")
        found = any(n == p + "x" for n, _ in e.ivf_search(name, vecs[0], k=10, nprobe=2)) or any(n == p + "x" for n, _ in e.ivf_search(name, vecs[-1], k=10, nprobe=2))
        got[case] = {"found": found, "indexed_delta": e.ivf_info(name)["indexed"] - base}; plan[case] = (cells, deletes)

    run("same_cell_twice", [[1.0, 0.05, 0, 0], [0.95, 0.0, 0.05, 0]], 0)
    run("cross_cell_then_delete", [[1.0, 0.05, 0, 0], [0, 0, 0.05, 1.0]], 1)
    run("insert_then_delete", [[1.0, 0.05, 0, 0]], 1)
    name = f"ie{TAG}w"; e.ivf_build(name, nlist=2, graph=G, model_key=K)
    try:
        got["other_width_answered"] = len(e.ivf_search(name, [1.0, 0.0, 0.0], k=3, nprobe=2)) > 0
    except Exception:
        got["other_width_answered"] = False
    # W53 (bug-srch-109): metric "cosine" over vectors of different lengths, read through ivf_search and through
    # the SQL function kg_IVF (SqlProcs.kgIVF -> IVFIndex.SearchProc -> Search).
    cname = f"ie{TAG}c"
    for n, v in COS_VECS.items():
        e.create_node(p + n, graph=G + "c"); e.store_embedding(p + n, v, graph=G + "c", model_key=K)
    e.ivf_build(cname, nlist=1, graph=G + "c", model_key=K, metric="cosine")
    # m8: which cell the build puts a1 in (read from ^IVF(name,"list",cell,node)) and which cell Insert picks for the
    # same vector; the centroids are the clusters' means under the observed build labels (provider input: k-means)
    io = e._iris_obj(); cell_inputs = {}
    for n, v in CELL_VECS.items():
        e.create_node(p + "k" + n, graph=G + "k"); e.store_embedding(p + "k" + n, v, graph=G + "k", model_key=K)
    for metric in ("cosine", "dot", "l2"):
        name = f"ie{TAG}k{metric[0]}"; e.ivf_build(name, nlist=2, graph=G + "k", model_key=K, metric=metric)
        labels = {n: [cc for cc in (0, 1) if io.isDefined("IVF", name, "list", cc, p + "k" + n)] for n in CELL_VECS}
        base = e.ivf_info(name)["indexed"]
        cell = e.ivf_insert(name, p + "ka1", CELL_VECS["a1"])
        after = [cc for cc in (0, 1) if io.isDefined("IVF", name, "list", cc, p + "ka1")]
        cell_inputs[metric] = labels
        got[f"cell_{metric}"] = {"build_cell": labels["a1"], "insert_cell": cell, "cells_after": after,
                                 "indexed_delta": e.ivf_info(name)["indexed"] - base}
    py = e.ivf_search(cname, COS_Q, k=3, nprobe=1)
    cur = c.cursor(); cur.execute(f"SELECT {e._ivg_schema}.kg_IVF(?, ?, ?, ?)", [cname, json.dumps(COS_Q), 3, 1])
    sq = [(r["id"], float(r["score"])) for r in json.loads(cur.fetchone()[0])]; cur.close()
    for key, rows in (("cosine_ivf_search", py), ("cosine_kg_IVF", sq)):
        got[key] = {"order": [n[len(p):] for n, _ in rows], "scores": {n[len(p):]: round(s, 3) for n, s in rows}}
    c.close()

    def predict(m):
        out = {k: port_seq(plan[k][0], plan[k][1], m) for k in plan}
        out["other_width_answered"] = not m.get("width_checked")
        out["cosine_ivf_search"] = out["cosine_kg_IVF"] = cos_predict(m)
        for metric, labels in cell_inputs.items():
            cents = []
            for k in (0, 1):
                mem = [CELL_VECS[n] for n, cs in labels.items() if cs == [k]]
                cents.append([sum(col) / len(mem) for col in zip(*mem)] if mem else [0.0] * 4)
            b = build_cell(CELL_VECS["a1"], cents); i = insert_cell(metric, CELL_VECS["a1"], cents, m)
            out[f"cell_{metric}"] = {"build_cell": [b], "insert_cell": i, "cells_after": sorted({b, i}),
                                     "indexed_delta": 1}
        return out

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    # Detection check: alter the observed deciding field (the cosine order read back) and require a mismatch.
    tampered = json.loads(json.dumps(got)); tampered["cosine_kg_IVF"]["order"] = list(reversed(tampered["cosine_kg_IVF"]["order"]))
    tamper_detected = any(tampered[k] != want[k] for k in want)
    body = {"kind": "binding", "model": "ivf_entries", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "cells_from_ivf_insert": {k: v[0] for k, v in plan.items()},
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "observation_tamper_detected": tamper_detected, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "ivf_entries.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/Graph/KG/IVFIndex.cls", "iris_src/src/Graph/KG/SqlProcs.cls", "iris_vector_graph/_engine/vector.py"]}},
            "scope": "Actual IVF calls on IRIS 2026.1 (pin 3eaa79cf), two cells, cosine; iteration 50: the build's cell for a node (read from ^IVF) against Insert's cell for the same vector under cosine, dot and l2 (two separated clusters, centroids taken as the clusters' means under the observed labels); the W53 cosine case through ivf_search and SQL kg_IVF (one cell, vectors of lengths 10, 1, 1); numpy and scikit-learn from the pinned venv for the build."}
    d = REPO / ".g5/Verus_verification/results/ivf_entries" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "cells_from_ivf_insert", "all_sensitivities_detected", "sensitivities_detected_cases", "observation_tamper_detected", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
