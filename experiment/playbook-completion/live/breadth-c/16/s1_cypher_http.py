"""Live checks of the Cypher HTTP server (iris_vector_graph.cypher_api) and its Bolt TCP listener on AUDITC.

    flock -s $RUN_DIR/breadth-c/auditc.lock timeout 1200 python s1_cypher_http.py

Three server runs, each started here on 127.0.0.1 and stopped by PID:
  A  no key:            health, /api/cypher write (journal), syntax error, /db/neo4j/tx/commit with a failing middle
                        statement (F-1610, journal), Bolt explicit transaction + ROLLBACK (F-1601, journal), Bolt PULL
                        with fetch_size 2 over 3 rows (F-1602), Bolt FAILURE code, UNWIND parity (F-1607 input)
  B  IVG_API_KEY set:   missing key -> 401, wrong key -> 401, key -> 200, /health public; Bolt wrong key -> FAILURE
  C  key + read-only:   Cypher write -> 403, tx/commit write -> 403, /admin/load -> 403, Bolt write -> AccessMode
Scratch ids start with c16 and are removed at the end.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Lane, run_dir  # noqa: E402

import httpx  # noqa: E402

OUT = run_dir("16")
HTTP, BOLT = 18610, 18611
KEY = "c16-secret-key"
R: dict = {"checks": {}}


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:600])


def count_ids(L, ids):
    q = "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id IN (%s)" % ",".join("?" * len(ids))
    return L.c.sql(q, *ids)


def server(tag, extra):
    env = jsrv.iris_env()
    env.update({"BOLT_TCP_HOST": "127.0.0.1", "BOLT_TCP_PORT": str(BOLT)})
    env.update(extra)
    return jsrv.start(tag, ["-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1",
                            "--port", str(HTTP)], env, HTTP, OUT / f"s1_server_{tag}.log")


def main():
    from neo4j import GraphDatabase
    L = Lane("c16")
    smap = L.smap
    url = f"http://127.0.0.1:{HTTP}"
    p = None
    try:
        # ---------------------------------------------------------------- A: no key
        p = server("A", {})
        R["server_A_pid"] = p.pid
        r = httpx.get(url + "/health", timeout=30)
        rec("A.health", status=r.status_code, body=r.json())

        q = "CREATE (n:C16H {id: 'c16:h1', name: 'h'}) RETURN n.id AS id"
        j = jsrv.journal_by_marker("POST /api/cypher write", lambda: httpx.post(
            url + "/api/cypher", json={"query": q}, timeout=60).json(), ["c16:h1"], smap)
        rec("A.api_cypher_write", journal=j)

        r = httpx.post(url + "/api/cypher", json={"query": "MATCH (n RETURN n"}, timeout=60)
        rec("A.api_cypher_syntax_error", status=r.status_code, body=r.json())

        stmts = [{"statement": "CREATE (n:C16T {id: 'c16:t1'}) RETURN n.id AS id"},
                 {"statement": "THIS IS NOT CYPHER"},
                 {"statement": "CREATE (n:C16T {id: 'c16:t3'}) RETURN n.id AS id"}]
        resp = {}

        def txc():
            rr = httpx.post(url + "/db/neo4j/tx/commit", json={"statements": stmts}, timeout=60)
            resp["status"], resp["body"] = rr.status_code, rr.json()
            return rr.status_code
        j = jsrv.journal_by_marker("POST /db/neo4j/tx/commit (3 statements, 2nd fails)", txc, ["c16:t1", "c16:t3"],
                                   smap)
        persisted = count_ids(L, ["c16:t1", "c16:t3"])
        rec("A.F1610_tx_commit_partial", http_status=resp["status"], body=resp["body"], persisted=persisted,
            reproduced=bool(persisted) and resp["status"] == 400, journal=j)

        drv = GraphDatabase.driver(f"bolt://127.0.0.1:{BOLT}", auth=("neo4j", "x"))
        try:
            def bolt_tx_rollback():
                with drv.session() as s:
                    tx = s.begin_transaction()
                    tx.run("CREATE (n:C16B {id: 'c16:b1'}) RETURN n.id AS id").consume()
                    tx.rollback()
                return "rolled back"
            j = jsrv.journal_by_marker("Bolt BEGIN; RUN CREATE; ROLLBACK", bolt_tx_rollback, ["c16:b1"], smap)
            with drv.session() as s:
                n_after = s.run("MATCH (n:C16B) WHERE n.id = 'c16:b1' RETURN count(n) AS c").single()["c"]
            rec("A.F1601_bolt_rollback", node_count_after_rollback=n_after, reproduced=n_after == 1,
                db_rows=count_ids(L, ["c16:b1"]), journal=j)

            # managed transaction with a failing second statement: the first statement's write survives
            def work(tx):
                tx.run("CREATE (n:C16B {id: 'c16:b2'}) RETURN n.id AS id").consume()
                tx.run("THIS IS NOT CYPHER").consume()
            err = None
            try:
                with drv.session() as s:
                    s.execute_write(work)
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:300]}"
            rec("A.F1601_bolt_managed_tx_failure", driver_error=err, db_rows=count_ids(L, ["c16:b2"]),
                reproduced=bool(count_ids(L, ["c16:b2"])))

            for i in (1, 2, 3):
                L.eng.create_node(f"c16:f{i}", labels=["C16F"])
            with drv.session(fetch_size=2) as s:
                rows = [r["id"] for r in s.run("MATCH (n:C16F) RETURN n.id AS id ORDER BY id")]
            with drv.session() as s:
                rows_default = [r["id"] for r in s.run("MATCH (n:C16F) RETURN n.id AS id ORDER BY id")]
            rec("A.F1602_pull_n", fetch_size=2, rows=rows, rows_default_fetch=rows_default,
                reproduced=len(rows) == 2 and len(rows_default) == 3)

            err = None
            try:
                with drv.session() as s:
                    s.run("MATCH (n RETURN n").consume()
            except Exception as e:
                err = {"type": type(e).__name__, "code": getattr(e, "code", None), "msg": str(e)[:200]}
            rec("A.bolt_syntax_error_failure_code", error=err)
        finally:
            drv.close()

        params = {"p": ["[2]", [2], True, "1"]}
        r = httpx.post(url + "/api/cypher", json={"query": "UNWIND $p AS e RETURN e", "parameters": params},
                       timeout=60)
        eng_rows = L.eng.execute_cypher("UNWIND $p AS e RETURN e", parameters=params).rows
        rec("A.unwind_mixed_param", http_rows=r.json().get("rows"), engine_rows=eng_rows)
        jsrv.stop(p)
        p = None

        # ---------------------------------------------------------------- B: key set
        p = server("B", {"IVG_API_KEY": KEY})
        R["server_B_pid"] = p.pid
        q = {"query": "MATCH (n:C16H) RETURN count(n) AS c"}
        rec("B.health_no_key", status=httpx.get(url + "/health", timeout=30).status_code)
        rec("B.cypher_no_key", status=httpx.post(url + "/api/cypher", json=q, timeout=30).status_code)
        rec("B.cypher_wrong_key", status=httpx.post(url + "/api/cypher", json=q, headers={"X-Api-Key": "nope"},
                                                    timeout=30).status_code)
        rec("B.cypher_key", status=httpx.post(url + "/api/cypher", json=q, headers={"X-Api-Key": KEY},
                                              timeout=30).status_code)
        rec("B.cypher_bearer", status=httpx.post(url + "/api/cypher", json=q,
                                                 headers={"Authorization": f"Bearer {KEY}"}, timeout=30).status_code)
        rec("B.admin_load_no_key", status=httpx.post(url + "/admin/load", content=b"", timeout=30).status_code)
        for cred in ("wrong", KEY):
            drv = GraphDatabase.driver(f"bolt://127.0.0.1:{BOLT}", auth=("neo4j", cred))
            try:
                with drv.session() as s:
                    v = s.run("MATCH (n:C16H) RETURN count(n) AS c").single()["c"]
                out = {"ok": v}
            except Exception as e:
                out = {"type": type(e).__name__, "code": getattr(e, "code", None), "msg": str(e)[:200]}
            finally:
                drv.close()
            rec(f"B.bolt_{'right' if cred == KEY else 'wrong'}_key", result=out)
        jsrv.stop(p)
        p = None

        # ---------------------------------------------------------------- C: key + read-only
        p = server("C", {"IVG_API_KEY": KEY, "IVG_READ_ONLY": "true"})
        R["server_C_pid"] = p.pid
        h = {"X-Api-Key": KEY}
        w = {"query": "CREATE (n:C16RO {id: 'c16:ro1'}) RETURN n.id AS id"}
        rec("C.cypher_write_readonly", status=httpx.post(url + "/api/cypher", json=w, headers=h, timeout=30).status_code)
        rec("C.tx_commit_write_readonly", status=httpx.post(url + "/db/neo4j/tx/commit", headers=h, timeout=30,
                                                            json={"statements": [{"statement": w["query"]}]}).status_code)
        rec("C.admin_load_readonly", status=httpx.post(url + "/admin/load", content=b"", headers=h,
                                                       timeout=30).status_code)
        rec("C.admin_explain_readonly", status=httpx.post(url + "/admin/explain", json={"query": "MATCH (n) RETURN n"},
                                                          headers=h, timeout=30).status_code)
        drv = GraphDatabase.driver(f"bolt://127.0.0.1:{BOLT}", auth=("neo4j", KEY))
        try:
            with drv.session() as s:
                s.run(w["query"]).consume()
            out = {"ok": True}
        except Exception as e:
            out = {"type": type(e).__name__, "code": getattr(e, "code", None), "msg": str(e)[:200]}
        finally:
            drv.close()
        rec("C.bolt_write_readonly", result=out, db_rows=count_ids(L, ["c16:ro1"]))
        jsrv.stop(p)
        p = None
    finally:
        jsrv.stop(p)
        # cleanup: every c16 node of the default graph this script made
        ids = ["c16:h1", "c16:t1", "c16:t3", "c16:b1", "c16:b2", "c16:f1", "c16:f2", "c16:f3", "c16:ro1"]
        for i in ids:
            try:
                L.eng.delete_node(i)
            except Exception as e:
                R.setdefault("cleanup_errors", []).append(f"{i}: {e}")
        R["left_after_cleanup"] = count_ids(L, ids)
        L.close()
        jsrv.dump(OUT / "s1_cypher_http.json", R)


if __name__ == "__main__":
    main()
