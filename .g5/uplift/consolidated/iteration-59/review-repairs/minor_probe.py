"""Iteration 59: reproduce review 56-58 G2 (CALL { } importing an UNWIND variable), G3 (ORDER BY over a held list with
booleans and numbers) and the bug-cyp-138 addition (literal lists in UNION), on both engines (native off / on), with
neighbors. Fixture ivg-cont-20261117-iris, USER; read-only queries plus nodes under prefix i59m_."""
import json, os, sys, time
from pathlib import Path
REPO = Path(os.environ.get("IVG_REPO", Path(__file__).resolve().parents[5]))
sys.path.insert(0, str(REPO / ".g5/Verus_verification/tools")); sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import binding_common as bc  # noqa
PIN = bc.import_pin()
import runtime  # noqa
c = runtime.connect()
from iris_vector_graph.engine import IRISGraphEngine
ENG = {m: IRISGraphEngine(c, embedding_dimension=768, native_cypher=(m == "1")) for m in ("0", "1")}
e = ENG["0"]
TAG = time.strftime("%H%M%S", time.gmtime()); P = f"i59m_{TAG}_"
e.create_node(P + "a", labels=[f"I59M{TAG}"], properties={"v": 1})
Q = {
 "G2_unwind_import": "UNWIND [1,2] AS i CALL { WITH i RETURN i*2 AS d } RETURN i, d",
 "G2_unwind_import_unwind": "UNWIND [1,2] AS i CALL { WITH i UNWIND range(1,i) AS j RETURN count(j) AS c } RETURN i, c",
 "G2_neighbor_match_import": f"MATCH (n:I59M{TAG}) CALL {{ WITH n RETURN n.v * 2 AS d }} RETURN d",
 "G2_neighbor_no_import": "UNWIND [1,2] AS i CALL { RETURN 5 AS d } RETURN i, d",
 "G2_neighbor_match_import_match": f"MATCH (n:I59M{TAG}) CALL {{ WITH n MATCH (n)-[:R59]->(m) RETURN count(m) AS c }} RETURN c",
 "G2_unwind_import_match": f"UNWIND ['{P}a', '{P}zz'] AS k CALL {{ WITH k MATCH (m {{id: k}}) RETURN count(m) AS c }} RETURN k, c",
 "G3_mixed": "UNWIND [2,'a',null,1.5,true] AS x RETURN x ORDER BY x",
 "G3_mixed_desc": "UNWIND [2,'a',null,1.5,true] AS x RETURN x ORDER BY x DESC",
 "G3_bools_numbers": "UNWIND [2,true,0.5,false] AS x RETURN x ORDER BY x",
 "G3_neighbor_numbers": "UNWIND [2,0.5,1] AS x RETURN x ORDER BY x",
 "G3_neighbor_after_with": "UNWIND [2,'a',null,1.5,true] AS x WITH x ORDER BY x RETURN x",
 "U_list_union": "RETURN [1,2] AS x UNION RETURN [3] AS x",
 "U_list_union_all": "RETURN [1,2] AS x UNION ALL RETURN [1,2] AS x",
 "U_neighbor_list_alone": "RETURN [1,2] AS x",
 "U_neighbor_scalar_union": "RETURN 1 AS x UNION RETURN 2 AS x",
 "m3_unwind_distinct": "UNWIND [1, 1.0] AS x RETURN DISTINCT x",
 "m3_union_1_10": "RETURN 1 AS x UNION RETURN 1.0 AS x",
}
out = {"tag": TAG, "fixture": runtime.NAME, "pin": bc.pin_identity(PIN)}
for mode in ("0", "1"):
    e = ENG[mode]
    for k, q in Q.items():
        try:
            r = e.execute_cypher(q, {})
            err = getattr(r, "error", None)
            out[f"{k}|native={mode}"] = {"error": err} if err else {"rows": [[repr(v) for v in row] for row in r.rows]}
        except Exception as x:
            out[f"{k}|native={mode}"] = {"raised": f"{type(x).__name__}: {str(x)[:200]}"}
dst = Path(__file__).with_name(f"minor-observed-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json")
dst.write_text(json.dumps(out, indent=1)); print(dst)
for k, v in out.items():
    if "|" in k: print(k, json.dumps(v)[:220])
