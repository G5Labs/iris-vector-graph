#!/usr/bin/env python3
"""Write-set pair 03 | GID-I4.10 | bulk_load_session: are rows written inside a bulk_load_session (index maintenance
disabled) seen by the unique key and by the writers' existence checks? (AUDITD, live)

    locks.sh iris python bls.py OUT.json

GID-I4.10 (02-graph-identity.md:95): a graph whose mode is off never holds parallel edges, whatever path writes.
bulk_load_session drops indexes at its start and rebuilds them at its end (nodes_edges.py:410-416, 450-460;
GraphSchema.disable_indexes, schema.py:1640-1685). Cases, default graph (mode off), each from an empty namespace:
  A  plain session: inside it add_nodes twice over one id, add_edges twice over one triple, the same engine's
     create_edge / create_node / store_node of those ids, and a second connection's create_edge of the triple while
     the session is open; after the session: one more create_edge.
  B  the same inside a caller transaction (driver autocommit off): the session keeps the indexes (docstring).
  C  control (expected violation, F-C0350's mode): BulkLoader.load_edges (INSERT %NOINDEX %NOCHECK) then create_edge
     of the same triple: the oracle must report the duplicate key.
Oracle: keys.keys_check (K1 no duplicate declared key by %IGNOREINDEX * full scans; K2 ^KG equals the rows), the
row count of the triple, and each writer's answer (False = already there).
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
sys.path.insert(0, str(HERE.parent / "capkeys"))
import lib  # noqa: E402
from keys import call, keys_check  # noqa: E402


def triple_rows(c, s="bl:a", p="R", o="bl:b"):
    return c.sql("SELECT ekey, COUNT(*) FROM %IGNOREINDEX * Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? "
                 "AND COALESCE(graph_id, '') = '' GROUP BY ekey", s, p, o)


def node_rows(c, n="bl:a"):
    return c.sql("SELECT COUNT(*) FROM %IGNOREINDEX * Graph_KG.nodes WHERE node_id = ? AND COALESCE(graph_id, '') = ''", n)[0][0]


def session_case(c, e, caller_txn):
    out = {"mode_off": not e.is_multigraph(None)}
    if caller_txn:
        c.conn.setAutoCommit(False)
    other = lib.conn()
    try:
        eo = lib.engine(other)
        with e.bulk_load_session() as s:
            out["add_nodes 1"] = call(lambda: s.add_nodes([{"id": "bl:a", "labels": ["L"], "properties": {"k": "1"}},
                                                          {"id": "bl:b", "labels": ["L"]}]))
            out["add_nodes 2 (same ids)"] = call(lambda: s.add_nodes([{"id": "bl:a", "labels": ["L"], "properties": {"k": "2"}}]))
            out["add_edges 1"] = call(lambda: s.add_edges([("bl:a", "bl:b", "R")]))
            out["add_edges 2 (same triple)"] = call(lambda: s.add_edges([("bl:a", "bl:b", "R")]))
            out["create_edge same triple, same engine, inside"] = call(lambda: e.create_edge("bl:a", "R", "bl:b"))
            out["create_node same id, inside"] = call(lambda: e.create_node("bl:a"))
            out["store_node same id, inside"] = call(lambda: e.store_node("bl:a", labels=["L"], properties={"k": "3"}))
            if not caller_txn:
                out["other connection create_edge same triple, inside"] = call(lambda: eo.create_edge("bl:a", "R", "bl:b"))
            out["inside: rows of the triple"] = call(lambda: triple_rows(c))
            out["inside: node rows of bl:a"] = call(lambda: node_rows(c))
        out["session_stats"] = {k: v for k, v in (getattr(s, "stats", None) or {}).items() if not str(k).endswith("seconds")}
        if caller_txn:
            c.conn.commit()
            c.conn.setAutoCommit(True)
        out["after: create_edge same triple"] = call(lambda: e.create_edge("bl:a", "R", "bl:b"))
        c.conn.commit()
    finally:
        try:
            other.conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        other.close()
    out["rows of the triple"] = triple_rows(c)
    out["node rows of bl:a"] = node_rows(c)
    return out


def control_noindex(c, e):
    from iris_vector_graph.bulk_loader import BulkLoader
    out = {"mode_off": not e.is_multigraph(None)}
    out["load_edges (%NOINDEX %NOCHECK)"] = call(lambda: BulkLoader(c.conn).load_edges([("bl:a", "R", "bl:b", None)]))
    out["create_edge same triple"] = call(lambda: e.create_edge("bl:a", "R", "bl:b"))
    out["rebuild_all_indices"] = call(lambda: BulkLoader(c.conn).rebuild_all_indices())
    c.conn.commit()
    out["rows of the triple"] = triple_rows(c)
    return out


CASES = [("A-session", lambda c, e: session_case(c, e, False), "holds"),
         ("B-session-in-caller-transaction", lambda c, e: session_case(c, e, True), "holds"),
         ("C-control-noindex-loader", control_noindex, "violated")]


def main() -> int:
    outp = Path(sys.argv[1])
    res = []
    for name, fn, want in CASES:
        c = lib.conn()
        t0 = time.time()
        r = {"case": name, "expected": want}
        try:
            lib.reset(c)
            e = lib.engine(c)
            r["steps"] = fn(c, e)
            kc = keys_check(c)
            r["key_violations"] = kc["violations"]
            r["outcome"] = "violated" if kc["violations"] else "holds"
            r["as_expected"] = r["outcome"] == want
        except Exception:  # noqa: BLE001
            r["outcome"] = "harness-error"
            r["trace"] = traceback.format_exc()[-1500:]
        finally:
            try:
                c.conn.rollback()
                c.conn.setAutoCommit(True)
            except Exception:  # noqa: BLE001
                pass
            try:
                from iris_vector_graph.bulk_loader import BulkLoader
                BulkLoader(c.conn).rebuild_all_indices()
            except Exception:  # noqa: BLE001
                pass
            lib.reset(c)
            c.close()
        r["secs"] = round(time.time() - t0, 2)
        res.append(r)
        print(json.dumps(r, default=str)[:2500], flush=True)
        lib.dump(outp, res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
