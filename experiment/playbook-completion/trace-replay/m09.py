"""Module 09 (native executor): trace replay through the gate machine (models/breadth-b/src/m09.rs:460-516).

The compiled-plan machine `planc` is not driven: its steps compile generated classes (IVGC.P<h>) into the
namespace in job or sync mode, which this lane does not do. Every native read here runs with the process compile
mode "off" (Graph.KG.Cypher.Gen.Mode, process-private), so Gen.For builds nothing (Gen.cls:64) and the
interpreter answers.

Scenario gate (default graph; tr09n -[:TRR]-> tr09m set up before the capture): a native read of the labelled hop
(no label yet), Cypher SET n:TRL on the SQL path, the read again, REMOVE n:TRL, the read again. Each read runs the
same query on a native engine (counting `_native_answers`) and on a SQL-path engine.
"""
from __future__ import annotations

import trlib
from common import engine, gkey, reset
from families_b import Gate

DESIGNS = ["as-built", "reviewed"]
N, M, LBL = "tr09n", "tr09m", "TRL"
# a shape the native planner plans (family A, a tallied hop: native_plan.plan_query); a row-returning hop read is
# not planned at the pin, so its answer would be the SQL path's whatever the gate says
Q_READ = f"MATCH (a:{LBL})-[:TRR]->(b) RETURN count(*) AS c"


def _facts(c):
    eng = engine(c)
    edge = bool(eng._adjacency_indexed)
    rows = c.sql("SELECT Name, Type, TypeClass FROM %Dictionary.CompiledIndex WHERE parent = 'Graph.KG.rdflabels'")
    lab = [r for r in rows if str(r[2]) == "Graph.KG.LabelIndex"]
    return {"edge_idx": edge, "label_idx": bool(lab), "label_index_rows": [list(map(str, r)) for r in rows]}


def s_gate(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c, native_cypher=False)
    eng.create_node(N)
    eng.create_node(M)
    eng.create_edge(N, "TRR", M)
    cap.meta["index_facts"] = _facts(c)
    c.close()
    cap.meta["gkey"] = gkey("")
    cap.begin()
    G = dict(family="gate")

    def read(c):
        from iris_vector_graph.cypher import native_plan
        c.call("Graph.KG.Cypher.Gen", "Mode", "off")
        nat = engine(c)
        n0 = int(getattr(nat, "_native_answers", 0))
        r1 = nat.execute_cypher(Q_READ)
        native_answered = int(getattr(nat, "_native_answers", 0)) > n0
        r2 = engine(c, native_cypher=False).execute_cypher(Q_READ)
        cnt = lambda r: int(r.rows[0][0]) if r.rows else 0  # noqa: E731
        return {"native_answered": native_answered, "native_count": cnt(r1), "sql_count": cnt(r2),
                "gate_reason": native_plan.native_gate(nat), "mode": str(c.call("Graph.KG.Cypher.Gen", "Effective"))}

    def cy(q):
        def f(c):
            r = engine(c, native_cypher=False).execute_cypher(q)
            if getattr(r, "error", None):
                raise RuntimeError(r.error)
            return "ok"
        return f
    cap.step("read", read, **G)
    cap.step("add-label", cy(f"MATCH (n {{id:'{N}'}}) SET n:{LBL}"), **G)
    cap.step("read", read, **G)
    cap.step("remove-label", cy(f"MATCH (n {{id:'{N}'}}) REMOVE n:{LBL}"), **G)
    cap.step("read", read, **G)


SCENARIOS = {"gate": s_gate}

EXPECT = {"gate": []}


def families(trace, design):
    return [Gate(N, LBL, trace["meta"]["gkey"], design)]


def footprint(trace):
    cy = trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"])
    rd = trlib.declared("09", ["eng:IRISGraphEngine.execute_cypher[native]", "cls:Graph.KG.Cypher.Exec.Run",
                               "cls:Graph.KG.Cypher.Gen.For"])
    return {"read": rd | trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"]),
            "add-label": cy, "remove-label": cy}
