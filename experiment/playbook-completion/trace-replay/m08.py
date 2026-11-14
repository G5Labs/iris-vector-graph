"""Module 08 (Cypher on the SQL path): trace replay through the txn machine (models/breadth-b/src/m08.rs).

Engine: native_cypher=False (the SQL path). Set up before the capture: the literal edge tr08d1-[:TRT]->tr08d2
(committed: the machine's E = 2) and two TRK nodes for the failing read step. Scenario txn:
  0 the F-0805 query: CREATE (c {id:'tr08c'}), (a {id:'tr08d1'})-[:TRT]->(b {id:'tr08d2'}) with E existing;
  1 caller: START (Native API TSTART on a persistent connection) and create_node tr08w (W pending);
  2 the F-0805 query again inside the caller's transaction;
  3 a stepped write whose read step fails (1/0, F-0806 wording), inside the caller's transaction;
  4 caller TCOMMIT;
  5 a stepped write whose read step succeeds (positive), no caller.
Instances: txn[lit] (C = tr08c, E = the literal edge), txn[step] (C = tr08short), txn[ok] (C = tr08ok); W = tr08w.
"""
from __future__ import annotations

import trlib
from common import engine, reset
from families_b import ReadOnly, Txn

DESIGNS = ["as-built", "reviewed"]
EDGE = ("tr08d1", "TRT", "tr08d2")
Q_LIT = "CREATE (c:TRD {id:'tr08c'}), (a:TRD {id:'tr08d1'})-[:TRT]->(b:TRD {id:'tr08d2'})"
Q_STEP_FAIL = "CREATE (:TRY {id:'tr08short'}) WITH * MATCH (b:TRK {k: 1/0}) CREATE (:TRZ)"
Q_STEP_OK = "CREATE (:TRY {id:'tr08ok'}) WITH * MATCH (b:TRK {k: 1}) CREATE (:TRZ)"


def _cy(c, q):
    eng = engine(c, native_cypher=False)
    r = eng.execute_cypher(q)
    err = getattr(r, "error", None)
    if err:
        raise RuntimeError(f"execute_cypher error: {err}")
    return {"rows": [list(x) for x in (r.rows or [])][:5]}


def s_txn(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    _cy(c, "CREATE (a:TRD {id:'tr08d1'})-[:TRT]->(b:TRD {id:'tr08d2'})")
    _cy(c, "CREATE (:TRK {id:'tr08k1', k: 1}), (:TRK {id:'tr08k2', k: 2})")
    c.close()
    cap.begin()
    ALL = ["lit", "step", "ok"]

    def tl(c):
        return int(c.o.getTLevel())

    def q_on(q, who=None):
        def f(c):
            try:
                return _cy(c, q)
            finally:
                cap.meta["tl"] = tl(c)
        return f
    cap.step("execute_cypher", q_on(Q_LIT), txn_fams=ALL, query_of="lit", caller_open=False)
    cap.steps[-1]["tlevel_above_caller"] = cap.meta["tl"]

    def begin(c):
        c.o.tStart()
        engine(c, native_cypher=False).create_node("tr08w")
        return {"tlevel": tl(c)}
    cap.step("caller-begin", begin, who="C", txn_fams=ALL, caller_open=True)
    cap.steps[-1]["tlevel_above_caller"] = cap.steps[-1]["reply"]["tlevel"] - 1
    cap.step("execute_cypher", q_on(Q_LIT), who="C", txn_fams=ALL, query_of="lit", caller_open=True)
    cap.steps[-1]["tlevel_above_caller"] = cap.meta["tl"] - 1
    cap.steps[-1]["caller_open"] = cap.meta["tl"] >= 1
    cap.step("execute_cypher", q_on(Q_STEP_FAIL), who="C", txn_fams=ALL, query_of="step", read_step_fails=True,
             caller_open=True)
    cap.steps[-1]["tlevel_above_caller"] = cap.meta["tl"] - 1
    cap.steps[-1]["caller_open"] = cap.meta["tl"] >= 1

    def commit(c):
        if tl(c) > 0:
            c.o.tCommit()
        return {"tlevel": tl(c)}
    cap.step("caller-commit", commit, who="C", txn_fams=ALL, caller_open=False)
    cap.step("execute_cypher", q_on(Q_STEP_OK), txn_fams=ALL, query_of="ok", read_step_fails=False,
             caller_open=False)
    cap.steps[-1]["tlevel_above_caller"] = cap.meta["tl"]


def s_readonly(cap: trlib.Capture):
    """Machine readonly: calls with read-only mode requested (execute_aql has no such argument): a read; a CREATE
    (refused by the text check); two AQL queries whose collection name carries a SET (F-0814); a dotted function that
    pastes Graph_KG.Txn_Begin (F-0815), $TLEVEL read on the call's own connection right after it."""
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    _cy(c, "CREATE (x:TRX {id:'tr08x', name:'ax'})-[:TRR]->(y:TRX {id:'tr08y'})")
    _cy(c, "CREATE (x:TRX {id:'tr08x2', name:'ax2'})-[:TRR]->(y:TRX {id:'tr08y2'})")
    c.close()
    cap.begin()
    O = dict(family="readonly")

    def call(kind, src="tr08x", key="pwn"):
        def f(c):
            eng = engine(c, native_cypher=False)
            if kind == "AqlWrite":
                coll = f"`TRR*1..1]->(v) SET v.{key} = 1 WITH v AS v MATCH (start)-[:TRR`"
                r = eng.execute_aql(f"FOR v IN 1..1 OUTBOUND '{src}' {coll} RETURN v")
            elif kind == "Read":
                r = eng.execute_cypher("MATCH (n:TRX) RETURN n.id", read_only=True)
            elif kind == "WriteClause":
                r = eng.execute_cypher("CREATE (:TRX {id:'tr08ro'})", read_only=True)
            else:
                r = eng.execute_cypher("RETURN `GRAPH_KG.TXN_BEGIN(0) AS LVL --`.f(1) AS v", read_only=True)
            cap.meta["tl"] = int(c.o.getTLevel())
            if getattr(r, "error", None):
                raise RuntimeError(str(r.error)[:300])
            return {"rows": [list(x) for x in (r.rows or [])][:5], "tlevel": cap.meta["tl"]}
        return f
    for kind, src, key in (("Read", None, None), ("WriteClause", None, None), ("AqlWrite", "tr08x", "pwn"),
                           ("AqlWrite", "tr08x2", "pwn2"), ("DottedTxnBegin", None, None)):
        cap.step(f"ro-{kind}", call(kind, src, key), kind=kind, **O)
        cap.steps[-1]["tlevel"] = cap.meta.get("tl", 0)


SCENARIOS = {"txn": s_txn, "readonly": s_readonly}

EXPECT = {"txn": [("txn[as-built]lit", Txn.DUP, "F-0805"), ("txn[as-built]step", Txn.MSG, "F-0806")],
          "readonly": [("readonly[as-built]", ReadOnly.RO, "F-0814/F-0815")]}


def families(trace, design):
    if trace["name"].endswith("-readonly"):
        return [ReadOnly(["tr08ro"], design)]
    return [Txn("lit", "tr08w", "tr08c", EDGE, "LiteralEdge", design),
            Txn("step", "tr08w", "tr08short", None, "Stepped", design),
            Txn("ok", "tr08w", "tr08ok", None, "Stepped", design)]


def footprint(trace):
    cy = trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"])
    return {"execute_cypher": cy, "caller-begin": trlib.declared("03", ["py:IRISGraphEngine.create_node"]),
            "caller-commit": set(), "ro-Read": cy, "ro-WriteClause": cy, "ro-DottedTxnBegin": cy,
            "ro-AqlWrite": trlib.declared("08", ["eng:IRISGraphEngine.execute_aql"])}
