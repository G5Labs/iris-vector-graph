"""HD-1603 probe: does the Cypher HTTP server run a failed write a second time?

Drives the pin's FastAPI app (iris_vector_graph.cypher_api) in-process with Starlette's TestClient (no lifespan, so no
Bolt listener), with _make_engine pointed at namespace AUDITIB. One fault is injected into the FIRST engine only, in
the test process: (A) execute the write for real, then raise ConnectionError (a connection that drops after the
commit: an ambiguous outcome); (B) raise ValueError before executing (a deterministic, non-connection error).
SHARED lane lock. Data: label Ib1Retry, removed at the end.

What it discriminates (no stated contract; history only): in v1.47.0 (PR #8, 9c683292) _run_cypher retried only when
the error text named COMMUNICATION or LICENSE; 7d62dbf5 (v1.48.0) widened it to every exception without saying so.
Alternatives: (a) retry every exception once [as built]; (b) retry only connection errors before the statement ran;
(c) never retry.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

for var in ("IVG_API_KEY", "IVG_READ_ONLY"):
    os.environ.pop(var, None)

from fastapi.testclient import TestClient  # noqa: E402

import iris_vector_graph.cypher_api as api  # noqa: E402
from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

LABEL = "Ib1Retry"
conns = []


def new_engine():
    c = Conn("AUDITIB")
    conns.append(c)
    return IRISGraphEngine(c.conn, namespace="AUDITIB", embedding_dimension=4)


def count(c):
    return c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label = ?", LABEL)[0][0]


def run_scenario(name, inject):
    calls = {"n": 0}
    made = {"n": 0}

    def make():
        eng = new_engine()
        made["n"] += 1
        real = eng.execute_cypher

        depth = {"d": 0}

        def wrapped(query, *a, **kw):
            # count only the server's top-level calls: the engine may call execute_cypher on itself internally
            top = depth["d"] == 0
            if top:
                calls["n"] += 1
            depth["d"] += 1
            try:
                if top and made["n"] == 1 and calls["n"] == 1:
                    return inject(real, query, *a, **kw)
                return real(query, *a, **kw)
            finally:
                depth["d"] -= 1

        eng.execute_cypher = wrapped
        return eng

    api._make_engine = make
    api._engine_cache = None
    client = TestClient(api.app)
    resp = client.post("/api/cypher", json={"query": f"CREATE (n:{LABEL} {{tag: '{name}'}}) RETURN n.tag"})
    return resp, calls["n"], made["n"]


def after_commit_drop(real, query, *a, **kw):
    real(query, *a, **kw)
    raise ConnectionError("simulated: connection dropped after the statement committed")


def deterministic_refusal(real, query, *a, **kw):
    raise ValueError("simulated: deterministic refusal before execution")


def main():
    probe = Conn("AUDITIB")
    cleanup_engine = IRISGraphEngine(probe.conn, namespace="AUDITIB", embedding_dimension=4)
    cleanup_engine.execute_cypher(f"MATCH (n:{LABEL}) DETACH DELETE n")
    before = count(probe)
    resp, calls, made = run_scenario("A", after_commit_drop)
    after_a = count(probe)
    print(f"OBS A (drop after commit): HTTP {resp.status_code}; execute_cypher calls {calls}; engines made {made}; "
          f"nodes written {after_a - before}")
    resp, calls, made = run_scenario("B", deterministic_refusal)
    after_b = count(probe)
    print(f"OBS B (ValueError before execution): HTTP {resp.status_code}; execute_cypher calls {calls}; "
          f"engines made {made}; nodes written {after_b - after_a}")
    print("RESULT one client request, one CREATE, ambiguous first outcome ->",
          "written twice (retry of a committed write)" if after_a - before == 2 else f"written {after_a - before}x")
    print("RESULT a non-connection error is retried (second engine made, second top-level call):",
          calls == 2 and made == 2)
    cleanup_engine.execute_cypher(f"MATCH (n:{LABEL}) DETACH DELETE n")
    print("OBS cleanup count:", count(probe))
    for c in conns:
        c.close()
    probe.close()


if __name__ == "__main__":
    main()
