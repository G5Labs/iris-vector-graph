#!/usr/bin/env python3
"""Does the pin reach the FETCH FIRST crash? Each call runs in its own child process on AUDITCORE (read-only calls
of the pin's Python API; the pin is deployed there by its own deploy path). Controls: the same API without the
FETCH FIRST shape. Prints one JSON object."""
import json
import os
import subprocess
import sys
from pathlib import Path

PC = Path(__file__).resolve().parents[2]
CHILD = r'''
import sys, json
sys.path.insert(0, %(tools)r)
from iris_conn import Conn
c = Conn("AUDITCORE")
kind = %(kind)r
if kind.startswith("store"):
    from iris_vector_graph.stores.iris_sql_store import IRISGraphStore
    st = IRISGraphStore(c.conn, namespace="AUDITCORE")
    r = st.query_nodes(label_filter=%(label)r, limit=2)
    print("ANSWER", type(r).__name__, flush=True)
else:
    from iris_vector_graph.engine import IRISGraphEngine
    e = IRISGraphEngine(c.conn, namespace="AUDITCORE")
    r = e.execute_cypher(%(q)r)
    rows = r.get("rows") if isinstance(r, dict) else getattr(r, "rows", r)
    print("ANSWER", json.dumps(rows, default=str)[:200], flush=True)
c.close()
'''
CALLS = [
    ("store-query_nodes-label (control: no FETCH FIRST)", "store", "env2-no-such-label", None),
    ("store-query_nodes-no-label (FETCH FIRST 2 ROWS ONLY, iris_sql_store.py:1179)", "store2", None, None),
    ("cypher RETURN ... LIMIT 2 (control)", "cypher", None, "MATCH (n) RETURN n.id LIMIT 2"),
    ("cypher WITH n LIMIT 2 (translator.py:4450 branch)", "cypher", None, "MATCH (n) WITH n LIMIT 2 RETURN n.id"),
]
import importlib.metadata as _m, iris as _iris
out = {"driver": _m.version("intersystems-irispython") + " " + _iris.__file__, "results": []}
for name, kind, label, q in CALLS:
    src = CHILD % {"tools": str(PC / "tools"), "kind": kind, "label": label, "q": q}
    try:
        r = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=120, env=os.environ)
        out["results"].append({"call": name, "returncode": r.returncode,
                               "answer": [ln for ln in r.stdout.splitlines() if ln.startswith("ANSWER")][:1],
                               "stderr_tail": [ln[:300] for ln in r.stderr.splitlines() if "WARNING" not in ln][-4:]})
    except subprocess.TimeoutExpired:
        out["results"].append({"call": name, "returncode": "timeout"})
print(json.dumps(out, indent=1))
