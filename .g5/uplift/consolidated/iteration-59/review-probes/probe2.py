import json, os, sys, time
REPO = os.environ["IVG_REPO"]
sys.path.insert(0, REPO + "/.g5/Verus_verification/tools"); sys.path.insert(0, REPO + "/.g5/uplift/consolidated/iteration-36")
import binding_common as bc
bc.import_pin()
import runtime
from iris_vector_graph.engine import IRISGraphEngine
TAG = time.strftime("%H%M%S", time.gmtime())
out = {}
for native in (False, True):
    c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=native)
    Q = {
     "order_mixed": "UNWIND [2, 'a', null, 1.5, true] AS x RETURN x ORDER BY x",
     "order_mixed_desc": "UNWIND [2, 'a', null, 1.5, true] AS x RETURN x ORDER BY x DESC",
     "order_bool_num": "UNWIND [2, true, 0.5, false] AS x RETURN x ORDER BY x",
     "order_str_num": "UNWIND ['b', 1, 'a', 3] AS x RETURN x ORDER BY x",
     "with_list_order": "WITH [2, 'a', 1.5, true] AS l UNWIND l AS x RETURN x ORDER BY x",
     "ret_list": "RETURN [1,2] AS x",
     "union_lists": "RETURN [1,2] AS x UNION RETURN [3] AS x",
     "union_all_float_int": "RETURN 1.5 AS x UNION ALL RETURN 2 AS x",
     "call_unwind_count": "CALL { UNWIND [1,2,3] AS j RETURN count(j) AS c } RETURN c",
     "call_with_i": "UNWIND [1,2] AS i CALL { WITH i RETURN i * 2 AS d } RETURN i, d",
     "call_with_i_unwind": "UNWIND [1,2] AS i CALL { WITH i UNWIND range(1, i) AS j RETURN count(j) AS c } RETURN i, c",
    }
    for k, q in Q.items():
        try:
            r = e.execute_cypher(q); out[f"{'NAT' if native else 'SQL'}_{k}"] = {"rows": r.rows, "error": (str(r.error)[:200] if r.error else None)}
        except Exception as x:
            out[f"{'NAT' if native else 'SQL'}_{k}"] = {"exc": type(x).__name__, "msg": str(x)[:200]}
    c.close()
json.dump(out, open(f"/tmp/review-56-58/probes/probe2-{TAG}.json", "w"), indent=1, default=str)
for k, v in out.items(): print(k, json.dumps(v, default=str)[:300])
