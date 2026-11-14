"""Module 11 (ledger core): trace replay through the m11 machines enable, commit, retry, guard and adopt.

Scenarios (each from a clean namespace):
- enable: a first enable on a never-enabled namespace (genesis), then a second enable from another process (the
  enabled fast path).
- commit: P1 commits inside a caller transaction (the head lock's release is deferred to the caller's end), the caller
  rolls back; P2 then commits plainly.
- retry: a commit with a post-commit property V1 and a retry key, a governed set of the property to V2, then a retry
  of the first changeset (F-1101: the replay writes V1 again; F-1106: the replay answers no statement ids).
- guard: engine E1 writes (its guard caches "not strict"), engine E2 turns strict on, E1 writes within the 5 s cache
  life (F-0801), the cache expires, E1's guarded write is refused, E1's bulk_delete_adjacency lands (F-1108), E1
  commits through the ledger.
- adopt: genesis, disable, an unrecorded create_node (all before the capture), then enable, which adopts (one
  adoption revision recording the node), then a ledger commit of an edge from that node (the machine's committer).
"""
from __future__ import annotations

import time

import trlib
from common import commit, cs, engine, reset
from families_11 import LedAdopt, LedCommit, LedEnable, LedGuard, LedRetry

DESIGNS = ["as-built", "reviewed"]


def _info(r):
    return {"seq": getattr(r, "seq", None), "revision_id": str(getattr(r, "revision_id", ""))}


def s_enable(cap: trlib.Capture):
    reset()
    cap.begin()
    cap.step("enable", lambda c: _info(engine(c).ledger.enable()), enabler=0)
    cap.step("enable", lambda c: _info(engine(c).ledger.enable()), enabler=1)


def s_commit(cap: trlib.Capture):
    reset(ledger=True)
    cap.begin()
    c1 = cs("P1 inside a caller transaction")
    c1.create_node("tr11p1")

    def p1(c):
        c.o.tStart()
        r = engine(c).ledger.commit(c1)
        return {"seq": r.revision.seq, "tlevel": int(c.o.getTLevel())}
    cap.step("p1-commit-in-caller-txn", p1, who="P1", commit_ops=["P1Lock", "P1Write", "P1Inner"])

    def p1_rollback(c):
        c.o.tRollback()
        return {"tlevel": int(c.o.getTLevel())}
    cap.step("p1-caller-rollback", p1_rollback, who="P1", commit_ops=[["P1Caller", False]])
    c2 = cs("P2 plain")
    c2.create_node("tr11p2")
    cap.step("p2-commit", commit(c2), commit_ops=["P2Lock", "P2Commit"])


NODE, PROP, KEY = "tr11r", "k", "tr11-retry"


def _retry_cs():
    c = cs("node with a post-commit property", KEY)
    c.create_node(NODE)
    c.post_commit_properties = {NODE: {PROP: "V1"}}
    return c


def s_retry(cap: trlib.Capture):
    reset(ledger=True)
    cap.begin()

    def first(c):
        r = engine(c).ledger.commit(_retry_cs())
        c.conn.commit()
        return {"seq": r.revision.seq, "replayed": r.replayed, "stmt_ids": {str(k): v for k, v in r.stmt_ids.items()},
                "post_commit_applied": r.post_commit_applied}
    cap.step("ledger-commit", first, retry_op="Commit")
    g = cs("governed set", "tr11-governed")
    g.set_property(NODE, PROP, "V2")
    cap.step("ledger-commit", commit(g), retry_op="GovernedSet")
    cap.step("ledger-commit", first, retry_op="Retry")


def s_guard(cap: trlib.Capture):
    reset(ledger=True)
    cap.begin()
    E1 = {}

    def e1():
        return E1["eng"]

    def w1(c):
        E1["eng"] = engine(c)
        return e1().create_edge("tr11g1", "R", "tr11g1b")
    cap.step("create_edge", w1, who="E1", guard_op="GuardedWrite")

    def strict_on(c):
        engine(c).ledger.set_strict(True)
        return "strict on"
    cap.step("set_strict", strict_on, guard_op="SetStrict", strict=True)
    cap.step("create_node", lambda c: e1().create_node("tr11g2"), who="E1", guard_op="GuardedWrite")

    def tick(c):
        time.sleep(5.5)
        return "waited 5.5 s (TTL_SECONDS = 5.0, ledger/guard.py:20)"
    cap.step("tick", tick, who="E1", guard_op="Tick")
    cap.step("create_node", lambda c: e1().create_node("tr11g3"), who="E1", guard_op="GuardedWrite")
    cap.step("bulk_delete_adjacency", lambda c: e1().bulk_delete_adjacency(["tr11g1"]), who="E1",
             guard_op="UnguardedWrite")
    lc = cs("a recorded write in strict mode")
    lc.create_node("tr11g4")

    def ledger_commit(c):
        r = e1().ledger.commit(lc)
        return {"seq": r.revision.seq}
    cap.step("ledger-commit", ledger_commit, who="E1", guard_op="LedgerCommit")


def s_adopt(cap: trlib.Capture):
    reset(ledger=True)
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        eng = engine(c)
        eng.ledger.disable()
        eng.create_node("tr11u")
        c.conn.commit()
    finally:
        c.close()
    cap.begin()
    cap.step("enable", lambda c: _info(engine(c).ledger.enable()), adopt=True)
    e = cs("an edge recorded after the adoption")
    e.create_node("tr11v")
    e.create_relationship("tr11u", "R", "tr11v")
    cap.step("ledger-commit", commit(e), commit_edge=True)


SCENARIOS = {"enable": s_enable, "commit": s_commit, "retry": s_retry, "guard": s_guard, "adopt": s_adopt}

EXPECT = {
    "enable": [],
    "commit": [],
    "retry": [("m11-retry", LedRetry.R_NOOP, "F-1101"), ("m11-retry", LedRetry.R_GOV, "F-1101"),
              ("m11-retry", LedRetry.R_STMT, "F-1106")],
    "guard": [("m11-guard", LedGuard.G_SG, "F-0801 (step 2) and F-1108 (step 5)")],
    "adopt": [],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    if name == "enable":
        return [LedEnable(design)]
    if name == "commit":
        return [LedCommit(1, "as-built" if design == "as-built" else "control-immediate-unlock")]
    if name == "retry":
        return [LedRetry(KEY, NODE, PROP, design)]
    if name == "guard":
        return [LedGuard(design)]
    if name == "adopt":
        return [LedAdopt("tr11u", ("tr11u", "R", "tr11v"), design)]
    raise KeyError(name)


_COMMIT = ["cls:Graph.KG.Ledger.Commit", "cls:Graph.KG.Ledger.CommitInTxn",
           "py:iris_vector_graph/ledger/client.py:GraphLedger.commit"]


def footprint(trace):
    led = trlib.declared("11", _COMMIT + ["cls:Graph.KG.LedgerApply.OpCreateNode"])
    return {
        "enable": trlib.declared("11", ["cls:Graph.KG.Ledger.Enable", "py:iris_vector_graph/ledger/client.py:GraphLedger.enable"]) | led,
        "p1-commit-in-caller-txn": led, "p1-caller-rollback": led, "p2-commit": led, "ledger-commit": led,
        "create_edge": trlib.declared("03", ["py:IRISGraphEngine.create_edge"]),
        "create_node": trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
        "bulk_delete_adjacency": trlib.declared("04", ["py:IRISGraphEngine.bulk_delete_adjacency"]),
        "set_strict": {"global:^IVG.Ledger", "sql:Graph_KG.ledger_stats"},
        "tick": set(),
    }
