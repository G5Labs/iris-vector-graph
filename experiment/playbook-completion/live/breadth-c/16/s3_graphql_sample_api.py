"""Live checks of the generated GraphQL server (iris_vector_graph.gql.create_app) and the sample API (api.main).

    locks.sh iris timeout 1200 python s3_graphql_sample_api.py

Fixture (AUDITC, removed at the end): one node id in the default graph and in graph c16g1 with different labels,
properties and edges; label C16Q on three g1-only nodes and one default-graph node; Protein c16:p1 in both graphs.
Connections: the Lane connection (shared by the in-process generated app), one for the sample API server, one
briefly opened and closed for the broken-database health probe, and the journal's terminal session: at most 4.

  generated GraphQL (in-process ASGI over the real engine): F-1603 outgoing/incoming and nodes(label) paging,
                     F-1611 /health over a closed connection
  sample API (uvicorn subprocess, 127.0.0.1:18630): F-1604 protein read and updateProtein write (journal),
                     F-1606 timeout field, F-1607 UNWIND parity, F-1608 concurrent /health + /api/cypher,
                     F-1609 /fhir-event with a failing temporal write (journal), status codes
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Conn, Lane, run_dir  # noqa: E402

import httpx  # noqa: E402

OUT = run_dir("16")
PORT = 18630
G1, G2 = "c16g1", "c16g2"
R: dict = {"checks": {}}
SLOW_N = 120


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:700])


def fixture(e):
    e.create_node("c16:x", ["C16P"], {"name": "x-default"})
    e.create_node("c16:z", ["C16P"], {"name": "z-default"})
    e.create_edge("c16:x", "C16_DEF_EDGE", "c16:z")
    e.create_node("c16:x", ["C16P"], {"name": "x-g1"}, graph=G1)
    e.create_node("c16:y", ["C16P"], {"name": "y-g1"}, graph=G1)
    e.create_edge("c16:x", "C16_G1_EDGE", "c16:y", graph=G1)
    for q in ("c16:qa", "c16:qb", "c16:qc"):
        e.create_node(q, ["C16Q"], graph=G1)
    e.create_node("c16:qz", ["C16Q"])
    e.create_node("c16:p1", ["Protein"], {"name": "p-default"})
    e.create_node("c16:p1", ["Protein", "C16G1Label"], {"name": "p-g1"}, graph=G1)
    e.create_node("c16:p2", ["Protein"], {"name": "p2-g1"}, graph=G1)
    e.create_edge("c16:p1", "INTERACTS_WITH", "c16:p2", graph=G1)
    e.bulk_create_nodes([{"id": f"c16:s{i:03d}", "labels": ["C16S"]} for i in range(SLOW_N)])


def props_of(L, nid):
    return L.c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props WHERE s = ? ORDER BY graph_id, \"key\"", nid)


def generated_graphql(L):
    from starlette.testclient import TestClient
    from iris_vector_graph.gql import create_app
    app = create_app(L.eng)
    with TestClient(app) as tc:
        q = '{ node(id: "c16:x") { id labels outgoing { predicate targetId } incoming { predicate targetId } } }'
        r = tc.post("/graphql", json={"query": q})
        body = r.json()
        out = (((body.get("data") or {}).get("node")) or {}).get("outgoing") or []
        rec("GQL.F1603_outgoing_default_node", status=r.status_code, body=body,
            expected_default_graph_only=[{"predicate": "C16_DEF_EDGE", "targetId": "c16:z"}],
            reproduced=any(o.get("predicate") == "C16_G1_EDGE" for o in out))
        r = tc.post("/graphql", json={"query": '{ nodes(label: "C16Q", limit: 3) { id } }'})
        ids = [n["id"] for n in ((r.json().get("data") or {}).get("nodes") or [])]
        rec("GQL.F1603_nodes_label_page", status=r.status_code, body=r.json(), default_graph_C16Q=["c16:qz"],
            g1_only_C16Q=["c16:qa", "c16:qb", "c16:qc"], page=ids, reproduced=("c16:qz" not in ids))
        r = tc.post("/graphql", json={"query": '{ node(id: "c16:y") { id labels } }'})
        rec("GQL.node_only_in_named_graph", status=r.status_code, body=r.json())
        r = tc.post("/graphql", json={"query": '{ nodes(label: "C16S" limit: 2) { id } }'})
        rec("GQL.syntax_error_status", status=r.status_code, body=r.json())
        r = tc.get("/health")
        rec("GQL.health_ok_db", status=r.status_code, body=r.json())
    # F-1611: the same app factory over a connection that no longer works
    c2 = Conn("AUDITC")
    from iris_vector_graph.engine import IRISGraphEngine
    e2 = IRISGraphEngine(c2.conn, namespace="AUDITC")
    app2 = create_app(e2)
    c2.conn.close()
    with TestClient(app2) as tc2:
        r = tc2.get("/health")
        rec("GQL.F1611_health_closed_connection", status=r.status_code, body=r.json(),
            reproduced=r.status_code == 200)


def sample_api(L):
    env = jsrv.iris_env()
    p = jsrv.start("sample-api", ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(PORT)], env,
                   PORT, OUT / "s3_sample_api.log", cwd=OUT, wait_path="/health")
    R["sample_api_pid"] = p.pid
    url = f"http://127.0.0.1:{PORT}"
    try:
        r = httpx.get(url + "/health", timeout=30)
        rec("API.health", status=r.status_code, body=r.json())
        q = '{ protein(id: "c16:p1") { id labels name interactsWith { id } } }'
        r = httpx.post(url + "/graphql", json={"query": q}, timeout=60)
        prot = ((r.json().get("data") or {}).get("protein")) or {}
        rec("API.F1604_protein_read", status=r.status_code, body=r.json(),
            expected_default_graph={"labels": ["Protein"], "name": "p-default", "interactsWith": []},
            reproduced=("C16G1Label" in (prot.get("labels") or []) or bool(prot.get("interactsWith"))
                        or prot.get("name") != "p-default"))
        before = props_of(L, "c16:p1")
        m = 'mutation { updateProtein(id: "c16:p1", input: {name: "p-updated"}) { id name } }'
        j = jsrv.journal_by_marker("sample API updateProtein", lambda: httpx.post(
            url + "/graphql", json={"query": m}, timeout=60).json(), ["c16:p1"], L.smap)
        after = props_of(L, "c16:p1")
        g1_name = [v for g, k, v in after if g == G1 and k == "name"]
        rec("API.F1604_updateProtein_cross_graph_write", props_before=before, props_after=after, journal=j,
            reproduced=g1_name == ["p-updated"])

        slow = f"MATCH (a:C16S), (b:C16S), (c:C16S) RETURN count(*) AS n"
        t0 = time.time()
        r = httpx.post(url + "/api/cypher", json={"query": slow, "timeout": 1}, timeout=600)
        el = time.time() - t0
        rec("API.F1606_timeout_ignored", status=r.status_code, seconds=round(el, 2),
            rows=(r.json().get("rows") if r.status_code == 200 else r.json()), reproduced=r.status_code == 200 and el > 1.5)

        params = {"p": ["[2]", [2], True, "1"]}
        r1 = httpx.post(url + "/api/cypher", json={"query": "UNWIND $p AS e RETURN e", "parameters": params},
                        timeout=60)
        gq = 'query($p: JSON) { executeCypher(query: "UNWIND $p AS e RETURN e", params: $p) }'
        r2 = httpx.post(url + "/graphql", json={"query": gq, "variables": {"p": params}}, timeout=60)
        eng = L.eng.execute_cypher("UNWIND $p AS e RETURN e", parameters=params).rows
        rec("API.F1607_unwind_parity", sample_api_cypher_route=r1.json(), sample_api_graphql_executeCypher=r2.json(),
            engine_execute_cypher=eng)

        for qq, name in (("MATCH (n RETURN n", "syntax"), ("MATCH (n:C16S) RETURN m.name", "undefined_variable"),
                         ("MATCH (n:C16S) RETURN n.id AS id ORDER BY nosuchfn(n) LIMIT 1", "execution")):
            r = httpx.post(url + "/api/cypher", json={"query": qq}, timeout=60)
            rec(f"API.status_{name}", status=r.status_code, body=r.json())

        # F-1608: /health (sync def, thread pool) beside /api/cypher (async def, event loop) on one connection
        stop_at = time.time() + 12
        stats = {"health": {"n": 0, "non200": 0}, "cypher": {"n": 0, "non200": 0, "wrong": 0, "samples": []}}

        def hammer_health():
            with httpx.Client(timeout=60) as c:
                while time.time() < stop_at:
                    rr = c.get(url + "/health")
                    stats["health"]["n"] += 1
                    if rr.status_code != 200:
                        stats["health"]["non200"] += 1

        def hammer_cypher():
            with httpx.Client(timeout=60) as c:
                while time.time() < stop_at:
                    rr = c.post(url + "/api/cypher", json={"query": "MATCH (n:C16S) RETURN count(n) AS c"})
                    stats["cypher"]["n"] += 1
                    if rr.status_code != 200:
                        stats["cypher"]["non200"] += 1
                        if len(stats["cypher"]["samples"]) < 5:
                            stats["cypher"]["samples"].append(rr.text[:300])
                    elif rr.json().get("rows") != [[SLOW_N]]:
                        stats["cypher"]["wrong"] += 1
                        if len(stats["cypher"]["samples"]) < 5:
                            stats["cypher"]["samples"].append(rr.text[:300])
        ts = [threading.Thread(target=hammer_health), threading.Thread(target=hammer_health),
              threading.Thread(target=hammer_cypher)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=120)
        rec("API.F1608_concurrent_health_and_query", stats=stats,
            reproduced=stats["health"]["non200"] + stats["cypher"]["non200"] + stats["cypher"]["wrong"] > 0)

        body = {"resourceType": "Condition", "id": "fe1", "fhirUrl": "c16:fe1", "patientRef": "c16:fp1",
                "date": "1960-01-01", "graph": G2}
        resp = {}

        def fe():
            rr = httpx.post(url + "/fhir-event/", json=body, timeout=60)
            resp["status"], resp["body"] = rr.status_code, rr.text[:500]
            return rr.status_code
        j = jsrv.journal_by_marker("POST /fhir-event (temporal write refused)", fe, ["c16:fe1", "c16:fp1"], L.smap)
        left = L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id IN ('c16:fe1','c16:fp1')")
        rec("API.F1609_fhir_event_partial", http=resp, left_in_db=left, journal=j,
            reproduced=resp["status"] == 500 and len(left) == 2)
        body2 = dict(body, id="fe2", fhirUrl="c16:fe2", patientRef="c16:fp2", date="2020-01-01")
        j = jsrv.journal_by_marker("POST /fhir-event (success)", lambda: httpx.post(
            url + "/fhir-event/", json=body2, timeout=60).status_code, ["c16:fe2", "c16:fp2"], L.smap)
        rec("API.fhir_event_success_footprint", journal=j)
    finally:
        jsrv.stop(p)


def main():
    L = Lane("c16")
    try:
        fixture(L.eng)
        try:
            generated_graphql(L)
        except Exception as e:
            rec("GQL.error", error=f"{type(e).__name__}: {e}"[:800])
        try:
            sample_api(L)
        except Exception as e:
            rec("API.error", error=f"{type(e).__name__}: {e}"[:800])
    finally:
        cl = {}
        for g in (G1, G2):
            try:
                cl[g] = L.eng.erase_graph(g)
            except Exception as e:
                cl[g] = f"error {e}"
        try:
            L.eng.execute_cypher("MATCH (n:C16S) DETACH DELETE n")
        except Exception as e:
            cl["C16S"] = f"error {e}"
        for i in ("c16:x", "c16:z", "c16:qz", "c16:p1"):
            try:
                L.eng.delete_node(i)
            except Exception as e:
                cl[i] = f"error {e}"
        R["cleanup"] = cl
        R["left_after_cleanup"] = L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c16'")
        R["props_left"] = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_props WHERE s %STARTSWITH 'c16'")
        L.close()
        jsrv.dump(OUT / "s3_graphql_sample_api.json", R)


if __name__ == "__main__":
    main()
