"""W33: the same algorithm option value through the engine method and Cypher CALL ivg.* (run-isolated fixture only)."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W33_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
PROCS = {  # Cypher name -> (engine method, {cypher option: python keyword})
 "ivg.degreeCentrality": ("degree_centrality", {"direction": "direction", "predicate": "predicate", "topK": "top_k"}),
 "ivg.betweenness": ("betweenness_centrality", {"sampleSize": "sample_size", "direction": "direction", "maxHops": "max_hops", "topK": "top_k", "memBudgetMB": "mem_budget_mb"}),
 "ivg.closeness": ("closeness_centrality", {"formula": "formula", "direction": "direction", "maxHops": "max_hops", "topK": "top_k"}),
 "ivg.eigenvector": ("eigenvector_centrality", {"maxIter": "max_iter", "tol": "tol", "topK": "top_k"}),
 "ivg.leiden": ("leiden_communities", {"maxLevels": "max_levels", "gamma": "gamma", "tol": "tol", "topK": "top_k", "randomSeed": "random_seed"}),
 "ivg.triangleCount": ("triangle_count", {"topK": "top_k"}),
 "ivg.scc": ("strongly_connected_components", {"topK": "top_k"}),
 "ivg.kcore": ("k_core", {"topK": "top_k"}),
}
CASES = [("ivg.closeness", "formula", "bogus"), ("ivg.closeness", "formula", "Classical"), ("ivg.closeness", "formula", "classical"),
 ("ivg.eigenvector", "maxIter", 0), ("ivg.eigenvector", "maxIter", 1001), ("ivg.eigenvector", "maxIter", 1000), ("ivg.eigenvector", "tol", 0),
 ("ivg.degreeCentrality", "direction", "sideways"), ("ivg.degreeCentrality", "direction", "OUT"), ("ivg.betweenness", "direction", "sideways"),
 ("ivg.closeness", "direction", "sideways"), ("ivg.degreeCentrality", "foo", 1), ("ivg.closeness", "foo", 1),
 ("ivg.degreeCentrality", "topK", 0), ("ivg.degreeCentrality", "topK", -1), ("ivg.degreeCentrality", "topK", "2"), ("ivg.degreeCentrality", "topK", 2.0),
 ("ivg.degreeCentrality", "topK", 2.5), ("ivg.degreeCentrality", "topK", True), ("ivg.degreeCentrality", "topK", 2),
 ("ivg.betweenness", "sampleSize", -1), ("ivg.betweenness", "sampleSize", 2.7), ("ivg.betweenness", "maxHops", 0), ("ivg.betweenness", "maxHops", -1),
 ("ivg.betweenness", "maxHops", 1001), ("ivg.betweenness", "memBudgetMB", 8), ("ivg.closeness", "maxHops", -1),
 ("ivg.leiden", "gamma", 0), ("ivg.leiden", "gamma", -1), ("ivg.leiden", "maxLevels", 0), ("ivg.leiden", "randomSeed", -1), ("ivg.leiden", "topK", 2),
 ("ivg.triangleCount", "topK", -1), ("ivg.scc", "topK", -1), ("ivg.kcore", "topK", -1), ("ivg.kcore", "topK", 2)]
def lit(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, str): return "'" + v + "'"
    return repr(v)
def outcome(fn):
    try:
        r = fn()
        rows = r.rows if hasattr(r, "rows") else (r.get("rows") if isinstance(r, dict) else r)
        err = getattr(r, "error", None) if hasattr(r, "error") else None
        if err: return ["result.error", str(err)[:160]]
        return ["ok", len(rows) if rows is not None else None]
    except Exception as x:
        return ["raised", type(x).__name__, str(x)[:200]]
def main():
    c = runtime.connect(); e = runtime.engine(c)
    for a, b in [("t1", "t2"), ("t2", "t3"), ("t3", "t1"), ("t3", "t4")]:
        for n in (a, b): e.create_node(f"w33{TAG}{n}")
        e.create_edge(f"w33{TAG}{a}", "W33R", f"w33{TAG}{b}")
    try: e.sync()
    except Exception as x: print("sync", x)
    out = {"run": RUN, "fixture": runtime.NAME, "cells": []}
    for proc, opt, val in CASES:
        meth, names = PROCS[proc]
        py = outcome(lambda: getattr(e, meth)(**{names.get(opt, opt): val}))
        cy = outcome(lambda: e.execute_cypher(f"CALL {proc}({{{opt}: {lit(val)}}}) YIELD node RETURN node"))
        same = (py[0] == "ok") == (cy[0] == "ok") and (py[0] != "ok" or py[1] == cy[1])
        out["cells"].append({"procedure": proc, "option": opt, "value": val, "python": py, "cypher": cy, "same_decision": same})
        print(f"{proc:22s} {opt:11s} {val!r:11s} same={same!s:5s} py={py} cy={cy}"[:330])
    c.close(); path = HERE / f"algo-options-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
if __name__ == "__main__":
    main()
