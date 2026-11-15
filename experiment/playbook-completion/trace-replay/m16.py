"""Module 16 (interfaces): trace replay through unit (M2), models/breadth-c/src/unit.rs.

Both entry points are driven in-process (no listening socket):
- bolt: the product's Bolt message dispatcher (iris_vector_graph/bolt_server.py BoltSession._dispatch) with a harness
  transport (the subclass overrides only _send_message, as the product's own TcpBoltSession does) and an engine on
  the step's identity-checked connection. The unit: BEGIN, RUN w1 (+PULL), RUN of a statement that fails (FAILURE),
  RESET (what a driver sends to end a failed transaction; the server IGNOREs ROLLBACK in the FAILED state), then the
  driver's managed retry: BEGIN, RUN w1 (+PULL), RUN w2 (+PULL), COMMIT (F-1601: every RUN committed at once; the
  failed attempt's w1 stays and the retry writes it again).
- http: POST /db/neo4j/tx/commit with two statements, the second failing, through FastAPI's TestClient over the
  product's cypher_api app (no lifespan, so no Bolt listener) (F-1610: the first statement stays committed); then
  the client's resend of the unit without the fault (unit.rs DriverRetry: the first statement is applied twice).
A fault-free Bolt unit (BEGIN, RUN a1, RUN a2, COMMIT) runs first on the same session, as its own machine instance.
The failing statement stands in for a transient failure of w2 (unit.rs's Run2 { ok: false }); the retry's w2 is the
same statement without the fault.
"""
from __future__ import annotations

import asyncio
import os

import trlib
from common import engine, pid_of_dbapi, reset
from families_c import Unit

DESIGNS = ["as-built", "reviewed"]
W1 = "CREATE (n:TR16W1 {marker: 'tr16w1'}) RETURN n.marker AS m"
W2 = "CREATE (n:TR16W2 {marker: 'tr16w2'}) RETURN n.marker AS m"
BAD = "THIS IS NOT CYPHER"


def _env():
    os.environ.update({"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": trlib.NS,
                       "IRIS_USERNAME": "_SYSTEM", "IRIS_PASSWORD": "SYS", "BOLT_ENABLED": "0"})
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)


def _msg(tag: int, *fields) -> bytes:
    from iris_vector_graph.bolt_server import PackStream
    return bytes([0xB0 + len(fields), tag]) + b"".join(PackStream.pack(f) for f in fields)


def s_bolt(cap: trlib.Capture):
    _env()
    reset()
    from iris_vector_graph import bolt_server as bs

    class HarnessBolt(bs.BoltSession):
        def __init__(self, get_engine_fn):
            super().__init__(None, get_engine_fn)
            self.out = []
            self.state = bs.BoltState.READY

        async def _send_message(self, tag, *fields):
            self.out.append({"tag": hex(tag), "fields": [str(f)[:200] for f in fields]})

    sess = {}
    cap.begin()

    def send(*msgs):
        def f(c):
            if "s" not in sess:
                sess["s"] = HarnessBolt(lambda: engine(c))
            s = sess["s"]
            s.out = []
            for m in msgs:
                asyncio.run(s._dispatch(m))
            return {"replies": s.out, "state": str(s.state)}
        return f
    run = lambda q: [_msg(bs.TAG_RUN, q, {}, {}), _msg(bs.TAG_PULL, {"n": -1})]  # noqa: E731
    # a first, fault-free unit on the same session (its own machine instance): BEGIN, RUN a1, RUN a2, COMMIT
    for op, msgs, act in (("bolt BEGIN", [_msg(bs.TAG_BEGIN, {})], "Begin"),
                          ("bolt RUN w1", run(W1.replace("TR16W1", "TR16A1")), "Run1"),
                          ("bolt RUN w2", run(W2.replace("TR16W2", "TR16A2")), "Run2"),
                          ("bolt COMMIT", [_msg(bs.TAG_COMMIT)], "Commit")):
        cap.step(op, send(*msgs), who="bolt", unit="bolt-a")
        st = cap.steps[-1]
        failed = any(r["tag"] == hex(bs.TAG_FAILURE) for r in (st["reply"] or {}).get("replies", []))
        st["model"] = [["Run2", not failed]] if act == "Run2" else [[act]]
    plan = [("bolt BEGIN", [_msg(bs.TAG_BEGIN, {})], "Begin"),
            ("bolt RUN w1", run(W1), "Run1"),
            ("bolt RUN w2", [_msg(bs.TAG_RUN, BAD, {}, {})], "Run2"),
            ("bolt RESET", [_msg(bs.TAG_RESET)], "Rollback"),
            ("bolt BEGIN", [_msg(bs.TAG_BEGIN, {})], "DriverRetry"),
            ("bolt RUN w1", run(W1), "Run1"),
            ("bolt RUN w2", run(W2), "Run2"),
            ("bolt COMMIT", [_msg(bs.TAG_COMMIT)], "Commit")]
    for op, msgs, act in plan:
        cap.step(op, send(*msgs), who="bolt", unit="bolt")
        st = cap.steps[-1]
        failed = any(r["tag"] == hex(bs.TAG_FAILURE) for r in (st["reply"] or {}).get("replies", []))
        st["model"] = [["Run2", not failed]] if act == "Run2" else [[act]]


def s_http(cap: trlib.Capture):
    _env()
    reset()
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api as api
    with api._engine() as e:
        pid0 = pid_of_dbapi(e.conn)
    tc = TestClient(api.app)

    def after():
        with api._engine_lock:
            api._reset_engine()
        tc.close()
    cap.after = [after]
    cap.begin()

    def post(stmts):
        def f(c):
            r = tc.post("/db/neo4j/tx/commit", json={"statements": [{"statement": q} for q in stmts]})
            with api._engine_lock:
                pid1 = pid_of_dbapi(api._get_engine().conn)
            return {"status": r.status_code, "body": r.json()}, sorted({pid0, pid1})
        return f
    h1, h2 = W1.replace("TR16W1", "TR16H1"), W2.replace("TR16W2", "TR16H2")
    # the request with a failing second statement, then the client's resend of the unit without the fault
    for i, (stmts, first) in enumerate((([h1, BAD], ["Begin"]), ([h1, h2], ["DriverRetry"]))):
        cap.step("POST /db/neo4j/tx/commit", post(stmts), unit="http")
        st = cap.steps[-1]
        errs = (st["reply"] or {}).get("body", {}).get("errors", [])
        st["model"] = [first, ["Run1"], ["Run2", not errs]]


SCENARIOS = {"bolt": s_bolt, "http": s_http}

EXPECT = {
    "bolt": [("unit[as-built]bolt", Unit.ATOMIC, "F-1601"), ("unit[as-built]bolt", Unit.ONCE, "F-1601")],
    "http": [("unit[as-built]http", Unit.ATOMIC, "F-1610"), ("unit[as-built]http", Unit.ONCE, "F-1610")],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "bolt":
        return [Unit("bolt-a", "TR16A1", "TR16A2", design), Unit("bolt", "TR16W1", "TR16W2", design)]
    if name == "http":
        return [Unit("http", "TR16H1", "TR16H2", design)]
    raise KeyError(name)


def footprint(trace):
    bolt = trlib.declared("16", ["Bolt RUN (TCP / WebSocket), inside BEGIN..ROLLBACK"])
    return {"bolt BEGIN": set(), "bolt RUN w1": bolt, "bolt RUN w2": bolt, "bolt RESET": set(), "bolt COMMIT": set(),
            "POST /db/neo4j/tx/commit": trlib.declared("16", ["POST /db/neo4j/tx/commit (N statements)"])}
