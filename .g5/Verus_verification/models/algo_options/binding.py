"""algo_options binding: each (procedure, option, value) of the W33 matrix through the actual engine method and the
actual Cypher CALL ivg.* on the run-isolated retest fixture; accept/refuse and, when accepted, the row count are
compared with a port of algo_options.rs (float options gamma and tol by the model's documented bounds). Six port
mutations mirror the controls. Ordinary data, fixture only."""
import hashlib, json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-28")); sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-25"))
import runtime  # noqa: E402
import algo_options_probe as probe  # noqa: E402  (the frozen W33 matrix and its two callers)
RUN = os.environ.get("AO_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
RANGES = {"topK": (0, 1_000_000), "maxHops": (0, 1000), "sampleSize": (0, 1_000_000), "maxIter": (1, 1000), "maxLevels": (1, 100),
          "memBudgetMB": (16, 8192), "randomSeed": (0, 2**32 - 1)}
def coerce(v):
    if isinstance(v, bool): return int(v)
    if isinstance(v, int): return v
    if isinstance(v, float): return int(v) if v == int(v) else None
    if isinstance(v, str):
        try: return int(v)
        except ValueError: return None
    return None
def model_ok(o, v, m):
    if o == "direction": return v in ("out", "in", "both")
    if o == "formula": return (v != "") if m.get("formula_any_case") else v in ("harmonic", "classical")
    if o == "predicate": return True
    if o == "gamma": return isinstance(v, (int, float)) and 0 < v <= 100
    if o == "tol": return isinstance(v, (int, float)) and 0 < v < 1
    n = coerce(v)
    if n is None: return bool(m.get("uncoercible_accepted"))
    lo, hi = RANGES.get(o, (1, 0))
    if o == "topK" and m.get("topk_from_one"): lo = 1
    if o == "maxIter" and m.get("maxiter_unbounded"): hi = 10**12
    return lo <= n <= hi
def decisions(proc, o, v, m):
    listed = o in probe.PROCS[proc][1]
    keyword = listed and not (m.get("keyword_differs") and o == "memBudgetMB")
    py = keyword and model_ok(o, v, m)
    cy = listed and (model_ok(o, v, m) if not m.get("cypher_skips_model") else (o != "direction" or v in ("out", "in", "both")))
    return py, cy
MUTS = ["cypher_skips_model", "keyword_differs", "topk_from_one", "maxiter_unbounded", "uncoercible_accepted", "formula_any_case"]
CASES = probe.CASES + [("ivg.betweenness", "memBudgetMB", 16), ("ivg.leiden", "gamma", 0.5), ("ivg.eigenvector", "tol", 0.5),
                       ("ivg.leiden", "tol", 1), ("ivg.degreeCentrality", "topK", "x")]
def main():
    t0 = time.time(); c = runtime.connect(); e = runtime.engine(c)
    cells, mism, sens = [], [], {m: 0 for m in MUTS}
    for proc, o, v in CASES:
        meth, names = probe.PROCS[proc]
        py = probe.outcome(lambda: getattr(e, meth)(**{names.get(o, o): v}))
        cy = probe.outcome(lambda: e.execute_cypher(f"CALL {proc}({{{o}: {probe.lit(v)}}}) YIELD node RETURN node"))
        got = (py[0] == "ok", cy[0] == "ok")
        rows_agree = (not all(got)) or py[1] == cy[1]
        want = decisions(proc, o, v, {})
        cell = {"procedure": proc, "option": o, "value": v, "python": py, "cypher": cy, "accepted": got, "expected": want, "rows_agree": rows_agree}
        cells.append(cell)
        if tuple(got) != tuple(want) or not rows_agree: mism.append(cell)
        for m in MUTS:
            if tuple(decisions(proc, o, v, {m: True})) != tuple(got): sens[m] += 1
    c.close()
    body = {"kind": "binding", "model": "algo_options", "fixture": runtime.NAME, "port": runtime.PORT, "product_baseline": runtime.PRODUCT, "run": RUN,
            "verdict": "AGREES" if not mism else "DISAGREES", "cases": len(cells), "comparisons": 2 * len(cells), "mismatches": mism,
            "sensitivities_detected_cases": sens, "all_sensitivities_detected": all(v > 0 for v in sens.values()), "cells": cells,
            "elapsed_s": round(time.time() - t0, 1),
            "inputs": {**{str(p.relative_to(REPO)): sha(p) for p in [HERE / "binding.py", HERE / "algo_options.rs", HERE / "model.json",
                       REPO / ".g5/uplift/consolidated/iteration-28/algo_options_probe.py"]},
                       **{q: sha(Path(runtime.PIN) / q) for q in ["iris_vector_graph/_validate.py", "iris_vector_graph/cypher/translator.py",
                          "iris_vector_graph/_engine/algorithms.py"]}},
            "scope": "Actual engine methods and Cypher CALL ivg.* (eight centrality and community procedures) on IRIS 2026.1, pin 3eaa79cf; "
                     "one option per call over the default graph. gds.* shims and ivg.ppr/pagerank are outside this binding."}
    out = REPO / ".g5/Verus_verification/results/algo_options" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-binding")
    out.mkdir(parents=True); (out / "receipt.json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "cases", "comparisons", "all_sensitivities_detected", "sensitivities_detected_cases", "elapsed_s")}))
    for x in mism[:5]: print("MISMATCH", json.dumps(x, default=str)[:500])
if __name__ == "__main__":
    main()
