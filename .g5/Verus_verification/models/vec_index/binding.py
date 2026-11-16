"""vec_index binding: actual vec_* engine calls (Graph.KG.VecIndex) on the run-isolated retest fixture, compared after
every operation with a port of vec_index.rs plus the metric arithmetic computed in Python (zero-padding a shorter
vector's extra components ignored by the element-wise operations, as $vectorop does).

Domain: for each of the five metrics, a seeded sequence of 30 operations on a fresh index with at most 12 vectors
(below the leaf size, so every tree is one leaf and a search ranks every candidate in it): inserts of new and stored
ids, builds, searches (k 1-6), expands, one re-create over the existing name and one insert of another width, then a
drop. Observed after each operation: vec_info count and dim; for searches and expands the ids, scores and distances.
Six port mutations mirror the model's controls; `build_keeps_old_planes` cannot change a one-leaf tree and is
reported, not required. Ordinary data, fixture only."""
import hashlib, json, math, os, random, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(Path(os.environ.get("IVG_RUNTIME_DIR", str(REPO / ".g5/uplift/consolidated/iteration-25")))))
import runtime  # noqa: E402
RUN = os.environ.get("VI_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
TAG = RUN.replace("T", "").replace("Z", "")[-8:]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pad(a, b):
    n = max(len(a), len(b)); return list(a) + [0.0] * (n - len(a)), list(b) + [0.0] * (n - len(b))
def dist(m, q, v):
    # $vectorop("v*") and ("v-") work over the shorter length; the cosine norms use each whole vector. Observed in the
    # first run of this binding: an l2 distance to a 2-wide vector ignores the query's third component.
    dot = sum(x * y for x, y in zip(q, v))
    if m == "cosine":
        n1, n2 = math.sqrt(sum(x * x for x in q)), math.sqrt(sum(x * x for x in v))
        return 1 - (0 if n1 == 0 or n2 == 0 else dot / (n1 * n2))
    if m == "dot": return -dot
    d = [abs(x - y) for x, y in zip(q, v)]
    return {"l2": math.sqrt(sum(x * x for x in d)), "l1": sum(d), "chebyshev": max(d)}[m]
def score(m, d, r):
    if m == "cosine": return 1 - d
    if m == "dot": return d if r.get("dot_score_is_distance") else -d
    return d


class Port:
    def __init__(self, m, r):
        self.m, self.r, self.vecs, self.count, self.dim, self.trees, self.waiting = m, r, {}, 0, 3, 4, set()
    def create(self, dim):
        if not self.r.get("create_keeps_count"): self.count = 0
        self.dim = dim
    def insert(self, i, v):
        if self.r.get("refuse_other_width") and self.dim > 0 and len(v) != self.dim: return
        if not (self.r.get("count_only_new_ids") and i in self.vecs): self.count += 1
        self.vecs[i] = v; self.dim = len(v)
        if self.r.get("insert_not_into_trees") and self.built: self.waiting.add(i)
    built = False
    def build(self):
        self.built = True; self.waiting = set()
    def search(self, q, k):
        cand = [i for i in self.vecs if i not in self.waiting]
        ranked = sorted(cand, key=lambda i: (round(dist(self.m, q, self.vecs[i]), 9), i))[:k]
        return [(i, round(score(self.m, dist(self.m, q, self.vecs[i]), self.r), 6), round(dist(self.m, q, self.vecs[i]), 6)) for i in ranked]
    def info(self):
        return {"count": self.count, "dim": self.dim}


def main():
    t0 = time.time()
    c = runtime.connect(); e = runtime.engine(c)
    MUTS = ["insert_not_into_trees", "count_only_new_ids", "refuse_other_width", "create_keeps_count",
            "build_keeps_old_planes", "dot_score_is_distance"]
    cells, mism, sens = [], [], {r: 0 for r in MUTS}
    rng = random.Random(20261116)
    for m in ["cosine", "dot", "l2", "l1", "chebyshev"]:
        name = f"vb{TAG}{m}"
        e.vec_create_index(name, 3, metric=m)
        ports = {None: Port(m, {}), **{r: Port(m, {r: True}) for r in MUTS}}
        ids = [f"d{j:02d}" for j in range(12)]
        ops = []
        for step in range(30):
            x = rng.random()
            if step == 18: ops.append(("create",))
            elif step == 24: ops.append(("insert", rng.choice(ids), [float(rng.randint(-3, 3)), float(rng.randint(-3, 3))]))
            elif x < 0.45: ops.append(("insert", rng.choice(ids), [float(rng.randint(-3, 3)) for _ in range(3)]))
            elif x < 0.6: ops.append(("build",))
            elif x < 0.85: ops.append(("search", [float(rng.randint(-3, 3)) for _ in range(3)], rng.randint(1, 6)))
            else: ops.append(("expand", rng.choice(ids), rng.randint(1, 4)))
        ops += [("drop",), ("search", [1.0, 0.0, 0.0], 3)]
        for op in ops:
            got = {}
            if op[0] == "create": e.vec_create_index(name, 3, metric=m)
            elif op[0] == "insert": e.vec_insert(name, op[1], op[2])
            elif op[0] == "build": e.vec_build(name)
            elif op[0] == "drop": e.vec_drop(name)
            elif op[0] == "search":
                got["hits"] = [(h["id"], round(h["score"], 6), round(h["distance"], 6)) for h in e.vec_search(name, op[1], k=op[2])]
            elif op[0] == "expand":
                got["hits"] = [(h["id"], round(h["score"], 6), round(h["distance"], 6)) for h in e.vec_expand(name, op[1], k=op[2])]
            info = e.vec_info(name); got["info"] = {"count": info["count"], "dim": info["dim"]}
            preds = {}
            for r, p in ports.items():
                if op[0] == "create": p.create(3)
                elif op[0] == "insert": p.insert(op[1], op[2])
                elif op[0] == "build": p.build()
                elif op[0] == "drop": p.__init__(m, p.r); p.dim = 0; p.trees = 0
                pr = {}
                if op[0] == "search": pr["hits"] = p.search(op[1], op[2])
                elif op[0] == "expand": pr["hits"] = p.search(p.vecs[op[1]], op[2]) if op[1] in p.vecs else []
                pr["info"] = p.info(); preds[r] = pr
            def same(a, b):
                if a["info"] != b["info"] or ("hits" in a) != ("hits" in b): return False
                if "hits" not in a: return True
                return len(a["hits"]) == len(b["hits"]) and all(x[0] == y[0] and abs(x[1] - y[1]) < 1e-5 and abs(x[2] - y[2]) < 1e-5
                                                                 for x, y in zip(a["hits"], b["hits"]))
            cell = {"metric": m, "op": [str(x) for x in op], "observed": got, "expected": preds[None]}
            cells.append(cell)
            if not same(got, preds[None]): mism.append(cell)
            for r in MUTS:
                if not same(got, preds[r]): sens[r] += 1
    c.close()
    required = [r for r in MUTS if r != "build_keeps_old_planes"]
    body = {"kind": "binding", "model": "vec_index", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT,
            "run": RUN, "seed": 20261116, "verdict": "AGREES" if not mism else "DISAGREES", "operations": len(cells),
            "comparisons": len(cells) + sum(1 for x in cells if "hits" in x["observed"]), "mismatches": mism,
            "sensitivities_detected_operations": sens, "all_required_sensitivities_detected": all(sens[r] > 0 for r in required),
            "not_detectable_here": ["build_keeps_old_planes (one-leaf trees)"], "cells": cells, "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "vec_index.rs", HERE / "model.json"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_src/src/Graph/KG/VecIndex.cls", "iris_vector_graph/_engine/vector.py"]}},
            "scope": "Actual Graph.KG.VecIndex through the engine's vec_* methods on IRIS 2026.1 (pin 3eaa79cf); indexes of at most 12 "
                     "vectors (one-leaf trees, exact ranking); integer-valued 3-wide vectors plus one 2-wide insert per metric. Multi-leaf "
                     "approximate search (nprobe, plane splits) is outside this binding."}
    out = REPO / ".g5/Verus_verification/results/vec_index" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "operations", "comparisons", "all_required_sensitivities_detected",
                                           "sensitivities_detected_operations", "elapsed_s")}))
    for x in mism[:6]: print("MISMATCH", json.dumps(x, default=str)[:600])


if __name__ == "__main__":
    main()
