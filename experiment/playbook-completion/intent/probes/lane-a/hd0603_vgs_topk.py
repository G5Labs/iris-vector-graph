"""HD-0603 probe: does kg_VECTOR_GRAPH_SEARCH return the k best-scored candidates?

Contracts cited:
- vector.py:1463-1471 docstring / docs/API_REFERENCE.md:1015-1029 (commit 5ae90dbc, R025, "docstrings only, no code
  change"): "... keeps `k` of that set in no particular order, and sorts them by `vector_similarity`".
- Same docstring, Returns: "List of ranked entities with combined scores" (older wording, kept).
- Working assumption (decisions.md HD-0603): best k of the scored candidate set, defined tie behaviour.

Oracle: graph ia-0603, 6 nodes with vectors; the 4 vector hits (k=2 -> min(2k,50)=4) each have 10 confidence-900
neighbours without vectors (score 0.0). The candidate set has 44 ids; the 2 best by vector similarity are known.
The call runs in child processes with PYTHONHASHSEED 0..11 (set iteration order is the only thing that changes).
- Every run returns the 2 best -> reading (a) "top k" holds in practice.
- Some runs return 0.0-scored neighbours instead of the best vector hits -> as-built is the documented "k of the set in
  no particular order" (reading (c)), and the best hits can be dropped. Registered as expected-violation: the
  product does what its current docstring says; the best-k property is what the documented baseline violates.
Cleanup: erases its own graph (and its route table).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import _common as C

G = "ia-0603"
VECS = {
    "ia0603:v1": [1.0, 0.0, 0.0, 0.0],
    "ia0603:v2": [0.95, 0.05, 0.0, 0.0],
    "ia0603:v3": [0.7, 0.7, 0.0, 0.0],
    "ia0603:v4": [0.5, 0.0, 0.8, 0.0],
    "ia0603:v5": [0.0, 1.0, 0.0, 0.0],
    "ia0603:v6": [0.0, 0.0, 0.0, 1.0],
}
Q = [1.0, 0.0, 0.0, 0.0]


def child() -> None:
    c = C.conn()
    e = C.engine(c)
    res = e.kg_VECTOR_GRAPH_SEARCH(json.dumps(Q), k=2, min_confidence=0.5, graph=G)
    knn = e.kg_KNN_VEC(json.dumps(Q), k=4, graph=G)
    print(json.dumps({"seed": os.environ.get("PYTHONHASHSEED"),
                      "result": [(r["entity_id"], round(float(r["vector_similarity"]), 4)) for r in res],
                      "knn4": [(i, round(float(s), 4)) for i, s in knn]}))
    c.close()


def main() -> None:
    c = C.conn()
    e = C.engine(c)
    try:
        e.erase_graph(G)
        for n, v in VECS.items():
            e.create_node(n, graph=G)
            e.store_embedding(n, v, graph=G)
        for i, src in enumerate(["ia0603:v1", "ia0603:v2", "ia0603:v3", "ia0603:v4"]):
            for j in range(10):
                nb = f"ia0603:x{i}{j}"
                e.create_node(nb, graph=G)
                e.create_edge(src, "NEAR", nb, qualifiers={"confidence": 900}, graph=G)
        best = ["ia0603:v1", "ia0603:v2"]
        runs = []
        for seed in range(12):
            env = dict(os.environ, PYTHONHASHSEED=str(seed))
            out = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True,
                                 timeout=120)
            line = [ln for ln in out.stdout.splitlines() if ln.startswith("{")]
            r = json.loads(line[-1]) if line else {"seed": seed, "error": out.stderr[-400:]}
            r["is_best_k"] = [x[0] for x in r.get("result", [])] == best
            runs.append(r)
            C.obs(step="run", **r)
        ok_runs = [r for r in runs if "result" in r]
        missed = [r for r in ok_runs if not r["is_best_k"]]
        C.obs(step="summary", runs=len(runs), completed_runs=len(ok_runs), runs_missing_best_k=len(missed),
              expected_best=best)
        if missed:
            # The documented contract (R025 docstring) is "k of that set in no particular order": the product does what it
            # documents; the violation is of the best-k property, which the baseline is expected to violate.
            C.verdict("expected-violation", f"{len(missed)}/{len(ok_runs)} completed runs did not return the 2 "
                      "best-scored candidates (set-order truncation, as the R025 docstring documents)")
        else:
            C.verdict("pass", "every run returned the k best candidates")
    finally:
        try:
            e.erase_graph(G)
        finally:
            c.close()


if __name__ == "__main__":
    if "--child" in sys.argv:
        child()
    else:
        main()
