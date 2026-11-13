"""HD-1703 probe: does IRISGraphStore.capabilities() say what the namespace can run, or what the code supports?

Part 1 (no IRIS): the store is built over a stub connection on which every statement fails, so nothing can be
deployed or reachable; IVG_DISABLE_ARNO=1 keeps the Arno probe from running. If capabilities() still reports every
algorithm True, it is a static catalogue (option b), not deployment detection (option a).
Part 2 (live, AUDITIB, read only): the engine's own `capabilities` property (IRISCapabilities, documented in
docs/API_REFERENCE.md as "What the namespace has deployed") next to the store's dict, to show the two facts the
product already keeps apart.

Discriminates option (a) "answer from what is deployed" from option (b) "static code-support catalogue".
Oracle (working assumption): code support and namespace availability are different facts; a static catalogue is
acceptable only when documented as one and when routing that needs availability does not treat it as availability
(the engine gates centrality etc. on it: _engine/algorithms.py:1096-1100). No stated contract for
store.capabilities() exists, so a deviation is an expected-violation, not a fail.
"""
import os
import sys

os.environ["IVG_DISABLE_ARNO"] = "1"
sys.path.insert(0, os.path.join(os.environ["WORK_DIR"], "experiment/playbook-completion/tools"))

from iris_vector_graph import IRISGraphStore  # noqa: E402


class _DeadCursor:
    description = None

    def execute(self, *a, **k):
        raise RuntimeError("stub: no database")

    def fetchone(self):
        raise RuntimeError("stub: no database")

    def fetchall(self):
        raise RuntimeError("stub: no database")

    def close(self):
        pass


class _DeadConn:
    def cursor(self):
        return _DeadCursor()

    def commit(self):
        pass

    def rollback(self):
        pass


store = IRISGraphStore(_DeadConn(), namespace="IB2NOSUCH")
try:
    caps = store.capabilities()
    algo = {k: v for k, v in caps.items() if not k.endswith("_arno")}
    print(f"part1 stub (nothing reachable): capabilities() keys={len(caps)} all_true={all(algo.values())}")
    print(f"part1 sample: { {k: caps[k] for k in ('pagerank', 'wcc', 'cdlp', 'leiden', 'k_core', 'temporal_edges')} }")
    static = all(algo.values())
except Exception as e:  # a deployment-aware implementation would fail or answer False here
    print(f"part1 stub: capabilities() raised {type(e).__name__}: {e}")
    static = False

os.environ.pop("IVG_DISABLE_ARNO", None)
from iris_conn import Conn  # noqa: E402
from iris_vector_graph import IRISGraphEngine  # noqa: E402

c = Conn("AUDITIB")
try:
    eng = IRISGraphEngine(c.conn, namespace="AUDITIB")
    ec = eng.capabilities
    sc = eng._store.capabilities()
    print(f"part2 AUDITIB engine.capabilities: objectscript_deployed={ec.objectscript_deployed} kg_built={ec.kg_built} "
          f"nkg_built={ec.nkg_built} graphoperators_deployed={ec.graphoperators_deployed}")
    print(f"part2 AUDITIB store.capabilities(): all algorithms True={all(v for k, v in sc.items() if not k.endswith('_arno'))} "
          f"arno keys={ {k: v for k, v in sc.items() if k.endswith('_arno')} }")
finally:
    c.close()

print("DISCRIMINATION (a) deployment-aware vs (b) static catalogue:", "(b) static catalogue" if static else "(a) or other")
print("ORACLE (working assumption): (b) is acceptable only if documented and not used as availability for routing;"
      " it is undocumented and gates routing (algorithms.py), so the assumption is not met")
print("OUTCOME:", "expected-violation (static catalogue; availability is a separate engine fact)" if static else "pass")
