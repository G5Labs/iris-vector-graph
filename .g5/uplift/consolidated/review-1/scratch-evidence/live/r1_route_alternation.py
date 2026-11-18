"""R1 reviewer probe: does the default route trial alternate native and SQL answers for bug-cyp-104's query?
Creates namespace R1N only, drops it afterwards."""
import json, subprocess, sys, time
sys.path.insert(0, "/home/ziniu_wu_g5labs_ai/experiments/model-coverage-uplift-20261117/runs/ivg-cov-a")
import runtime  # fixture constants; puts the pin on sys.path
NS = "R1N"
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
    e = IRISGraphEngine(c, embedding_dimension=8, namespace=NS)  # every native option at its default
    e.initialize_schema()
    e.create_node("r1a", labels=["R1A"], properties={"k": "a"})
    vals = ["", "b", 2, None, "a", 1]
    for i, v in enumerate(vals):
        props = {"k": f"t{i}"}
        if v is not None:
            props["p"] = v
        e.create_node(f"r1t{i}", labels=["R1T"], properties=props)
        e.create_edge("r1a", "R", f"r1t{i}")
    q = "MATCH (x {id: 'r1a'})-[:R]->(b) RETURN b.p AS p ORDER BY b.p"
    out = {"defaults": {"native_cypher": e.native_cypher, "native_route_ms": e.native_route_ms}, "calls": []}
    for i in range(12):
        before = getattr(e, "_native_answers", 0)
        r = e.execute_cypher(q)
        out["calls"].append({"call": i + 1, "native": getattr(e, "_native_answers", 0) - before,
                             "rows": [x[0] for x in r.rows], "error": r.error})
    sqlonly = IRISGraphEngine(c, embedding_dimension=8, namespace=NS, native_cypher=False)
    out["sql_only"] = [x[0] for x in sqlonly.execute_cypher(q).rows]
    out["distinct_answers"] = sorted({json.dumps(x["rows"]) for x in out["calls"]})
    print(json.dumps(out))
    c.close()
finally:
    print("drop:", drop().strip()[-40:])
