"""HD-1004 probe: how many rows the global PageRank owner lists, and whether the native route's ranking cuts.

Namespace AUDITIB. Writes nothing: it calls the owner Graph.KG.PageRank.PageRankGlobalJson exactly as
_execute_pagerank does for a default graph whose edgeless nodes are the given ids (iris_sql_store.py:2402-2408),
with 10,050 synthetic edgeless ids ib1_pr_NNNNN, plus whatever default-graph adjacency AUDITIB holds. SHARED lock.
Oracles (stated):
  - kg_PAGERANK docstring (algorithms.py:749-752, 4.6.0 R306): every node of the default graph takes part and the
    scores sum to 1 over node_count() nodes ("before, a node with no edge had no pair").
  - spec 236 Story 2 scenario 3 (spec.md:94-96): native and owner PageRank answers have the same node set.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.stores.iris_sql_store import _ranked_rows  # noqa: E402

N = 10050


def main():
    c = Conn("AUDITIB")
    ids = [f"ib1_pr_{i:05d}" for i in range(N)]
    raw = str(c.call("Graph.KG.PageRank", "PageRankGlobalJson", "0.85", "20", json.dumps(ids)))
    rows = json.loads(raw)
    listed = {r["id"] for r in rows}
    total = sum(float(r["score"]) for r in rows)
    mine_listed = len([i for i in ids if i in listed])
    print("OBS edgeless ids passed:", N)
    print("OBS owner rows returned:", len(rows), "of which synthetic:", mine_listed)
    print("OBS sum of listed scores: %.6f" % total)
    synthetic = [[f"n{i}", 1.0 / N] for i in range(N)]
    print("OBS native-route ranking _ranked_rows(rows, 0) keeps:", len(_ranked_rows(synthetic, 0)), "of", N)
    capped = len(rows) == 10000
    print("ORACLE docstring (every node listed, scores sum to 1):",
          "VIOLATED (owner stops at 10,000 rows; listed sum < 1)" if capped and total < 0.999 else "held")
    print("ORACLE spec 236 (native and owner node sets equal): native ranking keeps all", N,
          "-> sets differ above 10,000 nodes" if capped else "")
    c.close()


if __name__ == "__main__":
    main()
