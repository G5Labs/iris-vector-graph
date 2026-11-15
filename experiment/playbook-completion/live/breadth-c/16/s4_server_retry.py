"""HD-1603: does the Cypher HTTP server run a write a second time after an ambiguous failure?

    locks.sh iris timeout 600 python s4_server_retry.py

`_run_cypher` (iris_vector_graph/cypher_api.py:192-202) catches ANY exception from `engine.execute_cypher`, resets
the cached engine (closing its connection) and runs the same query once more. The fault injected here is a lost
acknowledgement: the real `execute_cypher` runs and commits against AUDITC, then the call raises ConnectionError, as a
dropped connection after the server-side commit would. The request goes through the real FastAPI app in this
process (ASGI test transport), so the server's own retry decides what happens. Nothing in the product is changed:
the fault is a wrapper around the engine method, installed only in this test process.

Cases (each with a control run without the fault):
  inc   MATCH ... SET n.counter = n.counter + 1     a non-idempotent update: one request, counter +2?
  anon  CREATE (n:C16R2 {name: 'dup'})              a create with no key: one request, two nodes?
  keyed CREATE (n:C16R3 {id: 'c16:r3'})             a create with an id: the retry hits the first attempt's row
Connections: the Lane connection, the app's engine (closed and reopened by the reset), the journal session: <= 4.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Lane, run_dir  # noqa: E402

OUT = run_dir("16")
R: dict = {"checks": {}}


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:700])


def main():
    os.environ.update(jsrv.iris_env())
    os.environ["BOLT_ENABLED"] = "0"
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)
    from starlette.testclient import TestClient
    from iris_vector_graph.engine import IRISGraphEngine
    import iris_vector_graph.cypher_api as capi

    orig = IRISGraphEngine.execute_cypher
    st = {"armed": False, "calls": 0, "faults": 0, "depth": 0}

    def faulty(self, query, *a, **kw):
        # execute_cypher re-enters itself for some statements; the fault fires only when the OUTERMOST call has
        # returned, i.e. after the engine committed (a first version raised inside a nested call, before the commit)
        st["calls"] += 1
        st["depth"] += 1
        try:
            res = orig(self, query, *a, **kw)
        finally:
            st["depth"] -= 1
        if st["armed"] and st["depth"] == 0:
            st["armed"] = False
            st["faults"] += 1
            raise ConnectionError("injected: the connection dropped after the server committed (acknowledgement lost)")
        return res
    IRISGraphEngine.execute_cypher = faulty

    L = Lane("c16")
    tc = TestClient(capi.app)  # no lifespan: no Bolt listener
    try:
        def post(q, armed):
            st["armed"], st["calls"] = armed, 0
            r = tc.post("/api/cypher", json={"query": q})
            return {"status": r.status_code, "body": r.json(), "engine_calls": st["calls"]}

        # inc
        L.eng.create_node("c16:r0", ["C16R"], {"counter": 0})
        q = "MATCH (n:C16R) WHERE n.id = 'c16:r0' SET n.counter = n.counter + 1 RETURN n.counter AS c"
        ctl = post(q, False)
        c1 = L.eng.get_node("c16:r0").get("counter")
        j = jsrv.journal_by_marker("POST /api/cypher SET counter+1 with lost ack", lambda: post(q, True), ["c16:r0", '"counter"'],
                                   L.smap)
        c2 = L.eng.get_node("c16:r0").get("counter")
        rec("inc", control=ctl, counter_after_control=c1, faulted=j["result"], counter_after_faulted=c2,
            commits=j["outermost_commits_by_pid"], pids=j["pids"],
            reproduced=(str(c2) == str(int(c1) + 2)), journal={k: v for k, v in j.items() if k != "raw_sample"})

        # anon
        q = "CREATE (n:C16R2 {name: 'dup'}) RETURN n.name AS name"
        ctl = post(q, False)
        n_ctl = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = 'C16R2'")[0][0]
        fl = post(q, True)
        n_f = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = 'C16R2'")[0][0]
        rec("anon", control=ctl, nodes_after_control=n_ctl, faulted=fl, nodes_after_faulted=n_f,
            reproduced=(n_f - n_ctl == 2))

        # keyed
        q = "CREATE (n:C16R3 {id: 'c16:r3'}) RETURN n.id AS id"
        fl = post(q, True)
        rows = L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id = 'c16:r3'")
        rec("keyed", faulted=fl, rows_in_db=rows,
            note="committed once; the answer the client gets after the server's retry is what matters here")
        R["faults_injected"] = st["faults"]
    finally:
        IRISGraphEngine.execute_cypher = orig
        try:
            with capi._engine_lock:
                capi._reset_engine()
        except Exception:
            pass
        cl = {}
        try:
            L.eng.execute_cypher("MATCH (n:C16R2) DETACH DELETE n")
        except Exception as e:
            cl["C16R2"] = str(e)
        for i in ("c16:r0", "c16:r3"):
            try:
                L.eng.delete_node(i)
            except Exception as e:
                cl[i] = str(e)
        R["cleanup_errors"] = cl
        R["left"] = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label IN ('C16R','C16R2','C16R3')")
        L.close()
        jsrv.dump(OUT / "s4_server_retry.json", R)


if __name__ == "__main__":
    main()
