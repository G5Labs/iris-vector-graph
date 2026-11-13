"""Live checks of module 02 (graph identity) findings in AUDITA. See probe_lib for the rules."""
from __future__ import annotations

import sys

from probe_lib import Result, conn, engine, erase, gname, run

EDGE_ROWS = ("SELECT ekey FROM Graph_KG.rdf_edges WHERE graph_id = ? AND s = ? AND p = ? AND o_id = ? "
             "ORDER BY ekey")


def _mg_two_then_drop_zero(eng, g):
    """Multigraph g: two Cypher CREATEs of one triple (k 0 and k 1), then a per-edge Cypher DELETE of k 0."""
    eng.create_node("a", graph=g)
    eng.create_node("b", graph=g)
    eng.set_multigraph(g, True)
    for k in (0, 1):
        eng.execute_cypher(f"USE GRAPH '{g}' MATCH (a {{node_id: 'a'}}), (b {{node_id: 'b'}}) "
                           f"CREATE (a)-[:R {{k: {k}}}]->(b)", {}, raise_on_error=True)
    eng.execute_cypher(f"USE GRAPH '{g}' MATCH (a {{node_id: 'a'}})-[r:R {{k: 0}}]->(b) DELETE r", {},
                       raise_on_error=True)


def p0201_mode_off_lone_ekey1(r: Result):
    """F-0201: after create, create, delete key-0 edge in a multigraph, mode off is accepted and create_edge adds a
    second row of the triple in a graph that says it is single-edge; a per-edge delete then leaves a row without
    adjacency. Oracle: spec 234 FR-002 (mode off => at most one row per triple)."""
    c, eng = engine()
    g = gname("m1")
    try:
        _mg_two_then_drop_zero(eng, g)
        r.obs("rows_after_delete_k0", [x[0] for x in c.sql(EDGE_ROWS, g, "a", "R", "b")])
        try:
            eng.set_multigraph(g, False)
            r.obs("mode_off_accepted", True)
        except Exception as e:
            r.obs("mode_off_accepted", f"refused: {e}")
        r.obs("is_multi_server", str(c.call("Graph.KG.GraphMode", "IsMulti", g)))
        r.obs("create_edge_returned", eng.create_edge("a", "R", "b", graph=g))
        ekeys = r.obs("rows_after_create_edge", [x[0] for x in c.sql(EDGE_ROWS, g, "a", "R", "b")])
        # Impact: remove the ekey-1 row with a per-edge Cypher delete; the surviving row should keep its adjacency.
        # WHERE form: the inline form {k: 1} fails on the create_edge row's NULL qualifiers (F-C0101).
        eng.execute_cypher(f"USE GRAPH '{g}' MATCH (a {{node_id: 'a'}})-[r:R]->(b) WHERE r.k = 1 DELETE r", {},
                           raise_on_error=True)
        r.obs("rows_after_delete_k1", [x[0] for x in c.sql(EDGE_ROWS, g, "a", "R", "b")])
        r.obs("adjacency_out_leaf_defined", int(c.o.isDefined("^KG", "out", g, "a", "R", "b")))
        v = eng.verify_graph(g)
        r.obs("verify_graph_ok", v.get("ok"))
        r.obs("verify_graph_drift", v.get("drift"))
        r["oracle"] = "mode off => at most one row per triple (spec 234 FR-002)"
        r["reproduced"] = len(ekeys) >= 2 and str(c.call("Graph.KG.GraphMode", "IsMulti", g)) == "0"
        r["verdict"] = "two rows of one triple in a mode-off graph" if r["reproduced"] else "not reproduced"
    finally:
        erase(eng, g)
        c.close()


def p0202_reserved_name_writers(r: Result):
    """F-0202: create_node / store_node accept graph "0" (no validate_graph_name), the counts and delete_node refuse
    it; store_edge into "0" fails late inside GraphKey.ForIndex. Oracle: ADR-0003 (the validator rejects "0")."""
    c, eng = engine()
    nid = gname("n0")
    try:
        try:
            r.obs("create_node_graph0", eng.create_node(nid, graph="0"))
        except Exception as e:
            r.obs("create_node_graph0", f"{type(e).__name__}: {e}")
        try:
            r.obs("store_node_graph0", eng.store_node(nid + "s", graph="0"))
        except Exception as e:
            r.obs("store_node_graph0", f"{type(e).__name__}: {str(e)[:300]}")
        r.obs("rows_in_graph_0", c.sql("SELECT node_id FROM Graph_KG.nodes WHERE graph_id = '0' AND node_id %STARTSWITH ?", nid))
        for name, fn in (("node_count", lambda: eng.node_count(graph="0")),
                         ("delete_node", lambda: eng.delete_node(nid, graph="0"))):
            try:
                r.obs(f"{name}_graph0", fn())
            except Exception as e:
                r.obs(f"{name}_graph0", f"{type(e).__name__}: {str(e)[:200]}")
        try:
            r.obs("store_edge_graph0", eng.store_edge(nid, "R", nid + "s", graph="0"))
        except Exception as e:
            r.obs("store_edge_graph0", f"{type(e).__name__}: {str(e)[:300]}")
        written = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = '0' AND node_id %STARTSWITH ?", nid)[0][0]
        r["oracle"] = "every writer that takes a graph name refuses the reserved name \"0\" (ADR-0003:119-121)"
        r["reproduced"] = written > 0
        r["verdict"] = f"{written} node rows written under the reserved graph name 0" if written else "refused"
    finally:
        # The API cannot remove them (delete_node refuses "0"): remove this probe's own rows by SQL.
        for t in ("rdf_props", "rdf_labels"):
            c.sql(f"DELETE FROM Graph_KG.{t} WHERE graph_id = '0' AND s %STARTSWITH ?", nid)
        c.sql("DELETE FROM Graph_KG.nodes WHERE graph_id = '0' AND node_id %STARTSWITH ?", nid)
        r.obs("cleanup_rows_left", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = '0' AND node_id %STARTSWITH ?", nid)[0][0])
        c.close()


def p0203_c1_control_char(r: Result):
    """F-0203 / P-0202: Python's name check accepts U+0085 (a C1 control); the server's $ZStrip(,"*C") check refuses
    it, so the write fails on the server with an IRIS error instead of the Python ValueError."""
    from iris_vector_graph._validate import validate_graph_name
    c, eng = engine()
    g = "ba\x85" + gname("c1")
    try:
        try:
            r.obs("python_validate", repr(validate_graph_name(g)))
        except Exception as e:
            r.obs("python_validate", f"{type(e).__name__}: {e}")
        sc = c.o.classMethodValue("%SYSTEM.Status", "GetErrorText", c.call("Graph.KG.GraphKey", "Validate", g))
        r.obs("server_validate_error_text", str(sc))
        try:
            r.obs("create_edge", eng.create_edge("a", "R", "b", graph=g))
        except Exception as e:
            r.obs("create_edge", f"{type(e).__name__}: {str(e)[:300]}")
        r["oracle"] = "the Python mirror refuses every name the server refuses (CHANGELOG.md:4618-4620)"
        r["reproduced"] = (not r["observed"]["python_validate"].startswith("ValueError")) and bool(str(sc))
        r["verdict"] = "Python accepts, server refuses" if r["reproduced"] else "not reproduced"
    finally:
        rest = c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE graph_id = ?", g)[0][0]
        r.obs("rows_left_in_c1_graph", rest)
        c.close()


def p0204_verify_parallel(r: Result):
    """F-0204 / F-0403: verify_graph on a healthy multigraph with two parallel edges reports missing adjacency.
    Oracle: spec 234 SC-005 (zero drift on a multigraph) and spec.md:78-80."""
    c, eng = engine()
    g = gname("vp")
    try:
        eng.create_node("a", graph=g)
        eng.create_node("b", graph=g)
        eng.set_multigraph(g, True)
        for k in (0, 1, 2):
            eng.execute_cypher(f"USE GRAPH '{g}' MATCH (a {{node_id: 'a'}}), (b {{node_id: 'b'}}) "
                               f"CREATE (a)-[:R {{k: {k}}}]->(b)", {}, raise_on_error=True)
        r.obs("rows", [x[0] for x in c.sql(EDGE_ROWS, g, "a", "R", "b")])
        r.obs("keyed_count", str(c.o.get("^KG", "out", g, "a", "R", "b", "#")))
        v = eng.verify_graph(g)
        r.obs("verify", {k: v.get(k) for k in ("ok", "counts", "drift")})
        r["oracle"] = "verify_graph(g)['ok'] is true for a multigraph whose index matches its rows"
        r["reproduced"] = v.get("ok") in (False, 0)
        r["verdict"] = "false drift on parallel edges" if r["reproduced"] else "verifies clean"
    finally:
        erase(eng, g)
        c.close()


def p0206_cross_graph_hydration(r: Result):
    """F-0206 (and F-0106's family): get_nodes_by_label takes ids from every graph and hydrates them from the
    default graph. Oracle: USER_GUIDE.md:466-467 and SYS-I2 (one graph's content never answers about another)."""
    c, eng = engine()
    g = gname("x")
    nid = gname("id")
    label = gname("L")
    try:
        eng.create_node(nid, labels=[label], properties={"where": "named"}, graph=g)
        eng.create_node(nid, labels=["Other"], properties={"where": "default"})
        got = r.obs("get_nodes_by_label", eng.get_nodes_by_label(label))
        hits = [n for n in got if (n.get("id") == nid or n.get("node_id") == nid)]
        bad = [n for n in hits if label not in (n.get("labels") or []) or
               (n.get("properties") or n).get("where") == "default"]
        r["oracle"] = "every node answered for label L holds L (and its properties) in its own graph"
        r["reproduced"] = bool(bad)
        r["verdict"] = "answered the default graph's node, which lacks the label" if bad else "scoped correctly"
    finally:
        erase(eng, g)
        try:
            eng.delete_node(nid, graph=None)
        except Exception as e:
            r.obs("cleanup_default", str(e))
        c.close()


def p0208_stale_mode_cache(r: Result):
    """F-0208: engine E1 caches multigraph mode on; E2 turns it off; E1's next Cypher CREATE of the same triple still
    writes MAX(ekey)+1, so the mode-off graph holds two rows of one triple."""
    c1, e1 = engine()
    c2, e2 = engine(conn())
    g = gname("sc")
    try:
        e1.create_node("a", graph=g)
        e1.create_node("b", graph=g)
        e1.set_multigraph(g, True)
        q = (f"USE GRAPH '{g}' MATCH (a {{node_id: 'a'}}), (b {{node_id: 'b'}}) CREATE (a)-[:R]->(b)")
        e1.execute_cypher(q, {}, raise_on_error=True)
        r.obs("e1_cached_multi", e1.is_multigraph(g))
        e2.set_multigraph(g, False)
        r.obs("server_mode_after_e2_off", str(c2.call("Graph.KG.GraphMode", "IsMulti", g)))
        r.obs("e1_cached_after", e1.is_multigraph(g))
        e1.execute_cypher(q, {}, raise_on_error=True)
        ekeys = r.obs("rows", [x[0] for x in c1.sql(EDGE_ROWS, g, "a", "R", "b")])
        r["oracle"] = "mode off => at most one row per triple, whichever engine writes (spec 234 FR-002)"
        r["reproduced"] = len(ekeys) >= 2
        r["verdict"] = "stale cache wrote a parallel edge into a mode-off graph" if r["reproduced"] else "refused"
    finally:
        erase(e1, g)
        c1.close()
        c2.close()


def pC0101_inline_rel_prop_null_qualifiers(r: Result):
    """New: a Cypher relationship pattern with an inline property, [r:R {k: 0}], fails with SQLCODE -149
    (Graph_KG.JSON_VALUE <INVALID OREF>) when a candidate edge has NULL qualifiers, which is what create_edge writes for
    an edge with no properties. The WHERE form of the same filter answers. Oracle: the two forms are equivalent
    openCypher; a filter on a missing property is false/null, not an error."""
    c, eng = engine()
    g = gname("jv")
    try:
        eng.create_node("a", graph=g)
        eng.create_node("b", graph=g)
        eng.create_edge("a", "R", "b", graph=g)
        r.obs("qualifiers", c.sql("SELECT qualifiers FROM Graph_KG.rdf_edges WHERE graph_id = ?", g))
        out = {}
        for name, q in (("where_form", f"USE GRAPH '{g}' MATCH (x)-[r:R]->(y) WHERE r.k = 0 RETURN x.node_id"),
                        ("inline_form", f"USE GRAPH '{g}' MATCH (x)-[r:R {{k: 0}}]->(y) RETURN x.node_id"),
                        ("inline_delete", f"USE GRAPH '{g}' MATCH (x)-[r:R {{k: 0}}]->(y) DELETE r"),
                        ("merge_inline", f"USE GRAPH '{g}' MATCH (x {{node_id: 'a'}}), (y {{node_id: 'b'}}) "
                                         "MERGE (x)-[r:R {k: 0}]->(y) RETURN count(r)")):
            try:
                out[name] = ["ok", eng.execute_cypher(q, {}, raise_on_error=True).rows]
            except Exception as e:
                out[name] = ["error", str(e)[-220:]]
        r.obs("cypher", out)
        try:
            r.obs("json_value_null", c.sql("SELECT Graph_KG.JSON_VALUE(NULL, '$.k')"))
        except Exception as e:
            r.obs("json_value_null", str(e)[-200:])
        r["oracle"] = "an inline relationship property filter answers like the equivalent WHERE filter"
        r["reproduced"] = out["where_form"][0] == "ok" and out["inline_form"][0] == "error"
        r["verdict"] = "inline form raises SQLCODE -149 on NULL qualifiers" if r["reproduced"] else "not reproduced"
    finally:
        erase(eng, g)
        c.close()


PROBES = {f.__name__: f for f in (p0201_mode_off_lone_ekey1, p0202_reserved_name_writers, p0203_c1_control_char,
                                  p0204_verify_parallel, p0206_cross_graph_hydration, p0208_stale_mode_cache,
                                  pC0101_inline_rel_prop_null_qualifiers)}

if __name__ == "__main__":
    sys.exit(run("02", PROBES, sys.argv[1:]))
