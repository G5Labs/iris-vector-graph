"""ivf_entries binding: fresh IVF indexes on the run-isolated continuation fixture (ivg-cont-20261117-iris) through the
actual ivf_build, ivf_insert, ivf_delete, ivf_search and ivf_info; the cells come from ivf_insert's answers and the
outcomes are compared with a port of ivf_entries.rs. Mutations mirror the controls. Ordinary data."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

RUN = os.environ.get("IE_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
MUTS = ["insert_replaces", "delete_all", "width_checked", "delete_noop"]


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
    c.close()

    def predict(m):
        out = {k: port_seq(plan[k][0], plan[k][1], m) for k in plan}
        out["other_width_answered"] = not m.get("width_checked")
        return out

    want = predict({})
    mism = [{"case": k, "observed": got[k], "expected": want[k]} for k in want if got[k] != want[k]]
    sens = {mm: sum(1 for k, v in predict({mm: True}).items() if v != got[k]) for mm in MUTS}
    body = {"kind": "binding", "model": "ivf_entries", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(want), "mismatches": mism, "observed": got,
            "cells_from_ivf_insert": {k: v[0] for k, v in plan.items()},
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(q.relative_to(REPO)): sha(q) for q in [HERE / "binding.py", HERE / "ivf_entries.rs", HERE / "model.json"]},
                       **{f: sha(Path(runtime.PIN) / f) for f in ["iris_src/src/Graph/KG/IVFIndex.cls", "iris_vector_graph/_engine/vector.py"]}},
            "scope": "Actual IVF calls on IRIS 2026.1 (pin 3eaa79cf), two cells, cosine; numpy and scikit-learn from the pinned venv for the build."}
    d = REPO / ".g5/Verus_verification/results/ivf_entries" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    d.mkdir(parents=True); (d / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "observed", "cells_from_ivf_insert", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism:
        print("MISMATCH", json.dumps(x, default=str))


if __name__ == "__main__":
    main()
