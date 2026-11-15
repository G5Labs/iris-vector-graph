"""Module 08 live-check helpers: scratch data in AUDITB (ids b08_*, graphs b08g*), setup and cleanup.

Scratch layout (all through the pin's Cypher API, SQL path: native_cypher=False):
- default graph '':  b08_s (B08L, z=1, name 'plain'), b08_t (B08L); edge b08_s -[:B08Q]-> b08_t
- graph b08gA:       b08_x (B08L, name 'ax') -[:B08R]-> b08_m (B08L) -[:B08S]-> b08_n (B08L)
- graph b08gB:       b08_m (B08B) -[:B08R]-> b08_leak (B08B)    (b08_m is an id shared with b08gA)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import *  # noqa: F401,F403,E402

GRAPHS = ["b08gA", "b08gB", "b08gC"]

_blive_write_log = write_log


def write_log(s, obj, name=None):  # noqa: F811  (blive's, with an optional rerun suffix: never overwrite a log)
    """blive.write_log, appending $B08_LOG_SUFFIX (e.g. '-rerun') to the log name so a rerun writes a NEW file."""
    import os as _os
    return _blive_write_log(s, obj, name=(name or s.name) + _os.environ.get("B08_LOG_SUFFIX", ""))


def run(s, q, params=None, **kw):
    """execute_cypher, returning (columns, rows, error, exception-type, exception-text)."""
    try:
        r = s.eng.execute_cypher(q, parameters=params or {}, **kw)
        return {"q": q, "columns": list(r.columns or []), "rows": [list(x) for x in (r.rows or [])],
                "error": getattr(r, "error", None), "exc": None, "sql": str(getattr(r, "sql", ""))[:2000]}
    except BaseException as e:  # noqa: BLE001  (recorded)
        return {"q": q, "columns": [], "rows": [], "error": None, "exc": type(e).__name__,
                "exc_mro": [c.__name__ for c in type(e).__mro__], "msg": str(e)[:1500]}


def scratch_counts(s):
    out = {}
    for t, col in (("nodes", "node_id"), ("rdf_labels", "s"), ("rdf_props", "s"), ("rdf_edges", "s")):
        out[t] = s.c.sql(f"SELECT COUNT(*) FROM Graph_KG.{t} WHERE {col} %STARTSWITH 'b08'")[0][0]
    out["rdf_edges_o"] = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE o_id %STARTSWITH 'b08'")[0][0]
    out["b08_labelled"] = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_labels WHERE label %STARTSWITH 'B08'")[0][0]
    out["b08_edge_types"] = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE p %STARTSWITH 'B08'")[0][0]
    return out


def cleanup(s):
    """Remove every b08 row (each graph) through Cypher DETACH DELETE; then verify with SQL. Raw SQL delete is the
    fallback for rows Cypher cannot reach (e.g. edges whose nodes are gone); functional indexes keep ^KG in step."""
    res = []
    for g in [None] + GRAPHS:
        pre = f"USE GRAPH '{g}' " if g else ""
        res.append(run(s, pre + "MATCH (n) WHERE n.id STARTS WITH 'b08' DETACH DELETE n"))
    # nodes the checks created without an id of their own (FOREACH, count-only CREATE): found by their B08* label
    for lab, g in s.c.sql("SELECT DISTINCT label, graph_id FROM Graph_KG.rdf_labels WHERE label %STARTSWITH 'B08'"):
        if not re.fullmatch(r"B08\w*", lab):
            continue
        pre = f"USE GRAPH '{g}' " if g else ""
        res.append(run(s, pre + f"MATCH (n:{lab}) DETACH DELETE n"))
    left = scratch_counts(s)
    if any(left.values()):
        for t, col in (("rdf_edges", "s"), ("rdf_edges", "o_id"), ("rdf_props", "s"), ("rdf_labels", "s"),
                       ("nodes", "node_id")):
            try:
                s.c.sql(f"DELETE FROM Graph_KG.{t} WHERE {col} %STARTSWITH 'b08'")
            except Exception as e:  # noqa: BLE001
                res.append({"sql_delete_error": f"{t}: {e}"})
        left = scratch_counts(s)
    return {"cypher": [r.get("exc") or r.get("error") for r in res], "left": left}


def setup(s):
    steps = [
        run(s, "CREATE (s:B08L {id:'b08_s', z:1, name:'plain'})-[:B08Q]->(t:B08L {id:'b08_t'})"),
        run(s, "USE GRAPH 'b08gA' CREATE (x:B08L {id:'b08_x', name:'ax'})-[:B08R]->(m:B08L {id:'b08_m'})"
               "-[:B08S]->(n:B08L {id:'b08_n'})"),
        run(s, "USE GRAPH 'b08gB' CREATE (m:B08B {id:'b08_m'})-[:B08R]->(l:B08B {id:'b08_leak'})"),
    ]
    rows = s.c.sql("SELECT graph_id, node_id FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'b08' ORDER BY 1, 2")
    edges = s.c.sql("SELECT graph_id, s, p, o_id FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'b08' ORDER BY 1, 2")
    return {"steps": [{k: v for k, v in st.items() if k != "sql"} for st in steps],
            "nodes": [list(r) for r in rows], "edges": [list(r) for r in edges]}


def ledger_meta(s):
    import json as _j
    return _j.loads(str(s.c.call("Graph.KG.Ledger", "Meta")))


def conn_retry(tries: int = 40, wait: float = 6.0):
    """Conn("AUDITB") with retries: IRIS Community allows 8 license connections shared by every lane, so a connect
    can fail with 'Unable to allocate a license' while other lanes hold them."""
    import time as _t
    last = None
    for _ in range(tries):
        try:
            return Conn(NAMESPACE)
        except Exception as e:  # noqa: BLE001
            last = e
            if "license" not in str(e).lower():
                raise
            _t.sleep(wait)
    raise last


@contextlib.contextmanager
def session08(name: str, **engine_kw):
    """blive.session with license-retrying connects (lane lock held for the whole session)."""
    with lane_lock():
        c = conn_retry()
        s = None
        try:
            eng = make_engine(c, **engine_kw)
            s = Session(name, c, eng, J.storage_map(c))
            yield s
        finally:
            for x in (s.extra_conns if s else []):
                x.close()
            c.close()
