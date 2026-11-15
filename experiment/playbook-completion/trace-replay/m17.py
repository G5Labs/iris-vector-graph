"""Module 17 (operations, the HTTP client): trace replay through retry (M1), models/breadth-c/src/retry.rs.

Scenario retry: one IVGClient.execute_cypher write (iris_vector_graph/sdk.py:209-228) against the product's Cypher
HTTP app (cypher_api.app, in-process through FastAPI's TestClient transport, no socket). The harness transport hands
the first request to the app and, after the app answered, raises httpx.ReadTimeout: the acknowledgement is lost
although the write committed (the ambiguous outcome HD-1702 names). The client resends; the second reply is
delivered (F-C1703: one call creates the write twice). A second call with its own marker gets every reply (the
model's exactly-once path). Nothing in the product is changed; the fault is in the
harness's transport.
"""
from __future__ import annotations

import os
import time

import trlib
from common import pid_of_dbapi, reset
from families_c import Retry

DESIGNS = ["as-built", "reviewed"]
MARKER = "tr17dup"
MARKER2 = "tr17once"
Q = "CREATE (n:TR17Dup {marker: $m}) RETURN n.marker AS m"


def _env():
    os.environ.update({"IRIS_HOST": "127.0.0.1", "IRIS_PORT": os.environ["IVG_PORT"], "IRIS_NAMESPACE": trlib.NS,
                       "IRIS_USERNAME": "_SYSTEM", "IRIS_PASSWORD": "SYS", "BOLT_ENABLED": "0"})
    for k in ("IVG_API_KEY", "IVG_READ_ONLY"):
        os.environ.pop(k, None)


def s_retry(cap: trlib.Capture):
    _env()
    reset()
    import httpx
    from fastapi.testclient import TestClient
    from iris_vector_graph import cypher_api as api
    from iris_vector_graph.sdk import IVGClient
    with api._engine() as e:
        pid0 = pid_of_dbapi(e.conn)
    tc = TestClient(api.app)
    log = []

    class LostAck(httpx.BaseTransport):
        """Forwards to the app; loses the reply of the first `drop` requests after the app answered."""

        def __init__(self, inner, drop=1):
            self.inner, self.drop = inner, drop

        def handle_request(self, request):
            resp = self.inner.handle_request(request)
            resp.read()
            ev = {"delivered": True, "status": resp.status_code, "t": round(time.time(), 3)}
            log.append(ev)
            if self.drop > 0:
                self.drop -= 1
                ev["reply_delivered"] = False
                raise httpx.ReadTimeout("harness: reply lost after the server answered", request=request)
            ev["reply_delivered"] = True
            return resp

    def after():
        with api._engine_lock:
            api._reset_engine()
        tc.close()
    cap.after = [after]
    cap.begin()

    def call(marker):
        def f(c):
            cl = IVGClient("http://testserver", max_retries=3, timeout=30.0)
            cl._client = httpx.Client(base_url="http://testserver", transport=LostAck(tc._transport, drop=1 if marker == MARKER else 0),
                                    timeout=30.0)
            try:
                r = cl.execute_cypher(Q, {"m": marker})
                out = {"rows": r.rows}
            finally:
                cl.close()
            with api._engine_lock:
                pid1 = pid_of_dbapi(api._get_engine().conn)
            return out, sorted({pid0, pid1})
        return f
    # call 1: its first reply is lost (LostAck drops one); call 2: a second write, every reply delivered
    for marker in (MARKER, MARKER2):
        n = len(log)
        cap.step("IVGClient.execute_cypher", call(marker), marker=marker)
        cap.steps[-1]["transport"] = list(log[n:])


SCENARIOS = {"retry": s_retry}

EXPECT = {"retry": [("retry[as-built]" + MARKER, Retry.ONCE, "F-C1703")]}


def families(trace, design):
    return [Retry("Write", MARKER, design), Retry("Write", MARKER2, design)]


def footprint(trace):
    return {"IVGClient.execute_cypher": trlib.declared("16", ["POST /api/cypher (write)"])}
