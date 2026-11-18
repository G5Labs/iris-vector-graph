"""R1 reviewer probe: does the default route trial alternate native and SQL answers for bug-cyp-104's query?
Creates namespace R1N only, drops it afterwards."""
import json, subprocess, sys, time
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/runs/ivg-cov-a")
import runtime  # fixture constants; puts the pin on sys.path
NS = "R1E"
def irs(script, ns="%SYS"):
    return subprocess.run(["docker", "exec", "-i", runtime.NAME, "iris", "session", "IRIS", "-U", ns],
                          input=script + "\nHalt\n", capture_output=True, text=True, timeout=300).stdout
TAIL = 'Write $Select($System.Status.IsOK(sc):"RESULT OK",1:"RESULT "_$System.Status.GetErrorText(sc)),!'
def drop():
    return irs(f'Set ns="{NS}", dir="/usr/irissys/mgr/{NS.lower()}/", sc=1\n'
        'If ##class(Config.Namespaces).Exists(ns) { Set sc=##class(Config.Namespaces).Delete(ns) }\n'
        'If ##class(Config.Databases).Exists(ns) { Set sc=##class(Config.Databases).Delete(ns) }\n'
        'If ##class(%File).Exists(dir_"IRIS.DAT") { Set sc=##class(SYS.Database).DeleteDatabase(dir) }\n' + TAIL)
def create():
    drop()
    out = irs(f'Set ns="{NS}", dir="/usr/irissys/mgr/{NS.lower()}/"\n'
        'Set ok=##class(%File).CreateDirectoryChain(dir) Set sc=##class(SYS.Database).CreateDatabase(dir) '
        'If $System.Status.IsOK(sc) { Set pdb("Directory")=dir, sc=##class(Config.Databases).Create(ns,.pdb) } '
        'If $System.Status.IsOK(sc) { Set pns("Globals")=ns, pns("Routines")=ns, sc=##class(Config.Namespaces).Create(ns,.pns) } ' + TAIL)
    assert "RESULT OK" in out, out
create()
try:
    import iris.dbapi
    from iris_vector_graph.engine import IRISGraphEngine
    c = iris.dbapi.connect(hostname="127.0.0.1", port=runtime.PORT, namespace=NS, username="_SYSTEM", password="SYS")
    e = IRISGraphEngine(c, embedding_dimension=8, namespace=NS)
    e.initialize_schema()
    out = {}
    out["create_h_ev1"] = e.create_node("ev1", labels=["Evidence"], properties={"note": "unrelated, graph h"}, graph="h")
    out["create_g_a"] = e.create_node("a", labels=["N"], graph="g")
    out["create_g_b"] = e.create_node("b", labels=["N"], graph="g")
    out["create_g_edge"] = e.create_edge("a", "R", "b", graph="g")
    cur = c.cursor()
    cur.execute("SELECT edge_id FROM Graph_KG.rdf_edges WHERE s = 'a' AND graph_id = 'g'")
    eid = cur.fetchall()[0][0]
    out["reify"] = e.reify_edge(eid, reifier_id="ev1")
    def where(nid):
        cur.execute("SELECT %EXACT(COALESCE(graph_id,'')) FROM Graph_KG.nodes WHERE node_id = ?", [nid])
        return sorted(r[0] for r in cur.fetchall())
    out["ev1_graphs_before"] = where("ev1")
    out["h_ev1_before"] = e.get_node("ev1", graph="h")
    out["delete_a_in_g"] = e.delete_node("a", graph="g")
    out["ev1_graphs_after"] = where("ev1")
    out["h_ev1_after"] = e.get_node("ev1", graph="h")
    print(json.dumps(out, default=str))
    cur.close(); c.close()
finally:
    print("drop:", drop().strip()[-12:])
