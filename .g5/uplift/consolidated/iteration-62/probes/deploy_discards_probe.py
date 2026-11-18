"""Iteration 62: does a failed rebuild of an already compiled shape remove its class? (query.compiled.deploy-discards)
I62C only, own connection (a failed class compile spoils its process's SQL compiles)."""
import json, os, sys
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/runs/ivg-cov-a")
import runtime, iris
from iris_vector_graph.engine import IRISGraphEngine
c = runtime.connect("I62C")
e = IRISGraphEngine(c, embedding_dimension=8, namespace="I62C", native_cypher=True)
T = "d" + os.urandom(2).hex()
e.create_node(f"{T}a", labels=["D" + T], properties={"k": "a"}); e.create_node(f"{T}b", labels=["D" + T], properties={"k": "b"})
e.create_edge(f"{T}a", "R" + T, f"{T}b")
nat = iris.createIRIS(c)
def entries():
    out, h = [], ""
    while True:
        h = nat.nextSubscript(False, "^IVG.CypherCompiled", h) if False else nat.classMethodValue("%Library.Global", "Get", "x") if False else None
        break
    # walk ^IVG.CypherCompiled with $Order through a tiny routine-free call
    return json.loads(str(nat.classMethodValue("%SYSTEM.SQL", "Help"))) if False else None
def walk():
    res, h = [], ""
    it = nat.iterator("^IVG.CypherCompiled")
    for h, _ in it.items():
        lst = nat.getAsList("^IVG.CypherCompiled", h) if hasattr(nat, "getAsList") else None
        res.append((h, str(nat.get("^IVG.CypherCompiled", h))))
    return res
def cls_exists(name):
    return bool(name) and int(nat.classMethodValue("%Dictionary.CompiledClass", "%ExistsId", name)) == 1
nat.classMethodVoid("Graph.KG.Cypher.Gen", "DropAll")
print("mode", nat.classMethodValue("Graph.KG.Cypher.Gen", "Mode", "sync"))
q = f"MATCH (a:D{T} {{k: $k}})-[:R{T}]->(b) RETURN b.k AS k"
r1 = e.execute_cypher(q, {"k": "a"}); print("first", r1.rows, getattr(e, "_native_answers", 0))
ent = walk(); print("entries", [(h, v[:120]) for h, v in ent])
cls = None
for h, v in ent:
    for part in v.split("\x00"):
        pass
# the class name is element 1 of the $List: read it in ObjectScript through %SYSTEM? use $ListGet via a classmethod-free path
h0 = ent[0][0]
raw = nat.get("^IVG.CypherCompiled", h0)
print("raw", repr(raw)[:200])
