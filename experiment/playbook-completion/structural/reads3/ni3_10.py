"""reads3 cases, module 10 (graph algorithms and traversal).

Declared footprint: the stores footprints/10.json lists for the entry point, restricted to the graph the call names;
a call that names no graph answers for the default graph alone (ALG-I3, 10-algorithms.md:45), a call with a graph
argument for that graph (ALG-I2). Entry points whose footprint is every graph by their own documentation keep it
(VarLength pAll=1, kg_NEIGHBORS/kg_MENTIONS: ALG-B9.10, the namespace counters, a Cypher CALL without USE GRAPH:
CONTEXT.md All-graphs read, test_460_r192 header). ^NKG holds every graph's edges with no graph key
(NKGAccel.cls:213-223): for the snapshot's own readers (export, counters, loader) a named graph's edges are inside;
for an algorithm that takes no graph they are outside (ALG-I3), which is how F-C1041 was established.
The ^NKG SQL functions and Cypher procedures refuse once a named graph has edges (ALG-B7, ALG-B7.2): for them that
perturbation is declared inside (the refusal reads which graphs hold edges, ALG-B7.5).
"""
from __future__ import annotations

import json

import ni3core as K
from ni3core import C3, G1, G2, NI, cm, cmv, multi

put = NI.put
algo_base = NI.algo_base
A_OUT = {"same ids and edges in the named graphs": NI.other_graphs(None)}


def og(g):
    return NI.other_graphs(g)


def sync(e, c):
    e.sync()


def g1_in(e, c):
    e.create_node("e", graph=G1)
    e.create_edge("a", "R", "e", graph=G1)
    e.create_edge("e", "R", "c", graph=G1)


def named_nodes_and_props(e, c):
    """No edge anywhere new: edgeless nodes with labels/properties in the named graphs, properties on the default
    graph's nodes (rdf_props only)."""
    for g in (G1, G2):
        put(e, g, {"a": (["N"], {"k": "z"}), "d": (["L"], {"k": "v1"}), "q": ([], {})}, [])
    for n in ("a", "b"):
        e.store_node(n, properties={"k": "v9", "extra": "x"})


def default_props(e, c):
    for n in ("a", "b"):
        e.store_node(n, properties={"k": "v9", "extra": "x"})


def bfs_out(reader):
    """Resolve a staged BFS answer: SORTED:<tag>:<n> through Traversal.ReadBFSResults, CHUNKED:<tag>:<n> through the
    method's own chunk reader, in the same process (the staging is the caller's)."""
    def f(c, v):
        s = str(v)
        if s.startswith("SORTED:"):
            parts = s.split(":")
            if len(parts) < 3 or parts[2] == "0" or parts[1] == "0":
                return {"sorted": []}
            return {"sorted": K.parse(str(c.o.classMethodValue("Graph.KG.TraversalBFS", "ReadBFSResults", parts[1])))}
        if s.startswith("CHUNKED:"):
            parts = s.split(":")
            if len(parts) < 3:
                return {"chunked": []}
            n = int(parts[-1])
            tag = ":".join(parts[1:-1])
            body = "".join(str(c.o.classMethodValue(*reader, tag, i) or "") for i in range(1, n + 1))
            return {"chunked": K.parse(body if body.startswith(("[", "{")) else "[" + body + "]")}
        return K.parse(v)
    return f


def staged(cls, meth, reader, *args):
    rd = bfs_out(reader)
    return lambda e, c: rd(c, c.o.classMethodValue(cls, meth, *args))


def khop_sorted(c, v):
    """KHopNeighborsSorted's SORTED:<tag>:<n>:<seed>:<k>, read back through NKGAccelAdjacency.ReadKHopResults(tag)."""
    s = str(v)
    if not s.startswith("SORTED:"):
        return K.parse(v)
    parts = s.split(":")
    body = str(c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "ReadKHopResults", parts[1]) or "")
    return {"count": parts[2], "rows": K.parse("[" + body + "]")}


def walk_nodes(cls):
    """A random walk's answer projected to the nodes visited beyond a, b, c (the walk itself is random)."""
    def f(e, c):
        raw = c.o.classMethodValue(cls, "RandomWalkJson", "a", 6, 20)
        v = bfs_out(("Graph.KG.NKGAccelAdjacency", "ReadLargeOutChunk"))(c, raw)
        v = v.get("chunked", v) if isinstance(v, dict) else v
        seen = {n for w in (v or []) for n in (w if isinstance(w, list) else [w])}
        return {"walked": bool(seen), "beyond_abc": sorted(seen - {"a", "b", "c"})}
    return f


def store(e):
    return e._store


def rows_of(r):
    return {"rows": NI.canon(NI.raw(getattr(r, "rows", r))), "error": getattr(r, "error", None)}


def cy(q):
    def f(e, c):
        r = e.execute_cypher(q)
        return {"rows": NI.canon([[NI.raw(x) for x in row] for row in (r.rows or [])]),
                "error": (K.DIGITS.sub("#", str(r.error))[:240] if r.error else None)}
    return f


def ppr_seed_rows(e, c):
    return str(c.o.classMethodValue("Graph.KG.PageRank", "RunJson", '["a"]', 0.85, 20, 0, 1.0, "", "", 1000))


def cases():
    L = []
    M = "10"
    T, TB, TK, TP, VL = "Graph.KG.Traversal", "Graph.KG.TraversalBFS", "Graph.KG.TraversalKHop", "Graph.KG.TraversalPaths", "Graph.KG.VarLength"
    CHUNK = (TB, "ReadBFSChunk")
    STREAM = (TB, "ReadLargeOutChunk")
    TSTREAM = (T, "ReadLargeOutChunk")
    # ------------------------------------------------------------ ^KG readers, the default graph (graph "" / no graph argument)
    for g, gname in ((None, "default"), (G1, "G1")):
        gs = g or ""
        spec = []
        for cls in (TB, T):
            spec += [
                (f"cls:{cls}.BFS", lambda e, c, cls=cls, gs=gs: K.parse(c.o.classMethodValue(cls, "BFSJSON" if False else "BFS", "a", "", 2, "", gs))),
                (f"cls:{cls}.BFSJSON", lambda e, c, cls=cls, gs=gs: K.parse(c.o.classMethodValue(cls, "BFSJSON", "a", "", 2, "", gs))),
                (f"cls:{cls}.BFSFast", lambda e, c, cls=cls, gs=gs: [int(c.o.classMethodValue(cls, "BFSFast", "a", "", 2, "", d, 0, gs)) for d in ("out", "in", "both")]),
                (f"cls:{cls}.BFSFastJson", lambda e, c, cls=cls, gs=gs: [K.parse(c.o.classMethodValue(cls, "BFSFastJson", "a", p, 2, "", d, gs)) for p, d in (("", "out"), ('["R"]', "out"), ("", "both"))]),
                (f"cls:{cls}.BFSFastJsonDirect", lambda e, c, cls=cls, gs=gs: [K.parse(c.o.classMethodValue(cls, "BFSFastJsonDirect", "a", p, 2, "", d, gs)) for p, d in (("", "out"), ("", "in"))]),
                (f"cls:{cls}.BFSFastJsonChunked", staged(cls, "BFSFastJsonChunked", CHUNK, "a", "", 2, "", "out", 0, gs)),
                (f"cls:{cls}.BFSFastStream", staged(cls, "BFSFastStream", STREAM if cls == TB else TSTREAM, "a", "", 2, "", "out", gs)),
                (f"cls:{cls}.ReadLargeOutChunk", staged(cls, "BFSFastStream", STREAM if cls == TB else TSTREAM, "b", "", 2, "", "both", gs)),
                (f"cls:{cls}.BFSFastJsonSorted", staged(cls, "BFSFastJsonSorted", CHUNK, "a", "", 2, "", "out", 0, gs, 1)),
                (f"cls:{cls}.BFSFastCountDistinct", lambda e, c, cls=cls, gs=gs: [int(c.o.classMethodValue(cls, "BFSFastCountDistinct", "a", "", 2, "", d, gs)) for d in ("out", "both")]),
            ]
        spec += [
            (f"cls:{TB}.ReachTypes", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(TB, "ReachTypes", '{"a":0,"b":1,"c":1}', "", "out", gs))),
            (f"cls:{TP}.ShortestPathJson", lambda e, c, gs=gs: [K.parse(c.o.classMethodValue(TP, "ShortestPathJson", "a", "c", 5, "", d, f, gs)) for d, f in (("out", 0), ("both", 1))]),
            (f"cls:{T}.ShortestPathJson", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(T, "ShortestPathJson", "a", "c", 5, "", "out", 0, gs))),
            (f"cls:{TP}.ShortestLength", lambda e, c, gs=gs: [int(c.o.classMethodValue(TP, "ShortestLength", "a", t, 5, "", "out", gs)) for t in ("c", "b", "d")]),
            (f"cls:{TP}.DijkstraJson", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(TP, "DijkstraJson", "a", "c", "", 9999, 10, "out", "", gs))),
            (f"cls:{T}.DijkstraJson", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(T, "DijkstraJson", "a", "c", "", 9999, 10, "out", "", gs))),
            (f"cls:{T}.DijkstraProc", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(T, "DijkstraProc", "a", "c", "", 9999, 10, "out", "", gs))),
            (f"cls:{TP}.DijkstraCost", lambda e, c, gs=gs: K.parse(c.o.classMethodValue(TP, "DijkstraCost", "a", "c", 9999, "out", "", gs, 0))),
            (f"cls:{VL}.Ends", lambda e, c, gs=gs: [K.parse(c.o.classMethodValue(VL, "Ends", "a", "", d, 1, 3, 0, gs)) for d in ("out", "both")]),
            (f"cls:{VL}.EndsCount", lambda e, c, gs=gs: [int(c.o.classMethodValue(VL, "EndsCount", "a", "", d, mn, 3, 0, gs)) for d, mn in (("out", 1), ("out", 2), ("both", 1))]),
            ("cls:Graph.KG.PageRank.RunJson", lambda e, c, gs=gs: K.parse(c.o.classMethodValue("Graph.KG.PageRank", "RunJson", '["a"]', 0.85, 20, 0, 1.0, gs, "", 1000))),
            ("cls:Graph.KG.PageRank.NodeSeeds", lambda e, c, gs=gs: K.parse(c.o.classMethodValue("Graph.KG.PageRank", "NodeSeeds", '["a","d","zz"]', gs))),
            ("cls:Graph.KG.PageRank.WithUnscored", lambda e, c, gs=gs: K.parse(c.o.classMethodValue("Graph.KG.PageRank", "WithUnscored", '[{"id":"a","score":0.5}]', "Graph_KG", gs, 1000))),
            ("cls:Graph.KG.Centrality.DegreeCentralityJson", lambda e, c, gs=gs: [K.parse(c.o.classMethodValue("Graph.KG.Centrality", "DegreeCentralityJson", d, "", 100, gs)) for d in ("out", "in", "both")]),
            ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.execute_vl_ends", lambda e, c, g=g: rows_of(store(e).execute_vl_ends("a", [], "out", 1, 3, graph=g))),
            ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.shortest_path_length", lambda e, c, g=g: [store(e).shortest_path_length("a", t, [], 5, "out", graph=g) for t in ("c", "d")]),
            ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.execute_shortest_path", lambda e, c, g=g: rows_of(store(e).execute_shortest_path("a", "c", [], 5, "out", False, graph=g))),
            ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.execute_degree_centrality", lambda e, c, gs=gs: rows_of(store(e).execute_degree_centrality("out", "", 100, gs))),
        ]
        if g is None:
            spec += [
                (f"cls:{TK}.KHopCount", lambda e, c: [int(c.o.classMethodValue(TK, "KHopCount", s, p)) for s, p in (("a", ""), ("a", "R"), ("d", ""))]),
                (f"cls:{T}.KHopCount", lambda e, c: [int(c.o.classMethodValue(T, "KHopCount", s, p)) for s, p in (("a", ""), ("a", "R"), ("d", ""))]),
                (f"cls:{TK}.KHopNeighborIds", lambda e, c: [str(c.o.classMethodValue(TK, "KHopNeighborIds", "a", p)).split("\n") for p in ("", "R")]),
                (f"cls:{T}.KHopNeighborIds", lambda e, c: [str(c.o.classMethodValue(T, "KHopNeighborIds", "a", p)).split("\n") for p in ("", "R")]),
                (f"cls:{TK}.KHop2Count", lambda e, c: [int(c.o.classMethodValue(TK, "KHop2Count", "a", p)) for p in ("", "R")]),
                (f"cls:{T}.KHop2Count", lambda e, c: [int(c.o.classMethodValue(T, "KHop2Count", "a", p)) for p in ("", "R")]),
                (f"cls:{TK}.KHop2NeighborIds", lambda e, c: [str(c.o.classMethodValue(TK, "KHop2NeighborIds", "a", p, 0)).split("\n") for p in ("", "R")]),
                (f"cls:{T}.KHop2NeighborIds", lambda e, c: [str(c.o.classMethodValue(T, "KHop2NeighborIds", "a", p, 0)).split("\n") for p in ("", "R")]),
                (f"cls:{TK}.KHop2CountFast", lambda e, c: [int(c.o.classMethodValue(TK, "KHop2CountFast", s, "R")) for s in ("a", "b")]),
                (f"cls:{T}.KHop2CountFast", lambda e, c: [int(c.o.classMethodValue(T, "KHop2CountFast", s, "R")) for s in ("a", "b")]),
                (f"cls:{TK}.KHop2CountExact", lambda e, c: [int(c.o.classMethodValue(TK, "KHop2CountExact", s, "R")) for s in ("a", "b")]),
                (f"cls:{T}.KHop2CountExact", lambda e, c: [int(c.o.classMethodValue(T, "KHop2CountExact", s, "R")) for s in ("a", "b")]),
                ("cls:Graph.KG.Algorithms.WCCJson", cm("Graph.KG.Algorithms", "WCCJson", "")),
                ("cls:Graph.KG.ArnoAccel.WCCJson", cm("Graph.KG.ArnoAccel", "WCCJson", 100)),
                ("cls:Graph.KG.Algorithms.CDLPJson", cm("Graph.KG.Algorithms", "CDLPJson", 10)),
                ("cls:Graph.KG.ArnoAccel.CDLPJson", cm("Graph.KG.ArnoAccel", "CDLPJson", 10)),
                ("cls:Graph.KG.PageRank.PageRankGlobalJson", cm("Graph.KG.PageRank", "PageRankGlobalJson", 0.85, 20, "")),
                ("cls:Graph.KG.ArnoAccel.PageRankGlobalJson", cm("Graph.KG.ArnoAccel", "PageRankGlobalJson", 0.85, 20)),
                ("cls:Graph.KG.ArnoAccel.PPRJson", cm("Graph.KG.ArnoAccel", "PPRJson", '["a"]', 0.85, 20)),
                ("cls:Graph.KG.PageRank.CheckArgs", cmv("Graph.KG.PageRank", "CheckArgs", 0.85, 20)),
                ("cls:Graph.KG.Subgraph.SubgraphJson", cm("Graph.KG.Subgraph", "SubgraphJson", '["a"]', 2, "", 100)),
                ("cls:Graph.KG.ArnoAccel.SubgraphJson", cm("Graph.KG.ArnoAccel", "SubgraphJson", '["a"]', 2, "", 100)),
                ("cls:Graph.KG.Subgraph.PPRGuidedJson", cm("Graph.KG.Subgraph", "PPRGuidedJson", '["a"]', 0.15, 0.00001, 50, 5, "")),
                ("cls:Graph.KG.ArnoAccel.BuildGraphJson", cm("Graph.KG.ArnoAccel", "BuildGraphJson")),
                ("py:iris_vector_graph/stores/arno_bridge.py:build_kg_adjacency_json", lambda e, c: K.parse(__import__("iris_vector_graph.stores.arno_bridge", fromlist=["x"]).build_kg_adjacency_json(e.conn))),
                ("py:iris_vector_graph/stores/arno_bridge.py:build_kg_adjacency_chunked", lambda e, c: list(map(NI.raw, __import__("iris_vector_graph.stores.arno_bridge", fromlist=["x"]).build_kg_adjacency_chunked(e.conn, server_side=False)))),
                ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.execute_subgraph", lambda e, c: rows_of(store(e).execute_subgraph(["a"], 1, [], 100))),
                ("py:iris_vector_graph/stores/iris_sql_store.py:IRISGraphStore.execute_betweenness_neighborhood", lambda e, c: rows_of(store(e).execute_betweenness_neighborhood("a", 2, 200, 20))),
                ("eng:IRISGraphEngine.betweenness_centrality_neighborhood", lambda e, c: NI.raw(e.betweenness_centrality_neighborhood("a"))),
                ("eng:IRISGraphEngine.kg_GRAPH_PATH", lambda e, c: NI.raw(e.kg_GRAPH_PATH("a", "R", "R"))),
                ("eng:IRISGraphEngine.kg_GRAPH_WALK_TVF", lambda e, c: NI.raw(e.kg_GRAPH_WALK_TVF("a", 2))),
                ("eng:IRISGraphEngine.kg_PPR", lambda e, c: NI.raw(e.kg_PPR(["a"]))),
                ("eng:IRISGraphEngine.kg_PPR_GUIDED_SUBGRAPH", lambda e, c: NI.raw(e.kg_PPR_GUIDED_SUBGRAPH(["a"], ppr_top_k=5))),
                ("eng:IRISGraphEngine.random_walk", lambda e, c: (lambda ws: {"walked": any(ws), "beyond_abc": sorted({n for w in ws for n in (w if isinstance(w, list) else [w])} - {"a", "b", "c"})})(e.random_walk("a", length=6, num_walks=20))),
                ("eng:IRISGraphEngine.bfs_vector_rerank", lambda e, c: NI.raw(e.bfs_vector_rerank("a", [1.0, 0.0, 0.0, 0.0]))),
                ("cls:Graph.KG.PageRankEmbedded.ComputePageRank", lambda e, c: K.parse(c.o.classMethodValue("Graph.KG.PageRankEmbedded", "ComputePageRank", "%", 10, 0.85, "", 0, 1.0))),
                ("cls:Graph.KG.PageRankEmbedded.ComputePageRankWithMetrics", lambda e, c: (lambda v: {"results": K.parse(v.invoke("%Get", "results")),
                                                                                                         "num_nodes": v.invoke("%Get", "num_nodes"), "num_edges": v.invoke("%Get", "num_edges")})(
                    c.o.classMethodValue("Graph.KG.PageRankEmbedded", "ComputePageRankWithMetrics", "%", 10, 0.85, 0.0001, "", 0, 1.0))),
            ]
        b = algo_base if g is None else (lambda e, c: (NI.base_in(G1)(e, c), e.create_edge("c", "R", "a", graph=G1)))
        L.append(C3(M, f"^KG algorithm and traversal readers, graph {gname} (class methods, their Traversal/ArnoAccel delegates, store and engine methods)",
                    multi(spec), b,
                    f"graph {gname}'s ^KG out/in/degc (and its rows for labels/props/seeds where the footprint lists them): ALG-I2/ALG-I3; footprints/10.json",
                    {"same ids and other edges in the other graphs": og(g)}, inside=(K.a_in if g is None else g1_in), prep=sync,
                    refusal_keys=("eng:IRISGraphEngine.bfs_vector_rerank",),
                    vacuous={"eng:IRISGraphEngine.random_walk": lambda v: "no walk steps: random_walk answers [] without the Arno library (algorithms.py:658-678, F-1002)" if isinstance(v, dict) and v.get("walked") is False else None,
                             "py:iris_vector_graph/stores/arno_bridge.py:build_kg_adjacency_chunked": lambda v: "the bridge raises before walking: libarno_callout not available (arno_bridge.py:658-767)" if K.is_err(v) else None}))
    # ------------------------------------------------------------ VarLength over a 600-node frontier: the parallel last level (LastLevelPart workers)
    def star(g, tag):
        def f(e, c):
            edges = [{"source_id": "a", "predicate": "R", "target_id": f"m{i}"} for i in range(600)]
            edges += [{"source_id": f"m{i}", "predicate": "R", "target_id": f"{tag}{i % 7}"} for i in range(600)]
            e.bulk_create_edges(edges, graph=g)
        return f

    def vl_parallel(e, c):
        """Ends twice; ^IRIS.Temp.IVG.VL's counter is incremented once per split level (LastLevel, VarLength.cls:303),
        read before and after (read only) to show the workers' path ran."""
        out = {}
        before = int(c.o.get("^IRIS.Temp.IVG.VL") or 0)
        for d, mx in (("out", 2), ("out", 3)):
            v = K.parse(c.o.classMethodValue(VL, "Ends", "a", "", d, 1, mx, 0, ""))
            out[f"{d}-{mx}"] = sorted((x["t"], x["l"]) for x in v) if isinstance(v, list) else v
        out["parallel_levels_run"] = int(c.o.get("^IRIS.Temp.IVG.VL") or 0) - before
        return out
    L.append(C3(M, "VarLength.Ends(a, out, 1..2 / 1..3, pAll=0, default graph) over a 600-node frontier (parallel last level)",
                multi([(f"cls:{VL}.LastLevelPart (through Ends: EndsByDistance -> LastLevel -> WorkMgr queue)", vl_parallel)]),
                star(None, "t"), "the default graph's trails from a (VarLength.cls:11-58, 297-396: LastLevelPart walks the graphs Setup selects from the caller's pAll/pGraph)",
                {"the same ids with other targets in a named graph": star(G2, "x")},
                inside=lambda e, c: (e.create_node("t9"), e.create_edge("m1", "R", "t9"))))
    # ------------------------------------------------------------ ^NKG algorithms called directly (no graph argument: the default graph's answer)
    NA, NT, NC, CO = "Graph.KG.NKGAccel", "Graph.KG.NKGAccelTraversal", "Graph.KG.NKGAccelCentrality", "Graph.KG.Communities"
    LOUT = ("Graph.KG.NKGAccelAdjacency", "ReadLargeOutChunk")
    nspec = []
    for cls in (NT, NA):
        nspec += [
            (f"cls:{cls}.KHopNeighbors", lambda e, c, cls=cls: K.parse(c.o.classMethodValue(cls, "KHopNeighbors", "a", 2, 1000))),
            (f"cls:{cls}.KHopNeighborsSorted", lambda e, c, cls=cls: khop_sorted(c, c.o.classMethodValue(cls, "KHopNeighborsSorted", "a", 2, 1000))),
            (f"cls:{cls}.KHopJson", staged(cls, "KHopJson", LOUT, "a", 2, 1000)),
            (f"cls:{cls}.RandomWalkJson", walk_nodes(cls)),
            (f"cls:{cls}.BFSJson", staged(cls, "BFSJson", CHUNK, "a", "[]", 3, 0)),
            (f"cls:{cls}.ShortestPathNKG", lambda e, c, cls=cls: [K.parse(c.o.classMethodValue(cls, "ShortestPathNKG", "a", t, 10)) for t in ("c", "d")]),
            (f"cls:{cls}.CountDistinctKHop", lambda e, c, cls=cls: [K.parse(c.o.classMethodValue(cls, "CountDistinctKHop", "a", "", 2, d)) for d in ("out", "both")]),
            (f"cls:{cls}.ClosenessGlobal", cm(cls if cls == NA else NC, "ClosenessGlobal", "harmonic", "out", 0, 100)),
            (f"cls:{cls}.ClosenessGlobalMSBFS", cm(cls if cls == NA else NC, "ClosenessGlobalMSBFS", "harmonic", "out", 0, 100)),
            (f"cls:{cls}.EigenvectorGlobal", cm(cls if cls == NA else NC, "EigenvectorGlobal", 200, 0.000001, 100, "Graph_KG")),
            (f"cls:{cls}.BetweennessGlobal", cm(cls if cls == NA else NC, "BetweennessGlobal", 0, 100, 200, "out", 0)),
            (f"cls:{cls}.BetweennessGlobalParallel", cm(cls if cls == NA else NC, "BetweennessGlobalParallel", 0, 100, 200, 1, "out", 0)),
            (f"cls:{cls}.BetweennessNeighborhood", cm(cls if cls == NA else NC, "BetweennessNeighborhood", "a", 2, 200, 20)),
        ]
    nspec = [(k.replace(f"cls:{NT}.Closeness", f"cls:{NC}.Closeness").replace(f"cls:{NT}.Eigen", f"cls:{NC}.Eigen").replace(f"cls:{NT}.Betweenness", f"cls:{NC}.Betweenness"), f) for k, f in nspec]
    nspec += [
        (f"cls:{NT}.LastBfsPath", lambda e, c: (c.o.classMethodValue(NT, "BFSJson", "a", "[]", 3, 0), str(c.o.classMethodValue(NT, "LastBfsPath")))[1]),
        (f"cls:{NT}.LastBfsError", lambda e, c: K.DIGITS.sub("#", str(c.o.classMethodValue(NT, "LastBfsError")))[:120]),
        (f"cls:{NT}.LastBfsChunks", cm(NT, "LastBfsChunks")),
        (f"cls:{NT}.StructuralGuard", lambda e, c: [int(c.o.classMethodValue(NT, "StructuralGuard", c.o.classMethodValue("Graph.KG.GraphIndex", "GetNodeIdx", n), "")) for n in ("a", "b")]),
        (f"cls:{CO}.TriangleCountJson", cm(CO, "TriangleCountJson", 100)),
        (f"cls:{CO}.KCoreJson", cm(CO, "KCoreJson", 100)),
        (f"cls:{CO}.SCCJson", cm(CO, "SCCJson", 100)),
        (f"cls:{CO}.LeidenJson", cm(CO, "LeidenJson", 10, 1.0, 0.0001, 100, 256, 7)),
        (f"cls:{CO}.LeidenJsonAuto", cm(CO, "LeidenJsonAuto", 10, 1.0, 0.0001, 100, 256, 7)),
        (f"cls:{CO}.LeidenJsonPy", cm(CO, "LeidenJsonPy", 1.0, 100, 7)),
        (f"cls:{CO}.ClosenessJsonPy", cm(CO, "ClosenessJsonPy", "harmonic", 100)),
    ]
    L.append(C3(M, "^NKG algorithms called directly over the Native API (no graph argument), after sync",
                multi(nspec), algo_base,
                "the default graph's edges (ALG-I3: an algorithm that takes no graph answers for the default graph alone); "
                "^NKG holds every graph's edges with no graph key (NKGAccel.cls:213-223)",
                {"same ids and edges in the named graphs (merged into ^NKG by sync)": NI.other_graphs(None),
                 "edgeless nodes with labels/props in the named graphs, props on default nodes": named_nodes_and_props},
                inside=K.a_in, prep=sync,
                vacuous={f"cls:{CO}.LeidenJsonPy": lambda v: "PYUNAVAIL: igraph/leidenalg not importable in this IRIS (Communities.cls:613-622)" if v == "PYUNAVAIL" else None,
                         f"cls:{CO}.ClosenessJsonPy": lambda v: "PYUNAVAIL: igraph not importable in this IRIS (Communities.cls:543-549)" if v == "PYUNAVAIL" else None}))
    # ------------------------------------------------------------ the snapshot's own readers (every graph by declaration) and the loaders
    snap = []
    for cls in ("Graph.KG.NKGAccelLoader", NA):
        snap += [
            (f"cls:{cls}.UseNKG", cm(cls, "UseNKG")),
            (f"cls:{cls}.GetFirstNKGNode", cm(cls, "GetFirstNKGNode")),
            (f"cls:{cls}.WarmAdjCache", cm(cls, "WarmAdjCache")),
            (f"cls:{cls}.Capabilities", cm(cls, "Capabilities")),
            (f"cls:{cls}.BuildNKGRust", cm(cls, "BuildNKGRust")),
            (f"cls:{cls}.Load", cm(cls, "Load", "")),
            (f"cls:{cls}.LoadedPath", cm(cls, "LoadedPath")),
            (f"cls:{cls}.IsLoaded", cm(cls, "IsLoaded")),
            (f"cls:{cls}.ResetCache", cmv(cls, "ResetCache")),
            (f"cls:{cls}.Unload", cmv(cls, "Unload")),
        ]
    snap += [
        ("cls:Graph.KG.NKGAccelLoader.LoadError", lambda e, c: (c.o.classMethodValue("Graph.KG.NKGAccelLoader", "Load", ""), str(c.o.classMethodValue("Graph.KG.NKGAccelLoader", "LoadError")))[1]),
        ("cls:Graph.KG.NKGAccelAdjacency.ExportAdjacency", cm("Graph.KG.NKGAccelAdjacency", "ExportAdjacency")),
        (f"cls:{NA}.ExportAdjacency", cm(NA, "ExportAdjacency")),
        ("cls:Graph.KG.NKGAccelAdjacency.ExportAdjacencyWithPreds", lambda e, c: sorted(str(c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "ExportAdjacencyWithPreds", "", 0)).split("\n"))),
        ("cls:Graph.KG.NKGAccelAdjacency.StoreLargeOut", lambda e, c: [str(c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "StoreLargeOut", "RD3", "x" * n)) for n in (10, 9500)]),
        ("cls:Graph.KG.NKGAccelAdjacency.ReadLargeOutChunk", lambda e, c: (c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "StoreLargeOut", "RD3", "y" * 9500),
                                                                           [len(str(c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "ReadLargeOutChunk", "RD3", i) or "")) for i in (1, 2, 3)])[1]),
        (f"cls:{NA}.ReadLargeOutChunk", lambda e, c: (c.o.classMethodValue("Graph.KG.NKGAccelAdjacency", "StoreLargeOut", "RD3", "z" * 9500),
                                                       [len(str(c.o.classMethodValue(NA, "ReadLargeOutChunk", "RD3", i) or "")) for i in (1, 2)])[1]),
        (f"cls:{NT}.Build2HopExact", cm(NT, "Build2HopExact")),
        (f"cls:{NA}.Build2HopExact", cm(NA, "Build2HopExact")),
        ("cls:Graph.KG.Traversal.NKGEdgeCount", cm(T, "NKGEdgeCount")),
        ("cls:Graph.KG.Traversal.NKGNodeCount", cm(T, "NKGNodeCount")),
        ("cls:Graph.KG.Traversal.NKGLiveNodeCount", cm(T, "NKGLiveNodeCount")),
        ("cls:Graph.KG.Traversal.NKGPopulated", cm(T, "NKGPopulated")),
        ("cls:Graph.KG.Traversal.KGEdgeCount", cm(T, "KGEdgeCount", 10000)),
        ("cls:Graph.KG.AlgoCache.Token (as an offset, see module 04's case)", lambda e, c: "covered in 04"),
    ]
    snap = [x for x in snap if not x[0].startswith("cls:Graph.KG.AlgoCache")]
    L.append(C3(M, "^NKG snapshot readers, loaders, counters (every graph by declaration), after sync",
                multi(snap), lambda e, c: (algo_base(e, c), put(e, G2, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y")])),
                "^NKG as a whole (no graph key, NKGAccel.cls:213-223), ^KG out for KGEdgeCount, process-private ^||NKGAccel, ^ArnoAccel(\"lib_path\")",
                {"edgeless nodes with labels/props in the named graphs, props on default nodes": named_nodes_and_props,
                 "a non-product scratch global": lambda e, c: c.o.set("x", K.SCRATCH, "k")},
                inside=K.a_in, prep=sync, inside_declared={"edges in another named graph": NI.other_graphs(None)}))
    # ------------------------------------------------------------ builders and every-graph writers of module 10 (answers: G1 / ^NKG)
    for entry, call in (("cls:Graph.KG.Traversal.BuildKG", cm(T, "BuildKG")), ("eng:IRISGraphEngine.sync", lambda e, c: e.sync())):
        L.append(C3(M, f"{entry.split(':', 1)[1]}: G1's state after", multi([(entry, lambda e, c, call=call: (call(e, c), K.gstate(c, G1))[1])]),
                    lambda e, c: (NI.base_in(G1)(e, c), e.create_edge("c", "R", "a", graph=G1)),
                    "every graph's rows rebuild that graph's ^KG; G1's from G1's rows (TraversalBuild.cls:30-214)",
                    {"same ids and other edges in the other graphs": og(G1)}, inside=g1_in))
    for entry, call in (("cls:Graph.KG.Traversal.BuildNKG", cm(T, "BuildNKG")), ("eng:IRISGraphEngine.rebuild_nkg", lambda e, c: e.rebuild_nkg()),
                        ("cls:Graph.KG.Traversal.InitNKGSkeleton", cm(T, "InitNKGSkeleton"))):
        L.append(C3(M, f"{entry.split(':', 1)[1]}: ^NKG afterwards (named)", multi([(entry, lambda e, c, call=call: (call(e, c), K.nkg_named(c))[1])]),
                    algo_base, "every graph's ^KG (^NKG merges every graph by design)",
                    {"edgeless nodes with labels/props in the named graphs, props on default nodes": named_nodes_and_props},
                    inside=K.a_in, inside_declared={"edges in a named graph": NI.other_graphs(None)}))
    for entry, store_, call in (("cls:Graph.KG.Traversal.BackfillDegp", "degc", cm(T, "BackfillDegp")), ("cls:Graph.KG.Traversal.Build2HopStats", "deg2p", cm(T, "Build2HopStats")),
                                ("cls:Graph.KG.Traversal.Build2HopExactStats", "deg2p_exact", cm(T, "Build2HopExactStats"))):
        L.append(C3(M, f"{entry.split(':', 1)[1]}: G1's {store_} afterwards", multi([(entry, lambda e, c, call=call, store_=store_: (call(e, c), K.walk(c, "^KG", store_, G1))[1])]),
                    lambda e, c: (NI.base_in(G1)(e, c), e.create_edge("c", "R", "a", graph=G1)),
                    f"every graph's ^KG out; G1's {store_} from G1's out (TraversalBuild.cls:927-1067)",
                    {"same ids and other edges in the other graphs": og(G1)}, inside=g1_in))
    # ------------------------------------------------------------ the Arno bridge: configuration readers (no graph data) and the library readers
    AA = "Graph.KG.ArnoAccel"
    arno = [
        (f"cls:{AA}.LibPath", lambda e, c: [str(c.o.classMethodValue(AA, "LibPath", p)) for p in ("", "/tmp/x.so")]),
        (f"cls:{AA}.TrustedPath", lambda e, c: [int(c.o.classMethodValue(AA, "TrustedPath", p)) for p in ("/usr/irissys/bin/libarno.so", "/tmp/../x.so", "rel.so")]),
        (f"cls:{AA}.RequireCallout", lambda e, c: [str(c.o.classMethodValue(AA, "RequireCallout", str(c.o.classMethodValue(AA, "LibPath", "")), "version"))]),
        (f"cls:{AA}.LoadedPath", cm(AA, "LoadedPath")),
        (f"cls:{AA}.LibExists", cm(AA, "LibExists", "")),
        (f"cls:{AA}.Load", cm(AA, "Load", "")),
        (f"cls:{AA}.GetLibPath", cm(AA, "GetLibPath")),
        (f"cls:{AA}.IsAvailable", cm(AA, "IsAvailable")),
        (f"cls:{AA}.ReaderRevisions", cm(AA, "ReaderRevisions")),
        (f"cls:{AA}.LibraryVersion", cm(AA, "LibraryVersion")),
        ("cls:Graph.KG.ArnoAccel.OpenLibrary (through NKGAccelLoader.Load/LoadError, which call it)", lambda e, c: (c.o.classMethodValue("Graph.KG.NKGAccelLoader", "Load", "/tmp/ivgauditd-rd3-none.so"), str(c.o.classMethodValue("Graph.KG.NKGAccelLoader", "LoadError")))[1]),
        ("py:iris_vector_graph/stores/arno_bridge.py:resolve_lib_path", lambda e, c: __import__("iris_vector_graph.stores.arno_bridge", fromlist=["x"]).resolve_lib_path(e.conn)),
        ("py:iris_vector_graph/stores/arno_bridge.py:record_configured_lib_path", lambda e, c: (__import__("iris_vector_graph.stores.arno_bridge", fromlist=["x"]).record_configured_lib_path(e.conn), str(c.o.classMethodValue(AA, "GetLibPath")))[1]),
        ("py:iris_vector_graph/arno_readers.py:read_reader_report", lambda e, c: __import__("iris_vector_graph.arno_readers", fromlist=["x"]).read_reader_report(store(e))),
        (f"cls:{AA}.PageRankNativeJson", cm(AA, "PageRankNativeJson", 0.85, 20)),
        (f"cls:{AA}.PPRNativeJson", lambda e, c: [K.parse(c.o.classMethodValue(AA, "PPRNativeJson", s, 0.85, 20)) for s in ('["a"]', '["d"]')]),
        (f"cls:{AA}.WCCNativeJson", cm(AA, "WCCNativeJson")),
        (f"cls:{AA}.CDLPNativeJson", cm(AA, "CDLPNativeJson", 10)),
        (f"cls:{AA}.SubgraphNativeJson", cm(AA, "SubgraphNativeJson", '["a"]', 2, 100)),
        (f"cls:{AA}.KhopSampleJson", cm(AA, "KhopSampleJson", '["a"]', 2, 16)),
        (f"cls:{AA}.RandomWalkJson", cm(AA, "RandomWalkJson", '["a"]', 5, 3)),
        (f"cls:{AA}.NeighborAggJson", cm(AA, "NeighborAggJson", '["a"]', 2)),
    ]
    L.append(C3(M, "ArnoAccel configuration readers, the bridge's path resolvers, and the library readers in this namespace (not USER)",
                multi(arno), algo_base, "^ArnoAccel(\"lib_path\"), process-private ^||ArnoAccel / ^||NKGAccel, the file system; the library readers refuse "
                "outside USER before reading (ArnoAccel.cls:241-250, 404-440)",
                {"same ids and edges in the named graphs": NI.other_graphs(None), "a non-product scratch global": lambda e, c: c.o.set("x", K.SCRATCH, "k")},
                inside=K.a_in, prep=sync,
                vacuous={**{f"cls:{AA}.{m}": (lambda v: "refused before any read: the library readers run only in USER (ArnoAccel.cls:241-250 NativeResult); "
                                                      "the library itself is absent here (F-1001), so its read of ^KG is not observable" if K.is_err(v) else None)
                            for m in ("PageRankNativeJson", "PPRNativeJson", "WCCNativeJson", "CDLPNativeJson", "SubgraphNativeJson")},
                         **{f"cls:{AA}.{m}": (lambda v: "answered the empty marker before any read: ReadsUser() is false outside USER (ArnoAccel.cls:404-440); "
                                                      "the library is absent here (F-1001)" if v in ([], {}) or (isinstance(v, dict) and v.get("layers") == []) else None)
                            for m in ("KhopSampleJson", "RandomWalkJson", "NeighborAggJson")}}))
    # ------------------------------------------------------------ every-graph readers by declaration
    L.append(C3(M, "kg_MENTIONS (kg_NEIGHBORS along a predicate: every graph, ALG-B9.10) and VarLength pAll=1", multi([
        ("eng:IRISGraphEngine.kg_MENTIONS", lambda e, c: sorted(NI.raw(e.kg_MENTIONS(["a"], "R")))),
        (f"cls:{VL}.Ends#pAll=1", lambda e, c: K.parse(c.o.classMethodValue(VL, "Ends", "a", "", "out", 1, 2, 1, ""))),
        ]), algo_base, "a's one-hop neighbours over R in every graph (algorithms.py:986-1027); every graph's trails from a (VarLength.cls:11-14 'pAll 1 for every graph')",
        {"other sources' edges in every graph": lambda e, c: [put(e, x, {"x": ([], {}), "y": ([], {})}, [("x", "R", "y")]) for x in (None, G1, G2)]},
        inside=K.a_in, inside_declared={"same ids and edges in the named graphs": NI.other_graphs(None)}))
    # ------------------------------------------------------------ kg_RERANK: the default graph's BM25 index (and vector leg)
    def rerank_base(e, c):
        put(e, None, {"a": (["L"], {"txt": "apple pie"}), "b": (["L"], {"txt": "banana bread"}), "c": (["L"], {"txt": "apple tart"})}, [("a", "R", "b")])
        e.bm25_build("rd3d", ["txt"])

    def rerank_out(e, c):
        put(e, G2, {"a": (["L"], {"txt": "apple apple apple"}), "q": (["L"], {"txt": "apple apple"}), "c": ([], {"txt": "nothing"})}, [])
        e.bm25_build("rd3g", ["txt"], graph=G2)

    def rerank_drop(e, c):
        for n in ("rd3d", "rd3g"):
            try:
                c.o.classMethodValue("Graph.KG.BM25Index", "Drop", n)
            except Exception:  # noqa: BLE001
                pass
    L.append(C3(M, "kg_RERANK(3, vector, 'apple'): default graph's fused answer", multi([
        ("eng:IRISGraphEngine.kg_RERANK", lambda e, c: NI.raw(e.kg_RERANK(3, "[1,0,0,0]", "apple"))),
        ]), rerank_base, "the default graph's BM25 index (^BM25Idx of the index recorded for graph '') and vector leg (vector.py:1382-1442)",
        {"a BM25 index of G2 with more matching documents, same ids": rerank_out},
        inside=lambda e, c: (e.create_node("q", properties={"txt": "apple apple apple"}), e.bm25_build("rd3d", ["txt"]))))
    # ------------------------------------------------------------ Cypher procedures (SQL path: native_cypher=False)
    nkg_procs = [("cypher:ivg.betweenness", "CALL ivg.betweenness() YIELD node, score RETURN node.node_id AS id, score"),
                 ("cypher:ivg.closeness", "CALL ivg.closeness() YIELD node, score RETURN node.node_id AS id, score"),
                 ("cypher:ivg.eigenvector", "CALL ivg.eigenvector() YIELD node, score RETURN node.node_id AS id, score"),
                 ("cypher:ivg.leiden", "CALL ivg.leiden({randomSeed: 7}) YIELD node, community RETURN node.node_id AS id, community"),
                 ("cypher:ivg.trianglecount", "CALL ivg.triangleCount() YIELD node, triangles RETURN node.node_id AS id, triangles"),
                 ("cypher:ivg.scc", "CALL ivg.scc() YIELD node, component RETURN node.node_id AS id, component"),
                 ("cypher:ivg.kcore", "CALL ivg.kcore() YIELD node, coreness RETURN node.node_id AS id, coreness")]
    L.append(C3(M, "the seven ^NKG Cypher procedures, no USE GRAPH (they refuse once a named graph has edges, ALG-B7)",
                multi([(k, cy(q)) for k, q in nkg_procs]), algo_base,
                "the default graph's edges through ^NKG; the refusal reads which graphs hold edges (ALG-B7, B7.5)",
                {"edgeless nodes with labels/props in the named graphs, props on default nodes": named_nodes_and_props},
                inside=K.a_in, prep=sync, inside_declared={"edges in a named graph (refusal)": NI.other_graphs(None)}))
    g1_procs = [("cypher:ivg.degreecentrality", f"USE GRAPH '{G1}' CALL ivg.degreeCentrality() YIELD node, score, degree RETURN node.node_id AS id, score, degree"),
                ("cypher:ivg.ppr", f"USE GRAPH '{G1}' CALL ivg.ppr(['a'], 0.85, 20) YIELD node, score RETURN node.node_id AS id, score"),
                ("cypher:ivg.neighbors", f"USE GRAPH '{G1}' CALL ivg.neighbors(['a'], 'R', 'both') YIELD neighbor RETURN neighbor.node_id AS id"),
                ("cypher:ivg.shortestpath.weighted", f"USE GRAPH '{G1}' CALL ivg.shortestPath.weighted('a', 'c') YIELD path, totalCost RETURN path, totalCost"),
                ("cypher:gds.pagerank.stream", f"USE GRAPH '{G1}' CALL gds.pageRank.stream('g') YIELD nodeId, score RETURN nodeId, score"),
                ("cypher:gds.betweenness.stream", f"USE GRAPH '{G1}' CALL gds.betweenness.stream('g') YIELD nodeId, score RETURN nodeId, score"),
                ("cypher:gds.shortestpath.dijkstra.stream", f"USE GRAPH '{G1}' CALL gds.shortestPath.dijkstra.stream('g', {{sourceNode: 'a', targetNode: 'c'}}) YIELD totalCost, nodeIds RETURN totalCost, nodeIds"),
                ("cypher:gds.shortestpath.dijkstra", f"USE GRAPH '{G1}' CALL gds.shortestPath.dijkstra('g', {{sourceNode: 'a', targetNode: 'c'}}) YIELD totalCost, nodeIds RETURN totalCost, nodeIds")]
    L.append(C3(M, "Cypher procedures scoped by USE GRAPH G1", multi([(k, cy(q)) for k, q in g1_procs]),
                lambda e, c: (NI.base_in(G1)(e, c), e.create_edge("c", "R", "a", graph=G1)),
                "graph G1's edges (USE GRAPH; ivg.degreeCentrality / ivg.ppr read the USE GRAPH, translator.py:225-240)",
                {"same ids and other edges in the other graphs": og(G1)}, inside=g1_in, prep=sync,
                refusal_keys=("cypher:gds.pagerank.stream", "cypher:gds.betweenness.stream", "cypher:gds.shortestpath.dijkstra.stream", "cypher:gds.shortestpath.dijkstra")))
    d_procs = [(k + "#default", q.replace(f"USE GRAPH '{G1}'", "USE GRAPH ''")) for k, q in g1_procs]
    L.append(C3(M, "Cypher procedures scoped by USE GRAPH '' (the default graph)", multi([(k, cy(q)) for k, q in d_procs]), algo_base,
                "the default graph's edges (USE GRAPH '')", {"same ids and edges in the named graphs": NI.other_graphs(None)},
                inside=K.a_in, prep=sync))
    return L
