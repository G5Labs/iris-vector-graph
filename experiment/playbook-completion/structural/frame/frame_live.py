#!/usr/bin/env python3
"""§3.6 frame per statement-shape class, live on AUDITD with the IRIS journal as oracle.

    locks.sh iris timeout 1500 python frame_live.py run <group> [<group> ...]     # groups: see GROUPS
    locks.sh iris timeout 600 python frame_live.py control                         # registered self-test

Per action: lib.reset(); the base data (BASE); the action's own setup; then journal mark -> the action through the
product's own API on one connection -> commit -> journal records of that connection's server process in AUDITD's
database -> frame_check.check against the entry point's declared writes (declared.py: footprints/NN.json or
correspondence.json, never widened) and the action's keys. Writes outside the capture (setup) are not judged.
Every captured process records only this harness's connection: other processes (another lane, a JOB the product
starts) are outside the pid filter and reported separately when they wrote AUDITD inside the window.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "live"))
sys.path.insert(0, str(HERE))
import lib  # noqa: E402
import frame_check as FC  # noqa: E402
import declared as DECL  # noqa: E402

J = lib.J
OUT = lib.OUT / "frame"

C_VER = (r'^\^KG\("__version"\)$', 'graph version stamp ^KG("__version"): $Increment on every content write '
         '(footprints/15.json notes; Adjacency.cls bumps)')
C_NKGVER = (r'^\^NKG\("\$meta","version"\)$', 'interned-snapshot version ^NKG("$meta","version") (footprints/15.json notes)')
C_HEAD = (r'^\^IVG\.Ledger\("(head|stmtNext)"\)$', 'ledger head / statement-id counters (correspondence.json commit writes)')
C_STATS = (r'^\^Graph\.KG\.LedgerStats[DI]', 'the ledger_stats counter row (LedgerStats.Bump; declared ledger_stats)')
C_ADJNL = (r'^\^IVG\.AdjNoLock', '^IVG.AdjNoLock(g) $Increment when the shared writer lock is not granted (Adjacency.cls:61-73)')
def C_GRAPH(g):
    """Per-graph metadata nodes a node/edge write of graph g sets (subscripted by the graph key, 0 = default)."""
    gk = '0' if g in (None, "", 0) else f'"{g}"'
    return [(rf'^\^KG\("tlast",{gk}\)$', "latest-event completeness flag of the action's graph (TemporalIndex.cls:87-92)"),
            (rf'^\^KG\("(deg2p|deg2p_exact|deg2p_exact_merged|degw)",{gk}\)$', "per-graph derived counts invalidated (Adjacency.cls:439, InvalidateDerived)"),
            (r'^\^NKG\("\$meta","stale"\)$', "interned snapshot marked stale when a named graph's last edge goes (TraversalBuild.cls:393-401)"),
            (r'^\^NKG\("\$meta","invalidated"\)$', "interned snapshot invalidation mark (Eraser.cls:1038-1042 InvalidateDerived)")]


WK_NKG = [("^NKG", "the interned snapshot is dropped whole (GraphIndex.cls:18-27 DropNKG via Eraser.cls:1036-1045 "
                    "InvalidateDerived: 'a per-graph erase cannot say which parts of it are gone'), declared '^NKG (DropNKG)' "
                    "(correspondence.json erase-graph, erase-nodes) and ^NKG (footprints/17.json delete_edges)"),
          ("^IVG.AlgoCache", "every graph's algorithm cache entries (Eraser.cls:1047-1052, ADR-0004), declared ^IVG.AlgoCache")]
DDL_NOTE = "the route's DROP TABLE (declared 'after commit DROP TABLE routes', correspondence.json erase-graph)"


C_STOP = (r'^\^BM25Idx\("__stop__"', 'BM25 stopword list ^BM25Idx("__stop__",word) (InitStopwords, footprints/07.json)')

BASE_IDS = ["fr:a", "fr:b", "fr:c", "fz:x", "fz:y", "fd:p", "fd:q"]
ALL_KEYS = BASE_IDS + ["fg", "fz"]


def base(c, e):
    """Graph fg: fr:a -R-> fr:b -R-> fr:c (fr:a labelled L, name=a); bystander graph fz: fz:x -R-> fz:y; default
    graph: fd:p -R-> fd:q."""
    for n in ("fr:a", "fr:b", "fr:c"):
        e.create_node(n, labels=["L"], properties={"name": n[-1]}, graph="fg")
    e.create_edge("fr:a", "R", "fr:b", graph="fg")
    e.create_edge("fr:b", "R", "fr:c", graph="fg")
    for n in ("fz:x", "fz:y"):
        e.create_node(n, labels=["L"], properties={"name": n[-1]}, graph="fz")
    e.create_edge("fz:x", "R", "fz:y", graph="fz")
    for n in ("fd:p", "fd:q"):
        e.create_node(n, labels=["L"], properties={"name": n[-1]})
    e.create_edge("fd:p", "R", "fd:q")
    c.conn.commit()


def vec(i=1.0):
    return [0.1 * i, 0.2, 0.3, 0.4]


# --------------------------------------------------------------------------------------------- the action table
# Each action: id, module, entry (footprint id), run(c, e, ctx) -> result, keys (list or callable(ctx, res)),
# optional: setup(c, e) -> ctx, counters, int_keys(ctx, res), any_key, ledger (enable before setup), note.

def A(id_, module, entry, run, keys, **kw):
    d = {"id": id_, "module": module, "entry": entry, "run": run, "keys": keys}
    d.update(kw)
    return d


def _ledger(e):
    return e.ledger


def _cs(msg="frame", **kw):
    from iris_vector_graph.ledger import Changeset
    return Changeset(actor="audit:frame", actor_type="ingest", message=msg, **kw)


def g02():
    return [A("02-set-multigraph", "02", "py:IRISGraphEngine.set_multigraph",
              lambda c, e, x: e.set_multigraph("fg", True), ["fg"])]


def g03():
    return [
        A("03-create-node", "03", "py:IRISGraphEngine.create_node",
          lambda c, e, x: e.create_node("fr:n", labels=["L"], properties={"k": "v"}, graph="fg"), ["fr:n"], counters=[C_VER]),
        A("03-create-edge", "03", "py:IRISGraphEngine.create_edge",
          lambda c, e, x: e.create_edge("fr:a", "S", "fr:c", qualifiers={"w": "1"}, graph="fg"), ["fr:a", "fr:c"], counters=[C_VER]),
        A("03-delete-edge", "03", "py:IRISGraphEngine.delete_edge",
          lambda c, e, x: e.delete_edge("fr:a", "R", "fr:b", graph="fg"), ["fr:a", "fr:b"], counters=[C_VER, C_NKGVER]),
        A("03-delete-node", "03", "py:IRISGraphEngine.delete_node",
          lambda c, e, x: e.delete_node("fr:c", graph="fg"), ["fr:c"], counters=[C_VER, C_NKGVER]),
        A("03-store-node", "03", "py:IRISGraphEngine.store_node",
          lambda c, e, x: e.store_node("fr:a", properties={"k2": "v2"}, labels=["M"], graph="fg"), ["fr:a"], counters=[C_VER, C_NKGVER]),
        A("03-store-edge", "03", "py:IRISGraphEngine.store_edge",
          lambda c, e, x: e.store_edge("fr:a", "R", "fr:b", qualifiers={"q": "2"}, graph="fg"), ["fr:a", "fr:b"], counters=[C_VER, C_NKGVER]),
        A("03-bulk-create-nodes", "03", "py:IRISGraphEngine.bulk_create_nodes",
          lambda c, e, x: e.bulk_create_nodes([{"id": "fr:m1", "labels": ["L"], "properties": {"k": "1"}}, {"id": "fr:m2"}], graph="fg"),
          ["fr:m1", "fr:m2"], counters=[C_VER, C_NKGVER]),
        A("03-bulk-create-edges", "03", "py:IRISGraphEngine.bulk_create_edges",
          lambda c, e, x: e.bulk_create_edges([{"source_id": "fr:a", "predicate": "B", "target_id": "fr:c"}], graph="fg",
                                              auto_sync=False), ["fr:a", "fr:c"], counters=[C_VER, C_NKGVER]),
        A("03-bulk-delete-nodes", "03", "py:IRISGraphEngine.bulk_delete_nodes",
          lambda c, e, x: str(e.bulk_delete_nodes(["fr:c"], graph="fg")), ["fr:c"], counters=[C_VER, C_NKGVER]),
        A("03-set-edge-weight", "03", "py:IRISGraphEngine.set_edge_weight",
          lambda c, e, x: e.set_edge_weight("fd:p", "R", "fd:q", 2.5), ["fd:p", "fd:q"], counters=[C_VER, C_NKGVER]),
        A("03-bulk-ingest-edges", "03", "py:IRISGraphEngine.bulk_ingest_edges",
          lambda c, e, x: e.bulk_ingest_edges([{"source_id": "fd:p", "target_id": "fd:n"}], predicate="K", auto_sync=False),
          ["fd:p", "fd:n"], counters=[C_VER, C_NKGVER]),
        A("03-erase-all", "03", "py:IRISGraphEngine.erase_all", lambda c, e, x: e.erase_all(), ALL_KEYS, any_key=True,
          note="whole-namespace erase: store level only; key level replaced by 'whole-store action'"),
    ]


def g04():
    return [
        A("04-sync", "04", "py:IRISGraphEngine.sync", lambda c, e, x: e.sync(), ALL_KEYS, counters=[C_VER, C_NKGVER], any_key=True,
          note="namespace-wide rebuild: keys are every base id and graph"),
        A("04-rebuild-kg", "04", "cls:Graph.KG.TraversalBuild.BuildKG", lambda c, e, x: e.rebuild_kg(), ALL_KEYS,
          counters=[C_VER, C_NKGVER], any_key=True, note="namespace-wide rebuild of ^KG: whole-store class"),
        A("04-rebuild-nkg", "04", "cls:Graph.KG.TraversalBuild.BuildNKG", lambda c, e, x: e.rebuild_nkg(), ALL_KEYS,
          counters=[C_VER, C_NKGVER], any_key=True, note="namespace-wide rebuild of ^NKG: whole-store class"),
        A("04-backfill-degp", "04", "cls:Graph.KG.TraversalBuild.BackfillDegp", lambda c, e, x: e.backfill_degp(), ALL_KEYS,
          counters=[C_VER]),
        A("04-reweight", "04", "cls:Graph.KG.Adjacency.Reweight",
          lambda c, e, x: c.call("Graph.KG.Adjacency", "Reweight", "fg", "fr:a", "R", "fr:b", 3), ["fr:a", "fr:b"],
          counters=[C_VER]),
        A("04-degree-cache", "04", "cls:Graph.KG.Adj.Degree",
          lambda c, e, x: c.call("Graph.KG.Adj", "Degree", "fg", "fr:a", ""), ["fr:a"], counters=[C_VER]),
    ]


def g05():
    T0 = 1_700_000_000
    def seed_t(c, e):
        e.create_edge_temporal("fr:a", "T", "fr:b", timestamp=T0, graph="fg")
        e.create_edge_temporal("fz:x", "T", "fz:y", timestamp=T0, graph="fz")
        c.conn.commit()
        return {}
    return [
        A("05-create-edge-temporal", "05", "py:IRISGraphEngine.create_edge_temporal",
          lambda c, e, x: e.create_edge_temporal("fr:a", "T", "fr:c", timestamp=T0 + 60, graph="fg"), ["fr:a", "fr:c"],
          counters=[C_VER, C_NKGVER] + C_GRAPH("fg")),
        A("05-bulk-create-edges-temporal", "05", "py:IRISGraphEngine.bulk_create_edges_temporal",
          lambda c, e, x: int(e.bulk_create_edges_temporal([{"s": "fr:b", "p": "T", "o": "fr:c", "ts": T0 + 5}], graph="fg")),
          ["fr:b", "fr:c"], counters=[C_VER, C_NKGVER] + C_GRAPH("fg")),
        A("05-delete-edge-temporal", "05", "py:IRISGraphEngine.delete_edge_temporal",
          lambda c, e, x: e.delete_edge_temporal("fr:a", "T", "fr:b", T0, graph="fg"), ["fr:a", "fr:b"], setup=seed_t,
          counters=[C_VER, C_NKGVER] + C_GRAPH("fg")),
        A("05-purge-before", "05", "py:IRISGraphEngine.purge_before", lambda c, e, x: e.purge_before(T0 + 1), ["fd:p", "fd:q"],
          setup=lambda c, e: (seed_t(c, e), e.create_edge_temporal("fd:p", "T", "fd:q", timestamp=T0), c.conn.commit()) and {},
          counters=[C_VER, C_NKGVER] + C_GRAPH(None),
          note="default graph only (temporal.py:624-630); temporal edges of graphs fg and fz at the same time must stay"),
        A("05-rebuild-temporal-latest", "05", "py:IRISGraphEngine.rebuild_temporal_latest",
          lambda c, e, x: e.rebuild_temporal_latest(graph="fg"), ["fg"], setup=seed_t),
        A("05-set-temporal-structural", "05", "py:IRISGraphEngine.set_temporal_structural",
          lambda c, e, x: e.set_temporal_structural("T", False, graph="fg"), ["fg", "T"],
          note="a change from the default (structural rows on): True on a fresh graph journals nothing"),
        A("05-backfill-structural-rows", "05", "py:IRISGraphEngine.backfill_temporal_structural_rows",
          lambda c, e, x: e.backfill_temporal_structural_rows("T", graph="fg"), ["fr:a", "fr:b"],
          setup=lambda c, e: (seed_t(c, e), e.set_temporal_structural("T", False, graph="fg"),
                              e.drop_temporal_structural_rows("T", graph="fg"), e.set_temporal_structural("T", True, graph="fg"),
                              c.conn.commit()) and {},
          counters=[C_VER, C_NKGVER]),
        A("05-drop-structural-rows", "05", "py:IRISGraphEngine.drop_temporal_structural_rows",
          lambda c, e, x: str(e.drop_temporal_structural_rows("T", graph="fg")), ["fg", "fr:a", "fr:b"],
          setup=lambda c, e: (seed_t(c, e), e.set_temporal_structural("T", True, graph="fg"),
                              e.backfill_temporal_structural_rows("T", graph="fg"), e.set_temporal_structural("T", False, graph="fg"),
                              c.conn.commit()) and {},
          counters=[C_VER, C_NKGVER]),
    ]


def g06():
    return [
        A("06-store-embedding-default", "06", "py:IRISGraphEngine.store_embedding",
          lambda c, e, x: e.store_embedding("fd:p", vec()), ["fd:p"]),
        A("06-store-embedding-graph-route", "06", "py:IRISGraphEngine.store_embedding",
          lambda c, e, x: e.store_embedding("fr:a", vec(), graph="fg"), ["fr:a", "fg"], owned_tables=_routes("fg"),
          note="first vector of graph fg: creates the routed table (DDL) and its registry row"),
        A("06-store-embeddings", "06", "py:IRISGraphEngine.store_embeddings",
          lambda c, e, x: e.store_embeddings([{"node_id": "fd:p", "embedding": vec()}, {"node_id": "fd:q", "embedding": vec(2)}]),
          ["fd:p", "fd:q"]),
        A("06-store-edge-embedding", "06", "py:IRISGraphEngine.store_edge_embedding",
          lambda c, e, x: e.store_edge_embedding("fd:p", "R", "fd:q", vec()), ["fd:p", "fd:q"]),
        A("06-enqueue", "06", "py:IRISGraphEngine.enqueue_for_embedding",
          lambda c, e, x: e.enqueue_for_embedding(["fd:p"]), ["fd:p"],
          counters=[(r'^\^EmbedQueue\("\$seq"\)$', "queue sequence counter ^EmbedQueue(\"$seq\") (footprints/06.json)")]),
        A("06-ivf-build", "06", "py:IRISGraphEngine.ivf_build",
          lambda c, e, x: e.ivf_build("fi", nlist=1), ["fi"],
          setup=lambda c, e: (e.store_embedding("fd:p", vec()), e.store_embedding("fd:q", vec(2)), c.conn.commit()) and {}),
        A("06-ivf-insert", "06", "py:IRISGraphEngine.ivf_insert",
          lambda c, e, x: e.ivf_insert("fi", "fd:n", vec(3)), ["fi"],
          setup=lambda c, e: (e.store_embedding("fd:p", vec()), e.store_embedding("fd:q", vec(2)), e.ivf_build("fi", nlist=1), c.conn.commit()) and {}),
        A("06-ivf-delete", "06", "py:IRISGraphEngine.ivf_delete",
          lambda c, e, x: e.ivf_delete("fi", "fd:q"), ["fi"],
          setup=lambda c, e: (e.store_embedding("fd:p", vec()), e.store_embedding("fd:q", vec(2)), e.ivf_build("fi", nlist=1), c.conn.commit()) and {}),
        A("06-ivf-drop", "06", "py:IRISGraphEngine.ivf_drop", lambda c, e, x: e.ivf_drop("fi"), ["fi"],
          setup=lambda c, e: (e.store_embedding("fd:p", vec()), e.ivf_build("fi", nlist=1), c.conn.commit()) and {}),
        A("06-vec-create", "06", "py:IRISGraphEngine.vec_create_index", lambda c, e, x: e.vec_create_index("fv", 4), ["fv"]),
        A("06-vec-insert", "06", "py:IRISGraphEngine.vec_insert", lambda c, e, x: e.vec_insert("fv", "d1", vec()), ["fv"],
          setup=lambda c, e: (e.vec_create_index("fv", 4), c.conn.commit()) and {}),
        A("06-vec-build", "06", "py:IRISGraphEngine.vec_build", lambda c, e, x: e.vec_build("fv"), ["fv"],
          setup=lambda c, e: (e.vec_create_index("fv", 4), e.vec_insert("fv", "d1", vec()), e.vec_insert("fv", "d2", vec(2)), c.conn.commit()) and {}),
        A("06-vec-drop", "06", "py:IRISGraphEngine.vec_drop", lambda c, e, x: e.vec_drop("fv"), ["fv"],
          setup=lambda c, e: (e.vec_create_index("fv", 4), c.conn.commit()) and {}),
        A("06-plaid-build", "06", "py:IRISGraphEngine.plaid_build",
          lambda c, e, x: e.plaid_build("fp", [{"id": "d1", "tokens": [vec(), vec(2)]}, {"id": "d2", "tokens": [vec(3)]}], n_clusters=1, dim=4),
          ["fp"]),
        A("06-plaid-drop", "06", "py:IRISGraphEngine.plaid_drop", lambda c, e, x: e.plaid_drop("fp"), ["fp"],
          setup=lambda c, e: (e.plaid_build("fp", [{"id": "d1", "tokens": [vec()]}], n_clusters=1, dim=4), c.conn.commit()) and {}),
    ]


def g07():
    def txt(c, e):
        e.store_node("fr:a", properties={"txt": "alpha beta gamma"}, graph="fg")
        e.store_node("fr:b", properties={"txt": "beta delta"}, graph="fg")
        c.conn.commit()
        return {}

    def mk(c, e):
        txt(c, e)
        e.bm25_build("fb", ["txt"], graph="fg")
        c.conn.commit()
        return {}
    return [
        A("07-bm25-build", "07", "eng:IRISGraphEngine.bm25_build", lambda c, e, x: e.bm25_build("fb", ["txt"], graph="fg"),
          ["fb"], counters=[C_STOP], setup=txt),
        A("07-bm25-insert", "07", "eng:IRISGraphEngine.bm25_insert", lambda c, e, x: e.bm25_insert("fb", "fr:n", "hello world"),
          ["fb"], setup=mk, counters=[C_STOP]),
        A("07-bm25-delete", "07", "eng:IRISGraphEngine.bm25_delete", lambda c, e, x: e.bm25_delete("fb", "fr:a"), ["fb"], setup=mk),
        A("07-bm25-upgrade", "07", "eng:IRISGraphEngine.bm25_upgrade", lambda c, e, x: e.bm25_upgrade("fb"), ["fb"], setup=mk),
        A("07-bm25-drop", "07", "eng:IRISGraphEngine.bm25_drop", lambda c, e, x: e.bm25_drop("fb"), ["fb"], setup=mk),
    ]


def g08():
    return [
        A("08-cypher-create", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("CREATE (n:CyL {id: 'fd:cy', name: 'cy'}) RETURN n.id")),
          ["fd:cy"], counters=[C_VER, C_NKGVER]),
        A("08-cypher-set", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("MATCH (n {id: 'fd:p'}) SET n.k3 = 'v3' RETURN n.id")), ["fd:p"],
          counters=[C_VER, C_NKGVER]),
        A("08-cypher-merge-rel", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("MATCH (a {id: 'fd:p'}), (b {id: 'fd:q'}) MERGE (a)-[:M]->(b)")),
          ["fd:p", "fd:q"], counters=[C_VER, C_NKGVER]),
        A("08-cypher-delete-rel", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("MATCH (a {id: 'fd:p'})-[r:R]->(b {id: 'fd:q'}) DELETE r")),
          ["fd:p", "fd:q"], counters=[C_VER, C_NKGVER]),
        A("08-cypher-detach-delete", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("MATCH (n {id: 'fd:q'}) DETACH DELETE n")), ["fd:q"],
          counters=[C_VER, C_NKGVER]),
        A("08-map-sql-table", "08", "eng:IRISGraphEngine.map_sql_table",
          lambda c, e, x: e.map_sql_table("Graph_KG.rdf_namespaces", "prefix", "FrNs"), ["FrNs"]),
    ]


def g09():
    return [
        A("09-gen-mode", "09", "cls:Graph.KG.Cypher.Gen.Mode", lambda c, e, x: c.call("Graph.KG.Cypher.Gen", "Mode", "off"), [],
          note="process-private ^||IVG.CypherGenMode only: no journaled write is expected"),
        A("09-gen-dropall", "09", "cls:Graph.KG.Cypher.Gen.DropAll", lambda c, e, x: str(c.call("Graph.KG.Cypher.Gen", "DropAll")),
          [], any_key=True, note="Kill ^IVG.CypherCompiled and delete package IVGC (none generated in AUDITD)"),
        A("09-native-read-off", "09", "eng:IRISGraphEngine.execute_cypher[native]",
          lambda c, e, x: (c.call("Graph.KG.Cypher.Gen", "Mode", "off"),
                           str(e.execute_cypher("MATCH (n:L) RETURN n.id ORDER BY n.id LIMIT 3"))[:200])[1],
          [], note="compile mode off in this process (no generated class compiled): a native read writes nothing persistent"),
    ]


def g10():
    return [
        A("10-pagerank-cache", "10", "eng:IRISGraphEngine.kg_PAGERANK", lambda c, e, x: str(e.kg_PAGERANK())[:200], [],
          counters=[(r'^\^IVG\.AlgoCache\(0,"pagerank"', 'AlgoCache.Put ^IVG.AlgoCache(0,"pagerank",hash) on a miss (footprints/10.json)')]),
        A("10-ppr-cache", "10", "eng:IRISGraphEngine.kg_PERSONALIZED_PAGERANK",
          lambda c, e, x: str(e.kg_PERSONALIZED_PAGERANK(["fd:p"]))[:200], ["fd:p", "fd:q"],
          counters=[(r'^\^IVG\.AlgoCache\(', 'AlgoCache.Put ^IVG.AlgoCache(g,"ppr",hash) on a miss (footprints/10.json)')]),
        A("10-pagerank-runjson", "10", "cls:Graph.KG.PageRank.RunJson",
          lambda c, e, x: str(c.call("Graph.KG.PageRank", "RunJson", '["fd:p"]', 0.85, 10))[:200], ALL_KEYS),
        A("10-degree-centrality", "10", "eng:IRISGraphEngine.degree_centrality",
          lambda c, e, x: str(e.degree_centrality(graph="fg"))[:200], ["fg", "fr:a", "fr:b", "fr:c"]),
        A("10-triangle-count", "10", "eng:IRISGraphEngine.triangle_count", lambda c, e, x: str(e.triangle_count())[:200], ALL_KEYS),
        A("10-rebuild-nkg", "10", "eng:IRISGraphEngine.rebuild_nkg", lambda c, e, x: e.rebuild_nkg(), ALL_KEYS,
          counters=[C_VER, C_NKGVER], any_key=True, note="namespace-wide rebuild of ^NKG: whole-store class"),
    ]


def _commit_basic(c, e, idem=None):
    led = e.ledger
    ch = _cs("tenant", idempotency_key=idem) if idem else _cs("tenant")
    ch.create_node("lt|a", labels=["T"], properties={"k": "v"})
    ch.create_node("lt|b")
    ch.create_relationship("lt|a", "R", "lt|b")
    return led.commit(ch)


def _rev(info) -> dict:
    return {"seq": int(info.seq), "rev": str(info.revision_id)}


def rev_counters(extra=()):
    """Counter nodes of one new revision: only that revision's seq and id (read from the action's result)."""
    def f(ctx, res):
        out = [C_HEAD, C_STATS, C_VER, C_NKGVER] + list(extra)
        for r in (res if isinstance(res, list) else [res]):
            if isinstance(r, dict) and r.get("seq") is not None:
                out += [(rf'^\^IVG\.Ledger\("(rec|idBySeq|redactedRev)",{r["seq"]}[,)]', f"records/seq index of the new revision {r['seq']}"),
                        (rf'^\^IVG\.Ledger\("revById","{r["rev"]}"\)', f"revision id index of {r['rev']}")]
        return out
    return f


def rev_keys(base_keys):
    def f(ctx, res):
        k = list(base_keys)
        for r in (res if isinstance(res, list) else [res]):
            if isinstance(r, dict) and r.get("rev"):
                k.append(r["rev"])
        return k
    return f


def g11():
    def enabled(c, e):
        e.ledger.enable()
        c.conn.commit()
        return {}

    def seeded(c, e):
        enabled(c, e)
        r = _commit_basic(c, e)
        c.conn.commit()
        return _rev(r.revision)

    def commit_ops(c, e, x):
        ch = _cs("ops")
        ch.create_node("lt|c", labels=["T"], properties={"p": "1"})
        ch.set_property("lt|a", "k", "v2")
        ch.add_label("lt|b", "U")
        ch.create_relationship("lt|b", "S", "lt|c", qualifiers={"w": "1"})
        return _rev(e.ledger.commit(ch).revision)

    def commit_detach(c, e, x):
        ch = _cs("detach")
        ch.delete_node("lt|a", mode="detach")
        return _rev(e.ledger.commit(ch).revision)

    def commit_temporal(c, e, x):
        ch = _cs("temporal")
        ch.create_temporal_edge("lt|a", "TT", "lt|b", ts=1_700_000_000)
        return _rev(e.ledger.commit(ch).revision)

    def replay(c, e, x):
        r = _commit_basic(c, e, idem="frame-idem-1")
        return dict(_rev(r.revision), replayed=bool(r.replayed))

    def replay_setup(c, e):
        enabled(c, e)
        _commit_basic(c, e, idem="frame-idem-1")
        c.conn.commit()
        return {}

    def reifier_delete_rel(c, e):
        seeded(c, e)
        eid = c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='lt|a' AND p='R' AND o_id='lt|b'")[0][0]
        e.reify_edge(int(eid), reifier_id="lt|re1")
        c.conn.commit()
        return {"edge_id": int(eid)}

    def delete_rel(c, e, x):
        ch = _cs("delete rel")
        ch.delete_relationship(("lt|a", "R", "lt|b"))
        return _rev(e.ledger.commit(ch).revision)

    def adoption_setup(c, e):
        seeded(c, e)
        e.ledger.disable()
        c.conn.commit()
        e.delete_edge("lt|a", "R", "lt|b")
        e.create_node("lt|d")
        c.conn.commit()
        return {}

    def reenable(c, e, x):
        e.ledger.enable()
        head = int(c.o.get("^IVG.Ledger", "head") or 0)
        rows = c.sql("SELECT seq, revision_id FROM Graph_KG.ledger_revisions WHERE seq > 1 ORDER BY seq")
        return [{"seq": int(a), "rev": str(b)} for a, b in rows if int(a) > 2] + [{"head": head}]

    def genesis(c, e, x):
        info = e.ledger.enable()
        return _rev(info)

    def post_commit(c, e, x):
        ch = _cs("pcp")
        ch.create_node("lt|e")
        ch.post_commit_properties = {"lt|e": {"pc": "1"}}
        return _rev(e.ledger.commit(ch).revision)

    META = (r'^\^IVG\.Ledger\("meta"', 'ledger state ^IVG.Ledger("meta",*) (Enable/Disable/SetStrict)')
    return [
        A("11-enable-genesis", "11", "corr:enable-genesis", genesis, rev_keys(ALL_KEYS + ["lt|a", "lt|b"]),
          setup=_noop_bypass, counters=rev_counters([META]),
          note="genesis captures every existing row (base + lt|a, lt|b): keys are all of them"),
        A("11-commit-basic", "11", "corr:commit", lambda c, e, x: _rev(_commit_basic(c, e).revision),
          rev_keys(["lt|a", "lt|b"]), setup=enabled, counters=rev_counters()),
        A("11-commit-ops", "11", "corr:commit", commit_ops, rev_keys(["lt|a", "lt|b", "lt|c"]), setup=seeded,
          counters=rev_counters()),
        A("11-commit-detach", "11", "corr:commit", commit_detach, rev_keys(["lt|a"]), setup=seeded, counters=rev_counters()),
        A("11-commit-temporal", "11", "corr:commit", commit_temporal, rev_keys(["lt|a", "lt|b"]), setup=seeded,
          counters=rev_counters(C_GRAPH(None))),
        A("11-commit-delete-rel-reified", "11", "corr:commit", delete_rel, rev_keys(["lt|a", "lt|b", "lt|re1"]),
          setup=reifier_delete_rel, counters=rev_counters(),
          note="reaches LedgerApply.cls:664 (DELETE FROM rdf_reifications of the deleted edge)"),
        A("11-replay", "11", "corr:replay", replay, ["lt|a", "lt|b", "frame-idem-1"], setup=replay_setup, counters=[C_STATS]),
        A("11-disable", "11", "corr:disable-strict", lambda c, e, x: e.ledger.disable(), [], setup=seeded,
          counters=[C_STATS, META]),
        A("11-set-strict", "11", "corr:disable-strict", lambda c, e, x: e.ledger.set_strict(True), [], setup=seeded,
          counters=[C_STATS, META]),
        A("11-reenable-adoption", "11", "corr:reenable-adoption", reenable, rev_keys(["lt|a", "lt|b", "lt|d"]), also_declared=[("11", "corr:commit")],
          setup=adoption_setup, counters=rev_counters([META]),
          note="adoption of a delete_rel made while disabled reaches LedgerGenesis.cls:110-111"),
        A("11-post-commit-properties", "11", "corr:commit", post_commit, rev_keys(["lt|e"]), setup=seeded,
          counters=rev_counters()),
    ]


def _noop_bypass(c, e):
    e.create_node("lt|a")
    e.create_node("lt|b")
    e.create_edge("lt|a", "R", "lt|b")
    c.conn.commit()
    return {}


def g12():
    def rich(c, e):
        e.store_embedding("fr:a", vec(), graph="fg")
        e.store_embedding("fz:x", vec(), graph="fz")
        e.rebuild_nkg()
        c.conn.commit()
        return {}
    return [
        A("12-erase-graph", "12", "corr:erase-graph", lambda c, e, x: e.erase_graph("fg"), ["fg", "fr:a", "fr:b", "fr:c"],
          setup=rich, counters=[C_VER, C_NKGVER] + C_GRAPH("fg"), owned_tables=_routes("fg"), owned_table_keys=True,
          whole_kills=WK_NKG, ddl_catalog=True,
          note="graph fg with a routed vector table and a built ^NKG; bystander graph fz has its own route"),
        A("12-erase-nodes-prefix", "12", "corr:erase-nodes",
          lambda c, e, x: e.delete_nodes_by_prefix("fr:", graph="fg"), ["prefix:fr:"], setup=rich,
          counters=[C_VER, C_NKGVER] + C_GRAPH("fg"), whole_kills=WK_NKG),
        A("12-drop-graph", "12", "corr:erase-graph", lambda c, e, x: e.drop_graph("fg"), ["fg", "fr:a", "fr:b", "fr:c"],
          setup=rich, counters=[C_VER, C_NKGVER] + C_GRAPH("fg"), owned_tables=_routes("fg"), owned_table_keys=True,
          whole_kills=WK_NKG, ddl_catalog=True),
        A("12-erase-all", "12", "corr:erase-edges-all", lambda c, e, x: str(c.call("Graph.KG.Eraser", "EraseAll")), ALL_KEYS,
          setup=rich, any_key=True, ddl_catalog=True),
    ]


def g13():
    def tenant(c, e):
        e.ledger.enable()
        ch = _cs("tenant a", idempotency_key="frame-red-1")
        ch.create_node("ta|1", properties={"k": "v"})
        ch.create_node("ta|2")
        ch.create_relationship("ta|1", "R", "ta|2")
        ra = e.ledger.commit(ch)
        ch = _cs("tenant b")
        ch.create_node("tb|1")
        rb = e.ledger.commit(ch)
        c.conn.commit()
        # bypass delete of the recorded edge leaves its ("tuple") entry (F-0303): DropStatements' tuple kill
        e.delete_edge("ta|1", "R", "ta|2")
        c.conn.commit()
        c.call("Graph.KG.Eraser", "EraseNodes", "", "ta|")
        c.conn.commit()
        return {"seq_a": ra.revision.seq, "rev_a": ra.revision.revision_id, "seq_b": rb.revision.seq}

    def redact(c, e, x):
        r = e.ledger.redact(None, prefix="ta")
        head = int(c.o.get("^IVG.Ledger", "head") or 0)
        row = c.sql("SELECT revision_id FROM Graph_KG.ledger_revisions WHERE seq = ?", head)
        return [{"seq": head, "rev": str(row[0][0]) if row else ""}, {"receipt": str(r)[:300]}]

    def keys(x, r):
        k = ["prefix:ta|", x["rev_a"], "frame-red-1"]
        return k + [d["rev"] for d in (r or []) if isinstance(d, dict) and d.get("rev")]

    return [A("13-redact", "13", "corr:redact-batch", redact, keys, setup=tenant, also_declared=[("13", "corr:redact-final")],
              int_keys=lambda x, r: [x["seq_a"]],
              counters=rev_counters([
                  (r'^\^IVG\.Ledger\("redacting"', 'the redaction marker and its scan state (redact-batch writes)'),
                  (r'^\^IVG\.Ledger\("idemRedacted",', 'sha256 of the redacted idempotency key (redact-batch writes)')]),
              note="declared: redact-batch + redact-final; tenant b's revision (seq_b) must not be written; "
                   "DropStatements' tuple kill (LedgerRedact.cls:465) reached via F-0303's leftover tuple")]


def g14():
    def seeded(c, e):
        e.ledger.enable()
        _commit_basic(c, e)
        c.conn.commit()
        return {}
    return [
        A("14-verify", "14", "corr:verify", lambda c, e, x: str(e.ledger.verify().result), [], setup=seeded, counters=[C_STATS]),
        A("14-readers", "14", "corr:readers",
          lambda c, e, x: str([len(e.ledger.history().revisions), e.ledger.stats(), e.ledger.head()])[:200], [], setup=seeded),
    ]


def g15():
    def edge(c, e):
        return {"eid": int(c.sql("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s='fd:p' AND p='R' AND o_id='fd:q'")[0][0])}
    return [
        A("15-reify-edge", "15", "IRISGraphEngine.reify_edge",
          lambda c, e, x: e.reify_edge(x["eid"], reifier_id="fd:re1", props={"why": "x"}), ["fd:re1"], setup=edge,
          counters=[C_VER]),
        A("15-delete-reification", "15", "IRISGraphEngine.delete_reification", lambda c, e, x: e.delete_reification("fd:re1"),
          ["fd:re1"], setup=lambda c, e: (e.reify_edge(edge(c, e)["eid"], reifier_id="fd:re1"), c.conn.commit()) and {},
          counters=[C_VER, C_NKGVER]),
        A("15-fhir-bridge-add", "15", "IRISGraphEngine.fhir_bridge_add", lambda c, e, x: e.fhir_bridge_add("C01", "fd:p"), ["C01", "fd:p"]),
        A("15-code-crosswalk-add", "15", "IRISGraphEngine.code_crosswalk_add",
          lambda c, e, x: e.code_crosswalk_add("http://loinc.org", "C02", "fd:p"), ["C02", "fd:p"]),
        A("15-register-namespace", "15", "IRISGraphEngine.register_namespace",
          lambda c, e, x: e.register_namespace("frx", "http://example.org/frx#"), ["frx"]),
        A("15-map-sql-table", "15", "IRISGraphEngine.map_sql_table",
          lambda c, e, x: e.map_sql_table("Graph_KG.rdf_namespaces", "prefix", "FrNs"), ["FrNs"]),
        A("15-map-sql-relationship", "15", "IRISGraphEngine.map_sql_relationship",
          lambda c, e, x: e.map_sql_relationship("FrNs", "SAME", "FrNs", target_fk="prefix"), ["FrNs"],
          setup=lambda c, e: (e.map_sql_table("Graph_KG.rdf_namespaces", "prefix", "FrNs"), c.conn.commit()) and {}),
        A("15-remove-table-mapping", "15", "IRISGraphEngine.remove_table_mapping", lambda c, e, x: e.remove_table_mapping("FrNs"),
          ["FrNs"], setup=lambda c, e: (e.map_sql_table("Graph_KG.rdf_namespaces", "prefix", "FrNs"), c.conn.commit()) and {}),
    ]


def _routes(g):
    def f(c, ctx):
        return [str(r[0]) for r in c.sql("SELECT table_name FROM Graph_KG.embedding_registry WHERE graph_id = ?", g)]
    return f


def _archive_values(path):
    """Every string value the archive carries (its NDJSON members' leaves): a merge restore's keys."""
    import zipfile
    out = set()
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            for ln in z.read(n).splitlines()[:20000]:
                try:
                    obj = json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                stack = [obj]
                while stack:
                    o = stack.pop()
                    if isinstance(o, dict):
                        stack += list(o.values())
                    elif isinstance(o, list):
                        stack += o
                    elif isinstance(o, str) and 1 < len(o) < 300:
                        out.add(o)
    return out


def _store(c):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    return IRISGraphStore(c.conn)


def g17():
    return [
        A("17-write-nodes", "17", "IRISGraphStore.write_nodes",
          lambda c, e, x: str(_store(c).write_nodes([{"id": "fd:s1", "labels": ["L"], "properties": {"k": "v"}}])), ["fd:s1"],
          counters=[C_VER, C_NKGVER]),
        A("17-write-edges", "17", "IRISGraphStore.write_edges",
          lambda c, e, x: str(_store(c).write_edges([{"source": "fd:p", "predicate": "W", "target": "fd:q"}])), ["fd:p", "fd:q"],
          counters=[C_VER, C_NKGVER]),
        A("17-delete-edges", "17", "IRISGraphStore.delete_edges",
          lambda c, e, x: str(_store(c).delete_edges([("fd:p", "R", "fd:q")])), ["fd:p", "fd:q"],
          counters=[C_VER, C_NKGVER], whole_kills=WK_NKG),
        A("17-delete-nodes", "17", "IRISGraphStore.delete_nodes", lambda c, e, x: str(_store(c).delete_nodes(["fd:q"])), ["fd:q"],
          counters=[C_VER, C_NKGVER]),
        A("17-write-temporal-edge", "17", "IRISGraphStore.write_temporal_edge",
          lambda c, e, x: str(_store(c).write_temporal_edge("fd:p", "TT", "fd:q", 1_700_000_000)), ["fd:p", "fd:q"],
          counters=[C_VER, C_NKGVER] + C_GRAPH(None)),
        A("17-meta-set", "17", "Graph.KG.Meta.Set / Delete", lambda c, e, x: str(c.call("Graph.KG.Meta", "Set", "frkey", "frval")),
          ["frkey"]),
    ]


def g18():
    def saved(c, e):
        d = tempfile.mkdtemp(prefix="st-frame-snap-")
        p = os.path.join(d, "s.zip")
        e.save_snapshot(p)
        vals = _archive_values(p)
        # the archive's content, then make the live content differ: a new node outside the archive
        e.create_node("fd:new", graph=None)
        e.delete_node("fd:q")
        c.conn.commit()
        return {"path": p, "archive_values": sorted(vals)}
    return [
        A("18-restore-merge", "18", "IRISGraphEngine.restore_snapshot(merge=True)",
          lambda c, e, x: str(e.restore_snapshot(x["path"], merge=True))[:300], lambda x, r: x["archive_values"], setup=saved,
          counters=[C_VER, C_NKGVER, (C_STOP[0], "the BM25 stopword list ^BM25Idx(\"__stop__\") the archive carries (snapshot globals)")], note="merge: writes only the archive's rows (keys = the archive's ids)"),
        A("18-restore-replace", "18", "IRISGraphEngine.restore_snapshot(merge=False)",
          lambda c, e, x: str(e.restore_snapshot(x["path"], merge=False))[:300], lambda x, r: x["archive_values"] + ["fd:new"],
          setup=saved, counters=[C_VER, C_NKGVER], any_key=True,
          note="replace: kills the live content (fd:new) and writes the archive"),
        A("18-setnodejson", "18", "Graph.KG.Snapshot.SetNodeJSON",
          lambda c, e, x: c.o.classMethodVoid("Graph.KG.Snapshot", "SetNodeJSON", "^VecIdx", '["fv","frk"]', '{"v":"frv"}'), ["fv"],
          setup=lambda c, e: (e.vec_create_index("fv", 4), c.conn.commit()) and {},
          note="the restore helper writes the vector-index node it is given (allow-list ^IVF/^PLAID/^VecIdx, Snapshot.cls:96-108)"),
    ]


def g01():
    return [
        A("01-initialize-schema-rerun", "01", "py:IRISGraphEngine.initialize_schema",
          lambda c, e, x: str({k: v for k, v in e.initialize_schema().items() if k in ("schema", "warnings", "objectscript_failed")})[:400],
          ALL_KEYS, any_key=True, note="second setup on a deployed namespace (the pin's own deploy path); store level only"),
        A("01-remove-legacy", "01", "py:IRISGraphEngine.remove_legacy_objects",
          lambda c, e, x: str(e.remove_legacy_objects(dry_run=False))[:300], [], any_key=True),
    ]


def gS():
    """Supplement (run after r4): actions for statement classes r4 did not observe."""
    def drift(c, e):
        e.ledger.enable()
        _commit_basic(c, e)
        c.conn.commit()
        e.create_node("lt|drift")       # a ledger-bypassing write: verify reports divergence
        c.conn.commit()
        return {}

    def adopt(c, e, x):
        rep = e.ledger.verify(adopt=True)
        rev = getattr(rep, "adoption_revision", None)
        return _rev(rev) if rev is not None else {"result": str(getattr(rep, "result", rep))}
    return [
        A("02-set-multigraph-off", "02", "py:IRISGraphEngine.set_multigraph", lambda c, e, x: e.set_multigraph("fg", False),
          ["fg"], setup=lambda c, e: (e.set_multigraph("fg", True), c.conn.commit()) and {}),
        A("03-store-node-replace", "03", "py:IRISGraphEngine.store_node",
          lambda c, e, x: e.store_node("fr:a", properties={"name": "changed"}, graph="fg"), ["fr:a"], counters=[C_VER, C_NKGVER]),
        A("06-store-embedding-overwrite", "06", "py:IRISGraphEngine.store_embedding", lambda c, e, x: e.store_embedding("fd:p", vec(2)),
          ["fd:p"], setup=lambda c, e: (e.store_embedding("fd:p", vec()), c.conn.commit()) and {}),
        A("08-cypher-set-existing", "08", "eng:IRISGraphEngine.execute_cypher",
          lambda c, e, x: str(e.execute_cypher("MATCH (n {id: 'fd:p'}) SET n.name = 'zz' RETURN n.id")), ["fd:p"],
          counters=[C_VER, C_NKGVER]),
        A("14-verify-adopt", "14", "corr:verify", adopt, rev_keys(["lt|drift", "lt|a", "lt|b"] + ALL_KEYS), setup=drift,
          also_declared=[("11", "corr:reenable-adoption"), ("11", "corr:commit")],
          counters=rev_counters([(r'^\^IVG\.Ledger\("meta"', 'ledger state')]),
          note="verify(adopt=True) writes an adoption revision (client.py:741-744 -> replay.verify); declared as the adoption path"),
        A("17-write-nodes-update", "17", "IRISGraphStore.write_nodes",
          lambda c, e, x: str(_store(c).write_nodes([{"id": "fd:p", "labels": ["L"], "properties": {"name": "upd"}}])), ["fd:p"],
          counters=[C_VER, C_NKGVER]),
    ]


def gS2():
    """Second supplement: an UPDATE by adoption, the adjacency module's own SQL insert, the ledger purge."""
    T0 = 1_700_000_000
    return [
        A("03-create-edge-adopts-temporal-row", "03", "py:IRISGraphEngine.create_edge",
          lambda c, e, x: e.create_edge("fr:a", "T", "fr:c", graph="fg"), ["fr:a", "fr:c"],
          setup=lambda c, e: (e.create_edge_temporal("fr:a", "T", "fr:c", timestamp=T0, graph="fg"), c.conn.commit()) and {},
          counters=[C_VER, C_NKGVER] + C_GRAPH("fg"),
          note="an explicit write adopts the temporal edge's marked row: UPDATE rdf_edges SET qualifiers = NULL (nodes_edges.py:88-93)"),
        A("04-assert-temporal-row", "04", "cls:Graph.KG.Adjacency.AssertTemporalRow",
          lambda c, e, x: str(c.call("Graph.KG.Adjacency", "AssertTemporalRow", "fg", "fr:new1", "T", "fr:new2", "1.0", 1)),
          ["fr:new1", "fr:new2"], counters=[C_VER, C_NKGVER] + C_GRAPH("fg"),
          note="the adjacency writer's marked structural row: INSERT nodes/rdf_edges (Adjacency.cls:575-620)"),
        A("14-purge-all", "14", "cls:Graph.KG.Ledger.PurgeAll", lambda c, e, x: str(c.call("Graph.KG.Ledger", "PurgeAll")),
          ["lt|a", "lt|b"], any_key=True,
          setup=lambda c, e: (e.ledger.enable(), _commit_basic(c, e), c.conn.commit()) and {},
          note="Kill ^IVG.Ledger, %KillExtent of LedgerRevision and LedgerStats (Ledger.cls:242-248); no footprint declares it"),
    ]


GROUPS = {"S": gS, "S2": gS2, "01": g01, "02": g02, "03": g03, "04": g04, "05": g05, "06": g06, "07": g07, "08": g08, "09": g09, "10": g10,
          "11": g11, "12": g12, "13": g13, "14": g14, "15": g15, "17": g17, "18": g18}


def other_writers(m, pid):
    """Records written to AUDITD by any other process in the window (another process, or a JOB the action started)."""
    recs = J.records_since(m, dbs={lib.DB})
    return sorted({r["p"] for r in recs if r["p"] != pid and r.get("g")})


def run_action(a: dict) -> dict:
    c = lib.conn()
    out = {"id": a["id"], "module": a["module"], "entry": a["entry"], "note": a.get("note", "")}
    try:
        lib.reset(c)
        with contextlib.suppress(Exception):
            c.call("Graph.KG.Cypher.Gen", "Mode", "off")   # this process never compiles a generated plan class
        e = lib.engine(c)
        base(c, e)
        ctx = {}
        if a.get("setup"):
            ctx = a["setup"](c, e) or {}
            c.conn.commit()
        e = lib.engine(c)
        smap = J.storage_map(c)
        try:
            decl = DECL.declared(a["module"], a["entry"])
        except KeyError:
            decl = {"stores": [], "source": "NOT DECLARED", "raw": None}
        def interned_map():
            d = {}
            with contextlib.suppress(Exception):
                if int(c.o.isDefined("^NKG", "$ND")):
                    for k, v in c.o.iterator("^NKG", "$ND").items():
                        with contextlib.suppress(Exception):
                            d[int(k)] = str(v)
            return d
        interned = interned_map()
        otab = set(a["owned_tables"](c, ctx)) if a.get("owned_tables") else set()
        m = J.mark()
        res, err = None, None
        try:
            res = a["run"](c, e, ctx)
            c.conn.commit()
        except Exception as ex:  # noqa: BLE001
            err = f"{type(ex).__name__}: {str(ex)[:400]}"
            with contextlib.suppress(Exception):
                c.conn.rollback()
        recs = J.records_since(m, dbs={lib.DB}, pids={c.pid})
        if a.get("owned_tables"):
            otab |= set(a["owned_tables"](c, ctx))
        interned.update(interned_map())
        smap2 = dict(smap)
        smap2.update(J.storage_map(c))
        keys = a["keys"](ctx, res) if callable(a["keys"]) else a["keys"]
        ik = a["int_keys"](ctx, res) if callable(a.get("int_keys")) else (a.get("int_keys") or [])
        cnt = a["counters"](ctx, res) if callable(a.get("counters")) else a.get("counters", [])
        decl_stores = decl["stores"] + [s2 for extra in a.get("also_declared", []) for s2 in DECL.declared(*extra)["stores"]]
        def row_lookup(root, rowid, c=c):
            import base64 as _b64
            with contextlib.suppress(Exception):
                v = c.o.getBytes(root, rowid)
                return None if v is None else _b64.b64encode(v).decode()
            return None
        if a.get("owned_table_keys"):   # the route's table name and its class name (kgemb<hash>, catalog entries)
            keys = list(keys) + sorted(otab) + sorted(t.replace("_", "") for t in otab)
        chk = FC.check(recs, smap2, decl_stores, keys, cnt, ik, a.get("any_key", False), row_lookup=row_lookup,
                       owned_tables=["Graph_KG." + t if "." not in t else t for t in otab], interned=interned,
                       whole_kills=a.get("whole_kills", []), ddl_catalog=a.get("ddl_catalog", False))
        chk["owned_tables"] = sorted(otab)
        out["keys_used"] = keys
        out["written_nodes"] = sorted({f"{r['t']} {r['g'][:100]}" for r in recs if r.get("g")})[:600]
        out.update({"result": res if isinstance(res, (str, int, float, bool, type(None), dict, list)) else str(res),
                    "error": err, "declared_source": decl["source"], "declared": decl["stores"], "keys": keys,
                    "int_keys": ik, "check": chk})
        out["exercised"] = err is None and chk["records"] > 0
        out["frame_ok"] = chk["store_ok"] and chk["key_ok"]
        print(f"{a['id']:34} err={'-' if err is None else err[:60]:62} rec={chk['records']:4} store_ok={chk['store_ok']} "
              f"key_ok={chk['key_ok']} ({chk['key_excursion_count']}) classes={chk['classes']}", flush=True)
    except Exception as ex:  # noqa: BLE001
        out["harness_error"] = f"{type(ex).__name__}: {ex}\n{traceback.format_exc()[-1500:]}"
        print(f"{a['id']:34} HARNESS ERROR {ex}", flush=True)
    finally:
        with contextlib.suppress(Exception):
            if int(c.o.isDefined("^IVGAuditDFrmS")):
                c.o.kill("^IVGAuditDFrmS")
        with contextlib.suppress(Exception):
            lib.reset(c)
        c.close()
    return out


def control() -> dict:
    """Registered self-test: three captured windows on the live journal; the checker must flag (a) a seeded write
    to a store the declaration does not name and (b) a seeded write of another node's row, and pass a conforming
    action."""
    res = {"offline": FC.self_test()}
    decl = DECL.declared("03", "py:IRISGraphEngine.create_node")["stores"]

    def window(fn):
        c = lib.conn()
        try:
            lib.reset(c)
            e = lib.engine(c)
            base(c, e)
            smap = J.storage_map(c)
            m = J.mark()
            fn(c, e)
            c.conn.commit()
            recs = J.records_since(m, dbs={lib.DB}, pids={c.pid})
            r = FC.check(recs, smap, decl, ["fr:ctl"], [C_VER])
            r["_both"] = FC.check(recs, smap, decl, ["fr:ctl", "fr:intruder"], [C_VER])
            return r
        finally:
            with contextlib.suppress(Exception):
                c.o.kill("^IVGAuditDFrmX")
            lib.reset(c)
            c.close()

    ok = window(lambda c, e: e.create_node("fr:ctl", labels=["L"], properties={"k": "v"}, graph="fg"))
    st = window(lambda c, e: (e.create_node("fr:ctl", labels=["L"], graph="fg"), c.o.set(1, "^IVGAuditDFrmX", 1)))
    ky = window(lambda c, e: (e.create_node("fr:ctl", labels=["L"], graph="fg"),
                              e.create_node("fr:intruder", labels=["L"], properties={"k": "v"}, graph="fg")))
    res["conforming"] = {"store_ok": ok["store_ok"], "key_ok": ok["key_ok"], "records": ok["records"]}
    res["seeded_store"] = {"store_ok": st["store_ok"], "excursions": st["store_excursions"]}
    res["seeded_key"] = {"store_ok": ky["store_ok"], "key_ok": ky["key_ok"], "key_excursion_count": ky["key_excursion_count"],
                         "sample": [x["node"] for x in ky["key_excursions"][:6]]}
    res["pass"] = (res["offline"]["pass"] and ok["store_ok"] and ok["key_ok"] and not st["store_ok"]
                   and ky["store_ok"] and not ky["key_ok"]
                   and ky["_both"]["key_ok"] and ky["_both"]["store_ok"])
    res["seeded_key"]["attributed"] = ("every flagged node is the intruder's: with the intruder's id added to the keys "
                                       f"the same window passes ({ky['_both']['key_ok']})")
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    if sys.argv[1] == "control":
        r = control()
        p = OUT / f"control-{stamp}.json"
        lib.dump(p, r)
        print(json.dumps(r, indent=1, default=str)[:3000])
        print("written", p)
        return 0 if r["pass"] else 1
    if sys.argv[1] == "run":
        groups = sys.argv[2:]
        only = os.environ.get("FRAME_ONLY", "")
        for g in groups:
            acts = GROUPS[g]()
            if only:
                acts = [a for a in acts if a["id"] in only.split(",")]
            res = [run_action(a) for a in acts]
            p = OUT / f"live-{g}-{stamp}.json"
            lib.dump(p, {"group": g, "utc": stamp, "namespace": lib.NS, "actions": res})
            print("written", p, flush=True)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
