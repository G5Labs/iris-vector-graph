"""W54 neighbors for the findings' wording (not frozen): the keys(n)/n[k] idiom, and the UNWIND ... CREATE write with
and without randomUUID(). Run-isolated continuation fixture; ordinary data."""
import json, os, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "iteration-36"))
import runtime  # noqa: E402
RUN = os.environ.get("W54_RUN", time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())); TAG = RUN[-7:-1]
from iris_vector_graph.engine import IRISGraphEngine  # noqa: E402
c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768); L = f"I47H{TAG}"; out = {"run": RUN, "fixture": runtime.NAME, "cases": {}}


def run(k, q):
    try:
        r = e.execute_cypher(q); out["cases"][k] = {"query": q, "rows": [list(x) for x in r.rows], "error": str(r.error)[-200:] if r.error else None}
    except Exception as x:
        out["cases"][k] = {"query": q, "exception": f"{type(x).__name__}: {str(x)[:240]}"}


e.execute_cypher(f"CREATE (:{L} {{id: 'i47h_{TAG}', a: 1, b: 'x'}})")
run("keys_idiom", f"MATCH (n:{L}) UNWIND keys(n) AS k RETURN k, n[k] ORDER BY k")
run("create_plain", f"UNWIND [1, 2, 3] AS i CREATE (:{L}P {{i: i, u: 'x'}})")
run("create_plain_read", f"MATCH (x:{L}P) RETURN count(x)")
run("create_uuid_single", f"CREATE (:{L}S {{u: randomUUID()}})")
run("create_uuid_single_read", f"MATCH (x:{L}S) RETURN x.u")
run("create_uuid_unwind", f"UNWIND [1, 2, 3] AS i CREATE (:{L}V {{i: i, u: randomUUID()}})")
run("create_uuid_unwind_read", f"MATCH (x:{L}V) RETURN count(x)")
c.close()
(HERE / f"cypherfn-observed3-{RUN}.json").write_text(json.dumps(out, indent=2, default=str) + "\n"); print(json.dumps(out["cases"], default=str)[:2500])
