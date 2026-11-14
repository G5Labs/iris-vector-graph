"""Journal footprints of two more module-16 writers on AUDITC.

    locks.sh iris timeout 600 python s7_more_writers.py

  POST /admin/load (Cypher HTTP server, 127.0.0.1:18650, Bolt off): an NDJSON body with two nodes, one edge and one
       malformed line: which stores, how many transactions, and is the load all-or-nothing?
  POST /api/cypher on the sample API (127.0.0.1:18651): a CREATE through the route's own translate-and-run path
       (START TRANSACTION .. COMMIT on the shared connection), and a CREATE whose second SQL statement fails.
Connections: Lane, one per server, the journal session: at most 4. Scratch ids c16:l*, c16:sa*; removed at the end.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import Lane, run_dir  # noqa: E402

import httpx  # noqa: E402

OUT = run_dir("16")
R: dict = {"checks": {}}


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:700])


def main():
    L = Lane("c16")
    p1 = p2 = None
    try:
        env = jsrv.iris_env()
        env["BOLT_ENABLED"] = "0"
        p1 = jsrv.start("cypher-http", ["-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1",
                                        "--port", "18650"], env, 18650, OUT / "s7_cypher_http.log")
        body = "\n".join([json.dumps({"kind": "node", "id": "c16:l1", "labels": ["C16L"], "properties": {"a": 1}}),
                          json.dumps({"kind": "node", "id": "c16:l2", "labels": ["C16L"]}),
                          "{not json",
                          json.dumps({"kind": "edge", "source": "c16:l1", "predicate": "C16_LOAD",
                                      "target": "c16:l2"})]).encode()
        j = jsrv.journal_by_marker("POST /admin/load", lambda: httpx.post(
            "http://127.0.0.1:18650/admin/load", content=body, timeout=120).json(), ["c16:l1", "c16:l2"], L.smap)
        rec("admin_load", journal=j)

        p2 = jsrv.start("sample-api", ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "18651"],
                        jsrv.iris_env(), 18651, OUT / "s7_sample_api.log", cwd=OUT)
        q = "CREATE (a:C16SA {id: 'c16:sa1'})-[:C16_SA_REL]->(b:C16SA {id: 'c16:sa2'}) RETURN a.id AS id"
        j = jsrv.journal_by_marker("sample API POST /api/cypher CREATE", lambda: httpx.post(
            "http://127.0.0.1:18651/api/cypher", json={"query": q}, timeout=120).json(), ["c16:sa1", "c16:sa2"],
            L.smap)
        rec("sample_api_cypher_create", journal=j,
            rows=L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id IN ('c16:sa1','c16:sa2')"),
            edges=L.c.sql("SELECT s, p, o_id FROM Graph_KG.rdf_edges WHERE s = 'c16:sa1'"),
            kg_out=L.eng.execute_cypher("MATCH (a {id: 'c16:sa1'})-[r]->(b) RETURN b.id AS b").rows)
    finally:
        jsrv.stop(p1)
        jsrv.stop(p2)
        try:
            L.eng.execute_cypher("MATCH (n:C16L) DETACH DELETE n")
            L.eng.execute_cypher("MATCH (n:C16SA) DETACH DELETE n")
        except Exception as e:
            R["cleanup_error"] = str(e)
        R["left"] = L.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'c16:l' "
                            "OR node_id %STARTSWITH 'c16:sa'")
        R["edges_left"] = L.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'c16:'")
        L.close()
        jsrv.dump(OUT / "s7_more_writers.json", R)


if __name__ == "__main__":
    main()
