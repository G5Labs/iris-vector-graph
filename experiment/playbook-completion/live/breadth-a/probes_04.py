"""Live checks of module 04 (adjacency) findings in AUDITA. See probe_lib for the rules."""
from __future__ import annotations

import sys

from probe_lib import Result, conn, engine, erase, gname, run


def p0402_rolled_back_edge_served_current(r: Result):
    """F-0402: writer W opens a transaction and creates an edge (the row hook writes ^KG and steps ^KG("__version")
    outside the transaction); reader R computes WCC (cached under the token it read) while W is open; W rolls back;
    a fresh engine's WCC is served from the cache, still joining the rolled-back edge's endpoints.
    Oracle: AlgoCache.cls:5-7 "never wrongly fresh"; ADR-0012:23-26 names this case unsafe."""
    cw, ew = engine()
    cr, er = engine(conn())
    x, y = gname("wx"), gname("wy")
    try:
        ew.create_node(x)
        ew.create_node(y)
        t0 = r.obs("token_before", int(cr.call("Graph.KG.AlgoCache", "Token")))
        cw.o.tStart()
        ew.create_edge(x, "R", y)
        r.obs("writer_tlevel", cw.o.getTLevel())
        t1 = r.obs("token_with_open_write", int(cr.call("Graph.KG.AlgoCache", "Token")))
        comp = er.kg_WCC()
        r.obs("wcc_during_open_write_same_component", comp.get(x) == comp.get(y))
        cw.o.tRollback()
        r.obs("edge_rows_after_rollback", cw.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s = ?", x)[0][0])
        r.obs("out_entry_after_rollback", int(cw.o.isDefined("^KG", "out", 0, x, "R", y)))
        t2 = r.obs("token_after_rollback", int(cr.call("Graph.KG.AlgoCache", "Token")))
        c3, e3 = engine(conn())
        try:
            comp2 = e3.kg_WCC()
            stats = getattr(e3._store, "_algo_cache_stats", {})
            r.obs("fresh_engine_cache_stats", dict(stats))
            joined = r.obs("fresh_engine_wcc_same_component", comp2.get(x) == comp2.get(y))
        finally:
            c3.close()
        r["oracle"] = "after W's rollback no current cached answer includes W's edge"
        r["reproduced"] = bool(joined) and t2 == t1 and t1 > t0
        r["verdict"] = ("cache entry stamped with the rolled-back write's token served the rolled-back edge"
                        if r["reproduced"] else "not reproduced")
    finally:
        if cw.o.getTLevel():
            cw.o.tRollback()
        for n in (x, y):
            try:
                ew.delete_node(n, graph=None)
            except Exception as e:
                r.obs(f"cleanup_{n}", str(e))
        cw.close()
        cr.close()


def p0405_weight_refresh_token(r: Result):
    """F-0405: Adjacency.PutShadow on an existing edge with a new weight moves neither the source generation nor the
    graph-version token. Oracle: CONTEXT.md:116-119 (every write path that can change an algorithm's answer moves
    the token)."""
    c, eng = engine()
    g = gname("ps")
    try:
        c.call("Graph.KG.Adjacency", "PutShadow", g, "s", "P", "o", "1.0")
        g0 = r.obs("gen_after_first", str(c.o.get("^KG", "gen", g, "s")))
        t0 = r.obs("token_after_first", int(c.call("Graph.KG.AlgoCache", "Token")))
        c.call("Graph.KG.Adjacency", "PutShadow", g, "s", "P", "o", "5.0")
        r.obs("weight_after_second", str(c.o.get("^KG", "out", g, "s", "P", "o")))
        g1 = r.obs("gen_after_second", str(c.o.get("^KG", "gen", g, "s")))
        t1 = r.obs("token_after_second", int(c.call("Graph.KG.AlgoCache", "Token")))
        r["oracle"] = "a stored weight change moves the graph-version token"
        r["reproduced"] = t1 == t0 and g1 == g0
        r["verdict"] = "weight changed 1.0 -> 5.0 with token and generation unchanged" if r["reproduced"] else "moved"
    finally:
        # Out the way it went in: the adjacency writer's own Remove (no SQL rows exist for this graph).
        c.call("Graph.KG.Adjacency", "Remove", g, "s", "P", "o")
        c.o.kill("^KG", "gen", g)
        c.o.kill("^KG", "degc", g)
        r.obs("cleanup_out_left", int(c.o.isDefined("^KG", "out", g)))
        c.close()


def p0406_degc_kill_under_warm_stamp(r: Result):
    """F-0406: with the warm stamp current, killing ^KG("degc", g) alone (ADR-0012: "Kill it and every answer is still
    right") makes degree centrality answer 0 for every node until the next write."""
    c, eng = engine()
    g = gname("dw")
    try:
        for n in ("a", "b", "c"):
            eng.create_node(n, graph=g)
        eng.create_edge("a", "R", "b", graph=g)
        eng.create_edge("a", "R", "c", graph=g)
        before = r.obs("centrality_before", {d["id"] if "id" in d else d.get("node"): d.get("degree")
                                              for d in eng.degree_centrality(graph=g)})
        r.obs("warm_fill", int(c.call("Graph.KG.Adj", "WarmAll", g)))
        r.obs("all_warm", int(c.call("Graph.KG.Adj", "AllWarm", g)))
        c.o.kill("^KG", "degc", g)
        r.obs("all_warm_after_kill", int(c.call("Graph.KG.Adj", "AllWarm", g)))
        after = r.obs("centrality_after_kill", {d["id"] if "id" in d else d.get("node"): d.get("degree")
                                                 for d in eng.degree_centrality(graph=g)})
        r.obs("Adj.Degree_a", int(c.call("Graph.KG.Adj", "Degree", g, "a")))
        r["oracle"] = "ADR-0012:17 the cache is derived: kill it and every answer is still right"
        r["reproduced"] = (before.get("a") == 2) and (after.get("a") == 0)
        r["verdict"] = "degree centrality answered 0 for a node with 2 out-edges" if r["reproduced"] else "still right"
    finally:
        erase(eng, g)
        c.close()


def p0407_reweight_generation(r: Result):
    """F-0407: Adjacency.Reweight changes a weight without the writer lock and without moving the source generation
    (ADR-0012:31 says every adjacency write bumps the generation and holds the shared lock; the code exempts it on
    purpose). Observed through the public set_edge_weight (default graph)."""
    c, eng = engine()
    s, o = gname("rs"), gname("ro")
    try:
        eng.create_node(s)
        eng.create_node(o)
        eng.create_edge(s, "R", o, weight=1.0)
        g0 = r.obs("gen_before", str(c.o.get("^KG", "gen", 0, s)))
        r.obs("set_edge_weight", eng.set_edge_weight(s, "R", o, 7.0))
        r.obs("weight_after", str(c.o.get("^KG", "out", 0, s, "R", o)))
        g1 = r.obs("gen_after", str(c.o.get("^KG", "gen", 0, s)))
        r["oracle"] = "ADR-0012:31 / spec 252 FR-004 as written: every index change moves the source's generation"
        r["reproduced"] = g0 == g1
        r["verdict"] = "weight changed, generation unchanged (docs over-state the rule)" if r["reproduced"] else "moved"
    finally:
        for n in (s, o):
            try:
                eng.delete_node(n, graph=None)
            except Exception as e:
                r.obs(f"cleanup_{n}", str(e))
        c.close()


def p0409_failed_sync_rolls_back_caller(r: Result):
    """F-0409: inside a caller's open transaction, a sync() whose BuildKG fails runs TROLLBACK with no argument and
    discards the caller's earlier uncommitted write. Oracle: CHANGELOG 4.6.4 (CHANGELOG.md:410-424) "An IVG write never
    commits or rolls back a transaction its caller opened". The failing row is made as the upstream
    test_a_failed_buildkg_leaves_the_adjacency_and_releases_the_rebuild_lock makes it (graph_id '0', %NOINDEX)."""
    c, eng = engine()
    tag = gname("pz")
    keep = gname("keep")
    try:
        cur = c.conn.cursor()
        for node_id in (tag + "s", tag + "o"):
            cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, '0')", [node_id])
        cur.execute("INSERT %NOINDEX INTO Graph_KG.rdf_edges (s, p, o_id, graph_id) VALUES (?, 'POISONS', ?, '0')",
                    [tag + "s", tag + "o"])
        c.conn.commit()
        cur.close()
        c.o.tStart()
        r.obs("caller_tlevel_before", c.o.getTLevel())
        r.obs("caller_create_node", eng.create_node(keep))
        r.obs("caller_sees_own_node", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", keep)[0][0])
        try:
            eng.sync()
            r.obs("sync", "returned")
        except Exception as e:
            r.obs("sync", f"{type(e).__name__}: {str(e)[:200]}")
        lvl = r.obs("caller_tlevel_after", c.o.getTLevel())
        left = r.obs("caller_node_after_failed_sync", c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id = ?", keep)[0][0])
        r["oracle"] = "the caller's transaction and its writes survive a failed IVG call made inside it"
        r["reproduced"] = lvl == 0 and left == 0
        r["verdict"] = "failed sync ended the caller's transaction and discarded its node" if r["reproduced"] else "kept"
    finally:
        if c.o.getTLevel():
            c.o.tRollback()
        cur = c.conn.cursor()
        try:
            cur.execute("DELETE %NOINDEX FROM Graph_KG.rdf_edges WHERE %NOINDEX graph_id = '0' AND %NOINDEX s = ?",
                        [tag + "s"])
            cur.execute('BUILD INDEX FOR TABLE Graph_KG.rdf_edges INDEX "%%DDLBEIndex"')
            cur.execute("DELETE FROM Graph_KG.nodes WHERE node_id %STARTSWITH ? AND graph_id = '0'", [tag])
            c.conn.commit()
        finally:
            cur.close()
        try:
            eng.delete_node(keep, graph=None)
        except Exception:
            pass
        r.obs("cleanup_poison_rows_left", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = '0'")[0][0])
        try:
            eng.sync()
            r.obs("cleanup_sync", "ok")
        except Exception as e:
            r.obs("cleanup_sync", str(e)[:200])
        c.close()


def pC0403_failed_rebuild_leaves_partial_adjacency(r: Result):
    """New candidate (journal J12 + source): with the adjacency index declared, BuildKG purges and refills ^KG out/in by
    %BuildIndices after its TCommit, in parallel jobs (TraversalBuild.cls:120-131), while its comment (:46-55) says the
    kill sits inside the transaction so that a row it cannot process leaves the old adjacency, never a destroyed one.
    Here a row the rebuild refuses (graph_id '0', made as the upstream test makes it) fails sync(); the graph's 400
    committed edges are then counted in ^KG("out")."""
    c, eng = engine()
    g = gname("rb")
    tag = gname("pz")
    n = 400
    try:
        eng.bulk_create_nodes([{"id": f"v{i}"} for i in range(n + 1)], graph=g)
        eng.bulk_create_edges([{"source_id": f"v{i}", "predicate": "R", "target_id": f"v{i+1}"} for i in range(n)], graph=g)
        rows = r.obs("rows", c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ?", g)[0][0])
        def out_count():
            k, cnt = "", 0
            while True:
                k = c.o.nextSubscript(False, "^KG", "out", g, k)
                if k in (None, ""):
                    return cnt
                cnt += 1
        r.obs("out_sources_before", out_count())
        cur = c.conn.cursor()
        for node_id in (tag + "s", tag + "o"):
            cur.execute("INSERT INTO Graph_KG.nodes (node_id, graph_id) VALUES (?, '0')", [node_id])
        cur.execute("INSERT %NOINDEX INTO Graph_KG.rdf_edges (s, p, o_id, graph_id) VALUES (?, 'POISONS', ?, '0')",
                    [tag + "s", tag + "o"])
        c.conn.commit()
        cur.close()
        try:
            eng.sync()
            r.obs("sync", "returned")
        except Exception as e:
            r.obs("sync", f"{type(e).__name__}: {str(e)[:160]}")
        after = r.obs("out_sources_after_failed_sync", out_count())
        v = eng.verify_graph(g)
        r.obs("verify_after", {"ok": v.get("ok"), "counts": v.get("counts")})
        r["oracle"] = "TraversalBuild.cls:46-55: a row the rebuild cannot process leaves the adjacency as it was"
        r["reproduced"] = after < n
        r["verdict"] = (f"{after} of {n} sources keep ^KG out after the failed rebuild" if r["reproduced"]
                        else "adjacency intact after the failed rebuild")
    finally:
        cur = c.conn.cursor()
        try:
            cur.execute("DELETE %NOINDEX FROM Graph_KG.rdf_edges WHERE %NOINDEX graph_id = '0' AND %NOINDEX s = ?",
                        [tag + "s"])
            cur.execute('BUILD INDEX FOR TABLE Graph_KG.rdf_edges INDEX "%%DDLBEIndex"')
            cur.execute("DELETE FROM Graph_KG.nodes WHERE node_id %STARTSWITH ? AND graph_id = '0'", [tag])
            c.conn.commit()
        finally:
            cur.close()
        try:
            eng.sync()
            r.obs("cleanup_sync", "ok")
        except Exception as e:
            r.obs("cleanup_sync", str(e)[:200])
        erase(eng, g)
        c.close()


PROBES = {f.__name__: f for f in (pC0403_failed_rebuild_leaves_partial_adjacency, p0402_rolled_back_edge_served_current, p0405_weight_refresh_token,
                                  p0406_degc_kill_under_warm_stamp, p0407_reweight_generation,
                                  p0409_failed_sync_rolls_back_caller)}

if __name__ == "__main__":
    sys.exit(run("04", PROBES, sys.argv[1:]))
