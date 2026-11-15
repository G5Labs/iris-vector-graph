"""Shared helper for breadth lane C live checks in namespace AUDITC (journal-validated footprints).

    from jcheck import Lane
    with Lane("c18") as L:                      # identity-checked Conn("AUDITC") + engine on the same process
        r = L.journaled("save", lambda: L.eng.save_snapshot(path))
        # r = {"label", "pid", "stores_written": [...], "units": [...], "outside_txn": [...], "records": n, "result"}

Nothing is compiled; product classes are the pin's, deployed by initialize_schema. Scratch content uses the lane's
own prefix (graph names and node ids start with the lane tag) so lanes never touch each other's data.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPLETION = HERE.parents[1]
sys.path.insert(0, str(COMPLETION / "tools"))
sys.path.insert(0, str(COMPLETION / "traces"))

from iris_conn import Conn  # noqa: E402
import journal  # noqa: E402

NS = "AUDITC"
DB = "/usr/irissys/mgr/auditc/"


def run_dir(sub: str) -> Path:
    p = Path(os.environ["RUN_DIR"]) / "breadth-c" / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


class Lane:
    def __init__(self, tag: str, engine: bool = True, **engine_kw):
        self.tag = tag
        self.c = Conn(NS)
        self.eng = None
        if engine:
            from iris_vector_graph.engine import IRISGraphEngine
            self.eng = IRISGraphEngine(self.c.conn, namespace=NS, **engine_kw)
        self._smap = None

    @property
    def smap(self):
        if self._smap is None:
            self._smap = journal.storage_map(self.c)
        return self._smap

    def journaled(self, label: str, fn, extra_pids=()):
        """Run fn() and return the journal's account of what this process (and extra_pids) wrote."""
        pids = {self.c.pid, *map(str, extra_pids)}
        m = journal.mark()
        err = None
        t0 = time.time()
        try:
            res = fn()
        except Exception as e:  # the outcome is data
            res = None
            err = f"{type(e).__name__}: {e}"[:2000]
            tb = traceback.format_exc()[-3000:]
        else:
            tb = None
        dt = time.time() - t0
        recs = journal.records_since(m, dbs={DB})
        mine = [r for r in recs if r["p"] in pids]
        others = sorted({r["p"] for r in recs} - pids)
        units = journal.transactions(mine)
        smap = self.smap
        stores = sorted({journal.store_of(r["g"], smap) for r in mine if r["g"]})
        # Classify each SET/KILL by the process's transaction bracket at that point in the journal:
        #   txn        inside an outermost BeginTrans..CommitTrans and journaled as transactional
        #   increment  inside a bracket but journaled non-transactional: IRIS $INCREMENT / ID counters, which a
        #              rollback does not undo by design (extent ID counters, ^KG("__version"), bitmap word counts)
        #   autocommit outside any bracket: a write no transaction covers
        open_ = {}
        cls = {"txn": set(), "increment": set(), "autocommit": set()}
        for r in mine:
            t = r["t"]
            if t == "BeginTrans":
                open_[r["p"]] = True
                continue
            if t == "CommitTrans" or t.startswith("RollBack") or t == "Rollback":
                open_.pop(r["p"], None)
                continue
            if not r["g"]:
                continue
            st = journal.store_of(r["g"], smap)
            if open_.get(r["p"]):
                cls["txn" if r["x"] else "increment"].add(st)
            else:
                cls["autocommit"].add(st)
        txn_units = [u for u in units if u["kind"] == "txn"]
        return {
            "label": label, "pid": self.c.pid, "seconds": round(dt, 3), "error": err, "traceback": tb,
            "result": _jsonable(res), "records": len(mine), "other_pids_in_window": others,
            "stores_written": stores,
            "stores_written_in_txn": sorted(cls["txn"]),
            "stores_with_nontransactional_increments": sorted(cls["increment"]),
            "stores_written_outside_any_txn": sorted(cls["autocommit"]),
            "outermost_transactions": len(txn_units),
            "transactions": [{"kind": u["kind"], "committed": u["committed"], "rolled_back": u.get("rolled_back"),
                              "nested_levels": u.get("nested_levels", 0), "n": len(u["records"]),
                              "stores": sorted({journal.store_of(r["g"], smap) for r in u["records"] if r["g"]})}
                             for u in txn_units],
            "autocommit_units": sum(1 for u in units if u["kind"] == "auto"),
            "raw": [{"t": r["t"], "x": r["x"], "g": r["g"][:200]} for r in mine[:400]],
        }

    def close(self):
        self.c.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        return repr(v)[:2000]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def second_engine(**engine_kw):
    """A second identity-checked connection to AUDITC (its own IRIS process) with an engine on it."""
    from iris_vector_graph.engine import IRISGraphEngine
    c2 = Conn(NS)
    engine_kw.setdefault("embedding_dimension", 4)
    return c2, IRISGraphEngine(c2.conn, namespace=NS, **engine_kw)
