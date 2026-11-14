"""Module 05 (temporal): trace replay through tmp_bucket and tmp_mark.

Scenarios:
- bucket: two coordinates of one triple in one bucket: insert (w 1), update at the same coordinate (w 2: F-0501, the
  update is counted again), skip-mode write at the occupied coordinate (nothing), insert at the second coordinate,
  delete of the first (the aggregate is rebuilt from tout, the counter decremented).
- mark: an explicit create_edge with qualifiers {"temporal": 1} followed by a temporal insert and the triple's last
  temporal delete (F-0505: the explicit row is retracted); on a second triple a temporal insert then
  TemporalIndex.Purge (F-0507: the marked row outlives every timestamp), then purge_before (finds nothing to retract).
"""
from __future__ import annotations

import trlib
from common import engine, gkey, reset
from families_a import TmpBucket, TmpMark

DESIGNS = ["as-built", "reviewed"]
G = "tr05g"
S, P, O = "tr05s", "TP", "tr05o"
TS = [1000, 1001]
BUCKET = 3   # 1000 \ 300 and 1001 \ 300 (TemporalIndex BUCKET = 300 s)


def s_bucket(cap: trlib.Capture):
    reset()
    cap.meta["gkey"] = gkey(G)
    cap.begin()

    def w(ts, weight, mode):
        def f(c):
            eng = engine(c)
            if mode == "insert":
                return eng.create_edge_temporal(S, P, O, timestamp=ts, weight=float(weight), graph=G)
            if mode == "update":
                return eng.create_edge_temporal(S, P, O, timestamp=ts, weight=float(weight), upsert=True, graph=G)
            return eng.create_edge_temporal(S, P, O, timestamp=ts, weight=float(weight), mode="skip", graph=G)
        return f
    for ts, weight, mode in ((TS[0], 1, "insert"), (TS[0], 2, "update"), (TS[0], 1, "skip"), (TS[1], 1, "insert")):
        cap.step("create_edge_temporal", w(ts, weight, mode), family="tmp_bucket", ts=ts, w=weight, mode=mode)
    cap.step("delete_edge_temporal", lambda c: engine(c).delete_edge_temporal(S, P, O, TS[0], graph=G),
             family="tmp_bucket", ts=TS[0])


def s_mark(cap: trlib.Capture):
    reset()
    cap.meta["gkey"] = gkey(G)
    cap.begin()
    t1 = ["tr05ms", "TR", "tr05mo"]
    cap.step("create_node", lambda c: engine(c).create_node("tr05ms", graph=G))
    cap.step("create_node", lambda c: engine(c).create_node("tr05mo", graph=G))
    cap.step("create_edge", lambda c: engine(c).create_edge(*t1, qualifiers={"temporal": 1}, graph=G), triple=t1,
             qualifiers={"temporal": 1})
    cap.step("create_edge_temporal", lambda c: engine(c).create_edge_temporal(*t1, timestamp=100, graph=G), triple=t1)
    cap.step("delete_edge_temporal", lambda c: engine(c).delete_edge_temporal(*t1, 100, graph=G), triple=t1)
    t2 = ["tr05ps", "TR", "tr05po"]
    cap.step("create_edge_temporal", lambda c: engine(c).create_edge_temporal(*t2, timestamp=100, graph=G), triple=t2)

    def purge(c):
        c.o.classMethodVoid("Graph.KG.TemporalIndex", "Purge")
        return "Purge() returned"
    cap.step("TemporalIndex.Purge", purge)
    cap.step("purge_before", lambda c: engine(c).purge_before(10_000_000_000))


SCENARIOS = {"bucket": s_bucket, "mark": s_mark}

EXPECT = {
    "bucket": [("tmp_bucket", TmpBucket.INV, "F-0501")],
    "mark": [("tmp_mark[as-built]tr05ms", TmpMark.EXPL, "F-0505"), ("tmp_mark[as-built]tr05ps", TmpMark.MARK, "F-0507")],
}


def families(trace, design):
    name = trace["name"].split("-", 1)[1]
    gk = trace["meta"]["gkey"]
    if name == "bucket":
        return [TmpBucket(gk, S, P, O, TS, BUCKET, design)]
    if name == "mark":
        return [TmpMark(G, gk, ("tr05ms", "TR", "tr05mo"), design), TmpMark(G, gk, ("tr05ps", "TR", "tr05po"), design)]
    raise KeyError(name)


def footprint(trace):
    return {
        "create_edge_temporal": trlib.declared("05", ["py:IRISGraphEngine.create_edge_temporal"]),
        "delete_edge_temporal": trlib.declared("05", ["py:IRISGraphEngine.delete_edge_temporal"]),
        "create_node": trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
        "create_edge": trlib.declared("03", ["py:IRISGraphEngine.create_edge"]),
        "TemporalIndex.Purge": trlib.declared("05", ["cls:Graph.KG.TemporalIndex.Purge"]),
        "purge_before": trlib.declared("05", ["py:IRISGraphEngine.purge_before"]),
    }
