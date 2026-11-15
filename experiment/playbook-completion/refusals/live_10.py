#!/usr/bin/env python3
"""Module 10 (algorithms): live probes of the stated refusals (ALG kind X) in namespace AUDITE.

    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_10.py [--out results.json] [case ...]
    bash experiment/playbook-completion/tools/locks.sh iris timeout 1500 \
        python experiment/playbook-completion/refusals/live_10.py --out results-rebuild-wait.json b12_wait

Each case triggers the refused condition through the product's real entry point (engine methods, CALL ivg.*
through engine.execute_cypher, the deployed SQL functions and the server class methods the statements name) inside a
journal window (rxlib): it holds when the product refuses as the statement says and the journal shows no net change
outside the stores the case names (each named store is justified in the case). Setup runs outside the windows.

Caller-supplied stores (ALG-B5.5, B5.21, B6.8): the engine's documented `store=` argument takes any GraphStore; the
product ships only IRISGraphStore, so the statements' "store whose degree method takes no graph", "store that lacks a
centrality method" and "store path that failed" are made with RX10CallerStore, a delegating object of this harness
(not a subclass, nothing patched or compiled) around a real IRISGraphStore on the same connection.

b12_wait (ALG-B12.3, B12.8) holds ^IVG.NKGBuild from a second connection and waits out the server's NKGBUILDWAIT
(900 s, TraversalBuild.cls:250) on two rebuilds at once: Graph.KG.Traversal.BuildNKG called directly (third
connection) and engine.sync() (main connection). It runs on its own (about 16 minutes).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rxlib import Lane, raises, returns, either, run_cases, engine, NS  # noqa: E402

import journal  # noqa: E402  (rxlib put traces/ on sys.path)

from iris_vector_graph.result import IVGResult  # noqa: E402
from iris_vector_graph.stores.iris_sql_store import IRISGraphStore  # noqa: E402

G = "rx10g"
A, B, C, D = "rx10:a", "rx10:b", "rx10:c", "rx10:d"


class RX10CallerStore:
    """A caller-supplied GraphStore: delegates to the product's IRISGraphStore except what a case changes."""

    def __init__(self, inner, drop=(), caps_drop=(), override=None):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_drop", set(drop))
        object.__setattr__(self, "_caps_drop", set(caps_drop))
        object.__setattr__(self, "_override", dict(override or {}))

    def __getattr__(self, name):
        if name in self._drop:
            raise AttributeError(name)
        if name in self._override:
            return self._override[name]
        return getattr(self._inner, name)

    def capabilities(self):
        caps = dict(self._inner.capabilities())
        for k in self._caps_drop:
            caps.pop(k, None)
        return caps


def caller_engine(L, **store_kw):
    from iris_vector_graph.engine import IRISGraphEngine
    inner = IRISGraphStore(L.c.conn, namespace=NS, schema="Graph_KG")
    return IRISGraphEngine(L.c.conn, namespace=NS, store=RX10CallerStore(inner, **store_kw), embedding_dimension=4)


def seed_default(L):
    e = L.eng
    for n in (A, B, C, D):
        e.create_node(n, labels=["RX10"])
    e.create_edge(A, "RX10R", B)
    e.create_edge(B, "RX10R", C)
    e.create_edge(C, "RX10R", D)
    L.c.conn.commit()


def seed_named(L):
    e = L.eng
    e.create_node("rx10:x", labels=["RX10"], graph=G)
    e.create_node("rx10:y", labels=["RX10"], graph=G)
    e.create_edge("rx10:x", "RX10R", "rx10:y", graph=G)
    L.c.conn.commit()


def cy(L, q):
    return lambda: L.eng.execute_cypher(q)


def sql1(L, q, *p):
    return lambda: L.c.sql(q, *p)


def call(L, cls, m, *a):
    return lambda: str(L.c.call(cls, m, *a))


ANY = "Exception"
#: IRIS's own SQL statement dictionary (^oddTSQL), written by the engine when it first prepares a statement text. It is
#: not product content and is missing from traces/journal.py's system-global filter; every case allows it.
SQLMETA = r"^\^oddTSQL"


def refuse(L, *a, allowed=(), **k):
    return L.refusal(*a, allowed=list(allowed) + [SQLMETA], **k)
NKG_SIDE = r"\^NKG|\^IVG\.BuiltFrom|\^IVG\.NKGBuild"   # the read-side ^NKG build (EnsureNKG), where a case names it


# ------------------------------------------------------------------------------------------------ empty namespace
def c_b7_4(L):
    """ALG-B7.4: with no snapshot built (empty namespace after EraseAll), a snapshot procedure fails and says so."""
    L.reset()
    L.note("ALG-B7.4", "setup: empty namespace", counts=L.counts(),
           nkg_first=str(L.c.call("Graph.KG.NKGAccel", "GetFirstNKGNode")))
    for q in ("CALL ivg.triangleCount() YIELD node, triangles RETURN node, triangles",
              "CALL ivg.scc() YIELD node, component RETURN node, component",
              "CALL ivg.kcore() YIELD node, coreness RETURN node, coreness"):
        refuse(L, "ALG-B7.4", f"empty namespace: {q.split(' YIELD')[0]}", cy(L, q),
                  returns(lambda r: (not r.rows) and "NKG not built" in str(r.error or ""),
                          "IVGResult with no rows and error naming '^NKG not built' (execute_cypher answers a failed "
                          "read in-band, query.py:1756-1774)"), entry="engine.execute_cypher")
        refuse(L, "ALG-B7.4", f"empty namespace: {q.split(' YIELD')[0]} raise_on_error=True",
               (lambda qq=q: L.eng.execute_cypher(qq, raise_on_error=True)),
               raises(ANY, match=r"NKG not built"), entry="engine.execute_cypher(raise_on_error=True)")
    refuse(L, "ALG-B7.4", "empty namespace: SQL Graph_KG.kg_TriangleCount()",
              sql1(L, "SELECT Graph_KG.kg_TriangleCount()"), raises(ANY, match=r"NKG not built"),
              entry="SQL function kg_TriangleCount (schema.py:2718-2734)")
    refuse(L, "ALG-B7.4", "empty namespace: Communities.TriangleCountJson",
              call(L, "Graph.KG.Communities", "TriangleCountJson", 10),
              returns(lambda r: str(r).startswith("ERROR:") and "NKG not built" in str(r), "'ERROR:^NKG not built'"),
              entry="Graph.KG.Communities.TriangleCountJson (Native API)")


# ------------------------------------------------------------------------------------------------ default graph only
def c_default(L):
    L.reset()
    seed_default(L)
    e = L.eng
    # warm the read-side snapshot outside the windows so a case's window shows only the refused call
    try:
        e.execute_cypher("CALL ivg.triangleCount() YIELD node, triangles RETURN node, triangles")
    except Exception as x:  # noqa: BLE001
        L.note("setup", "warm ^NKG failed", error=str(x)[:300])
    L.c.conn.commit()
    L.note("setup", "default graph a->b->c->d seeded", counts=L.counts(),
           nkg_first=str(L.c.call("Graph.KG.NKGAccel", "GetFirstNKGNode")))

    # ALG-B1.5 global PageRank
    refuse(L, "ALG-B1.5", "kg_PAGERANK damping 1.5", lambda: e.kg_PAGERANK(damping=1.5),
              raises("ValueError", match=r"damping"), entry="engine.kg_PAGERANK")
    refuse(L, "ALG-B1.5", "kg_PAGERANK damping 0", lambda: e.kg_PAGERANK(damping=0.0),
              raises("ValueError", match=r"damping"), entry="engine.kg_PAGERANK")
    refuse(L, "ALG-B1.5", "kg_PAGERANK max_iterations 0", lambda: e.kg_PAGERANK(max_iterations=0),
              raises("ValueError", match=r"max_iterations"), entry="engine.kg_PAGERANK")
    refuse(L, "ALG-B1.5", "PageRankGlobalJson damping 1.5 (class method)",
              call(L, "Graph.KG.PageRank", "PageRankGlobalJson", "1.5", "20"),
              raises(ANY, match=r"alpha|damping"), entry="Graph.KG.PageRank.PageRankGlobalJson")
    refuse(L, "ALG-B1.5", "PageRankGlobalJson maxIter 0 (class method)",
              call(L, "Graph.KG.PageRank", "PageRankGlobalJson", "0.85", "0"),
              raises(ANY, match=r"maxIter"), entry="Graph.KG.PageRank.PageRankGlobalJson")

    # ALG-B2.2 graph names
    refuse(L, "ALG-B2.2", "PPR graph '0'", lambda: e.kg_PERSONALIZED_PAGERANK([A], graph="0"),
              raises("ValueError", match=r'"0"|reserved'), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.2", "PPR graph with a control character",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], graph="rx10\x01g"),
              raises("ValueError", match=r"control character"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.2", "degree_centrality graph '0'", lambda: e.degree_centrality(graph="0"),
              raises("ValueError", match=r'"0"|reserved'), entry="engine.degree_centrality")

    # ALG-B2.8 PPR damping / rounds, every entry point
    refuse(L, "ALG-B2.8", "kg_PERSONALIZED_PAGERANK damping_factor 1.0",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], damping_factor=1.0),
              raises("ValueError", match=r"damping_factor"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.8", "kg_PERSONALIZED_PAGERANK max_iterations 0",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], max_iterations=0),
              raises("ValueError", match=r"max_iterations"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.8", "ppr alpha 2.0", lambda: e.ppr(A, alpha=2.0),
              raises("ValueError", match=r"alpha"), entry="engine.ppr")
    refuse(L, "ALG-B2.8", "kg_PPR damping 2", lambda: e.kg_PPR([A], damping=2.0),
              raises("ValueError", match=r"damping"), entry="engine.kg_PPR")
    refuse(L, "ALG-B2.8", "SQL kg_PPR dampingFactor 2",
              sql1(L, "SELECT Graph_KG.kg_PPR(?, 2.0)", json.dumps([A])),
              raises(ANY, match=r"alpha|damping"), entry="SQL function kg_PPR (schema.py:2582-2598)")
    refuse(L, "ALG-B2.8", "PageRank.RunJson alpha 2 (class method)",
              call(L, "Graph.KG.PageRank", "RunJson", json.dumps([A]), "2", "20"),
              raises(ANY, match=r"alpha"), entry="Graph.KG.PageRank.RunJson")
    refuse(L, "ALG-B2.8", "CALL ivg.ppr alpha 2",
              cy(L, f"CALL ivg.ppr(['{A}'], 2.0) YIELD node, score RETURN node, score"),
              raises(ANY, match=r"alpha|damping"), entry="engine.execute_cypher")

    # ALG-B2.9
    refuse(L, "ALG-B2.9", "negative reverse_edge_weight",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], bidirectional=True, reverse_edge_weight=-1.0),
              raises("ValueError", match=r"reverse_edge_weight"), entry="engine.kg_PERSONALIZED_PAGERANK")

    # ALG-B2.10
    refuse(L, "ALG-B2.10", "empty seed list", lambda: e.kg_PERSONALIZED_PAGERANK([]),
              raises("ValueError", match=r"at least one"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.10", "a single string seed", lambda: e.kg_PERSONALIZED_PAGERANK(A),
              raises("TypeError", match=r"not a string"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.10", "a seed that is not a string", lambda: e.kg_PERSONALIZED_PAGERANK([1]),
              raises("TypeError", match=r"node ID"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.10", "a nested-list seed", lambda: e.kg_PERSONALIZED_PAGERANK([[A]]),
              raises("TypeError"), entry="engine.kg_PERSONALIZED_PAGERANK")

    # ALG-B2.13
    refuse(L, "ALG-B2.13", "exclude_predicates as a string",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], exclude_predicates="RX10R"),
              raises("ValueError", match=r"not a string|list"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.13", "exclude entry with two dots",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], exclude_predicates=["a.b.c"]),
              raises("ValueError", match=r"Type\.p"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.13", "exclude entry not a string",
              lambda: e.kg_PERSONALIZED_PAGERANK([A], exclude_predicates=[3]),
              raises("ValueError", match=r"strings"), entry="engine.kg_PERSONALIZED_PAGERANK")
    refuse(L, "ALG-B2.13", "RunJson pExclude entry a.b.c (class method)",
              call(L, "Graph.KG.PageRank", "RunJson", json.dumps([A]), "0.85", "20", 0, "1.0", "",
                   json.dumps(["a.b.c"])),
              raises(ANY, match=r"malformed pExclude"), entry="Graph.KG.PageRank.RunJson")
    refuse(L, "ALG-B2.13", "RunJson pExclude not JSON (class method)",
              call(L, "Graph.KG.PageRank", "RunJson", json.dumps([A]), "0.85", "20", 0, "1.0", "", "RX10R"),
              raises(ANY, match=r"pExclude is not JSON"), entry="Graph.KG.PageRank.RunJson")

    # ALG-B3.4 WCC with a round limit below what the chain needs (a->b->c->d settles in 4 rounds)
    refuse(L, "ALG-B3.4", "kg_WCC max_iterations 1 on a 4-node chain", lambda: e.kg_WCC(max_iterations=1),
              raises(ANY, match=r"did not converge"), entry="engine.kg_WCC")
    refuse(L, "ALG-B3.4", "Algorithms.WCCJson maxIter 1 (class method)",
              call(L, "Graph.KG.Algorithms", "WCCJson", 1), raises(ANY, match=r"did not converge"),
              entry="Graph.KG.Algorithms.WCCJson")
    try:
        ok = e.kg_WCC(max_iterations=10)
        L.note("ALG-B3.4", "control: kg_WCC max_iterations 10 answers", answer=ok)
    except Exception as x:  # noqa: BLE001
        L.note("ALG-B3.4", "control: kg_WCC max_iterations 10 raised", error=str(x)[:300])

    # ALG-B5.3 direction
    refuse(L, "ALG-B5.3", "degree_centrality direction 'sideways'", lambda: e.degree_centrality(direction="sideways"),
              raises("ValueError", match=r"direction"), entry="engine.degree_centrality")
    refuse(L, "ALG-B5.3", "Centrality.DegreeCentralityJson direction 'sideways' (class method)",
              call(L, "Graph.KG.Centrality", "DegreeCentralityJson", "sideways", "", 10, ""),
              raises(ANY, match=r"direction must be"), entry="Graph.KG.Centrality.DegreeCentralityJson")
    refuse(L, "ALG-B5.3", "CALL ivg.degreeCentrality direction 'up'",
              cy(L, "CALL ivg.degreeCentrality({direction: 'up'}) YIELD node, score RETURN node, score"),
              raises(ANY, match=r"direction"), entry="engine.execute_cypher")

    # ALG-B5.10 betweenness arguments
    refuse(L, "ALG-B5.10", "betweenness sample_size -1", lambda: e.betweenness_centrality(sample_size=-1),
              raises("ValueError", match=r"sample_size"), entry="engine.betweenness_centrality")
    refuse(L, "ALG-B5.10", "betweenness direction 'sideways'",
              lambda: e.betweenness_centrality(direction="sideways"),
              raises("ValueError", match=r"direction"), entry="engine.betweenness_centrality")
    refuse(L, "ALG-B5.10", "betweenness max_hops 1001", lambda: e.betweenness_centrality(max_hops=1001),
              raises("ValueError", match=r"max_hops"), entry="engine.betweenness_centrality")
    refuse(L, "ALG-B5.10", "betweenness max_hops -1", lambda: e.betweenness_centrality(max_hops=-1),
              raises("ValueError", match=r"max_hops"), entry="engine.betweenness_centrality")
    refuse(L, "ALG-B5.10", "betweenness mem_budget_mb 8", lambda: e.betweenness_centrality(mem_budget_mb=8),
              raises("ValueError", match=r"mem_budget_mb"), entry="engine.betweenness_centrality")

    # ALG-B5.17 closeness formula
    refuse(L, "ALG-B5.17", "closeness formula 'mean'", lambda: e.closeness_centrality(formula="mean"),
              raises("ValueError", match=r"formula"), entry="engine.closeness_centrality")
    refuse(L, "ALG-B5.17", "closeness formula 'classic'", lambda: e.closeness_centrality(formula="classic"),
              raises("ValueError", match=r"formula"), entry="engine.closeness_centrality")

    # ALG-B5.22
    refuse(L, "ALG-B5.22", "bfs_vector_rerank on IRISGraphStore",
              lambda: e.bfs_vector_rerank(A, [0.0, 0.0, 0.0, 1.0]),
              raises("NotImplementedError", match=r"IRISGraphStore"), entry="engine.bfs_vector_rerank")

    # ALG-B5.94 server closeness / betweenness
    refuse(L, "ALG-B5.94", "NKGAccel.ClosenessGlobal direction 'sideways'",
              call(L, "Graph.KG.NKGAccel", "ClosenessGlobal", "harmonic", "sideways", 0, 10),
              returns(lambda r: str(r).startswith("ERROR:direction must be out, in or both"), "ERROR:direction..."),
              entry="Graph.KG.NKGAccel.ClosenessGlobal")
    refuse(L, "ALG-B5.94", "NKGAccel.ClosenessGlobalMSBFS direction 'up'",
              call(L, "Graph.KG.NKGAccel", "ClosenessGlobalMSBFS", "harmonic", "up", 0, 10),
              returns(lambda r: str(r).startswith("ERROR:direction must be out, in or both"), "ERROR:direction..."),
              entry="Graph.KG.NKGAccel.ClosenessGlobalMSBFS")
    refuse(L, "ALG-B5.94", "NKGAccel.BetweennessGlobal direction 'sideways'",
              call(L, "Graph.KG.NKGAccel", "BetweennessGlobal", 0, 10, 200, "sideways", 0),
              returns(lambda r: str(r).startswith("ERROR:direction must be out, in or both"), "ERROR:direction..."),
              entry="Graph.KG.NKGAccel.BetweennessGlobal")
    refuse(L, "ALG-B5.94", "NKGAccel.BetweennessGlobal maxHops -1",
              call(L, "Graph.KG.NKGAccel", "BetweennessGlobal", 0, 10, 200, "out", -1),
              returns(lambda r: str(r).startswith("ERROR:maxHops must be a whole number 0 or more"), "ERROR:maxHops..."),
              entry="Graph.KG.NKGAccel.BetweennessGlobal")
    refuse(L, "ALG-B5.94", "NKGAccel.BetweennessGlobal maxHops 1.5",
              call(L, "Graph.KG.NKGAccel", "BetweennessGlobal", 0, 10, 200, "out", "1.5"),
              returns(lambda r: str(r).startswith("ERROR:maxHops must be a whole number 0 or more"), "ERROR:maxHops..."),
              entry="Graph.KG.NKGAccel.BetweennessGlobal")
    refuse(L, "ALG-B5.94", "SQL kg_Betweenness direction 'sideways' -> IVG 5001",
              sql1(L, "SELECT Graph_KG.kg_Betweenness(0, 'sideways', 0, 10, 256)"),
              raises(ANY, match=r"direction must be out, in or both"), entry="SQL function kg_Betweenness")
    refuse(L, "ALG-B5.94", "SQL kg_Betweenness maxHops -1 -> IVG 5001",
              sql1(L, "SELECT Graph_KG.kg_Betweenness(0, 'out', -1, 10, 256)"),
              raises(ANY, match=r"maxHops must be a whole number"), entry="SQL function kg_Betweenness")
    refuse(L, "ALG-B5.94", "SQL kg_Closeness direction 'up' -> IVG 5001",
              sql1(L, "SELECT Graph_KG.kg_Closeness('harmonic', 'up', 0, 10)"),
              raises(ANY, match=r"direction must be out, in or both"), entry="SQL function kg_Closeness")

    # ALG-B6.7 Leiden settings
    refuse(L, "ALG-B6.7", "leiden gamma 0", lambda: e.leiden_communities(gamma=0.0),
              raises("ValueError", match=r"gamma"), entry="engine.leiden_communities")
    refuse(L, "ALG-B6.7", "leiden gamma -1", lambda: e.leiden_communities(gamma=-1.0),
              raises("ValueError", match=r"gamma"), entry="engine.leiden_communities")
    refuse(L, "ALG-B6.7", "leiden max_levels 0", lambda: e.leiden_communities(max_levels=0),
              raises("ValueError", match=r"max_levels"), entry="engine.leiden_communities")
    refuse(L, "ALG-B6.7", "leiden tol 1.0", lambda: e.leiden_communities(tol=1.0),
              raises("ValueError", match=r"tol"), entry="engine.leiden_communities")

    # ALG-B7.1 USE GRAPH on a snapshot procedure (no named graph has edges yet: R163 alone)
    for q in ("USE GRAPH '' CALL ivg.closeness() YIELD node, score RETURN node, score",
              f"USE GRAPH '{G}' CALL ivg.betweenness() YIELD node, score RETURN node, score",
              f"USE GRAPH '{G}' CALL ivg.leiden() YIELD node, community RETURN node, community"):
        refuse(L, "ALG-B7.1", f"{q.split(' YIELD')[0]}", cy(L, q),
                  raises(ANY, match=r"cannot be scoped to a graph"), entry="engine.execute_cypher")

    # ALG-B7.91 procedure options checked as the engine method checks them
    for q, pat in (("CALL ivg.betweenness({bogus: 1}) YIELD node, score RETURN node, score", r"Unknown parameters"),
                   ("CALL ivg.closeness({formula: 'classic'}) YIELD node, score RETURN node, score", r"formula"),
                   ("CALL ivg.closeness({maxHops: -1}) YIELD node, score RETURN node, score", r"maxHops|max_hops"),
                   ("CALL ivg.eigenvector({maxIter: 0}) YIELD node, score RETURN node, score", r"maxIter|max_iter"),
                   ("CALL ivg.leiden({gamma: 0}) YIELD node, community RETURN node, community", r"gamma"),
                   ("CALL ivg.leiden({weighted: true}) YIELD node, community RETURN node, community",
                    r"Unknown parameters"),
                   ("CALL ivg.triangleCount({topK: -1}) YIELD node, triangles RETURN node, triangles", r"topK|top_k"),
                   ("CALL ivg.scc({topK: -1}) YIELD node, component RETURN node, component", r"topK|top_k"),
                   ("CALL ivg.kcore({depth: 2}) YIELD node, coreness RETURN node, coreness", r"Unknown parameters")):
        refuse(L, "ALG-B7.91", q.split(" YIELD")[0], cy(L, q), raises(ANY, match=pat), entry="engine.execute_cypher")

    # ALG-B8.10 PPR-guided subgraph
    refuse(L, "ALG-B8.10", "kg_PPR_GUIDED_SUBGRAPH damping 2", lambda: e.kg_PPR_GUIDED_SUBGRAPH([A], damping=2.0),
              raises("ValueError", match=r"damping"), entry="engine.kg_PPR_GUIDED_SUBGRAPH")
    refuse(L, "ALG-B8.10", "kg_PPR_GUIDED_SUBGRAPH max_iterations 0",
              lambda: e.kg_PPR_GUIDED_SUBGRAPH([A], max_iterations=0),
              raises("ValueError", match=r"max_iterations"), entry="engine.kg_PPR_GUIDED_SUBGRAPH")

    # ALG-B10.6 weighted search
    refuse(L, "ALG-B10.6", "DijkstraJson weightProp 'cost'",
              call(L, "Graph.KG.TraversalPaths", "DijkstraJson", A, B, "cost", 9999, 10, "out"),
              raises(ANY, match=r"weightProp 'cost' is not supported"), entry="Graph.KG.TraversalPaths.DijkstraJson")
    refuse(L, "ALG-B10.6", "DijkstraJson direction 'up'",
              call(L, "Graph.KG.TraversalPaths", "DijkstraJson", A, B, "weight", 9999, 10, "up"),
              raises(ANY, match=r"direction must be"), entry="Graph.KG.TraversalPaths.DijkstraJson")
    refuse(L, "ALG-B10.6", "DijkstraCost direction 'sideways'",
              call(L, "Graph.KG.TraversalPaths", "DijkstraCost", A, B, 9999, "sideways"),
              raises(ANY, match=r"direction must be"), entry="Graph.KG.TraversalPaths.DijkstraCost")
    refuse(L, "ALG-B10.6", "CALL ivg.shortestPath.weighted weightProp 'cost'",
              cy(L, f"CALL ivg.shortestPath.weighted('{A}', '{B}', 'cost') YIELD path, totalCost RETURN path, totalCost"),
              raises(ANY, match=r"weightProp|cost"), entry="engine.execute_cypher")
    refuse(L, "ALG-B10.6", "CALL ivg.shortestPath.weighted direction 'up'",
              cy(L, f"CALL ivg.shortestPath.weighted('{A}', '{B}', 'weight', 9999, 10, 'up') YIELD path, totalCost "
                    "RETURN path, totalCost"),
              raises(ANY, match=r"direction"), entry="engine.execute_cypher")

    # ALG-B13.93 deprecated Rust build
    for cls in ("Graph.KG.NKGAccel", "Graph.KG.NKGAccelLoader"):
        refuse(L, "ALG-B13.93", f"{cls}.BuildNKGRust", call(L, cls, "BuildNKGRust"),
                  returns(lambda r: "error" in json.loads(str(r)) and "Graph.KG.Traversal.BuildNKG" in json.loads(str(r))["error"],
                          '{"error": "... Graph.KG.Traversal.BuildNKG"}'),
                  entry=f"{cls}.BuildNKGRust (Native API)")

    # ALG-B6.95 arno_call with the library missing (the only branch reachable without libarno_callout.so)
    from iris_vector_graph.stores import arno_bridge
    refuse(L, "ALG-B6.95", "arno_call kg_scc_global, library missing",
              lambda: arno_bridge.arno_call(L.c.conn, "kg_scc_global", "", 10),
              raises("ArnoError", match=r"not available"), entry="stores.arno_bridge.arno_call",
              allowed=[r'^\^IVG\.Deploy\("routines"'])  # first use only: the wrappers' DDL (arno_bridge.py:360-376)
    refuse(L, "ALG-B6.95", "arno_call unknown function name, library missing",
              lambda: arno_bridge.arno_call(L.c.conn, "kg_not_a_kernel", 1),
              raises("ArnoError"), entry="stores.arno_bridge.arno_call")

    # ALG-B13.3 SQL callout wrappers: another library file, or a function they do not use
    lib = str(L.c.call("Graph.KG.ArnoAccel", "LibPath"))
    rout = L.c.sql("SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = 'Graph_KG' "
                   "AND ROUTINE_NAME %STARTSWITH 'ivg_arno_zf_'")
    L.note("ALG-B13.3", "setup: Graph.KG.ArnoAccel.LibPath and wrappers present", lib_path=lib, wrappers=rout)
    refuse(L, "ALG-B13.3", "ivg_arno_zf_probe another library file",
              sql1(L, "SELECT Graph_KG.ivg_arno_zf_probe(?, ?)", "/tmp/rx10-not-the-library.so", "version"),
              raises(ANY, match=r"refused"), entry="SQL function ivg_arno_zf_probe")
    refuse(L, "ALG-B13.3", "ivg_arno_zf_probe a function the wrappers do not use",
              sql1(L, "SELECT Graph_KG.ivg_arno_zf_probe(?, ?)", lib, "kg_build_nkg"),
              raises(ANY, match=r"refused"), entry="SQL function ivg_arno_zf_probe")
    refuse(L, "ALG-B13.3", "ivg_arno_zf_call_2s another library file",
              sql1(L, "SELECT Graph_KG.ivg_arno_zf_call_2s(?, ?, ?, ?)", "/tmp/rx10-not-the-library.so", "version",
                   "", ""),
              raises(ANY, match=r"refused"), entry="SQL function ivg_arno_zf_call_2s")
    refuse(L, "ALG-B13.3", "ivg_arno_zf_call_2s a function the wrappers do not use",
              sql1(L, "SELECT Graph_KG.ivg_arno_zf_call_2s(?, ?, ?, ?)", lib, "kg_build_nkg", "", ""),
              raises(ANY, match=r"refused"), entry="SQL function ivg_arno_zf_call_2s")

    # caller-supplied stores
    # ALG-B5.21: a store without the centrality method refuses, naming the store
    eng21 = caller_engine(L, drop={"execute_betweenness", "execute_closeness"},
                          caps_drop={"betweenness", "closeness"})
    refuse(L, "ALG-B5.21", "caller store without execute_betweenness",
              lambda: eng21.betweenness_centrality(), raises("NotImplementedError", match=r"RX10CallerStore"),
              entry="engine.betweenness_centrality (store=RX10CallerStore)")
    refuse(L, "ALG-B5.21", "caller store without execute_closeness",
              lambda: eng21.closeness_centrality(), raises("NotImplementedError", match=r"RX10CallerStore"),
              entry="engine.closeness_centrality (store=RX10CallerStore)")
    # ALG-B6.8: the path that ran fails -> raised, never "no communities"
    err = IVGResult(columns=["id", "community", "size"], rows=[], error="rx10: the store's path failed")
    eng68 = caller_engine(L, override={
        "execute_leiden": lambda *a, **k: err, "execute_triangle_count": lambda *a, **k: err,
        "execute_scc": lambda *a, **k: err, "execute_k_core": lambda *a, **k: err})
    for m in ("leiden_communities", "triangle_count", "strongly_connected_components", "k_core"):
        refuse(L, "ALG-B6.8", f"{m}: the store's path reports a failure",
                  (lambda mm=m: getattr(eng68, mm)()), raises("RuntimeError", match=rf"{m} failed: rx10"),
                  entry=f"engine.{m} (store=RX10CallerStore)")

    # ALG-B15.2 / B15.3 / B15.10 / B15.11: the reader proof and gate decisions (no IRIS write either way)
    from iris_vector_graph import arno_readers, _arno_gate
    good = {"library": {"version": "arno-callout 1.2.1+abc123", "sha256": {"arm64": "a" * 64}},
            "proven_at": "2026-01-01",
            "algorithms": {"pagerank": {"min_revision": 1, "fixtures": ["f1", "f2", "f3", "f4", "f5"], "repeats": 5}}}
    L.note("ALG-B15.2", "control: a valid proof loads", problems=arno_readers.validate_proof(good))

    def bad(**alg):
        d = json.loads(json.dumps(good))
        d["algorithms"]["pagerank"].update(alg)
        return d
    for what, doc, pat in (("min_revision 0", bad(min_revision=0), r"min_revision"),
                           ("four fixtures", bad(fixtures=["f1", "f2", "f3", "f4"]), r"fixtures"),
                           ("four repeats", bad(repeats=4), r"repeats"),
                           ("bad version form", dict(good, library={"version": "1.2.1", "sha256": {"arm64": "a" * 64}}),
                            r"version"),
                           ("bad sha256", dict(good, library={"version": "arno-callout 1.2.1+abc", "sha256": {"x86_64": "zz"}}),
                            r"sha256")):
        refuse(L, "ALG-B15.2", f"Proof.from_dict {what}", (lambda d=doc: arno_readers.Proof.from_dict(d)),
                  raises("ValueError", match=pat), entry="arno_readers.Proof.from_dict")
    btw = json.loads(json.dumps(good))
    btw["algorithms"]["betweenness"] = dict(good["algorithms"]["pagerank"])
    refuse(L, "ALG-B15.3", "Proof.from_dict naming betweenness", lambda: arno_readers.Proof.from_dict(btw),
              raises("ValueError", match=r"betweenness: not a routed algorithm"), entry="arno_readers.Proof.from_dict")
    readers = arno_readers.read_reader_report(L.eng._store)
    proof_doc = json.loads((Path(__file__).resolve().parents[3] / "docs/dev/arno-reader-proof.json").read_text())
    refuse(L, "ALG-B15.10", "check_proof_against_report: committed proof vs this library report",
              lambda: _arno_gate.check_proof_against_report(proof_doc, readers),
              returns(lambda r: bool(r) or not proof_doc.get("algorithms"), "a non-empty problem list"),
              entry="_arno_gate.check_proof_against_report (the gate's --check)")
    L.note("ALG-B15.10", "observed: ReaderRevisions on AUDITE and the committed proof", readers=readers,
           proof_algorithms={k: v.get("min_revision") for k, v in proof_doc.get("algorithms", {}).items()},
           detect_arno=bool(L.eng._store._detect_arno()))
    refuse(L, "ALG-B15.10", "check_proof_against_report: claim above a reported revision",
              lambda: _arno_gate.check_proof_against_report(good, {"pagerank": 0}),
              returns(lambda r: any("requires revision 1, library reports 0" in p for p in r), "pagerank problem"),
              entry="_arno_gate.check_proof_against_report")
    refuse(L, "ALG-B15.11", "missing_library_action with IVG_REQUIRE_ARNO=1",
              lambda: _arno_gate.missing_library_action({"IVG_REQUIRE_ARNO": "1"}),
              returns(lambda r: r == "fail", "'fail'"), entry="_arno_gate.missing_library_action")
    L.note("ALG-B15.11", "control: missing_library_action without the switch",
           answer=_arno_gate.missing_library_action({}))


# ------------------------------------------------------------------------------------------------ named graph present
def c_named(L):
    L.reset()
    seed_default(L)
    seed_named(L)
    e = L.eng
    L.note("setup", "default chain + named graph rx10g x->y", counts=L.counts(),
           named=e._named_graph_with_edges() if hasattr(e, "_named_graph_with_edges") else None)
    procs = (("ivg.betweenness", "node, score", "betweenness_centrality"),
             ("ivg.closeness", "node, score", "closeness_centrality"),
             ("ivg.eigenvector", "node, score", "eigenvector_centrality"),
             ("ivg.leiden", "node, community", "leiden_communities"),
             ("ivg.triangleCount", "node, triangles", "triangle_count"),
             ("ivg.scc", "node, component", "strongly_connected_components"),
             ("ivg.kcore", "node, coreness", "k_core"))
    for p, y, meth in procs:
        refuse(L, "ALG-B7", f"CALL {p}() with a named graph's edges", cy(L, f"CALL {p}() YIELD {y} RETURN {y}"),
                  raises(ANY, match=rf"engine\.{meth}\(\)"), entry="engine.execute_cypher")
    for fn, args in (("kg_Betweenness", "()"), ("kg_Closeness", "()"), ("kg_Eigenvector", "()"),
                     ("kg_Leiden", "()"), ("kg_TriangleCount", "()"), ("kg_SCC", "()"), ("kg_KCore", "()")):
        refuse(L, "ALG-B7.2", f"SQL {fn} with a named graph's edges", sql1(L, f"SELECT Graph_KG.{fn}{args}"),
                  raises(ANY, match=rf"{fn} reads \^NKG.*graph {G} has edges"), entry=f"SQL function {fn}")
    refuse(L, "ALG-B7.2", "NKGAccel.RefuseMergedGraphs (class method)",
              call(L, "Graph.KG.NKGAccel", "RefuseMergedGraphs", "rx10-probe"),
              raises(ANY, match=rf"graph {G} has edges"), entry="Graph.KG.NKGAccel.RefuseMergedGraphs")
    # ALG-B5.5: a store whose degree method takes no graph fails for a named graph
    inner = IRISGraphStore(L.c.conn, namespace=NS, schema="Graph_KG")

    def old_degree(direction, predicate, top_k):
        return inner.execute_degree_centrality(direction, predicate, top_k)
    eng55 = caller_engine(L, override={"execute_degree_centrality": old_degree})
    refuse(L, "ALG-B5.5", "old-signature degree store, named graph", lambda: eng55.degree_centrality(graph=G),
              raises("TypeError", match=r"graph"), entry="engine.degree_centrality (store=RX10CallerStore)")
    try:
        d = eng55.degree_centrality()
        L.note("ALG-B5.5", "control: the same store answers the default graph", answer=d)
    except Exception as x:  # noqa: BLE001
        L.note("ALG-B5.5", "control: the same store, default graph, raised", error=str(x)[:300])
    try:
        L.note("ALG-B5.5", "control: the product's store answers the named graph",
               answer=e.degree_centrality(graph=G))
    except Exception as x:  # noqa: BLE001
        L.note("ALG-B5.5", "control: the product's store, named graph, raised", error=str(x)[:300])


# ------------------------------------------------------------------------------------------------ rebuild wait (900 s)
def c_b12_wait(L):
    """ALG-B12.3 and ALG-B12.8: a second connection holds ^IVG.NKGBuild; two rebuilds wait NKGBUILDWAIT (900 s)."""
    L.reset()
    seed_default(L)
    holder = L.conn()
    direct = L.conn()
    holder.o.lock("", 5, "^IVG.NKGBuild")
    L.note("ALG-B12.3", "setup: ^IVG.NKGBuild held by another process", holder_pid=holder.pid, direct_pid=direct.pid,
           main_pid=L.c.pid, nkgbuildwait=900)
    out = {}

    def run(name, fn):
        t0 = time.time()
        try:
            out[name] = {"returned": repr(fn())[:300], "seconds": round(time.time() - t0, 1)}
        except Exception as x:  # noqa: BLE001
            out[name] = {"error_type": type(x).__name__, "error": str(x)[:1500], "seconds": round(time.time() - t0, 1)}

    m = journal.mark()
    th = [threading.Thread(target=run, args=("direct", lambda: direct.call("Graph.KG.Traversal", "BuildNKG"))),
          threading.Thread(target=run, args=("sync", lambda: L.eng.sync()))]
    for t in th:
        t.start()
    time.sleep(20)
    still = {n: (n not in out) for n in ("direct", "sync")}
    L.note("ALG-B12.3", "after 20 s both rebuilds still wait for the lock", waiting=still)
    for t in th:
        t.join(timeout=1100)
    holder.o.unlock("", "^IVG.NKGBuild")
    recs = journal.records_since(m, dbs={"/usr/irissys/mgr/audite/"})
    smap = L.smap
    by_pid = {}
    for r in recs:
        if r["g"]:
            by_pid.setdefault(r["p"], []).append(r)

    def rec(statement, case, name, pid, pat, allowed_pat):
        o = out.get(name, {"error": "thread did not finish"})
        import re
        mine = by_pid.get(pid, [])
        net = journal.net_effect(mine)
        changed = {g: v for g, v in net.items() if not (allowed_pat and re.search(allowed_pat, g))}
        ok = "error" in o and re.search(pat, o["error"], re.S) is not None and o.get("seconds", 0) >= 890
        unchanged = not changed
        L.cases.append({
            "statement": statement, "case": case, "entry": name, "expect": f"raises /{pat}/ after >= 890 s",
            "refused_as_stated": ok, "why": json.dumps(o)[:600], "exception": o, "seconds": o.get("seconds"),
            "journal": {"records_of_this_process": len(mine), "net_changed_nodes": len(net),
                        "changed_outside_allowed": sorted(changed)[:60],
                        "changed_stores": sorted({journal.store_of(g, smap) for g in changed}),
                        "allowed_patterns": [allowed_pat] if allowed_pat else [], "window_records_all_pids": len(recs),
                        "pids": sorted(by_pid)},
            "unchanged": unchanged,
            "outcome": "holds-live" if ok and unchanged else ("refused-but-changed" if ok else "not-refused-as-stated")})
        print(f"[{'OK ' if ok and unchanged else 'BAD'}] {statement} {case} :: {json.dumps(o)[:300]}", flush=True)
    rec("ALG-B12.3", "BuildNKG waits NKGBUILDWAIT for another build's lock, then fails and says so", "direct",
        direct.pid, r"another \^NKG build held \^IVG\.NKGBuild for 900 seconds", None)
    # engine.sync() rebuilds ^KG from the tables first (BuildKG, by design), then ^NKG, which fails
    rec("ALG-B12.8", "engine.sync() whose ^NKG rebuild fails raises naming the server method", "sync",
        L.c.pid, r"BuildNKG", r"^\^KG\(")
    L.drop(direct)
    L.drop(holder)


CASES = [("b7_4", c_b7_4), ("default", c_default), ("named", c_named)]
LONG = [("b12_wait", c_b12_wait)]


def main():
    args = sys.argv[1:]
    out = "results.json"
    if args[:1] == ["--out"]:
        out, args = args[1], args[2:]
    only = args or None
    cases = CASES + LONG if only else CASES
    with Lane("10") as L:
        L.reset()
        L.control()
        run_cases(L, cases, only)
        L.reset()
        L.save(out)


if __name__ == "__main__":
    main()
