#!/usr/bin/env python3
"""Module 10 live check F-1003: global PageRank lists at most 10,000 nodes on the owner route (AUDITB).

    bash experiment/playbook-completion/tools/locks.sh iris timeout 900 python experiment/playbook-completion/live/breadth-b/10_live_cap.py

Default graph: hub b10_h with an edge to each of 10,050 nodes b10_c00000.. (bulk_create_nodes / bulk_create_edges,
the pin's bulk API). kg_PAGERANK() (owner route: the Arno library is absent here) is compared with node_count() and
with the sum of the scores; a direct PageRank.PageRankGlobalJson call is counted too. The native route (every node,
iris_sql_store.py:2396-2399) needs the arno-callout library: blocked-access. All b10_ nodes are removed after
(delete_nodes_by_prefix) and the cache invalidated.
"""
import importlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blive import session, write_log  # noqa: E402

c10 = importlib.import_module("10_common")
N = 10050


def main():
    log = {}
    with session("10-live-cap") as s:
        eng = s.eng
        log["cleanup_before"] = c10.cleanup_b10(s)
        t0 = time.time()
        ids = [f"b10_c{i:05d}" for i in range(N)]
        eng.bulk_create_nodes([{"id": "b10_h"}] + [{"id": i} for i in ids])
        eng.bulk_create_edges([{"source_id": "b10_h", "predicate": "B10C", "target_id": i} for i in ids])
        log["load_seconds"] = round(time.time() - t0, 1)
        n_nodes = eng.node_count()
        n_edges = s.c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE graph_id = ''")[0][0]
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        t0 = time.time()
        pr = eng.kg_PAGERANK()
        log["pagerank_seconds"] = round(time.time() - t0, 1)
        raw = str(s.c.call("Graph.KG.PageRank", "PageRankGlobalJson", "0.85", "20"))
        try:
            direct = len(json.loads(raw))
        except Exception:  # noqa: BLE001
            direct = f"unparsed ({len(raw)} chars): {raw[:80]}"
        listed = {r[0] for r in pr}
        log.update({
            "node_count": n_nodes, "default_graph_edges": n_edges, "arno": eng._store._detect_arno(),
            "kg_PAGERANK_rows": len(pr), "score_sum": round(sum(r[1] for r in pr), 6),
            "hub_listed": "b10_h" in listed, "unlisted_nodes": n_nodes - len(listed),
            "PageRankGlobalJson_rows": direct,
            "reproduced": len(pr) < n_nodes and len(pr) == 10000,
        })
        print(json.dumps(log, default=str))
        t0 = time.time()
        deleted = eng.delete_nodes_by_prefix("b10_")
        log["deleted"] = deleted
        log["cleanup_seconds"] = round(time.time() - t0, 1)
        log["cleanup_after"] = c10.cleanup_b10(s)
        s.c.call("Graph.KG.AlgoCache", "InvalidateAll")
        log["state_after"] = c10.state(s)
        p = write_log(s, log)
        print("reproduced", log["reproduced"], "log", p)


if __name__ == "__main__":
    main()
