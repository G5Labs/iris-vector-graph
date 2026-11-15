"""Module 15 (integrations): what can be traced on IRIS Community, and why no machine replays it.

The module's machines (models/breadth-c/src/fhir.rs M3 sync, register.rs M6 register) need a FHIR repository
(HS_FHIRServer.Repo, IRIS for Health); IRIS Community 2026.1 has none, and Graph.KG.FHIRGraph.Register refuses at
its first check (FHIRGraph.cls:179-181) before any write. The reification writers (reify_edge, delete_reification:
iris_vector_graph/_engine/schema.py:3264-3400) run on Community, but no breadth-c family models them (fhir.rs,
register.rs only). The scenario records both, so the gap is exact: the Register refusal writes nothing (its journal
segment is empty) and the reify/delete_reification transactions match no model step.

Scenario reify: node a, b and edge a-[R]->b committed (outside the capture); Register (direct class call, the refusal);
reify_edge(edge_id) with a property; delete_reification.
"""
from __future__ import annotations

import trlib
from common import engine, reset

DESIGNS = ["as-built"]
A, R, B = "tr15a", "TR", "tr15b"


def s_reify(cap: trlib.Capture):
    reset()
    from iris_conn import Conn
    c = Conn(trlib.NS)
    eng = engine(c)
    eng.create_node(A)
    eng.create_node(B)
    eng.create_edge(A, R, B)
    eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ?", A, R, B)[0][0]
    c.close()
    cap.meta["edge_id"] = int(eid)
    cap.begin()
    cap.step("FHIRGraph.Register", lambda c: str(c.call("Graph.KG.FHIRGraph", "Register", "", "[]", 60, "")))
    cap.step("reify_edge", lambda c: engine(c).reify_edge(int(eid), reifier_id="tr15reif", props={"src": "tr15"}))
    cap.step("delete_reification", lambda c: engine(c).delete_reification("tr15reif"))


SCENARIOS = {"reify": s_reify}
EXPECT = {"reify": []}


def families(trace, design):
    return []   # no breadth-c family models reification or a refused-before-any-write Register


def footprint(trace):
    return {"FHIRGraph.Register": trlib.declared("15", ["IRISGraphEngine.fhir_graph_register -> Graph.KG.FHIRGraph.Register"]),
            "reify_edge": trlib.declared("15", ["IRISGraphEngine.reify_edge"]),
            "delete_reification": trlib.declared("15", ["IRISGraphEngine.delete_reification"])}
