"""HD-1605 probe: the generated GraphQL app's depth limit and health route, against the sample API's.

Generated app: iris_vector_graph.gql.create_app(engine) on namespace AUDITIB, driven in-process with TestClient.
Data: default-graph node ib1_gq_loop (label Ib1Loop) with a self-loop, so outgoing{node{outgoing{...}}} resolves at
every level. SHARED lane lock.
Observes: (1) whether a query nested 14 levels through outgoing/node is rejected at validation (as the sample API's
QueryDepthLimiter, default 10, does, api/gql/schema.py:287-327) or runs; (2) the generated schema's extensions;
(3) /health with the engine's connection closed.
No stated contract for the generated app's depth (spec 019 was a Draft MVP and listed security as future work);
the sample API's limit comes from spec 003 (CHANGELOG.md:4297-4308).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

for var in ("IVG_API_KEY", "IVG_READ_ONLY"):
    os.environ.pop(var, None)

from fastapi.testclient import TestClient  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
from iris_vector_graph.gql import create_app  # noqa: E402

NODE = "ib1_gq_loop"
DEPTH = 14


def nested(depth):
    q = "id"
    for _ in range(depth):
        q = f"id outgoing {{ predicate node {{ {q} }} }}"
    return f'{{ node(id: "{NODE}") {{ {q} }} }}'


def deepest(data):
    d, cur = 0, data.get("node") if data else None
    while cur and cur.get("outgoing"):
        cur = cur["outgoing"][0].get("node")
        d += 1
    return d


def main():
    c = Conn("AUDITIB")
    eng = IRISGraphEngine(c.conn, namespace="AUDITIB", embedding_dimension=4)
    eng.delete_nodes_by_prefix("ib1_gq_")
    eng.create_node(NODE, labels=["Ib1Loop"], properties={"name": "loop"})
    eng.create_edge(NODE, "SELF", NODE)
    app = create_app(eng)
    client = TestClient(app)
    resp = client.post("/graphql", json={"query": nested(DEPTH)})
    body = resp.json()
    errs = body.get("errors")
    print(f"OBS generated app, query nested {DEPTH} levels: HTTP {resp.status_code}; errors "
          f"{[e.get('message')[:120] for e in errs] if errs else None}; levels resolved {deepest(body.get('data'))}")
    try:
        from iris_vector_graph.gql import schema as gschema  # noqa: F401
        ext = app.router.routes  # noqa: F841
    except Exception:  # noqa: BLE001
        pass
    try:
        import api.gql.schema as sample
        print("OBS sample API schema extensions:", [type(e).__name__ if not isinstance(e, type) else e.__name__
                                                     for e in sample.schema.extensions],
              "max depth", sample._max_query_depth())
    except Exception as exc:  # noqa: BLE001
        print("OBS sample API schema not importable here:", type(exc).__name__, str(exc)[:120])

    # health with the database gone
    c2 = Conn("AUDITIB")
    eng2 = IRISGraphEngine(c2.conn, namespace="AUDITIB", embedding_dimension=4)
    app2 = create_app(eng2)
    c2.conn.close()
    h = TestClient(app2).get("/health")
    print(f"OBS generated app /health with its connection closed: HTTP {h.status_code} {h.json()}")
    rejected = bool(errs) and any("depth" in (e.get("message") or "").lower() for e in errs)
    print("RESULT generated app depth limit enforced:", rejected)
    print("RESULT generated app health reports healthy with no database:",
          h.status_code == 200 and h.json().get("status") == "healthy")
    eng.delete_nodes_by_prefix("ib1_gq_")
    c.close()


if __name__ == "__main__":
    main()
