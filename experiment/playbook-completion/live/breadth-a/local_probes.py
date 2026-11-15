"""Local (no IRIS) checks of findings whose trigger is a database failure IRIS cannot be made to produce on demand
without changing the product or the server: the pin's own functions run against fake connections that fail the one
call the finding names. Evidence grade: a test-style reproduction (the product code ran; the database was a fake).

    python experiment/playbook-completion/live/breadth-a/local_probes.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
import logging
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
RESULTS = HERE / "results"
LOG = Path(os.environ["RUN_DIR"]) / "breadth-a" / "live" / f"local-{dt.datetime.now():%Y%m%dT%H%M%S}.log"


class FailingCursor:
    def __init__(self, msg):
        self.msg = msg
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        raise Exception(self.msg)

    def fetchone(self):
        return None

    def close(self):
        pass


class FakeConn:
    def __init__(self, msg):
        self.msg = msg
        self.cursors = []

    def cursor(self):
        c = FailingCursor(self.msg)
        self.cursors.append(c)
        return c

    def commit(self):
        pass


class FakeIris:
    """%SYSTEM.OBJ.Delete fails: the status is an error, IsOK answers 0."""

    def __init__(self):
        self.calls = []

    def classMethodValue(self, cls, method, *args):
        self.calls.append((cls, method, args))
        if (cls, method) == ("%SYSTEM.OBJ", "Delete"):
            return "0 error"
        if (cls, method) == ("%SYSTEM.Status", "IsOK"):
            return 0
        raise AssertionError((cls, method))


def f0101(r):
    """F-0101: remove_legacy_objects marks a view removed when DROP VIEW failed, and marks every later item of a class
    removed when the class delete failed. Oracle: data-model.md:50-60 (`removed` is whether it was dropped)."""
    from iris_vector_graph._engine import legacy
    items = [
        {"kind": "view", "sql_name": "SQLUser.kg_old_view", "class_name": "User.kgoldview", "ivg_owned": True},
        {"kind": "procedure", "sql_name": None, "class_name": "User.CypherFn", "ivg_owned": True},
        {"kind": "procedure", "sql_name": None, "class_name": "User.CypherFn", "ivg_owned": True},
    ]
    orig = legacy.present_legacy_objects
    legacy.present_legacy_objects = lambda conn, iris_obj, with_grants=True: [dict(i) for i in items]
    try:
        out = legacy.remove_legacy_objects(FakeConn("SQLCODE -30 DROP VIEW refused"), FakeIris(), dry_run=False)
    finally:
        legacy.present_legacy_objects = orig
    r["observed"] = {"removed": [(i["kind"], i["class_name"], i.get("removed")) for i in out],
                     "every_drop_and_delete_failed": True}
    r["oracle"] = "removed is True only for an object that was dropped or deleted"
    r["reproduced"] = out[0].get("removed") is True and out[2].get("removed") is True
    r["verdict"] = "view and second SqlProc item reported removed although every drop/delete failed"


def f0601(r):
    """F-0601: get_embedding_identity answers None (nothing recorded) for any failure of the registry read, so
    enforce_embedding_identity lets the write through; a privilege error (SQLCODE -99) is not a missing registry.
    Oracle: ADR-0006 (refusable before it happens) and FR-014 (not opt-in)."""
    from iris_vector_graph._engine.schema import SchemaMixin

    class Self(SchemaMixin):
        _ivg_schema = "Graph_KG"

        def __init__(self):
            self.conn = FakeConn("[SQLCODE: <-99>:<Privilege violation>] SELECT on Graph_KG.embedding_registry")

        def _t(self, name):
            return f"Graph_KG.{name}"

    s = Self()
    rec = s.get_embedding_identity("kg_emb_abc", graph_id="g")
    try:
        res = s.enforce_embedding_identity("kg_emb_abc", dimension=8, graph_id="g")
        enforced = f"returned {res!r} (write proceeds)"
    except Exception as e:
        enforced = f"raised {type(e).__name__}: {e}"
    r["observed"] = {"get_embedding_identity": repr(rec), "enforce_embedding_identity": enforced}
    r["oracle"] = "a registry read that fails for any reason but absence refuses the write"
    r["reproduced"] = rec is None and enforced.startswith("returned")
    r["verdict"] = "privilege error on the registry read turned the identity check off"


def main():
    LOG.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    logging.basicConfig(stream=buf, level=logging.DEBUG)
    for fn in (f0101, f0601):
        r = {"id": f"local_{fn.__name__}", "doc": fn.__doc__.strip(), "module": fn.__name__[1:3]}
        try:
            fn(r)
        except Exception as e:
            import traceback
            r["error"] = traceback.format_exc()
            r["reproduced"] = None
        r["log"] = "$RUN_DIR/" + str(LOG.relative_to(Path(os.environ["RUN_DIR"])))
        buf.write(json.dumps(r, indent=1, default=str) + "\n")
        print(json.dumps(r, indent=1, default=str))
        (RESULTS / f"local_{fn.__name__}.json").write_text(json.dumps(r, indent=1, sort_keys=True, default=str) + "\n")
    LOG.write_text(buf.getvalue())
    print("log:", LOG)


if __name__ == "__main__":
    main()
