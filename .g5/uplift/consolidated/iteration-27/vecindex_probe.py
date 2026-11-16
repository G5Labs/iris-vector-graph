"""W32: VecIndex lifecycle through vec_search / vec_info / vec_expand (run-isolated retest fixture only)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W32_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def ids(hits): return [(h["id"], round(h["score"], 6), round(h["distance"], 6)) for h in hits] if isinstance(hits, list) else hits
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}
    def case(name, fn):
        try: out["cases"][name] = fn()
        except Exception: out["cases"][name] = {"exception": traceback.format_exc()[-1200:]}
    V = {"a": [1, 0, 0], "b": [0.9, 0.1, 0], "c": [0, 1, 0], "d": [0, 0, 1]}; q = [1, 0.05, 0]
    def lifecycle():
        n = f"vx{TAG}life"; r = {}
        r["create"] = e.vec_create_index(n, 3)
        for k, v in V.items(): e.vec_insert(n, k, v)
        r["V1_no_build"] = ids(e.vec_search(n, q, k=2)); r["info0"] = e.vec_info(n)
        r["build"] = e.vec_build(n); r["V2_built"] = ids(e.vec_search(n, q, k=2))
        e.vec_insert(n, "z", q); r["V3_after_insert"] = ids(e.vec_search(n, q, k=2))
        r["build2"] = e.vec_build(n); r["V4_rebuilt"] = ids(e.vec_search(n, q, k=2))
        r["V5_k10"] = ids(e.vec_search(n, q, k=10)); r["V8_expand"] = ids(e.vec_expand(n, "a", k=2))
        r["info_before_reinsert"] = e.vec_info(n)
        e.vec_insert(n, "a", [0, 1, 0]); r["V9_after_reinsert_info"] = e.vec_info(n); r["V9_search"] = ids(e.vec_search(n, [0, 1, 0], k=10))
        r["V10_recreate"] = e.vec_create_index(n, 3); r["V10_info"] = e.vec_info(n); r["V10_search"] = ids(e.vec_search(n, q, k=10))
        try: e.vec_insert(n, "w", [1, 0]); r["V11_insert"] = "accepted"
        except Exception as x: r["V11_insert"] = f"{type(x).__name__}: {str(x)[:200]}"
        r["V11_info"] = e.vec_info(n)
        try: r["V11_search3"] = ids(e.vec_search(n, q, k=10))
        except Exception as x: r["V11_search3"] = f"{type(x).__name__}: {str(x)[:200]}"
        e.vec_drop(n)
        try: r["V12_after_drop"] = ids(e.vec_search(n, q, k=3))
        except Exception as x: r["V12_after_drop"] = f"{type(x).__name__}: {str(x)[:200]}"
        r["V12_info"] = e.vec_info(n)
        return r
    case("lifecycle", lifecycle)
    def metrics():
        r = {}; W = {"near": [1, 0.1, 0], "long": [5, 3, 0], "far": [0, 1, 0]}
        for m in ("cosine", "dot", "l2"):
            n = f"vx{TAG}{m}"; e.vec_create_index(n, 3, metric=m)
            for k, v in W.items(): e.vec_insert(n, k, v)
            r[m] = ids(e.vec_search(n, [1, 0, 0], k=3)); e.vec_drop(n)
        return r
    case("V6_V7_metrics", metrics)
    c.close(); path = HERE / f"vecindex-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["cases"].items():
        print("==", k)
        for kk, vv in (v.items() if isinstance(v, dict) else []): print("  ", kk, json.dumps(vv, default=str)[:300])
if __name__ == "__main__":
    main()
