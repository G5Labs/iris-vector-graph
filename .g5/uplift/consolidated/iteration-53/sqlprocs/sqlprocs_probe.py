"""Iteration 53 Part B probe: MatchEdges / MatchEdgesAllGraphs, DijkstraPath, backfill_temporal_rows, rebuild_edge_indices.

Runs only against ivg-cont-20261117-iris, in a namespace I53P this probe creates from %SYS (dropped and re-created on
each run). Users i53p_* are created in %SYS and deleted at the end.

    (cd $RUN_DIR/pin && IVG_REPO=$OLDPWD $RUN_DIR/venv/bin/python -B $OLDPWD/.g5/uplift/consolidated/iteration-53/sqlprocs/sqlprocs_probe.py)
"""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(os.environ.get("IVG_REPO", str(HERE.parents[4]))).resolve()
sys.path.insert(0, str(REPO / ".g5/uplift/consolidated/iteration-36"))
import runtime  # noqa: E402

NS = os.environ.get("I53P_NS", "I53P")
PW = "i53pPass9"
RUN = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
OK_TAIL = 'Write "RESULT ",$Select($System.Status.IsOK(sc):"OK",1:$System.Status.GetErrorText(sc)),!'


def iris_sys(script):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "%SYS"],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout


def recreate_namespace(ns=NS):
    script = (f'Set ns="{ns}", dir="/usr/irissys/mgr/{ns.lower()}/"\n'
              'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
              'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
              'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n'
              'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
              'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
              'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } '
              + OK_TAIL)
    out = iris_sys(script)
    assert "RESULT OK" in out, out


def connect(user="_SYSTEM", pw="SYS"):
    import iris.dbapi
    from tests import conftest as fx
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username=user, password=pw)
    if not fx.container_hostname_matches(fx.probe_instance_hostname(c), fx.docker_container_hostname(runtime.NAME),
                                         fx.docker_container_id(runtime.NAME)):
        c.close(); raise RuntimeError("fixture identity mismatch")
    return c


def engine(c):
    from iris_vector_graph.engine import IRISGraphEngine
    return IRISGraphEngine(c, embedding_dimension=8, native_cypher=False)


USERS = {
    # user: SQL grants (the role gives the database only)
    "i53p_noselect": ["GRANT EXECUTE ON SCHEMA Graph_KG TO {u}", "GRANT SELECT ON Graph_KG.nodes TO {u}"],
    "i53p_select": ["GRANT EXECUTE ON SCHEMA Graph_KG TO {u}", "GRANT SELECT ON SCHEMA Graph_KG TO {u}"],
    "i53p_writer": ["GRANT EXECUTE ON SCHEMA Graph_KG TO {u}", "GRANT SELECT ON SCHEMA Graph_KG TO {u}",
                    "GRANT INSERT, UPDATE, DELETE ON SCHEMA Graph_KG TO {u}"],
}


def make_users(cur):
    for u, grants in USERS.items():
        out = iris_sys(f'If ##class(Security.Users).Exists("{u}") {{ Set sc=##class(Security.Users).Delete("{u}") }}\n'
                       f'Set sc=##class(Security.Users).Create("{u}","%DB_%DEFAULT","{PW}","i53p probe user")\n' + OK_TAIL)
        assert "RESULT OK" in out, out
        for g in grants:
            cur.execute(g.format(u=u))


def drop_users():
    return {u: "RESULT OK" in iris_sys(f'Set sc=##class(Security.Users).Delete("{u}")\n' + OK_TAIL) for u in USERS}


def q1(cur, sql, args=()):
    try:
        cur.execute(sql, list(args))
        r = cur.fetchone()
        return r[0] if r else None
    except Exception as x:
        return f"EXC {type(x).__name__}: {str(x)[:220]}"


def main():
    t0 = time.time()
    recreate_namespace()
    c = connect(); cur = c.cursor(); e = engine(c)
    out = {"run": RUN, "namespace": NS, "setup": None}
    st = e.initialize_schema()
    out["setup_adjacency"] = st.get("adjacency_index") if isinstance(st, dict) else str(st)[:300]
    # ---- fixture graph g: a-P(1)->b-P(1)->c-P(1)->d, a-P(10)->d, a-Q(1)->e, e-Q->d (no weight); g2 shares a-P->b
    for g in ("g", "g2", "gz", None):
        pass
    E = [("a", "P", "b", 1.0, "g"), ("b", "P", "c", 1.0, "g"), ("c", "P", "d", 1.0, "g"), ("a", "P", "d", 10.0, "g"),
         ("a", "Q", "e", 1.0, "g"), ("e", "Q", "d", None, "g"),
         ("a", "P", "b", 2.0, "g2"), ("a", "P", "b2", 1.0, "g2"),
         ("s", "Z", "t", 0.0, "gz"), ("s", "Y", "u", -2.0, "gz"),
         ("x", "P", "y", 3.0, None)]
    for s_, p_, o_, w_, g_ in E:
        for n in (s_, o_):
            e.create_node(n, graph=g_)
        e.create_edge(s_, p_, o_, weight=w_, graph=g_)
    ME = {}
    def me(k, sql, args=()):
        r = q1(cur, sql, args)
        try:
            ME[k] = sorted(json.loads(r), key=lambda d: (d["g"], d["s"], d["p"], d["o"])) if isinstance(r, str) and r.startswith("[") else r
        except Exception:
            ME[k] = r
    me("a_P_g", "SELECT Graph_KG.MatchEdges('a','P',0,'g')")
    me("a_all_g", "SELECT Graph_KG.MatchEdges('a','',0,'g')")
    me("a_null_g", "SELECT Graph_KG.MatchEdges('a',NULL,0,'g')")
    me("any_P_g", "SELECT Graph_KG.MatchEdges('','P',0,'g')")
    me("a_P_g2", "SELECT Graph_KG.MatchEdges('a','P',0,'g2')")
    me("a_P_allgraphs", "SELECT Graph_KG.MatchEdgesAllGraphs('a','P',0)")
    me("a_P_g_shard1", "SELECT Graph_KG.MatchEdges('a','P',1,'g')")
    me("a_P_g_shard7", "SELECT Graph_KG.MatchEdges('a','P',7,'g')")
    me("x_P_default_empty", "SELECT Graph_KG.MatchEdges('x','P',0,'')")
    me("x_P_default_zero", "SELECT Graph_KG.MatchEdges('x','P',0,0)")
    me("x_P_default_null", "SELECT Graph_KG.MatchEdges('x','P',0,NULL)")
    me("x_P_default_omitted", "SELECT Graph_KG.MatchEdges('x','P')")
    me("a_P_nograph_omitted", "SELECT Graph_KG.MatchEdges('a','P')")
    me("s_gz", "SELECT Graph_KG.MatchEdges('s','',0,'gz')")
    me("e_Q_g_unweighted", "SELECT Graph_KG.MatchEdges('e','Q',0,'g')")
    out["matchedges"] = ME
    # ---- IVG_EDGESCAN: the same Cypher hop on both SQL plans (no USE GRAPH, USE GRAPH '' and a named graph)
    CY = {}
    for flag in ("0", "1"):
        os.environ["IVG_EDGESCAN"] = flag
        for k, q in (("nograph", "MATCH (a {id: 'a'})-[r:P]->(b) RETURN b.id AS o%s, r.weight AS w ORDER BY o%s, w"),
                     ("default", "USE GRAPH '' MATCH (a {id: 'x'})-[r:P]->(b) RETURN b.id AS o%s, r.weight AS w ORDER BY o%s"),
                     ("named", "USE GRAPH 'g' MATCH (a {id: 'a'})-[r:P]->(b) RETURN b.id AS o%s ORDER BY o%s"),
                     ("count", "MATCH (a {id: 'a'})-[r]->(b) RETURN count(r) AS n%s")):
            qq = q.replace("%s", flag)
            try:
                r = e.execute_cypher(qq)
                CY[f"{k}_{flag}"] = {"rows": [list(x) for x in r.rows], "err": str(r.error) if getattr(r, "error", None) else None}
            except Exception as x:
                CY[f"{k}_{flag}"] = f"EXC {type(x).__name__}: {str(x)[:200]}"
    os.environ.pop("IVG_EDGESCAN", None)
    out["edgescan"] = CY
    # ---- multigraph: parallel edges seen by the scan and by rdf_edges
    MG = {}
    try:
        e.set_multigraph("gm", True)
        for n in ("m1", "m2"):
            e.create_node(n, graph="gm")
        MG["e1"] = e.create_edge("m1", "P", "m2", weight=1.0, graph="gm")
        MG["e2"] = e.create_edge("m1", "P", "m2", weight=5.0, graph="gm")
        MG["rows"] = q1(cur, "SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = 'gm' AND s = 'm1'")
        r = q1(cur, "SELECT Graph_KG.MatchEdges('m1','P',0,'gm')")
        MG["scan"] = json.loads(r) if isinstance(r, str) and r.startswith("[") else r
        r = q1(cur, "SELECT Graph_KG.MatchEdgesAllGraphs('m1','P',0)")
        MG["scan_all"] = json.loads(r) if isinstance(r, str) and r.startswith("[") else r
        for flag in ("0", "1"):
            os.environ["IVG_EDGESCAN"] = flag
            r = e.execute_cypher(f"MATCH (a {{id: 'm1'}})-[r:P]->(b) RETURN count(r) AS n{flag}")
            MG[f"cypher_count_{flag}"] = [list(x) for x in r.rows]
            r = e.execute_cypher(f"CALL ivg.shortestPath.weighted('m1', 'm2') YIELD totalCost RETURN totalCost AS c{flag}")
            MG[f"dijkstra_{flag}"] = [list(x) for x in r.rows]
        os.environ.pop("IVG_EDGESCAN", None)
        MG["dijkstra_sql"] = q1(cur, "SELECT Graph_KG.DijkstraPath('m1','m2','',9999,10,'out','','gm')")
    except Exception as x:
        MG["exc"] = f"{type(x).__name__}: {str(x)[:200]}"
    out["multigraph"] = MG
    # ---- DijkstraPath
    DJ = {}
    def dj(k, args):
        r = q1(cur, "SELECT Graph_KG.DijkstraPath(?,?,?,?,?,?,?,?)", args)
        try:
            DJ[k] = json.loads(r) if isinstance(r, str) and r.startswith("{") else r
        except Exception:
            DJ[k] = r
    base = ["a", "d", "", 9999, 10, "out", "", "g"]
    def var(**kw):
        a = list(base); idx = {"src": 0, "dst": 1, "wp": 2, "cost": 3, "hops": 4, "dir": 5, "preds": 6, "graph": 7}
        for k, v in kw.items():
            a[idx[k]] = v
        return a
    dj("defaults", base)
    dj("hops1", var(hops=1)); dj("hops2", var(hops=2)); dj("hops0", var(hops=0)); dj("hopsneg", var(hops=-1))
    dj("cost1_5", var(cost=1.5)); dj("cost2", var(cost=2)); dj("cost1_99", var(cost=1.99)); dj("cost10", var(cost=10))
    dj("predsP", var(preds='["P"]')); dj("preds_emptylist", var(preds="[]")); dj("predsQ", var(preds='["Q"]'))
    dj("out_from_d", var(src="d", dst="a")); dj("in_from_d", var(src="d", dst="a", dir="in"))
    dj("both_from_d", var(src="d", dst="a", dir="both"))
    dj("dir_sideways", var(dir="sideways")); dj("wp_cost", var(wp="cost")); dj("wp_weight", var(wp="weight"))
    dj("graph_empty", var(graph="")); dj("graph_g2_ab", var(dst="b", graph="g2"))
    dj("zero_weight", ["s", "t", "", 9999, 10, "out", "", "gz"]); dj("neg_weight", ["s", "u", "", 9999, 10, "out", "", "gz"])
    dj("same_a", var(dst="a")); dj("same_unknown", var(src="zz", dst="zz")); dj("same_unknown_cost0", var(src="zz", dst="zz", cost=0))
    dj("empty_both", var(src="", dst="")); dj("empty_src", var(src=""))
    dj("unknown_dst", var(dst="nope")); dj("default_graph_x_y", ["x", "y", "", 9999, 10, "out", "", ""])
    DJ["null_graph"] = q1(cur, "SELECT Graph_KG.DijkstraPath('x','y','',9999,10,'out','',NULL)")
    DJ["omitted_args"] = q1(cur, "SELECT Graph_KG.DijkstraPath('x','y')")
    # the Cypher CALL on the same graph
    CALL = {}
    for k, q in (("defaults", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd') YIELD path, totalCost RETURN path, totalCost"),
                 ("hops1", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd', 'weight', 9999, 1) YIELD path, totalCost RETURN path, totalCost"),
                 ("sideways", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd', 'weight', 9999, 10, 'sideways') YIELD path RETURN path"),
                 ("wp_cost", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('a', 'd', 'cost') YIELD path RETURN path"),
                 ("empty_both", "USE GRAPH 'g' CALL ivg.shortestPath.weighted('', '') YIELD path RETURN path"),
                 ("nograph", "CALL ivg.shortestPath.weighted('a', 'b') YIELD path, totalCost RETURN path, totalCost")):
        try:
            r = e.execute_cypher(q)
            CALL[k] = {"rows": [list(x) for x in r.rows], "err": str(r.error) if getattr(r, "error", None) else None}
        except Exception as x:
            CALL[k] = f"EXC {type(x).__name__}: {str(x)[:200]}"
    out["dijkstra"] = DJ; out["call"] = CALL
    # ---- backfill_temporal_rows
    BF = {}
    T = 1_700_000_000
    e.create_edge_temporal("ta", "T", "tb", timestamp=T, weight=2.0, graph="g")
    e.create_edge_temporal("ta", "T", "tb", timestamp=T + 1, weight=3.0, graph="g")
    e.create_edge_temporal("tc", "T", "td", timestamp=T, graph="g")
    e.create_edge_temporal("ua", "T", "ub", timestamp=T)                 # default graph
    e.set_temporal_structural("TO", False, graph="g")
    e.create_edge_temporal("oa", "TO", "ob", timestamp=T, graph="g")     # temporal-only
    def rows():
        cur.execute("SELECT graph_id, s, p, o_id, qualifiers FROM Graph_KG.rdf_edges WHERE p IN ('T', 'TO') ORDER BY graph_id, s")
        return [list(r) for r in cur.fetchall()]
    BF["rows_before"] = rows()
    BF["first"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()")
    BF["rows_after_first"] = rows()
    BF["second"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()")
    cur.execute("DELETE FROM Graph_KG.rdf_edges WHERE graph_id = 'g' AND s = 'tc' AND p = 'T'")
    BF["rows_after_delete"] = rows()
    BF["kg_after_delete"] = q1(cur, "SELECT Graph_KG.MatchEdges('tc','T',0,'g')")
    BF["third"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()")
    BF["rows_after_third"] = rows()
    BF["kg_after_third"] = q1(cur, "SELECT Graph_KG.MatchEdges('tc','T',0,'g')")
    # an explicit (unmarked) row for a triple that also has a timestamp
    e.create_edge("ea", "T", "eb", graph="g")
    e.create_edge_temporal("ea", "T", "eb", timestamp=T, graph="g")
    BF["fourth"] = q1(cur, "SELECT Graph_KG.backfill_temporal_rows()")
    BF["rows_after_fourth"] = rows()
    out["backfill"] = BF
    # ---- rebuild_edge_indices
    RB = {}
    RB["count_before"] = q1(cur, "SELECT COUNT(*) FROM Graph_KG.rdf_edges")
    RB["ok"] = q1(cur, "SELECT Graph_KG.rebuild_edge_indices('Graph_KG')")
    RB["lower"] = q1(cur, "SELECT Graph_KG.rebuild_edge_indices('graph_kg')")
    RB["default_arg"] = q1(cur, "SELECT Graph_KG.rebuild_edge_indices()")
    RB["not_identifier"] = q1(cur, "SELECT Graph_KG.rebuild_edge_indices('Graph_KG; DROP')")
    RB["no_such_schema"] = q1(cur, "SELECT Graph_KG.rebuild_edge_indices('NoSuchSchema')")
    RB["count_after"] = q1(cur, "SELECT COUNT(*) FROM Graph_KG.rdf_edges")
    RB["kg_after"] = q1(cur, "SELECT Graph_KG.MatchEdges('a','P',0,'g')")
    out["rebuild"] = RB
    # ---- privileges
    make_users(cur)
    PR = {}
    try:
        for u in USERS:
            cu = connect(u, PW); k = cu.cursor()
            PR[u] = {
                "matchedges": q1(k, "SELECT Graph_KG.MatchEdges('a','P',0,'g')"),
                "matchedges_all": q1(k, "SELECT Graph_KG.MatchEdgesAllGraphs('a','P',0)"),
                "dijkstra": q1(k, "SELECT Graph_KG.DijkstraPath('a','d','',9999,10,'out','','g')"),
                "dijkstra_same": q1(k, "SELECT Graph_KG.DijkstraPath('a','a','',9999,10,'out','','g')"),
                "backfill": q1(k, "SELECT Graph_KG.backfill_temporal_rows()"),
                "rebuild": q1(k, "SELECT Graph_KG.rebuild_edge_indices('Graph_KG')"),
            }
            cu.close()
    finally:
        out["users_dropped"] = drop_users()
    out["privileges"] = PR
    out["elapsed_s"] = round(time.time() - t0, 1)
    c.close()
    path = HERE / f"sqlprocs-observed-{RUN}.json"
    path.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(path)


if __name__ == "__main__":
    main()
