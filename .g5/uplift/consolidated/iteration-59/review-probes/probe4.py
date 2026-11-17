import json, os, sys, time
REPO = os.environ["IVG_REPO"]
sys.path.insert(0, REPO + "/.g5/Verus_verification/tools"); sys.path.insert(0, REPO + "/.g5/uplift/consolidated/iteration-36")
import binding_common as bc
bc.import_pin()
import runtime
from iris_vector_graph.engine import IRISGraphEngine
TAG = time.strftime("%H%M%S", time.gmtime()); P = f"rv58p_{TAG}_"
c = runtime.connect(); e = IRISGraphEngine(c, embedding_dimension=768, native_cypher=False)
L = f"RV58P{TAG}"
e.create_node(P + "a", labels=[L])
out = {}
for k, q in {"fixed": f"MATCH (a:{L}) OPTIONAL MATCH p = (a)-[:RV58NONE]->(b) RETURN length(p) AS l, p IS NULL AS isnull",
             "fixed2": f"MATCH (a:{L}) OPTIONAL MATCH p = (a)-[:RV58NONE]->()-[:RV58NONE]->(b) RETURN length(p) AS l",
             "varlen": f"MATCH (a:{L}) OPTIONAL MATCH p = (a)-[:RV58NONE*1..2]->(b) RETURN length(p) AS l"}.items():
    r = e.execute_cypher(q); out[k] = r.rows if r.rows is not None else r.error
print(json.dumps(out, default=str))
