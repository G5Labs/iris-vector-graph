"""Status maps and bind addresses of the Cypher HTTP server and Bolt listener, with no IRIS at all.

    python s6_status_maps.py        (connects to no IRIS: IRIS_HOST points at a closed local port)

  map.http   /api/cypher, /db/neo4j/tx/commit, /db/neo4j/query/v2, /health, /schema when the engine's database
             call fails with a connection error (stub engine whose execute_cypher raises ConnectionError; the
             server's reconnect then fails against 127.0.0.1:1). Which HTTP status and Neo4j code does a caller get?
  map.bolt   the Bolt TCP listener (start_tcp_bolt_server) with an engine factory that fails to connect, and with an
             engine whose query raises a connection error: which FAILURE code does a neo4j driver see?
  bind       `uvicorn iris_vector_graph.cypher_api:app --host 127.0.0.1` without BOLT_TCP_HOST: where does Bolt
             listen? (IVG_API_KEY is set so the listener refuses unauthenticated sessions while it is up.)
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jsrv  # noqa: E402
from jcheck import run_dir  # noqa: E402

OUT = run_dir("16")
R: dict = {"checks": {}}
NOIRIS = {"IRIS_HOST": "127.0.0.1", "IRIS_PORT": "1", "IRIS_NAMESPACE": "AUDITC", "IRIS_USERNAME": "_SYSTEM",
          "IRIS_PASSWORD": "SYS", "BOLT_ENABLED": "0"}


def rec(name, **kv):
    R["checks"][name] = kv
    print(name, json.dumps(kv, default=str)[:600])


class _Res:
    error = None
    columns = ["one"]
    rows = [[1]]
    bolt_column_types = None


class StubEngine:
    """Stands in for IRISGraphEngine: every query fails as a dropped IRIS connection would."""

    class conn:  # noqa: N801
        @staticmethod
        def close():
            pass

    def execute_cypher(self, query, parameters=None, **kw):
        raise ConnectionError("<COMMUNICATION LINK ERROR> Failed to connect to server (simulated)")


def http_map():
    os.environ.update(NOIRIS)
    os.environ.pop("IVG_API_KEY", None)
    os.environ.pop("IVG_READ_ONLY", None)
    from starlette.testclient import TestClient
    import iris_vector_graph.cypher_api as capi
    tc = TestClient(capi.app)
    for path, body in (("/api/cypher", {"query": "RETURN 1 AS one"}),
                       ("/db/neo4j/tx/commit", {"statements": [{"statement": "RETURN 1 AS one"}]}),
                       ("/db/neo4j/query/v2", {"statement": "RETURN 1 AS one"})):
        capi._engine_cache = StubEngine()
        r = tc.post(path, json=body)
        rec(f"map.http.{path}", status=r.status_code, body=r.json())
    capi._engine_cache = StubEngine()
    r = tc.get("/health")
    rec("map.http./health", status=r.status_code, body=r.json())
    capi._engine_cache = None
    r = tc.get("/schema")
    rec("map.http./schema (no IRIS reachable)", status=r.status_code, body=str(r.json())[:300])


def bolt_map():
    from neo4j import GraphDatabase
    from iris_vector_graph.bolt_server import start_tcp_bolt_server

    def failing_factory():
        raise ConnectionError("<COMMUNICATION LINK ERROR> Unable to allocate a license (simulated)")

    for label, factory, port in (("factory_fails", failing_factory, 18616),
                                 ("query_fails", lambda: StubEngine(), 18619)):
        loop = asyncio.new_event_loop()
        srv = loop.run_until_complete(start_tcp_bolt_server(factory, host="127.0.0.1", port=port))
        t = threading.Thread(target=loop.run_forever, daemon=True)
        t.start()
        try:
            drv = GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x"))
            try:
                with drv.session() as s:
                    s.run("RETURN 1 AS one").consume()
                out = {"ok": True}
            except Exception as e:
                out = {"type": type(e).__name__, "code": getattr(e, "code", None),
                       "classification": getattr(e, "classification", None),
                       "retryable": getattr(e, "is_retryable", lambda: None)(), "msg": str(e)[:300]}
            finally:
                drv.close()
            rec(f"map.bolt.{label}", result=out)
        finally:
            loop.call_soon_threadsafe(srv.close)
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=10)


def bind_check():
    env = dict(NOIRIS)
    env.pop("BOLT_ENABLED")
    env.update({"IVG_API_KEY": "c16-secret-key", "BOLT_TCP_PORT": "18618", "BOLT_ENABLED": "1"})  # http_map set 0 in os.environ
    p = jsrv.start("bind", ["-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1", "--port",
                            "18617"], env, 18617, OUT / "s6_bind.log", wait_path="/openapi")
    try:
        time.sleep(1)
        ss = subprocess.run(["ss", "-ltn"], capture_output=True, text=True).stdout
        lines = [ln for ln in ss.splitlines() if ":18617" in ln or ":18618" in ln]
        rec("bind.uvicorn_host_127", http_host_arg="127.0.0.1", listening=lines,
            bolt_on_all_interfaces=any(("0.0.0.0:18618" in ln or "*:18618" in ln) for ln in lines))
    finally:
        jsrv.stop(p)


def main():
    for f in (http_map, bolt_map, bind_check):
        try:
            f()
        except Exception as e:
            rec(f"{f.__name__}.error", error=f"{type(e).__name__}: {e}"[:600])
    jsrv.dump(OUT / "s6_status_maps.json", R)


if __name__ == "__main__":
    main()
