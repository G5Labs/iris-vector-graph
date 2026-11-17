import sys, json, os, asyncio, threading, socket, time
sys.path.insert(0, sys.argv[1] + '/.g5/uplift/consolidated/iteration-36'); import runtime
from iris_vector_graph.engine import IRISGraphEngine
from iris_vector_graph import bolt_server as bs
import importlib.metadata as md
P='i58d_080853_'; L='I58DL080853'; K='I58DK080853'
Q = {"hop": f"MATCH (a:{L})-[:{K}]->(b) RETURN a.node_id AS id, b.node_id AS t, b.v AS v, b.s AS s ORDER BY id, t",
     "nohop": f"MATCH (n:{L}) RETURN n.node_id AS id, n.v AS v, n.s AS s ORDER BY id",
     "hop_plain": f"MATCH (a:{L})-[:{K}]->(b) RETURN a.node_id AS id, b.node_id AS t",
     "nohop_plain": f"MATCH (n:{L}) RETURN n.node_id AS id, n.v AS v",
     "nohop_typed": f"MATCH (n:{L}) RETURN n.node_id AS id, n.v AS v, n.s AS s"}
out = {"driver": md.version("intersystems-irispython"), "queries": Q}
c = runtime.connect()
def rows(r): return sorted([[repr(v) for v in x] for x in r.rows])
def run(label, eng, q):
    cnt = {"native": 0, "shadow_compare": 0}
    orig_t, orig_s = eng._try_native, eng._shadow_compare
    def t(*a, **k):
        r = orig_t(*a, **k); cnt["native"] += r is not None; return r
    def s(*a, **k):
        cnt["shadow_compare"] += 1; return orig_s(*a, **k)
    eng._try_native = t; eng._shadow_compare = s
    try:
        r = eng.execute_cypher(q, {}); v = {"rows": rows(r), "error": getattr(r, "error", None)}
    except Exception as x:
        v = {"error": repr(x)[:300]}
    v.update(cnt); return v
sqle = runtime.engine(c); nat = IRISGraphEngine(c, embedding_dimension=768)
G = "Graph.KG.Cypher.Gen"
for qk, q in Q.items():
    out[qk] = {"SQL": run("SQL", sqle, q)}
    for mode in ("off", "sync", "job"):
        out[qk]["mode_set_" + mode] = str(nat._iris_obj().classMethodValue(G, "Mode", mode))
        out[qk]["NATIVE_" + mode] = run(mode, nat, q)
        out[qk]["NATIVE_" + mode + "_again"] = run(mode, nat, q)
    os.environ["IVG_CYPHER_SHADOW"] = "1"
    out[qk]["SHADOW_sync"] = (nat._iris_obj().classMethodValue(G, "Mode", "sync"), run("shadow", nat, q))[1]
    os.environ.pop("IVG_CYPHER_SHADOW")
    nat._iris_obj().classMethodValue(G, "Mode", "")
# Bolt with shadow on
import neo4j
os.environ["IVG_CYPHER_SHADOW"] = "1"
c2 = runtime.connect(); e2 = IRISGraphEngine(c2, embedding_dimension=768)
loop = asyncio.new_event_loop(); threading.Thread(target=lambda: (asyncio.set_event_loop(loop), loop.run_forever()), daemon=True).start()
s0 = socket.socket(); s0.bind(("127.0.0.1", 0)); port = s0.getsockname()[1]; s0.close()
srv = asyncio.run_coroutine_threadsafe(bs.start_tcp_bolt_server(lambda: e2, host="127.0.0.1", port=port), loop).result(10)
with neo4j.GraphDatabase.driver(f"bolt://127.0.0.1:{port}", auth=("neo4j", "x")) as d:
    for qk, q in Q.items():
        try:
            with d.session() as s:
                out[qk]["BOLT_SHADOW"] = sorted([[repr(v) for v in r.values()] for r in s.run(q)])
        except Exception as x:
            out[qk]["BOLT_SHADOW"] = repr(x)[:300]
os.environ.pop("IVG_CYPHER_SHADOW")
loop.call_soon_threadsafe(srv.close); time.sleep(0.3); loop.call_soon_threadsafe(loop.stop)
c.close(); c2.close()
json.dump(out, open(sys.argv[2], "w"), indent=1)
for qk in Q:
    base = out[qk]["SQL"]["rows"]
    print(qk, {k: (v.get("rows") == base, v.get("native"), v.get("shadow_compare"), v.get("error")) if isinstance(v, dict) else (v == base if isinstance(v, list) else v) for k, v in out[qk].items()})
