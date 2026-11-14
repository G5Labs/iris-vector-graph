#!/usr/bin/env python3
"""Lock plans from production behaviour (§3.5 lock plans; contract clauses Locks: deferral / modes / names / wait).

    python lockplan.py OUT_DIR [--only NAME ...]

Each probe: a probe process P holds a lock (^IVG.Ledger("head") or ^IVG.AdjW(key)) in a given mode; an operation
process X starts a product operation in a thread. While P holds, an observer reads X's process state
(%SYS.ProcessQuery: State, CurrentLineAndRoutine, InTransaction) and the lock table (%SYS.LockQuery_List()); just
before P releases, a journal mark is taken, so X's journal records before the mark are what X wrote while it waited
(or before it asked). After X finishes the lock table is read again. Nested probes run the operation inside a
transaction X opened, and read the lock table after the operation returned and again after X's own COMMIT, which is
where a deferred release must happen. Runs in AUDITC only, under the IRIS lock; nothing compiled.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NS, DB, Conn, dump, engine, journal, reset, version  # noqa: E402

from iris_vector_graph.ledger import Changeset  # noqa: E402


def lock_table(obs: Conn = None):
    """The IRIS lock table rows naming ^IVG.* (%SYS.LockQuery_List(): owner pid, mode, flags, counts, reference)."""
    own = obs is None
    c = Conn(NS) if own else obs
    try:
        rows = c.sql("SELECT * FROM %SYS.LockQuery_List()")
    finally:
        if own:
            c.close()
    out = []
    for r in rows:
        r = [None if v is None else str(v) for v in r]
        if any("IVG" in (v or "") for v in r[6:8]):
            out.append({"owner": r[1], "mode": r[2], "flags": r[3], "counts": r[4], "ref": r[6]})
    return out


def proc_state(obs: Conn, pid: str):
    try:
        r = obs.sql("SELECT State, CurrentLineAndRoutine, InTransaction FROM %SYS.ProcessQuery WHERE Pid = ?", pid)
        return {"state": str(r[0][0]), "at": str(r[0][1]), "in_txn": str(r[0][2])} if r else {}
    except Exception as ex:  # noqa: BLE001
        return {"error": str(ex)[:200]}


def cs(msg):
    return Changeset(actor="audit:lockplan", actor_type="ingest", message=msg)


class Probe:
    def __init__(self, name, lock, mode, hold, op, setup=None, nested=False, expect=""):
        self.name, self.lock, self.mode, self.hold, self.op = name, lock, mode, hold, op
        self.setup, self.nested, self.expect = setup, nested, expect

    def run(self):
        ctl = Conn(NS)
        reset(ctl)
        engine(ctl).ledger.enable()
        ctl.conn.commit()
        if self.setup:
            self.setup(ctl)
            ctl.conn.commit()
        ctl.close()
        P, X, obs = Conn(NS), Conn(NS), Conn(NS)
        res = {"probe": self.name, "lock": self.lock, "mode": self.mode, "hold_s": self.hold, "expect": self.expect,
               "pids": {"P": P.pid, "X": X.pid}}
        m0 = journal.mark()
        if self.lock is not None:
            g, subs = self.lock
            P.o.lock(self.mode, 1, g, *subs)
        done = {}

        def work():
            t = time.time()
            try:
                if self.nested:
                    X.sql("START TRANSACTION")
                done["result"] = self.op(X)
            except Exception as ex:  # noqa: BLE001
                done["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
            done["t"] = round(time.time() - t, 3)
        th = threading.Thread(target=work)
        t0 = time.time()
        th.start()
        samples = []
        while time.time() - t0 < self.hold:
            time.sleep(min(0.7, max(0.05, self.hold / 4)))
            samples.append({"t": round(time.time() - t0, 2), **proc_state(obs, X.pid)})
        res["x_state_while_held"] = samples
        res["locks_while_held"] = lock_table(obs) if self.lock is not None else []
        m_rel = journal.mark()
        rel_t = time.time() - t0
        if self.lock is not None:
            P.o.releaseAllLocks()
        th.join(90)
        res["released_at_s"] = round(rel_t, 2)
        res["x"] = done
        res["x_state_after"] = proc_state(obs, X.pid)
        res["locks_after_op"] = lock_table(obs)
        if self.nested:
            try:
                X.sql("COMMIT")
            except Exception as ex:  # noqa: BLE001
                res["nested_commit_error"] = str(ex)[:200]
            res["locks_after_outer_commit"] = lock_table(obs)
        recs = journal.records_since(m0, dbs={DB}, pids={X.pid})
        res["x_records_before_release"] = [{"a": r["a"], "t": r["t"], "g": r["g"][:90]} for r in recs if r["a"] <= m_rel.address]
        res["x_records_total"] = len(recs)
        res["x_record_globals"] = sorted({journal.global_root(r["g"]) for r in recs if r["g"]})
        res["x_adjnolock"] = [r["g"] for r in recs if r["g"].startswith("^IVG.AdjNoLock")]
        txns = journal.transactions(recs)
        # what X's transactions left behind (net of rollbacks), and the content rows per graph afterwards
        res["x_net_effect_roots"] = sorted({journal.global_root(g) for u in txns if u["kind"] == "txn"
                                            for g in journal.net_effect(u["records"])})
        res["x_net_effect_nodes"] = sorted({g[:80] for u in txns if u["kind"] == "txn" for g in journal.net_effect(u["records"])})[:40]
        res["rows_after"] = [list(map(str, r)) for r in obs.sql(
            "SELECT graph_id, COUNT(*) FROM Graph_KG.rdf_edges GROUP BY graph_id")] + \
            [["nodes"] + list(map(str, r)) for r in obs.sql("SELECT graph_id, COUNT(*) FROM Graph_KG.nodes GROUP BY graph_id")]
        res["x_transactions"] = [{"kind": u["kind"], "committed": u["committed"], "n": len(u["records"]),
                                  "rolled_back": u.get("rolled_back"), "nested": u.get("nested_levels")} for u in txns]
        for c in (P, X, obs):
            c.close()
        return res


def commit_node(nid):
    def f(c):
        ch = cs("lp node")
        ch.create_node(nid)
        r = engine(c).ledger.commit(ch)
        return {"seq": r.revision.seq}
    return f


def commit_edge(s, o, graph=None):
    def f(c):
        ch = cs("lp edge")
        ch.create_node(s)
        ch.create_node(o)
        ch.create_relationship(s, "R", o, graph=graph)
        r = engine(c).ledger.commit(ch)
        return {"seq": r.revision.seq}
    return f


def seed_edge(s, o, graph=None):
    def f(c):
        ch = cs("seed")
        ch.create_node(s)
        ch.create_node(o)
        ch.create_relationship(s, "R", o, graph=graph)
        engine(c).ledger.commit(ch)
    return f


def seed_erased(prefix):
    def f(c):
        ch = cs("seed erased")
        ch.create_node(prefix + "|1", properties={"k": "v"})
        engine(c).ledger.commit(ch)
        c.conn.commit()
        c.call("Graph.KG.Eraser", "EraseNodes", "", prefix + "|")
    return f


def purge(c):
    c.call("Graph.KG.Ledger", "PurgeAll")


HEAD = ("^IVG.Ledger", ("head",))


def adjw(key):
    return ("^IVG.AdjW", (key,))


PROBES = [
    Probe("head-commit", HEAD, "", 2.5, commit_node("lp|1"), expect="X waits for the head lock inside CommitInTxn "
          "(Ledger.cls:440) with a transaction open (TSTART :402) and has written nothing; commits after release"),
    Probe("head-commit-timeout", HEAD, "", 33.0, commit_node("lp|2"), expect="lock_timeout after 30 s "
          "(Ledger.cls:440-443); nothing of the changeset is written; head unchanged"),
    Probe("head-redact", HEAD, "", 2.5, lambda c: json.loads(str(c.call("Graph.KG.LedgerRedact", "Redact", "", "rd", "|",
          "audit:lockplan", 2, 0, "Graph_KG"))), setup=seed_erased("rd"),
          expect="X passes the unlocked opening reads (LedgerRedact.cls:202-212) and waits in Batch (:282)"),
    Probe("head-erase-nodes", HEAD, "", 2.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseNodes", "", "en|")),
          setup=seed_edge("en|1", "en|2"), expect="as built: the eraser takes no head lock and finishes while it is "
          "held (Eraser.cls:322-636); reviewed design HD-1201: it would wait"),
    Probe("head-erase-graph", HEAD, "", 2.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseGraph", "EG")),
          setup=seed_edge("eg|1", "eg|2", "EG"), expect="as built: no head lock (Eraser.cls:47-305)"),
    Probe("head-enable", HEAD, "", 2.5, lambda c: json.loads(str(c.call("Graph.KG.Ledger", "Enable", 0, 50000, 250000,
          "Graph_KG"))), setup=purge, expect="X reads the state unlocked (Ledger.cls:254) and waits at :266"),
    Probe("head-disable", HEAD, "", 2.5, lambda c: json.loads(str(c.call("Graph.KG.Ledger", "Disable"))),
          expect="Disable takes no lock (Ledger.cls:331-358): finishes while the head lock is held"),
    Probe("head-verify", HEAD, "", 2.5, lambda c: engine(c).ledger.verify().result, setup=seed_edge("vf|1", "vf|2"),
          expect="verify takes no lock: finishes while held"),
    Probe("deferred-nested-commit", None, "", 1.5, commit_edge("dn|1", "dn|2"), nested=True,
          expect="after commit() returns inside X's open transaction, X still owns ^IVG.Ledger(\"head\") and "
          "^IVG.AdjW(0) (shared): their unlocks (Ledger.cls:404, Adjacency.cls:93) are deferred; both go at X's COMMIT"),
    Probe("deferred-nested-erase", None, "", 1.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseGraph", "NE")),
          setup=seed_edge("ne|1", "ne|2", "NE"), nested=True,
          expect="EraseGraph nested in X's transaction: ^IVG.AdjW(\"NE\") shared held until X's COMMIT"),
    Probe("adjw-commit", adjw(0), "", 2.5, commit_edge("aw|1", "aw|2"),
          expect="X holds the head lock and waits for ^IVG.AdjW(0) shared in Adjacency.WriterLock (:63) "
          "during the edge INSERT; order head -> AdjW; after release it proceeds with the lock (no AdjNoLock)"),
    Probe("adjw-commit-timeout", adjw(0), "", 7.0, commit_edge("at|1", "at|2"),
          expect="WriterLock gives up after 5 s and writes without the lock, SET ^IVG.AdjNoLock(0) (:61-73); the "
          "commit succeeds"),
    Probe("adjw-shared-compatible", adjw(0), "S", 1.5, commit_edge("as|1", "as|2"),
          expect="a shared holder does not delay the writer's shared lock (contract: shared locks are compatible)"),
    Probe("adjw-erase-graph", adjw("EG"), "", 2.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseGraph", "EG")),
          setup=seed_edge("eg|1", "eg|2", "EG"),
          expect="X waits for ^IVG.AdjW(\"EG\") shared in its rdf_edges DELETE (functional index) or RemoveGraph (:431)"),
    Probe("adjw-erase-graph-timeout", adjw("EG"), "", 12.0, lambda c: int(c.call("Graph.KG.Eraser", "EraseGraph", "EG")),
          setup=seed_edge("eg|1", "eg|2", "EG"),
          expect="row writer gives up after 5 s (AdjNoLock), RemoveGraph refuses after 5 s more: the erase throws and "
          "rolls back (Eraser.cls:234-235, :259-261)"),
    Probe("adjw-erase-all-parent", adjw(0), "", 2.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseAll")),
          setup=commit_node("ep|1"),
          expect="no edge rows, so no row writer lock: EraseAll waits in RemoveAll for the parent ^IVG.AdjW#\"S\" "
          "(Adjacency.cls:455), which conflicts with the probe's exclusive lock on the child ^IVG.AdjW(0)"),
    Probe("adjw-erase-all", adjw(0), "", 2.5, lambda c: int(c.call("Graph.KG.Eraser", "EraseAll")),
          setup=seed_edge("ea|1", "ea|2"),
          expect="EraseAll asks ^IVG.AdjW(0) (row writer) and the parent ^IVG.AdjW#S (RemoveAll :455): waits"),
]


def main() -> int:
    out = Path(sys.argv[1])
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    c = Conn(NS)
    print("engine:", version(c), flush=True)
    c.close()
    results = []
    for p in PROBES:
        if only and p.name not in only:
            continue
        r = p.run()
        results.append(r)
        dump(out / f"{p.name}.json", r)
        print(json.dumps({"probe": p.name, "x": r["x"], "x_state": r["x_state_while_held"][-1:] if r["x_state_while_held"] else None,
                          "locks_held": r["locks_while_held"], "before_release": len(r["x_records_before_release"]),
                          "after_op": r["locks_after_op"], "after_outer": r.get("locks_after_outer_commit")},
                         default=str)[:1500], flush=True)
    dump(out / "lockplan.json", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
