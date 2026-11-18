import json, subprocess, sys
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/runs/ivg-cov-a")
import runtime, iris
from iris_vector_graph.engine import IRISGraphEngine
def os_(script):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", "I62C"],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=120).stdout
def state():
    out = os_('Set h=$Order(^IVG.CypherCompiled("")) Write "<<",h,"|",$ListGet(^IVG.CypherCompiled(h),1),"|",$ListGet(^IVG.CypherCompiled(h),3),"|",$Extract($ListGet(^IVG.CypherCompiled(h),4),1,80),"|",##class(%Dictionary.CompiledClass).%ExistsId("IVGC.P"_h),"|",##class(%Dictionary.ClassDefinition).%ExistsId("IVGC.P"_h),">>",!')
    return out.split("<<", 1)[1].split(">>", 1)[0]
obs = {"before": state()}
os_('Set h=$Order(^IVG.CypherCompiled("")) Set $List(^IVG.CypherCompiled(h),3)="stale" Set ^IVG.CypherGen("breaktest")=1')
obs["stale_marked"] = state()
c = runtime.connect("I62C")
e = IRISGraphEngine(c, embedding_dimension=8, namespace="I62C", native_cypher=True)
nat = iris.createIRIS(c)
nat.classMethodValue("Graph.KG.Cypher.Gen", "Mode", "sync")
lab = sys.argv[1]
r = e.execute_cypher(f"MATCH (a:D{lab} {{k: $k}})-[:R{lab}]->(b) RETURN b.k AS k", {"k": "a"})
obs["rebuild_answer"] = [r.rows, r.error, getattr(e, "_native_answers", 0)]
os_('Kill ^IVG.CypherGen("breaktest")')
obs["after_failed_rebuild"] = state()
c.close()
print(json.dumps(obs, indent=1))
