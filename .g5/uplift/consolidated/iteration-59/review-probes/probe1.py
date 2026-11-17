"""Reviewer probe (review-56-58), fixture ivg-cont-20261117-iris, USER, prefix rv58_. No sync()."""
import asyncio, json, os, socket, sys, threading, time, traceback
REPO = os.environ["IVG_REPO"]
sys.path.insert(0, REPO + "/.g5/Verus_verification/tools"); sys.path.insert(0, REPO + "/.g5/uplift/consolidated/iteration-36")
import binding_common as bc
bc.import_pin()
import runtime
from iris_vector_graph.engine import IRISGraphEngine

TAG = time.strftime("%H%M%S", time.gmtime())
P = f"rv58_{TAG}_"
out = {"tag": TAG}

def err(x): return {"err": type(x).__name__, "msg": str(x)[:300]}

c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=False)
c3 = runtime.connect(); e3 = IRISGraphEngine(c3, embedding_dimension=768, native_cypher=False)

def count(label):
    r = e3.execute_cypher(f"MATCH (n:{label}) RETURN count(n) AS c", {})
    return r.rows[0][0] if r.rows else r.error

# ---- A. bug-plt-127 via neo4j driver against the product's TCP Bolt listener
try:
    import neo4j
    from iris_vector_graph import bolt_server as bs
    c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
    s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"): os.environ.pop(k, None)
    srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
    d = neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"), connection_timeout=10)
    L = f"RV58{TAG}Rb"
    with d.session() as s:
        tx = s.begin_transaction(); tx.run(f"CREATE (:{L} {{id:'{P}rb0'}})").consume(); tx.rollback()
    time.sleep(0.2); out["A_rollback_count"] = count(L)
    L2 = f"RV58{TAG}Cm"
    with d.session() as s:
        tx = s.begin_transaction(); tx.run(f"CREATE (:{L2} {{id:'{P}cm0'}})").consume(); tx.commit()
    time.sleep(0.2); out["A_commit_count"] = count(L2)
    # neighbor: read inside an open tx sees nothing of other ... skip; uncommitted visibility from other session BEFORE rollback
    L3 = f"RV58{TAG}Vis"
    with d.session() as s:
        tx = s.begin_transaction(); tx.run(f"CREATE (:{L3} {{id:'{P}vis0'}})").consume()
        out["A_visible_to_other_before_end"] = count(L3)
        tx.rollback()
    d.close(); srv.close(); loop.call_soon_threadsafe(loop.stop)
except Exception as x:
    out["A_error"] = err(x); traceback.print_exc()

# ---- B. HTTP /db/neo4j/tx/commit batch with a failing middle statement
try:
    os.environ.update(IRIS_HOST="127.0.0.1", IRIS_PORT=str(runtime.PORT), IRIS_NAMESPACE="USER", IRIS_USERNAME="_SYSTEM", IRIS_PASSWORD="SYS")
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api
    LB = f"RV58{TAG}Http"
    with TestClient(cypher_api.app) as client:
        t = client.post("/db/neo4j/tx/commit", json={"statements": [
            {"statement": f"CREATE (:{LB} {{id:'{P}h1'}})", "parameters": {}},
            {"statement": "RETURN 1 AS a UNION RETURN 2 AS b", "parameters": {}},
            {"statement": f"CREATE (:{LB} {{id:'{P}h3'}})", "parameters": {}},
        ]})
        out["B_status"] = t.status_code; out["B_body"] = json.dumps(t.json())[:400]
    out["B_count_after"] = count(LB)
except Exception as x:
    out["B_error"] = err(x); traceback.print_exc()

# ---- C. bug-srch-116 place_quarantined over DB-API
try:
    cur = c.cursor()
    qt = e._quarantine_table()
    cur.execute(f"INSERT INTO {qt} (node_id, source_table, emb, dimension, dtype, reason) VALUES (?, 'kg_NodeEmbeddings', TO_VECTOR('1,0,0,0', DOUBLE), 4, 'DOUBLE', 'no_node')", [P + "q1"])
    c.commit()
    cur.execute(f"SELECT q_rowid FROM {qt} WHERE node_id = ?", [P + "q1"]); qid = int(cur.fetchone()[0]); cur.close()
    out["C_qid"] = qid
    try:
        out["C_place"] = e.place_quarantined(qid, graph="rv58_nograph", model_key="rv58_nomodel")
    except Exception as x:
        out["C_place"] = err(x)
    try:
        out["C_place_missing"] = e.place_quarantined(999999999, graph="rv58_nograph", model_key="rv58_nomodel")
    except Exception as x:
        out["C_place_missing"] = err(x)
    cur = c.cursor(); cur.execute(f"SELECT COUNT(*) FROM {qt} WHERE node_id = ?", [P + "q1"]); out["C_row_kept"] = int(cur.fetchone()[0])
    cur.execute(f"DELETE FROM {qt} WHERE node_id = ?", [P + "q1"]); c.commit(); cur.close()
except Exception as x:
    out["C_error"] = err(x); traceback.print_exc()

# ---- D. W62: bug-cyp-155 and openCypher neighbors (SQL path, driver 5.3.2)
LD = f"RV58{TAG}V"
e.execute_cypher(f"CREATE (:{LD} {{id:'{P}d1', v: 3, f: 2.5, b: true, s: 'x'}})")
e.execute_cypher(f"CREATE (:{LD} {{id:'{P}d2', s: 'y'}})")
Q = {
    "D_with_coalesce": f"MATCH (n:{LD} {{id:'{P}d1'}}) WITH coalesce(n.v, n.s) AS x RETURN x",
    "D_ret_coalesce": f"MATCH (n:{LD} {{id:'{P}d1'}}) RETURN coalesce(n.v, n.s) AS x",
    "D_with_coalesce_float": f"MATCH (n:{LD} {{id:'{P}d1'}}) WITH coalesce(n.f, 0) AS x RETURN x",
    "D_with_coalesce_bool_where": f"MATCH (n:{LD}) WITH n, coalesce(n.v, 0) AS x WHERE x > 2 RETURN n.id AS id",
    "D_with_coalesce_arith": f"MATCH (n:{LD} {{id:'{P}d1'}}) WITH coalesce(n.v, 0) AS x RETURN x + 1 AS y",
    "D_with_prop_then_arith": f"MATCH (n:{LD} {{id:'{P}d1'}}) WITH n.v AS x RETURN x + 1 AS y",
    "D_case": f"MATCH (n:{LD} {{id:'{P}d1'}}) RETURN CASE WHEN n.v > 1 THEN n.b ELSE n.s END AS x",
    "D_unwind_int_float_group": "UNWIND [1, 1.0, 2] AS x RETURN x, count(*) AS c ORDER BY c DESC",
    "D_unwind_int_float_distinct": "UNWIND [1, 1.0] AS x RETURN DISTINCT x",
    "D_union_int_float": "RETURN 1 AS x UNION RETURN 1.0 AS x",
    "D_union_lists": "RETURN [1,2] AS x UNION RETURN [1,2] AS x",
    "D_order_mixed": "UNWIND [2, 'a', null, 1.5, true] AS x RETURN x ORDER BY x",
    "D_optional_count": f"MATCH (n:{LD} {{id:'{P}d2'}}) OPTIONAL MATCH (n)-[:RV58NONE]->(m) RETURN count(m) AS c, collect(m.id) AS l",
    "D_foreach_null": f"MATCH (n:{LD} {{id:'{P}d2'}}) FOREACH (x IN null | SET n.z = x) RETURN n.id AS id",
    "D_call_sub_count": "UNWIND [1,2] AS i CALL { WITH i UNWIND range(1, i) AS j RETURN count(j) AS c } RETURN i, c",
    "D_with_star": f"MATCH (n:{LD} {{id:'{P}d1'}}) WITH * RETURN n.v AS v",
}
for k, q in Q.items():
    try:
        r = e.execute_cypher(q)
        out[k] = {"rows": r.rows, "error": r.error}
    except Exception as x:
        out[k] = err(x)
# SET += with a null value: openCypher removes the property
try:
    e.execute_cypher(f"MATCH (n:{LD} {{id:'{P}d1'}}) SET n += {{s: null, t: 'new'}}")
    r = e.execute_cypher(f"MATCH (n:{LD} {{id:'{P}d1'}}) RETURN n.s AS s, n.t AS t, n.v AS v")
    out["D_set_plus_null"] = {"rows": r.rows, "error": r.error}
except Exception as x:
    out["D_set_plus_null"] = err(x)

fn = f"/tmp/review-56-58/probes/probe1-{TAG}.json"
json.dump(out, open(fn, "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
