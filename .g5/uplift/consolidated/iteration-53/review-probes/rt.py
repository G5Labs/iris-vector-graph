import os, sys, json
TREE="/tmp/review-50-52/tree"
sys.path.insert(0, TREE)
os.environ.update(IVG_TEST_CONTAINER="ivg-cont-20261117-iris", IVG_PORT="36317", IVG_NAMESPACE="USER", IVG_AUTO_START_CONTAINER="0")
import iris.dbapi
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph.cypher.parser import parse_query
def connect():
    c = iris.dbapi.connect(hostname="127.0.0.1", port=36317, namespace="USER", username="_SYSTEM", password="SYS")

    return c
def eng(c): return IRISGraphEngine(c, embedding_dimension=768)
def run(e, q, params=None):
    try:
        r = e.execute_cypher(q, params or {})
        rows = r.get("rows") if isinstance(r, dict) else getattr(r, "rows", r)
        return {"rows": [list(x) for x in rows] if rows is not None else None, "raw_type": type(r).__name__,
                "err": (r.get("error") if isinstance(r, dict) else getattr(r, "error", None))}
    except Exception as x:
        return {"exc": f"{type(x).__name__}: {str(x)[:300]}"}
