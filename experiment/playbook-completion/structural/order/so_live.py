#!/usr/bin/env python3
"""Live confirmation of the storage-order reliance sites the disposition table calls findings (AUDITD, observation
only). Each probe writes the same data in two insertion orders (reset between them) through the product's own
writers and calls the order-reliant entry point; a different answer for the same data is the reliance shown live.

    locks.sh iris timeout 900 python so_live.py OUT.json

P03a get_node_ids_by_property(limit=2)        nodes_edges.py:820-828      F-C0302
P03b get_property_pairs_like(limit=2)         nodes_edges.py:904-911      F-C0302
P03c _filter_edges_by_properties              nodes_edges.py:584-618      F-0206 (triple in two graphs)
P11  ledger delete_relationship by tuple on a multigraph with two parallel edges: which edge FindEdge picks
                                              LedgerApply.cls:144-157     F-0205
P16  GraphQL resolve_nodes(label, limit=2, offset=0|2) pages               gql/resolvers.py:32-46   F-C1642
P17  IRISGraphStore.query_nodes(limit=2) in a child process (the driver may crash): its exit status and answer
                                              iris_sql_store.py:1176-1181 F-C1742 / F-C1743
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "live"))
import lib  # noqa: E402


def fresh():
    c = lib.conn()
    lib.reset(c)
    return c, lib.engine(c)


def p03(order):
    c, e = fresh()
    try:
        ids = [f"so3:{i}" for i in range(6)]
        for n in (ids if order == "forward" else ids[::-1]):
            e.create_node(n, labels=["L"], properties={"k": "v", "t": "x" + n[-1]})
        e.create_node("so3:0", graph="so3g")
        e.create_node("so3:1", graph="so3g")
        pair = [("", {"w": "1"}), ("so3g", {"w": "2"})]
        for g, q in (pair if order == "forward" else pair[::-1]):
            e.create_edge("so3:0", "R", "so3:1", qualifiers=q, graph=g or None)
        c.conn.commit()
        e = lib.engine(c)
        return {"get_node_ids_by_property_limit2": e.get_node_ids_by_property("k", "v", limit=2),
                "get_property_pairs_like_limit2": [list(x) for x in e.get_property_pairs_like("t", "x%", limit=2)],
                "filter_edges_w1_default_edge": e._filter_edges_by_properties([{"s": "so3:0", "p": "R", "o": "so3:1"}], {"w": "1"}),
                "edge_rows": c.sql("SELECT s, p, o_id, graph_id, qualifiers FROM Graph_KG.rdf_edges ORDER BY graph_id")}
    finally:
        lib.reset(c)
        c.close()


def p11(order):
    """Two parallel edges of one triple in a multigraph: the first by create_edge, the second by a multigraph Cypher
    CREATE (the product's way to add a parallel edge, spec 234 FR-008; tests/e2e/test_multigraph_rel_identity_e2e.py:36-39).
    Then a ledger delete_relationship by tuple, which resolves the row with FindEdge (no ekey, no ORDER BY)."""
    from iris_vector_graph.ledger import Changeset
    c, e = fresh()
    try:
        e.set_multigraph("so11g", True)
        e.create_node("so11:a", graph="so11g")
        e.create_node("so11:b", graph="so11g")
        first, second = ("1", "2") if order == "forward" else ("2", "1")
        e.create_edge("so11:a", "R", "so11:b", qualifiers={"w": first}, graph="so11g")
        r1 = e.execute_cypher("USE GRAPH 'so11g' MATCH (a {node_id: $a}), (b {node_id: $b}) CREATE (a)-[:R {w: $w}]->(b)",
                              {"a": "so11:a", "b": "so11:b", "w": second})
        c.conn.commit()
        before = c.sql("SELECT edge_id, ekey, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = 'so11g' ORDER BY edge_id")
        plan = None
        with contextlib.suppress(Exception):
            plan = [str(x[0])[:1500] for x in c.sql("EXPLAIN SELECT %ID, qualifiers FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND graph_id = ?")]
        e.ledger.enable()
        c.conn.commit()
        ch = Changeset(actor="audit:so", actor_type="ingest", message="delete one parallel edge by tuple")
        ch.delete_relationship(("so11:a", "R", "so11:b", "so11g"))
        r = e.ledger.commit(ch)
        c.conn.commit()
        after = c.sql("SELECT ekey, qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = 'so11g' ORDER BY ekey")
        return {"cypher_create_error": getattr(r1, "error", None),
                "rows_before (edge_id, ekey, qualifiers)": before,
                "commit_ok": bool(getattr(r, "revision", None)), "rows_after (ekey, qualifiers)": after,
                "findedge_plan": plan}
    finally:
        with contextlib.suppress(Exception):
            e.set_multigraph("so11g", False)
        lib.reset(c)
        c.close()


class _Info:
    def __init__(self, ctx):
        self.context = ctx


def p16(order):
    from iris_vector_graph.gql.resolvers import resolve_nodes
    c, e = fresh()
    try:
        ids = [f"so16:{i}" for i in range(5)]
        for n in (ids if order == "forward" else ids[::-1]):
            e.create_node(n, labels=["Q"], properties={"name": n})
        c.conn.commit()
        e = lib.engine(c)

        def page(off):
            return [getattr(x, "id", str(x)) for x in asyncio.run(resolve_nodes(_Info({"engine": e}), "Q", limit=2, offset=off))]
        return {"page_offset0": page(0), "page_offset2": page(2), "page_offset4": page(4)}
    finally:
        lib.reset(c)
        c.close()


CHILD = r'''
import sys, json
sys.path.insert(0, sys.argv[1])
import lib
c = lib.conn(); e = lib.engine(c)
print("CHILD-START", flush=True)
r = e._store.query_nodes(limit=2)
print("CHILD-ANSWER " + json.dumps({"rows": [list(x) for x in r.rows], "error": r.error}, default=str), flush=True)
c.close()
'''


def p17(order):
    c, e = fresh()
    try:
        ids = [f"so17:{i}" for i in range(5)]
        for n in (ids if order == "forward" else ids[::-1]):
            e.create_node(n, labels=["O"], properties={"k": "v"})
        c.conn.commit()
        env = dict(os.environ)
        r = subprocess.run([sys.executable, "-c", CHILD, str(HERE.parents[0] / "live")], capture_output=True, text=True,
                           timeout=120, env=env)
        ans = [ln for ln in r.stdout.splitlines() if ln.startswith("CHILD-")]
        return {"child_returncode": r.returncode, "child_stdout_marks": ans,
                "child_stderr_tail": [ln for ln in r.stderr.splitlines() if "WARNING:root" not in ln][-6:]}
    finally:
        lib.reset(c)
        c.close()


RAW = r'''
import sys, json
sys.path.insert(0, sys.argv[1])
import lib
c = lib.conn()
print("CHILD-START", flush=True)
cur = c.conn.cursor()
cur.execute(sys.argv[2])
print("CHILD-ANSWER " + json.dumps([list(r) for r in cur.fetchall()], default=str), flush=True)
c.close()
'''


def p17b(order):
    """Attribution controls for P17: the same statement text sent by a harness cursor in a child process
    (FETCH FIRST, the product's text), and the TOP spelling the product uses elsewhere."""
    c, e = fresh()
    try:
        ids = [f"so17:{i}" for i in range(5)]
        for n in (ids if order == "forward" else ids[::-1]):
            e.create_node(n, labels=["O"], properties={"k": "v"})
        c.conn.commit()
        out = {}
        for tag, q in (("fetch_first", "SELECT node_id FROM Graph_KG.nodes FETCH FIRST 2 ROWS ONLY"),
                       ("top", "SELECT TOP 2 node_id FROM Graph_KG.nodes")):
            r = subprocess.run([sys.executable, "-c", RAW, str(HERE.parents[0] / "live"), q], capture_output=True,
                               text=True, timeout=120)
            out[tag] = {"statement": q, "child_returncode": r.returncode,
                        "child_stdout_marks": [ln for ln in r.stdout.splitlines() if ln.startswith("CHILD-")]}
        return out
    finally:
        lib.reset(c)
        c.close()


def main() -> int:
    out = Path(sys.argv[1])
    res = {"namespace": lib.NS, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "probes": {}}
    only = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
    for name, fn in (("P03", p03), ("P11", p11), ("P16", p16), ("P17", p17), ("P17b", p17b)):
        if only and name not in only:
            continue
        r = {}
        for order in ("forward", "reverse"):
            try:
                r[order] = fn(order)
            except Exception as ex:  # noqa: BLE001
                r[order] = {"harness_error": f"{type(ex).__name__}: {str(ex)[:300]}"}
        keys = sorted(set(r["forward"]) & set(r["reverse"]))
        r["differs"] = {k: json.dumps(r["forward"][k], sort_keys=True, default=str) != json.dumps(r["reverse"][k], sort_keys=True, default=str) for k in keys}
        res["probes"][name] = r
        print(name, json.dumps(r, default=str)[:1500], flush=True)
        lib.dump(out, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
