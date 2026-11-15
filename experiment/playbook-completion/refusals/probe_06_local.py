#!/usr/bin/env python3
"""Module 06: pin code against a stand-in connection whose registry SELECT fails with a privilege error (no IRIS).

    python experiment/playbook-completion/refusals/probe_06_local.py   # -> $RUN_DIR/refusals/06/local.json

The live namespace cannot produce "the registry is there but cannot be read": that needs a second IRIS user without
SELECT on Graph_KG.embedding_registry (the versions lane's least-privilege user is disabled and is not this lane's to
enable). The same condition is put to the pin's own methods here through a cursor that raises SQLCODE -99 on that
table, as the breadth-a lane did for F-0601. Graded `probe` (pin code, stand-in connection), never `live`.
  VEC-X1.16  a write's identity check when the registry read fails   (stated: refused)
  VEC-X8.4   embedding_inventory when the registry read fails        (stated: raises, not an empty report)
  VEC-X2.16  the route read when the registry read fails             (stated: raises, no legacy fallback)
  VEC-X4.5   embedding_count when its count fails                    (stated: raises, not 0)
Control: the same methods with a registry-absent error (SQLCODE -30) behave as documented for an absent registry.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

PRIV = "[SQLCODE: <-99>:<Privilege violation>] SELECT on Graph_KG.embedding_registry"
ABSENT = "[SQLCODE: <-30>:<Table or view not found>] Graph_KG.embedding_registry"


class Cur:
    def __init__(self, msg):
        self.msg = msg

    def execute(self, sql, params=None):
        raise RuntimeError(self.msg)

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConn:
    def __init__(self, msg):
        self.msg = msg

    def cursor(self):
        return Cur(self.msg)

    def commit(self):
        pass

    def rollback(self):
        pass


def subject(msg):
    from iris_vector_graph._engine.schema import SchemaMixin
    from iris_vector_graph._engine.embeddings import EmbeddingsMixin

    class S(EmbeddingsMixin, SchemaMixin):
        _ivg_schema = "Graph_KG"
        _schema_prefix = "Graph_KG"
        embedding_config = None
        embedder = None
        vector_dtype = "DOUBLE"
        embedding_dimension = 4

        def __init__(self):
            self.conn = FakeConn(msg)
            self._route_cache = {}

        def _t(self, name):
            return f"Graph_KG.{name}"

    return S()


def call(fn):
    try:
        return {"returned": repr(fn())[:300]}
    except Exception as e:  # noqa: BLE001
        return {"raised": f"{type(e).__name__}: {str(e)[:300]}"}


def main():
    out = {"doc": __doc__.strip(), "cases": []}
    for label, msg in (("privilege", PRIV), ("absent-control", ABSENT)):
        s = subject(msg)
        rows = [
            ("VEC-X1.16", "enforce_embedding_identity",
             call(lambda: s.enforce_embedding_identity("kg_emb_0123456789abcdef", dimension=4, graph_id="g"))),
            ("VEC-X8.4", "embedding_inventory", call(lambda: s.embedding_inventory())),
            ("VEC-X2.16", "_read_route", call(lambda: s._read_route("g", None))),
            ("VEC-X4.5", "embedding_count", call(lambda: s.embedding_count())),
        ]
        for sid, meth, r in rows:
            out["cases"].append({"statement": sid, "condition": label, "method": meth, **r})
    verdict = {}
    for c in out["cases"]:
        if c["condition"] != "privilege":
            continue
        refused = "raised" in c
        verdict[c["statement"]] = "refused (raised)" if refused else "NOT refused: " + c.get("returned", "")
    out["verdict_under_privilege_error"] = verdict
    p = Path(os.environ["RUN_DIR"]) / "refusals" / "06" / "local.json"
    p.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out["cases"], indent=1))
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    main()
