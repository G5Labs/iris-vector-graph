"""W35: PLAID build/insert/search/info, F-0608's PLAID branch (run-isolated retest fixture only)."""
import json, os, sys, time, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-25"))
import runtime  # noqa: E402
RUN = os.environ.get("W35_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
def hits(h): return [(x["id"], round(x["score"], 6)) for x in h] if isinstance(h, list) else h
def main():
    c = runtime.connect(); e = runtime.engine(c); out = {"run": RUN, "fixture": runtime.NAME, "steps": {}}
    def step(k, fn):
        try: out["steps"][k] = fn()
        except Exception as x: out["steps"][k] = f"RAISED {type(x).__name__}: {str(x)[:300]}"
    bad = f"pl{TAG}bad"
    step("P1_build_mixed_width", lambda: e.plaid_build(bad, [{"id": "a", "tokens": [[1, 0, 0], [0, 1]]}, {"id": "b", "tokens": [[0, 0, 1]]}], n_clusters=2))
    step("P1_info", lambda: e.plaid_info(bad))
    n = f"pl{TAG}ix"
    docs = [{"id": "d1", "tokens": [[1, 0, 0], [0.9, 0.1, 0]]}, {"id": "d2", "tokens": [[0, 1, 0], [0.1, 0.9, 0]]},
            {"id": "d3", "tokens": [[0, 0, 1]]}, {"id": "d4", "tokens": [[0.5, 0.5, 0]]}]
    step("build", lambda: e.plaid_build(n, docs, n_clusters=3))
    step("info0", lambda: e.plaid_info(n))
    step("P2_insert_new", lambda: (e.plaid_insert(n, "d5", [[0, 0.7, 0.7], [0, 0.6, 0.8]]), "ok")[1])
    step("P2_info", lambda: e.plaid_info(n))
    step("P2_search", lambda: hits(e.plaid_search(n, [[0, 0.7, 0.7]], k=3, nprobe=3)))
    step("P3_before_search_old_dir", lambda: hits(e.plaid_search(n, [[1, 0, 0]], k=5, nprobe=3)))
    step("P3_reinsert_d1_elsewhere", lambda: (e.plaid_insert(n, "d1", [[0, 0, 1]]), "ok")[1])
    step("P3_info", lambda: e.plaid_info(n))
    step("P3_search_old_dir", lambda: hits(e.plaid_search(n, [[1, 0, 0]], k=5, nprobe=3)))
    step("P3_search_new_dir", lambda: hits(e.plaid_search(n, [[0, 0, 1]], k=5, nprobe=3)))
    step("P4_insert_2wide", lambda: (e.plaid_insert(n, "d6", [[1, 0]]), "ok")[1])
    step("P4_info", lambda: e.plaid_info(n))
    step("P4_search", lambda: hits(e.plaid_search(n, [[1, 0, 0.5]], k=6, nprobe=3)))
    step("P5_unknown", lambda: {"search": hits(e.plaid_search(f"pl{TAG}none", [[1, 0, 0]])), "info": e.plaid_info(f"pl{TAG}none")})
    for x in (bad, n):
        try: e.plaid_drop(x)
        except Exception: pass
    c.close(); path = HERE / f"plaid-observed-{RUN}.json"; path.write_text(json.dumps(out, indent=1, default=str) + "\n"); print(path)
    for k, v in out["steps"].items(): print("==", k, json.dumps(v, default=str)[:400])
if __name__ == "__main__":
    main()
