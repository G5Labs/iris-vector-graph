#!/usr/bin/env python3
"""F-C1306 probe, release side: commit two tenants' changesets through v4.5.1's own ledger.

Run by probe.py exactly the way the pinned fixture runs its own `_ledger_child`
(scripts/fixtures/build_release_namespace.py:run_ledger_commits): PYTHONPATH on the release worktree
`~/.cache/ivg-bench/releases/v4.5.1`, cwd there, IVG_BUILD_SCHEMA_PREFIX the release engine's schema_prefix.
It refuses to run unless `iris_vector_graph` resolves into that worktree. It commits through the release's public
`engine.ledger.commit(Changeset(...))`, compiles nothing, and prints its result with the fixture's `emit_result`.

    argv: <tag> <namespace>

Tenant T is the fixture's own `r114` (ids `r114:*`), tenant O is `o114` (ids `o114:*`). Every changeset carries a
message, a source, a correlation id and an idempotency key whose text starts `fc1306T-` (T) or `fc1306O-` (O).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

#: (tenant, message, source, correlation_id, idempotency_key, ops); ops are Changeset calls.
CHANGESETS = [
    ("T", "fc1306T-msg-3 onboarding note for tenant r114", {"system": "fc1306T-src-3"}, "fc1306T-corr-3",
     "fc1306T-idem-3",
     [("create_node", ("r114:c",), {"labels": ["R114"]}),
      ("set_property", ("r114:c", "secret", "fc1306T-val-c"), {}),
      ("create_relationship", ("r114:a", "R114", "r114:c"), {})]),
    ("O", "fc1306O-msg-1 onboarding note for tenant o114", {"system": "fc1306O-src-1"}, "fc1306O-corr-1",
     "fc1306O-idem-1",
     [("create_node", ("o114:a",), {"labels": ["O114"]}),
      ("create_node", ("o114:b",), {"labels": ["O114"]}),
      ("create_relationship", ("o114:a", "O114", "o114:b"), {})]),
    ("T", "fc1306T-msg-4 second note for tenant r114", {"system": "fc1306T-src-4"}, "fc1306T-corr-4",
     "fc1306T-idem-4",
     [("set_property", ("r114:b", "secret", "fc1306T-val-b"), {})]),
    ("O", "fc1306O-msg-2 second note for tenant o114", {"system": "fc1306O-src-2"}, "fc1306O-corr-2",
     "fc1306O-idem-2",
     [("set_property", ("o114:a", "secret", "fc1306O-val-a"), {})]),
]


def main() -> int:
    tag, ns = sys.argv[1], sys.argv[2]
    import iris
    import iris_vector_graph
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.ledger import Changeset

    # the fixture's helpers (emit_result, RELEASES, PORT, EMBEDDING_DIM), after the release's package is imported
    repo = Path(__file__).resolve().parents[3]
    sys.path.append(str(repo / "scripts" / "fixtures"))
    import build_release_namespace as brn

    here = Path(iris_vector_graph.__file__).resolve()
    if brn.RELEASES.resolve() not in here.parents:
        print(f"refusing: iris_vector_graph resolved to {here}, not the {tag} worktree", file=sys.stderr)
        return 2
    prefix = os.environ.get("IVG_BUILD_SCHEMA_PREFIX") or "Graph_KG"
    conn = iris.connect("localhost", brn.PORT, ns, "_SYSTEM", "SYS")
    committed = []
    try:
        engine = IRISGraphEngine(conn, embedding_dimension=brn.EMBEDDING_DIM, namespace=ns, schema_prefix=prefix)
        for tenant, message, source, corr, idem, ops in CHANGESETS:
            actor = "r114" if tenant == "T" else "o114"
            cs = Changeset(actor=actor, actor_type="system", message=message, source=source, correlation_id=corr,
                           idempotency_key=idem)
            for name, args, kwargs in ops:
                getattr(cs, name)(*args, **kwargs)
            res = engine.ledger.commit(cs)
            committed.append({"tenant": tenant, "result": repr(res)[:300]})
        cur = conn.cursor()
        cur.execute("SELECT seq, kind, actor, op_count, message, source, correlation_id, idempotency_key "
                    "FROM Graph_KG.ledger_revisions ORDER BY seq")
        rows = [[None if v is None else (int(v) if i in (0, 3) and v is not None else str(v))
                 for i, v in enumerate(r)] for r in cur.fetchall()]
    finally:
        conn.close()
    brn.emit_result({"package": str(here.parent), "committed": committed, "graph_kg_ledger_revisions": rows})
    return 0


if __name__ == "__main__":
    sys.exit(main())
