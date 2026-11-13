"""HD-1002 probe: does kg_CDLP signal that its labels did not settle?

Namespace AUDITIB, default graph, data prefix ib1_cd_ (a path a -> b -> c, the example of docs/COMMUNITIES.md:192-208).
SHARED lane lock. Other default-graph components cannot change these three nodes' labels (label propagation is local
to a connected component).

Oracle (stated contract, docs/COMMUNITIES.md:205-208, maintainer commit af2bc84e W6): on the path the labels swap
every round, "kg_CDLP() gives no sign of it", and a caller tells by comparing max_iterations k with k + 1.
The decisions.md working assumption (expose whether labels settled) is a strengthening; this probe shows whether the
pin exposes anything.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

P = "ib1_cd_"


def main():
    c = Conn("AUDITIB")
    eng = IRISGraphEngine(c.conn, namespace="AUDITIB", embedding_dimension=4)
    eng.delete_nodes_by_prefix(P)
    for n in "abc":
        eng.create_node(P + n)
    eng.create_edge(P + "a", "NEXT", P + "b")
    eng.create_edge(P + "b", "NEXT", P + "c")
    mine = [P + n for n in "abc"]
    rounds = {}
    for k in range(1, 7):
        out = eng.kg_CDLP(max_iterations=k)
        rounds[k] = {n: out.get(n) for n in mine}
        extra_keys = [key for key in out if not isinstance(key, str) or key.startswith("_")]
        print(f"OBS k={k} type={type(out).__name__} labels={json.dumps(rounds[k], sort_keys=True)} "
              f"non-node keys={extra_keys}")
    settled = all(rounds[k] == rounds[k + 1] for k in range(1, 6))
    print("OBS labels identical across k=1..6:", settled)
    print("ORACLE (COMMUNITIES.md: no sign; k vs k+1 differ on the path):",
          "HOLDS (oscillates, return carries no convergence signal)" if not settled else "differs from docs")
    eng.delete_nodes_by_prefix(P)
    c.close()


if __name__ == "__main__":
    main()
