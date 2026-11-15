"""HD-1001 probe: what random_walk answers without the Arno library, and which graph's edges the walk it calls reads.

Namespace AUDITIB, data prefix ib1_rw_ (default graph) and graph ib1_rw_g. Run under the EXCLUSIVE lane lock
(it rebuilds ^NKG with the pin's engine.sync() and erases its own named graph).

Oracle (stated contracts):
  - docs/ADMIN_GUIDE.md:651-654: "IVG is complete without it: every algorithm has an ObjectScript implementation,
    which is what answers when the library is absent."  CONTEXT.md (Arno): "IVG answers the same without it".
  - docs/USER_GUIDE.md:767-769: Python methods that take no graph "answer the default graph", never every graph.
  - The random_walk docstring (algorithms.py:659-662) instead states: without the library it returns [].
Observed values printed: whether the library is detected, random_walk's answer, and the second node of 40 walks of
length 1 from the shared seed through the exact call random_walk makes when the library is present
(engine._arno_call("Graph.KG.NKGAccel", "RandomWalkJson", ...); the library only gates that call).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))
from iris_conn import Conn  # noqa: E402

from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402

P = "ib1_rw_"
G = "ib1_rw_g"


def cleanup(eng):
    try:
        eng.erase_graph(G)
    except Exception as exc:  # noqa: BLE001
        print("cleanup erase_graph:", exc)
    try:
        eng.delete_nodes_by_prefix(P)
    except Exception as exc:  # noqa: BLE001
        print("cleanup delete_nodes_by_prefix:", exc)


def main():
    c = Conn("AUDITIB")
    eng = IRISGraphEngine(c.conn, namespace="AUDITIB", embedding_dimension=4)
    cleanup(eng)
    # default graph: a -> b ; named graph G: a -> c (same seed id in both graphs)
    eng.create_node(P + "a")
    eng.create_node(P + "b")
    eng.create_edge(P + "a", "RW", P + "b")
    eng.create_node(P + "a", graph=G)
    eng.create_node(P + "c", graph=G)
    eng.create_edge(P + "a", "RW", P + "c", graph=G)

    detected = eng._detect_arno()
    caps = getattr(eng, "_arno_capabilities", {})
    walk = eng.random_walk(P + "a", 1, 30)
    print("OBS arno_detected:", detected, "capabilities:", json.dumps(caps, sort_keys=True))
    print("OBS engine.random_walk(seed, 1, 30) ->", json.dumps(walk))

    eng.sync()  # the pin's documented rebuild of ^KG and ^NKG
    use_nkg = c.call("Graph.KG.NKGAccel", "UseNKG")
    raw = eng._arno_call("Graph.KG.NKGAccel", "RandomWalkJson", P + "a", "1", "40")
    walks = json.loads(raw)
    seconds = sorted({w[1] for w in walks if len(w) > 1})
    print("OBS UseNKG after sync:", use_nkg)
    print("OBS NKGAccel.RandomWalkJson(seed, 1, 40): walks", len(walks), "distinct second nodes", seconds)

    default_only = {P + "b"}
    merged = bool(set(seconds) - default_only)
    print("ORACLE-1 (ADMIN_GUIDE/CONTEXT: same answer without the library): random_walk non-empty ->",
          "VIOLATED" if walk == [] and walks else "held")
    print("ORACLE-2 (USER_GUIDE: default graph only): walk reaches only", sorted(default_only), "->",
          "VIOLATED (named-graph edge walked)" if merged else "held")
    print("DOCSTRING (returns [] without the library):", "matches" if walk == [] and not detected else "differs")
    cleanup(eng)
    eng.sync()
    c.close()


if __name__ == "__main__":
    main()
