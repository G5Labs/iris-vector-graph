import sys, json
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/iris-vector-graph-playbook-uplift-20261113/iris-vector-graph-audit/experiment/playbook-completion/tools")
from iris_conn import Conn
c = Conn("AUDITCORE")
o = c.o
out = {"gen_env2e1g": [], "gen_default_prefix": [], "kg_out_env2e1g": int(o.isDefined("^KG", "out", "env2e1g")),
       "kg_in_env2e1g": int(o.isDefined("^KG", "in", "env2e1g")), "scratch": int(o.isDefined("^IVGAuditE1"))}
s = ""
while True:
    s = o.nextSubscript(False, "^KG", "gen", "env2e1g", s)
    if not s: break
    out["gen_env2e1g"].append(s)
s = "env2e1-"
while True:
    s = o.nextSubscript(False, "^KG", "gen", 0, s)
    if not s or not str(s).startswith("env2e1-"): break
    out["gen_default_prefix"].append(s)
out["rows"] = {"nodes": c.sql("SELECT COUNT(*) FROM Graph_KG.nodes WHERE node_id %STARTSWITH 'env2e1'")[0][0],
               "edges": c.sql("SELECT COUNT(*) FROM Graph_KG.rdf_edges WHERE s %STARTSWITH 'env2e1' OR graph_id = 'env2e1g'")[0][0],
               "registry": c.sql("SELECT COUNT(*) FROM Graph_KG.embedding_registry WHERE graph_id = 'env2e1g'")[0][0]}
print(json.dumps(out))
c.close()
