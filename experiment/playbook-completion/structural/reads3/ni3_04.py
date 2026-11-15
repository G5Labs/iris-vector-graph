"""reads3 cases, module 04 (adjacency index, degree cache, rebuilt stores).

Declared footprint of each action: the stores footprints/04.json lists for the entry point, restricted to the graph
the call names (SYS-I2: an answer about graph g reads only g's data). Entry points whose footprint is every graph by
their own documentation (EdgeScan.MatchEdgesAllGraphs, DeleteAdjacencyAllGraphs, BulkDeleteAdjacency, WarmCache, the
namespace counters) are checked against perturbations of stores they do not declare; ^NKG has no graph dimension
(Adjacency.cls:94, NKGAccel.cls:213-223), so for its maintenance and build methods named-graph edges are inside.

For a writer the answer is its outcome and the target graph's state afterwards (rows of the four content tables in
that graph and its ^KG out/in/label/gen/degc/deg2p subtrees); for an every-graph writer, the declared target's
entries in every graph and whether anything else changed.
"""
from __future__ import annotations

import json
import os
import subprocess

import ni3core as K
from ni3core import C3, G1, G2, NI, cm, cmv, multi

put = NI.put
SERVER_FILE = "/tmp/ivgauditd-rd3-edges.json"


def og(g):
    return NI.other_graphs(g)


def base(g):
    return NI.base_in(g)


def sync(e, c):
    e.sync()


def ins_edge(g):
    return lambda e, c: (e.create_node("e", graph=g), e.create_edge("a", "T", "e", graph=g), e.create_edge("e", "R", "c", graph=g))


def props_and_loners_everywhere(e, c):
    """Content no adjacency store holds: labelled and edgeless nodes with properties, in every graph."""
    for g in (None, G1, G2):
        e.create_node("lz1", labels=["Z"], properties={"k": "z"}, graph=g)
        e.create_node("lz2", graph=g)


def props_and_loners_except(target):
    """props_and_loners_everywhere in every graph but the target (whose rows are the answer)."""
    def f(e, c):
        for g in (None, G1, G2):
            if g == target:
                continue
            e.create_node("lz1", labels=["Z"], properties={"k": "z"}, graph=g)
            e.create_node("lz2", graph=g)
    return f


def same_edge_elsewhere(s, p, o, gs=(None, G2)):
    return lambda e, c: [put(e, x, {s: ([], {}), o: ([], {})}, [(s, p, o)]) for x in gs]


def W(fn, g=G1):
    """A writer's answer: its outcome and graph g's state afterwards."""
    def f(e, c):
        try:
            r = K.parse(fn(e, c))
            err = None
        except Exception as ex:  # noqa: BLE001
            r, err = None, K.errtext(ex)
            try:
                c.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        try:
            c.conn.commit()
        except Exception:  # noqa: BLE001
            pass
        return {"result": r, "error": err, "state": K.gstate(c, g)}
    return f


def kg_all(c):
    """Every graph's ^KG out/in entries as tuples."""
    out = []
    for sub in ("out", "in"):
        for row in K.walk(c, "^KG", sub):
            out.append(tuple(row))
    return set(out)


def every_graph_writer(fn, touches):
    """An every-graph writer: what is left of its declared target (in every graph) and whether any other ^KG out/in
    entry changed. touches(row) says whether an entry belongs to the declared target."""
    def f(e, c):
        before = kg_all(c)
        try:
            r = K.parse(fn(e, c))
            err = None
        except Exception as ex:  # noqa: BLE001
            r, err = None, K.errtext(ex)
        c.conn.commit()
        after = kg_all(c)
        return {"result": r, "error": err, "target_left": sorted(map(list, (x for x in after if touches(x)))),
                "other_entries_changed": sorted(map(list, (before ^ after) - {x for x in (before | after) if touches(x)}))}
    return f


def keyed_row(g, s, p, o, ekey):
    """A parallel edge: one more rdf_edges row of the triple under another ekey (SQL, the table's own writer path;
    the adjacency functional index maintains ^KG from it, AdjIndex.cls:1-8)."""
    def f(e, c):
        cur = c.conn.cursor()
        cur.execute("INSERT INTO Graph_KG.rdf_edges (s, p, o_id, graph_id, ekey) VALUES (?, ?, ?, ?, ?)", [s, p, o, g or "", ekey])
        cur.close()
    return f


def multigraph(g, s, p, o, keys):
    def f(e, c):
        e.set_multigraph(g, True)
        put(e, g, {s: ([], {}), o: ([], {})}, [(s, p, o)])
        for k in keys:
            keyed_row(g, s, p, o, k)(e, c)
    return f


def multi_base(g):
    """Graph g in multigraph mode with two rows of a-R-b (ekeys 0 and 1)."""
    def f(e, c):
        e.set_multigraph(g, True)
        NI.base_in(g)(e, c)
        keyed_row(g, "a", "R", "b", 1)(e, c)
    return f


def multi_elsewhere(e, c):
    for x in (None, G2):
        multigraph(x, "a", "R", "b", (1, 2, 5))(e, c)


def ekeys(c, g, s, p, o):
    return sorted(int(r[0]) for r in NI.hsql(c, "SELECT ekey FROM Graph_KG.rdf_edges WHERE s = ? AND p = ? AND o_id = ? AND COALESCE(graph_id,'') = ?", s, p, o, g or ""))


def next_sources(g):
    def f(e, c):
        out, s = [], ""
        for _ in range(50):
            s = c.o.classMethodValue("Graph.KG.Adj", "NextSource", g, s)
            if s is None or str(s) == "":
                break
            s = str(s)
            out.append(s)
        return out
    return f


def degc(g, src=None):
    return lambda e, c: K.walk(c, "^KG", "degc", K.gkey(g), *([src] if src else []))


def temporal_row(g, s="a", p="T", o="c"):
    return lambda e, c: str(c.o.classMethodValue("Graph.KG.Adjacency", "AssertTemporalRow", K.gkey(g), s, p, o, "2", 1))


def root_set(*triples):
    def f(e, c):
        for s, p, o in triples:
            c.o.set("", K.ROOTG, s, p, o)
    return f


def docker_rm(path):
    subprocess.run(["docker", "exec", os.environ["IVG_TEST_CONTAINER"], "rm", "-f", path], capture_output=True, timeout=60)


def server_file(e, c):
    docker_rm(SERVER_FILE)
    c.o.classMethodVoid("Graph.KG.Snapshot", "WriteFileChunk", SERVER_FILE,
                        json.dumps([{"s": "a", "o": "q"}, {"s": "q", "o": "b"}]), 0)


def ingest_file(e, c):
    try:
        return c.o.classMethodValue("Graph.KG.EdgeScan", "BulkIngestEdgesFile", SERVER_FILE, "KNOWS")
    finally:
        docker_rm(SERVER_FILE)


def nkg_ids(names):
    return lambda e, c: {n: str(c.o.classMethodValue("Graph.KG.GraphIndex", "GetNodeIdx", n)) for n in names}


def graphindex_call(e, c):
    out = {}
    o = c.o
    out["cls:Graph.KG.GraphIndex.GetNodeIdx"] = {n: str(o.classMethodValue("Graph.KG.GraphIndex", "GetNodeIdx", n)) for n in ("a", "b", "c", "q1", "lz1")}
    out["cls:Graph.KG.GraphIndex.GetLabelIdx"] = {n: str(o.classMethodValue("Graph.KG.GraphIndex", "GetLabelIdx", n)) for n in ("R", "S", "Q1", "Z")}
    out["cls:Graph.KG.GraphIndex.InternNode"] = {n: str(o.classMethodValue("Graph.KG.GraphIndex", "InternNode", n)) for n in ("a", "q1")}
    out["cls:Graph.KG.GraphIndex.InternLabel"] = {n: str(o.classMethodValue("Graph.KG.GraphIndex", "InternLabel", n)) for n in ("R", "Q1")}
    sidx = o.classMethodValue("Graph.KG.GraphIndex", "GetNodeIdx", "a")
    pidx = o.classMethodValue("Graph.KG.GraphIndex", "GetLabelIdx", "R")
    oidx = o.classMethodValue("Graph.KG.GraphIndex", "GetNodeIdx", "q1")
    o.classMethodVoid("Graph.KG.GraphIndex", "UpdateStructuralHLL", sidx, pidx, oidx)
    out["cls:Graph.KG.GraphIndex.UpdateStructuralHLL"] = K.walk(c, "^NKG", "$agg", sidx, pidx)
    o.classMethodValue("Graph.KG.GraphIndex", "DeleteIndex", "", "a", "R", "b", "")
    out["cls:Graph.KG.GraphIndex.DeleteIndex"] = K.nkg_named(c)
    o.classMethodVoid("Graph.KG.GraphIndex", "InitStructuralLabels")
    out["cls:Graph.KG.GraphIndex.InitStructuralLabels"] = K.walk(c, "^NKG", "$LS")
    o.classMethodVoid("Graph.KG.GraphIndex", "DropNKG")
    out["cls:Graph.KG.GraphIndex.DropNKG"] = {"nkg_after": K.nkg_named(c), "defined": [r for r in K.walk(c, "^NKG") if r[:2] != ["$meta", "version"]]}
    return out


def algocache_call(e, c):
    """AlgoCache: Token as an offset from the token the setup left; Lookup/Get of G1's entry; the store's
    _cached_algorithm answering G1's call from it (compute must not run)."""
    o = c.o
    t_now = int(o.classMethodValue("Graph.KG.AlgoCache", "Token"))
    t_ref = int(c.o.get("^IVGAuditDRd3X", "token"))
    out = {"cls:Graph.KG.AlgoCache.Token": t_now - t_ref,
           "cls:Graph.KG.AlgoCache.Lookup": [str(o.classMethodValue("Graph.KG.AlgoCache", "Lookup", G1, "wcc", "h1")),
                                              str(o.classMethodValue("Graph.KG.AlgoCache", "Lookup", G1, "wcc", "h2"))],
           "cls:Graph.KG.AlgoCache.Get": [str(o.classMethodValue("Graph.KG.AlgoCache", "Get", G1, "wcc", "h1")),
                                           str(o.classMethodValue("Graph.KG.AlgoCache", "Get", G1, "pagerank", "h1"))]}
    st = e._store
    ran = []

    def compute():
        from iris_vector_graph.result import IVGResult as R
        ran.append(1)
        return R(columns=["id"], rows=[["computed"]])
    r = st._cached_algorithm("wcc", G1, {"p": 1}, ["id"], compute)
    out["py:iris_vector_graph.stores.iris_sql_store.IRISGraphStore._cached_algorithm"] = {"rows": r.rows, "computed": bool(ran)}
    return out


def algocache_prep(e, c):
    """Entries for G1 put at the token current after base + perturbation; the token recorded for Token's offset."""
    from iris_vector_graph import algo_cache
    tok = int(c.o.classMethodValue("Graph.KG.AlgoCache", "Token"))
    c.o.set(str(tok), "^IVGAuditDRd3X", "token")
    c.o.classMethodValue("Graph.KG.AlgoCache", "Put", G1, "wcc", "h1", tok, '[["g1-answer"]]')
    c.o.classMethodValue("Graph.KG.AlgoCache", "Put", G1, "wcc", algo_cache.param_hash({"p": 1}), tok, '[["g1-cached"]]')


def algocache_outside(e, c):
    """Other graphs' entries under the same algorithm and hashes, and their data."""
    from iris_vector_graph import algo_cache
    NI.other_graphs(G1)(e, c)
    c.conn.commit()
    tok = int(c.o.classMethodValue("Graph.KG.AlgoCache", "Token"))
    for g in ("", G2):
        c.o.classMethodValue("Graph.KG.AlgoCache", "Put", g, "wcc", "h1", tok, '[["other"]]')
        c.o.classMethodValue("Graph.KG.AlgoCache", "Put", g, "wcc", "h2", tok, '[["other-h2"]]')
        c.o.classMethodValue("Graph.KG.AlgoCache", "Put", g, "wcc", algo_cache.param_hash({"p": 1}), tok, '[["other"]]')


def algocache_inside(e, c):
    """G1's own entries for (wcc, h2) and (pagerank, h1) at the current token."""
    tok = int(c.o.classMethodValue("Graph.KG.AlgoCache", "Token"))
    c.o.classMethodValue("Graph.KG.AlgoCache", "Put", G1, "wcc", "h2", tok, '[["g1-h2"]]')
    c.o.classMethodValue("Graph.KG.AlgoCache", "Put", G1, "pagerank", "h1", tok, '[["g1-pr"]]')


def status_adjacency(e, c):
    st = e.status()
    d = NI.raw(st.adjacency)
    return d


def verify_sync_call(e, c):
    r = NI.raw(e.verify_sync())
    return K.mask3(NI.mask(r))


def api_call(method, path):
    def f(e, c):
        from starlette.testclient import TestClient
        import iris_vector_graph.cypher_api as api
        api._engine_cache = K.engine(c)
        try:
            with TestClient(api.app) as tc:
                r = tc.request(method, path)
        finally:
            api._engine_cache = None
        body = r.text
        try:
            body = r.json()
        except Exception:  # noqa: BLE001
            body = [ln for ln in r.text.splitlines() if not ln.startswith("ivg_status_probe_ms")]
        if isinstance(body, dict):
            body.pop("probe_ms", None)
            body.pop("iris_version", None)
            body.pop("ivg_version", None)
        return {"status": r.status_code, "body": body}
    return f


def api_then_state(method, path, g=G1):
    def f(e, c):
        r = api_call(method, path)(e, c)
        return {"response": r, "state": K.gstate(c, g)}
    return f


def cases():
    L = []
    M = "04"
    # ---------------------------------------------------------------- Adj readers and the per-graph degree cache
    for g, gname in ((G1, "G1"), (None, "default")):
        k = K.gkey(g)
        spec = [
            ("cls:Graph.KG.Adj.Count", lambda e, c, k=k: [int(c.o.classMethodValue("Graph.KG.Adj", "Count", k, s, p)) for s, p in (("a", ""), ("a", "R"), ("b", ""), ("d", ""))]),
            ("cls:Graph.KG.Adj.HasEdges", lambda e, c, k=k: [int(c.o.classMethodValue("Graph.KG.Adj", "HasEdges", k, s, p)) for s, p in (("a", ""), ("a", "S"), ("c", ""), ("d", ""))]),
            ("cls:Graph.KG.Adj.NextSource", next_sources(k)),
            ("cls:Graph.KG.Adj.Cached", lambda e, c, k=k: [str(c.o.classMethodValue("Graph.KG.Adj", "Degree", k, "a", ""))] +
             [str(c.o.classMethodValue("Graph.KG.Adj", "Cached", k, s, p)) for s, p in (("a", ""), ("a", "R"), ("b", ""))]),
            ("cls:Graph.KG.Adj.WarmFill", lambda e, c, k=k, g=g: {"stored": int(c.o.classMethodValue("Graph.KG.Adj", "WarmFill", k, "b")), "degc_b": degc(g, "b")(e, c)}),
            ("cls:Graph.KG.Adj.WarmAll", lambda e, c, k=k, g=g: {"filled": int(c.o.classMethodValue("Graph.KG.Adj", "WarmAll", k)), "degc": degc(g)(e, c)}),
            ("cls:Graph.KG.Adj.AllWarm", lambda e, c, k=k: int(c.o.classMethodValue("Graph.KG.Adj", "AllWarm", k))),
        ]
        L.append(C3(M, f"Adj readers and degree-cache fill, graph {gname}", multi(spec), base(g),
                    f"graph {gname}'s ^KG out/degc/gen (and ^KG(\"__version\") for the warm stamp): Adj.cls:93-250",
                    {"same ids and other edges in the other graphs": og(g)}, inside=ins_edge(g)))
    # every-graph cache fills: the answer is G1's cache afterwards (the return value counts every graph, declared)
    for entry, call in (("cls:Graph.KG.Adj.WarmCache", cm("Graph.KG.Adj", "WarmCache")),
                        ("cls:Graph.KG.Adjacency.EndRebuild", cm("Graph.KG.Adjacency", "EndRebuild", 1)),
                        ("cls:Graph.KG.TraversalBuild.BackfillDegp", cm("Graph.KG.TraversalBuild", "BackfillDegp"))):
        L.append(C3(M, f"{entry.split(':')[1]}: G1's degree cache afterwards", multi([(entry, lambda e, c, call=call: (call(e, c), {"degc": degc(G1)(e, c), "degw": bool(int(c.o.isDefined("^KG", "degw", G1)))})[1])]),
                    base(G1), "every graph's ^KG out (Adj.cls:220-230 'WarmAll' per graph); G1's entries come from G1's out",
                    {"same ids and other edges in the other graphs": og(G1)}, inside=ins_edge(G1)))
    # ---------------------------------------------------------------- the one writer (graph-scoped), outcome + G1 state
    wr = [
        ("cls:Graph.KG.Adjacency.Put", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "Put", G1, "a", "R", "d", "2"), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "the same edge a-R-d in the other graphs": same_edge_elsewhere("a", "R", "d")}),
        ("cls:Graph.KG.EdgeScan.WriteAdjacency", lambda e, c: c.o.classMethodVoid("Graph.KG.EdgeScan", "WriteAdjacency", "a", "R", "d", "2", G1), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "the same edge a-R-d in the other graphs": same_edge_elsewhere("a", "R", "d")}),
        ("cls:Graph.KG.Adjacency.PutShadow", lambda e, c: [c.o.classMethodValue("Graph.KG.Adjacency", "PutShadow", G1, "a", "R", x, "3") for x in ("b", "d")], base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same edges in the other graphs": same_edge_elsewhere("a", "R", "d")}),
        ("cls:Graph.KG.Adjacency.Remove", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "Remove", G1, "a", "R", "b"), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "the same edge a-R-b in the other graphs (HeldElsewhere)": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.EdgeScan.DeleteAdjacency", lambda e, c: c.o.classMethodVoid("Graph.KG.EdgeScan", "DeleteAdjacency", "a", "R", "b", G1), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "the same edge a-R-b in the other graphs (HeldElsewhere)": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.Reweight", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "Reweight", G1, "a", "R", "b", "4"), base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same edge a-R-b in the other graphs": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.RemoveSource", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RemoveSource", G1, "a"), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "a's edges in the other graphs": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.RemoveNode", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RemoveNode", G1, "b"), base(G1), sync,
         {"same ids and other edges in the other graphs": og(G1), "b's edges in the other graphs": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.RowPut", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RowPut", G1, "a", "R", "d", '{"weight":2}', ""), base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same edge in the other graphs": same_edge_elsewhere("a", "R", "d")}),
        ("cls:Graph.KG.Adjacency.RowRemove", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RowRemove", G1, "a", "R", "b", ""), base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same edge in the other graphs": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.RowUpdate", lambda e, c: [c.o.classMethodValue("Graph.KG.Adjacency", "RowUpdate", G1, "a", "R", "b", '{"weight":5}', "0", G1, "a", "R", "b", "", "0"),
                                                          c.o.classMethodValue("Graph.KG.Adjacency", "RowUpdate", G1, "b", "S", "a", "", "0", G1, "b", "R", "c", "", "0")], base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same edges in the other graphs": same_edge_elsewhere("a", "R", "b")}),
        ("cls:Graph.KG.Adjacency.AssertTemporalRow", temporal_row(G1), base(G1), None,
         {"same ids and other edges in the other graphs": og(G1), "the same temporal row in the other graphs": lambda e, c: [temporal_row(x)(e, c) for x in (None, G2)]}),
        ("cls:Graph.KG.Adjacency.RetractTemporalRow", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RetractTemporalRow", G1, "a", "T", "c"),
         lambda e, c: (base(G1)(e, c), temporal_row(G1)(e, c)), None,
         {"same ids and other edges in the other graphs": og(G1), "the same temporal row in the other graphs": lambda e, c: [temporal_row(x)(e, c) for x in (None, G2)]}),
        ("cls:Graph.KG.Adjacency.RetractTemporalRows", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RetractTemporalRows", G1, K.ROOTG),
         lambda e, c: (base(G1)(e, c), temporal_row(G1)(e, c), root_set(("a", "T", "c"))(e, c)), None,
         {"same ids and other edges in the other graphs": og(G1), "the same temporal row in the other graphs": lambda e, c: [temporal_row(x)(e, c) for x in (None, G2)]}),
        ("cls:Graph.KG.Adjacency.RetractTemporalShadows", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RetractTemporalShadows", G1, K.ROOTG),
         lambda e, c: (base(G1)(e, c), c.o.classMethodValue("Graph.KG.Adjacency", "Put", G1, "a", "T", "c", "1"), root_set(("a", "T", "c"), ("a", "R", "b"))(e, c)), None,
         {"same ids and other edges in the other graphs": og(G1), "rows of a-T-c in the other graphs": lambda e, c: [temporal_row(x)(e, c) for x in (None, G2)]}),
        ("cls:Graph.KG.Adjacency.WriterLock", lambda e, c: {"granted": c.o.classMethodValue("Graph.KG.Adjacency", "WriterLock", G1, "audit"),
                                                            "nolock": K.walk(c, "^IVG.AdjNoLock", G1)}, base(G1), None,
         {"same ids and other edges in the other graphs": og(G1)}),
    ]
    for entry, call, b, prep, outside in wr:
        L.append(C3(M, f"{entry.split(':')[1]} on G1: outcome and G1 state", multi([(entry, W(call))]), b,
                    "G1's ^KG entries of the edge/node named (Adjacency.cls; footprints/04.json reads); ^NKG reads are per identifier "
                    "(no graph dimension, Adjacency.cls:94)", outside, inside=ins_edge(G1), prep=prep))
    # multigraph writers (keyed)
    kw = [
        ("cls:Graph.KG.Adjacency.PutKeyed", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "PutKeyed", G1, "a", "R", "b", 7, "2.5")),
        ("cls:Graph.KG.EdgeScan.WriteAdjacencyKeyed", lambda e, c: c.o.classMethodValue("Graph.KG.EdgeScan", "WriteAdjacencyKeyed", "a", "R", "b", "2.5", G1, 7)),
        ("cls:Graph.KG.Adjacency.RemoveKeyed", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RemoveKeyed", G1, "a", "R", "b", max(ekeys(c, G1, "a", "R", "b")))),
        ("cls:Graph.KG.EdgeScan.DeleteAdjacencyKeyed", lambda e, c: c.o.classMethodValue("Graph.KG.EdgeScan", "DeleteAdjacencyKeyed", "a", "R", "b", G1, max(ekeys(c, G1, "a", "R", "b")))),
        ("cls:Graph.KG.Adjacency.RowPut#multigraph", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RowPut", G1, "a", "R", "b", '{"weight":3}', "9")),
        ("cls:Graph.KG.Adjacency.RowRemove#multigraph", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RowRemove", G1, "a", "R", "b", str(max(ekeys(c, G1, "a", "R", "b"))))),
        ("cls:Graph.KG.Adjacency.RowUpdate#multigraph", lambda e, c: c.o.classMethodValue("Graph.KG.Adjacency", "RowUpdate", G1, "a", "R", "b", '{"weight":6}', str(max(ekeys(c, G1, "a", "R", "b"))),
                                                                                         G1, "a", "R", "b", "", str(max(ekeys(c, G1, "a", "R", "b"))))),
    ]
    for entry, call in kw:
        L.append(C3(M, f"{entry.split(':')[1]} on multigraph G1 (two a-R-b rows): outcome and G1 state", multi([(entry, W(call))]),
                    lambda e, c: (multi_base(G1)(e, c)), "G1's rows of the triple (OtherEdgeKeys, Adjacency.cls:886-902, scoped by graph_id) and G1's ^KG entries of the triple",
                    {"same ids and other edges in the other graphs": og(G1), "the same triple, several rows, in other multigraphs": multi_elsewhere},
                    inside=keyed_row(G1, "a", "R", "b", 3)))
    # the functional index's hooks (AdjIndex Insert/Update/DeleteIndex -> RowPut/RowUpdate/RowRemove) through SQL DML
    def dml(e, c):
        cur = c.conn.cursor()
        out = {}
        cur.execute("INSERT INTO Graph_KG.rdf_edges (s, p, o_id, graph_id) VALUES ('a', 'T', 'c', ?)", [G1])
        c.conn.commit()
        out["cls:Graph.KG.AdjIndex.InsertIndex"] = K.gstate(c, G1)["kg"]
        cur.execute("UPDATE Graph_KG.rdf_edges SET qualifiers = '{\"weight\":3}' WHERE s = 'a' AND p = 'T' AND o_id = 'c' AND graph_id = ?", [G1])
        c.conn.commit()
        out["cls:Graph.KG.AdjIndex.UpdateIndex"] = K.gstate(c, G1)["kg"]
        cur.execute("DELETE FROM Graph_KG.rdf_edges WHERE s = 'a' AND p = 'R' AND o_id = 'b' AND graph_id = ?", [G1])
        c.conn.commit()
        out["cls:Graph.KG.AdjIndex.DeleteIndex"] = K.gstate(c, G1)["kg"]
        cur.close()
        return out
    L.append(C3(M, "SQL INSERT/UPDATE/DELETE on rdf_edges in G1 (AdjIndex functional-index hooks): G1's ^KG after each", dml, base(G1),
                "the row written and G1's ^KG entries of its triple (AdjIndex.cls:12-26 -> Adjacency.RowPut/RowUpdate/RowRemove)",
                {"same ids and other edges in the other graphs": og(G1), "a-T-c and a-R-b in the other graphs": lambda e, c: (same_edge_elsewhere("a", "T", "c")(e, c), same_edge_elsewhere("a", "R", "b")(e, c))},
                inside=ins_edge(G1)))
    # every-graph writers: the target in every graph, nothing else
    L.append(C3(M, "EdgeScan.DeleteAdjacencyAllGraphs(a, R, b): target left in every graph, other entries changed", multi([
        ("cls:Graph.KG.EdgeScan.DeleteAdjacencyAllGraphs", every_graph_writer(lambda e, c: c.o.classMethodVoid("Graph.KG.EdgeScan", "DeleteAdjacencyAllGraphs", "a", "R", "b"),
                                                                               lambda x: (x[0] == "out" and x[2:5] == ("a", "R", "b")) or (x[0] == "in" and x[2:5] == ("b", "R", "a"))))]),
        lambda e, c: (base(G1)(e, c), same_edge_elsewhere("a", "R", "b")(e, c)),
        "the triple's out/in entries in every graph (EdgeScan.cls:190-225)",
        {"other triples in every graph": lambda e, c: [put(e, x, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y"), ("a", "S", "x")]) for x in (None, G1, G2)]},
        inside=lambda e, c: e.create_edge("b", "R", "a", graph=G2)))
    L.append(C3(M, "EdgeScan.BulkDeleteAdjacency([b]): b's entries left in every graph, other entries changed", multi([
        ("cls:Graph.KG.EdgeScan.BulkDeleteAdjacency", every_graph_writer(lambda e, c: c.o.classMethodValue("Graph.KG.EdgeScan", "BulkDeleteAdjacency", '["b"]'),
                                                                           lambda x: "b" in x[2:5]))]),
        lambda e, c: (base(G1)(e, c), same_edge_elsewhere("a", "R", "b")(e, c)),
        "node b's out/in entries in every graph (EdgeScan.cls:432-472)",
        {"other nodes' edges in every graph": lambda e, c: [put(e, x, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y"), ("a", "S", "x")]) for x in (None, G1, G2)]},
        inside=lambda e, c: e.create_edge("c", "R", "b", graph=G2)))
    L.append(C3(M, "engine.bulk_delete_adjacency([b]) (every graph's rows of b's edges): b's entries left, other entries changed", multi([
        ("py:IRISGraphEngine.bulk_delete_adjacency", every_graph_writer(lambda e, c: e.bulk_delete_adjacency(["b"]), lambda x: "b" in x[2:5]))]),
        lambda e, c: (base(G1)(e, c), same_edge_elsewhere("a", "R", "b")(e, c)),
        "every graph's rdf_edges rows with b as source or target (nodes_edges.py:2301-2339)",
        {"other nodes' edges in every graph": lambda e, c: [put(e, x, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y"), ("a", "S", "x")]) for x in (None, G1, G2)]},
        inside=lambda e, c: e.create_edge("c", "R", "b", graph=G2)))
    # default-graph bulk writers
    L.append(C3(M, "EdgeScan.RegisterDefaultNode(zz / a): result and the default graph's rows", multi([
        ("cls:Graph.KG.EdgeScan.RegisterDefaultNode", W(lambda e, c: [c.o.classMethodValue("Graph.KG.EdgeScan", "RegisterDefaultNode", n) for n in ("zz", "a")], g=None))]),
        base(None), "the default graph's nodes row of the id (EdgeScan.cls:247-258)",
        {"zz and a in the named graphs": lambda e, c: [put(e, x, {"zz": ([], {}), "a": ([], {})}, []) for x in (G1, G2)]},
        inside=lambda e, c: e.create_node("zz", labels=["Q"])))
    L.append(C3(M, "EdgeScan.BulkIngestEdgesSQL([a->q, q->b], KNOWS): result and the default graph's state", multi([
        ("cls:Graph.KG.EdgeScan.BulkIngestEdgesSQL", W(lambda e, c: c.o.classMethodValue("Graph.KG.EdgeScan", "BulkIngestEdgesSQL", json.dumps([{"s": "a", "o": "q"}, {"s": "q", "o": "b"}]), "KNOWS"), g=None))]),
        base(None), "the default graph's rows of the endpoints and edges (EdgeScan.cls:260-313)",
        {"same ids and other edges in the named graphs": og(None), "the same KNOWS edges in the named graphs": lambda e, c: [put(e, x, {"a": ([], {}), "q": ([], {}), "b": ([], {})}, [("a", "KNOWS", "q"), ("q", "KNOWS", "b")]) for x in (G1, G2)]},
        inside=lambda e, c: e.create_node("q", labels=["Z"])))
    L.append(C3(M, "EdgeScan.BulkIngestEdgesFile(server file [a->q, q->b], KNOWS): result and the default graph's state", multi([
        ("cls:Graph.KG.EdgeScan.BulkIngestEdgesFile", W(ingest_file, g=None))]),
        lambda e, c: (base(None)(e, c), server_file(e, c)), "the named file and the default graph's rows (EdgeScan.cls:315-324 -> BulkIngestEdgesSQL)",
        {"same ids and other edges in the named graphs": og(None), "the same KNOWS edges in the named graphs": lambda e, c: [put(e, x, {"a": ([], {}), "q": ([], {}), "b": ([], {})}, [("a", "KNOWS", "q"), ("q", "KNOWS", "b")]) for x in (G1, G2)]},
        inside=lambda e, c: e.create_node("q", labels=["Z"])))
    L.append(C3(M, "EdgeScan.BulkIngestNodesSQL([a +Q k=v9, q]): result and the default graph's state", multi([
        ("cls:Graph.KG.EdgeScan.BulkIngestNodesSQL", W(lambda e, c: c.o.classMethodValue("Graph.KG.EdgeScan", "BulkIngestNodesSQL", json.dumps([{"id": "a", "labels": ["Q"], "props": {"k": "v9", "n": "1"}}, {"id": "q", "labels": ["L"], "props": {"k": "v1"}}])), g=None))]),
        base(None), "the default graph's nodes/labels/props rows of the ids (EdgeScan.cls:326-430)",
        {"same ids with labels/props in the named graphs": og(None), "q with a label and k in the named graphs": lambda e, c: [put(e, x, {"q": (["Q"], {"k": "zz", "n": "2"})}, []) for x in (G1, G2)]},
        inside=lambda e, c: e.create_node("q", labels=["Z"], properties={"k": "old"})))
    # ---------------------------------------------------------------- interned snapshot maintenance (^NKG, per identifier)
    L.append(C3(M, "GraphIndex: GetNodeIdx/GetLabelIdx/InternNode/InternLabel/UpdateStructuralHLL/DeleteIndex/InitStructuralLabels/DropNKG after sync",
                graphindex_call, NI.algo_base, "^NKG's dictionaries and edges (per identifier, no graph dimension: Adjacency.cls:94; GraphIndex.cls:22-186)",
                {"properties/labels and edgeless nodes in every graph": props_and_loners_everywhere}, inside=K.a_in,
                prep=sync, inside_declared={"edges in a named graph (^NKG merges every graph's edges: declared)": og(None)}))
    # ---------------------------------------------------------------- builders and counters
    def g1_after(fn):
        return lambda e, c: (fn(e, c), K.gstate(c, G1))[1]
    def mbase(e, c):
        NI.base_in(G1)(e, c)
        e.set_multigraph(G1, True)
        e.create_edge("a", "R", "b", graph=G1)
        e.create_edge("b", "R", "c", graph=G1)
    builders = [
        ("cls:Graph.KG.TraversalBuild.BuildKG", g1_after(cm("Graph.KG.TraversalBuild", "BuildKG"))),
        ("py:IRISGraphEngine.rebuild_kg", g1_after(lambda e, c: e.rebuild_kg())),
        ("py:IRISGraphEngine.sync", g1_after(lambda e, c: e.sync())),
        ("rest:POST /admin/indexes/rebuild", api_then_state("POST", "/admin/indexes/rebuild")),
    ]
    for entry, call in builders:
        L.append(C3(M, f"{entry.split(':', 1)[1]} over multigraph G1 and the other graphs: G1's state after", multi([(entry, call)]), mbase,
                    "every graph's rdf_edges/rdf_labels rows rebuild that graph's ^KG (TraversalBuild.cls:30-214); G1's ^KG from G1's rows",
                    {"same ids and other edges in the other graphs": og(G1), "labelled and edgeless nodes with properties in the other graphs": props_and_loners_except(G1)},
                    inside=ins_edge(G1)))
    nkgb = [
        ("cls:Graph.KG.TraversalBuild.BuildNKG", lambda e, c: (str(c.o.classMethodValue("Graph.KG.TraversalBuild", "BuildNKG")), K.nkg_named(c))[1]),
        ("py:IRISGraphEngine.rebuild_nkg", lambda e, c: (e.rebuild_nkg(), K.nkg_named(c))[1]),
        ("cls:Graph.KG.TraversalBuild.EnsureNKG", lambda e, c: (c.o.classMethodValue("Graph.KG.Adjacency", "Remove", G2, "x", "R", "y"),
                                                                str(c.o.classMethodValue("Graph.KG.TraversalBuild", "EnsureNKG")), K.nkg_named(c))[1:]),
    ]
    for entry, call in nkgb:
        L.append(C3(M, f"{entry.split(':', 1)[1]}: ^NKG afterwards (named)", multi([(entry, call)]),
                    lambda e, c: (NI.algo_base(e, c), put(e, G2, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y")]), e.sync()),
                    "every graph's ^KG out/in (^NKG merges every graph by design: Adjacency.cls:94, NKGAccel.cls:213-223)",
                    {"properties/labels and edgeless nodes in every graph": props_and_loners_everywhere},
                    inside=lambda e, c: (e.create_node("e"), e.create_edge("a", "R", "e")),
                    inside_declared={"edges in another named graph": og(None)}))
    L.append(C3(M, "TraversalBuild.InitNKGSkeleton on an empty ^NKG", multi([
        ("cls:Graph.KG.TraversalBuild.InitNKGSkeleton", lambda e, c: (str(c.o.classMethodValue("Graph.KG.TraversalBuild", "InitNKGSkeleton")), K.walk(c, "^NKG", "$LS"), K.nkg_named(c)["meta"]))]),
        NI.algo_base, "^NKG $meta and $LS only (TraversalBuild.cls:216-224)",
        {"same ids and edges in the named graphs": og(None), "properties/labels and edgeless nodes in every graph": props_and_loners_everywhere}))
    counters = [
        ("cls:Graph.KG.TraversalBuild.NKGEdgeCount", cm("Graph.KG.TraversalBuild", "NKGEdgeCount")),
        ("cls:Graph.KG.TraversalBuild.NKGNodeCount", cm("Graph.KG.TraversalBuild", "NKGNodeCount")),
        ("cls:Graph.KG.TraversalBuild.NKGLiveNodeCount", cm("Graph.KG.TraversalBuild", "NKGLiveNodeCount")),
        ("cls:Graph.KG.TraversalBuild.NKGPopulated", cm("Graph.KG.TraversalBuild", "NKGPopulated")),
        ("cls:Graph.KG.TraversalBuild.KGEdgeCount", cm("Graph.KG.TraversalBuild", "KGEdgeCount", 10000)),
        ("cls:Graph.KG.TraversalBuild.DictSweepAllowed", cm("Graph.KG.TraversalBuild", "DictSweepAllowed")),
        ("py:IRISGraphEngine.status", status_adjacency),
        ("rest:GET /server", api_call("GET", "/server")),
        ("rest:GET /metrics", api_call("GET", "/metrics")),
        ("py:IRISGraphEngine.verify_sync", verify_sync_call),
        ("py:iris_vector_graph.engine.IRISGraphEngine._adjacency_indexed", lambda e, c: e._adjacency_indexed),
    ]
    L.append(C3(M, "namespace counters and reports (every graph's adjacency, by declaration) after sync", multi(counters),
                lambda e, c: (NI.algo_base(e, c), put(e, G2, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y")])),
                "every graph's ^KG out / ^NKG $meta / rdf_edges counts (TraversalBuild.cls:226-247, 1071-1103; admin.py:396-411 'every graph's together')",
                {"node properties (rdf_props rows only) in two graphs": lambda e, c: [e.store_node(n, properties={"k": "v1", "extra": "x"}, graph=g) for g, n in ((None, "a"), (G2, "x"))],
                 "a non-product scratch global": lambda e, c: c.o.set("x", K.SCRATCH, "k")},
                inside=lambda e, c: (e.create_node("e"), e.create_edge("a", "R", "e")), prep=sync))
    for entry, store in (("cls:Graph.KG.TraversalBuild.Build2HopStats", "deg2p"), ("cls:Graph.KG.TraversalBuild.Build2HopExactStats", "deg2p_exact"),
                         ("py:IRISGraphEngine.backfill_deg2p_exact", "deg2p_exact"), ("py:IRISGraphEngine.backfill_2hop_exact", "deg2p_exact")):
        meth = entry.split(".")[-1]
        call = (cm("Graph.KG.TraversalBuild", meth) if entry.startswith("cls:") else (lambda e, c, m=meth: getattr(e, m)()))
        L.append(C3(M, f"{entry.split(':', 1)[1]}: G1's {store} afterwards", multi([(entry, lambda e, c, call=call, store=store: (call(e, c), K.walk(c, "^KG", store, G1))[1])]),
                    lambda e, c: (base(G1)(e, c), e.create_edge("c", "R", "a", graph=G1)),
                    f"every graph's ^KG out; G1's ^KG(\"{store}\", G1) from G1's out (TraversalBuild.cls:939-1067: 'The second hop stays inside graph g')",
                    {"same ids and other edges in the other graphs": og(G1)}, inside=ins_edge(G1)))
    # ---------------------------------------------------------------- readers
    L.append(C3(M, "AlgoCache Token/Lookup/Get and the store's _cached_algorithm, G1", algocache_call, base(G1),
                "^IVG.AlgoCache(G1 key, algorithm, hash) and ^KG(\"__version\") (AlgoCache.cls:18-43; iris_sql_store.py:921-988)",
                {"other graphs' entries under the same algorithm and hashes, and their data": algocache_outside},
                inside=algocache_inside, prep=algocache_prep))
    L.append(C3(M, "EdgeScan.MatchEdges (G1, default) and MatchEdgesAllGraphs", multi([
        ("cls:Graph.KG.EdgeScan.MatchEdges", lambda e, c: [K.parse(c.o.classMethodValue("Graph.KG.EdgeScan", "MatchEdges", s, p, 0, G1)) for s, p in (("a", ""), ("a", "R"), ("", "R"))]),
        ("cls:Graph.KG.EdgeScan.MatchEdges#default", lambda e, c: [K.parse(c.o.classMethodValue("Graph.KG.EdgeScan", "MatchEdges", s, p, 0, 0)) for s, p in (("a", ""), ("", "R"))]),
        ]), lambda e, c: (base(G1)(e, c), put(e, None, {"a": ([], {}), "q": ([], {})}, [("a", "R", "q")])),
        "^KG(out, graph) of the source/predicate (EdgeScan.cls:46-61, 93-147)",
        {"same ids and other edges in G2": lambda e, c: put(e, G2, NI.NOISE_NODES, NI.NOISE_EDGES)}, inside=ins_edge(G1)))
    L.append(C3(M, "EdgeScan.MatchEdgesAllGraphs(a, '' / R)", multi([
        ("cls:Graph.KG.EdgeScan.MatchEdgesAllGraphs", lambda e, c: [K.parse(c.o.classMethodValue("Graph.KG.EdgeScan", "MatchEdgesAllGraphs", "a", p)) for p in ("", "R")])]),
        lambda e, c: (base(G1)(e, c), put(e, G2, {"a": ([], {}), "q": ([], {})}, [("a", "R", "q")])),
        "a's ^KG out entries in every graph (EdgeScan.cls:62-84)",
        {"other sources' edges in every graph, properties": lambda e, c: [put(e, x, {"x": (["L"], {"k": "1"}), "y": ([], {})}, [("x", "R", "y"), ("b", "R", "x")]) for x in (None, G1, G2)]},
        inside=lambda e, c: e.create_edge("a", "S", "b", graph=G2)))
    L.append(C3(M, "verify_graph's class method and the loner readers, G1", multi([
        ("cls:Graph.KG.GraphVerify.VerifyGraph", lambda e, c: K.parse(c.o.classMethodValue("Graph.KG.GraphVerify", "VerifyGraph", G1))),
        ("py:iris_vector_graph._edgeless.loners", lambda e, c: __import__("iris_vector_graph._edgeless", fromlist=["loners"]).loners(c.o, "Graph_KG", G1)),
        ("py:iris_vector_graph._edgeless.loners_sql", lambda e, c: __import__("iris_vector_graph._edgeless", fromlist=["loners_sql"]).loners_sql(c.conn, "Graph_KG.nodes", "Graph_KG.rdf_edges", G1)),
        ("cls:Graph.KG.Edgeless.Loners (through SQL kg_DegreeCentrality, which calls it)", lambda e, c: K.parse(c.sql("SELECT Graph_KG.kg_DegreeCentrality('out', '', 100, ?)", G1)[0][0])),
        ]), lambda e, c: (base(G1)(e, c), e.create_node("z", graph=G1), e.create_node("y", graph=G1), e.create_edge("y", "R", "y", graph=G1)),
        "G1's nodes rows and ^KG out/in (Edgeless.cls:15-85; GraphVerify.cls:40-172; _edgeless.py:21-55)",
        {"same ids and other edges in the other graphs": og(G1),
         "z and y with edges in the other graphs": lambda e, c: [put(e, x, {"z": ([], {}), "y": ([], {}), "w": ([], {})}, [("z", "R", "w"), ("w", "R", "y")]) for x in (None, G2)]},
        inside=lambda e, c: e.create_edge("z", "R", "a", graph=G1)))
    return L
