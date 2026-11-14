#!/usr/bin/env python3
"""3.6-capacity/01, release side: load content into a v4.5.1 namespace through v4.5.1's own API.

Run by upgrade_probe.py the way the pinned fixture runs its children (scripts/fixtures/build_release_namespace.py:
run_ledger_commits): PYTHONPATH on the release worktree ~/.cache/ivg-bench/releases/v4.5.1, cwd there. It refuses to
run unless iris_vector_graph resolves into that worktree, compiles nothing, writes only through v4.5.1's public
API (BulkLoader.load_networkx, bulk_create_nodes/bulk_create_edges with a graph, bulk_create_edges_temporal,
store_embeddings, ledger.enable/commit), and prints its result with the fixture's emit_result.

    argv: <namespace> <nodes> <edges> <named_nodes> <temporal> <vectors> <commits>
"""
from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

FIXTURES = Path(os.environ["IVG_AUDIT_REPO"]) / "scripts" / "fixtures"
sys.path.insert(0, str(FIXTURES))


def main() -> int:
    import build_release_namespace as brn  # the pinned fixture (emit_result, RELEASES, PORT, EMBEDDING_DIM)
    import iris
    import iris_vector_graph
    here = Path(iris_vector_graph.__file__).resolve()
    if brn.RELEASES.resolve() not in here.parents:
        print(f"refusing: iris_vector_graph resolved to {here}, not the v4.5.1 worktree", file=sys.stderr)
        return 2
    import networkx as nx
    from iris_vector_graph.bulk_loader import BulkLoader
    from iris_vector_graph.engine import IRISGraphEngine
    from iris_vector_graph.ledger import Changeset
    ns = sys.argv[1]
    n_nodes, n_edges, n_named, n_temporal, n_vec, n_commits = (int(x) for x in sys.argv[2:8])
    rnd = random.Random(451)
    conn = iris.connect("localhost", brn.PORT, ns, "_SYSTEM", "SYS")
    timings = {}
    try:
        eng = IRISGraphEngine(conn, embedding_dimension=brn.EMBEDDING_DIM, namespace=ns)
        t = time.time()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'cap:'")
        have = int(cur.fetchone()[0])
        cur.close()
        stats = {"skipped": f"{have} cap: nodes already loaded by an earlier run of this child"} if have >= n_nodes else None
        G = nx.DiGraph()
        for i in range(0 if stats else n_nodes):
            G.add_node(f"cap:{i:07d}", namespace="CapNode", name=f"node {i}", score=str(i % 97))
        for j in range(0 if stats else n_edges):
            a, b = rnd.randrange(n_nodes), rnd.randrange(n_nodes)
            if a != b:
                G.add_edge(f"cap:{a:07d}", f"cap:{b:07d}", relation="CAP_REL", w=str(j % 13))
        stats = stats or BulkLoader(conn).load_networkx(G, label_attr="namespace")
        conn.commit()
        timings["load_networkx"] = round(time.time() - t, 1)
        t = time.time()
        # v4.5.1's bulk_create_nodes takes the graph per node dict (its nodes_edges.py:1404), not as an argument
        nodes = [{"id": f"capg:{i:06d}", "labels": ["CapNamed"], "properties": {"k": str(i)}, "graph": "capg"} for i in range(n_named)]
        for k in range(0, len(nodes), 5000):
            eng.bulk_create_nodes(nodes[k:k + 5000])
        edges = [{"source_id": f"capg:{i:06d}", "predicate": "CAPG", "target_id": f"capg:{(i * 7 + 1) % n_named:06d}"}
                 for i in range(n_named)]
        for k in range(0, len(edges), 5000):
            eng.bulk_create_edges(edges[k:k + 5000], graph="capg")
        conn.commit()
        timings["named_graph"] = round(time.time() - t, 1)
        t = time.time()
        tedges = [{"s": f"cap:{i % n_nodes:07d}", "p": "CAP_T", "o": f"cap:{(i * 3 + 1) % n_nodes:07d}",
                   "ts": 1_700_000_000 + i} for i in range(n_temporal)]
        tw = 0
        for k in range(0, len(tedges), 5000):
            tw += int(eng.bulk_create_edges_temporal(tedges[k:k + 5000]))
        conn.commit()
        timings["temporal"] = round(time.time() - t, 1)
        t = time.time()
        items = [{"node_id": f"cap:{i:07d}", "embedding": [((i * 31 + d) % 17) / 17.0 for d in range(brn.EMBEDDING_DIM)]}
                 for i in range(n_vec)]
        for k in range(0, len(items), 1000):
            eng.store_embeddings(items[k:k + 1000])
        conn.commit()
        timings["vectors"] = round(time.time() - t, 1)
        t = time.time()
        eng.ledger.enable()
        for i in range(n_commits):
            ch = Changeset(actor="cap451", actor_type="ingest", message=f"cap451 commit {i}",
                           correlation_id=f"cap451-corr-{i % 5}", idempotency_key=f"cap451-idem-{i}")
            ch.create_node(f"capl:{i:05d}", labels=["CapLedger"])
            ch.set_property(f"capl:{i:05d}", "n", str(i))
            if i:
                ch.create_relationship(f"capl:{i - 1:05d}", "CAPL", f"capl:{i:05d}")
            eng.ledger.commit(ch)
        conn.commit()
        timings["ledger"] = round(time.time() - t, 1)
    finally:
        conn.close()
    brn.emit_result({"bulkloader_stats": {k: v for k, v in stats.items() if not isinstance(v, (dict, list))},
                     "temporal_written": tw, "timings": timings, "requested": sys.argv[2:8]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
