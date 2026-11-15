#!/usr/bin/env python3
"""Module 16 (interfaces: Cypher HTTP server and Bolt, sample API, GraphQL servers, fraud server, security helpers):
live probes of every stated refusal (API kind X) reachable in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_16.py [case ...]

Servers:
  - the Cypher HTTP server with its Bolt TCP listener (`uvicorn iris_vector_graph.cypher_api:app`), started here as a
    subprocess on free 127.0.0.1 ports against AUDITE (IRIS_HOST/IRIS_PORT/IRIS_NAMESPACE), once with IVG_API_KEY and
    once with IVG_API_KEY + IVG_READ_ONLY, and stopped by PID (its own session group) after its cases. Its IRIS
    connections: the HTTP engine (made lazily) and one per Bolt session that runs a query (F-C1601: never given
    back until the server stops), at most 3 here;
  - the sample API (`api.main.create_app(engine)`), the generated GraphQL app (`iris_vector_graph.gql.create_app`),
    the Cypher HTTP app (for setup width) and the fraud server (`iris_fraud_server.app.create_app`) in process
    (Starlette TestClient, no lifespan), on the lane's own engine. The fraud server's module imports torch and
    structlog, which are not installed here; inert stand-ins are put in sys.modules for that import only (the
    refused paths, the request model and the EGO branch, use neither; its startup event is not run).
Each refused call runs in a journal window (rxlib; AUDITE database, every process). Raw Bolt messages come from
rx1516.Bolt. Scratch ids/graphs rx16*. Results: $RUN_DIR/refusals/16/.
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, REPO  # noqa: E402
from rx1516 import Listener, Bolt, summary, HELLO, LOGON, LOGOFF, RESET, RUN, PULL  # noqa: E402

KEY = "rx16-secret-key"
PY = sys.executable


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def node_rows(L, *ids):
    q = "SELECT node_id, graph_id FROM Graph_KG.nodes WHERE node_id IN (%s)" % ",".join("?" * len(ids))
    return [tuple(r) for r in L.c.sql(q, *ids)]


class Server:
    """The Cypher HTTP server + Bolt TCP listener as a subprocess against AUDITE."""

    def __init__(self, L, tag, extra):
        import httpx
        self.http, self.bolt = free_port(), free_port()
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("IVG_API_KEY", "IVG_READ_ONLY", "IVG_FHIR_ALLOWED", "FHIR_BASE_URL", "IRIS_"))}
        env.update({"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": "AUDITE",
                    "IRIS_USERNAME": "_SYSTEM", "IRIS_PASSWORD": "SYS", "BOLT_TCP_HOST": "127.0.0.1",
                    "BOLT_TCP_PORT": str(self.bolt)})
        env.update(extra)
        self.log = L.out / f"server-{tag}.log"
        self.lf = open(self.log, "w")
        self.p = subprocess.Popen([PY, "-m", "uvicorn", "iris_vector_graph.cypher_api:app", "--host", "127.0.0.1",
                                   "--port", str(self.http)], cwd=str(REPO), env=env, stdout=self.lf,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        self.url = f"http://127.0.0.1:{self.http}"
        deadline = time.time() + 90
        while time.time() < deadline:
            if self.p.poll() is not None:
                raise RuntimeError(f"server {tag} exited {self.p.returncode}; see {self.log}")
            try:
                if httpx.get(self.url + "/openapi", timeout=5).status_code == 200:  # public; makes no engine
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)
        else:
            self.stop()
            raise RuntimeError(f"server {tag} not ready")
        deadline = time.time() + 30
        while time.time() < deadline:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", self.bolt)) == 0:
                    break
            time.sleep(0.5)
        L.note("API-X1.5", f"server {tag} started", pid=self.p.pid, http=self.http, bolt=self.bolt,
               env={k: ("<set>" if k == "IVG_API_KEY" else v) for k, v in extra.items()})

    def post(self, path, **kw):
        import httpx
        r = httpx.post(self.url + path, timeout=60, **kw)
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = r.text[:500]
        return {"status": r.status_code, "body": body}

    def stop(self):
        if self.p.poll() is None:
            os.killpg(self.p.pid, signal.SIGTERM)
            try:
                self.p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.p.pid, signal.SIGKILL)
                self.p.wait(timeout=10)
        self.lf.close()


UNAUTH = {"error": "unauthorized", "message": "X-Api-Key header required"}


def bolt_refused(code):
    return returns(lambda r: r["summary"] == "FAILURE" and r["code"] == code, f"Bolt FAILURE {code}")


# ------------------------------------------------------------------------------------------------ server with key
def c_key_server(L):
    srv = Server(L, "key", {"IVG_API_KEY": KEY})
    try:
        create = {"query": "CREATE (n:RX16 {id: 'rx16:k1'}) RETURN n.id AS id"}
        for k, hdr in (("no key", {}), ("wrong key", {"X-Api-Key": "nope"}), ("empty key", {"X-Api-Key": ""}),
                       ("wrong bearer", {"Authorization": "Bearer nope"})):
            L.refusal("API-X1.5", f"POST /api/cypher CREATE, {k}", lambda: srv.post("/api/cypher", json=create,
                                                                                   headers=hdr),
                      returns(lambda r: r["status"] == 401 and r["body"] == UNAUTH, "401 " + json.dumps(UNAUTH)),
                      after=lambda: {"rx16:k1 rows": node_rows(L, "rx16:k1")}, entry="Cypher HTTP server (uvicorn)")
        L.refusal("API-X1.5", "POST /db/neo4j/tx/commit CREATE, no key",
                  lambda: srv.post("/db/neo4j/tx/commit", json={"statements": [{"statement": create["query"]}]}),
                  returns(lambda r: r["status"] == 401 and r["body"] == UNAUTH, "401"),
                  after=lambda: {"rx16:k1 rows": node_rows(L, "rx16:k1")}, entry="Cypher HTTP server (uvicorn)")
        L.refusal("API-X1.5", "POST /admin/load, no key", lambda: srv.post("/admin/load", content=b'{"id":"x"}'),
                  returns(lambda r: r["status"] == 401 and r["body"] == UNAUTH, "401"),
                  entry="Cypher HTTP server (uvicorn)")
        # Bolt: nothing runs before HELLO/LOGON shows the key (API-X9.3)
        b = Bolt(srv.bolt, versions=(0x00000404,))
        L.refusal("API-X9.3", "Bolt 4.4 RUN CREATE before HELLO",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b1'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b1"), "bolt_version": hex(b.version)},
                  entry="Bolt TCP listener")
        b.close()
        b = Bolt(srv.bolt, versions=(0x00000405,))
        hello = summary(b.call(HELLO, {"user_agent": "rx16/1.0"}))
        L.refusal("API-X9.3", "Bolt 5 HELLO without credentials, then RUN CREATE (no LOGON)",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b2'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b2"), "hello": hello, "bolt_version": hex(b.version)},
                  entry="Bolt TCP listener")
        b.close()
        b = Bolt(srv.bolt, versions=(0x00000404,))
        bad_hello = summary(b.call(HELLO, {"user_agent": "rx16/1.0", "scheme": "basic", "principal": "neo4j",
                                           "credentials": "wrong"}))
        reset = summary(b.call(RESET))
        L.refusal("API-X9.3", "Bolt 4.4 refused HELLO, RESET, then RUN CREATE",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b3'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b3"), "hello": bad_hello, "reset": reset},
                  entry="Bolt TCP listener")
        b.close()
        # control: Bolt 5 HELLO + LOGON with the key runs a read (one engine connection in the server)
        b = Bolt(srv.bolt, versions=(0x00000405,))
        ctl = [summary(b.call(HELLO, {"user_agent": "rx16/1.0"})),
               summary(b.call(LOGON, {"scheme": "basic", "principal": "neo4j", "credentials": KEY})),
               summary(b.call(RUN, "RETURN 1 AS one", {}, {})), summary(b.call(PULL, {"n": -1}))]
        L.note("API-X9.3", "control: Bolt 5 HELLO + LOGON with the key, RUN + PULL a read", replies=ctl)
        # API-X9.4: a wrong key ends the login, even a good earlier one; RESET does not bring it back
        bad = summary(b.call(LOGON, {"scheme": "basic", "principal": "neo4j", "credentials": "wrong"}))
        reset = summary(b.call(RESET))
        L.refusal("API-X9.4", "Bolt 5 good LOGON, wrong LOGON, RESET, then RUN CREATE",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b4'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b4"), "wrong_logon": bad, "reset": reset},
                  entry="Bolt TCP listener")
        b.close()
        b = Bolt(srv.bolt, versions=(0x00000405,))
        seq = [summary(b.call(HELLO, {"user_agent": "rx16/1.0"})),
               summary(b.call(LOGON, {"scheme": "basic", "principal": "neo4j", "credentials": KEY})),
               summary(b.call(LOGOFF))]
        L.refusal("API-X9.4", "Bolt 5 good LOGON, LOGOFF, then RUN CREATE",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b5'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b5"), "before": seq}, entry="Bolt TCP listener")
        b.close()
        b = Bolt(srv.bolt, versions=(0x00000404,))
        seq = [summary(b.call(HELLO, {"user_agent": "rx16/1.0", "scheme": "basic", "principal": "neo4j",
                                      "credentials": KEY})),
               summary(b.call(HELLO, {"user_agent": "rx16/1.0", "scheme": "basic", "principal": "neo4j",
                                      "credentials": "wrong"})),
               summary(b.call(RESET))]
        L.refusal("API-X9.4", "Bolt 4.4 good HELLO, wrong HELLO, RESET, then RUN CREATE",
                  lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:b6'}) RETURN n.id", {}, {})),
                  bolt_refused("Neo.ClientError.Security.Unauthorized"),
                  after=lambda: {"rows": node_rows(L, "rx16:b6"), "before": seq}, entry="Bolt TCP listener")
        b.close()
    finally:
        srv.stop()
        L.note("API-X1.5", "server key stopped", exit=srv.p.returncode)


# ------------------------------------------------------------------------------------------------ read-only server
def c_ro_server(L):
    with Listener("record") as lis:
        listed = lis.url + "/fhir"
        srv = Server(L, "readonly", {"IVG_API_KEY": KEY, "IVG_READ_ONLY": "true", "IVG_FHIR_ALLOWED_BASES": listed})
        h = {"X-Api-Key": KEY}
        try:
            ro = lambda r: r["status"] == 403 and (r["body"] or {}).get("error") == "read_only_mode"  # noqa: E731
            for path, kw in (("/admin/load", {"content": b'{"id":"rx16:l1"}'}),
                             ("/admin/schema/init", {"json": {"embedding_dimension": 4}}),
                             ("/admin/indexes/rebuild", {}), ("/admin/embed", {"json": {}}),
                             ("/admin/snapshot", {})):
                L.refusal("API-X3.2", f"POST {path} read-only", lambda: srv.post(path, headers=h, **kw),
                          returns(ro, "403 read_only_mode"), entry="Cypher HTTP server (uvicorn)")
            import httpx

            def kill_query():
                r = httpx.delete(srv.url + "/admin/queries/rx16q", headers=h, timeout=30)
                return {"status": r.status_code, "body": r.json()}
            L.refusal("API-X3.2", "DELETE /admin/queries/{id} read-only", kill_query,
                      returns(ro, "403 read_only_mode"), entry="Cypher HTTP server (uvicorn)")
            r = srv.post("/admin/explain", headers=h, json={"query": "MATCH (n) RETURN n.id"})
            L.note("API-X3.2", "control: POST /admin/explain answers under read-only", status=r["status"],
                   has_sql=isinstance(r["body"], dict) and "sql" in r["body"])
            stmts = [{"statement": "MATCH (n:RX16) RETURN count(n) AS c"},
                     {"statement": "CREATE (n:RX16 {id: 'rx16:t1'}) RETURN n.id AS id"},
                     {"statement": "MATCH (n:RX16) RETURN count(n) AS c"}]
            L.refusal("API-X8.6.2", "tx/commit read, write, read under read-only",
                      lambda: srv.post("/db/neo4j/tx/commit", headers=h, json={"statements": stmts}),
                      returns(lambda r: r["status"] == 403 and r["body"]["results"] == []
                              and r["body"]["errors"][0]["code"] == "Neo.ClientError.Statement.AccessMode",
                              "403, results [], AccessMode"),
                      after=lambda: {"rows": node_rows(L, "rx16:t1")}, entry="Cypher HTTP server (uvicorn)")
            # API-X8.5.6: an unlisted FHIR base is not fetched (the listed one is lis.url/fhir)
            for k, base in (("unlisted host", "http://169.254.169.254/fhir"),
                            ("listed base plus a path", listed + "/r4"), ("listed base as a prefix", listed + "x")):
                n0 = len(lis.connections)
                L.refusal("API-X8.5.6", f"POST /api/cypher fhir_base_url {k}",
                          lambda: srv.post("/api/cypher", headers=h, json={"query": "RETURN 1 AS n",
                                                                         "fhir_patient_id": "p1",
                                                                         "fhir_base_url": base}),
                          returns(lambda r: r["status"] == 400 and "IVG_FHIR_ALLOWED_BASES" in json.dumps(r["body"]),
                                  "400 naming IVG_FHIR_ALLOWED_BASES"),
                          after=lambda: {"fetches_seen": len(lis.connections) - n0},
                          entry="Cypher HTTP server (uvicorn)")
                c = L.cases[-1]
                if c["observations"].get("fetches_seen"):
                    c["outcome"], c["why"] = "not-refused-as-stated", c["why"] + " | fetched"
            n0 = len(lis.connections)
            r = srv.post("/api/cypher", headers=h, json={"query": "RETURN 1 AS n", "fhir_patient_id": "p1",
                                                        "fhir_base_url": listed + "/"})
            L.note("API-X8.5.6", "control: the listed base, trailing slash, is fetched", status=r["status"],
                   fetches_seen=len(lis.connections) - n0)
            # API-X9.7: Bolt RUN of a write under read-only
            b = Bolt(srv.bolt, versions=(0x00000404,))
            hello = summary(b.call(HELLO, {"user_agent": "rx16/1.0", "scheme": "basic", "principal": "neo4j",
                                           "credentials": KEY}))
            L.refusal("API-X9.7", "Bolt RUN CREATE under read-only",
                      lambda: summary(b.call(RUN, "CREATE (n:RX16 {id: 'rx16:r1'}) RETURN n.id", {}, {})),
                      bolt_refused("Neo.ClientError.Statement.AccessMode"),
                      after=lambda: {"rows": node_rows(L, "rx16:r1"), "hello": hello,
                                     "next_run": summary(b.call(RUN, "RETURN 1", {}, {}))},
                      entry="Bolt TCP listener")
            b.close()
        finally:
            srv.stop()
            L.note("API-X3.2", "server readonly stopped", exit=srv.p.returncode)


# ------------------------------------------------------------------------------------------------ Cypher app in process
def c_schema_width(L):
    """API-X8.10.9: POST /admin/schema/init at a width the (empty) vector columns do not have -> 409."""
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)
    from starlette.testclient import TestClient
    from iris_vector_graph import cypher_api
    eng = L.fresh_engine()
    cur = L.c.conn.cursor()
    try:
        plan = eng._plan_vector_dimensions(cur, 7)
    finally:
        cur.close()
    L.note("API-X8.10.9", "vector columns as the engine's own read-only plan sees them for width 7", plan=plan)
    cypher_api._engine_cache = eng
    tc = TestClient(cypher_api.app)
    try:
        def call():
            r = tc.post("/admin/schema/init", json={"embedding_dimension": 7, "auto_deploy_objectscript": False})
            return {"status": r.status_code, "body": r.json()}
        L.refusal("API-X8.10.9", "POST /admin/schema/init embedding_dimension 7 (columns empty, other width)", call,
                  returns(lambda r: r["status"] == 409, "409"), entry="cypher_api POST /admin/schema/init (ASGI)")
    finally:
        cypher_api._engine_cache = None
        L.fresh_engine()


# ------------------------------------------------------------------------------------------------ sample API
def _sample_apps(L):
    # api.main builds a module-level app at import from IRIS_HOST/IRIS_PORT: aim it at a closed port so it can
    # reach no IRIS at all (it then falls back to engine=None).
    os.environ["IRIS_HOST"], os.environ["IRIS_PORT"] = "127.0.0.1", "9"
    sys.path.insert(0, str(REPO))
    import api.main as sample
    return sample


def _env(**kv):
    for k in ("IVG_API_KEY", "IVG_READ_ONLY", "IVG_ALLOW_FHIR_WRITES", "IVG_CYPHER_MAX_HOPS"):
        os.environ.pop(k, None)
    for k, v in kv.items():
        os.environ[k] = v


def _seed_proteins(L):
    e = L.eng
    e.create_node("rx16:p1", labels=["Protein"], properties={"name": "p1"})
    e.create_node("rx16:p2", labels=["Protein"], properties={"name": "p2-default"})
    e.create_node("rx16:p2", labels=["Protein"], properties={"name": "p2-named"}, graph="rx16g")
    e.create_node("rx16:p3", labels=["Protein"], properties={"name": "p3-named"}, graph="rx16g")
    L.c.conn.commit()


def c_sample_api(L):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    sample = _sample_apps(L)
    L.fresh_engine()
    _seed_proteins(L)
    app = sample.create_app(L.eng)
    tc = TestClient(app)
    gql = lambda q: (lambda r: {"status": r.status_code, "body": r.json()})(tc.post("/graphql", json={"query": q}))  # noqa
    try:
        # API-X1.6: the /graphql web socket without the key
        _env(IVG_API_KEY=KEY)

        def ws(headers):
            try:
                with tc.websocket_connect("/graphql", subprotocols=["graphql-transport-ws"], headers=headers) as w:
                    w.close()
                return {"accepted": True}
            except WebSocketDisconnect as e:
                return {"accepted": False, "close_code": e.code}
        L.refusal("API-X1.6", "sample API /graphql web socket without the key", lambda: ws({}),
                  returns(lambda r: r == {"accepted": False, "close_code": 1008}, "closed 1008 before accept"),
                  entry="sample API (ASGI, ApiKeyMiddleware)")
        L.refusal("API-X1.6", "sample API /graphql web socket with a wrong key", lambda: ws({"X-Api-Key": "nope"}),
                  returns(lambda r: r == {"accepted": False, "close_code": 1008}, "closed 1008 before accept"),
                  entry="sample API (ASGI, ApiKeyMiddleware)")
        L.note("API-X1.6", "control: with the key the web socket is accepted", result=ws({"X-Api-Key": KEY}))
        # API-X3.3: read-only refuses fhir-event writes; IVG_ALLOW_FHIR_WRITES lets them through
        payload = {"resourceType": "Condition", "id": "rx16c1", "fhirUrl": "http://rx16.example/Condition/rx16c1",
                   "patientRef": "Patient/rx16p", "date": "2024-01-01"}
        _env(IVG_READ_ONLY="true")
        L.refusal("API-X3.3", "POST /fhir-event/ under read-only",
                  lambda: (lambda r: {"status": r.status_code, "body": r.json()})(tc.post("/fhir-event/", json=payload)),
                  returns(lambda r: r["status"] == 403 and r["body"].get("error") == "read_only_mode",
                          "403 read_only_mode"), after=lambda: {"rows": node_rows(L, "Condition/rx16c1", "rx16c1")},
                  entry="sample API (ASGI, ReadOnlyMiddleware)")
        _env(IVG_READ_ONLY="true", IVG_ALLOW_FHIR_WRITES="true")
        r = tc.post("/fhir-event/", json={**payload, "graph": "bad\u0001"})
        L.note("API-X3.3", "control: with IVG_ALLOW_FHIR_WRITES the request passes the middleware (refused by the "
               "model, 422)", status=r.status_code)
        # API-X5.1: hop cap
        q11 = {"query": "MATCH (a:RX16)-[*1..11]->(b) RETURN a.id LIMIT 1"}
        cap = lambda r: r["status"] == 413 and r["body"].get("errorCode") == "COMPLEXITY_LIMIT_EXCEEDED"  # noqa
        post = lambda body: (lambda r: {"status": r.status_code, "body": r.json()})(tc.post("/api/cypher", json=body))  # noqa
        _env()
        L.refusal("API-X5.1", "POST /api/cypher *1..11 (default cap)", lambda: post(q11), returns(cap, "413"),
                  entry="sample API /api/cypher")
        L.refusal("API-X5.1", "POST /api/cypher unbounded * (100 hops)",
                  lambda: post({"query": "MATCH (a:RX16)-[*]->(b) RETURN a.id LIMIT 1"}), returns(cap, "413"),
                  entry="sample API /api/cypher")
        _env(IVG_CYPHER_MAX_HOPS="abc")
        L.refusal("API-X5.1", "POST /api/cypher *1..11 (cap set to a bad value -> 10)", lambda: post(q11),
                  returns(cap, "413"), entry="sample API /api/cypher")
        _env(IVG_CYPHER_MAX_HOPS="5")
        L.refusal("API-X5.1", "POST /api/cypher *1..6 (cap lowered to 5)",
                  lambda: post({"query": "MATCH (a:RX16)-[*1..6]->(b) RETURN a.id LIMIT 1"}), returns(cap, "413"),
                  entry="sample API /api/cypher")
        _env(IVG_CYPHER_MAX_HOPS="20")
        r = post(q11)
        L.note("API-X5.1", "control: cap raised to 20 accepts *1..11", status=r["status"])
        # API-X5.2: read-only refuses a writing query
        _env(IVG_READ_ONLY="true")
        L.refusal("API-X5.2", "POST /api/cypher CREATE under read-only",
                  lambda: post({"query": "CREATE (n:RX16 {id: 'rx16:w1'}) RETURN n.id"}),
                  returns(lambda r: r["status"] == 403 and r["body"].get("errorType") == "access", "403 access"),
                  after=lambda: {"rows": node_rows(L, "rx16:w1")}, entry="sample API /api/cypher")
        # API-X6.8: read-only GraphQL mutations and the Cypher field
        for k, q in (("createProtein", 'mutation { createProtein(input: {id: "rx16:new1", name: "n"}) { id } }'),
                     ("updateProtein", 'mutation { updateProtein(id: "rx16:p1", input: {name: "changed"}) { id } }'),
                     ("deleteProtein", 'mutation { deleteProtein(id: "rx16:p1") }')):
            L.refusal("API-X6.8", f"{k} under read-only", lambda: gql(q),
                      returns(lambda r: bool(r["body"].get("errors")) and "read-only" in json.dumps(r["body"]["errors"]),
                              "GraphQL error naming read-only mode"),
                      after=lambda: {"rows": node_rows(L, "rx16:new1", "rx16:p1")}, entry="sample API /graphql")
        L.refusal("API-X6.8", "executeCypher CREATE under read-only",
                  lambda: gql('{ executeCypher(query: "CREATE (n:RX16 {id: \'rx16:w2\'}) RETURN n.id") }'),
                  returns(lambda r: "not allowed in read-only mode" in json.dumps(r["body"].get("data")),
                          "{'error': 'mutation queries not allowed in read-only mode'}"),
                  after=lambda: {"rows": node_rows(L, "rx16:w2")}, entry="sample API /graphql")
        # API-X6.1: depth limit
        _env()
        nest = "interactsWith(first: 2) { name "
        deep = 'query TooDeep { protein(id: "rx16:p1") { name ' + nest * 12 + "}" * 13 + "}"
        L.refusal("API-X6.1", "GraphQL query 13 levels deep", lambda: gql(deep),
                  returns(lambda r: any("depth" in json.dumps(e).lower() for e in r["body"].get("errors") or []),
                          "error naming the depth limit"), entry="sample API /graphql")
        ok = gql('query { protein(id: "rx16:p1") { name ' + nest * 3 + "}" * 4 + "}")
        L.note("API-X6.1", "control: 4 levels are not refused for depth",
               depth_errors=[e for e in ok["body"].get("errors") or [] if "depth" in json.dumps(e).lower()])
        # API-X6.91 / X6.93: protein mutations
        L.refusal("API-X6.91", "createProtein of an id the default graph holds",
                  lambda: gql('mutation { createProtein(input: {id: "rx16:p1", name: "dup"}) { id } }'),
                  returns(lambda r: "already exists" in json.dumps(r["body"].get("errors")), "error: already exists"),
                  after=lambda: {"props": L.c.sql("SELECT graph_id, \"key\", val FROM Graph_KG.rdf_props "
                                                  "WHERE s='rx16:p1'")}, entry="sample API /graphql")
        L.refusal("API-X6.91", "createProtein with a 3-wide vector",
                  lambda: gql('mutation { createProtein(input: {id: "rx16:new2", name: "v", embedding: [0.1, 0.2, 0.3]})'
                              ' { id } }'),
                  returns(lambda r: "768-dimensional" in json.dumps(r["body"].get("errors")), "error: 768-dimensional"),
                  after=lambda: {"rows": node_rows(L, "rx16:new2")}, entry="sample API /graphql")
        L.refusal("API-X6.93", "deleteProtein of an id only a named graph holds",
                  lambda: gql('mutation { deleteProtein(id: "rx16:p3") }'),
                  returns(lambda r: "not found" in json.dumps(r["body"].get("errors")), "error: not found"),
                  after=lambda: {"rows": node_rows(L, "rx16:p3")}, entry="sample API /graphql")
        L.refusal("API-X6.93", "deleteProtein of an id the default and a named graph hold",
                  lambda: gql('mutation { deleteProtein(id: "rx16:p2") }'),
                  returns(lambda r: "more than one graph" in json.dumps(r["body"].get("errors")),
                          "error: held by more than one graph"),
                  after=lambda: {"rows": node_rows(L, "rx16:p2")}, entry="sample API /graphql")
        # API-X7.3: graph name check on the FHIR event route
        _env()
        for k, g in (("control character", "bad\u0001name"), ("257 characters", "g" * 257), ('"0"', "0")):
            L.refusal("API-X7.3", f"POST /fhir-event/ graph {k}",
                      lambda: (lambda r: {"status": r.status_code})(tc.post("/fhir-event/", json={**payload, "graph": g})),
                      returns(lambda r: r["status"] == 422, "422"),
                      after=lambda: {"rows": node_rows(L, "Condition/rx16c1", "rx16c1")}, entry="sample API /fhir-event/")
        # API-X7.9: no engine
        app0 = sample.create_app(engine=None)
        tc0 = TestClient(app0)
        L.refusal("API-X7.9", "POST /fhir-event/ on an app with no engine",
                  lambda: (lambda r: {"status": r.status_code, "body": r.json()})(tc0.post("/fhir-event/", json=payload)),
                  returns(lambda r: r["status"] == 503, "503"),
                  after=lambda: {"rows": node_rows(L, "Condition/rx16c1", "rx16c1")}, entry="sample API /fhir-event/")
    finally:
        _env()


def c_gql_depth_configured(L):
    """API-X6.1 'past the level an operator sets': IVG_GRAPHQL_MAX_DEPTH is read when the schema module loads, so a
    fresh process; the refusal is in validation, before any resolver (no IRIS)."""
    code = ("import json; from api.gql.schema import schema\n"
            "nest = 'interactsWith(first: 2) { name '\n"
            "q = 'query Q { protein(id: \"x\") { name ' + nest * 3 + '}' * 4 + '}'\n"
            "r = schema.execute_sync(q)\n"
            "print('RESULT', json.dumps([str(e) for e in (r.errors or [])]))\n")
    for k, v, want in (("set to 3", "3", True), ("unusable value 'ten' (default 10)", "ten", False)):
        def run():
            env = {kk: vv for kk, vv in os.environ.items() if not kk.startswith("IRIS_")}
            env.update({"IVG_GRAPHQL_MAX_DEPTH": v, "IRIS_HOST": "127.0.0.1", "IRIS_PORT": "9"})
            p = subprocess.run([PY, "-c", code], cwd=str(REPO), env=env, capture_output=True, text=True, timeout=120)
            line = next((x for x in p.stdout.splitlines() if x.startswith("RESULT ")), "RESULT null")
            return {"exit": p.returncode, "errors": json.loads(line[7:]), "stderr": p.stderr[-300:]}
        if want:
            L.refusal("API-X6.1", f"GraphQL 4 levels with IVG_GRAPHQL_MAX_DEPTH {k}", run,
                      returns(lambda r: any("depth" in e.lower() for e in r["errors"] or []), "error naming the depth"),
                      entry="api.gql.schema (fresh process)")
        else:
            L.note("API-X6.1", f"control: IVG_GRAPHQL_MAX_DEPTH {k} accepts 4 levels", result=run())


def c_ivg_gql(L):
    from starlette.testclient import TestClient
    from iris_vector_graph.gql import create_app
    L.fresh_engine()
    app = create_app(L.eng)
    tc = TestClient(app)
    _env(IVG_READ_ONLY="true")
    try:
        q = '{ cypher(query: "CREATE (n:RX16 {id: \'rx16:g1\'}) RETURN n.id AS id") { columns rows } }'
        L.refusal("API-X10.2", "generated GraphQL cypher field CREATE under read-only",
                  lambda: (lambda r: {"status": r.status_code, "body": r.json()})(tc.post("/graphql", json={"query": q})),
                  returns(lambda r: "not allowed in read-only mode" in json.dumps(r["body"].get("errors")),
                          "GraphQL error (PermissionError)"),
                  after=lambda: {"rows": node_rows(L, "rx16:g1")}, entry="iris_vector_graph.gql app /graphql")
    finally:
        _env()


# ------------------------------------------------------------------------------------------------ fraud server
class _Inert(types.ModuleType):
    """A module stand-in whose every attribute is a callable stand-in (torch/structlog are not installed here)."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _InertObj()


class _InertObj:
    def __call__(self, *a, **k):
        return _InertObj()

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _InertObj()


def c_fraud(L):
    from starlette.testclient import TestClient
    saved = {k: sys.modules.get(k) for k in ("torch", "structlog")}
    for k in saved:
        if saved[k] is None:
            sys.modules[k] = _Inert(k)
    sys.path.insert(0, str(REPO / "src"))
    try:
        from iris_fraud_server import app as fraud
        tc = TestClient(fraud.create_app())  # no lifespan: the startup event (model, IRIS SQL) does not run
        body = {"mode": "MLP", "payer": "acct:rx16", "device": "dev:rx16", "ip": "ip:127.0.0.1",
                "merchant": "merchant:rx16", "amount": 1.0}
        post = lambda b: (lambda r: {"status": r.status_code, "body": r.json()})(tc.post("/fraud/score", json=b))  # noqa
        for f in ("payer", "device", "ip", "merchant"):
            L.refusal("API-X13.6", f"POST /fraud/score {f} without a colon", lambda: post({**body, f: "nocolon"}),
                      returns(lambda r: r["status"] == 422 and "Expected 'namespace:id'" in json.dumps(r["body"]),
                              "422 naming the id format"), entry="fraud server (ASGI)")
        L.refusal("API-X13.106", "POST /fraud/score mode EGO", lambda: post({**body, "mode": "EGO"}),
                  returns(lambda r: r["status"] == 501 and "not implemented" in json.dumps(r["body"]),
                          "501 EGO mode not implemented"), entry="fraud server (ASGI)")
        L.refusal("API-X13.106", "POST /fraud/score mode XYZ", lambda: post({**body, "mode": "XYZ"}),
                  returns(lambda r: r["status"] == 422, "422 from the request model"), entry="fraud server (ASGI)")
        L.note("API-X13.106", "fraud server imported with inert torch/structlog stand-ins",
               stand_ins=[k for k, v in saved.items() if v is None])
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
        sys.modules.pop("iris_fraud_server.app", None)


# ------------------------------------------------------------------------------------------------ security helpers
def c_security(L):
    from iris_vector_graph import VectorOptimizer
    from iris_vector_graph.engine import IRISGraphEngine
    vo = VectorOptimizer(L.c.conn)
    for k, t in (("not a graph table", "secrets"), ("schema-qualified with SQL", "Graph_KG.nodes; DROP TABLE x"),
                 ("routed shape without 16 hex", "kg_emb_zz"), ("another schema's table", "Other.users")):
        L.refusal("API-X14.1", f"VectorOptimizer.get_vector_statistics {k}", lambda: vo.get_vector_statistics(t),
                  raises("ValueError", match=r"not in the allowlist"), entry="VectorOptimizer.get_vector_statistics")
    e = L.fresh_engine()
    e.create_node("rx16:v1", labels=["RX16"])
    L.c.conn.commit()
    for k, vec in (("a quote in an element", [1.0, 2.0, 3.0, "4'); --"]), ("a word element", [1.0, 2.0, 3.0, "x"])):
        L.refusal("API-X14.4", f"store_embedding with {k}", lambda: e.store_embedding("rx16:v1", vec),
                  raises("ValueError", match=r"not a number|not a vector"),
                  after=lambda: {"emb_rows": L.c.sql("SELECT COUNT(*) FROM Graph_KG.kg_NodeEmbeddings "
                                                     "WHERE id = 'rx16:v1'")[0][0]},
                  entry="engine.store_embedding")
    for k, dt in (("SQL in the type", "DOUBLE), 'x') --"), ("digits", "FLOAT32"), ("a space", "DOUBLE X")):
        L.refusal("API-X14.5", f"engine vector_dtype {k}", lambda: IRISGraphEngine(L.c.conn, vector_dtype=dt),
                  raises("ValueError", match=r"not a vector element type"), entry="IRISGraphEngine(vector_dtype=)")
    L.refusal("API-X14.5", "store_embedding dtype with digits",
              lambda: e.store_embedding("rx16:v1", [1.0, 2.0, 3.0, 4.0], dtype="FLOAT32"),
              raises("ValueError", match=r"not a vector element type"), entry="engine.store_embedding")


CASES = [("key_server", c_key_server), ("ro_server", c_ro_server), ("schema_width", c_schema_width),
         ("sample_api", c_sample_api), ("gql_depth_configured", c_gql_depth_configured), ("ivg_gql", c_ivg_gql),
         ("fraud", c_fraud), ("security", c_security)]


def main():
    only = sys.argv[1:] or None
    name = os.environ.get("RX_RESULTS", "results.json" if not only else "results-partial.json")
    with Lane("16") as L:
        L.reset()
        L.control()
        run_cases(L, CASES, only)
        L.reset()
        L.save(name)


if __name__ == "__main__":
    main()
