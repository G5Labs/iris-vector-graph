"""plaid_index binding: actual plaid_build / plaid_insert / plaid_info / plaid_search on the run-isolated retest
fixture against a port of plaid_index.rs (MaxSim = sum over query tokens of the best dot product with a stored token,
element-wise products stopping at the shorter vector). A seeded sequence of 24 inserts (new IDs, stored IDs, and
2-wide tokens) and searches with nprobe equal to the number of centroids, so every document is a candidate. Four port
mutations mirror the controls. Ordinary data, fixture only."""
import hashlib, json, os, random, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("PL_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def maxsim(q, ts): return sum(max((dot(qt, t) for t in ts), default=0.0) for qt in q)
class Port:
    def __init__(self, docs, m): self.m, self.tok, self.n, self.total = m, {d: list(t) for d, t in docs.items()}, len(docs), sum(len(t) for t in docs.values())
    def insert(self, d, ts):
        if self.m.get("insert_refuses_other_width") and any(len(t) != 3 for t in ts): return
        if self.m.get("keep_old_tokens") and d in self.tok: self.tok[d] = self.tok[d] + ts
        else: self.tok[d] = ts
        if not (self.m.get("count_only_new_docs") and d in self.seen): self.n += 1
        self.total += len(ts); self.seen.add(d)
    def search(self, q, k):
        r = sorted(((round(maxsim(q, t), 6), d) for d, t in self.tok.items()), key=lambda x: (-x[0], x[1]))[:k]
        return [(d, s) for s, d in r]
def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    rng = random.Random(20261116); name = f"pb{TAG}"
    def vec(w=3): return [float(rng.randint(-2, 2)) for _ in range(w)]
    docs = {f"d{i}": [vec() for _ in range(rng.randint(1, 3))] for i in range(6)}
    MUTS = ["build_skips_width_check", "count_only_new_docs", "keep_old_tokens", "insert_refuses_other_width"]
    cells, mism, sens = [], [], {m: 0 for m in MUTS}
    # build refusal (P1) with and without a mixed width
    bad = dict(docs); bad["dx"] = [vec(), vec(2)]
    try: e.plaid_build(name + "x", [{"id": d, "tokens": t} for d, t in bad.items()], n_clusters=3); refused = False
    except ValueError: refused = True
    cells.append({"op": "build mixed widths", "refused": refused, "info_after": e.plaid_info(name + "x")})
    if not refused or e.plaid_info(name + "x") != {}: mism.append(cells[-1])
    if not refused: pass
    sens["build_skips_width_check"] += 1 if refused else 0
    e.plaid_build(name, [{"id": d, "tokens": t} for d, t in docs.items()], n_clusters=3)
    nlist = e.plaid_info(name)["nlist"]
    ports = {None: Port(docs, {}), **{m: Port(docs, {m: True}) for m in MUTS if m != "build_skips_width_check"}}
    for p in ports.values(): p.seen = set(docs)
    for step in range(24):
        x = rng.random()
        if x < 0.55:
            d = rng.choice(list(docs) + [f"n{step}"]); w = 2 if rng.random() < 0.2 else 3
            ts = [vec(w) for _ in range(rng.randint(1, 2))]
            e.plaid_insert(name, d, ts)
            for p in ports.values(): p.insert(d, ts)
            got = e.plaid_info(name); obs = {"indexed": got["indexed"], "totalTokens": got["totalTokens"], "dim": got["dim"]}
            cell = {"op": "insert", "doc": d, "width": w, "observed": obs, "expected": {"indexed": ports[None].n, "totalTokens": ports[None].total, "dim": 3}}
            ok = cell["observed"] == cell["expected"]
            for m, p in ports.items():
                if m and {"indexed": p.n, "totalTokens": p.total, "dim": 3} != obs: sens[m] += 1
        else:
            q = [vec() for _ in range(rng.randint(1, 2))]; k = rng.randint(1, 5)
            got = [(h["id"], round(h["score"], 6)) for h in e.plaid_search(name, q, k=k, nprobe=nlist)]
            cell = {"op": "search", "query": q, "k": k, "observed": got, "expected": ports[None].search(q, k)}
            ok = [s for _, s in got] == [s for _, s in cell["expected"]] and set(got) == set(cell["expected"])
            for m, p in ports.items():
                if m and [s for _, s in p.search(q, k)] != [s for _, s in got]: sens[m] += 1
        cells.append(cell)
        if not ok: mism.append(cell)
    for n in (name, name + "x"):
        try: e.plaid_drop(n)
        except Exception: pass
    c.close()
    body = {"kind": "binding", "model": "plaid_index", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT, "run": RUN,
            "seed": 20261116, "verdict": "AGREES" if not mism else "DISAGREES", "operations": len(cells), "comparisons": len(cells), "mismatches": mism,
            "sensitivities_detected_operations": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "cells": cells,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "plaid_index.rs", HERE / "model.json"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_src/src/Graph/KG/PLAIDSearch.cls", "iris_vector_graph/_engine/vector.py"]}},
            "scope": "Actual Graph.KG.PLAIDSearch through the engine's plaid_* methods on IRIS 2026.1 (pin 3eaa79cf); six 3-wide documents, "
                     "24 seeded inserts and searches; nprobe equal to the centroid count (candidate selection by centroid not exercised); "
                     "ties compared as score multisets."}
    out = REPO / ".g5/Verus_verification/results/plaid_index" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "operations", "all_sensitivities_detected", "sensitivities_detected_operations", "elapsed_s")}))
    for x in mism[:5]: print("MISMATCH", json.dumps(x, default=str)[:600])
if __name__ == "__main__":
    main()
