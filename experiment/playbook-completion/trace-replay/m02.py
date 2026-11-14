"""Module 02 (graph identity): trace replay through gid_mode.

Scenarios:
- offlone: multigraph on; two Cypher CREATEs of one triple (edge keys 0 and 1); a per-edge Cypher DELETE of key 0;
  mode off (accepted: one row); create_edge (F-0201: its guard checks key 0 only, so the mode-off graph holds two rows).
- cache: engine E1 turns the mode on and CREATEs the triple (E1 caches "on"); engine E0 turns the mode off (one row:
  accepted); E1 CREATEs again (F-0208: its cached mode writes key MAX+1).
"""
from __future__ import annotations

import trlib
from common import engine, reset
from families_a import GidMode

DESIGNS = ["as-built", "reviewed"]
A, R, B = "tr02a", "R", "tr02b"


def _nodes(g):
    from iris_conn import Conn
    c = Conn(trlib.NS)
    try:
        eng = engine(c)
        eng.create_node(A, graph=g)
        eng.create_node(B, graph=g)
    finally:
        c.close()


def _create(g, k=None):
    props = f" {{k: {k}}}" if k is not None else ""
    return (f"USE GRAPH '{g}' MATCH (a {{node_id: '{A}'}}), (b {{node_id: '{B}'}}) CREATE (a)-[:{R}{props}]->(b)")


def s_offlone(cap: trlib.Capture):
    g = "tr02m"
    reset()
    _nodes(g)
    cap.meta["g"] = g
    cap.begin()
    E = {}

    def eng(c):
        E.setdefault("e", engine(c))
        return E["e"]
    cap.step("set_multigraph", lambda c: eng(c).set_multigraph(g, True), who="E0", gid="SetOn", engine=0)
    for k in (0, 1):
        cap.step("execute_cypher", lambda c, k=k: str(eng(c).execute_cypher(_create(g, k), {}, raise_on_error=True))[:80],
                 who="E0", gid="CyCreate", engine=0)
    q = f"USE GRAPH '{g}' MATCH (a {{node_id: '{A}'}})-[r:{R} {{k: 0}}]->(b) DELETE r"
    cap.step("execute_cypher", lambda c: str(eng(c).execute_cypher(q, {}, raise_on_error=True))[:80], who="E0",
             gid="CyDelete", ekey=0)
    cap.step("set_multigraph", lambda c: eng(c).set_multigraph(g, False), who="E0", gid="SetOff", engine=0)
    cap.step("create_edge", lambda c: eng(c).create_edge(A, R, B, graph=g), who="E0", gid="CreateEdge", engine=0)


def s_cache(cap: trlib.Capture):
    g = "tr02c"
    reset()
    _nodes(g)
    cap.meta["g"] = g
    cap.begin()
    E = {}

    def eng(c, name):
        E.setdefault(name, engine(c))
        return E[name]
    cap.step("set_multigraph", lambda c: eng(c, "e1").set_multigraph(g, True), who="E1", gid="SetOn", engine=1)
    cap.step("execute_cypher", lambda c: str(eng(c, "e1").execute_cypher(_create(g), {}, raise_on_error=True))[:80],
             who="E1", gid="CyCreate", engine=1)
    cap.step("set_multigraph", lambda c: eng(c, "e0").set_multigraph(g, False), who="E0", gid="SetOff", engine=0)
    cap.step("execute_cypher", lambda c: str(eng(c, "e1").execute_cypher(_create(g), {}, raise_on_error=True))[:80],
             who="E1", gid="CyCreate", engine=1)


SCENARIOS = {"offlone": s_offlone, "cache": s_cache}
EXPECT = {"offlone": [("gid_mode", GidMode.INV, "F-0201")], "cache": [("gid_mode", GidMode.INV, "F-0208")]}


def families(trace, design):
    return [GidMode(trace["meta"]["g"], (A, R, B), design)]


def footprint(trace):
    cy = trlib.declared("08", ["eng:IRISGraphEngine.execute_cypher"])
    return {"set_multigraph": trlib.declared("02", ["py:IRISGraphEngine.set_multigraph"]),
            "execute_cypher": cy, "create_edge": trlib.declared("03", ["py:IRISGraphEngine.create_edge"])}
